import sys, importlib, traceback
sys.dont_write_bytecode = True
p = r"G:/UE_Project/P_VFX/Tools/VFXMaster"
if p not in sys.path: sys.path.insert(0, p)
for name in ("vfx_graph", "vfx_hlsl", "build_vfx_master"):
    sys.modules.pop(name, None)
try:
    import build_vfx_master as B
    m = B.build()
    print("材质:", m.get_path_name())
    try:
        B.make_presets(m); print("预设实例 OK")
    except Exception:
        traceback.print_exc()
except Exception:
    traceback.print_exc()
