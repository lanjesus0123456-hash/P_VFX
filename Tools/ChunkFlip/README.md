# 碎块翻转生长 -> UE 5.8 流程

## 一键流程（编辑器内）
1. 工具里用「输出固定模型」导出 ASCII FBX（不要选骨骼动画）。
2. UE 菜单 Tools > Execute Python Script，选 `ue_chunkflip_pipeline.py`（默认处理 `Test/A_clone.fbx`）。
   换文件就在 Output Log 的 Python 命令行里运行：
   ```python
   import sys; sys.path.append(r"G:/UE_Project/P_VFX/Tools/ChunkFlip")
   import ue_chunkflip_pipeline as P; P.run(r"D:/路径/xxx.fbx")
   ```
3. 结果在 `/Game/VFXTool_Test/ChunkFlip/`：`SM_xxx_UE`、`M_ChunkFlipGrow`、`MI_xxx`，当前关卡会放一个 `ChunkFlip_Preview`。

脚本自动处理：全精度 UV、不重算法线、关 Nanite、包围盒外扩 30%。

## 数据布局（转换后）
| UV | 内容 |
|---|---|
| UV0 | 原始 UV |
| UV1 | 生长值 (U = 扫描值) |
| UV2 | 碎块中心 X, Y（厘米，本地空间） |
| UV3 | 碎块中心 Z, 每块随机值 |

UE 导入 FBX 时会把顶点 Y 取反、UV 的 V 改成 1-V，转换脚本已经预先补偿。手动改脚本时注意这一点。

## 材质参数
| 分组 | 参数 | 说明 |
|---|---|---|
| 01 流动 | Flow | 生长进度，-0.2 = 全无，1.2 = 全部长完 |
| | Band | 扫描带宽度，越大过渡越柔 |
| | RandSpread | 每块随机错开，0 = 整齐推进 |
| | CurveMode | 0 生长 / 1 消散 / 2 掠过（长出再缩回） |
| | Reverse | 1 = 反向 |
| 02 缩放 | MinScale / ChunkScale | 未长出时的缩放 / 碎块整体大小 |
| 03 旋转 | HeadRot / MidRot / TailRot | 头 / 中 / 尾 XYZ 旋转（角度） |
| 04 颜色 | HeadCol / MidCol / TailCol / EmissiveStrength | 头中尾颜色，扫描带发光强度 |

## 驱动
- 镜头：Sequencer 给 `MI` 或 MID 的 `Flow` 打关键帧（-0.2 -> 1.2）。
- 特效：Niagara Mesh Renderer 用这个网格，把 `Flow` 换成 Dynamic Parameter 接粒子生命周期。

## 已知限制
- 碎块旋转后，光照法线没有跟着转。风格化 Unlit 或自发光为主时看不出来。
- 母材质是 Default Lit + Masked。要接归玥材质包，把 `ChunkFlipGrow_VS` 的输出接到它的 WPO 上即可。
