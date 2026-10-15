# -*- coding: utf-8 -*-
"""M_VFX_Master 各功能模块的 HLSL（Custom 节点代码）。

约定：
  * UV：ST = (平铺U, 平铺V, 偏移U, 偏移V)，Pan = (速度U, 速度V, 旋转角度, 极坐标0/1)
  * 颜色：RGBA，A = 强度
  * 强度向量（扰动/折射）：R = 总强度，G = U 方向，B = V 方向，A = Z 轴
  * 通道选择：(R, G, B, A) 权重点乘
"""

UV_FUNC = r"""
float2 uv = UV;
float2 c = float2(0.5, 0.5);
if (Pan.w > 0.5) {
    float2 d = uv - c;
    uv = float2(atan2(d.y, d.x) / 6.2831853 + 0.5, length(d) * 2.0);
}
float a = radians(Pan.z);
float sa, ca; sincos(a, sa, ca);
uv = mul(float2x2(ca, -sa, sa, ca), uv - c) + c;
uv = uv * ST.xy + ST.zw + Pan.xy * Time + Extra;
return uv;
"""

ROTATE_UV = r"""
float a = radians(Angle);
float sa, ca; sincos(a, sa, ca);
return mul(float2x2(ca, -sa, sa, ca), UV - 0.5) + 0.5;
"""

# 粒子数据替换：主贴图偏移 / 扰动总强度
REPLACE_ZW = "return float4(ST.xy, P.xy);"
REPLACE_X = "return float4(P, S.yzw);"

FLIPBOOK = r"""
float total = Grid.x * Grid.y;
float f = (Grid.w > 0.5) ? Frame : Time * Grid.z;
f = floor(fmod(f, total));
float2 cell = float2(fmod(f, Grid.x), floor(f / Grid.x));
return (frac(UV) + cell) / Grid.xy;
"""

# 扰动：S = (总强度, U, V, Z)
DISTORT = r"""
float2 n = Texture2DSample(Tex, TexSampler, NUV).rg * 2.0 - 1.0;
return n * S.yz * S.x * Mask;
"""
# 扰动 Z 轴（VS）：沿模型本地 Z 偏移
DISTORT_Z = r"""
float n = Texture2DSampleLevel(Tex, TexSampler, NUV, 0).r * 2.0 - 1.0;
return float3(0.0, 0.0, n * S.w * S.x);
"""

FLOWMAP = r"""
float2 dir = (Texture2DSample(Tex, TexSampler, FUV).rg * 2.0 - 1.0) * Strength;
float t = Time * Speed;
float p0 = frac(t), p1 = frac(t + 0.5);
FlowB = dir * p1;
Blend = abs(p0 * 2.0 - 1.0);
return dir * p0;
"""

# 主贴图采样：流动贴图双相位；Off 非 0 时 R/B 通道错开（色散、故障共用）
SAMPLE_MAIN = r"""
float4 a = Texture2DSample(Tex, TexSampler, TUV + FlowA);
float4 b = Texture2DSample(Tex, TexSampler, TUV + FlowB);
if (any(Off != 0.0)) {
    a.r = Texture2DSample(Tex, TexSampler, TUV + FlowA + Off).r;
    a.b = Texture2DSample(Tex, TexSampler, TUV + FlowA - Off).b;
    b.r = Texture2DSample(Tex, TexSampler, TUV + FlowB + Off).r;
    b.b = Texture2DSample(Tex, TexSampler, TUV + FlowB - Off).b;
}
return lerp(a, b, Blend);
"""

# 色散：D = (方向U, 方向V, 强度, 径向0/1)
DISPERSION = r"""
float2 d = (D.w > 0.5) ? (UV - 0.5) : D.xy;
return d * D.z * 0.01;
"""

# 归玥 Refine（同 Guiyue_MF_Refine）：Ctrl = (Power, HDR强度, Soft强度, 虚实比例)
REFINE = r"""
float3 x = max(T.rgb, 0.0);
float3 hard = pow(x, max(Ctrl.x, 1e-3)) * Ctrl.y;
float3 soft = x * Ctrl.z;
return float4(lerp(hard, soft, Ctrl.w), T.a);
"""

# 视差映射：切线空间视线步进，输出 UV 偏移
#   P = (深度, 步数, 高度通道0R1G2B3A, 反向0/1)
PARALLAX = r"""
float3 v = normalize(VT);
int steps = clamp((int)P.y, 4, 32);
float2 dUV = -v.xy / max(abs(v.z), 0.2) * P.x / steps;
float layer = 1.0 / steps, d = 0.0;
float4 hm = float4(P.z < 0.5, abs(P.z - 1.0) < 0.5, abs(P.z - 2.0) < 0.5, P.z > 2.5);
float2 uv = UV;
float h = dot(Texture2DSampleLevel(Tex, TexSampler, uv, 0), hm);
h = (P.w > 0.5) ? 1.0 - h : h;
[loop] for (int i = 0; i < steps && d < 1.0 - h; i++) {
    uv += dUV; d += layer;
    h = dot(Texture2DSampleLevel(Tex, TexSampler, uv, 0), hm);
    h = (P.w > 0.5) ? 1.0 - h : h;
}
return uv - UV;
"""

