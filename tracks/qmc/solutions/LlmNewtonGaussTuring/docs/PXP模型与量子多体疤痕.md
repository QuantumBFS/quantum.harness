---
title: PXP 模型与量子多体疤痕
date: 2026-07-20
tags:
  - quantum-many-body-scars
  - PXP
  - exact-diagonalization
  - weak-ergodicity-breaking
status: note
related:
  - tracks/ed/NOTES.md
  - tracks/ed/TASK_REPORT_track3_4.md
  - 文献库/ED/
---

# PXP 模型与量子多体疤痕

## 摘要

本文整理一维 Rydberg 阻塞极限下的 PXP 模型，以及该模型中量子多体疤痕（quantum many-body scars, QMBS）的定义、谱结构、动力学签名与扰动稳健性要点。叙述以可操作定义与可核验表述为主，数值量级以文献及本工作空间已完成的精确对角化（ED）复现为参照，并标明适用范围与未解决问题。

---

## 1. 背景与问题

孤立量子多体系统的长时间局域动力学，通常由能量本征态的性质约束。若在给定能量密度处，典型本征态的局域可观测量期望与热力学预言一致，则一般初态会热化：晚时间局域量仅依赖少量守恒量（能量等），初态细节被擦除。该图像的标准表述是本征态热化假说（eigenstate thermalization hypothesis, ETH）[1]。

量子多体疤痕描述的是一类**弱遍历破缺**（weak ergodicity breaking）现象：哈密顿量在高能量密度区仍可具有混沌谱统计，但谱中嵌有**稀疏**的非典型本征态子集；若初态在该子集上具有足够大的权重，则动力学可呈现长时间相干振荡，而非迅速热化 [2, 3]。与多体局域化（MBL）不同，PXP 型疤痕出现在平移不变、无强无序的干净系统中，非典型态的相对数目通常随系统尺寸呈多项式（或更弱）增长，相对希尔伯特空间维数趋于零。

实验上，一维 Rydberg 原子阵列在强阻塞区的淬火动力学给出了关键证据：由周期-2 初态出发可观测到持续振荡 [4]。有效理论描述即 PXP 模型 [2]。

---

## 2. 模型

### 2.1 局域希尔伯特空间与阻塞约束

每个格点取两能级：原子基态 $\lvert\circ\rangle$（常编码为比特 $0$）与 Rydberg 激发 $\lvert\bullet\rangle$（比特 $1$）。强近邻 van der Waals 相互作用使相邻双激发在能量上被排除。**硬阻塞极限**下，物理空间限制为

$$
\mathcal{H}_{\mathrm{cons}}
=
\mathrm{span}\bigl\{\text{无相邻 $\bullet$ 的位形}\bigr\}.
\tag{1}
$$

周期边界条件（PBC）下，$\dim\mathcal{H}_{\mathrm{cons}}=L_N$，其中 $L_N$ 为 Lucas 数，满足 Fibonacci 型递推，渐近 $\dim\mathcal{H}_{\mathrm{cons}}\sim\varphi^N$，$\varphi=(1+\sqrt{5})/2$，而非 $2^N$。

### 2.2 PXP 哈密顿量

在阻塞投影子空间内，驱动项取 Rabi 频率 $\Omega$ 的形式。标准纯 PXP 点（失谐 $\Delta=0$）写为

$$
H_{\mathrm{PXP}}
=
\Omega\sum_{i=1}^{N}
P_{i-1}\,X_i\,P_{i+1},
\qquad
P_i=\lvert\circ\rangle\langle\circ\rvert_i
=\frac{1-Z_i}{2},
\tag{2}
$$

其中 $X_i,Z_i$ 为格点 $i$ 上的 Pauli 算符（约定：$Z\lvert\bullet\rangle=+\lvert\bullet\rangle$，$Z\lvert\circ\rangle=-\lvert\circ\rangle$ 时与常见自旋记法一致，编码细节以实现为准）。算符含义是：仅当左右近邻均处于基态时，格点 $i$ 才允许翻转。

