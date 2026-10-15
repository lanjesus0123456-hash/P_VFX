import sys, importlib, traceback
sys.dont_write_bytecode = True
p = r"G:/UE_Project/P_VFX/Tools/ChunkFlip"
if p not in sys.path: sys.path.insert(0, p)
import chunkflip_to_ue, ue_chunkflip_pipeline as P
importlib.reload(chunkflip_to_ue); importlib.reload(P)
try:
    P.run()
except Exception:
    traceback.print_exc()
print("\n".join(P._log_lines))
