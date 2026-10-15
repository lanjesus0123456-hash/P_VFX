# 通过 UE Python Remote Execution 在已打开的编辑器里执行脚本文件
# 用法: python -I ue_run.py 脚本.py
import sys, time, json
sys.path.insert(0, r"F:/EPIC/UE_Engine/UE_5.8/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python")
import remote_execution as re_

code = open(sys.argv[1], encoding="utf-8").read()
r = re_.RemoteExecution()
r.start()
try:
    for _ in range(50):
        if r.remote_nodes:
            break
        time.sleep(0.1)
    if not r.remote_nodes:
        print("没找到 UE 编辑器节点（检查 Python 插件的 Enable Remote Execution）")
        sys.exit(2)
    node = r.remote_nodes[0]
    r.open_command_connection(node["node_id"])
    res = r.run_command(code, unattended=True, exec_mode=re_.MODE_EXEC_FILE)
    for o in res.get("output", []):
        print(o.get("output", "").rstrip())
    print("== success:", res.get("success"), res.get("result", "") if not res.get("success") else "")
finally:
    r.stop()
