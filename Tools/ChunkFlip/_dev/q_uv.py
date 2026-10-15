import unreal
sm = unreal.load_asset("/Game/VFXTool_Test/ChunkFlip/SM_A_clone_UE")
md = sm.get_static_mesh_description(0)
n = md.get_vertex_instance_count()
print("vertex instances:", n)
# 前 3 个碎块：比较 UV2/UV3 里的 pivot 与该顶点所属块的位置
chunks = {}
for i in range(min(n, 24*40)):
    vi = unreal.VertexInstanceID(i)
    v = md.get_vertex_instance_vertex(vi)
    p = md.get_vertex_position(v)
    u2 = md.get_vertex_instance_uv(vi, 2); u3 = md.get_vertex_instance_uv(vi, 3)
    key = (round(u2.x, 2), round(u2.y, 2), round(u3.x, 2))
    chunks.setdefault(key, []).append((p.x, p.y, p.z))
for k, ps in list(chunks.items())[:4]:
    c = [sum(q[j] for q in ps) / len(ps) for j in range(3)]
    print("UV pivot=(%.2f, %.2f, %.2f)  实际顶点中心=(%.2f, %.2f, %.2f)" % (k + tuple(c)))
