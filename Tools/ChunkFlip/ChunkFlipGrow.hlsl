// ============================================================================
// 碎块翻转生长 - UE Custom 节点代码
// ue_chunkflip_pipeline.py 会自动建好材质并粘贴代码，手动搭建时参考下面的说明。
//
// 拆成两个 Custom 节点（PreSkinnedPosition 只能在顶点着色器用）：
//   [VS] ChunkFlipGrow_VS : 输出 Float3 本地位置偏移 -> TransformVector(Local->World) -> WPO
//   [PS] ChunkFlipGrow_PS : 输出 Float3 Tint，附加输出 Phase / Grow (Float1)
//
// 共用 Inputs：
//   Growth     : TexCoord[1]      x = 生长值
//   PivotZRand : TexCoord[3]      x = 碎块中心 Z，y = 每块随机值
//   Flow       : 流动值（-0.2 ~ 1.2）
//   Band       : 流动区域范围（0.05 ~ 0.5）
//   RandSpread : 随机错开量（0 ~ 0.3）
//   CurveMode  : 0=生长(0→1)  1=消散(1→0)  2=掠过(0→1→0)
//   Reverse    : 1 = 反向
// VS 额外 Inputs：LocalPos(PreSkinnedPosition) / PivotXY(TexCoord[2]) / MinScale / ChunkScale /
//                 HeadRot / MidRot / TailRot（角度）
// PS 额外 Inputs：HeadCol / MidCol / TailCol
// ============================================================================

// @@COMMON
float g = Growth.x + (PivotZRand.y - 0.5) * RandSpread;
g = lerp(g, 1.0 - g, saturate(Reverse));
// s：0 = 扫描带还没到达，1 = 扫描带已经过去
float s = saturate((Flow - g) / max(Band, 1e-4));
float c;
if (CurveMode < 0.5)      c = s;                        // 生长
else if (CurveMode < 1.5) c = 1.0 - s;                  // 消散
else                      c = 1.0 - abs(s * 2.0 - 1.0); // 掠过
c = c * c * (3.0 - 2.0 * c);
float t1 = saturate(s * 2.0);
float t2 = saturate(s * 2.0 - 1.0);

// @@VS
float scl = lerp(MinScale, 1.0, c) * ChunkScale;
float3 rotDeg = lerp(lerp(HeadRot.xyz, MidRot.xyz, t1), TailRot.xyz, t2);
// 欧拉角 -> 旋转矩阵（R = Rz * Ry * Rx）
float3 r = rotDeg * (3.14159265 / 180.0);
float3 sn, cs;
sincos(r, sn, cs);
float3x3 Rx = float3x3(1, 0, 0,   0, cs.x, -sn.x,   0, sn.x, cs.x);
float3x3 Ry = float3x3(cs.y, 0, sn.y,   0, 1, 0,   -sn.y, 0, cs.y);
float3x3 Rz = float3x3(cs.z, -sn.z, 0,   sn.z, cs.z, 0,   0, 0, 1);
float3x3 R  = mul(Rz, mul(Ry, Rx));
// 绕碎块中心缩放 + 旋转
float3 pivot = float3(PivotXY.x, PivotXY.y, PivotZRand.x);
float3 local = LocalPos - pivot;
float3 moved = pivot + mul(R, local * scl);
return moved - LocalPos;

// @@PS
Phase = s;
Grow = c;
return lerp(lerp(HeadCol.rgb, MidCol.rgb, t1), TailCol.rgb, t2);
