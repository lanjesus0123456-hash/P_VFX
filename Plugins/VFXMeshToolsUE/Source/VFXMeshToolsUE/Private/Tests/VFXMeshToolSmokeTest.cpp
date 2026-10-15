#if WITH_DEV_AUTOMATION_TESTS
#include "VFXMeshToolActor.h"
#include "ProceduralMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVFXMeshToolSmokeTest, "VFX.MeshTool.Smoke",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FVFXMeshToolSmokeTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    if (!TestNotNull(TEXT("World"), World)) return false;
    FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
    Context.SetCurrentWorld(World);
    AVFXMeshToolActor* Actor = World->SpawnActor<AVFXMeshToolActor>();
    if (!TestNotNull(TEXT("Actor"), Actor))
    {
        GEngine->DestroyWorldContext(World);
        World->DestroyWorld(false);
        return false;
    }

    Actor->Mode = EVFXMeshToolMode::GroundSpikes;
    Actor->SpikeLayout.Count = 8;
    Actor->SpikeLayout.Seed = 42;
    Actor->Rebuild();
    TestEqual(TEXT("Ground spike count"), Actor->GetGeneratedPieceCount(), 8);
    TestEqual(TEXT("Generated pieces are transient"), Actor->GetInstanceComponents().Num(), 0);
    TArray<FVector> OriginalPositions;
    for (UProceduralMeshComponent* Piece : Actor->GeneratedPieces)
    {
        OriginalPositions.Add(Piece->GetRelativeLocation());
        const FProcMeshSection* Section = Piece->GetProcMeshSection(0);
        TestTrue(TEXT("Spike has triangles"), Section && Section->ProcIndexBuffer.Num() >= 3);
    }
    Actor->SetGrowthTime(0.0f);
    TestTrue(TEXT("First spike starts hidden"), Actor->GeneratedPieces[0]->GetRelativeScale3D().Z < 0.01f);
    Actor->Tick(Actor->GetGrowthDuration() + 0.1f);
    TestTrue(TEXT("Runtime tick completes growth"), Actor->GeneratedPieces[0]->GetRelativeScale3D().Z > 0.99f);
    Actor->SetGrowthTime(Actor->GetGrowthDuration() + 0.1f);
    for (UProceduralMeshComponent* Piece : Actor->GeneratedPieces)
        TestTrue(TEXT("All spikes finish grown"), Piece->GetRelativeScale3D().Z > 0.99f);
    Actor->Rebuild();
    for (int32 I = 0; I < OriginalPositions.Num(); ++I)
        TestTrue(TEXT("Seed reproduces layout"),
            OriginalPositions[I].Equals(Actor->GeneratedPieces[I]->GetRelativeLocation(), 0.001f));

    Actor->Mode = EVFXMeshToolMode::Spline;
    Actor->SplinePaths.SetNum(2);
    Actor->SplinePaths[0].Points = { FVector(0, 0, 0), FVector(100, 0, 0) };
    Actor->SplinePaths[1].Points = { FVector(0, 100, 0), FVector(100, 100, 0) };
    Actor->SplineSurface = EVFXSplineSurface::Tube;
    Actor->Rebuild();
    const FProcMeshSection* SplineSection = Actor->MainMesh->GetProcMeshSection(0);
    TestTrue(TEXT("Two spline paths make a mesh"),
        SplineSection && SplineSection->ProcIndexBuffer.Num() >= 12);
    Actor->SetActorLocation(FVector(200, 50, 0));
    const FVector Before = Actor->SplinePaths[0].Points[0];
    Actor->SetPointSpace(EVFXPointSpace::World);
    TestTrue(TEXT("World position conversion"),
        Actor->SplinePaths[0].Points[0].Equals(Actor->GetActorTransform().TransformPosition(Before), 0.001f));
    Actor->SetPointSpace(EVFXPointSpace::Local);
    TestTrue(TEXT("Round trip local coordinates"),
        Actor->SplinePaths[0].Points[0].Equals(Before, 0.001f));

    Actor->Mode = EVFXMeshToolMode::Helix;
    Actor->HelixProfile.GetRichCurve()->AddKey(0.5f, 0.5f);
    Actor->Rebuild();
    const FProcMeshSection* HelixSection = Actor->MainMesh->GetProcMeshSection(0);
    TestTrue(TEXT("Helix profile makes triangles"),
        HelixSection && HelixSection->ProcIndexBuffer.Num() > 0);
    if (HelixSection && HelixSection->ProcVertexBuffer.Num() > 1152)
    {
        const float OuterRadius = HelixSection->ProcVertexBuffer[0].Position.Size2D();
        const float WaistRadius = HelixSection->ProcVertexBuffer[1152].Position.Size2D();
        TestTrue(TEXT("Helix waist is half horizontal scale"),
            FMath::IsNearlyEqual(WaistRadius / OuterRadius, 0.5f, 0.02f));
    }

    Actor->Mode = EVFXMeshToolMode::Custom;
    Actor->CustomHeightPoints.SetNum(1);
    Actor->CustomHeightPoints[0].Position = FVector2D(0, 0);
    Actor->CustomHeightPoints[0].HeightOffset = 20.0f;
    Actor->bIrregularEdge = true;
    Actor->Rebuild();
    const FProcMeshSection* CustomBefore = Actor->MainMesh->GetProcMeshSection(0);
    TestTrue(TEXT("Irregular custom mesh"),
        CustomBefore && CustomBefore->ProcIndexBuffer.Num() > 0);
    float HeightBefore = 0.0f;
    if (CustomBefore)
    {
        TestTrue(TEXT("Irregular edge adds boundary detail"),
            CustomBefore->ProcVertexBuffer.Num() > 96);
        float Nearest = FLT_MAX;
        for (const FProcMeshVertex& Vertex : CustomBefore->ProcVertexBuffer)
        {
            const float D = Vertex.Position.SizeSquared2D();
            if (D < Nearest) { Nearest = D; HeightBefore = Vertex.Position.Z; }
        }
    }
    Actor->CustomBoundary[0].Z += 50.0f;
    Actor->Rebuild();
    const FProcMeshSection* CustomAfter = Actor->MainMesh->GetProcMeshSection(0);
    TestTrue(TEXT("Custom remains valid after boundary height edit"),
        CustomAfter && CustomAfter->ProcIndexBuffer.Num() > 0);
    if (CustomAfter)
    {
        float HeightAfter = 0.0f, Nearest = FLT_MAX;
        for (const FProcMeshVertex& Vertex : CustomAfter->ProcVertexBuffer)
        {
            const float D = Vertex.Position.SizeSquared2D();
            if (D < Nearest) { Nearest = D; HeightAfter = Vertex.Position.Z; }
        }
        TestTrue(TEXT("Interior height follows lifted boundary"),
            HeightAfter > HeightBefore + 0.1f);
    }

    Actor->Mode = EVFXMeshToolMode::Fracture;
    Actor->FractureSource = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
    Actor->FragmentCount = 2;
    Actor->Rebuild();
    TestEqual(TEXT("Plane separates into two fragments"), Actor->GetGeneratedPieceCount(), 2);
    for (UProceduralMeshComponent* Piece : Actor->GeneratedPieces)
    {
        const FProcMeshSection* Section = Piece->GetProcMeshSection(0);
        TestTrue(TEXT("Fragment has front, back and sides"),
            Section && Section->ProcIndexBuffer.Num() > 6);
    }

    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
    return !HasAnyErrors();
}
#endif


