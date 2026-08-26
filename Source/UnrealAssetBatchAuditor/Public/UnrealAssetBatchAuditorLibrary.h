#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "UnrealAssetBatchAuditorLibrary.generated.h"

USTRUCT(BlueprintType)
struct FStaticMeshAuditLODMetadata
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 Index = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int64 TriangleCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int64 VertexCount = 0;
};

USTRUCT(BlueprintType)
struct FStaticMeshAuditMetadata
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString AssetPath;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString AssetName;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    TArray<FStaticMeshAuditLODMetadata> LodMetadata;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 MaterialSlotCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    bool bNaniteEnabled = false;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    bool bCollected = false;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString ErrorCode;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString Error;
};

/**
 * Read-only Editor boundary used by Python orchestration.
 *
 * This class intentionally exposes no SavePackage, build, Nanite toggle, or asset mutation API.
 * Passing explicit object paths keeps scan scope reviewable. A later optimized implementation may
 * replace the internals without changing the Python-facing batch contract.
 */
UCLASS()
class UNREALASSETBATCHAUDITOR_API UUnrealAssetBatchAuditorLibrary final
    : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Asset Audit")
    static TArray<FStaticMeshAuditMetadata> CollectStaticMeshMetadata(
        const TArray<FString>& AssetPaths);
};
