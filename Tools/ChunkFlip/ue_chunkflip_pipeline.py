# -*- coding: utf-8 -*-
"""
碎块翻转生长：转换 + 导入 + 建材质，一步完成（UE 5.8 编辑器内运行）

编辑器里：Tools > Execute Python Script 选这个文件，会转换 SOURCE_FBX；
或在 Output Log 的 Python 命令行里：
    import sys; sys.path.append(r"G:/UE_Project/P_VFX/Tools/ChunkFlip")
    import ue_chunkflip_pipeline as P; P.run(r"D:/xxx.fbx")
"""
import os
import sys

import unreal

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import chunkflip_to_ue as C  # noqa: E402

DEST = "/Game/VFXTool_Test/ChunkFlip"
SOURCE_FBX = os.path.join(TOOLS_DIR, "Test", "A_clone.fbx")
MAT_NAME = "M_ChunkFlipGrow"

mel = unreal.MaterialEditingLibrary
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
_log_lines = []


def log(msg):
    _log_lines.append(str(msg))
    unreal.log("[ChunkFlip] %s" % msg)


# ----------------------------------------------------------------------------
# 导入
# ----------------------------------------------------------------------------
def import_static_mesh(fbx_path, dest):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", fbx_path)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)

    opts = unreal.FbxImportUI()
    opts.set_editor_property("import_mesh", True)
    opts.set_editor_property("import_as_skeletal", False)
    opts.set_editor_property("import_materials", False)
    opts.set_editor_property("import_textures", False)
    opts.set_editor_property("import_animations", False)
    opts.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    sd = opts.get_editor_property("static_mesh_import_data")
    sd.set_editor_property("combine_meshes", True)
    sd.set_editor_property("generate_lightmap_u_vs", False)
    sd.set_editor_property("auto_generate_collision", False)
    sd.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    sd.set_editor_property("import_uniform_scale", 1.0)
    task.set_editor_property("options", opts)

    asset_tools.import_asset_tasks([task])
    paths = list(task.get_editor_property("imported_object_paths") or [])
    meshes = [unreal.load_asset(p) for p in paths]
    meshes = [m for m in meshes if isinstance(m, unreal.StaticMesh)]
    if not meshes:
        raise RuntimeError("导入失败，没有得到 StaticMesh：%s" % paths)
    return meshes[0]


def fix_mesh_settings(sm, extent):
    """全精度 UV、不重算法线、不生成光照 UV、关 Nanite、扩大包围盒。"""
    ses = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    bs = ses.get_lod_build_settings(sm, 0)
    bs.set_editor_property("use_full_precision_u_vs", True)
    bs.set_editor_property("recompute_normals", False)
    bs.set_editor_property("generate_lightmap_u_vs", False)
    ses.set_lod_build_settings(sm, 0, bs)

    ns = sm.get_editor_property("nanite_settings")
    if ns.get_editor_property("enabled"):
        ns.set_editor_property("enabled", False)
        sm.set_editor_property("nanite_settings", ns)

    # 碎块旋转时可能超出原包围盒，留 30% 余量防止被裁剪
    e = unreal.Vector(extent.x * 0.3, extent.y * 0.3, extent.z * 0.3)
    sm.set_editor_property("positive_bounds_extension", e)
    sm.set_editor_property("negative_bounds_extension", e)
    log("UV 通道数: %d" % ses.get_num_uv_channels(sm, 0))


# ----------------------------------------------------------------------------
# 材质
# ----------------------------------------------------------------------------
SCALARS = [  # 名字, 默认值, 分组
    ("Flow", 0.5, "01 流动"), ("Band", 0.2, "01 流动"), ("RandSpread", 0.15, "01 流动"),
    ("Reverse", 0.0, "01 流动"), ("CurveMode", 0.0, "01 流动"),
    ("MinScale", 0.0, "02 缩放"), ("ChunkScale", 1.0, "02 缩放"),
    ("EmissiveStrength", 3.0, "04 颜色"),
]
VECTORS = [
    ("HeadRot", (180.0, 90.0, 0.0), "03 旋转"), ("MidRot", (30.0, 0.0, 0.0), "03 旋转"),
    ("TailRot", (0.0, 0.0, 0.0), "03 旋转"),
    ("HeadCol", (1.0, 0.35, 0.05), "04 颜色"), ("MidCol", (1.0, 0.85, 0.4), "04 颜色"),
    ("TailCol", (0.25, 0.6, 1.0), "04 颜色"),
]
COMMON_INPUTS = ["Growth", "PivotZRand", "Flow", "Band", "RandSpread", "CurveMode", "Reverse"]
VS_INPUTS = ["LocalPos", "PivotXY"] + COMMON_INPUTS + ["MinScale", "ChunkScale", "HeadRot", "MidRot", "TailRot"]
PS_INPUTS = COMMON_INPUTS + ["HeadCol", "MidCol", "TailCol"]


