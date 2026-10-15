# -*- coding: utf-8 -*-
"""
构建特效母材质 M_VFX_Master（UE 5.8）

功能（每项一个静态开关，关闭不参与编译）：
  全局：使用粒子数据 / 顶点色权重 / 整体旋转 / 混合模式与深度（材质实例里覆盖）
  自发光（主贴图 + RefineColor） / 序列帧 / 叠加 / 遮罩 / 溶解 / 扰动 / 菲涅尔 / 透明度菲涅尔
  软粒子 / 顶点偏移 / VAT 顶点动画 / 折射 / 流动贴图 / 色散 / 视差映射 / 故障 / 碎块翻转生长

粒子数据（Niagara Dynamic Parameter）：
  Param1/2 = 主贴图平铺偏移的 Offset U/V   Param3 = 溶解进度   Param4 = 扰动总强度
"""
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(os.path.dirname(HERE), "ChunkFlip")):
    if p not in sys.path:
        sys.path.insert(0, p)

import vfx_graph  # noqa: E402
import vfx_hlsl as H  # noqa: E402


from vfx_graph import Graph, F1, F2, F3, F4, mel  # noqa: E402

DEST = "/Game/VFX/Materials/Master"
NAME = "M_VFX_Master"
TEX = "/Game/归玥材质包LTS/09_Temp/Texture/"
T_MAIN = TEX + "Tex_Mask_001"
T_NOISE = TEX + "Tex_Noise_001"
T_MASK = TEX + "Tex_Mask_002"
T_WHITE = "/Engine/EngineResources/WhiteSquareTexture"

MP = unreal.MaterialProperty
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

# 分组名：数字前缀控制面板顺序
G0 = "00 全局"
G1 = "01 自发光"
G3 = "02 叠加"
G4 = "03 遮罩"
G2 = "04 序列帧"
G5 = "05 溶解"
G6 = "06 扰动"
G7 = "07 菲涅尔"
G8 = "08 透明度菲涅尔"
G9 = "09 软粒子"
G10 = "10 顶点偏移"
G11 = "11 VAT顶点动画"
G12 = "12 折射"
G13 = "13 流动贴图"
G15 = "14 色散"
G16 = "15 视差映射"
G17 = "16 故障"
G14 = "17 碎块翻转"

VAT_MF = "/Game/归玥材质包LTS/07_MF/Guiyue_Vat_Revamp"
ENUM_DIR = "/Game/VFX/Materials/Master/Enums"


def _material():
    path = "%s/%s" % (DEST, NAME)
    mat = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if isinstance(mat, unreal.Material):
        # 先断开所有材质输出，再删节点：否则每删一个节点都会触发一次残缺图的编译，
        # 上百次失败编译会把编辑器内存吃光（2026-10-07 实测崩溃过一次）
        for prop in (MP.MP_EMISSIVE_COLOR, MP.MP_OPACITY, MP.MP_OPACITY_MASK, MP.MP_BASE_COLOR,
                     MP.MP_WORLD_POSITION_OFFSET, MP.MP_REFRACTION, MP.MP_NORMAL):
            n = mel.get_material_property_input_node(mat, prop)
            if n is not None:
                mel.delete_material_expression(mat, n)
        mel.delete_all_material_expressions(mat)
        # 手动编辑留下的孤立节点 delete_all 有时删不掉，逐个清
        for e in list(mel.get_material_expressions(mat)):
            mel.delete_material_expression(mat, e)
        left = mel.get_material_expressions(mat)
        if left:
            raise RuntimeError("旧节点没清干净: %s" % [e.get_name() for e in left])
    else:
        mat = asset_tools.create_asset(NAME, DEST, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("refraction_method", unreal.RefractionMode.RM_2D_OFFSET)
    for p in ("used_with_niagara_sprites", "used_with_niagara_ribbons", "used_with_niagara_mesh_particles",
              "used_with_particle_sprites", "used_with_mesh_particles", "used_with_static_lighting"):
        try:
            mat.set_editor_property(p, p != "used_with_static_lighting")
        except Exception:
            pass
    return mat


def _enum_param(g, name, default, group, prio, enum_name, labels):
    """下拉栏参数：标量 + UserDefinedEnum，ControlType 必须设为 Enumeration 才会显示成下拉栏。
    枚举资产不存在时只建空壳，需要在编辑器里补选项。"""
    key = "enum_" + name
    if key in g.cache:
        return g.cache[key]
    p = g.scalar(name, default, group, prio)
    path = "%s/%s" % (ENUM_DIR, enum_name)
    e = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if e is None:
        fac = unreal.new_object(unreal.load_class(None, "/Script/UnrealEd.EnumFactory"))
        e = asset_tools.create_asset(enum_name, ENUM_DIR, unreal.UserDefinedEnum, fac)
        unreal.EditorAssetLibrary.save_loaded_asset(e)
        ENUMS_TODO.append((path, labels))
    elif _enum_count(e) < len(labels):
        ENUMS_TODO.append((path, labels))
    p.set_editor_property("control_type", unreal.MaterialScalarParameterControlType.ENUMERATION)
    p.set_editor_property("enumeration", e)
    g.cache[key] = p
    return p


def _enum_count(e):
    # Python 读不到枚举项，借用 T3D 导出数 Names 条目
    t = unreal.AssetExportTask()
    t.object = e
    t.filename = os.path.join(HERE, "_dev", "_enum.t3d")
    t.automated, t.prompt, t.replace_identical = True, False, True
    t.exporter = unreal.ObjectExporterT3D()
    if not unreal.Exporter.run_asset_export_task(t):
        return 0
    raw = open(t.filename, "rb").read()
    txt = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "ignore")
    return max(0, txt.count("NewEnumerator") - (1 if "_MAX" in txt else 0))


