# M_VFX_Master 特效母材质

参考 Unity 特效 Shader 的功能结构，从零搭建（不改归玥包）。RefineColor 公式与 `Guiyue_MF_Refine` 一致，VAT 调用归玥的 `Guiyue_Vat_Revamp`。
每个功能一个静态开关，关闭的功能不参与编译。

- 重建：编辑器 Tools > Execute Python Script > `build_vfx_master.py`（会清空母材质节点重搭，手动改的连线会丢，改动请写回脚本）
- 产物：`/Game/VFX/Materials/Master/`
  - `M_VFX_Master`：母材质（Unlit / Translucent / 双面）
  - `MI_VFX_Additive`、`MI_VFX_Translucent`：两种混合方式的预设
  - `Enums/`：下拉栏用的枚举

## 约定
- 颜色参数都是 RGBA，A = 强度
- UV：`平铺偏移` = (Tiling U, Tiling V, Offset U, Offset V)；`速度UV/旋转/极坐标` = (速度 U, 速度 V, 旋转角度, 极坐标 0/1)
- 通道选择：(R, G, B, A) 权重，例如 (0, 0, 0, 1) 取 A
- 强度向量（扰动 / 折射）：R = 总强度，G = U 方向，B = V 方向，A = Z 轴

## 面板分组
| 分组 | 开关 | 说明 |
|---|---|---|
| 00 全局 | 使用粒子数据? | Dynamic Parameter：P1/P2 替换主贴图平铺偏移的 Offset，P3 溶解进度，P4 扰动总强度 |
| 01 自发光 | RefineColor? | 主贴图 + 主颜色(A=强度) |
| 02 叠加 | 叠加? | 叠加方式下拉：乘法 / 加法 |
| 03 遮罩 | 遮罩? | |
| 04 序列帧 | 序列帧动画? | |
| 05 溶解 | 溶解? | 软硬、描边、方向溶解 |
| 06 扰动 | 扰动? / 扰动影响遮罩? / 扰动影响颜色? / 扰动影响溶解? | 强度 RGBA；Z 轴沿模型本地 Z 偏移顶点 |
| 07 / 08 | 菲涅尔? / 透明度菲涅尔? | |
| 09 软粒子 | 触边虚化(软粒子)? | |
| 10 顶点偏移 | 顶点偏移? | |
| 11 VAT顶点动画 | VAT顶点动画? | Houdini Labs VAT，贴图和 Bound 参数在面板里填 |
| 12 折射 | 折射? | 控制方式下拉：通道 / 贴图 / 通道x贴图 / 通道+贴图 |
| 13 流动贴图 | 流动贴图? | |
| 14 色散 | 色散? / 色散 极坐标? | 对最终结果做 RGB 分离（R/G/B 各算一遍完整效果）；极坐标模式按中心径向/旋转错开；带色散遮罩 |
| 15 视差映射 | 视差映射? | 高度图步进，最多 32 步 |
| 16 故障 | 故障? | 按块随机错位（作用于所有图层的基础 UV）+ RGB 分离 + 闪烁/扫描线 |
| 17 碎块翻转 | 碎块翻转生长? | 需配合 `Tools/ChunkFlip` 转换过的网格 |

## 下拉栏
标量参数的 UI > Control Type 设为 Enumeration 才会显示成下拉栏（脚本已设置）。UE 的 Python 无法给枚举添加选项，`Enums/` 下的两个枚举需要手动打开，按顺序添加：
- `E_VFX_BlendOp`：乘法叠加、加法叠加
- `E_VFX_RefractMode`：通道控制、贴图控制、通道x贴图、通道+贴图

## State Settings 对应
| Unity | UE |
|---|---|
| Add / Blend | 实例 > Material Property Overrides > Blend Mode；Additive 时 `颜色乘透明度` 设 1 |
| 剔除正反面 | 实例覆盖 Two Sided |
| 写深度 / 深度剔除 | 母材质 Translucency 里的 Output Depth / Disable Depth Test |

## 性能
色散或故障打开时，颜色部分会算三遍（R/G/B 各一遍），像素指令约为关闭时的 2.5 倍；两者都关时只算一遍。
