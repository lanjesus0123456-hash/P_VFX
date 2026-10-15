"""UE 5 editor resource importer. Manifest planning also works outside Unreal."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time

TEXTURES = {".png", ".tga", ".jpg", ".jpeg", ".bmp", ".psd", ".tif", ".tiff", ".exr", ".hdr", ".dds"}
AUDIO = {".wav"}
MODELS = {".fbx", ".obj"}
SUPPORT = TEXTURES | AUDIO | MODELS

def clean_name(value):
    value = re.sub(r"[^A-Za-z0-9_]", "_", value)
    return (value.strip("_") or "Asset")[:80]

def safe_source(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError("无效的资源相对路径：" + str(relative))
    parts = Path(relative).parts
    if Path(relative).is_absolute() or ".." in parts:
        raise ValueError("资源路径超出导出目录：" + relative)
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("资源路径超出导出目录：" + relative)
    return resolved

def read_manifest(filename):
    filename = Path(filename).resolve()
    data = json.loads(filename.read_text(encoding="utf-8-sig"))
    if data.get("schemaVersion") != 1 or not isinstance(data.get("assets"), list):
        raise ValueError("无法识别资源清单版本。")
    guids = set()
    for item in data["assets"]:
        guid = item.get("guid", "")
        if not re.fullmatch(r"[0-9a-fA-F]{32}", guid) or guid.lower() in guids:
            raise ValueError("资源 GUID 无效或重复：" + guid)
        guids.add(guid.lower())
        safe_source(filename.parent, item["file"])
    return filename, data

def plan_manifest(filename, destination="/Game/UnityImports"):
    filename, data = read_manifest(filename)
    destination = destination.rstrip("/")
    if not re.fullmatch(r"/Game(?:/[A-Za-z0-9_]+)+", destination):
        raise ValueError("UE 目录须以 /Game/ 开头，目录名使用字母、数字和下划线。")
    # Include a root identity so same-named prefabs from different locations never collide.
    identity = hashlib.sha256(json.dumps([data.get("sourceProject", ""), data.get("roots", [])], sort_keys=True).encode()).hexdigest()[:8]
    package = clean_name(data.get("name", "UnityResources")) + "_" + identity
    ue_root = destination + "/" + package
    plans = []
    for item in data["assets"]:
        source = safe_source(filename.parent, item["file"])
        suffix = source.suffix.lower()
        parts = Path(item["path"]).parts
        folders = [clean_name(x) for x in parts[:-1] if x not in ("Assets", "Res")]
        folder = ue_root + ("/" + "/".join(folders) if folders else "")
        name = clean_name(source.stem) + "_" + item["guid"][:8]
        reason = ""
        if not source.is_file():
            reason = "导出的源文件不存在"
        elif suffix not in SUPPORT:
            reason = "保留 Unity 源文件和引用信息；UE 无对应资源导入器"
        elif suffix == ".fbx" and item.get("meshCount") == 0:
            reason = "仅骨架/仅动画的 FBX 需要先指定 UE Skeleton"
        plans.append({"record": item, "source": str(source), "folder": folder,
                      "name": name, "reason": reason, "extension": suffix})
    return data, ue_root, plans

def write_json(filename, data):
    filename.parent.mkdir(parents=True, exist_ok=True)
    temporary = filename.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(filename)

def _fbx_options(unreal, record):
    options = unreal.FbxImportUI()
    options.set_editor_property("automated_import_should_detect_type", False)
    skeletal = record.get("skinned", False)
    options.set_editor_property("import_as_skeletal", skeletal)
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    options.set_editor_property("import_animations", skeletal and record.get("animationCount", 0) > 0)
    options.set_editor_property("create_physics_asset", False)
    options.set_editor_property("mesh_type_to_import",
        unreal.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else unreal.FBXImportType.FBXIT_STATIC_MESH)
    import_data = options.get_editor_property("skeletal_mesh_import_data" if skeletal else "static_mesh_import_data")
    import_data.set_editor_property("convert_scene", True)
    import_data.set_editor_property("convert_scene_unit", True)
    if not skeletal:
        import_data.set_editor_property("combine_meshes", False)
        import_data.set_editor_property("auto_generate_collision", False)
    return options

def _texture_settings(unreal, asset, settings):
    if not settings or not isinstance(asset, unreal.Texture):
        return
    asset.set_editor_property("srgb", bool(settings.get("srgb", True)) and not settings.get("normalMap", False))
    if settings.get("normalMap"):
        asset.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
    wrap = {0: unreal.TextureAddress.TA_WRAP, 1: unreal.TextureAddress.TA_CLAMP,
            2: unreal.TextureAddress.TA_MIRROR, 3: unreal.TextureAddress.TA_CLAMP}
    asset.set_editor_property("address_x", wrap.get(settings.get("wrapU", 0), unreal.TextureAddress.TA_WRAP))
    asset.set_editor_property("address_y", wrap.get(settings.get("wrapV", 0), unreal.TextureAddress.TA_WRAP))

def _owned_output_paths(unreal, plan, primary_paths):
    prefix = plan["folder"] + "/" + plan["name"]
    related = unreal.EditorAssetLibrary.list_assets(plan["folder"], recursive=False, include_folder=False)
    return sorted(set(primary_paths) | {
        p for p in related if p.split(".", 1)[0] == prefix or p.split(".", 1)[0].startswith(prefix + "_")
    })

def _save_and_describe(unreal, paths, settings=None):
    objects = []
    for object_path in paths:
        asset = unreal.EditorAssetLibrary.load_asset(object_path)
        if asset is None:
            raise RuntimeError("无法读取导入结果：" + object_path)
        if settings:
            _texture_settings(unreal, asset, settings)
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
            raise RuntimeError("保存资源失败：" + object_path)
        objects.append({"path": object_path, "name": asset.get_name(), "type": asset.get_class().get_name()})
    return objects

def import_manifest(filename, destination="/Game/UnityImports", replace=False):
    import unreal
    data, ue_root, plans = plan_manifest(filename, destination)
    report_id = hashlib.sha256(ue_root.encode()).hexdigest()[:16]
    saved = Path(unreal.SystemLibrary.get_project_saved_directory()) / "UnityResourceBridge"
    report_file = saved / (report_id + ".json")
    old = {}
    if report_file.exists():
        old = json.loads(report_file.read_text(encoding="utf-8")).get("guidToUnreal", {})
    report = {"schemaVersion": 1, "sourceManifest": str(Path(filename).resolve()),
              "ueRoot": ue_root, "guidToUnreal": {}, "assets": [],
              "materials": data.get("materials", []), "rendererBindings": data.get("rendererBindings", []),
              "missingDependencies": data.get("missing", []), "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S")}
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    errors = []
    with unreal.ScopedSlowTask(len(plans), "导入 Unity 引用资源") as slow:
        slow.make_dialog(True)
        for plan in plans:
            if slow.should_cancel():
                report["cancelled"] = True
                break
            record = plan["record"]
            guid = record["guid"]
            slow.enter_progress_frame(1, record["path"])
            row = {"guid": guid, "unityPath": record["path"], "status": "skipped",
                   "reason": plan["reason"], "unrealPaths": []}
            report["assets"].append(row)
            if plan["reason"]:
                continue
            fingerprint = hashlib.sha256(Path(plan["source"]).read_bytes() +
                json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()
            previous = old.get(guid, {})
            existing = previous.get("unrealPaths", [])
            occupied = plan["folder"] + "/" + plan["name"]
            has_previous = bool(existing) and all(unreal.EditorAssetLibrary.does_asset_exist(p) for p in existing)
            if not replace and (has_previous or unreal.EditorAssetLibrary.does_asset_exist(occupied)):
                if not has_previous:
                    row.update(status="conflict", reason="目标资源已存在且没有本工具的导入记录")
                    errors.append(row)
                    continue
                existing = _owned_output_paths(unreal, plan, existing)
                previous["unrealPaths"] = existing
                previous["objects"] = _save_and_describe(unreal, existing)
                row.update(status="unchanged" if previous.get("sha256") == fingerprint else "exists_changed",
                           reason="" if previous.get("sha256") == fingerprint else "源文件有变更；默认保留已导入资源。可显式更新。",
                           unrealPaths=existing)
                report["guidToUnreal"][guid] = previous
                continue
            try:
                task = unreal.AssetImportTask()
                task.set_editor_property("filename", plan["source"])
                task.set_editor_property("destination_path", plan["folder"])
                task.set_editor_property("destination_name", plan["name"])
                task.set_editor_property("automated", True)
                task.set_editor_property("replace_existing", replace)
                task.set_editor_property("replace_existing_settings", replace)
                task.set_editor_property("save", False)
                if plan["extension"] in MODELS:
                    task.set_editor_property("factory", unreal.FbxFactory())
                    task.set_editor_property("options", _fbx_options(unreal, record))
                tools.import_asset_tasks([task])
                paths = list(task.get_editor_property("imported_object_paths"))
                if not paths:
                    raise RuntimeError("UE 没有生成资源，请查看 Output Log 中该文件的导入错误。")
                paths = _owned_output_paths(unreal, plan, paths)
                objects = _save_and_describe(unreal, paths, record.get("texture"))
                mapping = {"unityPath": record["path"], "sha256": fingerprint,
                           "unrealPaths": paths, "objects": objects, "subAssets": record.get("subAssets", [])}
                report["guidToUnreal"][guid] = mapping
                row.update(status="imported", reason="", unrealPaths=paths)
            except Exception as error:
                row.update(status="failed", reason=str(error))
                errors.append(row)
                unreal.log_error("UnityBridge: " + record["path"] + ": " + str(error))
            # Persist progress, including when a later import fails or the user cancels.
            write_json(report_file, report)
    for material in report["materials"]:
        for texture in material.get("textures", []):
            texture["unrealPaths"] = report["guidToUnreal"].get(texture.get("guid"), {}).get("unrealPaths", [])
    counts = {}
    for row in report["assets"]:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    report["counts"] = counts
    asset_types = {}
    for mapping in report["guidToUnreal"].values():
        for obj in mapping.get("objects", []):
            asset_types[obj["type"]] = asset_types.get(obj["type"], 0) + 1
    report["unrealAssetTypes"] = asset_types
    report["unrealAssetCount"] = sum(asset_types.values())
    report["reportFile"] = str(report_file)
    write_json(report_file, report)
    write_json(Path(filename).parent / "ue_import_report.json", report)
    summary = {"目录": ue_root, "结果": counts, "报告": str(report_file)}
    print(json.dumps(summary, ensure_ascii=False))
    unreal.log("UnityBridge: " + json.dumps(summary, ensure_ascii=False))
    if report.get("cancelled"):
        raise RuntimeError("用户取消了导入；已保存完成部分和导入报告。")
    if errors:
        raise RuntimeError(str(len(errors)) + " 个资源未导入成功，详见报告。")
    if report["missingDependencies"]:
        raise RuntimeError("Unity 导出时存在缺失依赖，详见报告。")
    return report

def choose_and_import():
    import unreal
    import tkinter
    from tkinter import filedialog, messagebox
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        filename = filedialog.askopenfilename(title="选择 Unity 导出的资源清单",
            filetypes=[("Unity 资源清单", "unity_manifest.json"), ("JSON", "*.json")], parent=root)
        if not filename:
            return
        report = import_manifest(filename)
        messagebox.showinfo("Unity → UE", "资源导入完成\n" + report["ueRoot"] +
                            "\n" + json.dumps(report["counts"], ensure_ascii=False) +
                            "\n报告：" + report["reportFile"], parent=root)
    except Exception as error:
        unreal.log_error(str(error))
        messagebox.showerror("Unity → UE", str(error), parent=root)
    finally:
        root.destroy()

def register_menu():
    import unreal
    menus = unreal.ToolMenus.get()
    main = menus.find_menu("LevelEditor.MainMenu")
    if not main:
        return False
    submenu = main.add_sub_menu("UnityResourceBridge", "UnityResourceBridge",
        "UnityResourceBridge", "Unity → UE", "导入 Unity 引用资源")
    entry = unreal.ToolMenuEntry(name="UnityResourceBridge.Import",
        type=unreal.MultiBlockType.MENU_ENTRY)
    entry.set_label("导入 Unity 资源…")
    entry.set_tool_tip("选择由 Unity 导出的 unity_manifest.json")
    entry.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, "",
        "import unity_bridge; unity_bridge.choose_and_import()")
    submenu.add_menu_entry("Import", entry)
    menus.refresh_all_widgets()
    return True