ENUMS_TODO = []


def _globals(g):
    """全局参数、粒子数据、16 故障、14 色散偏移：只建一次，三个颜色通道共用。"""
    t = g.time()
    # ------------------------------------------------------------------ 00 全局
    g.dyn(["主贴图偏移U", "主贴图偏移V", "溶解进度", "扰动总强度"])
    rot = g.scalar("整体旋转", 0.0, G0, 2, -180, 180)
    uv_rot = g.custom("整体旋转", H.ROTATE_UV, [("UV", g.uv(0)), ("Angle", rot)], F2)
    vcol = g.vector("模型顶点色权重(RGB颜色 A透明)", (1, 1, 1, 1), G0, 1)
    out = dict(t=t)
    out["vc_c"] = g.custom("顶点色权重RGB", "return W.r;", [("W", vcol)], F1)
    out["vc_a"] = g.custom("顶点色权重A", "return W.a;", [("W", vcol)], F1)
    pd = "使用粒子数据?"
    # 粒子数据开：P1/P2 替换主贴图平铺偏移的 ZW，P3 替换溶解进度，P4 替换扰动总强度(R)
    main_st_p = g.vector("主贴图 平铺偏移", (1, 1, 0, 0), G1, 3)
    out["main_st"] = g.gate(pd, False, G0, g.custom("粒子偏移", H.REPLACE_ZW,
                            [("ST", main_st_p), ("P", g.append(g.dyn_ch(0), g.dyn_ch(1)))], F4), main_st_p, 0)
    out["p_dis"] = g.gate(pd, False, G0, g.dyn_ch(2), g.scalar("溶解进度", 0.0, G5, 1, 0, 1), 0)
    dst_p = g.vector("扰动强度(总/U/V/Z)", (0.05, 1, 1, 0), G6, 1)
    out["dst_s"] = g.gate(pd, False, G0, g.custom("粒子扰动", H.REPLACE_X,
                          [("S", dst_p), ("P", g.dyn_ch(3))], F4), dst_p, 0)

    # ------------------------------------------------------------------ 16 故障
    # 错位加在基础 UV 上，遮罩/溶解/叠加等所有图层一起被切开
    gl = g.custom("故障", H.GLITCH, [
        ("UV", uv_rot),
        ("G", g.vector("故障(强度/切块行数/频率/错位距离)", (0.5, 12, 8, 0.15), G17, 1)),
        ("G2", g.vector("故障(RGB分离/切块列数/闪烁/扫描线)", (2, 1, 0.3, 0), G17, 2)),
        ("Time", t)], F2, [("Split", F2), ("Flick", F1)])
    on = "故障?"
    uv_g = g.add(uv_rot, g.gate(on, False, G17, gl, g.c2(0, 0)))
    out["uv0"] = uv_g
    out["flick"] = g.gate(on, False, G17, (gl, "Flick"), g.c(1))
    gl_split = g.gate(on, False, G17, (gl, "Split"), g.c2(0, 0))

    # ------------------------------------------------------------------ 14 色散
    # 对最终结果做 RGB 分离：R/G/B 三个通道各算一遍完整效果，UV 分别 +偏移 / 0 / -偏移
    d_mask = g.custom("色散遮罩", H.MASK, [
        ("Tex", g.texture("色散遮罩", T_WHITE, G15, 4)), ("TUV", _uv(g, "色散遮罩", G15, 5, uv_g)),
        ("Ch", g.vector("色散遮罩 通道", (1, 0, 0, 0), G15, 7))], F1)
    disp = g.custom("色散偏移", H.DISP_OFFSET, [
        ("UV", uv_g), ("Mask", d_mask),
        ("D", g.vector("色散(方向U/方向V/强度/-)", (1, 0, 1, 0), G15, 1)),
        ("P", g.vector("色散极坐标(径向/旋转/中心U/中心V)", (1, 0, 0.5, 0.5), G15, 3)),
        ("Polar", g.gate("色散 极坐标?", False, G15, g.c(1), g.c(0), 2))], F2)
    disp = g.gate("色散?", False, G15, disp, g.c2(0, 0))
    out["split"] = g.add(disp, gl_split)
    vt = g.new(unreal.MaterialExpressionTransform)
    vt.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD)
    vt.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_TANGENT)
    g.link(g.camera_vec(), vt, "")
    out["view_t"] = vt
    return out


