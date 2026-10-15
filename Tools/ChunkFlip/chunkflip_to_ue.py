# -*- coding: utf-8 -*-
"""
碎块翻转生长工具 -> UE 转换脚本

把「自定义碎块翻转生长动画工具」导出的静态 ASCII FBX 转成 UE 能正确读取的 FBX。

工具原始数据（Unity 约定）：
    UV2.U   = 生长扫描值 (0~1)
    UV2.V   = 绕中心点的角度 (0~1)
    法线 N  = 顶点指向自己碎块中心的单位向量（不是表面法线）
    顶点色R = 顶点到碎块中心的距离（原始数值，未归一化）
    => 碎块中心 pivot = P + Cd * N

UE 导入后会把顶点色截断到 8bit 0~1、重算法线，所以这里改成：
    UV0     = 原始 UV
    UV1     = 生长值 (U=生长扫描值, V=角度)
    UV2     = pivot.x, pivot.y   （UE 本地空间，厘米；V 按 UE 导入时的 1-V 翻转预先补偿）
    UV3     = pivot.z, 每块随机值 (0~1)
    法线    = 真实几何面法线（平直着色）
    坐标系  = Z-up / 厘米，导入时 UE 只做 Y 轴镜像

用法：
    UE 自带 Python 直接跑：
        python.exe -I chunkflip_to_ue.py 输入.fbx [输出.fbx]
    或在 UE 编辑器里用 import_chunkflip.py 一键转换并导入。
"""
import math
import os
import random
import re
import sys

__all__ = ["convert_file", "convert_text"]

# ----------------------------------------------------------------------------
# ASCII FBX 解析
# ----------------------------------------------------------------------------
_TOKEN_RE = re.compile(
    r'"[^"]*"'                                      # 字符串
    r'|;[^\n]*'                                     # 注释
    r'|[A-Za-z_][\w|]*:'                            # 节点名
    r'|\*\d+'                                       # 数组长度标记
    r'|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'   # 数字
    r'|[{},]'
    r'|[A-Za-z_]\w*'                                # 裸字（如 Shading: T）
)


class Node(object):
    __slots__ = ("name", "props", "children")

    def __init__(self, name, props, children):
        self.name, self.props, self.children = name, props, children

    def find(self, name):
        for c in self.children:
            if c.name == name:
                return c
        return None

    def find_all(self, name):
        return [c for c in self.children if c.name == name]

    def array(self, name):
        """读取 `Name: *N { a: ... }` 形式的数组。"""
        n = self.find(name)
        if n is None:
            return None
        a = n.find("a")
        return list(a.props) if a is not None else list(n.props)


def _conv(tok):
    if tok[0] == '"':
        return tok[1:-1]
    try:
        return int(tok)
    except ValueError:
        try:
            return float(tok)
        except ValueError:
            return tok


def parse_fbx_ascii(text):
    toks = [t for t in _TOKEN_RE.findall(text) if t[0] != ";"]
    pos = [0]
    n = len(toks)

    def parse_children():
        kids = []
        while pos[0] < n:
            t = toks[pos[0]]
            if t == "}":
                pos[0] += 1
                return kids
            if t.endswith(":") and t[0] != '"':
                kids.append(parse_node())
            else:
                pos[0] += 1  # 容错：跳过游离 token
        return kids

    def parse_node():
        name = toks[pos[0]][:-1]
        pos[0] += 1
        props, children = [], []
        while pos[0] < n:
            t = toks[pos[0]]
            if t == ",":
                pos[0] += 1
            elif t == "{":
                pos[0] += 1
                children = parse_children()
                break
            elif t == "}" or (t.endswith(":") and t[0] != '"'):
                break
            else:
                props.append(t if t[0] == "*" else _conv(t))
                pos[0] += 1
        return Node(name, props, children)

    root = []
    while pos[0] < n:
        if toks[pos[0]].endswith(":"):
            root.append(parse_node())
        else:
            pos[0] += 1
    return Node("root", [], root)


