import unreal
mf = unreal.load_asset("/Game/归玥材质包LTS/07_MF/Guiyue_MF_Refine")
t = unreal.AssetExportTask()
t.object = mf
t.filename = r"G:/UE_Project/P_VFX/Tools/ChunkFlip/_dev/refine.t3d"
t.automated = True; t.prompt = False; t.replace_identical = True
t.exporter = unreal.ObjectExporterT3D()
print(unreal.Exporter.run_asset_export_task(t))
