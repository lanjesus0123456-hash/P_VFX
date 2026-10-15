#include "VFXMeshToolActor.h"
#include "VFXMeshToolGeometry.h"
#include "ProceduralMeshComponent.h"

static float Cross2(const FVector2D& A, const FVector2D& B)
{
    return A.X * B.Y - A.Y * B.X;
}
static FVector2D XY(const FVector& P) { return FVector2D(P.X, P.Y); }

static bool SegmentsCross(const FVector2D& A, const FVector2D& B,
                          const FVector2D& C, const FVector2D& D)
{
    const float AB1 = Cross2(B - A, C - A), AB2 = Cross2(B - A, D - A);
    const float CD1 = Cross2(D - C, A - C), CD2 = Cross2(D - C, B - C);
    return AB1 * AB2 < -0.0001f && CD1 * CD2 < -0.0001f;
}

static bool SimplePolygon(const TArray<FVector>& Boundary)
{
    const int32 N = Boundary.Num();
    for (int32 I = 0; I < N; ++I)
        for (int32 J = I + 1; J < N; ++J)
        {
            if (J == I + 1 || (I == 0 && J == N - 1)) continue;
            if (SegmentsCross(XY(Boundary[I]), XY(Boundary[(I + 1) % N]),
                              XY(Boundary[J]), XY(Boundary[(J + 1) % N]))) return false;
        }
    return true;
}

static TArray<FVector> IrregularBoundary(const TArray<FVector>& Source,
                                        int32 Subdivisions, float Amplitude,
                                        float Frequency, int32 Seed)
{
    if (Source.Num() < 3 || Amplitude <= 0.0f || Subdivisions <= 1) return Source;
    TArray<float> Phases;
    FRandomStream Random(Seed);
    for (int32 I = 0; I < Source.Num(); ++I)
        Phases.Add(Random.FRandRange(-PI, PI));
    for (int32 Attempt = 0; Attempt < 8; ++Attempt)
    {
        TArray<FVector> Result;
        const float Scale = Amplitude * FMath::Pow(0.5f, Attempt);
        for (int32 I = 0; I < Source.Num(); ++I)
        {
            const FVector A = Source[I], B = Source[(I + 1) % Source.Num()];
            const FVector2D Edge = XY(B - A);
            const FVector2D Normal = FVector2D(-Edge.Y, Edge.X).GetSafeNormal();
            for (int32 J = 0; J < Subdivisions; ++J)
            {
                const float T = static_cast<float>(J) / Subdivisions;
                FVector P = FMath::Lerp(A, B, T);
                const float Wave = FMath::Sin(PI * T) *
                    FMath::Sin(2.0f * PI * Frequency * T + Phases[I]);
                P.X += Normal.X * Wave * Scale;
                P.Y += Normal.Y * Wave * Scale;
                Result.Add(P);
            }
        }
        if (SimplePolygon(Result)) return Result;
    }
    return Source;
}

static bool InsideTriangle(const FVector2D& P, const FVector2D& A,
                           const FVector2D& B, const FVector2D& C)
{
    const float C0 = Cross2(B - A, P - A);
    const float C1 = Cross2(C - B, P - B);
    const float C2 = Cross2(A - C, P - C);
    return C0 >= -0.0001f && C1 >= -0.0001f && C2 >= -0.0001f;
}

static TArray<FIntVector> Triangulate(const TArray<FVector>& Boundary)
{
    TArray<FIntVector> Faces;
    TArray<int32> Remaining;
    for (int32 I = 0; I < Boundary.Num(); ++I) Remaining.Add(I);
    int32 Guard = 0;
    while (Remaining.Num() > 3 && Guard++ < Boundary.Num() * Boundary.Num())
    {
        bool Clipped = false;
        for (int32 I = 0; I < Remaining.Num(); ++I)
        {
            const int32 Prev = Remaining[(I + Remaining.Num() - 1) % Remaining.Num()];
            const int32 Curr = Remaining[I];
            const int32 Next = Remaining[(I + 1) % Remaining.Num()];
            const FVector2D A = XY(Boundary[Prev]), B = XY(Boundary[Curr]), C = XY(Boundary[Next]);
            if (Cross2(B - A, C - B) <= KINDA_SMALL_NUMBER) continue;
            bool Contains = false;
            for (int32 Other : Remaining)
            {
                if (Other == Prev || Other == Curr || Other == Next) continue;
                if (InsideTriangle(XY(Boundary[Other]), A, B, C)) { Contains = true; break; }
            }
            if (Contains) continue;
            Faces.Add(FIntVector(Prev, Curr, Next));
            Remaining.RemoveAt(I);
            Clipped = true;
            break;
        }
        if (!Clipped) break;
    }
    if (Remaining.Num() == 3)
        Faces.Add(FIntVector(Remaining[0], Remaining[1], Remaining[2]));
    return Faces;
}