更一般的 Rydberg–Ising 型有效模型在投影前还含失谐与相互作用；PXP 是**无限近邻阻塞、仅保留投影驱动**的极限。本文若无特别说明，均取 $\Omega=1$ 作为能量单位。

### 2.3 对称性

PXP 在 PBC 下常见对称性包括：

| 对称性 | 作用 | 常用后果 |
|---|---|---|
| 平移 $T$ | 格点循环移位 | 动量 $k$ 好量子数 |
| 空间反演 $I$ | $i\mapsto N-i$ | 宇称 $p=\pm 1$ |
| 粒子–空穴型手征结构 | 存在 $C$ 使 $CHC=-H$（纯 PXP） | 谱关于 $E=0$ 对称；零能子空间需单独处理 |

解析疤痕塔时，常在 $\lvert\mathbb{Z}_2\rangle$ 有非零投影的对称性扇区中工作，例如 $k=0$、$p=+1$ [2]。

### 2.4 代表初态

周期-2 Néel 态（偶长度链）

$$
\lvert\mathbb{Z}_2\rangle
=
\lvert\bullet\circ\bullet\circ\cdots\bullet\circ\rangle
\tag{3}
$$

能量密度高，却与下文疤痕塔重叠显著，是实验与数值中的标准初态。对照初态可取约束空间内与塔重叠可忽略的随机合法积态。

---

## 3. 量子多体疤痕：定义与诊断

### 3.1 操作定义

设 $H\lvert E_n\rangle=E_n\lvert E_n\rangle$。称子集 $\{\lvert S_k\rangle\}_{k=0}^{M}$ 为**疤痕塔**（scar tower），若同时满足：

1. **稀疏性**：$M+1$ 远小于 $\dim\mathcal{H}$（PXP 中经验上 $M\sim N$）；
2. **非典型性**：在可比能量密度下，局域可观测量与纠缠相对典型本征态偏离 ETH 预期；
3. **与指定初态的大重叠**：对 $\lvert\psi_0\rangle=\lvert\mathbb{Z}_2\rangle$，
   $$
   \sum_{k=0}^{M}\lvert\langle S_k\lvert\psi_0\rangle\rvert^2
   \tag{4}
   $$
   保持有限且显著大于随机态的典型重叠尺度；
4. **近似等间距**：
   $$
   E_k \approx E_{\mathrm{ref}}+k\,\omega,
   \qquad k=0,1,\ldots,M,
   \tag{5}
   $$
   其中 $\omega$ 在有限尺寸下近似为常数。

主体谱仍可呈现能级排斥与 Wigner–Dyson 型 gap-ratio 统计，因此疤痕是**嵌在混沌谱中的稀疏结构**，不蕴含整体可积。

### 3.2 谱诊断：重叠–能量图

计算 $\lvert\langle E_n\lvert\mathbb{Z}_2\rangle\rvert^2$ 对 $E_n$ 作图。典型结果是：热背景上叠加一条 $\sim N+1$ 个峰组成的“梳状”结构，即疤痕塔。峰位中位间距给出 $\omega$。文献与本工作空间 ED 复现中，纯 PXP 有 $\omega\sim 1.33\,\Omega$ 量级 [2]。

### 3.3 动力学诊断：保真度复活

定义 Loschmidt 型保真度

$$
F(t)
=
\bigl\lvert\langle\psi_0\lvert e^{-iHt}\rvert\psi_0\rangle\bigr\rvert^2.
\tag{6}
$$

若 $\lvert\psi_0\rangle$ 主要支撑在严格等间距塔上，$E_k=E_{\mathrm{ref}}+k\omega$，则当

$$
T=\frac{2\pi}{\omega}
\tag{7}
$$

时 $F(T)=1$。间距仅近似时，$F(t)$ 在 $t\approx T,2T,\ldots$ 出现局部极大，且包络衰减。纯 PXP 中 $T\sim 4.7/\Omega$ 量级；本工作空间 $N=26$ ED 得到 $T_{\mathrm{rev}}\approx 4.80$、$F_{\mathrm{rev}}\approx 0.69$，与文献一致量级 [2]。

