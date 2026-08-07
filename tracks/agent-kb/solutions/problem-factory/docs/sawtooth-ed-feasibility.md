# 锯齿链 ED 可行性报告（#112 day-1 锚点电池）

日期：2026-07-28 · 作者：求解侧 · 结论先行：**锚点电池在 N=16–20 本机可做，N=24 勉强，N=28 留给集群；builder 必须 sparse-native**

## 1. 机器盘点（本机）

| 项 | 值 | 含义 |
|---|---|---|
| CPU | i7-10870H，8C/16T @2.2GHz | 笔记本级，LAPACK 实测 ~7 GFLOPS |
| RAM | 7.6 GB（可用 ~4.6 GB） | **硬约束**：dense ED 上限 D≈16k |
| 集群（备用） | 曙光 qdagnormal，32C/2TB/A800 | N=28 与有限温全谱的去处 |

## 2. 复杂度模型

Sz 守恒下最大 sector 维数 D = C(N, N/2)：

| N | N_c（原胞） | D | dense 内存 (D²×8B) | sparse 内存 (~9 nnz/行) | 本机判决 |
|---|---|---|---|---|---|
| 16 | 8 | 12,870 | 1.3 GB | ~1 MB | ✅ dense 全 sector 可跑 |
| 18 | 9 | 48,620 | 19 GB ✗ | ~4 MB | sparse only |
| 20 | 10 | 184,756 | 273 GB ✗ | ~15 MB | sparse ✅ |
| 24 | 12 | 2.7 M | — | ~220 MB | sparse 勉强（分钟级） |
| 28 | 14 | 40.1 M | — | ~2.9 GB + Lanczos 基 ~6 GB | ❌ 超本机 RAM → 集群 |

锯齿链每格点 4 条键（2 J₁ + 2 J₂），nnz/行约为普通链 2 倍，上表 sparse 列已含此因子。

## 3. 实测基准（本机，XXZ Sz=0 sector）

| L | D | dense eigvalsh | sparse eigsh k=4 | matvec |
|---|---|---|---|---|
| 14 | 3,432 | 5.5 s | 0.01 s | — |
| 16 | 12,870 | **287 s** | 0.06 s | — |
| 18 | 48,620 | 内存不够 | 0.21 s | 1.0 ms |
| 20 | 184,756 | 内存不够 | 1.8 s | 4.7 ms |

外推（D 每 +2 格点 ×3.8）：L=24 sparse ~1 min；L=28 ~5–15 min 但 **RAM 爆**。

## 4. 逐锚点可行性（#112 day-1 电池）

| 锚点 | 所需 sector | 本机方案 | 上限 |
|---|---|---|---|
| ① 平带 ε=−4J₁ | 单磁振子，dim=N | 免费 | 任意 N |
| ② 跳变 ΔM=M_sat/2 | 每 Sz sector 基态能 | sparse 逐 sector | N=24–26 |
| ③ 简并计数（精确整数） | h=h_sat 处逐 sector 数简并 | N≤16 dense 全谱；N=18–20 shift-invert | N=20 |
| ④ 剩余熵 0.2406 | ③的总和 | 同③ | N=20 |
| （day-4 有限温全谱） | 全部本征值 | 273 GB dense @N=20 | **集群专属** |

③的注意点：h_sat 处基态巨简并（N_c=8 时 Lucas 数 L₈=47），Lanczos 对重根收敛慢；用已知解析基态能 E_k 做 shift-invert 直接数零空间，避开迭代收敛问题。LU 填内存估计 N=20 ~1–2 GB，可行。

## 5. 对实现的要求（builder 设计约束）

1. `pf/ed.py` 新增 `sawtooth` builder：**sparse-native**（eigsh/shift-invert），dense 仅用于 N≤16 的整数计数验证
2. J₂/J₁=1（Monti–Sütő）与 2（平带点）是两个不同特殊点——issue 警告的混淆陷阱，两个点分别进 static fire
3. 发射纪律不变：先跑 N=16 全电池（~5 min dense 计数），再逐级放大

## 6. 风险

- 本机 RAM 7.6 GB：跑 N≥20 sparse 时关浏览器等大户
- shift-invert 的 LU 填内存可能超估，N=20 先小试再上量
- h=h_sat 精确简并依赖浮点容差：整数计数用相对容差 1e-8 分组
