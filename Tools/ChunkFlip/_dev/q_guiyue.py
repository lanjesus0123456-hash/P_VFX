import unreal
mel = unreal.MaterialEditingLibrary
R = "/Game/归玥材质包LTS"
for p in ("/01_Pro/Guiyue_Pro_2607", "/01_Pro/Guiyue_Simple_2607", "/07_MF/Guiyue_MF_Refine"):
    a = unreal.load_asset(R + p)
    print("==", p, type(a).__name__ if a else None)
    if isinstance(a, unreal.Material):
        ex = mel.get_material_expressions(a)
        print("  节点数:", len(ex), " blend:", a.get_editor_property("blend_mode"), " shading:", a.get_editor_property("shading_model"))
        st = {}
        for e in ex: st[type(e).__name__] = st.get(type(e).__name__, 0) + 1
        print("  类型:", sorted(st.items(), key=lambda x: -x[1])[:14])
        print("  静态开关:", len(mel.get_static_switch_parameter_names(a)), " 标量:", len(mel.get_scalar_parameter_names(a)), " 向量:", len(mel.get_vector_parameter_names(a)), " 贴图:", len(mel.get_texture_parameter_names(a)))
        mfs = sorted({e.get_editor_property("material_function").get_path_name().split("/")[-1].split(".")[0] for e in ex if isinstance(e, unreal.MaterialExpressionMaterialFunctionCall) and e.get_editor_property("material_function")})
        print("  函数:", mfs)
    elif isinstance(a, unreal.MaterialFunction):
        ex = mel.get_material_function_expressions(a) if hasattr(mel, "get_material_function_expressions") else []
        print("  节点数:", len(ex))
        for e in ex:
            if isinstance(e, (unreal.MaterialExpressionFunctionInput,)):
                print("   输入:", e.get_editor_property("input_name"), e.get_editor_property("input_type"))
            elif isinstance(e, unreal.MaterialExpressionFunctionOutput):
                print("   输出:", e.get_editor_property("output_name"))