static float BoundaryHeight(const TArray<FVector>& Boundary, const FVector2D& P)
{
    const int32 N = Boundary.Num();
    TArray<FVector2D> Vectors;
    TArray<float> Distances;
    Vectors.Reserve(N); Distances.Reserve(N);
    for (const FVector& Vertex : Boundary)
    {
        const FVector2D V = XY(Vertex) - P;
        const float D = V.Size();
        if (D < 0.0001f) return Vertex.Z;
        Vectors.Add(V); Distances.Add(D);
    }
    TArray<float> HalfTangents;
    HalfTangents.Reserve(N);
    for (int32 I = 0; I < N; ++I)
    {
        const int32 Next = (I + 1) % N;
        const FVector2D A = XY(Boundary[I]), B = XY(Boundary[Next]);
        const FVector2D Edge = B - A;
        const float LengthSq = Edge.SizeSquared();
        if (LengthSq > KINDA_SMALL_NUMBER)
        {
            const float T = FVector2D::DotProduct(P - A, Edge) / LengthSq;
            if (T >= 0.0f && T <= 1.0f &&
                (P - FMath::Lerp(A, B, T)).SizeSquared() < 0.0001f)
                return FMath::Lerp(Boundary[I].Z, Boundary[Next].Z, T);
        }
        const float Denom = Distances[I] * Distances[Next] +
            FVector2D::DotProduct(Vectors[I], Vectors[Next]);
        HalfTangents.Add(FMath::Abs(Denom) > 1e-8f
            ? Cross2(Vectors[I], Vectors[Next]) / Denom : 0.0f);
    }
    float Sum = 0.0f, Weighted = 0.0f;
    for (int32 I = 0; I < N; ++I)
    {
        const float W = (HalfTangents[(I + N - 1) % N] + HalfTangents[I]) / Distances[I];
        Sum += W;
        Weighted += W * Boundary[I].Z;
    }
    return FMath::Abs(Sum) > 1e-8f ? Weighted / Sum : 0.0f;
}

void AVFXMeshToolActor::BuildCustom()
{
    if (CustomBoundary.Num() < 3) return;
    TArray<FVector> Boundary = bIrregularEdge
        ? IrregularBoundary(CustomBoundary, FMath::Clamp(EdgeSubdivisions, 1, 32),
            FMath::Max(0.0f, IrregularAmplitude), FMath::Max(0.1f, EdgeFrequency), IrregularSeed)
        : CustomBoundary;
    float Area = 0.0f;
    for (int32 I = 0; I < Boundary.Num(); ++I)
        Area += Cross2(XY(Boundary[I]), XY(Boundary[(I + 1) % Boundary.Num()]));
    if (Area < 0.0f) Algo::Reverse(Boundary);
    const TArray<FIntVector> Faces = Triangulate(Boundary);
    if (Faces.IsEmpty()) return;
    FVector2D Min(FLT_MAX, FLT_MAX), Max(-FLT_MAX, -FLT_MAX);
    for (const FVector& P : Boundary)
    {
        Min.X = FMath::Min(Min.X, P.X); Min.Y = FMath::Min(Min.Y, P.Y);
        Max.X = FMath::Max(Max.X, P.X); Max.Y = FMath::Max(Max.Y, P.Y);
    }
    const FVector2D Size = Max - Min;
    const int32 Density = FMath::Clamp(CustomSubdivision, 1, 16);
    auto SurfacePoint = [this, &Boundary](const FVector2D& P) -> FVector
    {
        float Height = BoundaryHeight(Boundary, P);
        for (const FVFXHeightPoint& Control : CustomHeightPoints)
        {
            const float T = FMath::Clamp((P - Control.Position).Size() /
                FMath::Max(1.0f, Control.Radius), 0.0f, 1.0f);
            const float Falloff = (1.0f - T) * (1.0f - T);
            Height += Control.HeightOffset * Falloff;
        }
        return FVector(P.X, P.Y, Height);
    };
    auto UV = [&Min, &Size](const FVector2D& P)
    {
        return FVector2D((P.X - Min.X) / FMath::Max(1.0f, Size.X),
                         (P.Y - Min.Y) / FMath::Max(1.0f, Size.Y));
    };
    FVFXProcData Data;
    for (const FIntVector& Face : Faces)
    {
        const FVector2D A = XY(Boundary[Face.X]), B = XY(Boundary[Face.Y]),
                        C = XY(Boundary[Face.Z]);
        auto P = [&A, &B, &C, Density](int32 I, int32 J)
        {
            return A + (B - A) * (static_cast<float>(I) / Density)
                     + (C - A) * (static_cast<float>(J) / Density);
        };
        for (int32 I = 0; I < Density; ++I)
            for (int32 J = 0; J < Density - I; ++J)
            {
                const FVector2D P00 = P(I, J), P10 = P(I + 1, J), P01 = P(I, J + 1);
                Data.Tri(SurfacePoint(P00), SurfacePoint(P10), SurfacePoint(P01),
                    UV(P00), UV(P10), UV(P01));
                if (J < Density - I - 1)
                {
                    const FVector2D P11 = P(I + 1, J + 1);
                    Data.Tri(SurfacePoint(P10), SurfacePoint(P11), SurfacePoint(P01),
                        UV(P10), UV(P11), UV(P01));
                }
            }
    }
    Data.Apply(MainMesh);
}
