import unreal
mel = unreal.MaterialEditingLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
tmp = "/Game/VFXTool_Test/_probe"
if unreal.EditorAssetLibrary.does_asset_exist(tmp + "/M_probe"):
    unreal.EditorAssetLibrary.delete_asset(tmp + "/M_probe")
m = at.create_asset("M_probe", tmp, unreal.Material, unreal.MaterialFactoryNew())
for cls in (unreal.MaterialExpressionDynamicParameter, unreal.MaterialExpressionStaticSwitchParameter,
            unreal.MaterialExpressionDepthFade, unreal.MaterialExpressionAppendVector,
            unreal.MaterialExpressionTextureObjectParameter, unreal.MaterialExpressionTransform,
            unreal.MaterialExpressionVertexColor, unreal.MaterialExpressionTwoSidedSign):
    e = mel.create_material_expression(m, cls, 0, 0)
    print(cls.__name__, "in:", mel.get_material_expression_input_names(e), "out:", mel.get_material_expression_output_names(e))
print([x for x in dir(unreal) if "Refraction" in x])
for x in [x for x in dir(unreal) if "Refraction" in x]:
    print(x, [y for y in dir(getattr(unreal, x)) if y.isupper()])
print([p for p in ("refraction_method", "used_with_niagara_sprites", "used_with_niagara_ribbons", "used_with_niagara_mesh_particles", "translucency_pass", "blend_mode") if hasattr(m, "get_editor_property") and m.get_editor_property(p) is not None])
print("BlendMode:", [y for y in dir(unreal.BlendMode) if y.startswith("BLEND")])
for p in ("/Engine/EngineResources/WhiteSquareTexture", "/Engine/EngineResources/Black", "/Engine/EngineResources/DefaultTexture", "/Engine/EngineMaterials/DefaultWhiteGrid", "/Engine/BasicShapes/Plane", "/Engine/EngineResources/GradientTexture0"):
    print(p, unreal.EditorAssetLibrary.does_asset_exist(p))
unreal.EditorAssetLibrary.delete_asset(tmp + "/M_probe")
