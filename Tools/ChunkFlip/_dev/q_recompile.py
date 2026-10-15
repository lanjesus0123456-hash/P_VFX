import unreal
mel = unreal.MaterialEditingLibrary
m = unreal.load_asset("/Game/VFXTool_Test/ChunkFlip/M_ChunkFlipGrow")
xf = [e for e in mel.get_material_expressions(m) if isinstance(e, unreal.MaterialExpressionTransform)][0]
print("xf 输入节点:", [n.get_name() if n else None for n in mel.get_inputs_for_material_expression(m, xf)] if hasattr(mel, "get_inputs_for_material_expression") else "?")
mel.recompile_material(m)
print("recompiled")