def _front(g, gb, uv0):
    """单个颜色通道的 UV 相关部分：流动贴图 / 扰动 / 视差 / 主贴图 / 序列帧。uv0 已含故障和色散偏移。"""
    t = gb["t"]
    # ------------------------------------------------------------------ 13 流动贴图
    flow = g.custom("流动贴图", H.FLOWMAP, [
        ("Tex", g.texture("流动贴图", T_NOISE, G13, 1)), ("FUV", _uv(g, "流动贴图", G13, 2, uv0)),
        ("Strength", g.scalar("流动强度", 0.1, G13, 4, 0, 1)),
        ("Speed", g.scalar("流动速度", 0.5, G13, 5, 0, 5)), ("Time", t)], F2,
        [("FlowB", F2), ("Blend", F1)])
    fl = "流动贴图?"
    flow_a = g.gate(fl, False, G13, flow, g.c2(0, 0))
    flow_b = g.gate(fl, False, G13, (flow, "FlowB"), g.c2(0, 0))
    flow_w = g.gate(fl, False, G13, (flow, "Blend"), g.c(0))

    # ------------------------------------------------------------------ 06 扰动
    d_uv = _uv(g, "扰动", G6, 3, uv0, pan=(0.1, 0.1, 0, 0))
    d_tex = g.texture("扰动贴图", T_NOISE, G6, 2)
    d_mask = g.custom("扰动遮罩", H.MASK, [
        ("Tex", g.texture("扰动遮罩", T_WHITE, G6, 5)), ("TUV", uv0),
        ("Ch", g.vector("扰动遮罩 通道", (1, 0, 0, 0), G6, 6))], F1)
    dist = g.custom("扰动", H.DISTORT, [("Tex", d_tex), ("NUV", d_uv), ("S", gb["dst_s"]), ("Mask", d_mask)], F2)
    dist = g.gate("扰动?", False, G6, dist, g.c2(0, 0))
    dist_z = g.custom("扰动Z", H.DISTORT_Z, [("Tex", d_tex), ("NUV", d_uv), ("S", gb["dst_s"])], F3)
    dist_z = g.gate("扰动?", False, G6, dist_z, g.c3(0, 0, 0))
    dist_mask = g.gate("扰动影响遮罩?", False, G6, dist, g.c2(0, 0), 7)
    dist_col = g.gate("扰动影响颜色?", True, G6, dist, g.c2(0, 0), 8)
    dist_dis = g.gate("扰动影响溶解?", True, G6, dist, g.c2(0, 0), 9)

    # ------------------------------------------------------------------ 15 视差映射
    vt = gb["view_t"]
    par = g.custom("视差映射", H.PARALLAX, [
        ("Tex", g.texture("视差 高度图", T_NOISE, G16, 1)), ("UV", uv0), ("VT", vt),
        ("P", g.vector("视差(深度/步数/高度通道0R1G2B3A/反向)", (0.05, 16, 0, 0), G16, 2))], F2)
    par = g.gate("视差映射?", False, G16, par, g.c2(0, 0))

    # ------------------------------------------------------------------ 01 自发光 + 04 序列帧
    extra = g.custom("主贴图UV偏移", "return A + B;", [("A", dist_col), ("B", par)], F2)
    m_uv = g.custom("主贴图UV", H.UV_FUNC, [
        ("UV", uv0), ("ST", gb["main_st"]),
        ("Pan", g.vector("主贴图 速度UV/旋转/极坐标", (0, 0, 0, 0), G1, 4)),
        ("Time", t), ("Extra", extra)], F2)
    fb = g.custom("序列帧", H.FLIPBOOK, [
        ("UV", m_uv), ("Grid", g.vector("序列帧 列/行/帧率/手动(0或1)", (4, 4, 15, 0), G2, 1)),
        ("Frame", g.scalar("序列帧 手动帧", 0.0, G2, 2)), ("Time", t)], F2)
    m_uv = g.gate("序列帧动画?", False, G2, fb, m_uv)
    main_t = g.custom("主贴图采样", H.SAMPLE_MAIN, [
        ("Tex", g.texture("主贴图", T_MAIN, G1, 1)), ("TUV", m_uv),
        ("FlowA", flow_a), ("FlowB", flow_b), ("Blend", flow_w)], F4)
    refine = g.custom("RefineColor", H.REFINE, [
        ("T", main_t), ("Ctrl", g.vector("Refine 颜色控制(Power/HDR/Soft/Lerp)", (1, 1, 1, 0.5), G1, 10))], F4)
    main = g.gate("RefineColor?", True, G1, refine, main_t, 9)
    return dict(t=t, uv0=uv0, dist=dist_dis, dist_mask=dist_mask, dist_col=dist_col, dist_z=dist_z,
                main=main, p_dis=gb["p_dis"], vc_c=gb["vc_c"], vc_a=gb["vc_a"])


