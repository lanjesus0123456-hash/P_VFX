# 用法: rt_suite.py make | rt_suite.py run 起始序号 个数
import sys, time, json
sys.path.insert(0, r"G:/UE_Project/P_VFX/Tools/VFXMaster/_dev")
from rt_host import UE, mean, diff
from tests import T, PLANE
ue = UE()
try:
    if sys.argv[1] == "make":
        ue.run("importlib.reload(T)\nT.setup()")
        for t in T:
            ue.run("T.make_mi(%r, %r, vectors=%r, scalars=%r)" % (t[0], t[1], t[2].get("v", {}), t[2].get("s", {})))
            for k, v in t[2].get("t", {}).items():
                ue.run("T.settex(%r, %r, %r)" % (t[0], k, v))
        print("已建 %d 个测试实例，开始后台编译" % len(T))
    else:
        a, n = int(sys.argv[2]), int(sys.argv[3])
        bg = ue.val("T.capture(False)")
        for t in T[a:a + n]:
            name, exp = t[0], t[5]
            mesh = t[6] if len(t) > 6 else PLANE
            ue.run("T.use(%r, %r)" % (name, mesh))
            time.sleep(2.5)   # 换材质/网格后等渲染资源就绪
            ue.val("T.capture(True)")
            ue.run("T.setp(%r, scalars=%r, vectors=%r)" % (name, t[3].get("s", {}), t[3].get("v", {})))
            time.sleep(1.5)
            pa = ue.val("T.capture(True)")
            ue.run("T.setp(%r, scalars=%r, vectors=%r)" % (name, t[4].get("s", {}), t[4].get("v", {})))
            time.sleep(1.5)
            pb = ue.val("T.capture(True)")
            dA, dB, dAB = diff(pa, bg), diff(pb, bg), diff(pa, pb)
            # 噪声基线：透明度 0 时与背景差约 3；正常显示约 30
            VIS, GONE = 15, 10
            if exp == "diff":       ok = max(dA, dB) > VIS and dAB > 3
            elif exp == "vanish":   ok = dA > VIS and dB < GONE
            elif exp == "same":     ok = dA > VIS and dAB < 1.5   # 关掉影响颜色后，扰动强度不应改变画面
            elif exp == "vanish_a": ok = dA < GONE           # 粒子数据未接 Niagara 时默认 1 -> 溶解进度 1 -> 消失
            else:                   ok = dA > VIS            # 能正常显示即视为编译通过
            print("%-16s A与背景=%6.2f  B与背景=%6.2f  A与B=%6.2f  %s" % (name, dA, dB, dAB, "通过" if ok else "未通过"))
finally:
    ue.close()
