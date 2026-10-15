import sys
sys.argv = ["x", "run", "0", "99"]
sys.path.insert(0, r"G:/UE_Project/P_VFX/Tools/VFXMaster/_dev")
import tests
keep = sys.stdin.read().split()
tests.T[:] = [t for t in tests.T if t[0] in keep]
exec(open(r"G:/UE_Project/P_VFX/Tools/VFXMaster/_dev/rt_suite.py", encoding="utf-8").read())
