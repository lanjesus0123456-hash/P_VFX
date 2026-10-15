# 在 UE 里执行：渲染测试工具函数（被 rt_host.py 分步调用）
import unreal
mel = unreal.MaterialEditingLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
D = "/Game/VFX/Materials/Master/_Test"
M = unreal.load_asset("/Game/VFX/Materials/Master/M_VFX_Master")

def find(label):
    for a in eas.get_all_level_actors():
        if a.get_actor_label() == label:
            return a

TEST_MAP = "/Game/VFXTool_Test/map_vfx_test"


def setup(mesh="/Engine/BasicShapes/Plane"):
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not w.get_path_name().startswith(TEST_MAP):
        raise RuntimeError("当前不是测试关卡(%s)，不在这里摆测试物体" % w.get_path_name())
    for l in ("VFXM_TestPlane", "VFXM_Cap", "VFXM_Capture"):
        a = find(l)
        if a: eas.destroy_actor(a)
    p = eas.spawn_actor_from_object(unreal.load_asset(mesh), unreal.Vector(0, 2000, 300), unreal.Rotator(roll=0, pitch=90, yaw=0))
    p.set_actor_label("VFXM_TestPlane")
    c = eas.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(-150, 2000, 300), unreal.Rotator(0, 0, 0))
    c.set_actor_label("VFXM_Cap")
    cc = c.capture_component2d
    rt = unreal.RenderingLibrary.create_render_target2d(world, 64, 64, unreal.TextureRenderTargetFormat.RTF_RGBA16F)
    unreal.EditorAssetLibrary.does_asset_exist  # noqa
    cc.set_editor_property("texture_target", rt)
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_SCENE_COLOR_HDR)
    cc.set_editor_property("capture_every_frame", False)
    cc.set_editor_property("fov_angle", 50.0)
    path = D + "/MI_Render"
    mi = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
        at.create_asset("MI_Render", D, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, M)
    mel.clear_all_material_instance_parameters(mi)
    mel.update_material_instance(mi)
    p.static_mesh_component.set_material(0, mi)
    globals()["_rt"] = rt

def mi():
    return unreal.load_asset(D + "/MI_Render")

def set_params(scalars=None, switches=None, vectors=None, blend=None):
    m = mi()
    for k, v in (switches or {}).items():
        mel.set_material_instance_static_switch_parameter_value(m, k, v)
    for k, v in (scalars or {}).items():
        mel.set_material_instance_scalar_parameter_value(m, k, v)
    for k, v in (vectors or {}).items():
        mel.set_material_instance_vector_parameter_value(m, k, unreal.LinearColor(*v))
    if blend is not None:
        ov = m.get_editor_property("base_property_overrides")
        ov.set_editor_property("override_blend_mode", True)
        ov.set_editor_property("blend_mode", blend)
        m.set_editor_property("base_property_overrides", ov)
    mel.update_material_instance(m)

def capture(show_plane=True):
    p, c = find("VFXM_TestPlane"), find("VFXM_Cap")
    cc = c.capture_component2d
    cc.clear_hidden_components()
    if not show_plane:
        cc.hide_actor_components(p)
    cc.capture_scene()
    px = unreal.RenderingLibrary.read_render_target(world, cc.get_editor_property("texture_target"))
    return [(q.r, q.g, q.b) for q in px]


# ---------------------------------------------------------------- 每个功能一个测试实例
def make_mi(name, switches, vectors=None, scalars=None):
    path = D + "/" + name
    m = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
        at.create_asset(name, D, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(m, M)
    mel.clear_all_material_instance_parameters(m)
    for k, v in switches.items():
        mel.set_material_instance_static_switch_parameter_value(m, k, v)
    for k, v in (vectors or {}).items():
        mel.set_material_instance_vector_parameter_value(m, k, unreal.LinearColor(*v))
    for k, v in (scalars or {}).items():
        mel.set_material_instance_scalar_parameter_value(m, k, v)
    mel.update_material_instance(m)
    return m

def use(name, mesh=None):
    p = find("VFXM_TestPlane")
    if mesh:
        p.static_mesh_component.set_static_mesh(unreal.load_asset(mesh))
    p.static_mesh_component.set_material(0, unreal.load_asset(D + "/" + name))

def setp(name, scalars=None, vectors=None):
    m = unreal.load_asset(D + "/" + name)
    for k, v in (scalars or {}).items():
        mel.set_material_instance_scalar_parameter_value(m, k, v)
    for k, v in (vectors or {}).items():
        mel.set_material_instance_vector_parameter_value(m, k, unreal.LinearColor(*v))
    mel.update_material_instance(m)

def settex(name, param, path):
    m = unreal.load_asset(D + "/" + name)
    mel.set_material_instance_texture_parameter_value(m, param, unreal.load_asset(path))
    mel.update_material_instance(m)
