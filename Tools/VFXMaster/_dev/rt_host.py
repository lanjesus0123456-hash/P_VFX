# 宿主端：通过 Remote Execution 分步驱动 rt_lib，期间等待着色器编译。单次运行控制在 ~100 秒内。
import sys, time, json
sys.path.insert(0, r"F:/EPIC/UE_Engine/UE_5.8/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python")
import remote_execution as R

PRE = ("import sys, importlib\np=r'G:/UE_Project/P_VFX/Tools/VFXMaster/_dev'\n"
       "sys.path.insert(0,p) if p not in sys.path else None\nimport rt_lib as T\n")

class UE:
    def __init__(self):
        self.r = R.RemoteExecution(); self.r.start()
        for _ in range(50):
            if self.r.remote_nodes: break
            time.sleep(0.1)
        self.r.open_command_connection(self.r.remote_nodes[0]["node_id"])
    def run(self, code):
        res = self.r.run_command(PRE + code, unattended=True, exec_mode=R.MODE_EXEC_FILE)
        out = "\n".join(o.get("output", "") for o in res.get("output", []))
        if not res.get("success"):
            raise RuntimeError(res.get("result", "") + out)
        return out
    def val(self, expr):
        out = self.run("import json\nprint('@@'+json.dumps(%s))" % expr)
        return json.loads(out.split("@@")[-1].strip().splitlines()[0])
    def close(self): self.r.stop()

def mean(px): return sum(sum(p) for p in px) / (3.0 * len(px))
def diff(a, b): return sum(abs(x - y) for p, q in zip(a, b) for x, y in zip(p, q)) / (3.0 * len(a))

if __name__ == "__main__":
    steps = json.load(open(sys.argv[1], encoding="utf-8"))
    ue = UE()
    try:
        if steps.get("setup"):
            ue.run("importlib.reload(T)\nT.setup(%r)" % steps.get("mesh", "/Engine/BasicShapes/Plane"))
            time.sleep(3)
        bg = ue.val("T.capture(False)")
        base = None
        for st in steps["cases"]:
            ue.run("T.set_params(scalars=%r, switches=%r, vectors=%r)" % (st.get("s", {}), st.get("sw", {}), st.get("v", {})))
            time.sleep(st.get("wait", 2))
            px = ue.val("T.capture(True)")
            if base is None: base = px
            print("%-30s 亮度=%6.1f  与背景差=%6.2f  与基准差=%6.2f" % (st["name"], mean(px), diff(px, bg), diff(px, base)))
    finally:
        ue.close()
