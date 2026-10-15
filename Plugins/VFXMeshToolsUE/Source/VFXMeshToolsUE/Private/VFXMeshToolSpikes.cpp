#include "VFXMeshToolActor.h"
#include "VFXMeshToolGeometry.h"
#include "ProceduralMeshComponent.h"

static FVector SpikeRingPoint(int32 Index, int32 Sides, float Width,
                              float Depth, float Height, float Scale,
                              EVFXSpikeShape Shape)
{
    float Angle = 2.0f * PI * Index / Sides;
    if (Shape == EVFXSpikeShape::Blade) Angle += PI * 0.25f;
    const float X = Shape == EVFXSpikeShape::Blade
        ? FMath::Sign(FMath::Cos(Angle)) * Width * 0.5f
        : FMath::Cos(Angle) * Width * 0.5f;
    const float Y = Shape == EVFXSpikeShape::Blade
        ? FMath::Sign(FMath::Sin(Angle)) * Depth * 0.5f
        : FMath::Sin(Angle) * Depth * 0.5f;
    return FVector(X * Scale, Y * Scale, Height);
}

static FVFXProcData MakeSpike(EVFXSpikeShape Shape, float Width,
                              float Depth, float Height, int32 RequestedSides)
{
    FVFXProcData Data;
    const int32 Sides = Shape == EVFXSpikeShape::Blade ? 4 :
        FMath::Clamp(RequestedSides, 3, 16);
    const bool bShoulder = Shape != EVFXSpikeShape::Cone;
    const float ShoulderZ = Height * (Shape == EVFXSpikeShape::Blade ? 0.62f : 0.5f);
    const float ShoulderScale = Shape == EVFXSpikeShape::Blade ? 0.48f : 0.72f;
    const FVector Apex(Shape == EVFXSpikeShape::Blade ? Width * 0.15f : 0.0f, 0, Height);
    const FLinearColor Color = Shape == EVFXSpikeShape::Crystal
        ? FLinearColor(0.3f, 0.8f, 1.0f) : Shape == EVFXSpikeShape::Blade
        ? FLinearColor(0.85f, 0.55f, 0.35f) : FLinearColor(0.75f, 0.72f, 0.65f);
    for (int32 I = 0; I < Sides; ++I)
    {
        const float U0 = static_cast<float>(I) / Sides, U1 = static_cast<float>(I + 1) / Sides;
        const FVector A = SpikeRingPoint(I, Sides, Width, Depth, 0, 1, Shape);
        const FVector B = SpikeRingPoint(I + 1, Sides, Width, Depth, 0, 1, Shape);
        if (!bShoulder)
            Data.Tri(A, B, Apex, FVector2D(U0, 0), FVector2D(U1, 0),
                     FVector2D((U0 + U1) * 0.5f, 1), Color);
        else
        {
            const FVector C = SpikeRingPoint(I, Sides, Width, Depth,
                ShoulderZ, ShoulderScale, Shape);
            const FVector D = SpikeRingPoint(I + 1, Sides, Width, Depth,
                ShoulderZ, ShoulderScale, Shape);
            Data.Quad(A, B, D, C, FVector2D(U0, 0), FVector2D(U1, 0),
                      FVector2D(U1, ShoulderZ / Height),
                      FVector2D(U0, ShoulderZ / Height), Color);
            Data.Tri(C, D, Apex, FVector2D(U0, ShoulderZ / Height),
                     FVector2D(U1, ShoulderZ / Height),
                     FVector2D((U0 + U1) * 0.5f, 1), Color);
        }
        Data.Tri(B, A, FVector::ZeroVector,
                 FVector2D(B.X / Width + 0.5f, B.Y / Depth + 0.5f),
                 FVector2D(A.X / Width + 0.5f, A.Y / Depth + 0.5f),
                 FVector2D(0.5f, 0.5f), Color);
    }
    return Data;
}

void AVFXMeshToolActor::BuildSpikes()
{
    const int32 Count = FMath::Clamp(SpikeLayout.Count, 1, 128);
    TArray<int32> Order;
    for (int32 I = 0; I < Count; ++I) Order.Add(I);
    if (SpikeGrowth.Order == EVFXSpikeOrder::CenterOut)
    {
        const float Center = (Count - 1) * 0.5f;
        Order.Sort([Center](int32 A, int32 B)
        {
            const float DA = FMath::Abs(A - Center), DB = FMath::Abs(B - Center);
            return DA == DB ? A < B : DA < DB;
        });
    }
    else if (SpikeGrowth.Order == EVFXSpikeOrder::Random)
    {
        FRandomStream Shuffle(SpikeLayout.Seed ^ 0x53A71);
        for (int32 I = Count - 1; I > 0; --I)
            Order.Swap(I, Shuffle.RandRange(0, I));
    }
    TArray<int32> Rank;
    Rank.SetNum(Count);
    for (int32 I = 0; I < Count; ++I) Rank[Order[I]] = I;
    FRandomStream Random(SpikeLayout.Seed);
    for (int32 I = 0; I < Count; ++I)
    {
        float Angle = 0.0f;
        FVector Position = FVector::ZeroVector;
        if (SpikeLayout.Mode == EVFXSpikeLayout::Line)
            Position.X = (I - (Count - 1) * 0.5f) * FMath::Max(1.0f, SpikeLayout.Spacing);
        else
        {
            const float T = SpikeLayout.Mode == EVFXSpikeLayout::Ring
                ? static_cast<float>(I) / Count
                : Count == 1 ? 0.5f : static_cast<float>(I) / (Count - 1);
            Angle = SpikeLayout.Mode == EVFXSpikeLayout::Ring ? T * 360.0f
                : (T - 0.5f) * FMath::Clamp(SpikeLayout.ArcAngle, 0.0f, 360.0f);
            Position = FVector(FMath::Sin(FMath::DegreesToRadians(Angle)),
                               FMath::Cos(FMath::DegreesToRadians(Angle)), 0)
                       * FMath::Max(1.0f, SpikeLayout.Radius);
        }
        const float Jitter = FMath::Max(0.0f, SpikeLayout.Jitter);
        Position.X += Random.FRandRange(-Jitter, Jitter);
        Position.Y += Random.FRandRange(-Jitter, Jitter);
        EVFXSpikeShape Shape = SpikeShape.Shape == EVFXSpikeShape::Mixed
            ? static_cast<EVFXSpikeShape>(Random.RandRange(0, 2)) : SpikeShape.Shape;
        const float Height = FMath::Max(1.0f, SpikeShape.Height) *
            FMath::Max(0.1f, 1.0f + Random.FRandRange(
                -SpikeShape.HeightVariation, SpikeShape.HeightVariation));
        const float TiltPitch = Random.FRandRange(-SpikeShape.TiltVariation, SpikeShape.TiltVariation);
        const float TiltRoll = Random.FRandRange(-SpikeShape.TiltVariation, SpikeShape.TiltVariation);
        UProceduralMeshComponent* Piece = MakePiece(
            FString::Printf(TEXT("GroundSpike_%02d"), I + 1), Position);
        Piece->SetRelativeRotation(FRotator(TiltPitch, Angle, TiltRoll));
        MakeSpike(Shape, FMath::Max(1.0f, SpikeShape.Width),
                  FMath::Max(1.0f, SpikeShape.Depth), Height,
                  SpikeShape.RadialSides).Apply(Piece);
        SpikeStartTimes.Add(Rank[I] * FMath::Max(0.0f, SpikeGrowth.Stagger));
    }
    UpdateGrowth(PreviewGrowthTime);
}
