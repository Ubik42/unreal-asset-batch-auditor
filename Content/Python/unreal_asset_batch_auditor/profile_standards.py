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
    "ProfileChange",
    "ProfileValidation",
    "asset_type_for",
    "clone_as_project_profile",
    "diff_profiles",
    "save_project_profile",
    "validate_profile",
]
