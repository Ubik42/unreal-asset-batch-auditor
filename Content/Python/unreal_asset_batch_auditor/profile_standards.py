from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .contracts import PROFILE_VERSION_V3, AuditProfile, ContractError
from .texture_contracts import TEXTURE_PROFILE_VERSION, TextureAuditProfile

AssetType = Literal["static_mesh", "texture2d"]
PROFILE_EDITOR_VIEW_VERSION = "unreal-profile-editor-view@1.0.0"


@dataclass(frozen=True)
class ProfileEditorField:
    path: str
    label: str
    kind: str
    value: Any
    options: tuple[str, ...] = ()
    minimum: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "label": self.label,
            "kind": self.kind,
            "value": self.value,
            "options": list(self.options),
            "minimum": self.minimum,
        }


@dataclass(frozen=True)
class ProfileValidation:
    valid: bool
    asset_type: AssetType | None
    errors: dict[str, str]


@dataclass(frozen=True)
class ProfileChange:
    path: str
    change: Literal["added", "changed", "removed"]
    before: Any = None
    after: Any = None


_FIELD_LABELS = {
    "profile_id": "标准 ID",
    "profile_version": "标准版本",
    "schema_version": "Schema 版本",
    "rules": "检查规则",
    "enabled": "是否启用",
    "severity": "问题级别",
    "max_lod0": "LOD0 上限",
    "max_count": "数量上限",
    "min_count": "数量下限",
    "max_size": "尺寸上限",
    "expected": "期望状态",
    "allowed_values": "允许值",
    "allowed_combinations": "压缩与色彩空间组合",
    "description": "用途说明",
    "max_missing_slots": "缺失槽上限",
    "min_primitive_count": "最少简单碰撞体",
    "allow_complex_as_simple": "允许 Complex As Simple",
    "required": "是否强制",
    "min_uv_channel_count": "最少 UV 通道",
    "min_resolution": "最低 Lightmap 分辨率",
    "required_prefixes": "允许名前缀",
    "pattern": "完整命名正则",
    "allowed_roots": "允许目录根",
    "forbidden_segments": "禁用目录段",
    "srgb": "sRGB",
}

_RULE_LABELS = {
    "triangle_budget": "三角形预算",
    "vertex_budget": "顶点预算",
    "material_slots": "材质槽数量",
    "lod_count": "LOD 数量",
    "nanite": "Nanite 状态",
    "simple_collision": "简单碰撞",
    "lightmap_uv": "Lightmap UV",
    "lightmap_resolution": "Lightmap 分辨率",
    "object_name": "资产命名",
    "package_path": "项目目录",
    "missing_materials": "缺失材质",
    "unique_materials": "唯一材质数量",
    "texture_dependencies": "纹理依赖数量",
    "texture_dimension": "依赖纹理尺寸",
    "source_dimension": "源纹理尺寸",
    "power_of_two": "2 次幂尺寸",
    "mip_count": "Mip 数量",
    "texture_group": "Texture Group",
    "compression_color_space": "压缩与色彩空间",
    "virtual_texture": "Virtual Texture",
    "streaming": "纹理流送",
}


def asset_type_for(raw: dict[str, Any]) -> AssetType:
    schema = raw.get("schema_version")
    if schema == PROFILE_VERSION_V3:
        return "static_mesh"
    if schema == TEXTURE_PROFILE_VERSION:
        return "texture2d"
    raise ContractError(f"unsupported profile schema_version: {schema!r}")


def validate_profile(raw: dict[str, Any]) -> ProfileValidation:
    try:
        _validate_identity(raw)
        kind = asset_type_for(raw)
        if kind == "static_mesh":
            AuditProfile.from_dict(raw)
        else:
            TextureAuditProfile.from_dict(raw)
        return ProfileValidation(True, kind, {})
    except (ContractError, KeyError, TypeError, ValueError) as exc:
        message = str(exc)
        path = _error_path(message)
        return ProfileValidation(False, None, {path: _localize_error(path, message)})


