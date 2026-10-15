import json
import math
import traceback
from pathlib import Path
import unreal

ROOT = Path(r"E:\BaiduNetdiskDownload\P_VFX")
REPORT = ROOT / "Saved/VFXMeshTools/Reports/UE58_0_1_1/integration.json"
LEVEL = "/Game/VFXMeshTools_Test/UE58_02/Map_VFXMeshTools_Test"
MATERIALS = "/Game/VFXMeshTools_Test/UE58_02/Materials"
result = {"project": str(ROOT / "P_VFX.uproject"), "engine": unreal.SystemLibrary.get_engine_version(), "level": LEVEL, "status": "running", "checks": []}


def check(ok, name):
    if not ok:
        raise RuntimeError(name)
    result["checks"].append(name)


def material(name, rgb):
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset = tools.create_asset(name, MATERIALS, unreal.Material, unreal.MaterialFactoryNew())
    check(asset is not None, "Create material " + name)
    asset.set_editor_property("two_sided", True)
    color = unreal.MaterialEditingLibrary.create_material_expression(asset, unreal.MaterialExpressionConstant3Vector, -300, 0)
    color.set_editor_property("constant", unreal.LinearColor(*rgb, 1.0))
    unreal.MaterialEditingLibrary.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = unreal.MaterialEditingLibrary.create_material_expression(asset, unreal.MaterialExpressionConstant, -300, 150)
    rough.set_editor_property("r", 0.65)
    unreal.MaterialEditingLibrary.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    unreal.MaterialEditingLibrary.recompile_material(asset)
    check(unreal.EditorAssetLibrary.save_loaded_asset(asset, False), "Save material " + name)
    return asset


def path(points):
    p = unreal.VFXSplinePath()
    p.set_editor_property("points", [unreal.Vector(*v) for v in points])
    return p


def configure(actor, props):
    for key, value in props.items():
        actor.set_editor_property(key, value)
    actor.rebuild()