def _props70(node):
    """Properties70 -> {名字: [值...]}"""
    out = {}
    p70 = node.find("Properties70") if node is not None else None
    if p70 is None:
        return out
    for p in p70.find_all("P"):
        if p.props:
            out[p.props[0]] = p.props[4:]
    return out


def _layer(geom, elem_name, data_name, index_name, comps, layer_idx, poly_vi, poly_sizes):
    """把一个 LayerElement 展开成「每个多边形顶点(角)一份」的列表。"""
    elem = None
    for e in geom.find_all(elem_name):
        if (e.props[0] if e.props else 0) == layer_idx:
            elem = e
            break
    if elem is None:
        return None
    mapping = (elem.find("MappingInformationType").props[0]
               if elem.find("MappingInformationType") else "ByPolygonVertex")
    ref = (elem.find("ReferenceInformationType").props[0]
           if elem.find("ReferenceInformationType") else "Direct")
    raw = elem.array(data_name) or []
    vals = [tuple(raw[i:i + comps]) for i in range(0, len(raw) - comps + 1, comps)]
    idx = elem.array(index_name) if ref in ("IndexToDirect", "Index") else None

    def pick(k):
        return vals[idx[k] if idx is not None else k]

    out = []
    if mapping == "ByPolygonVertex":
        out = [pick(k) for k in range(len(poly_vi))]
    elif mapping in ("ByVertice", "ByVertex", "ByControlPoint"):
        out = [pick(v) for v in poly_vi]
    elif mapping == "ByPolygon":
        for p, sz in enumerate(poly_sizes):
            out.extend([pick(p)] * sz)
    elif mapping == "AllSame":
        out = [pick(0)] * len(poly_vi)
    else:
        raise ValueError("不支持的 MappingInformationType: %s" % mapping)
    return out


# ----------------------------------------------------------------------------
# 小型矩阵工具（行主序 4x4，列向量约定）
# ----------------------------------------------------------------------------
def _mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _mat_t(x, y, z):
    return [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]


def _mat_s(x, y, z):
    return [[x, 0, 0, 0], [0, y, 0, 0], [0, 0, z, 0], [0, 0, 0, 1]]