def build_profile_editor_view(source_path: str | Path) -> dict[str, Any]:
    source = _read_object(source_path)
    validation = validate_profile(source)
    if not validation.valid or validation.asset_type is None:
        raise ContractError(next(iter(validation.errors.values())))
    identity = [
        _field("profile_id", source["profile_id"]),
        _field("profile_version", source["profile_version"]),
        _field("description", source.get("description", "")),
    ]
    rule_rows: list[dict[str, Any]] = []
    for rule_id, rule in source["rules"].items():
        fields = [
            _field(f"rules.{rule_id}.{name}", value)
            for name, value in rule.items()
        ]
        rule_rows.append(
            {
                "rule_id": rule_id,
                "label": _RULE_LABELS.get(rule_id, rule_id),
                "fields": [item.to_dict() for item in fields],
            }
        )
    return {
        "schema_version": PROFILE_EDITOR_VIEW_VERSION,
        "asset_type": validation.asset_type,
        "asset_type_label": "模型交付" if validation.asset_type == "static_mesh" else "纹理交付",
        "source_path": str(Path(source_path)),
        "profile_id": source["profile_id"],
        "profile_version": source["profile_version"],
        "identity_fields": [item.to_dict() for item in identity],
        "rules": rule_rows,
    }


def evaluate_profile_edit(
    source_path: str | Path,
    values: dict[str, Any],
    *,
    save: bool = False,
    project_profile_root: str | Path | None = None,
) -> dict[str, Any]:
    source_file = Path(source_path).resolve()
    source = _read_object(source_file)
    descriptors = {
        field["path"]: field
        for field in _all_editor_fields(build_profile_editor_view(source_file))
    }
    draft = copy.deepcopy(source)
    errors: dict[str, str] = {}
    for path, raw_value in values.items():
        descriptor = descriptors.get(path)
        if descriptor is None:
            errors[path] = f"{path}：当前 Profile 不支持该编辑字段"
            continue
        try:
            _set_path(draft, path, _parse_editor_value(descriptor, raw_value))
        except (TypeError, ValueError) as exc:
            errors[path] = f"{descriptor['label']}：{exc}"
    if not isinstance(draft.get("profile_id"), str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{2,63}", draft["profile_id"]
    ):
        errors.setdefault(
            "profile_id", "标准 ID：必须使用 3–64 位英文小写字母、数字或连字符"
        )
    if not isinstance(draft.get("profile_version"), str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+", draft["profile_version"]
    ):
        errors.setdefault("profile_version", "标准版本：必须使用 x.y.z 语义版本")
    validation = validate_profile(draft)
    for path, message in validation.errors.items():
        errors.setdefault(path, message)
    changes = diff_profiles(source, draft) if not errors else []
    result: dict[str, Any] = {
        "schema_version": PROFILE_EDITOR_VIEW_VERSION,
        "status": "invalid" if errors else "ready",
        "errors": errors,
        "changes": [
            {
                "path": item.path,
                "label": _label_for_path(item.path),
                "change": item.change,
                "before": _display_value(item.before),
                "after": _display_value(item.after),
            }
            for item in changes
        ],
        "change_count": len(changes),
    }
    if save and not errors:
        if project_profile_root is None:
            raise ContractError("保存项目标准时缺少项目目录边界")
        root = Path(project_profile_root).resolve()
        if source_file.parent != root:
            raise ContractError("只能保存项目自有标准；内置模板保持只读")
        save_project_profile(draft, source_file)
        result["status"] = "saved"
        result["profile_path"] = str(source_file)
        result["profile_id"] = draft["profile_id"]
        result["profile_version"] = draft["profile_version"]
    return result


