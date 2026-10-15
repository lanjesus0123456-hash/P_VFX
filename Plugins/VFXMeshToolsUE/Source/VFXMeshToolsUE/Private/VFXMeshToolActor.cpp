#include "VFXMeshToolActor.h"
#include "VFXMeshToolGeometry.h"
#include "Components/SceneComponent.h"
#include "ProceduralMeshComponent.h"
#include "UObject/UnrealType.h"

AVFXMeshToolActor::AVFXMeshToolActor()
{
    PrimaryActorTick.bCanEverTick = true;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("VFXRoot"));
    SetRootComponent(SceneRoot);
    MainMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("VFXMainMesh"));
    MainMesh->SetupAttachment(SceneRoot);
    MainMesh->bUseAsyncCooking = true;
    SplinePaths.SetNum(1);
    SplinePaths[0].Points = { FVector(-100, 0, 0), FVector(0, 0, 50), FVector(100, 0, 0) };
    CustomBoundary = { FVector(-100, -100, 0), FVector(100, -100, 0),
                       FVector(100, 100, 0), FVector(-100, 100, 0) };
    HelixProfile.GetRichCurve()->AddKey(0.0f, 1.0f);
    HelixProfile.GetRichCurve()->AddKey(1.0f, 1.0f);
    SpikeGrowth.Curve.GetRichCurve()->AddKey(0.0f, 0.0f);
    SpikeGrowth.Curve.GetRichCurve()->AddKey(1.0f, 1.0f);
}

void AVFXMeshToolActor::PostLoad()
{
    Super::PostLoad();
    LastAppliedPointSpace = PointSpace;
}

void AVFXMeshToolActor::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    Rebuild();
}

void AVFXMeshToolActor::BeginPlay()
{
    Super::BeginPlay();
    Rebuild();
    GrowthClock = 0.0f;
    if (Mode == EVFXMeshToolMode::GroundSpikes && bPlayGrowth) UpdateGrowth(0.0f);
}

void AVFXMeshToolActor::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (Mode != EVFXMeshToolMode::GroundSpikes || !bPlayGrowth) return;
    GrowthClock += FMath::Max(0.0f, DeltaSeconds);
    const float Duration = GetGrowthDuration();
    UpdateGrowth(bLoopGrowth && Duration > KINDA_SMALL_NUMBER
        ? FMath::Fmod(GrowthClock, Duration) : GrowthClock);
}

#if WITH_EDITOR
void AVFXMeshToolActor::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);
    if (PropertyChangedEvent.GetPropertyName() == GET_MEMBER_NAME_CHECKED(AVFXMeshToolActor, PointSpace))
        SetPointSpace(PointSpace);
    else Rebuild();
}
#endif

void AVFXMeshToolActor::SetPointSpace(EVFXPointSpace NewSpace)
{
    if (NewSpace != LastAppliedPointSpace)
    {
        for (FVFXSplinePath& Path : SplinePaths)
            for (FVector& Point : Path.Points)
                Point = NewSpace == EVFXPointSpace::World
                    ? GetActorTransform().TransformPosition(Point)
                    : GetActorTransform().InverseTransformPosition(Point);
        LastAppliedPointSpace = NewSpace;
    }
    PointSpace = NewSpace;
    Rebuild();
}

void AVFXMeshToolActor::ClearPieces()
{
    for (UProceduralMeshComponent* Piece : GeneratedPieces)
        if (IsValid(Piece)) Piece->DestroyComponent();
    GeneratedPieces.Empty();
    SpikeStartTimes.Empty();
}

UProceduralMeshComponent* AVFXMeshToolActor::MakePiece(const FString& Name, const FVector& Position)
{
    UProceduralMeshComponent* Piece = NewObject<UProceduralMeshComponent>(this, NAME_None, RF_Transient);
    Piece->SetupAttachment(SceneRoot);
    Piece->CreationMethod = EComponentCreationMethod::UserConstructionScript;
    Piece->ComponentTags.Add(FName(*Name));
    Piece->SetRelativeLocation(Position);
    Piece->bUseAsyncCooking = true;
    Piece->SetMaterial(0, Material);
    Piece->RegisterComponent();
    GeneratedPieces.Add(Piece);
    return Piece;
}

void AVFXMeshToolActor::Rebuild()
{
    if (!SceneRoot || !MainMesh) return;
    ClearPieces();
    MainMesh->ClearAllMeshSections();
    MainMesh->SetMaterial(0, Material);
    switch (Mode)
    {
    case EVFXMeshToolMode::Spline: BuildSpline(); break;
    case EVFXMeshToolMode::Helix: BuildHelix(); break;
    case EVFXMeshToolMode::Custom: BuildCustom(); break;
    case EVFXMeshToolMode::Fracture: BuildFracture(); break;
    case EVFXMeshToolMode::GroundSpikes: BuildSpikes(); break;
    }
}

void AVFXMeshToolActor::SetGrowthTime(float Seconds)
{
    GrowthClock = FMath::Max(0.0f, Seconds);
    UpdateGrowth(GrowthClock);
}

float AVFXMeshToolActor::GetGrowthDuration() const
{
    if (SpikeStartTimes.IsEmpty()) return FMath::Max(0.05f, SpikeGrowth.Duration);
    float MaxStart = 0.0f;
    for (float T : SpikeStartTimes) MaxStart = FMath::Max(MaxStart, T);
    return MaxStart + FMath::Max(0.05f, SpikeGrowth.Duration);
}

void AVFXMeshToolActor::UpdateGrowth(float Seconds)
{
    const FRichCurve* Curve = SpikeGrowth.Curve.GetRichCurveConst();
    const float Duration = FMath::Max(0.05f, SpikeGrowth.Duration);
    for (int32 I = 0; I < GeneratedPieces.Num() && I < SpikeStartTimes.Num(); ++I)
    {
        const float Relative = Seconds - SpikeStartTimes[I];
        const float T = FMath::Clamp(Relative / Duration, 0.0f, 1.0f);
        const float Scale = Relative < 0.0f ? 0.001f :
            FMath::Max(0.001f, Curve->Eval(T, T));
        GeneratedPieces[I]->SetRelativeScale3D(FVector(1.0f, 1.0f, Scale));
    }
}