def _hlsl_sections():
    """ChunkFlipGrow.hlsl 按 // @@COMMON / @@VS / @@PS 分段。"""
    src = open(os.path.join(TOOLS_DIR, "ChunkFlipGrow.hlsl"), encoding="utf-8").read()
    secs, cur = {}, None
    for line in src.splitlines():
        if line.startswith("// @@"):
            cur = line[5:].strip()
            secs[cur] = []
        elif cur:
            secs[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in secs.items()}


def _custom(mat, desc, code, inputs, out_type, extra_outs, x, y):
    n = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, x, y)
    n.set_editor_property("description", desc)
    n.set_editor_property("output_type", out_type)
    ins = []
    for name in inputs:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        ins.append(ci)
    n.set_editor_property("inputs", ins)
    outs = []
    for name, t in extra_outs:
        co = unreal.CustomOutput()
        co.set_editor_property("output_name", name)
        co.set_editor_property("output_type", t)
        outs.append(co)
    n.set_editor_property("additional_outputs", outs)
    n.set_editor_property("code", code)
    return n


def _link(a, a_out, b, b_in):
    """连线并检查返回值，失败重试一次，仍失败就报错。"""
    for _ in range(2):
        if mel.connect_material_expressions(a, a_out, b, b_in):
            return
    raise RuntimeError("连线失败: %s.%s -> %s.%s" % (a.get_name(), a_out, b.get_name(), b_in))


def _verify_custom(mat, node, names):
    """确认 Custom 节点每个输入都接上了。"""
    ins = mel.get_inputs_for_material_expression(mat, node)
    missing = [n for n, src in zip(names, ins) if src is None]
    if missing:
        raise RuntimeError("%s 缺少输入: %s" % (node.get_editor_property("description"), missing))