def _mat_r_xyz(rx, ry, rz):
    """FBX 默认 eEulerXYZ：先绕 X，再 Y，再 Z => R = Rz * Ry * Rx"""
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    cy, sy = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    mx = [[1, 0, 0, 0], [0, cx, -sx, 0], [0, sx, cx, 0], [0, 0, 0, 1]]
    my = [[cy, 0, sy, 0], [0, 1, 0, 0], [-sy, 0, cy, 0], [0, 0, 0, 1]]
    mz = [[cz, -sz, 0, 0], [sz, cz, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    return _mat_mul(mz, _mat_mul(my, mx))


def _xform_p(m, p):
    return tuple(m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3))


def _det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _vec3(props, default):
    vals = [float(v) for v in props[-3:]] if props and len(props) >= 3 else None
    return tuple(vals) if vals else default


def _model_local_matrix(model, warnings):
    """Lcl T/R/S + PreRotation（不支持 Rotation/Scaling Pivot，遇到会提示）。"""
    p = _props70(model)
    t = _vec3(p.get("Lcl Translation"), (0.0, 0.0, 0.0))
    r = _vec3(p.get("Lcl Rotation"), (0.0, 0.0, 0.0))
    s = _vec3(p.get("Lcl Scaling"), (1.0, 1.0, 1.0))
    pre = _vec3(p.get("PreRotation"), (0.0, 0.0, 0.0))
    for k in ("RotationPivot", "ScalingPivot", "RotationOffset", "ScalingOffset", "PostRotation"):
        if any(abs(v) > 1e-6 for v in _vec3(p.get(k), (0.0, 0.0, 0.0))):
            warnings.append("模型 %s 带 %s，转换脚本未处理，结果可能偏移" % (model.props[1], k))
    if int((p.get("RotationOrder") or [0])[-1]) != 0:
        warnings.append("模型 %s 的旋转顺序不是 XYZ，按 XYZ 处理" % model.props[1])
    m = _mat_t(*t)
    m = _mat_mul(m, _mat_r_xyz(*pre))
    m = _mat_mul(m, _mat_r_xyz(*r))
    return _mat_mul(m, _mat_s(*s))


def _geometric_matrix(model):
    p = _props70(model)
    m = _mat_t(*_vec3(p.get("GeometricTranslation"), (0.0, 0.0, 0.0)))
    m = _mat_mul(m, _mat_r_xyz(*_vec3(p.get("GeometricRotation"), (0.0, 0.0, 0.0))))
    return _mat_mul(m, _mat_s(*_vec3(p.get("GeometricScaling"), (1.0, 1.0, 1.0))))


def _axis_matrix(gs):
    """源坐标系 -> 规范坐标系（右手、Z-up、-Y 朝前、X 朝右、厘米）。"""
    p = _props70(gs)

    def gi(name, default):
        v = p.get(name)
        return int(v[-1]) if v else default

    def axis(idx, sign):
        e = [0.0, 0.0, 0.0]
        e[idx] = float(sign)
        return e

    up = axis(gi("UpAxis", 1), gi("UpAxisSign", 1))
    front = axis(gi("FrontAxis", 2), gi("FrontAxisSign", 1))
    right = axis(gi("CoordAxis", 0), gi("CoordAxisSign", 1))
    usf = float((p.get("UnitScaleFactor") or [1.0])[-1])
    # 规范空间分量：x = p·right, y = -(p·front), z = p·up
    rows = [right, [-v for v in front], up]
    m = [[rows[i][j] * usf for j in range(3)] + [0.0] for i in range(3)]
    m.append([0.0, 0.0, 0.0, 1.0])
    return m, usf


# ----------------------------------------------------------------------------
# 读取工具导出的 FBX
# ----------------------------------------------------------------------------
def read_chunkflip_fbx(text):
    """返回规范空间(Z-up 厘米)下按「角」展开的网格数据。"""
    root = parse_fbx_ascii(text)
    if root.find("FBXHeaderExtension") is None and "Kaydara FBX Binary" in text[:64]:
        raise ValueError("这是二进制 FBX，请在工具里导出 ASCII FBX")
    objects = root.find("Objects")
    if objects is None:
        raise ValueError("FBX 里没有 Objects 节点，不是有效的 ASCII FBX")
    axis_m, usf = _axis_matrix(root.find("GlobalSettings"))
    warnings = []

    geoms = {g.props[0]: g for g in objects.find_all("Geometry")}
    models = {m.props[0]: m for m in objects.find_all("Model")}
    geo_to_model, parent = {}, {}
    conns = root.find("Connections")
    for c in (conns.find_all("C") if conns else []):
        if c.props[0] != "OO":
            continue
        src, dst = c.props[1], c.props[2]
        if src in geoms and dst in models:
            geo_to_model[src] = dst
        elif src in models:
            parent[src] = dst

    def world(mid):
        m = _model_local_matrix(models[mid], warnings)
        p = parent.get(mid)
        while p in models:
            m = _mat_mul(_model_local_matrix(models[p], warnings), m)
            p = parent.get(p)
        return m

    pos, uv0, uv1, cd, nrm, corner_poly = [], [], [], [], [], []
    polys = []          # 每个多边形的角索引列表
    poly_geo = []       # 每个多边形所属 geometry 序号
    for gi_, (gid, g) in enumerate(geoms.items()):
        if g.props[-1] != "Mesh":
            continue
        verts = g.array("Vertices") or []
        pvi = g.array("PolygonVertexIndex") or []
        cps = [tuple(verts[i:i + 3]) for i in range(0, len(verts), 3)]
        mid = geo_to_model.get(gid)
        m = axis_m
        if mid is not None:
            m = _mat_mul(axis_m, _mat_mul(world(mid), _geometric_matrix(models[mid])))
        lin = [r[:3] for r in m[:3]]
        if _det3(m) < 0:
            warnings.append("Geometry %s 带镜像变换，已自动翻转面朝向" % gid)

        # 多边形拆分（负数 = 多边形结尾，真实索引 = ~i）
        poly_vi, sizes, cur = [], [], 0
        for v in pvi:
            if v < 0:
                poly_vi.append(~v)
                sizes.append(cur + 1)
                cur = 0
            else:
                poly_vi.append(v)
                cur += 1

        uv_a = _layer(g, "LayerElementUV", "UV", "UVIndex", 2, 0, poly_vi, sizes)
        uv_b = _layer(g, "LayerElementUV", "UV", "UVIndex", 2, 1, poly_vi, sizes)
        nn = _layer(g, "LayerElementNormal", "Normals", "NormalsIndex", 3, 0, poly_vi, sizes)
        col = _layer(g, "LayerElementColor", "Colors", "ColorIndex", 4, 0, poly_vi, sizes)
        if uv_b is None:
            raise ValueError("缺少第二套 UV（生长值），确认导出的是工具的「静态模型」而不是骨骼动画")
        if nn is None or col is None:
            raise ValueError("缺少法线或顶点色，无法还原碎块中心")

        base = len(pos)
        for k, v in enumerate(poly_vi):
            pos.append(_xform_p(m, cps[v]))
            # 方向向量走线性部分（不归一化，距离 Cd 一起乘上缩放）
            d = nn[k]
            nrm.append(tuple(lin[i][0] * d[0] + lin[i][1] * d[1] + lin[i][2] * d[2] for i in range(3)))
            cd.append(float(col[k][0]))
            uv0.append(uv_a[k] if uv_a else (0.0, 0.0))
            uv1.append(uv_b[k])
        k = base
        flip = _det3(m) < 0
        for sz in sizes:
            ids = list(range(k, k + sz))
            polys.append(ids[::-1] if flip else ids)
            poly_geo.append(gi_)
            k += sz

    if not polys:
        raise ValueError("FBX 里没有找到网格")
    return {"pos": pos, "uv0": uv0, "uv1": uv1, "cd": cd, "dir": nrm,
            "polys": polys, "usf": usf, "warnings": warnings}


# ----------------------------------------------------------------------------
# 计算 pivot / 分块 / 面法线
# ----------------------------------------------------------------------------
def build_ue_mesh(src, seed=7):
    pos, cd, dr, polys = src["pos"], src["cd"], src["dir"], src["polys"]
    # 每个角的 pivot = P + Cd * N（方向已带缩放，所以单位一致）
    piv = [(p[0] + c * d[0], p[1] + c * d[1], p[2] + c * d[2]) for p, c, d in zip(pos, cd, dr)]

    # 按多边形取平均 pivot，再按量化坐标合并成碎块
    scale = max(1e-6, max(max(abs(v) for v in p) for p in pos))
    q = scale * 1e-4                      # 量化精度：模型尺寸的万分之一
    chunk_of_key, chunk_piv, chunk_cnt = {}, [], []
    poly_chunk = []
    spread = 0.0
    for ids in polys:
        cx = sum(piv[i][0] for i in ids) / len(ids)
        cy = sum(piv[i][1] for i in ids) / len(ids)
        cz = sum(piv[i][2] for i in ids) / len(ids)
        for i in ids:
            spread = max(spread, abs(piv[i][0] - cx), abs(piv[i][1] - cy), abs(piv[i][2] - cz))
        key = (round(cx / q), round(cy / q), round(cz / q))
        c = chunk_of_key.get(key)
        if c is None:
            # 量化边界附近：查邻格
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        c = chunk_of_key.get((key[0] + dx, key[1] + dy, key[2] + dz))
                        if c is not None:
                            break
                    if c is not None:
                        break
                if c is not None:
                    break
        if c is None:
            c = len(chunk_piv)
            chunk_of_key[key] = c
            chunk_piv.append([0.0, 0.0, 0.0])
            chunk_cnt.append(0)
        chunk_piv[c][0] += cx
        chunk_piv[c][1] += cy
        chunk_piv[c][2] += cz
        chunk_cnt[c] += 1
        poly_chunk.append(c)
    chunk_piv = [tuple(v / n for v in p) for p, n in zip(chunk_piv, chunk_cnt)]

    warnings = list(src["warnings"])
    if spread > scale * 1e-3:
        warnings.append("同一个面上的 pivot 不一致(最大偏差 %.4g)，顶点色可能被截断或不是工具原始导出" % spread)

    rng = random.Random(seed)
    chunk_rand = [rng.random() for _ in chunk_piv]

    # 面法线（Newell 法，兼容四边形/多边形）
    face_n = []
    for ids in polys:
        nx = ny = nz = 0.0
        for a, b in zip(ids, ids[1:] + ids[:1]):
            pa, pb = pos[a], pos[b]
            nx += (pa[1] - pb[1]) * (pa[2] + pb[2])
            ny += (pa[2] - pb[2]) * (pa[0] + pb[0])
            nz += (pa[0] - pb[0]) * (pa[1] + pb[1])
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        face_n.append((nx / ln, ny / ln, nz / ln))

    return {"pos": pos, "uv0": src["uv0"], "uv1": src["uv1"], "polys": polys,
            "face_n": face_n, "poly_chunk": poly_chunk, "chunk_piv": chunk_piv,
            "chunk_rand": chunk_rand, "warnings": warnings}


# ----------------------------------------------------------------------------
# 写出 UE 用的 ASCII FBX（Z-up / -Y 前 / 厘米）
# ----------------------------------------------------------------------------
def _fmt(vals):
    return ",".join("%.7g" % v for v in vals)


def write_ue_fbx(mesh, name="ChunkFlip"):
    """UE 导入 FBX 时把 Y 取反（右手 -> 左手），pivot 存进 UV 时提前取反保持一致。"""
    pos, polys = mesh["pos"], mesh["polys"]
    # 位置去重：同一位置共用 control point，避免 UE 当成断开的面（法线另外写）
    cp_index, cps, pvi = {}, [], []
    for ids in polys:
        for j, i in enumerate(ids):
            key = tuple(round(v, 5) for v in pos[i])
            c = cp_index.get(key)
            if c is None:
                c = len(cps)
                cp_index[key] = c
                cps.append(pos[i])
            pvi.append(~c if j == len(ids) - 1 else c)

    normals, uvs = [], [[], [], [], []]
    for p, ids in enumerate(polys):
        piv = mesh["chunk_piv"][mesh["poly_chunk"][p]]
        rnd = mesh["chunk_rand"][mesh["poly_chunk"][p]]
        for i in ids:
            normals.extend(mesh["face_n"][p])
            uvs[0].extend(mesh["uv0"][i])
            uvs[1].extend(mesh["uv1"][i])
            # UE 导入时：位置 Y 取反（右手->左手），UV 的 V 变成 1-V。
            # 所以 V 里存 1+y，导入后 1-(1+y) = -y，正好等于 UE 里的顶点 Y。
            uvs[2].extend((piv[0], 1.0 + piv[1]))  # UE 本地 X, Y
            uvs[3].extend((piv[2], 1.0 - rnd))     # UE 本地 Z, 每块随机值（导入后还原为 rnd）
    uv_names = ["UV0_Base", "UV1_Growth", "UV2_PivotXY", "UV3_PivotZ_Rand"]

    flat_cp = [v for p in cps for v in p]
    out = []
    w = out.append
    w("; FBX 7.4.0 project file\n; Generated by chunkflip_to_ue.py\n\n")
    w("FBXHeaderExtension:  {\n    FBXHeaderVersion: 1003\n    FBXVersion: 7400\n}\n")
    w("GlobalSettings:  {\n    Version: 1000\n    Properties70:  {\n")
    for k, v in (("UpAxis", 2), ("UpAxisSign", 1), ("FrontAxis", 1), ("FrontAxisSign", -1),
                 ("CoordAxis", 0), ("CoordAxisSign", 1), ("OriginalUpAxis", 2), ("OriginalUpAxisSign", 1)):
        w('        P: "%s", "int", "Integer", "",%d\n' % (k, v))
    w('        P: "UnitScaleFactor", "double", "Number", "",1\n')
    w('        P: "OriginalUnitScaleFactor", "double", "Number", "",1\n')
    w("    }\n}\n\n")
    w("Definitions:  {\n    Version: 100\n    Count: 3\n")
    for t, c in (("Model", 1), ("Geometry", 1), ("Material", 1)):
        w('    ObjectType: "%s" {\n        Count: %d\n    }\n' % (t, c))
    w("}\n\nObjects:  {\n")
    w('    Geometry: 1000, "Geometry::%s", "Mesh" {\n' % name)
    w("        Vertices: *%d {\n            a: %s\n        }\n" % (len(flat_cp), _fmt(flat_cp)))
    w("        PolygonVertexIndex: *%d {\n            a: %s\n        }\n" % (len(pvi), ",".join(map(str, pvi))))
    w("        GeometryVersion: 124\n")
    w('        LayerElementNormal: 0 {\n            Version: 101\n            Name: ""\n'
      '            MappingInformationType: "ByPolygonVertex"\n            ReferenceInformationType: "Direct"\n'
      "            Normals: *%d {\n                a: %s\n            }\n        }\n" % (len(normals), _fmt(normals)))
    for li, (nm, data) in enumerate(zip(uv_names, uvs)):
        w('        LayerElementUV: %d {\n            Version: 101\n            Name: "%s"\n'
          '            MappingInformationType: "ByPolygonVertex"\n            ReferenceInformationType: "Direct"\n'
          "            UV: *%d {\n                a: %s\n            }\n        }\n" % (li, nm, len(data), _fmt(data)))
    w('        LayerElementMaterial: 0 {\n            Version: 101\n            Name: ""\n'
      '            MappingInformationType: "AllSame"\n            ReferenceInformationType: "IndexToDirect"\n'
      "            Materials: *1 {\n                a: 0\n            }\n        }\n")
    for li in range(4):
        w("        Layer: %d {\n            Version: 100\n" % li)
        if li == 0:
            w('            LayerElement:  {\n                Type: "LayerElementNormal"\n                TypedIndex: 0\n            }\n')
            w('            LayerElement:  {\n                Type: "LayerElementMaterial"\n                TypedIndex: 0\n            }\n')
        w('            LayerElement:  {\n                Type: "LayerElementUV"\n                TypedIndex: %d\n            }\n' % li)
        w("        }\n")
    w("    }\n")
    w('    Model: 2000, "Model::%s", "Mesh" {\n        Version: 232\n        Properties70:  {\n'
      '            P: "DefaultAttributeIndex", "int", "Integer", "",0\n        }\n        Shading: T\n        Culling: "CullingOff"\n    }\n' % name)
    w('    Material: 3000, "Material::M_%s", "" {\n        Version: 102\n        ShadingModel: "lambert"\n    }\n' % name)
    w("}\n\nConnections:  {\n")
    w('    C: "OO",2000,0\n    C: "OO",1000,2000\n    C: "OO",3000,2000\n}\n')
    return "".join(out)


# ----------------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------------
def convert_text(text, name="ChunkFlip", seed=7):
    mesh = build_ue_mesh(read_chunkflip_fbx(text), seed=seed)
    return write_ue_fbx(mesh, name), mesh


def convert_file(src_path, dst_path=None, seed=7):
    with open(src_path, "rb") as f:
        raw = f.read()
    if raw.startswith(b"Kaydara FBX Binary"):
        raise ValueError("这是二进制 FBX，请在工具里导出 ASCII FBX")
    text = raw.decode("utf-8", errors="replace")
    base = os.path.splitext(os.path.basename(src_path))[0]
    name = re.sub(r"[^\w]", "_", base) or "ChunkFlip"
    if dst_path is None:
        dst_path = os.path.join(os.path.dirname(src_path), "SM_%s_UE.fbx" % name)
    fbx, mesh = convert_text(text, "SM_" + name, seed)
    with open(dst_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(fbx)
    info = {"output": dst_path, "chunks": len(mesh["chunk_piv"]),
            "polys": len(mesh["polys"]), "warnings": mesh["warnings"]}
    return info


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    info = convert_file(argv[1], argv[2] if len(argv) > 2 else None)
    print("输出: %s" % info["output"])
    print("碎块数: %d  面数: %d" % (info["chunks"], info["polys"]))
    for w in info["warnings"]:
        print("警告: " + w)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
