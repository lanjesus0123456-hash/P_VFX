#include "VFXMeshToolActor.h"
#include "VFXMeshToolGeometry.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "ProceduralMeshComponent.h"

static uint64 EdgeKey(uint32 A, uint32 B)
{
    const uint64 Lo = FMath::Min(A, B), Hi = FMath::Max(A, B);
    return (Lo << 32) | Hi;
}
static void AddFaceEdge(TMap<uint64, TArray<int32>>& Map, uint32 A, uint32 B, int32 Face)
{
    Map.FindOrAdd(EdgeKey(A, B)).Add(Face);
}
static FVector SourcePosition(const FStaticMeshLODResources& LOD, uint32 Index)
{
    return FVector(LOD.VertexBuffers.PositionVertexBuffer.VertexPosition(Index));
}
static FVector2D SourceUV(const FStaticMeshLODResources& LOD, uint32 Index)
{
    if (LOD.VertexBuffers.StaticMeshVertexBuffer.GetNumTexCoords() == 0)
        return FVector2D::ZeroVector;
    const FVector2f Value = LOD.VertexBuffers.StaticMeshVertexBuffer.GetVertexUV(Index, 0);
    return FVector2D(Value.X, Value.Y);
}

void AVFXMeshToolActor::BuildFracture()
{
    if (!FractureSource) return;
#if !WITH_EDITOR
    if (!FractureSource->bAllowCPUAccess)
    {
        UE_LOG(LogTemp, Warning, TEXT("VFX fracture source %s requires Allow CPU Access"), *FractureSource->GetName());
        return;
    }
#endif
    const FStaticMeshRenderData* Render = FractureSource->GetRenderData();
    if (!Render || Render->LODResources.IsEmpty()) return;
    const FStaticMeshLODResources& LOD = Render->LODResources[0];
    const int32 FaceCount = LOD.IndexBuffer.GetNumIndices() / 3;
    if (FaceCount <= 0 || FaceCount > 50000) return;
    TArray<FIntVector> Faces;
    Faces.Reserve(FaceCount);
    TMap<uint64, TArray<int32>> EdgeFaces;
    for (int32 I = 0; I < FaceCount; ++I)
    {
        const uint32 A = LOD.IndexBuffer.GetIndex(I * 3);
        const uint32 B = LOD.IndexBuffer.GetIndex(I * 3 + 1);
        const uint32 C = LOD.IndexBuffer.GetIndex(I * 3 + 2);
        Faces.Add(FIntVector(A, B, C));
        AddFaceEdge(EdgeFaces, A, B, I);
        AddFaceEdge(EdgeFaces, B, C, I);
        AddFaceEdge(EdgeFaces, C, A, I);
    }
    TArray<TArray<int32>> Neighbors;
    Neighbors.SetNum(FaceCount);
    for (const TPair<uint64, TArray<int32>>& Pair : EdgeFaces)
        for (int32 I = 0; I < Pair.Value.Num(); ++I)
            for (int32 J = I + 1; J < Pair.Value.Num(); ++J)
            {
                Neighbors[Pair.Value[I]].Add(Pair.Value[J]);
                Neighbors[Pair.Value[J]].Add(Pair.Value[I]);
            }
    TArray<int32> Assignment;
    Assignment.Init(INDEX_NONE, FaceCount);
    TArray<TArray<int32>> Groups;
    const int32 TargetCount = FMath::Clamp(FragmentCount, 1, FMath::Min(FaceCount, 64));
    FRandomStream Random(FractureSeed);
    int32 Unassigned = FaceCount;
    for (int32 GroupIndex = 0; GroupIndex < TargetCount && Unassigned > 0; ++GroupIndex)
    {
        const int32 Goal = FMath::DivideAndRoundUp(Unassigned, TargetCount - GroupIndex);
        int32 Seed = Random.RandRange(0, FaceCount - 1);
        while (Assignment[Seed] != INDEX_NONE) Seed = (Seed + 1) % FaceCount;
        TArray<int32> Queue;
        Queue.Add(Seed);
        Assignment[Seed] = GroupIndex;
        Groups.AddDefaulted();
        for (int32 Read = 0; Read < Queue.Num() && Groups[GroupIndex].Num() < Goal; ++Read)
        {
            const int32 Face = Queue[Read];
            Groups[GroupIndex].Add(Face);
            --Unassigned;
            TArray<int32> Candidates = Neighbors[Face];
            for (int32 K = Candidates.Num() - 1; K > 0; --K)
                Candidates.Swap(K, Random.RandRange(0, K));
            for (int32 Adjacent : Candidates)
            {
                if (Assignment[Adjacent] != INDEX_NONE) continue;
                Assignment[Adjacent] = GroupIndex;
                Queue.Add(Adjacent);
            }
        }
        // Queued faces not yet consumed are returned to the unassigned pool.
        for (int32 Read = Groups[GroupIndex].Num(); Read < Queue.Num(); ++Read)
            Assignment[Queue[Read]] = INDEX_NONE;
    }
    // Disconnected islands or index seams join the nearest existing fragment.
    for (int32 I = 0; I < FaceCount; ++I)
        if (Assignment[I] == INDEX_NONE)
        {
            int32 Nearest = 0;
            float Distance = FLT_MAX;
            const FIntVector F = Faces[I];
            const FVector Center = (SourcePosition(LOD, F.X) +
                SourcePosition(LOD, F.Y) + SourcePosition(LOD, F.Z)) / 3.0f;
            for (int32 G = 0; G < Groups.Num(); ++G)
            {
                if (Groups[G].IsEmpty()) continue;
                const FIntVector Sample = Faces[Groups[G][0]];
                const FVector SampleCenter = (SourcePosition(LOD, Sample.X) +
                    SourcePosition(LOD, Sample.Y) + SourcePosition(LOD, Sample.Z)) / 3.0f;
                const float D = FVector::DistSquared(Center, SampleCenter);
                if (D < Distance) { Distance = D; Nearest = G; }
            }
            Groups[Nearest].Add(I);
            Assignment[I] = Nearest;
        }
    const FVector SourceCenter = FractureSource->GetBounds().Origin;
    for (int32 G = 0; G < Groups.Num(); ++G)
    {
        if (Groups[G].IsEmpty()) continue;
        FVector Pivot = FVector::ZeroVector;
        FVector NormalSum = FVector::ZeroVector;
        TMap<uint64, int32> EdgeCounts;
        for (int32 Face : Groups[G])
        {
            const FIntVector F = Faces[Face];
            const FVector A = SourcePosition(LOD, F.X);
            const FVector B = SourcePosition(LOD, F.Y);
            const FVector C = SourcePosition(LOD, F.Z);
            Pivot += (A + B + C) / 3.0f;
            NormalSum += FVector::CrossProduct(B - A, C - A).GetSafeNormal();
            EdgeCounts.FindOrAdd(EdgeKey(F.X, F.Y))++;
            EdgeCounts.FindOrAdd(EdgeKey(F.Y, F.Z))++;
            EdgeCounts.FindOrAdd(EdgeKey(F.Z, F.X))++;
        }
        Pivot /= Groups[G].Num();
        const FVector Offset = NormalSum.GetSafeNormal(KINDA_SMALL_NUMBER, FVector::UpVector) *
            FMath::Max(0.1f, FragmentThickness);
        const FVector Direction = (Pivot - SourceCenter).GetSafeNormal();
        UProceduralMeshComponent* Piece = MakePiece(
            FString::Printf(TEXT("Fracture_%02d"), G + 1),
            Pivot + Direction * FracturePreviewSeparation);
        FVFXProcData Data;
        for (int32 Face : Groups[G])
        {
            const FIntVector F = Faces[Face];
            const uint32 Id[3] = { static_cast<uint32>(F.X), static_cast<uint32>(F.Y),
                                    static_cast<uint32>(F.Z) };
            const FVector A = SourcePosition(LOD, Id[0]) - Pivot;
            const FVector B = SourcePosition(LOD, Id[1]) - Pivot;
            const FVector C = SourcePosition(LOD, Id[2]) - Pivot;
            const FVector2D U0 = SourceUV(LOD, Id[0]), U1 = SourceUV(LOD, Id[1]),
                            U2 = SourceUV(LOD, Id[2]);
            const FLinearColor Color = FLinearColor::MakeFromHSV8(
                static_cast<uint8>(G * 41), 150, 255);
            Data.Tri(A, B, C, U0, U1, U2, Color);
            Data.Tri(C - Offset, B - Offset, A - Offset, U2, U1, U0, Color);
            for (int32 E = 0; E < 3; ++E)
            {
                const uint32 Start = Id[E], End = Id[(E + 1) % 3];
                if (EdgeCounts.FindRef(EdgeKey(Start, End)) != 1) continue;
                const FVector V0 = SourcePosition(LOD, Start) - Pivot;
                const FVector V1 = SourcePosition(LOD, End) - Pivot;
                const float Length = FVector::Distance(V0, V1) /
                    FMath::Max(1.0f, FragmentThickness);
                Data.Quad(V0 - Offset, V1 - Offset, V1, V0,
                    FVector2D(0, 0), FVector2D(Length, 0),
                    FVector2D(Length, 1), FVector2D(0, 1), Color);
            }
        }
        Data.Apply(Piece);
    }
}

