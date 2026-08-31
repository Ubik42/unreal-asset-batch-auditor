#include "UnrealAssetBatchAuditorLibrary.h"

#include "Engine/StaticMesh.h"
#include "Engine/Texture.h"
#include "Materials/MaterialInterface.h"
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
