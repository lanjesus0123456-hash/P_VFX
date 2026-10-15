import unreal
mel = unreal.MaterialEditingLibrary
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = [a for a in eas.get_all_level_actors() if a.get_actor_label() == "ChunkFlip_Preview"][0]
mi = unreal.load_asset("/Game/VFXTool_Test/ChunkFlip/MI_A_clone")

cap = [a for a in eas.get_all_level_actors() if a.get_actor_label() == "ChunkFlip_Capture"]
if cap:
    cap = cap[0]
else:
    cap = eas.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(300, 0, 253), unreal.Rotator(0, 0, 180))
    cap.set_actor_label("ChunkFlip_Capture")
cc = cap.capture_component2d
rt = unreal.RenderingLibrary.create_render_target2d(world, 128, 128, unreal.TextureRenderTargetFormat.RTF_RGBA8)
cc.set_editor_property("texture_target", rt)
cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_BASE_COLOR)
cc.set_editor_property("primitive_render_mode", unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
cc.show_only_actor_components(actor)
cc.set_editor_property("capture_every_frame", False)
cc.set_editor_property("fov_angle", 40.0)

def shot(tag, **params):
    for k, v in params.items():
        mel.set_material_instance_scalar_parameter_value(mi, k, v)
    mel.update_material_instance(mi)
    cc.capture_scene()
    px = unreal.RenderingLibrary.read_render_target(world, rt)
    W = 128
    on = [(i % W, i // W) for i, c in enumerate(px) if (c.r + c.g + c.b) > 6]
    if on:
        xs = [p[0] for p in on]; ys = [p[1] for p in on]
        bb = (min(xs), min(ys), max(xs), max(ys))
    else:
        bb = None
    print("%-28s 覆盖=%5d  包围框=%s" % (tag, len(on), bb))
    return len(on), bb

base = dict(Flow=1.2, ChunkScale=1.0, MinScale=0.0, RandSpread=0.0, CurveMode=0.0, Reverse=0.0, Band=0.2)
shot("完整(Flow=1.2)", **base)
shot("未生长(Flow=-0.2)", **dict(base, Flow=-0.2))
shot("生长一半(Flow=0.5)", **dict(base, Flow=0.5))
shot("完整+每块缩小一半", **dict(base, ChunkScale=0.5))
shot("反向一半", **dict(base, Flow=0.5, Reverse=1.0))
shot("恢复默认", **dict(base, Flow=0.5, RandSpread=0.15, Reverse=0.0))