def mesh_stats(component):
    if component.get_num_sections() == 0:
        return {"vertices": 0, "triangles": 0}
    vertices, indices, normals, uvs, tangents = unreal.ProceduralMeshLibrary.get_section_from_procedural_mesh(component, 0)
    check(len(vertices) > 0 and len(indices) > 0 and len(indices) % 3 == 0, "Nonempty triangle mesh")
    check(all(0 <= i < len(vertices) for i in indices), "Mesh index range")
    check(all(math.isfinite(v.x) and math.isfinite(v.y) and math.isfinite(v.z) for v in vertices), "Finite mesh vertices")
    return {"vertices": len(vertices), "triangles": len(indices) // 3}


def actor_stats(actor):
    pieces = list(actor.get_editor_property("generated_pieces"))
    main = mesh_stats(actor.get_editor_property("main_mesh"))
    piece_stats = [mesh_stats(p) for p in pieces]
    return {"label": actor.get_actor_label(), "mode": str(actor.get_editor_property("mode")), "piece_count": len(pieces), "main": main, "pieces": piece_stats}


def run():
    check(not unreal.EditorAssetLibrary.does_asset_exist(LEVEL), "New dedicated test level path")
    unreal.EditorAssetLibrary.make_directory(MATERIALS)
    unreal.EditorAssetLibrary.make_directory("/Game/VFXMeshTools_Test/UE58_02")
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    check(levels.new_level(LEVEL), "Create dedicated test level")
    mats = {
        "Spline": material("M_Test_Spline", (0.08, 0.55, 1.0)),
        "Helix": material("M_Test_Helix", (0.6, 0.2, 0.95)),
        "Custom": material("M_Test_Custom", (0.1, 0.8, 0.4)),
        "Fracture": material("M_Test_Fracture", (1.0, 0.4, 0.08)),
        "GroundSpikes": material("M_Test_GroundSpikes", (0.15, 0.7, 0.9)),
        "Floor": material("M_Test_Floor", (0.055, 0.065, 0.08))
    }
    for item in actors.get_all_level_actors():
        if isinstance(item, unreal.WorldSettings):
            item.set_editor_property("default_game_mode", unreal.GameModeBase)
    cube = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    floor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 50, -12))
    floor.set_actor_label("VFX_Test_Floor")
    floor.set_actor_scale3d(unreal.Vector(22, 16, 0.2))
    comp = floor.get_component_by_class(unreal.StaticMeshComponent)
    comp.set_static_mesh(cube)
    comp.set_material(0, mats["Floor"])
    floor.set_folder_path("VFX_Test/Stage")
    light = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 700), unreal.Rotator(-50, -35, 0))
    light.set_actor_label("VFX_Test_KeyLight")
    light.set_folder_path("VFX_Test/Stage")
    lc = light.get_component_by_class(unreal.DirectionalLightComponent)
    lc.set_mobility(unreal.ComponentMobility.MOVABLE)
    lc.set_intensity(8)
    fill = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500), unreal.Rotator(-30, 140, 0))
    fill.set_actor_label("VFX_Test_FillLight")
    fill.set_folder_path("VFX_Test/Stage")
    fc = fill.get_component_by_class(unreal.DirectionalLightComponent)
    fc.set_mobility(unreal.ComponentMobility.MOVABLE)
    fc.set_intensity(3)
    camera = actors.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(-1100, -1450, 1200), unreal.Rotator(-32, 58, 0))
    camera.set_actor_label("VFX_Test_Camera")
    camera.set_folder_path("VFX_Test/Stage")
    camera.set_editor_property("auto_activate_for_player", unreal.AutoReceiveInput.PLAYER0)
    camera.get_component_by_class(unreal.CameraComponent).set_field_of_view(65)
    player = actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(0, -650, 150), unreal.Rotator(-10, 90, 0))
    player.set_actor_label("VFX_Test_PlayerStart")
    player.set_folder_path("VFX_Test/Stage")
    descriptions = [
        ("Spline", "01_样条线_双路径", (-650, -350, 50), unreal.VFXMeshToolMode.SPLINE),
        ("Helix", "02_螺旋模型", (0, -350, 0), unreal.VFXMeshToolMode.HELIX),
        ("Custom", "03_自定义_起伏和不规则边缘", (650, -350, 30), unreal.VFXMeshToolMode.CUSTOM),
        ("Fracture", "04_破碎_两个碎片", (-380, 400, 70), unreal.VFXMeshToolMode.FRACTURE),
        ("GroundSpikes", "05_地刺_循环生长", (430, 400, 0), unreal.VFXMeshToolMode.GROUND_SPIKES)
    ]
    tools = {}
    for kind, label, location, mode in descriptions:
        a = actors.spawn_actor_from_class(unreal.VFXMeshToolActor, unreal.Vector(*location))
        a.set_actor_label(label)
        a.set_folder_path("VFX_Test/Models")
        configure(a, {"mode": mode, "material": mats[kind]})
        tools[kind] = a
    configure(tools["Spline"], {
        "spline_paths": [path([(-180,-80,0),(-70,-80,110),(80,-80,30),(180,-80,100)]), path([(-180,80,40),(-70,80,140),(80,80,0),(180,80,110)])],
        "spline_surface": unreal.VFXSplineSurface.TUBE, "spline_width": 25.0, "spline_samples_per_segment": 12
    })
    configure(tools["Helix"], {"helix_height": 280.0, "helix_radius": 100.0, "helix_turns": 2.0, "helix_tube_radius": 16.0})
    height = unreal.VFXHeightPoint()
    height.set_editor_property("position", unreal.Vector2D(0, 0))
    height.set_editor_property("height_offset", 70.0)
    height.set_editor_property("radius", 200.0)
    configure(tools["Custom"], {
        "custom_boundary": [unreal.Vector(-150,-150,0),unreal.Vector(150,-150,40),unreal.Vector(150,150,80),unreal.Vector(-150,150,20)],
        "custom_height_points": [height], "irregular_edge": True, "irregular_amplitude": 22.0, "edge_subdivisions": 10
    })
    configure(tools["Fracture"], {"fracture_source": unreal.load_asset("/Engine/BasicShapes/Plane.Plane"), "fragment_count": 2, "fragment_thickness": 10.0, "fracture_preview_separation": 35.0})
    tools["Fracture"].set_actor_scale3d(unreal.Vector(2.5, 2.5, 2.5))
    spikes = tools["GroundSpikes"]
    layout = spikes.get_editor_property("spike_layout")
    layout.set_editor_property("mode", unreal.VFXSpikeLayout.RING)
    layout.set_editor_property("count", 8)
    layout.set_editor_property("radius", 180.0)
    layout.set_editor_property("seed", 42)
    growth = spikes.get_editor_property("spike_growth")
    growth.set_editor_property("duration", 1.0)
    growth.set_editor_property("stagger", 0.12)
    configure(spikes, {"spike_layout": layout, "spike_growth": growth, "play_growth": True, "loop_growth": True})
    check(spikes.get_generated_piece_count() == 8, "Eight ground spikes in project")
    spikes.set_growth_time(0)
    check(all(p.get_editor_property("RelativeScale3D").z < 0.01 for p in spikes.get_editor_property("generated_pieces")), "Growth starts hidden")
    spikes.set_growth_time(spikes.get_growth_duration() + 0.1)
    check(all(p.get_editor_property("RelativeScale3D").z > 0.99 for p in spikes.get_editor_property("generated_pieces")), "Growth finishes fully grown")
    check(tools["Fracture"].get_generated_piece_count() == 2, "Two fracture pieces in project")
    result["before_save"] = [actor_stats(a) for a in tools.values()]
    for item in result["before_save"]:
        check(item["main"]["triangles"] > 0 or item["piece_count"] > 0, "Visible generated mesh " + item["label"])
    label_texts = ["01 Spline / 2 Paths", "02 Helix", "03 Custom / Irregular Edge", "04 Fracture / 2 Shards", "05 Ground Spikes / Loop Growth"]
    for desc, text in zip(descriptions, label_texts):
        loc = desc[2]
        label = actors.spawn_actor_from_class(unreal.TextRenderActor, unreal.Vector(loc[0], loc[1]-210, 0.5), unreal.Rotator(90, 90, 0))
        label.set_actor_label("Label_" + desc[0])
        label.set_folder_path("VFX_Test/Labels")
        text_component = label.get_component_by_class(unreal.TextRenderComponent)
        text_component.set_text(unreal.Text(text))
        text_component.set_world_size(25.0)
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(unreal.Vector(-1100,-1450,1200), unreal.Rotator(-32,58,0))
    check(levels.save_current_level(), "Save test level")
    check(levels.load_level(LEVEL), "Reload saved test level")
    loaded = [a for a in actors.get_all_level_actors() if isinstance(a, unreal.VFXMeshToolActor)]
    check(len(loaded) == 5, "Five native tool actors survive level reload")
    result["after_reload"] = [actor_stats(a) for a in loaded]
    for item in result["after_reload"]:
        check(item["main"]["triangles"] > 0 or item["piece_count"] > 0, "Generated meshes survive level reload " + item["label"])
    loaded_spikes = next(a for a in loaded if a.get_editor_property("mode") == unreal.VFXMeshToolMode.GROUND_SPIKES)
    check(loaded_spikes.get_editor_property("loop_growth"), "Loop growth setting survives reload")
    unreal.log("VFX_MESH_PROJECT_INTEGRATION_PASS " + LEVEL)


try:
    run()
    result["status"] = "passed"
except Exception:
    result["status"] = "failed"
    result["error"] = traceback.format_exc()
    unreal.log_error(result["error"])
finally:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")