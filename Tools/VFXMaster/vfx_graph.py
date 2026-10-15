# -*- coding: utf-8 -*-
"""用 Python 搭材质图的小工具：参数缓存、静态开关、Custom 节点、带校验的连线。"""
import unreal

mel = unreal.MaterialEditingLibrary
OT = unreal.CustomMaterialOutputType
F1, F2, F3, F4 = OT.CMOT_FLOAT1, OT.CMOT_FLOAT2, OT.CMOT_FLOAT3, OT.CMOT_FLOAT4


def sampler_for(tex):
    """按贴图的压缩设置和 sRGB 选采样类型，不匹配会编译报错。"""
    ST, TC = unreal.MaterialSamplerType, unreal.TextureCompressionSettings
    cs = tex.get_editor_property("compression_settings")
    srgb = tex.get_editor_property("srgb")
    if cs == TC.TC_NORMALMAP:
        return ST.SAMPLERTYPE_NORMAL
    if cs == TC.TC_MASKS:
        return ST.SAMPLERTYPE_MASKS
    if cs in (TC.TC_GRAYSCALE, TC.TC_ALPHA):
        return ST.SAMPLERTYPE_GRAYSCALE if srgb else ST.SAMPLERTYPE_LINEAR_GRAYSCALE
    return ST.SAMPLERTYPE_COLOR if srgb else ST.SAMPLERTYPE_LINEAR_COLOR


def _src(s):
    return s if isinstance(s, tuple) else (s, "")


