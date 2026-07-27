# Challenge #15 × CF-Flow：论文缺口与扩展设计

> 状态：研究设计草案，尚未进入实现。
> 日期：2026-07-27
> 目标：判断 arXiv:2512.00527 已覆盖 Challenge #15 的哪些部分，并给出可验证的扩展路线。
>
> 项目入口：[BOTS:848 Challenge #15](../README.md)；最低验收：[Benchmark v0](benchmark-v0.md)

Benchmark 决策：Challenge 的最低验收标准已经单独冻结为 [Benchmark v0](benchmark-v0.md)。后文的 N→∞、chirality 和 κ 扫描均为扩展项，不阻塞 Benchmark v0 通过。

## 1. 来源与版本

- Challenge #15：<https://github.com/QuantumBFS/quantum.harness/issues/15>
  - 标题：Symmetric neural-network ansatz for the chiral graviton in ν = 1/3 fractional quantum Hall state
  - 发布者：Lei Wang；Issue 页面显示为 accepted challenge。
  - 本笔记核对的是 2026-07-27 的页面快照。
- Mytraya Gattu, *Dressing composite fermions with artificial intelligence*, arXiv:2512.00527v1：<https://arxiv.org/abs/2512.00527>
  - v1 提交日期：2025-11-29；PDF 标注日期：2025-12-02。
  - 本次审阅依据：arXiv v1 PDF 全文（20 页）。
- S.-F. Liou, F. D. M. Haldane, K. Yang, E. H. Rezayi, *Chiral Gravitons in Fractional Quantum Hall Liquids*, arXiv:1904.12231 / PRL 123, 146801 (2019)：<https://arxiv.org/abs/1904.12231>
- Harness 初始审阅基线：`d2532921cc6779559658d85bc665c42d11012331`。
- 当前项目分支：`challenge/qmc-chiral-graviton`。

边界：2512.00527v1 的正文只说计算使用 JAX，没有给出伴随代码仓库。因此“复现 CF-Flow”目前意味着按论文重实现，除非作者另行提供代码。

## 2. 一句话结论

CF-Flow 已经提供了 Challenge 最难的对称性骨架，但论文没有计算 chiral graviton：它算的是 L=N 的远距离准粒子–准空穴输运隙，而 Challenge 要的是同一通量下最低 L=2 的长波中性模。最有价值的研究扩展是：把 CF-Flow 改造成严格 LLL、L=0/L=2 联合训练的 ansatz，再做五重简并、L²、热力学外推和手性谱权重；随后利用论文原本的 LL-mixing 能力研究 graviton 随 κ 的演化。

## 3. Challenge 的精确定义

固定设置：

- Haldane sphere；N 个完全极化电子；ν=1/3；2Q=3(N−1)。
- 最低 Landau level（LLL）中的 chord-distance Coulomb 相互作用。
- 基态：L=0。
- chiral graviton 候选：最低 L=2 中性激发。
- 目标量：Δ₂(N)=E₂(N)−E₀(N)，单位 e²/(εℓ_B)，带 Monte Carlo 统计误差。

验收还要求：

- 交换反对称性和 SO(3) 旋转等变性；
- ⟨L²⟩=L(L+1)=6（取 ħ=1）；
- M=−2,−1,0,1,2 五个分量能量简并；
- 随机旋转后的 irrep 变换检查；
- 强版本做 N→∞ 外推和/或 chiral metric operator 的 bright/dark 手性响应。

## 4. 论文真正做了什么

### 4.1 可直接继承的部分

1. **反对称性骨架**
   - 参考态 Ψ₀ 是 Jain/JK 投影的 CF determinant × Jastrow，已经是费米反对称波函数（Sec. III，Eqs. 8–12）。
   - 学到的 Jastrow 因子是 permutation-invariant，backflow coordinates 是 permutation-equivariant，所以 Eq. 21 的神经 dressing 不改变参考态的交换符号。

2. **球面对称性骨架**
   - backflow coordinate 被构造成 O(3)-equivariant；振幅与相位 Jastrow 由 SO(3)/O(3) invariants 构造（Sec. IV–V，Eqs. 21、27–31；Fig. 3）。
   - 论文明确声称 ansatz 被限制在参考 CF 波函数的单一总角动量 sector，并可从任意选定 angular-momentum sector 的 CF 波函数初始化（pp. 13–14）。

3. **L=2 参考态已经在形式上可构造**
   - Eq. 12 用 Clebsch–Gordan 系数组合 CF quasihole–quasiparticle configurations，构造确定 (L,M) 的 CF exciton。
   - 对 ν=1/3：Q*=(N−1)/2，L_QH=(N−1)/2，L_QP=(N+1)/2，耦合允许 L=1,…,N；把论文的 L=N 改成 L=2 就得到 Challenge 所需的自然 seed。

4. **可扩展训练经验**
   - κ、N、Q 被嵌入同一“foundation” ansatz；用 stochastic reconfiguration 和分阶段训练。
   - 模型约 5×10⁴ 参数；论文称单一 size 的计算在一张 A100 上少于两天。
   - ground-state 部分宣称可到约 26 个以上电子。

### 4.2 论文实际算的 observable

- ground states：ν=1/3、2/5 的 L=0，主要研究 κ∈[1,20] 的 Landau-level mixing。
- excited state：ν=1/3 的最大角动量 CF exciton，**L=N**。
- 论文的 gap 是

  Δ_tr(N,κ)=E(L=N;N,κ)−E(L=0;N,κ)，

  对应球面上最大分离的 quasiparticle–quasihole pair，即 transport gap。
- Fig. 6 的 excited-state sizes 是 N=6,7,8,12；对 Δ_tr 做了 1/N 外推。
- 这不是 Challenge 的

  Δ₂(N)=E(L=2;N,κ=0)−E(L=0;N,κ=0)。

## 5. 逐项对照矩阵

| Challenge 要求 | 2512.00527 是否完成 | 原文证据 | 仍缺什么 |
|---|---|---|---|
| Fermionic antisymmetry | 架构层面基本完成 | CF determinant/Jastrow；permutation-invariant dressing 与 equivariant backflow | 加显式 swap residual 数值测试 |
| SO(3) equivariance | 架构层面完成 | Eqs. 21、27–31；Fig. 3；单一 L sector 声明 | 按 Challenge 做随机旋转、D^(L)(R) 数值测试 |
| 严格 LLL | **未完成** | 论文研究完整 Hamiltonian H=ΣK_i/κ+V；generic backflow 允许 higher-LL dressing | 需要 exact LLL-closed ansatz/投影；有限小 κ 只能当近似路线 |
| L=0 ground state | 部分完成 | Fig. 4–5 | Challenge 要 κ=0、相同 flux 与 L=2 的联合误差控制 |
| 最低 L=2 state | **未算** | Eq. 12 能构造任意 (L,M)，但 Fig. 6 选 L=N | 改 seed 为 Ψ_CF^(2,M)，优化最低 L=2 |
| Δ₂=E₂−E₀ | **未算** | 论文只给 Δ_tr | 需要同一 variational family/state-averaged 训练与误差传播 |
| ⟨L²⟩=6 | **未报告** | 只用“restricted to one sector”的构造论证 | 显式估计 ⟨L²⟩ 与 Var(L²) |
| 5-fold multiplet | **未报告** | 未展示 M=−2,…,2 | 从一个共享 reduced state 生成五个 M 并比较能量 |
| small-N ED cross-check | 仅对 L=N transport gap 做过 N=6 LLL ED 对比 | Fig. 6 | 对 L=0/2 做 N=6–10 的逐项 ED 对比 |
| beyond ED + N→∞ | transport gap 做过；L=2 没做 | Fig. 6 | NQS 做 N≥12，并外推 Δ₂∞ |
| helicity/chirality | **未做** | paper 的 inversion-odd phase 不是 graviton helicity measurement | 计算 O_±/rank-2 chiral metric spectral weights |
| L=0/L=2 单网络联合表示 | **未展示** | “single ansatz”指跨 κ、N、Q 且固定 sector | shared trunk + L-specific irrep head/state-averaged VMC |

## 6. 两个不能忽略的技术缺口

### 6.1 “正确 monopole sector”不等于“严格 LLL”

CF-Flow 的 Aharonov–Bohm phase 和 equivariant backflow 保证正确 monopole charge Q，避免 Dirac string 造成的发散；但 generic backflow 和 non-holomorphic distance features仍会产生 higher-LL components。论文正是为了研究 LL mixing 才允许这种 dressing。

因此：

- 直接把 κ 设成很小并不自动满足 Challenge 的“LLL ansatz”；
- 若用小 κ 路线，必须报告 cyclotron occupation/kinetic leakage 并做 κ→0 外推，而且最终仍可能不被视为严格验收；
- 强版本应让每个电子坐标始终处在固定 2Q 次齐次 holomorphic spinor polynomial 空间，或改用本身就是 LLL Fock-space 的表示。

### 6.2 固定短距离零点会影响高精度 gap

Appendix A 指出：smooth analytic CF-Flow 不能改变两电子相遇时的零点阶数。ν=1/3 Laughlin ground seed 固定 M=3，但精确 Coulomb ground state 含很小的 M=1 成分；论文认为该误差低于当前能量噪声。

对 Δ₂ 而言，ground 和 excited state 的系统误差相减，不保证像总能量那样无害。应考虑：

- multi-reference L=0 ansatz（Laughlin + L=0 projected CF exciton/multi-exciton）；
- 允许 M=1 channel 的 LLL-closed basis mixing；
- 用 energy-variance extrapolation 检查两态的 variational bias 是否对称。

## 7. 三条扩展路线

### 路线 A：Challenge MVP——直接把 CF-Flow 从 L=N 改到 L=2

动作：

1. 用 Eq. 12 构造 Ψ_CF^(2,M)；ground 使用 Ψ_CF^(0,0)。
2. 共享 symmetry-preserving dressing trunk，联合最小化 E₀ 与五个 E₂M。
3. N=6、8 先和 ED 对照；给 Δ₂、统计误差、L²、五重简并、旋转与换粒子测试。

优点：最贴近论文，最快得到 Challenge 的核心结果。

风险：原始 backflow 不严格封闭在 LLL；若只以 finite κ 或 kinetic penalty 实现，必须明确这是近似 MVP，不应宣称已经完成严格 LLL 版本。

### 路线 B：强研究版——LLL-exact、state-averaged equivariant NQS（推荐）

核心设计：

- Hilbert space 从一开始就是固定 Q 的 LLL：
  - 方案 B1：SU(2)-equivariant occupation-basis NQS，fermionic Fock basis 自动处理反对称性；
  - 方案 B2：由 JK-projected CF configurations 构成的 LLL-closed multi-reference ansatz，神经网络参数化截断 CF basis 的系数；
  - 方案 B3：给 generic real-space NQS 加 exact LLL + L group projector（表达力最强，但投影成本最高）。
- shared trunk 表示共同 correlations；L=0 与 L=2 只通过 irrep/reference head 区分。
- loss 可取：

  ℒ = w₀E₀ + w₂(1/5)Σ_{M=−2}^{2}E₂M，

  L 不同使 0/2 态按对称性自动正交，不需要人工 overlap penalty。

优点：完全匹配 Challenge，方法本身有发表价值。

风险：这是主要架构研发工作；先在 N=6 做 exact-LLL closure 和 SU(2) transformation 单元测试，再决定 B1/B2/B3，避免大规模训练后才发现投影不可用。

### 路线 C：最自然的论文物理扩展——LL mixing 下的 chiral graviton

在完成 κ=0 Challenge 后，利用 CF-Flow 原本的优势研究：

- Δ₂(N,κ)=E(L=2)−E(L=0)；
- graviton spectral weight W_±(κ)；
- chirality polarization C(κ)；
- L=2 mode 是否在论文提出的 first-order transition 前失去谱权重或并入 continuum；
- 与 Δ_tr(L=N,κ) 的不同演化。

这条线把 Challenge 和 2512.00527 真正连接起来：论文已知的是 transport gap 随 κ 指数衰减到有限值，未知的是 long-wavelength geometric mode 是否表现出相同尺度和相变信号。

## 8. 手性应该怎样测，而不是怎样“猜”

L=2 只证明 spin magnitude 为 2，不证明 helicity sign。

Liou et al. 定义 rank-2 chiral metric operators

O_∓^(2)=Σ_q (q_x ∓ i q_y)² V_q exp(−q²ℓ²/2) ρ̄_qρ̄_−q，

以及 spectral function

I_σ(ω)=Σ_n |⟨n|O_σ|0⟩|² δ(ω−ω_n)。

对目标态可报告：

- W_±=|⟨Ψ₂|O_±|Ψ₀⟩|²；
- C=(W_−−W_+)/(W_−+W_+)；
- 完整或 Lanczos/VMC 近似的 I_±(ω)。

约定必须写清：在 Liou et al. 的 convention 中 O_− 创建 angular momentum −2 的 graviton。对 model Laughlin state，O_+ annihilates ground state；对 Coulomb ground state，I_+ 不严格为零，但相对 I_− 强烈压低。因此验收应使用 weight ratio/polarization，而不是仅凭 L=2 标签宣布“−2 chirality”。

## 9. 验证矩阵与数值门槛

| 检查 | 建议实现 | 通过标准 |
|---|---|---|
| 交换反对称 | 随机交换 i,j，比较 Ψ(P_ijΩ)/Ψ(Ω) | 接近 −1；float64 单元测试 residual 约 1e−10 或更小 |
| L=0 旋转 | 随机 R∈SO(3) | Ψ₀(RΩ)=Ψ₀(Ω)（含统一 gauge convention） |
| L=2 等变 | 同时评估五分量 | Ψ₂M(RΩ)=Σ_M′D^(2)_MM′(R)Ψ₂M′(Ω) |
| LLL closure | holomorphic degree/Fock-basis检查，或 LL occupation | 强版本 identically zero leakage；近似版必须随 κ→0 收敛 |
| L² | local estimator 或 group/Casimir action | ⟨L²⟩=6 within error，且 Var(L²)≈0 |
| 五重简并 | 共享参数评估五个 M | max E₂M−min E₂M 小于约 2σ_combined |
| ED | N=6–10 的 E₀、E₂、Δ₂、W_± | VMC 能量是上界；gap 与 ED 在声明的误差预算内 |
| MC 误差 | 多链、blocking/τ_int、独立 seeds、bootstrap | 报告 effective sample size 和 σ_Δ，不只报 sample std |
| variational bias | local-energy variance + 多容量/多 seed | Δ₂ 对容量稳定；必要时做 E vs variance 外推 |
| thermodynamic | N≥12 的若干点 | 比较 Δ∞+a/N 与 Δ∞+a/N+b/N²，报告模型选择系统误差 |

注意：五个 M 不应分别训练五套无关网络。应从同一个 reduced L=2 state 通过 CG/ladder 或 irrep head 生成；否则“劈裂”混合了优化噪声和真正的等变性误差。

## 10. 推荐执行顺序

### Gate 0：定义与 ED 基线

- 固定 Hamiltonian、背景电荷、sphere density correction、能量单位和 operator convention。
- 用 ED 得到 N=6、7、8（资源允许再到 9/10）的 E₀、E₂、Δ₂、L²、W_±。
- 这一步决定后续 NQS 是否真的命中“最低 L=2”，而非错误的 CF exciton branch。

### Gate 1：L=2 symmetry plumbing

- 实现 Eq. 12 的 L=2、M=−2,…,2 seed。
- 先不训练，完成 swap、rotation、L²、五重能量的一致性测试。

### Gate 2：state-averaged VMC

- shared trunk + L-specific head；联合优化 L=0 和 L=2。
- small N 对 ED；比较 separate training 与 state-averaged gap 的误差和 bias。

### Gate 3：严格 LLL 判定

- 如果 direct CF-Flow 有不可忽略 higher-LL leakage，就停止把它当 Challenge final ansatz，切换到 B1/B2/B3。
- 只有 exact closure 或有说服力的 κ→0 limit 才进入正式结果表。

### Gate 4：beyond ED 与外推

- 目标 sizes：N=12、14、16、20，按实际 GPU 成本调整。
- 每个 N 至少多 seed；联合做 MC error、optimizer spread、finite-size fit uncertainty。

### Gate 5：chirality 与 LL-mixing 扩展

- 先做 κ=0 的 W_±/C；再扫 κ，连接论文的 transport-gap 结果。

## 11. 预期论文/Challenge 贡献表述

最小可交付：

> We extend the symmetry-preserving CF-Flow construction from the maximally separated L=N CF exciton to the long-wavelength L=2 sector at ν=1/3, and certify the spin-2 multiplet through L² and SO(3) covariance tests.

强版本：

> We introduce an LLL-exact, state-averaged SO(3)-equivariant neural ansatz for the L=0 Laughlin ground state and L=2 graviton, obtain Δ₂ beyond ED sizes, and resolve its helicity through chiral metric spectral weights.

自然后续：

> We track the chiral graviton gap and spectral weight through Landau-level mixing and compare the long-wavelength geometric mode with the transport gap, testing whether the graviton supplies an earlier signature of the LL-mixing-driven transition.

## 12. 当前推荐

当前执行边界改为“先通过 Benchmark v0，再选择研究扩展”：

1. v0 只要求 N=6、严格 LLL、L=0/L=2 energies、误差条、L²、五重简并、对称性实测、ED 对照和可复现交付；
2. Eq. 12 → L=2 与五分量 symmetry plumbing 是 v0 的核心实现；
3. larger N、chirality 和 κ 扫描作为 benchmark 通过后的独立扩展，不混入最低验收判断。

当前不建议直接大规模复现 Fig. 6：它验证的是 L=N transport gap，而且原文未给代码；先做 small-N ED + L=2 seed 的可行性门控，能更快暴露规范、LLL 和角动量构造错误。


