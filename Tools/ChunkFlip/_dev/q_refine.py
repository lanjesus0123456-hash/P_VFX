import unreal
mel = unreal.MaterialEditingLibrary
R = "/Game/归玥材质包LTS"
mf = unreal.load_asset(R + "/07_MF/Guiyue_MF_Refine")
ex = mel.get_material_function_expressions(mf)
def nm(e):
    t = type(e).__name__.replace("MaterialExpression", "")
    extra = ""
    for p in ("input_name", "output_name", "parameter_name", "r", "const_a", "const_b", "code", "description"):
        try:
            v = e.get_editor_property(p)
            if v not in (None, "", 0.0): extra += " %s=%r" % (p, v if not isinstance(v, str) else v[:200])
        except Exception: pass
    return "%s(%s)%s" % (t, e.get_name().split("_")[-1], extra)
for e in ex:
    ins = []
    try: ins = mel.get_inputs_for_material_expression_in_function(mf, e) if hasattr(mel, "get_inputs_for_material_expression_in_function") else []
    except Exception: pass
    print(nm(e), " <- ", [nm(i).split(" ")[0] if i else None for i in ins] if ins else "")
# Pro 里 Refine 的调用和上游参数
m = unreal.load_asset(R + "/01_Pro/Guiyue_Pro_2607")
for e in mel.get_material_expressions(m):
    if isinstance(e, unreal.MaterialExpressionMaterialFunctionCall) and e.get_editor_property("material_function") == mf:
        ins = mel.get_inputs_for_material_expression(m, e)
        print("Pro 调用 Refine:", [nm(i) if i else None for i in ins])
        for i in ins:
            if i:
                for j in mel.get_inputs_for_material_expression(m, i):
                    print("     上游:", nm(j) if j else None)
