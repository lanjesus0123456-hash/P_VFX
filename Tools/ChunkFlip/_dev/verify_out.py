# 读转换后 FBX 原始数据：每块的 UV2/UV3 pivot 与该块顶点的几何中心对比；法线朝外检查
import sys, math
sys.path.insert(0, sys.argv[1]); sys.dont_write_bytecode = True
import chunkflip_to_ue as C
root = C.parse_fbx_ascii(open(sys.argv[2], encoding="utf-8").read())
g = root.find("Objects").find("Geometry")
V = g.array("Vertices"); cps = [tuple(V[i:i+3]) for i in range(0, len(V), 3)]
pvi = g.array("PolygonVertexIndex")
uv = {e.props[0]: e.array("UV") for e in g.find_all("LayerElementUV")}
Nn = g.find("LayerElementNormal").array("Normals")
polys, cur = [], []
for k, v in enumerate(pvi):
    cur.append((k, ~v if v < 0 else v))
    if v < 0: polys.append(cur); cur = []
chunks = {}
for poly in polys:
    k0 = poly[0][0]
    piv = (uv[2][2*k0], -uv[2][2*k0+1], uv[3][2*k0])
    key = tuple(round(x, 3) for x in piv)
    chunks.setdefault(key, {"piv": piv, "cp": set(), "polys": []})
    chunks[key]["cp"].update(c for _, c in poly); chunks[key]["polys"].append(poly)
err, bad_n = 0.0, 0
for d in chunks.values():
    cg = [sum(cps[c][i] for c in d["cp"]) / len(d["cp"]) for i in range(3)]
    err = max(err, max(abs(cg[i] - d["piv"][i]) for i in range(3)))
    for poly in d["polys"]:
        k, c = poly[0]
        fc = [sum(cps[cc][i] for _, cc in poly) / len(poly) for i in range(3)]
        if sum(Nn[3*k+i] * (fc[i] - d["piv"][i]) for i in range(3)) <= 0: bad_n += 1
rnd = [uv[3][i] for i in range(1, len(uv[3]), 2)]
print("碎块=%d  pivot 与几何中心最大误差=%.5f cm  法线朝内的面=%d/%d  随机值范围 %.3f~%.3f"
      % (len(chunks), err, bad_n, len(polys), min(rnd), max(rnd)))
print("生长值 UV1.u 范围 %.3f~%.3f" % (min(uv[1][0::2]), max(uv[1][0::2])))
