#pragma once
#include "CoreMinimal.h"
#include "ProceduralMeshComponent.h"

struct FVFXProcData
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UV;
    TArray<FLinearColor> Colors;

    void Tri(const FVector& A, const FVector& B, const FVector& C,
             const FVector2D& U0 = FVector2D::ZeroVector,
             const FVector2D& U1 = FVector2D(1, 0),
             const FVector2D& U2 = FVector2D(0, 1),
             const FLinearColor& Color = FLinearColor::White)
    {
        const FVector N = FVector::CrossProduct(B - A, C - A).GetSafeNormal();
        if (N.IsNearlyZero()) return;
        const int32 Base = Vertices.Num();
        Vertices.Add(A); Vertices.Add(B); Vertices.Add(C);
        Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UV.Add(U0); UV.Add(U1); UV.Add(U2);
        Colors.Add(Color); Colors.Add(Color); Colors.Add(Color);
        Triangles.Add(Base); Triangles.Add(Base + 1); Triangles.Add(Base + 2);
    }

    void Quad(const FVector& A, const FVector& B, const FVector& C, const FVector& D,
              const FVector2D& U0, const FVector2D& U1,
              const FVector2D& U2, const FVector2D& U3,
              const FLinearColor& Color = FLinearColor::White)
    {
        Tri(A, B, C, U0, U1, U2, Color);
        Tri(A, C, D, U0, U2, U3, Color);
    }

    void Apply(UProceduralMeshComponent* Target) const
    {
        if (!Target || Triangles.IsEmpty()) return;
        TArray<FProcMeshTangent> Tangents;
        Target->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UV,
            Colors, Tangents, false);
    }
};
