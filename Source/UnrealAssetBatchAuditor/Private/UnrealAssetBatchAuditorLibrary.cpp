#include "UnrealAssetBatchAuditorLibrary.h"

#include "AssetCompilingManager.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture.h"
#include "Engine/Texture2D.h"
#include "Materials/MaterialInterface.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstance.h"
#include "MaterialShared.h"
#include "PhysicsEngine/BodySetup.h"
#include "Runtime/Launch/Resources/Version.h"
#include "StaticMeshResources.h"
#include "UObject/SoftObjectPath.h"

namespace
{
FString CollisionTraceFlagToString(const ECollisionTraceFlag Flag)
{
    switch (Flag)
    {
    case CTF_UseDefault: return TEXT("project_default");
    case CTF_UseSimpleAndComplex: return TEXT("simple_and_complex");
    case CTF_UseSimpleAsComplex: return TEXT("use_simple_as_complex");
    case CTF_UseComplexAsSimple: return TEXT("use_complex_as_simple");
    default: return TEXT("unknown");
    }
}

template <typename EnumType>
FString EnumName(const EnumType Value)
{
    const UEnum* Enum = StaticEnum<EnumType>();
    return Enum ? Enum->GetNameStringByValue(static_cast<int64>(Value)) : TEXT("unknown");
}
}

TArray<FStaticMeshAuditMetadata> UUnrealAssetBatchAuditorLibrary::CollectStaticMeshMetadata(
    const TArray<FString>& AssetPaths)
{
    TArray<FStaticMeshAuditMetadata> Results;
    Results.Reserve(AssetPaths.Num());

    for (const FString& AssetPath : AssetPaths)
    {
        FStaticMeshAuditMetadata Result;
        Result.AssetPath = AssetPath;

        const FSoftObjectPath SoftPath(AssetPath);
        UObject* LoadedObject = SoftPath.TryLoad();
        const UStaticMesh* StaticMesh = Cast<UStaticMesh>(LoadedObject);
        if (StaticMesh == nullptr)
        {
            Result.ErrorCode = TEXT("NOT_STATIC_MESH");
            Result.Error = TEXT("Object could not be loaded as UStaticMesh.");
            Results.Add(MoveTemp(Result));
            continue;
        }

        Result.AssetName = StaticMesh->GetName();
        Result.MaterialSlotCount = StaticMesh->GetStaticMaterials().Num();
        TSet<FString> UniqueMaterialPaths;
        TSet<UTexture*> UniqueTextures;
        for (const FStaticMaterial& StaticMaterial : StaticMesh->GetStaticMaterials())
        {
            const UMaterialInterface* Material = StaticMaterial.MaterialInterface;
            if (Material == nullptr)
            {
                ++Result.MissingMaterialSlotCount;
                continue;
            }
            UniqueMaterialPaths.Add(Material->GetPathName());
            TArray<UTexture*> UsedTextures;
            Material->GetUsedTextures(UsedTextures);
            for (UTexture* Texture : UsedTextures)
            {
                if (Texture != nullptr)
                {
                    UniqueTextures.Add(Texture);
                }
            }
        }
        Result.MaterialPaths = UniqueMaterialPaths.Array();
        Result.MaterialPaths.Sort();
        Result.UniqueMaterialCount = Result.MaterialPaths.Num();
        for (UTexture* Texture : UniqueTextures)
        {
            Result.TexturePaths.Add(Texture->GetPathName());
            Result.MaxTextureDimension = FMath::Max(
                Result.MaxTextureDimension,
                FMath::RoundToInt(FMath::Max(Texture->GetSurfaceWidth(), Texture->GetSurfaceHeight())));
        }
        Result.TexturePaths.Sort();
        Result.TextureDependencyCount = Result.TexturePaths.Num();
#if ENGINE_MAJOR_VERSION > 5 || (ENGINE_MAJOR_VERSION == 5 && ENGINE_MINOR_VERSION >= 8)
        Result.bNaniteEnabled = StaticMesh->GetNaniteSettings().bEnabled;
#else
        Result.bNaniteEnabled = StaticMesh->NaniteSettings.bEnabled;
#endif
        Result.LightmapCoordinateIndex = StaticMesh->GetLightMapCoordinateIndex();
        Result.LightmapResolution = StaticMesh->GetLightMapResolution();
        if (const UBodySetup* BodySetup = StaticMesh->GetBodySetup())
        {
            Result.SimpleCollisionPrimitiveCount = BodySetup->AggGeom.GetElementCount();
            Result.CollisionComplexity = CollisionTraceFlagToString(BodySetup->CollisionTraceFlag);
        }
        else
        {
            Result.CollisionComplexity = TEXT("missing_body_setup");
        }

        const FStaticMeshRenderData* RenderData = StaticMesh->GetRenderData();
        if (RenderData == nullptr)
        {
            Result.ErrorCode = TEXT("MISSING_RENDER_DATA");
            Result.Error = TEXT("Static Mesh has no render data.");
            Results.Add(MoveTemp(Result));
            continue;
        }

        Result.LodMetadata.Reserve(RenderData->LODResources.Num());
        if (!RenderData->LODResources.IsEmpty())
        {
            Result.UvChannelCount =
                RenderData->LODResources[0].VertexBuffers.StaticMeshVertexBuffer.GetNumTexCoords();
        }
        for (int32 LODIndex = 0; LODIndex < RenderData->LODResources.Num(); ++LODIndex)
        {
            const FStaticMeshLODResources& LODResource = RenderData->LODResources[LODIndex];
            FStaticMeshAuditLODMetadata LOD;
            LOD.Index = LODIndex;
            LOD.VertexCount = LODResource.GetNumVertices();
            for (const FStaticMeshSection& Section : LODResource.Sections)
            {
                LOD.TriangleCount += Section.NumTriangles;
            }
            Result.LodMetadata.Add(LOD);
        }

        Result.bCollected = true;
        Results.Add(MoveTemp(Result));
    }

    return Results;
}