# 故障：按行切块随机横移 + RGB 分离
#   G = (强度0~1, 切块行数, 跳变频率, RGB分离)
GLITCH = r"""
float t = floor(Time * G.z);
float row = floor(UV.y * G.y);
float r = frac(sin(dot(float2(row, t), float2(12.9898, 78.233))) * 43758.5453);
float on = step(1.0 - G.x, r);
Split = float2(G.w * on * 0.01, 0.0);
return float2((r - 0.5) * 0.2 * G.x * on, 0.0);
"""

# 叠加：返回 (贴图RGB*颜色RGB, 贴图A)，K = 颜色A（强度）
ADD = r"""
float4 t = Texture2DSample(Tex, TexSampler, TUV);
K = Col.a;
return float4(t.rgb * Col.rgb, t.a);
"""

MASK = r"""
return dot(Texture2DSample(Tex, TexSampler, TUV), Ch);
"""

# 溶解：Amount 0~1，Soft 软硬，EdgeW 描边宽度；Dir = (方向U, 方向V, 强度, 开关)
DISSOLVE = r"""
float n = dot(Texture2DSample(Tex, TexSampler, DUV), Ch);
if (Dir.w > 0.5) {
    float2 d = normalize(Dir.xy + 1e-5);
    n = lerp(n, dot(BaseUV - 0.5, d) + 0.5, saturate(Dir.z));
}
float a = Amount * (1.0 + Soft + EdgeW) - Soft * 0.5;
float m = smoothstep(a - Soft * 0.5, a + Soft * 0.5 + 1e-4, n);
float e = smoothstep(a - Soft * 0.5, a + Soft * 0.5 + 1e-4, n - EdgeW);
Edge = saturate(m - e);
return m;
"""

# 菲涅尔：Pw 次幂，Str 强度，Inv 反向，TS 双面修正
FRESNEL = r"""
float3 n = normalize(N) * ((TS > 0.5) ? Sign : 1.0);
float f = pow(1.0 - saturate(dot(n, normalize(V))), max(Pw, 1e-3));
f = (Inv > 0.5) ? 1.0 - f : f;
return saturate(f) * Str;
"""

# 顶点偏移（VS）：Ctrl = (强度, 速度U, 速度V, 平铺)
VERTEX_OFFSET = r"""
float2 uv = UV * Ctrl.w + Ctrl.yz * Time;
float n = dot(Texture2DSampleLevel(Tex, TexSampler, uv, 0), Ch);
return N * (n - 0.5 * Bias) * Ctrl.x;
"""

SUM3 = "return A + B + C;"

# 折射：Mode 0=通道控制 1=贴图控制 2=通道x贴图 3=通道+贴图
#   通道值取自最终 RGBA；S = (总强度, U方向, V方向, -)
REFRACT = r"""
float c = dot(float4(C, A), Ch);
float2 t = Texture2DSample(Tex, TexSampler, RUV).rg * 2.0 - 1.0;
float2 o;
if (Mode < 0.5)      o = c.xx;
else if (Mode < 1.5) o = t;
else if (Mode < 2.5) o = c * t;
else                 o = c + t;
return o * S.yz * S.x;
"""

# 最终合成
#   Tint / EdgeCol / FresCol / Add 颜色：RGB 颜色，A 强度
#   AddMode：0 = 乘法叠加，1 = 加法叠加
COMBINE = r"""
float3 col = Main.rgb * Tint.rgb * Tint.a;
float  a   = Main.a;
// 叠加
if (AddMode < 0.5) {
    col = lerp(col, col * Add.rgb, AddK);
    a  *= lerp(1.0, Add.a, AddK * AddAlpha);
} else {
    col += Add.rgb * Add.a * AddK;
    a = saturate(a + Add.a * AddK * AddAlpha);
}
a *= MaskV;
// 溶解描边
col = lerp(col, EdgeCol.rgb * EdgeCol.a, Edge);
a *= saturate(Dis + Edge);
// 菲涅尔
col += FresCol.rgb * FresCol.a * Fres;
a *= AFres;
// 顶点色
col *= lerp(1.0, VC.rgb, VCc);
a   *= lerp(1.0, VC.a, VCa);
// 碎块翻转
a *= ChunkA;
col += ChunkGlow;
a = saturate(a * Opacity) * SoftP;
Alpha = a;
return col * lerp(1.0, a, PremulA);
"""

# 碎块扫描带发光：Col RGB 颜色，A 强度
CHUNK_GLOW = r"""
float e = 1.0 - abs(Phase * 2.0 - 1.0);
return Tint * Col.rgb * Col.a * e * e;
"""