def diff_profiles(source: dict[str, Any], draft: dict[str, Any]) -> list[ProfileChange]:
    changes: list[ProfileChange] = []

    def walk(path: str, before: Any, after: Any) -> None:
        if isinstance(before, dict) and isinstance(after, dict):
            for key in sorted(set(before) | set(after)):
                child = f"{path}.{key}" if path else key
                if key not in before:
                    changes.append(ProfileChange(child, "added", after=after[key]))
                elif key not in after:
                    changes.append(ProfileChange(child, "removed", before=before[key]))
                else:
                    walk(child, before[key], after[key])
            return
        if before != after:
            changes.append(ProfileChange(path, "changed", before, after))

    walk("", source, draft)
    return changes


def clone_as_project_profile(
    source_path: str | Path,
    project_profile_root: str | Path,
    *,
    requested_id: str | None = None,
    requested_version: str = "1.0.0",
) -> Path:
    source = _read_object(source_path)
    validation = validate_profile(source)
    if not validation.valid:
        raise ContractError(next(iter(validation.errors.values())))
    draft = copy.deepcopy(source)
    base_id = requested_id or f"{source['profile_id']}-project"
    root = Path(project_profile_root)
    root.mkdir(parents=True, exist_ok=True)
    profile_id = _unique_profile_id(root, _safe_profile_id(base_id))
    draft["profile_id"] = profile_id
    draft["profile_version"] = requested_version
    source_description = str(draft.get("description", "")).strip()
    draft["description"] = (
        f"项目自有验收标准；复制自 {source['profile_id']}。"
        + (f" {source_description}" if source_description else "")
    )
    suffix = "v3" if validation.asset_type == "static_mesh" else "v1"
    return save_project_profile(draft, root / f"{profile_id}.{suffix}.json")


def save_project_profile(raw: dict[str, Any], destination: str | Path) -> Path:
    validation = validate_profile(raw)
    if not validation.valid:
        raise ContractError(next(iter(validation.errors.values())))
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(raw, ensure_ascii=False, indent=2) + "\n"
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, target)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return target


