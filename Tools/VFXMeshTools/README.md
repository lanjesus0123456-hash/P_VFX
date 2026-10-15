# P_VFX 特效模型工具测试

已安装 **VFX Mesh Tools UE v0.1.1（UE 5.8）**。本工程实际使用 UE 5.8.3，因此从原 UE 5.3 测试版单独编译了适配版本。

## 打开测试关卡

双击本目录的 **打开VFX测试关卡.cmd**。

也可打开 P_VFX 工程，在内容浏览器中进入：

`Content > VFXMeshTools_Test > UE58_02 > Map_VFXMeshTools_Test`

工程原来的启动关卡保持原设置。

## 手动测试

在世界大纲中选择 `VFX_Test/Models` 下的对象，使用 Details 参数区调整；点击 **Rebuild** 可手动刷新。

| 对象 | 可测试内容 |
| --- | --- |
| 01_样条线_双路径 | SplinePaths 修改控制点、新增路径；SplineSurface 选择条带／十字／管状；PointSpace 切换 Local／World |
| 02_螺旋模型 | HelixProfile 编辑沿高度的水平轮廓缩放曲线，可把中部设为 0.5 观察收腰 |
| 03_自定义_起伏和不规则边缘 | 修改边界 Z，观察内部高度点跟随；调边缘幅度、细分、频率和随机种子 |
| 04_破碎_两个碎片 | 调碎片厚度、预览散开量；更换 FractureSource 和碎片数量 |
| 05_地刺_循环生长 | 调形状、排列、数量、随机种子、时长及错峰；点击 Play 观察循环生长 |

UE 的竖直轴是 Z。测试关卡已放置 8 根环形排列地刺，开启 Play Growth 和 Loop Growth；编辑器默认显示完整模型，运行后从根部开始错峰生长。

这次导入保留了原工程已有插件、默认启动地图及 EngineAssociation，增加 VFXMeshToolsUE 插件配置。原工程描述文件备份在：

`Saved/VFXMeshTools/Backups/20261015_UE58_0_1_1/P_VFX.uproject.before`

## 自动验收结果

- UE 5.8.3：编辑器 Development、游戏 Development、游戏 Shipping 三目标编译成功。
- 此 P_VFX 工程内 `VFX.MeshTool.Smoke`：1 通过，0 失败，0 警告，覆盖五种模式、坐标换算、收腰、高度跟随、破碎、地刺确定性和运行时 Tick 生长。
- 专用关卡：110 项检查通过；网格索引及坐标有效；8 根地刺从隐藏到完全生长；2 个碎片；保存重载后 5 个工具对象及全部生成网格恢复。
- 详细结果在 `Saved/VFXMeshTools/Reports/UE58_0_1_1`。

## 测试版范围

破碎为表面分片加厚。此 UE 测试版在引擎内生成与播放；FBX 导出仍由 Unity v1.7／v1.8 发布版提供。样条数据在 UE 中随关卡／对象参数保存，此版没有 Unity v1.9 的独立 JSON 预设按钮。