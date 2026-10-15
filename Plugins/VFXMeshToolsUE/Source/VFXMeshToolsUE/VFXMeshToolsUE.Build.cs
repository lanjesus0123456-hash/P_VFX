using UnrealBuildTool;
public class VFXMeshToolsUE : ModuleRules
{
    public VFXMeshToolsUE(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.NoPCHs;
        PrivateDefinitions.Add("PLATFORM_HAS_ASAN_INCLUDE=0");
        PublicDependencyModuleNames.AddRange(new string[] {
            "Core", "CoreUObject", "Engine", "ProceduralMeshComponent"
        });
    }
}