TArray<FTexture2DAuditMetadata> UUnrealAssetBatchAuditorLibrary::CollectTexture2DMetadata(
    const TArray<FString>& AssetPaths)
{
    TArray<FTexture2DAuditMetadata> Results;
    Results.Reserve(AssetPaths.Num());

    for (const FString& AssetPath : AssetPaths)
    {
        FTexture2DAuditMetadata Result;
        Result.AssetPath = AssetPath;

        const FSoftObjectPath SoftPath(AssetPath);
        UObject* LoadedObject = SoftPath.TryLoad();
        UTexture2D* Texture = Cast<UTexture2D>(LoadedObject);
        if (Texture == nullptr)
        {
            Result.ErrorCode = TEXT("NOT_TEXTURE2D");
            Result.Error = TEXT("Object could not be loaded as UTexture2D.");
            Results.Add(MoveTemp(Result));
            continue;
        }

        FAssetCompilingManager::Get().FinishCompilationForObjects({Texture});
        Result.AssetName = Texture->GetName();
        Result.SourceWidth = Texture->Source.GetSizeX();
        Result.SourceHeight = Texture->Source.GetSizeY();
        if (Result.SourceWidth <= 0 || Result.SourceHeight <= 0)
        {
            Result.ErrorCode = TEXT("MISSING_SOURCE_DATA");
            Result.Error = TEXT("Texture2D has no readable editor source dimensions.");
            Results.Add(MoveTemp(Result));
            continue;
        }

        Result.PlatformWidth = FMath::Max(1, FMath::RoundToInt(Texture->GetSurfaceWidth()));
        Result.PlatformHeight = FMath::Max(1, FMath::RoundToInt(Texture->GetSurfaceHeight()));
        Result.MipCount = FMath::Max(1, Texture->GetNumMips());
        Result.MipGenSettings = EnumName<TextureMipGenSettings>(Texture->MipGenSettings.GetValue());
        Result.TextureGroup = EnumName<TextureGroup>(Texture->LODGroup.GetValue());
        Result.CompressionSettings =
            EnumName<TextureCompressionSettings>(Texture->CompressionSettings.GetValue());
        Result.bSrgb = Texture->SRGB;
        Result.bVirtualTextureStreaming = Texture->VirtualTextureStreaming;
        Result.bNeverStream = Texture->NeverStream;
        Result.bCollected = true;
        Results.Add(MoveTemp(Result));
    }

    return Results;
}