**负对照**：同约束空间内与塔重叠可忽略的初态不应呈现稳定周期高峰。缺少对照则无法排除数值或有限尺寸假象。

### 3.4 与相关概念的区分

| 概念 | 要点 |
|---|---|
| ETH / 强遍历 | 典型高能本征态局域地热；一般初态热化 |
| QMBS | 稀疏非典型本征态 + 特殊初态长时间相干 |
| MBL | 强无序下大量本征态局域；机制与干净 PXP 疤痕不同 |
| 可积系统 | 广泛守恒律；谱统计常近 Poisson；与“主体混沌 + 稀疏疤痕”不同 |

---

## 4. 等间距塔与周期动力学

仅保留塔分量时，

$$
\lvert\psi(t)\rangle
\approx
\sum_{k=0}^{M}
c_k\,e^{-iE_k t}\lvert S_k\rangle,
\qquad
c_k=\langle S_k\lvert\psi_0\rangle.
\tag{8}
$$

若式 (5) 严格成立，相位因子 $e^{-ik\omega t}$ 在 $t=2\pi/\omega$ 同步重聚，初态完全复活。近似等间距与塔外泄漏导致：

- 首峰 $F(T)<1$；
- 后续峰衰减；
- 有限尺寸下 $\omega$ 与 $T$ 随 $N$ 缓慢漂移。

前向散射近似（forward scattering approximation, FSA）将 $H$ 拆为升降部分 $H^\pm$，从 $\lvert\mathbb{Z}_2\rangle$ 迭代生成近似支撑疤痕子空间 $\mathcal{K}$ 的向量序列 [2]。PXP 中 $\mathcal{K}$ 上的代数结构仅近似闭合，故复活非完美。

---

## 5. 精确疤痕与近似疤痕

### 5.1 近似疤痕（纯 PXP）

纯 PXP 的 $\lvert\mathbb{Z}_2\rangle$ 动力学是近似疤痕的典范：存在清晰塔与周期复活，但 $F(T)$ 明显小于 1，且长时间衰减。主体 gap-ratio 随 $N$ 增大趋向 GOE 侧，支持“主体混沌 + 稀疏例外”的图像 [2]。

### 5.2 精确或近乎完美的构造

两类相关结果应区分：

1. **精确本征态构造**：在 Rydberg 阻塞链及相关模型中，可解析或半解析给出满足本征方程的特殊态 [5]。
2. **准局域变形增强复活**：Choi 等引入

$$
\delta H_R
=
-\sum_i\sum_{d=2}^{R}
h_d\,C X_i C\,(Z_{i-d}+Z_{i+d}),
\tag{9}
$$

并用 ansatz

$$
h_d
=
\frac{h_0}{\bigl(\varphi^{d-1}-\varphi^{-(d-1)}\bigr)^2},
\qquad
\varphi=\frac{1+\sqrt{5}}{2},
\tag{10}
$$

取 $R=N/2$、$h_0\approx 0.051$ 时，大尺寸上首峰保真度可接近 $1-10^{-6}$ 量级，而主体谱仍可保持热统计 [6]。单距离 $d=2$ 的解析优化值 $h_2=1/2-1/\sqrt{5}\approx 0.053$ 已显著提升复活 [6]。

本工作空间在 $N=18$、full Choi ansatz 下得到 $F_{\mathrm{pure}}\approx 0.776$、$F_{\mathrm{Choi}}\approx 0.988$（同一 $\lvert\mathbb{Z}_2\rangle$ 淬火），与“变形抑制泄漏、提高首峰”的结论一致；文献中 $F\approx 0.9998$ 的量级对应更大 $N$ 的报道，小尺寸不应强行等同。

**分类意义**：精确塔与近似塔在微扰下的寿命标度预期不同，比较 $\alpha$ 前必须固定对象。

---

## 6. 扰动下的稳健性

### 6.1 问题提法

设

$$
H(\lambda)=H_0+\lambda V,
\tag{11}
$$

