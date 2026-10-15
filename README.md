# P_VFX

UE **5.8.3** 特效工程，包含现有资源、UnityResourceBridge 和 VFX Mesh Tools UE v0.1.1 测试工具。

## 获取工程

本仓库的模型、地图与资源文件通过 Git LFS 保存。首次下载应使用支持 Git LFS 的 Git 客户端。

```bash
git lfs install
git clone https://github.com/lanjesus0123456-hash/P_VFX.git
cd P_VFX
git lfs pull
```

使用 UE 5.8.3 打开 `P_VFX.uproject`。两个工程插件的源码及现用 Windows 编辑器 DLL 已包含在仓库中；其他引擎构建或平台需从源码重新编译。缓存、日志、编译临时文件由本机重建。

## VFX 模型测试

在内容浏览器打开：

`Content/VFXMeshTools_Test/UE58_02/Map_VFXMeshTools_Test`

关卡包含 Spline 双路径、Helix、自定义起伏面片与不规则边缘、破碎和 8 根环形地刺。选择世界大纲中的 `VFX_Test/Models` 对象，在 Details 中调整参数。点击 **Play** 可观察地刺错峰循环生长。

- [工具使用说明](Tools/VFXMeshTools/README.md)
- [工程验收记录](Tools/VFXMeshTools/Reports/integration.json)
- [自动化测试记录](Tools/VFXMeshTools/Reports/automation-report.json)

## 同步范围

纳入工程描述文件、Config、Content、插件源码／DLL／模块描述及 Tools；排除 DerivedDataCache、Intermediate、Saved、插件编译临时文件、调试符号和本地会话状态。