using UnrealBuildTool;
public class VFXMaterialControls : ModuleRules
{
 public VFXMaterialControls(ReadOnlyTargetRules Target) : base(Target)
 {
  PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
  PrivateDependencyModuleNames.AddRange(new [] { "Core", "CoreUObject", "Engine", "UnrealEd", "MaterialEditor", "PropertyEditor" });
 }
}