def _uv(g, label, grp, prio, uv0, pan=(0, 0, 0, 0), extra=None):
    return g.custom(label + "UV", H.UV_FUNC, [
        ("UV", uv0), ("ST", g.vector(label + " 平铺偏移", (1, 1, 0, 0), grp, prio)),
        ("Pan", g.vector(label + " 速度UV/旋转/极坐标", pan, grp, prio + 1)),
        ("Time", g.time()), ("Extra", extra if extra is not None else g.c2(0, 0))], F2)


def _layers(g, f):
    """叠加 / 遮罩 / 溶解 / 菲涅尔 / 软粒子"""
    uv0, out = f["uv0"], {}
    # 02 叠加：乘法 / 加法（下拉栏）
    add = g.custom("叠加", H.ADD, [
        ("Tex", g.texture("叠加贴图", T_NOISE, G3, 1)), ("TUV", _uv(g, "叠加", G3, 3, uv0, extra=f["dist_col"])),
        ("Col", g.vector("叠加颜色(A=强度)", (1, 1, 1, 1), G3, 5))], F4, [("K", F1)])
    out["add"] = g.gate("叠加?", False, G3, add, g.c4(1, 1, 1, 1))
    out["add_k"] = g.gate("叠加?", False, G3, (add, "K"), g.c(0))
    out["add_mode"] = _enum_param(g, "叠加方式", 0.0, G3, 2, "E_VFX_BlendOp", ["乘法叠加", "加法叠加"])
    out["add_a"] = g.scalar("叠加 影响透明度", 0.0, G3, 6, 0, 1)
    # 03 遮罩
    mask = g.custom("遮罩", H.MASK, [
        ("Tex", g.texture("遮罩贴图", T_MASK, G4, 1)), ("TUV", _uv(g, "遮罩", G4, 2, uv0, extra=f["dist_mask"])),
        ("Ch", g.vector("遮罩 通道", (1, 0, 0, 0), G4, 4))], F1)
    out["mask"] = g.gate("遮罩?", False, G4, mask, g.c(1))
    # 05 溶解
    dis = g.custom("溶解", H.DISSOLVE, [
        ("Tex", g.texture("溶解贴图", T_NOISE, G5, 2)), ("DUV", _uv(g, "溶解", G5, 3, uv0, extra=f["dist"])),
        ("Ch", g.vector("溶解 通道", (1, 0, 0, 0), G5, 5)), ("BaseUV", g.uv(0)),
        ("Dir", g.vector("方向溶解(方向UV/强度/开关)", (0, 1, 0.5, 0), G5, 6)),
        ("Amount", f["p_dis"]), ("Soft", g.scalar("溶解 软硬", 0.1, G5, 7, 0, 1)),
        ("EdgeW", g.scalar("溶解 描边宽度", 0.05, G5, 8, 0, 0.5))], F1, [("Edge", F1)])
    out["dis"] = g.gate("溶解?", False, G5, dis, g.c(1))
    out["edge"] = g.gate("溶解?", False, G5, (dis, "Edge"), g.c(0))
    out["edge_col"] = g.vector("溶解 描边颜色(A=强度)", (1, 0.5, 0.1, 4), G5, 9)
    # 07 菲涅尔 / 08 透明度菲涅尔 / 09 软粒子：与 UV 无关，三个颜色通道共用一份
    if "layers_static" not in g.cache:
        st = {}
        base = [("N", g.normal_ws()), ("V", g.camera_vec()), ("Sign", g.two_sided_sign())]
        fres = g.custom("菲涅尔", H.FRESNEL, base + [
            ("Pw", g.scalar("菲涅尔 范围", 3.0, G7, 2, 0.1, 10)), ("Str", g.c(1)),
            ("Inv", g.scalar("菲涅尔 反向", 0.0, G7, 3, 0, 1)), ("TS", g.scalar("菲涅尔 双面修正", 1.0, G7, 4, 0, 1))], F1)
        st["fres"] = g.gate("菲涅尔?", False, G7, fres, g.c(0))
        st["fres_col"] = g.vector("菲涅尔颜色(A=强度)", (1, 1, 1, 1), G7, 1)
        afres = g.custom("透明度菲涅尔", H.FRESNEL, base + [
            ("Pw", g.scalar("透明度菲涅尔 范围", 2.0, G8, 1, 0.1, 10)),
            ("Str", g.scalar("透明度菲涅尔 强度", 1.0, G8, 2, 0, 5)),
            ("Inv", g.scalar("透明度菲涅尔 反向", 1.0, G8, 3, 0, 1)),
            ("TS", g.scalar("透明度菲涅尔 双面修正", 1.0, G8, 4, 0, 1))], F1)
        st["afres"] = g.gate("透明度菲涅尔?", False, G8, afres, g.c(1))
        # 09 软粒子
        df = g.new(unreal.MaterialExpressionDepthFade)
        g.link(g.c(1), df, "Opacity")
        g.link(g.scalar("软粒子 距离", 20.0, G9, 1, 0, 200), df, "FadeDistance")
        st["soft"] = g.gate("触边虚化(软粒子)?", False, G9, df, g.c(1))
        g.cache["layers_static"] = st
    out.update(g.cache["layers_static"])
    return out


