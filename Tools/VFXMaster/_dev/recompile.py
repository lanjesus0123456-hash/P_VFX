import unreal
m = unreal.load_asset("/Game/VFX/Materials/Master/M_VFX_Master")
unreal.MaterialEditingLibrary.recompile_material(m)
print("recompiled")
