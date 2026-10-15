# Houdini 独立校验
# 1) 原 FBX：按连通块求几何中心 C_geo，和工具约定 P + Cd*N 对比（验证数据约定）
# 2) 转换后 FBX：读 UV2/UV3 还原 pivot，与同一块的几何中心对比（验证转换）
import hou, sys
src, dst = sys.argv[1], sys.argv[2]
obj = hou.node("/obj")

def piece_check(path, name, snippet):
    g = obj.createNode("geo", name)
    f = g.createNode("file"); f.parm("file").set(path)
    w = g.createNode("attribwrangle"); w.setInput(0, f)
    w.parm("class").set(3)  # vertex
    w.parm("snippet").set(snippet)
    c = g.createNode("connectivity"); c.setInput(0, w); c.parm("connecttype").set(1)
    geo = c.geometry()
    pts = {}
    for pr in geo.prims():
        cls = pr.attribValue("class")
        for v in pr.vertices():
            pts.setdefault(cls, {"P": [], "piv": []})
            pts[cls]["P"].append(v.point().position())
            pts[cls]["piv"].append(hou.Vector3(v.attribValue("piv")))
    errs, spread = [], []
    for cls, d in pts.items():
        # 几何中心：去重后的点平均（立方体角点对称）
        uniq = {tuple(round(x, 6) for x in p): p for p in d["P"]}
        cg = sum(uniq.values(), hou.Vector3()) / len(uniq)
        pv = sum(d["piv"], hou.Vector3()) / len(d["piv"])
        errs.append((cg - pv).length())
        spread.append(max((p - pv).length() for p in d["piv"]))
    bb = geo.boundingBox()
    print("[%s] 碎块=%d 包围盒尺寸=%s" % (name, len(pts), tuple(round(x, 4) for x in bb.sizevec())))
    print("   pivot 与几何中心最大误差=%.6g  块内 pivot 最大离散=%.6g" % (max(errs), max(spread)))
    return geo

piece_check(src, "src", 'v@piv = v@P + f@Cd * v@N;')
# 转换后：Houdini 把 FBX 第 2/3/4 套 UV 读成 uv3/uv4/...，先列属性名
g = obj.createNode("geo", "probe"); f = g.createNode("file"); f.parm("file").set(dst)
print("转换后顶点属性:", [a.name() for a in f.geometry().vertexAttribs()])