class Graph(object):
    def __init__(self, mat):
        self.m = mat
        self.cache = {}
        self.customs = []      # (node, [input names]) 用于最后校验
        self.n = 0

    # ------------------------------------------------------------------ 基础
    def new(self, cls):
        self.n += 1
        return mel.create_material_expression(self.m, cls, -400 * (self.n % 8), 150 * self.n)

    def link(self, src, dst, pin=""):
        node, out = _src(src)
        for _ in range(2):
            if mel.connect_material_expressions(node, out, dst, pin):
                return
        raise RuntimeError("连线失败 %s.%s -> %s.%s  可用输出=%s 可用输入=%s" % (
            node.get_name(), out, dst.get_name(), pin,
            mel.get_material_expression_output_names(node),
            mel.get_material_expression_input_names(dst)))

    def output(self, src, prop):
        node, out = _src(src)
        if not mel.connect_material_property(node, out, prop):
            raise RuntimeError("连接材质输出失败: %s -> %s" % (node.get_name(), prop))

    def once(self, key, cls, **props):
        if key not in self.cache:
            n = self.new(cls)
            for k, v in props.items():
                n.set_editor_property(k, v)
            self.cache[key] = n
        return self.cache[key]

    # ------------------------------------------------------------------ 常用输入
    def time(self):
        return self.once("time", unreal.MaterialExpressionTime)

    def uv(self, i=0):
        return self.once("uv%d" % i, unreal.MaterialExpressionTextureCoordinate, coordinate_index=i)

    def vcolor(self):
        return (self.once("vc", unreal.MaterialExpressionVertexColor), "")

    def vcolor_rgba(self):
        # VertexColor 的 RGBA 需要 Append(RGB, A)
        if "vc4" not in self.cache:
            vc = self.once("vc", unreal.MaterialExpressionVertexColor)
            ap = self.new(unreal.MaterialExpressionAppendVector)
            self.link((vc, ""), ap, "A")
            self.link((vc, "A"), ap, "B")
            self.cache["vc4"] = ap
        return self.cache["vc4"]

    def normal_ws(self):
        return self.once("nws", unreal.MaterialExpressionVertexNormalWS)

    def camera_vec(self):
        return self.once("cam", unreal.MaterialExpressionCameraVectorWS)

    def two_sided_sign(self):
        return self.once("tss", unreal.MaterialExpressionTwoSidedSign)

    def local_pos(self):
        return self.once("lpos", unreal.MaterialExpressionPreSkinnedPosition)

    def dyn(self, names):
        """Dynamic Parameter。连线用 Param1~4（中文引脚名连不上），finish() 时再改显示名。"""
        if "dyn" not in self.cache:
            d = self.new(unreal.MaterialExpressionDynamicParameter)
            # 旧材质里残留的节点名会被复用，显式重置成默认名再连线
            d.set_editor_property("param_names", ["Param1", "Param2", "Param3", "Param4"])
            self.cache["dyn"] = d
            self.dyn_names = list(names)
        return self.cache["dyn"]

    def dyn_ch(self, i):
        """取 Dynamic Parameter 第 i 个分量(0~3)。按名连线在 5.8 不稳定，统一走 RGBA 再拆。"""
        key = "dynch%d" % i
        if key not in self.cache:
            self.cache[key] = self.custom("粒子数据%d" % (i + 1), "return D[%d];" % i,
                                          [("D", (self.cache["dyn"], "RGBA"))], F1)
        return self.cache[key]

    def finish(self):
        if "dyn" in self.cache and getattr(self, "dyn_names", None):
            self.cache["dyn"].set_editor_property("param_names", self.dyn_names)

    def c(self, v):
        return self.once("c1_%r" % v, unreal.MaterialExpressionConstant, r=float(v))

    def c2(self, x, y):
        return self.once("c2_%r_%r" % (x, y), unreal.MaterialExpressionConstant2Vector, r=float(x), g=float(y))

    def c3(self, x, y, z):
        return self.once("c3_%r_%r_%r" % (x, y, z), unreal.MaterialExpressionConstant3Vector,
                         constant=unreal.LinearColor(x, y, z, 0.0))

    def c4(self, x, y, z, w):
        return self.once("c4_%r_%r_%r_%r" % (x, y, z, w), unreal.MaterialExpressionConstant4Vector,
                         constant=unreal.LinearColor(x, y, z, w))

    # ------------------------------------------------------------------ 参数
    def _param(self, cls, name, group, prio, **props):
        key = "p_" + name
        if key in self.cache:
            return self.cache[key]
        p = self.new(cls)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("group", group)
        p.set_editor_property("sort_priority", prio)
        for k, v in props.items():
            p.set_editor_property(k, v)
        self.cache[key] = p
        return p

    def scalar(self, name, default, group, prio=0, smin=None, smax=None):
        p = self._param(unreal.MaterialExpressionScalarParameter, name, group, prio, default_value=float(default))
        if smin is not None:
            p.set_editor_property("slider_min", float(smin))
            p.set_editor_property("slider_max", float(smax))
        return p

    def vector(self, name, rgba, group, prio=0):
        """返回 (节点, "RGBA")：默认输出是 RGB(float3)，要 float4 必须指定 RGBA。"""
        return (self._param(unreal.MaterialExpressionVectorParameter, name, group, prio,
                            default_value=unreal.LinearColor(*rgba)), "RGBA")

    def texture(self, name, default_path, group, prio=0, sampler=None):
        """TextureObjectParameter：贴图对象，交给 Custom 节点用 Texture2DSample 采样。"""
        tex = unreal.load_asset(default_path)
        p = self._param(unreal.MaterialExpressionTextureObjectParameter, name, group, prio, texture=tex)
        p.set_editor_property("sampler_type", sampler if sampler is not None else sampler_for(tex))
        return p

    def switch(self, name, default, group, prio=0):
        """新建一个静态开关参数（同名复用）。连线时用 switch_link。"""
        return self._param(unreal.MaterialExpressionStaticSwitchParameter, name, group, prio,
                           default_value=bool(default))

    def gate(self, name, default, group, on, off, prio=0):
        """静态开关：开 = on，关 = off。返回开关节点。"""
        key = "g_%s_%s_%s" % (name, (id(_src(on)[0]), _src(on)[1]), (id(_src(off)[0]), _src(off)[1]))
        if key in self.cache:
            return self.cache[key]
        # 同一个参数名可以有多个开关节点，UE 会合并为一个参数
        self.n += 1
        s = mel.create_material_expression(self.m, unreal.MaterialExpressionStaticSwitchParameter, 0, 150 * self.n)
        s.set_editor_property("parameter_name", name)
        s.set_editor_property("group", group)
        s.set_editor_property("sort_priority", prio)
        s.set_editor_property("default_value", bool(default))
        self.link(on, s, "True")
        self.link(off, s, "False")
        self.cache[key] = s
        return s

    # ------------------------------------------------------------------ 运算
    def add(self, a, b):
        n = self.new(unreal.MaterialExpressionAdd)
        self.link(a, n, "A")
        self.link(b, n, "B")
        return n

    def append(self, a, b):
        n = self.new(unreal.MaterialExpressionAppendVector)
        self.link(a, n, "A")
        self.link(b, n, "B")
        return n

    def custom(self, desc, code, inputs, out_type=F1, extra=()):
        """inputs: [(名字, 源)]；extra: [(输出名, 类型)]"""
        n = self.new(unreal.MaterialExpressionCustom)
        n.set_editor_property("description", desc)
        n.set_editor_property("output_type", out_type)
        ins = []
        for name, _ in inputs:
            ci = unreal.CustomInput()
            ci.set_editor_property("input_name", name)
            ins.append(ci)
        n.set_editor_property("inputs", ins)
        outs = []
        for name, t in extra:
            co = unreal.CustomOutput()
            co.set_editor_property("output_name", name)
            co.set_editor_property("output_type", t)
            outs.append(co)
        n.set_editor_property("additional_outputs", outs)
        n.set_editor_property("code", code)
        for name, src in inputs:
            self.link(src, n, name)
        self.customs.append((n, [x[0] for x in inputs], list(inputs)))
        return n

    def mf(self, path, inputs):
        """调用材质函数。inputs: {输入名: 源}"""
        n = self.new(unreal.MaterialExpressionMaterialFunctionCall)
        fn = unreal.load_asset(path)
        if hasattr(n, "set_material_function"):
            n.set_material_function(fn)
        else:
            n.set_editor_property("material_function", fn)
        for k, v in inputs.items():
            self.link(v, n, k)
        return n

    # ------------------------------------------------------------------ 校验
    def verify(self):
        """所有 Custom 输入都接上；缺的按记录重连一次。"""
        bad = []
        for node, names, pairs in self.customs:
            ins = mel.get_inputs_for_material_expression(self.m, node)
            for (name, src), got in zip(pairs, ins):
                if got is None:
                    self.link(src, node, name)
                    if mel.get_inputs_for_material_expression(self.m, node)[names.index(name)] is None:
                        bad.append("%s.%s" % (node.get_editor_property("description"), name))
        if bad:
            raise RuntimeError("以下输入没接上: %s" % bad)
