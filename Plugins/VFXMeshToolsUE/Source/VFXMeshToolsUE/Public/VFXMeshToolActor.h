#pragma once

#include "CoreMinimal.h"
#include "Curves/CurveFloat.h"
#include "GameFramework/Actor.h"
#include "VFXMeshToolActor.generated.h"

class UProceduralMeshComponent;
class UStaticMesh;
class UMaterialInterface;

UENUM(BlueprintType)
enum class EVFXMeshToolMode : uint8 { Spline, Helix, Custom, Fracture, GroundSpikes };
UENUM(BlueprintType)
enum class EVFXPointSpace : uint8 { Local, World };
UENUM(BlueprintType)
enum class EVFXSplineSurface : uint8 { Strip, Cross, Tube };
UENUM(BlueprintType)
enum class EVFXSpikeShape : uint8 { Cone, Crystal, Blade, Mixed };
UENUM(BlueprintType)
enum class EVFXSpikeLayout : uint8 { Line, Ring, Arc };
UENUM(BlueprintType)
enum class EVFXSpikeOrder : uint8 { Sequential, CenterOut, Random };

USTRUCT(BlueprintType)
struct FVFXSplinePath
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spline")
    TArray<FVector> Points;
};

USTRUCT(BlueprintType)
struct FVFXHeightPoint
{
    GENERATED_BODY()
    // Horizontal location; displayed height is sampled from the boundary plus HeightOffset.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Custom")
    FVector2D Position = FVector2D::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Custom")
    float HeightOffset = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Custom", meta=(ClampMin="1"))
    float Radius = 100.0f;
};

USTRUCT(BlueprintType)
struct FVFXSpikeShapeSettings
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes")
    EVFXSpikeShape Shape = EVFXSpikeShape::Mixed;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="1"))
    float Width = 35.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="1"))
    float Depth = 30.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="1"))
    float Height = 150.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="0", ClampMax="0.8"))
    float HeightVariation = 0.25f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="3", ClampMax="16"))
    int32 RadialSides = 6;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="0", ClampMax="35"))
    float TiltVariation = 8.0f;
};

USTRUCT(BlueprintType)
struct FVFXSpikeLayoutSettings
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes")
    EVFXSpikeLayout Mode = EVFXSpikeLayout::Line;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="1", ClampMax="128"))
    int32 Count = 8;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="1"))
    float Spacing = 75.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="1"))
    float Radius = 200.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="0", ClampMax="360"))
    float ArcAngle = 120.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="0"))
    float Jitter = 15.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes")
    int32 Seed = 1;
};

USTRUCT(BlueprintType)
struct FVFXSpikeGrowthSettings
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="0.05"))
    float Duration = 0.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="0"))
    float Stagger = 0.08f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes")
    EVFXSpikeOrder Order = EVFXSpikeOrder::Sequential;
    UPROPERTY(EditAnywhere, Category="Ground Spikes")
    FRuntimeFloatCurve Curve;
};

UCLASS(Blueprintable)
class VFXMESHTOOLSUE_API AVFXMeshToolActor : public AActor
{
    GENERATED_BODY()
public:
    AVFXMeshToolActor();
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void PostLoad() override;
#if WITH_EDITOR
    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="VFX")
    TObjectPtr<USceneComponent> SceneRoot;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="VFX")
    TObjectPtr<UProceduralMeshComponent> MainMesh;
    UPROPERTY(Transient, VisibleInstanceOnly, Category="VFX")
    TArray<TObjectPtr<UProceduralMeshComponent>> GeneratedPieces;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="VFX")
    EVFXMeshToolMode Mode = EVFXMeshToolMode::GroundSpikes;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="VFX")
    TObjectPtr<UMaterialInterface> Material;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spline")
    EVFXPointSpace PointSpace = EVFXPointSpace::Local;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spline")
    TArray<FVFXSplinePath> SplinePaths;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spline")
    EVFXSplineSurface SplineSurface = EVFXSplineSurface::Strip;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spline", meta=(ClampMin="1"))
    float SplineWidth = 50.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spline", meta=(ClampMin="1", ClampMax="32"))
    int32 SplineSamplesPerSegment = 8;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spline", meta=(ClampMin="3", ClampMax="16"))
    int32 SplineTubeSides = 6;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Helix", meta=(ClampMin="1"))
    float HelixHeight = 300.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Helix", meta=(ClampMin="1"))
    float HelixRadius = 100.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Helix", meta=(ClampMin="0.1"))
    float HelixTurns = 2.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Helix", meta=(ClampMin="3", ClampMax="512"))
    int32 HelixSegments = 64;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Helix", meta=(ClampMin="3", ClampMax="16"))
    int32 HelixSides = 6;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Helix", meta=(ClampMin="1"))
    float HelixTubeRadius = 12.0f;
    // X-axis: normalized height, Y-axis: complete horizontal section scale.
    UPROPERTY(EditAnywhere, Category="Helix")
    FRuntimeFloatCurve HelixProfile;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Custom")
    TArray<FVector> CustomBoundary;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Custom")
    TArray<FVFXHeightPoint> CustomHeightPoints;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Custom")
    bool bIrregularEdge = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Custom", meta=(ClampMin="0"))
    float IrregularAmplitude = 12.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Custom", meta=(ClampMin="1", ClampMax="32"))
    int32 EdgeSubdivisions = 8;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Custom", meta=(ClampMin="0.1"))
    float EdgeFrequency = 2.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Custom")
    int32 IrregularSeed = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Custom", meta=(ClampMin="1", ClampMax="16"))
    int32 CustomSubdivision = 4;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fracture")
    TObjectPtr<UStaticMesh> FractureSource;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fracture", meta=(ClampMin="1", ClampMax="64"))
    int32 FragmentCount = 6;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fracture", meta=(ClampMin="0.1"))
    float FragmentThickness = 5.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fracture")
    int32 FractureSeed = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fracture")
    float FracturePreviewSeparation = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes")
    FVFXSpikeShapeSettings SpikeShape;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes")
    FVFXSpikeLayoutSettings SpikeLayout;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes")
    FVFXSpikeGrowthSettings SpikeGrowth;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes")
    bool bPlayGrowth = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes")
    bool bLoopGrowth = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground Spikes", meta=(ClampMin="0"))
    float PreviewGrowthTime = 100.0f;

    UFUNCTION(BlueprintCallable, CallInEditor, Category="VFX")
    void Rebuild();
    UFUNCTION(BlueprintCallable, Category="VFX|Spline")
    void SetPointSpace(EVFXPointSpace NewSpace);
    UFUNCTION(BlueprintCallable, Category="VFX|Ground Spikes")
    void SetGrowthTime(float Seconds);
    UFUNCTION(BlueprintPure, Category="VFX|Ground Spikes")
    float GetGrowthDuration() const;
    UFUNCTION(BlueprintPure, Category="VFX")
    int32 GetGeneratedPieceCount() const { return GeneratedPieces.Num(); }

private:
    UPROPERTY(Transient)
    EVFXPointSpace LastAppliedPointSpace = EVFXPointSpace::Local;
    TArray<float> SpikeStartTimes;
    float GrowthClock = 0.0f;
    void ClearPieces();
    UProceduralMeshComponent* MakePiece(const FString& Name, const FVector& Position);
    void BuildSpline();
    void BuildHelix();
    void BuildCustom();
    void BuildFracture();
    void BuildSpikes();
    void UpdateGrowth(float Seconds);
};