其中 $H_0$ 为纯 PXP 或已变形模型。$\lambda=0$ 时存在疤痕塔与复活；$\lambda\neq 0$ 时塔被混合、等间距被破坏，复活衰减。由 $F(t)$ 提取特征时间 $\tau(\lambda)$（主诊断用保真度；纠缠熵对方向区分能力弱，不宜单独作为 $\alpha$ 的判别量），并拟合

$$
\tau(\lambda)\sim\lambda^{-\alpha}.
\tag{12}
$$

### 6.2 文献中的标度阵营（适用对象不同）

| 对象 | 代表性标度 | 参考文献 |
|---|---|---|
| 精确疤痕 + 一般局域扰动 | 下界型 $\tau\gtrsim\lambda^{-1/(1+d)}$（一维常与 $\alpha\sim 1$ 数值讨论相关） | Lin–Chandran–Motrunich, Phys. Rev. Research **2**, 033044 (2020) [7] |
| 近似疤痕 / 无 RSGA 保护 | 常出现 $\alpha\sim 2$ 型（二阶微扰 / Fermi 黄金规则型泄漏） | 例如 Mao–Sun–You, arXiv:2602.21962 [8] |

二者描述的是**不同设定**，不是对同一矩阵元的互斥实验预言。有意义的数值工作需先标明：塔为精确或近似；扰动是否保持相关对称性或 commutant 结构 [9]。

### 6.3 范围限制

有限尺寸 ED **不能**判定热力学极限下疤痕是否永久存活；可交付的是有限 $L$ 的 $\tau(\lambda,L)$、有效指数 $\alpha(L)$ 或局部 $\alpha(\lambda)$，以及分类表。外推 $L\to\infty$ 需单独论证，且文献已提示有限尺寸外推可能误导。

---

## 7. 数值方法要点（ED）

### 7.1 基组与检验

1. 枚举约束合法基，检验 $\dim=L_N$；
2. 构造稀疏 $H$（纯 PXP 或含 Choi 项）；
3. 按需投影到对称性扇区；
4. 全谱或 Krylov 时间演化：
   - 谱诊断：扇区内稠密对角化；
   - 淬火：$e^{-iHt}\lvert\psi_0\rangle$（如 `expm_multiply` 轨迹模式）。

### 7.2 易错点（与物理相关）

1. **宇称投影重复计数**导致扇区基不正交，能级统计失真；
2. **手征对称**使 $\pm E$ 同扇区并存，对全谱取近邻间距会人为压低 gap-ratio，应在单一手征半谱上统计并剔除零模；
3. **热对照窗口**若含 $t\to 0^+$，会把初始衰减误判为复活。

### 7.3 本工作空间锚点（供对照，非普遍定理）

| 量 | 设定 | 结果 |
|---|---|---|
| 约束维数 | $N=26$ PBC | $L_{26}=271443$ |
| 塔间距 | 纯 PXP，$k=0,p=+1$ | $\omega\approx 1.339$ |
| 复活 | 同上，$\lvert\mathbb{Z}_2\rangle$ | $T_{\mathrm{rev}}\approx 4.80$，$F_{\mathrm{rev}}\approx 0.693$ |
| Choi 首峰 | $N=18$，full ansatz | $F_{\mathrm{Choi}}\approx 0.988$ vs $F_{\mathrm{pure}}\approx 0.776$ |

代码与结果路径见 `tracks/ed/`；文献全文见 `notes/文献库/ED/`。

---

## 8. 结构提纲（机制层面，简述）

下列陈述概括主流理论语言，细节以原文献为准：

1. 硬约束改变了局域算符在位形图上的连通性；
2. FSA 生成近似不变子空间 $\mathcal{K}$；
3. $\mathcal{K}$ 上存在近似谱生成代数（近似 $\mathfrak{su}(2)$ / RSGA）；代数误差控制泄漏率，从而控制 $F(t)$ 包络；
4. 准局域变形可减小误差而不必使整体可积 [6]；
5. commutant 代数提供对称性保护子空间的分类语言，可用于标记扰动方向 [9]。