TArray<FMaterialInterfaceAuditMetadata>
UUnrealAssetBatchAuditorLibrary::CollectMaterialInterfaceMetadata(
    const TArray<FString>& AssetPaths)
{
    TArray<FMaterialInterfaceAuditMetadata> Results;
    Results.Reserve(AssetPaths.Num());

    for (const FString& AssetPath : AssetPaths)
    {
        FMaterialInterfaceAuditMetadata Result;
        Result.AssetPath = AssetPath;

        const FSoftObjectPath SoftPath(AssetPath);
        UObject* LoadedObject = SoftPath.TryLoad();
        UMaterialInterface* MaterialInterface = Cast<UMaterialInterface>(LoadedObject);
        if (MaterialInterface == nullptr)
        {
            Result.ErrorCode = TEXT("NOT_MATERIAL_INTERFACE");
            Result.Error = TEXT("Object could not be loaded as UMaterialInterface.");
            Results.Add(MoveTemp(Result));
            continue;
        }

        Result.AssetName = MaterialInterface->GetName();
        const UMaterialInstance* MaterialInstance = Cast<UMaterialInstance>(MaterialInterface);
        Result.MaterialKind = MaterialInstance ? TEXT("material_instance") : TEXT("material");
        const UMaterial* BaseMaterial = MaterialInterface->GetBaseMaterial();
        if (BaseMaterial == nullptr)
        {
            Result.ErrorCode = TEXT("MISSING_BASE_MATERIAL");
            Result.Error = TEXT("Material Interface has no readable base material.");
            Results.Add(MoveTemp(Result));
            continue;
        }
        Result.BaseMaterialPath = BaseMaterial->GetPathName();
        Result.MaterialDomain = EnumName<EMaterialDomain>(BaseMaterial->MaterialDomain.GetValue());
        Result.BlendMode = EnumName<EBlendMode>(MaterialInterface->GetBlendMode());
        Result.bTwoSided = MaterialInterface->IsTwoSided();

        const FMaterialShadingModelField ShadingModels = MaterialInterface->GetShadingModels();
        for (int32 Index = 0; Index < static_cast<int32>(MSM_NUM); ++Index)
        {
            const EMaterialShadingModel ShadingModel =
                static_cast<EMaterialShadingModel>(Index);
            if (ShadingModels.HasShadingModel(ShadingModel))
            {
                Result.ShadingModels.Add(EnumName<EMaterialShadingModel>(ShadingModel));
            }
        }
        if (Result.ShadingModels.IsEmpty())
        {
            Result.ShadingModels.Add(TEXT("MSM_Unlit"));
        }

        if (MaterialInstance != nullptr)
        {
            const UMaterialInterface* Current = MaterialInstance;
            TSet<const UMaterialInterface*> Visited;
            Visited.Add(Current);
            while (const UMaterialInstance* CurrentInstance = Cast<UMaterialInstance>(Current))
            {
                const UMaterialInterface* Parent = CurrentInstance->Parent;
                if (Parent == nullptr)
                {
                    break;
                }
                if (Result.ParentDepth == 0)
                {
                    Result.ParentPath = Parent->GetPathName();
                }
                if (Visited.Contains(Parent))
                {
                    Result.ErrorCode = TEXT("MATERIAL_PARENT_CYCLE");
                    Result.Error = TEXT("Material Instance parent chain contains a cycle.");
                    break;
                }
                Visited.Add(Parent);
                ++Result.ParentDepth;
                Current = Parent;
            }
            if (!Result.ErrorCode.IsEmpty())
            {
                Results.Add(MoveTemp(Result));
                continue;
            }
        }

        TArray<UTexture*> UsedTextures;
        MaterialInterface->GetUsedTextures(UsedTextures);
        TSet<FString> UniqueTexturePaths;
        for (UTexture* Texture : UsedTextures)
        {
            if (Texture == nullptr)
            {
                continue;
            }
            UniqueTexturePaths.Add(Texture->GetPathName());
            Result.MaxTextureDimension = FMath::Max(
                Result.MaxTextureDimension,
                FMath::RoundToInt(
                    FMath::Max(Texture->GetSurfaceWidth(), Texture->GetSurfaceHeight())));
        }
        Result.TexturePaths = UniqueTexturePaths.Array();
        Result.TexturePaths.Sort();
        Result.TextureDependencyCount = Result.TexturePaths.Num();
        Result.bCollected = true;
        Results.Add(MoveTemp(Result));
    }

    return Results;
}