def _chunk_sections():
    src = open(os.path.join(os.path.dirname(HERE), "ChunkFlip", "ChunkFlipGrow.hlsl"), encoding="utf-8").read()
    secs, cur = {}, None
    for line in src.splitlines():
        if line.startswith("// @@"):
            cur = line[5:].strip()
            secs[cur] = []
        elif cur:
            secs[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in secs.items()}


def _chunk(g):
    """14 碎块翻转生长：PS 输出透明度和发光，VS 输出本地偏移。"""
    sec = _chunk_sections()
    common = [("Growth", g.uv(1)), ("PivotZRand", g.uv(3)),
              ("Flow", g.scalar("流动值", 0.5, G14, 1, -0.2, 1.2)),
              ("Band", g.scalar("流动区域范围", 0.2, G14, 2, 0.01, 1)),
              ("RandSpread", g.scalar("随机错开", 0.15, G14, 3, 0, 0.5)),
              ("CurveMode", g.scalar("曲线(0生长 1消散 2掠过)", 0.0, G14, 4, 0, 2)),
              ("Reverse", g.scalar("反向", 0.0, G14, 5, 0, 1))]
    ps = g.custom("碎块翻转_PS", sec["COMMON"] + "\n" + sec["PS"], common + [
        ("HeadCol", g.vector("头部颜色", (1, 0.35, 0.05, 1), G14, 20)),
        ("MidCol", g.vector("中部颜色", (1, 0.85, 0.4, 1), G14, 21)),
        ("TailCol", g.vector("尾部颜色", (0.25, 0.6, 1, 1), G14, 22))], F3,
        [("Phase", F1), ("Grow", F1)])
    glow = g.custom("碎块扫描带发光", H.CHUNK_GLOW,
                    [("Phase", (ps, "Phase")), ("Tint", ps),
                     ("Col", g.vector("扫描带发光(A=强度)", (1, 1, 1, 3), G14, 23))], F3)
    vs = g.custom("碎块翻转_VS", sec["COMMON"] + "\n" + sec["VS"], [
        ("LocalPos", g.local_pos()), ("PivotXY", g.uv(2))] + common + [
        ("MinScale", g.scalar("未长出缩放", 0.0, G14, 10, 0, 1)),
        ("ChunkScale", g.scalar("方块大小", 1.0, G14, 11, 0, 2)),
        ("HeadRot", g.vector("头部旋转XYZ", (180, 90, 0, 0), G14, 12)),
        ("MidRot", g.vector("中部旋转XYZ", (30, 0, 0, 0), G14, 13)),
        ("TailRot", g.vector("尾部旋转XYZ", (0, 0, 0, 0), G14, 14))], F3)
    on = "碎块翻转生长?"
    return dict(a=g.gate(on, False, G14, (ps, "Grow"), g.c(1)),
                glow=g.gate(on, False, G14, glow, g.c3(0, 0, 0)),
                wpo=g.gate(on, False, G14, vs, g.c3(0, 0, 0)))