def _read_object(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ContractError("Profile 根节点必须是对象")
    return raw


def _validate_identity(raw: dict[str, Any]) -> None:
    profile_id = raw.get("profile_id")
    version = raw.get("profile_version")
    if not isinstance(profile_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", profile_id):
        raise ContractError("profile_id must use 3-64 lowercase letters, numbers, or hyphens")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ContractError("profile_version must use semantic version x.y.z")


def _field(path: str, value: Any) -> ProfileEditorField:
    leaf = path.split(".")[-1]
    if leaf == "severity":
        return ProfileEditorField(path, _label_for_path(path), "enum", value, ("info", "warning", "error"))
    if leaf == "expected":
        return ProfileEditorField(path, _label_for_path(path), "enum", value, ("enabled", "disabled", "any"))
    if leaf == "allowed_combinations":
        text = "; ".join(
            f"{item['compression']}|{'srgb' if item['srgb'] else 'linear'}" for item in value
        )
        return ProfileEditorField(path, _label_for_path(path), "compression_list", text)
    if isinstance(value, bool):
        return ProfileEditorField(path, _label_for_path(path), "boolean", value)
    if isinstance(value, int):
        minimum = 0 if leaf in {"max_missing_slots", "min_primitive_count"} else 1
        return ProfileEditorField(path, _label_for_path(path), "integer", value, minimum=minimum)
    if isinstance(value, list):
        return ProfileEditorField(path, _label_for_path(path), "string_list", ", ".join(value))
    if value is None:
        return ProfileEditorField(path, _label_for_path(path), "nullable_string", "")
    return ProfileEditorField(path, _label_for_path(path), "string", str(value))


def _all_editor_fields(view: dict[str, Any]) -> list[dict[str, Any]]:
    fields = list(view["identity_fields"])
    for rule in view["rules"]:
        fields.extend(rule["fields"])
    return fields


def _parse_editor_value(descriptor: dict[str, Any], value: Any) -> Any:
    kind = descriptor["kind"]
    if kind == "boolean":
        if not isinstance(value, bool):
            raise TypeError("必须使用开关")
        return value
    text = str(value).strip()
    if kind == "integer":
        if not re.fullmatch(r"-?[0-9]+", text):
            raise ValueError("必须填写整数")
        parsed = int(text)
        minimum = descriptor.get("minimum")
        if minimum is not None and parsed < minimum:
            raise ValueError(f"不能小于 {minimum}")
        return parsed
    if kind == "enum":
        if text not in descriptor["options"]:
            raise ValueError("请选择有效选项")
        return text
    if kind == "string_list":
        items = [item.strip() for item in text.split(",") if item.strip()]
        if not items:
            raise ValueError("至少填写一项，使用英文逗号分隔")
        return items
    if kind == "compression_list":
        combinations = []
        for index, item in enumerate(part.strip() for part in text.split(";") if part.strip()):
            pieces = [piece.strip() for piece in item.split("|")]
            if len(pieces) != 2 or pieces[1] not in {"srgb", "linear"} or not pieces[0]:
                raise ValueError(f"第 {index + 1} 项应写成 TC_Default|srgb 或 TC_Normalmap|linear")
            combinations.append({"compression": pieces[0], "srgb": pieces[1] == "srgb"})
        if not combinations:
            raise ValueError("至少填写一种压缩与色彩空间组合")
        return combinations
    if kind == "nullable_string":
        return text or None
    if not text:
        raise ValueError("不能为空")
    return text


def _set_path(root: dict[str, Any], path: str, value: Any) -> None:
    segments = path.split(".")
    cursor = root
    for segment in segments[:-1]:
        cursor = cursor[segment]
    cursor[segments[-1]] = value


def _label_for_path(path: str) -> str:
    segments = path.split(".")
    leaf = segments[-1]
    if len(segments) >= 3 and segments[0] == "rules":
        return f"{_RULE_LABELS.get(segments[1], segments[1])} · {_FIELD_LABELS.get(leaf, leaf)}"
    return _FIELD_LABELS.get(leaf, leaf)


def _display_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "启用" if value else "关闭"
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _safe_profile_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower()).strip("-")
    if not normalized:
        raise ContractError("标准 ID 只能包含英文小写字母、数字和连字符")
    return normalized


def _unique_profile_id(root: Path, base: str) -> str:
    candidate = base
    index = 2
    existing = {path.name.lower() for path in root.glob("*.json")}
    while any(name.startswith(f"{candidate}.") for name in existing):
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def _error_path(message: str) -> str:
    match = re.search(r"(?:field: |^)([a-z_][a-z0-9_.\[\]]*)", message)
    if match:
        return match.group(1)
    if "schema_version" in message:
        return "schema_version"
    return "profile"


def _localize_error(path: str, message: str) -> str:
    leaf = re.sub(r"\[\d+\]", "", path).split(".")[-1]
    label = _FIELD_LABELS.get(leaf, path)
    translations = {
        "must be a non-empty string": "不能为空",
        "must be an integer": "必须是整数",
        "must be a boolean": "必须是开关值",
        "must be >=": "不能小于",
        "must be info, warning, or error": "必须选择提示、警告或错误",
        "missing required field": "缺少必填字段",
        "unsupported": "版本不受支持",
        "must use 3-64 lowercase letters, numbers, or hyphens": "必须使用 3–64 位英文小写字母、数字或连字符",
        "must use semantic version x.y.z": "必须使用 x.y.z 语义版本",
    }
    detail = message
    for english, chinese in translations.items():
        if english in message:
            detail = chinese
            if english == "must be >=":
                detail += message.split(english, 1)[1]
            break
    return f"{label}：{detail}"


__all__ = [
    "PROFILE_EDITOR_VIEW_VERSION",
    "ProfileChange",
    "ProfileEditorField",
    "ProfileValidation",
    "asset_type_for",
    "build_profile_editor_view",
    "clone_as_project_profile",
    "diff_profiles",
    "evaluate_profile_edit",
    "save_project_profile",
    "validate_profile",
]