def build_material(dest):
    # 已存在就复用（被实例/Actor 引用时删不掉），清空节点后重建
    path = "%s/%s" % (dest, MAT_NAME)
    mat = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if isinstance(mat, unreal.Material):
        mel.delete_all_material_expressions(mat)
    else:
        mat = asset_tools.create_asset(MAT_NAME, dest, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("two_sided", True)

    def node(cls, x, y):
        return mel.create_material_expression(mat, cls, x, y)

    sec = _hlsl_sections()
    F1, F3 = unreal.CustomMaterialOutputType.CMOT_FLOAT1, unreal.CustomMaterialOutputType.CMOT_FLOAT3
    vs = _custom(mat, "ChunkFlipGrow_VS", sec["COMMON"] + "\n" + sec["VS"], VS_INPUTS, F3, [], -400, -200)
    ps = _custom(mat, "ChunkFlipGrow_PS", sec["COMMON"] + "\n" + sec["PS"], PS_INPUTS, F3,
                 [("Phase", F1), ("Grow", F1)], -400, 300)

    src_nodes = {"LocalPos": node(unreal.MaterialExpressionPreSkinnedPosition, -900, -500)}
    for i, n in ((1, "Growth"), (2, "PivotXY"), (3, "PivotZRand")):
        tc = node(unreal.MaterialExpressionTextureCoordinate, -900, -500 + i * 80)
        tc.set_editor_property("coordinate_index", i)
        src_nodes[n] = tc
    y = -150
    for n, v, grp in SCALARS:
        p = node(unreal.MaterialExpressionScalarParameter, -900, y)
        p.set_editor_property("parameter_name", n)
        p.set_editor_property("default_value", v)
        p.set_editor_property("group", grp)
        src_nodes[n] = p
        y += 70
    for n, v, grp in VECTORS:
        p = node(unreal.MaterialExpressionVectorParameter, -900, y)
        p.set_editor_property("parameter_name", n)
        p.set_editor_property("default_value", unreal.LinearColor(v[0], v[1], v[2], 1.0))
        p.set_editor_property("group", grp)
        src_nodes[n] = p
        y += 120
    for n in VS_INPUTS:
        _link(src_nodes[n], "", vs, n)
    for n in PS_INPUTS:
        _link(src_nodes[n], "", ps, n)

    # WPO：本地偏移 -> 世界
    xf = node(unreal.MaterialExpressionTransform, 0, -200)
    xf.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
    xf.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    _link(vs, "", xf, "")
    mel.connect_material_property(xf, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)

    # 颜色 / 扫描带发光 / 缩没的碎块剔除
    mel.connect_material_property(ps, "", unreal.MaterialProperty.MP_BASE_COLOR)
    edge = _custom(mat, "EdgeGlow", "float e = 1.0 - abs(Phase * 2.0 - 1.0);\nreturn Tint * Strength * e * e;",
                   ["Phase", "Tint", "Strength"], F3, [], 0, 300)
    _link(ps, "Phase", edge, "Phase")
    _link(ps, "", edge, "Tint")
    _link(src_nodes["EmissiveStrength"], "", edge, "Strength")
    mel.connect_material_property(edge, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(ps, "Grow", unreal.MaterialProperty.MP_OPACITY_MASK)
    mat.set_editor_property("opacity_mask_clip_value", 0.01)

    mel.layout_material_expressions(mat)
    # Custom 节点改完 additional_outputs 后输出引脚会重建，首次连到 Transform 的线偶尔丢失，这里补连一次
    _link(vs, "", xf, "")
    _verify_custom(mat, vs, VS_INPUTS)
    _verify_custom(mat, ps, PS_INPUTS)
    _verify_custom(mat, edge, ["Phase", "Tint", "Strength"])
    if mel.get_inputs_for_material_expression(mat, xf)[0] is None:
        raise RuntimeError("Transform 节点没有输入")
    mel.recompile_material(mat)
    return mat



def make_instance(mat, dest, name):
    path = "%s/%s" % (dest, name)
    mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if not isinstance(mi, unreal.MaterialInstanceConstant):
        mi = asset_tools.create_asset(name, dest, unreal.MaterialInstanceConstant,
                                      unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, mat)
    return mi


# ----------------------------------------------------------------------------
# 测试关卡摆放 + 截图
# ----------------------------------------------------------------------------
def place_preview(sm, mi, label="ChunkFlip_Preview"):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in eas.get_all_level_actors():
        if a.get_actor_label().startswith(label):
            eas.destroy_actor(a)
    actor = eas.spawn_actor_from_object(sm, unreal.Vector(0, 0, 200), unreal.Rotator(0, 0, 0))
    actor.set_actor_label(label)
    actor.static_mesh_component.set_material(0, mi)
    return actor


def check_material(mat):
    """编译错误检查：UE 5.x 提供 get_statistics / compile errors 的方式不同，尽量兼容。"""
    errs = []
    try:
        errs = list(mel.get_material_compile_errors(mat) or [])  # 部分版本才有
    except Exception:
        pass
    try:
        st = mel.get_statistics(mat)
        log("材质统计: VS=%s PS=%s" % (st.num_vertex_shader_instructions, st.num_pixel_shader_instructions))
        if st.num_pixel_shader_instructions <= 0:
            errs.append("像素着色器指令数为 0，材质可能编译失败")
    except Exception as e:
        log("读取材质统计失败: %s" % e)
    return errs


# ----------------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------------
def run(src_fbx=SOURCE_FBX, dest=DEST, place=True):
    _log_lines[:] = []
    base = os.path.splitext(os.path.basename(src_fbx))[0]
    out_dir = os.path.join(TOOLS_DIR, "Converted")
    os.makedirs(out_dir, exist_ok=True)
    out_fbx = os.path.join(out_dir, "SM_%s_UE.fbx" % C.re.sub(r"[^\w]", "_", base))
    info = C.convert_file(src_fbx, out_fbx)
    log("转换: 碎块=%d 面=%d -> %s" % (info["chunks"], info["polys"], out_fbx))
    for w in info["warnings"]:
        log("转换警告: " + w)

    sm = import_static_mesh(out_fbx, dest)
    # 重新导入会保留上次的包围盒扩展，先清零再量，避免每跑一次叠加一次
    zero = unreal.Vector(0, 0, 0)
    sm.set_editor_property("positive_bounds_extension", zero)
    sm.set_editor_property("negative_bounds_extension", zero)
    bounds = sm.get_bounds()
    fix_mesh_settings(sm, bounds.box_extent)
    log("StaticMesh: %s  包围盒半径=%.2f" % (sm.get_path_name(), bounds.sphere_radius))

    mat = build_material(dest)
    for e in check_material(mat):
        log("材质错误: " + e)
    mi = make_instance(mat, dest, "MI_%s" % base)
    unreal.EditorAssetLibrary.save_directory(dest, only_if_is_dirty=False, recursive=True)
    log("已保存到 %s" % dest)

    if place:
        a = place_preview(sm, mi)
        log("已在当前关卡放置预览 Actor: %s" % a.get_actor_label())
    return sm, mat, mi


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # 让远程执行能看到错误
        import traceback
        log("失败: %s\n%s" % (exc, traceback.format_exc()))
    finally:
        with open(os.path.join(TOOLS_DIR, "_dev", "last_run.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(_log_lines))