def _vertex(g, f, chunk_wpo):
    """10 顶点偏移 + 扰动Z + 碎块翻转（本地空间，求和后转世界）+ 11 VAT（世界空间）"""
    nrm_l = g.new(unreal.MaterialExpressionTransform)
    nrm_l.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD)
    nrm_l.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_LOCAL)
    g.link(g.normal_ws(), nrm_l, "")
    vo = g.custom("顶点偏移", H.VERTEX_OFFSET, [
        ("Tex", g.texture("顶点偏移贴图", T_NOISE, G10, 1)), ("UV", f["uv0"]), ("N", nrm_l),
        ("Ctrl", g.vector("顶点偏移(强度/速度U/速度V/平铺)", (5, 0.2, 0.2, 1), G10, 2)),
        ("Ch", g.vector("顶点偏移 通道", (1, 0, 0, 0), G10, 3)),
        ("Bias", g.scalar("顶点偏移 双向(0单向 1双向)", 1.0, G10, 4, 0, 1)), ("Time", g.time())], F3)
    vo = g.gate("顶点偏移?", False, G10, vo, g.c3(0, 0, 0))
    s = g.custom("本地偏移求和", H.SUM3, [("A", chunk_wpo), ("B", vo), ("C", f["dist_z"])], F3)
    xf = g.new(unreal.MaterialExpressionTransform)
    xf.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
    xf.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    g.link(s, xf, "")
    # VAT：Houdini Labs Vertex Animation Textures（归玥 Guiyue_Vat_Revamp），参数在函数里，实例面板可见
    vat = g.mf(VAT_MF, {})
    vat = g.gate("VAT顶点动画?", False, G11, (vat, "World Position Offset"), g.c3(0, 0, 0))
    return g.add(xf, vat)


def _pass(g, gb, uv0, ck):
    """完整算一遍颜色和透明度（色散时 R/G/B 各算一遍）。"""
    f = _front(g, gb, uv0)
    L = _layers(g, f)
    col = g.custom("最终合成", H.COMBINE, [
        ("Main", f["main"]), ("Tint", g.vector("主颜色(A=强度)", (1, 1, 1, 1), G1, 0)),
        ("Add", L["add"]), ("AddK", L["add_k"]), ("AddMode", L["add_mode"]), ("AddAlpha", L["add_a"]),
        ("MaskV", L["mask"]),
        ("Dis", L["dis"]), ("Edge", L["edge"]), ("EdgeCol", L["edge_col"]),
        ("Fres", L["fres"]), ("FresCol", L["fres_col"]), ("AFres", L["afres"]),
        ("VC", g.vcolor_rgba()), ("VCc", f["vc_c"]), ("VCa", f["vc_a"]),
        ("ChunkA", ck["a"]), ("ChunkGlow", ck["glow"]), ("Flick", gb["flick"]),
        ("Opacity", g.scalar("整体透明度", 1.0, G0, 3, 0, 1)), ("SoftP", L["soft"]),
        ("PremulA", g.scalar("颜色乘透明度(Additive用1)", 0.0, G0, 4, 0, 1))], F3, [("Alpha", F1)])
    return f, col


