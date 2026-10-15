import unreal
mel = unreal.MaterialEditingLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
tmp = "/Game/VFXTool_Test/_probe"
m = at.create_asset("M_probe2", tmp, unreal.Material, unreal.MaterialFactoryNew())
v = mel.create_material_expression(m, unreal.MaterialExpressionVectorParameter, 0, 0)
print("vec outs:", mel.get_material_expression_output_names(v))
d = mel.create_material_expression(m, unreal.MaterialExpressionDepthFade, 0, 0)
print("mi static switch api:", hasattr(mel, "set_material_instance_static_switch_parameter_value"))
mi = at.create_asset("MI_probe2", tmp, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
bpo = mi.get_editor_property("base_property_overrides")
print("overrides:", [p for p in dir(bpo) if p.startswith("override_") or p in ("blend_mode", "two_sided")])
unreal.EditorAssetLibrary.delete_directory(tmp)
