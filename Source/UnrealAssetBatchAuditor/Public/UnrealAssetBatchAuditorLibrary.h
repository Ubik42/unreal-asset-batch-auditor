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
    TArray<FString> MaterialPaths;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 MissingMaterialSlotCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 UniqueMaterialCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    TArray<FString> TexturePaths;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 TextureDependencyCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 MaxTextureDimension = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    bool bNaniteEnabled = false;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 SimpleCollisionPrimitiveCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString CollisionComplexity;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 UvChannelCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 LightmapCoordinateIndex = -1;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 LightmapResolution = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    bool bCollected = false;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString ErrorCode;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString Error;
};

USTRUCT(BlueprintType)
struct FTexture2DAuditMetadata
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString AssetPath;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString AssetName;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 SourceWidth = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 SourceHeight = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 PlatformWidth = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 PlatformHeight = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    int32 MipCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString MipGenSettings;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString TextureGroup;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    FString CompressionSettings;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    bool bSrgb = false;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    bool bVirtualTextureStreaming = false;

    UPROPERTY(BlueprintReadOnly, Category = "Asset Audit")
    bool bNeverStream = false;

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
 * Material dependency facts come from UMaterialInterface::GetUsedTextures in the current Editor;
 * they are not a cooked dependency graph or a runtime GPU-cost measurement. Passing explicit object
 * paths keeps scan scope reviewable.
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

    UFUNCTION(BlueprintCallable, Category = "Asset Audit")
    static TArray<FTexture2DAuditMetadata> CollectTexture2DMetadata(
        const TArray<FString>& AssetPaths);
};