def build():
    mat = _material()
    g = Graph(mat)
    gb = _globals(g)
    ck = _chunk(g)

    # G 通道（也是不分离时的结果）用原 UV，R/B 通道错开
    fG, cG = _pass(g, gb, gb["uv0"], ck)
    _, cR = _pass(g, gb, g.add(gb["uv0"], gb["split"]), ck)
    _, cB = _pass(g, gb, g.custom("UV减", "return A - B;", [("A", gb["uv0"]), ("B", gb["split"])], F2), ck)
    rgb = g.custom("RGB分离合成", H.RGB_SPLIT, [
        ("R", cR), ("G", cG), ("B", cB), ("AR", (cR, "Alpha")), ("AG", (cG, "Alpha")), ("AB", (cB, "Alpha")),
        ("Pm", g.scalar("颜色乘透明度(Additive用1)", 0.0, G0, 4, 0, 1))], F3, [("Alpha", F1)])
    # 色散和故障都关时，R/B 两遍不参与编译
    col = g.gate("色散?", False, G15, rgb, g.gate("故障?", False, G17, rgb, cG))
    alpha = g.gate("色散?", False, G15, (rgb, "Alpha"),
                   g.gate("故障?", False, G17, (rgb, "Alpha"), (cG, "Alpha")))
    g.output(col, MP.MP_EMISSIVE_COLOR)
    g.output(alpha, MP.MP_OPACITY)

    # 12 折射：控制方式下拉栏（通道 / 贴图 / 相乘 / 相加）
    refr = g.custom("折射", H.REFRACT, [
        ("C", col), ("A", alpha),
        ("Ch", g.vector("折射 控制通道(RGBA)", (0, 0, 0, 1), G12, 2)),
        ("Tex", g.texture("折射贴图", T_NOISE, G12, 4)),
        ("RUV", _uv(g, "折射", G12, 5, gb["uv0"], pan=(0.05, 0.05, 0, 0))),
        ("Mode", _enum_param(g, "折射控制方式", 0.0, G12, 1, "E_VFX_RefractMode",
                             ["通道控制", "贴图控制", "通道x贴图", "通道+贴图"])),
        ("S", g.vector("折射强度(总/U/V/-)", (0.05, 1, 1, 0), G12, 3))], F2)
    g.output(g.gate("折射?", False, G12, refr, g.c2(0, 0)), MP.MP_REFRACTION)

    g.output(_vertex(g, fG, ck["wpo"]), MP.MP_WORLD_POSITION_OFFSET)

    mel.layout_material_expressions(mat)
    g.verify()
    g.finish()
    mel.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    if ENUMS_TODO:
        unreal.log_warning("[VFXMaster] 以下枚举需要手动补选项: %s" % ENUMS_TODO)
    return mat


# ----------------------------------------------------------------------------
# 预设实例：常用混合方式
# ----------------------------------------------------------------------------
PRESETS = {
    "MI_VFX_Additive": dict(blend=unreal.BlendMode.BLEND_ADDITIVE, scalars={"颜色乘透明度(Additive用1)": 1.0}),
    "MI_VFX_Translucent": dict(blend=unreal.BlendMode.BLEND_TRANSLUCENT, scalars={}),
}


def make_presets(mat):
    out = []
    for name, cfg in PRESETS.items():
        path = "%s/%s" % (DEST, name)
        mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
        if not isinstance(mi, unreal.MaterialInstanceConstant):
            mi = asset_tools.create_asset(name, DEST, unreal.MaterialInstanceConstant,
                                          unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, mat)
        ov = mi.get_editor_property("base_property_overrides")
        ov.set_editor_property("override_blend_mode", True)
        ov.set_editor_property("blend_mode", cfg["blend"])
        mi.set_editor_property("base_property_overrides", ov)
        for k, v in cfg["scalars"].items():
            mel.set_material_instance_scalar_parameter_value(mi, k, v)
        mel.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        out.append(mi)
    return out


if __name__ == "__main__":
    m = build()
    make_presets(m)
    unreal.log("[VFXMaster] 完成: %s" % m.get_path_name())