---

## 9. 结论

1. PXP 是 Rydberg 强阻塞极限的有效自旋模型，动力学定义在无相邻激发的约束空间上。
2. 量子多体疤痕是嵌在（可混沌的）多体谱中的稀疏非典型本征态塔，以与特定初态的大重叠及近似等间距为谱特征，以保真度周期复活为动力学特征。
3. 纯 PXP 给出近似疤痕；Choi 型变形可显著提高首峰保真度；精确构造与近似塔在扰动标度上不可混为一谈。
4. 扰动稳健性由 $\tau(\lambda)\sim\lambda^{-\alpha}$ 刻画，比较 $\alpha$ 前必须固定塔类型与扰动代数属性；有限尺寸结果不自动外推到热力学极限。

---

## 参考文献

1. M. Srednicki, *Chaos and quantum thermalization*, Phys. Rev. E **50**, 888 (1994); J. M. Deutsch, Phys. Rev. A **43**, 2046 (1991).
2. C. J. Turner, A. A. Michailidis, D. A. Abanin, M. Serbyn, and Z. Papić, *Weak ergodicity breaking from quantum many-body scars*, Nat. Phys. **14**, 745 (2018); arXiv:1711.03528.
3. 综述性讨论见例如 M. Serbyn, D. A. Abanin, and Z. Papić, *Quantum many-body scars and weak breaking of ergodicity*, Nat. Phys. **17**, 675 (2021) 及相关文献。
4. H. Bernien et al., *Probing many-body dynamics on a 51-atom quantum simulator*, Nature **551**, 579 (2017); arXiv:1707.04344.
5. C.-J. Lin and O. I. Motrunich, *Exact quantum many-body scar states in the Rydberg-blockaded atom chain*, Phys. Rev. Lett. **122**, 173401 (2019); arXiv:1810.00888.
6. S. Choi et al., *Emergent SU(2) dynamics and perfect quantum many-body scars*, Phys. Rev. Lett. **122**, 220603 (2019); arXiv:1812.05561.
7. C.-J. Lin, A. Chandran, and O. I. Motrunich, *Slow thermalization of exact quantum many-body scar states under perturbations*, Phys. Rev. Research **2**, 033044 (2020); arXiv:1910.07669.
8. M.-Y. Mao, Z. Sun, and W.-L. You, *Tighter thermalization bounds for perturbed quantum many-body scars*, arXiv:2602.21962 (2026).
9. S. Moudgalya and O. I. Motrunich, *Exhaustive characterization of quantum many-body scars using commutant algebras*, Phys. Rev. X **14**, 041069 (2024); arXiv:2209.03377.

---

## 附录 A. 符号表

| 符号 | 含义 |
|---|---|
| $N$ | 链长（格点数） |
| $\Omega$ | Rabi 频率（能量单位常取 1） |
| $P_i$ | 格点 $i$ 基态投影 |
| $\mathcal{H}_{\mathrm{cons}}$ | 阻塞约束空间 |
| $L_N$ | PBC 下约束空间维数（Lucas） |
| $\lvert\mathbb{Z}_2\rangle$ | 周期-2 初态 |
| $\omega$ | 疤痕塔能量间距 |
| $T$ | 复活周期 $\approx 2\pi/\omega$ |
| $F(t)$ | 初态保真度 |
| $\lambda,V$ | 扰动强度与算符 |
| $\tau,\alpha$ | 衰减时间与标度指数 |

## 附录 B. 相关本地路径

| 内容 | 路径 |
|---|---|
| 复现笔记与坑 | `tracks/ed/NOTES.md` |
| Track 3/4 任务报告 | `tracks/ed/TASK_REPORT_track3_4.md` |
| 纯 PXP ED | `tracks/ed/solutions/pxp_scars_ed.py` |
| Choi 锚点 | `tracks/ed/solutions/pxp_choi_anchor.py` |
| 文献 Markdown | `notes/文献库/ED/` |
| 本笔记 | `notes/Harnessing Quantum 2026/PXP模型与量子多体疤痕.md` |
