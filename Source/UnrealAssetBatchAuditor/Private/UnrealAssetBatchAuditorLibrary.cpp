#include "UnrealAssetBatchAuditorLibrary.h"

#include "Engine/StaticMesh.h"
#include "Runtime/Launch/Resources/Version.h"
#include "StaticMeshResources.h"
#include "UObject/SoftObjectPath.h"

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
#if ENGINE_MAJOR_VERSION > 5 || (ENGINE_MAJOR_VERSION == 5 && ENGINE_MINOR_VERSION >= 8)
        Result.bNaniteEnabled = StaticMesh->GetNaniteSettings().bEnabled;
#else
        Result.bNaniteEnabled = StaticMesh->NaniteSettings.bEnabled;
#endif

        const FStaticMeshRenderData* RenderData = StaticMesh->GetRenderData();
        if (RenderData == nullptr)
        {
            Result.ErrorCode = TEXT("MISSING_RENDER_DATA");
            Result.Error = TEXT("Static Mesh has no render data.");
            Results.Add(MoveTemp(Result));
            continue;
        }

        Result.LodMetadata.Reserve(RenderData->LODResources.Num());
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
