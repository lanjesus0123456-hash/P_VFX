#include "VFXMeshToolActor.h"
#include "VFXMeshToolGeometry.h"
#include "ProceduralMeshComponent.h"

static FVector CatmullSample(const TArray<FVector>& P, int32 Segment, float T)
{
    const int32 N = P.Num();
    const FVector A = P[FMath::Max(0, Segment - 1)];
    const FVector B = P[Segment];
    const FVector C = P[Segment + 1];
    const FVector D = P[FMath::Min(N - 1, Segment + 2)];
    const FVector M0 = 0.5f * (C - A);
    const FVector M1 = 0.5f * (D - B);
    return FMath::CubicInterp(B, M0, C, M1, T);
}

void AVFXMeshToolActor::BuildSpline()
{
    FVFXProcData Data;
    const float HalfWidth = FMath::Max(1.0f, SplineWidth) * 0.5f;
    const int32 Samples = FMath::Clamp(SplineSamplesPerSegment, 1, 32);
    const int32 Sides = FMath::Clamp(SplineTubeSides, 3, 16);
    for (const FVFXSplinePath& Path : SplinePaths)
    {
        if (Path.Points.Num() < 2) continue;
        TArray<FVector> Local;
        Local.Reserve(Path.Points.Num());
        for (const FVector& Point : Path.Points)
            Local.Add(PointSpace == EVFXPointSpace::World
                ? GetActorTransform().InverseTransformPosition(Point) : Point);
        TArray<FVector> Centers;
        for (int32 S = 0; S < Local.Num() - 1; ++S)
            for (int32 J = 0; J < Samples; ++J)
                Centers.Add(CatmullSample(Local, S, static_cast<float>(J) / Samples));
        Centers.Add(Local.Last());
        const int32 Last = Centers.Num() - 1;
        for (int32 I = 0; I < Last; ++I)
        {
            const FVector Tangent0 = (Centers[FMath::Min(I + 1, Last)] -
                Centers[FMath::Max(0, I - 1)]).GetSafeNormal(KINDA_SMALL_NUMBER, FVector::ForwardVector);
            const FVector Tangent1 = (Centers[FMath::Min(I + 2, Last)] -
                Centers[I]).GetSafeNormal(KINDA_SMALL_NUMBER, FVector::ForwardVector);
            FVector Right0 = FVector::CrossProduct(FVector::UpVector, Tangent0).GetSafeNormal();
            FVector Right1 = FVector::CrossProduct(FVector::UpVector, Tangent1).GetSafeNormal();
            if (Right0.IsNearlyZero()) Right0 = FVector::RightVector;
            if (Right1.IsNearlyZero()) Right1 = FVector::RightVector;
            const FVector Up0 = FVector::CrossProduct(Tangent0, Right0).GetSafeNormal();
            const FVector Up1 = FVector::CrossProduct(Tangent1, Right1).GetSafeNormal();
            const float V0 = static_cast<float>(I) / Last;
            const float V1 = static_cast<float>(I + 1) / Last;
            if (SplineSurface != EVFXSplineSurface::Tube)
            {
                Data.Quad(Centers[I] + Right0 * HalfWidth,
                          Centers[I] - Right0 * HalfWidth,
                          Centers[I + 1] - Right1 * HalfWidth,
                          Centers[I + 1] + Right1 * HalfWidth,
                          FVector2D(0, V0), FVector2D(1, V0),
                          FVector2D(1, V1), FVector2D(0, V1));
                if (SplineSurface == EVFXSplineSurface::Cross)
                    Data.Quad(Centers[I] + Up0 * HalfWidth,
                              Centers[I] - Up0 * HalfWidth,
                              Centers[I + 1] - Up1 * HalfWidth,
                              Centers[I + 1] + Up1 * HalfWidth,
                              FVector2D(0, V0), FVector2D(1, V0),
                              FVector2D(1, V1), FVector2D(0, V1));
                continue;
            }
            for (int32 Side = 0; Side < Sides; ++Side)
            {
                const float A0 = 2.0f * PI * Side / Sides;
                const float A1 = 2.0f * PI * (Side + 1) / Sides;
                const FVector R00 = Centers[I] + HalfWidth *
                    (Right0 * FMath::Cos(A0) + Up0 * FMath::Sin(A0));
                const FVector R01 = Centers[I] + HalfWidth *
                    (Right0 * FMath::Cos(A1) + Up0 * FMath::Sin(A1));
                const FVector R10 = Centers[I + 1] + HalfWidth *
                    (Right1 * FMath::Cos(A0) + Up1 * FMath::Sin(A0));
                const FVector R11 = Centers[I + 1] + HalfWidth *
                    (Right1 * FMath::Cos(A1) + Up1 * FMath::Sin(A1));
                const float U0 = static_cast<float>(Side) / Sides;
                const float U1 = static_cast<float>(Side + 1) / Sides;
                Data.Quad(R00, R01, R11, R10,
                    FVector2D(U0, V0), FVector2D(U1, V0),
                    FVector2D(U1, V1), FVector2D(U0, V1));
            }
        }
    }
    Data.Apply(MainMesh);
}

static FVector HelixRingPoint(float T, float Angle, float Radius,
                              float Height, float Turns, float TubeRadius,
                              const FRichCurve* Profile)
{
    const float Theta = T * Turns * 2.0f * PI;
    const FVector Radial(FMath::Cos(Theta), FMath::Sin(Theta), 0.0f);
    const FVector Tangent(-FMath::Sin(Theta) * Radius * Turns * 2.0f * PI,
                           FMath::Cos(Theta) * Radius * Turns * 2.0f * PI,
                           Height);
    const FVector Side = FVector::CrossProduct(Tangent.GetSafeNormal(), Radial).GetSafeNormal();
    FVector P = Radial * Radius + FVector::UpVector * (T * Height)
              + TubeRadius * (Radial * FMath::Cos(Angle) + Side * FMath::Sin(Angle));
    const float Scale = FMath::Max(0.001f, Profile->Eval(T, 1.0f));
    P.X *= Scale; P.Y *= Scale;
    return P;
}

void AVFXMeshToolActor::BuildHelix()
{
    FVFXProcData Data;
    const int32 Segments = FMath::Clamp(HelixSegments, 3, 512);
    const int32 Sides = FMath::Clamp(HelixSides, 3, 16);
    const FRichCurve* Profile = HelixProfile.GetRichCurveConst();
    for (int32 I = 0; I < Segments; ++I)
    {
        const float T0 = static_cast<float>(I) / Segments;
        const float T1 = static_cast<float>(I + 1) / Segments;
        for (int32 Side = 0; Side < Sides; ++Side)
        {
            const float U0 = static_cast<float>(Side) / Sides;
            const float U1 = static_cast<float>(Side + 1) / Sides;
            const float A0 = U0 * 2.0f * PI;
            const float A1 = U1 * 2.0f * PI;
            Data.Quad(
                HelixRingPoint(T0, A0, HelixRadius, HelixHeight, HelixTurns, HelixTubeRadius, Profile),
                HelixRingPoint(T0, A1, HelixRadius, HelixHeight, HelixTurns, HelixTubeRadius, Profile),
                HelixRingPoint(T1, A1, HelixRadius, HelixHeight, HelixTurns, HelixTubeRadius, Profile),
                HelixRingPoint(T1, A0, HelixRadius, HelixHeight, HelixTurns, HelixTubeRadius, Profile),
                FVector2D(U0, T0), FVector2D(U1, T0),
                FVector2D(U1, T1), FVector2D(U0, T1));
        }
    }
    Data.Apply(MainMesh);
}

