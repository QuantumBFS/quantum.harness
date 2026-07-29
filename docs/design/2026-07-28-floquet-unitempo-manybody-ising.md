# Floquet-uniTEMPO 推广到多体：驱动斜场 Ising 链 + 边界热库的设计方案

日期：2026-07-28
状态：设计讨论稿（未实现）
前置文档：`docs/uniTEMPO-vs-PT-TEBD-comparison.md`（路线 A/B/C 可行性分析）、`tracks/mps/results/20260727-195949-mickiewicz2026-fig2/`（单自旋 Floquet-IF 已验证实现）

---

## 1. 问题设定

### 1.1 哈密顿量

一维倾斜场 Ising 链，$N$ 个自旋 $1/2$，横场受周期驱动：

$$
H_{\rm sys}(t) = \sum_{i=1}^{N-1} J\, \sigma_z^i \sigma_z^{i+1} + \sum_{i=1}^N \left[ h_z(t)\, \sigma_z^i + h_x\, \sigma_x^i \right]
$$

$$
h_z(t) = h_z + A\cos(\omega_d t)
$$

链的**左端点**（$i=1$）耦合一个玻色热库：

$$
H_{SB} = \sigma_z^1 \otimes B, \qquad B = \sum_k g_k\,(b_k + b_k^\dagger)
$$

$$
J(\omega) = \alpha\, \omega\, e^{-\omega/\omega_c}, \qquad T = 0
$$

零温 Ohmic 浴的浴关联函数（bcf）有闭式：

$$
\eta(t) = \langle B(t) B(0) \rangle = \frac{\alpha\, \omega_c^2}{(1 + i\omega_c t)^2}
$$

初态取系统-浴因子化：$\rho_{\rm tot}(0) = \rho_0 \otimes \rho_B^{\rm th}$，$\rho_0$ 为系统的纯态积态（如 $|{\uparrow_z\cdots\uparrow_z}\rangle$）。

### 1.2 为什么选"边界浴"而不是"共浴"

这是整个方案成立的支点。影响泛函（IF）只对**耦合算符所在格点**的路径敏感。边界耦合时 IF 只依赖站点 1 的 Liouville 路径 $\{\mu_k^1\}$，因此：

1. **IF 与单杂质情形严格相同**——不多不少，就是 Mickiewicz 复刻中已验证的那个均匀张量 $f$（同一浴、同一 $\delta t$、同一 $S = \sigma_z$）；
2. **IF 完全不知道驱动的存在，也不知道链的存在**。$f$ 只依赖 $(S, \eta(t), \delta t)$。驱动只出现在系统侧的 Trotter 门里，相互作用只出现在空间 MPS 的门里；
3. 记忆方向的键维 $\chi_b$ 就是单自旋验证过的值（我们的参数点 $\chi_b = 41$），**与 $N$ 无关、与 $\omega_d$ 无关**。共浴情形（路线 B）的"记忆跨越多个驱动周期导致 $\chi$ 爆炸"的担心在这里不存在——它是对**观测量和稳态纠缠**的担心，不是对 IF 构造的担心。

代价：物理上边界浴描述的是"链的一端接热库"（boundary-driven 输运几何），而非集体退相干。这恰好是频率分辨热流 $\bar j(\omega)$ 这个 challenge 核心观测量的自然几何——热流从浴流进链，穿过键 $(1,2)$ 进入体内。

---

## 2. 数学结构

### 2.1 路径积分与 IF 因子化

在 Liouville 空间做 Suzuki–Trotter 分解，时间步长 $\delta t$。每个格点每个时间步携带一个 Liouville 指标 $\mu_k^i \in \{1,\dots,4\}$（等价于 $(s, s')$，$s, s' \in \{\uparrow_z, \downarrow_z\}$）。$K$ 步后的约化密度矩阵：

$$
\rho_K(\vec\mu_K) = \sum_{\vec\mu_1, \dots, \vec\mu_{K-1}} \left[ \prod_{k=1}^{K} \mathcal U_k(\vec\mu_{k-1} \to \vec\mu_k) \right] F_K(\mu_1^1, \dots, \mu_K^1)
$$

其中 $\mathcal U_k$ 是系统侧的 Liouville 门（含驱动，含 Ising 相互作用，不含浴），而浴的全部影响收进 $F_K$——它**只依赖站点 1 的指标序列**。

### 2.2 uniTEMPO 的均匀 IF

uniTEMPO（Link24）把 $F_K$ 写成时间方向平移不变的 MPO：

$$
F_K(\mu_1^1, \dots, \mu_K^1) = v_l^T\, f^{\mu_1^1} f^{\mu_2^1} \cdots f^{\mu_K^1}\, v_r
$$

- $f^\mu$：4 个 $\chi_b \times \chi_b$ 矩阵（$\mu = (s,s')$ 取 4 个值），由 iTEBD 收缩无限 IF 网络得到，与 $K$ 无关；
- $v_l, v_r$：左右边界矢量（$\chi_b$ 维）；
- 我们的验证参数点：$\delta t = \pi/60$，SVD tol $= 10^{-7}$，自动记忆深度 $n_c = 1024$（记忆时间 $\approx 54/\Omega$），$\chi_b = 41$。

**关键效率来源**：对任意时长、任意 $N$、任意驱动波形，$f$ 只算一次（我们的复刻中收缩耗时 31 s）。

### 2.3 短时传播子 $Q$

uniTEMPO 论文给出的半群形式，把"系统局域演化 + 记忆推进一步"合并成一个超算符：

$$
Q(\nu; n)(\lambda; i) = \sum_{\mu} f^{\mu}_{in}\, U^{\lambda\mu\nu}
$$

$$
U^{\lambda\mu\nu} = \langle \lambda |\, u \otimes u^*\, | \mu \rangle, \qquad u = e^{-i\delta t\, h_1(t_k)}
$$

这里 $h_1(t_k)$ 是站点 1 的**单体**含时项（横场、纵场、驱动）；$(\lambda, i)$ 是输入（系统 Liouville 指标、记忆指标），$(\nu, n)$ 是输出。注意 $Q$ 里**不含** Ising 键 $(1,2)$——键相互作用作为分离的两体门处理（见 §3.3 的 Trotter 排序）。

### 2.4 增广 MPS 表示

联合态 = 系统的密度矩阵 MPO（空间 MPS，Liouville 物理指标维数 $d_L = 4$）在站点 1 多挂一条记忆腿 $m \in \{1, \dots, \chi_b\}$：

$$
\Psi_K(\mu^1, \dots, \mu^N; m) = \sum_{a_1, \dots, a_{N-1}} B^{\mu^1}_{m, a_1}\, A^{[2]\mu^2}_{a_1, a_2} \cdots A^{[N]\mu^N}_{a_{N-1}}
$$

```
        memory m (χ_b)
         │
         B^{μ¹} ──a₁── A^{μ²} ──a₂── A^{μ³} ── ... ── A^{μᴺ}
         │              │              │                  │
         μ¹             μ²             μ³                 μᴺ      (d_L = 4 each)
```

- 体部张量 $A^{[i]}$：常规 MPO-MPS 张量，空间键维 $\chi_s$；
- 边界张量 $B$：双腿（记忆 $m$、空间 $a_1$），是"系统 ⊗ 浴记忆"的接口；
- 初态：$\Psi_0 = \rho_0 \otimes v_r$，即 $B^{\mu^1}_{m, 1} = (v_r)_m\, \rho_0^{(1)}(\mu^1)$，体部为 $\rho_0$ 的平凡 MPO（积态，$\chi_s = 1$）。

### 2.5 测量（cap）

任意时刻的系统约化密度矩阵 = 用左边界矢量封掉记忆腿：

$$
\rho_K(\mu^1, \dots, \mu^N) = \sum_m (v_l)_m\, \Psi_K(\mu^1, \dots, \mu^N; m)
$$

封口后是标准的 $N$ 站点 MPO，期望值 $\langle O \rangle = \mathrm{tr}(O\rho)$ 用常规 MPO 收缩。健康检查：$\mathrm{tr}\,\rho_K = 1$（机器精度量级漂移即报警）。

---

## 3. 时间步算法

### 3.1 Strang 分裂

把一步 $\delta t$ 的生元分成两组：

- 组 $\mathcal A$：各站点单体项（含驱动）+ 边界浴步 $Q$；
- 组 $\mathcal B$：全部 Ising 键 $J\sigma_z^i\sigma_z^{i+1}$ 的两体 Liouville 门。

二阶 Strang：

$$
\Psi_{k+1} = e^{\mathcal A \delta t/2}\, e^{\mathcal B \delta t}\, e^{\mathcal A \delta t/2}\, \Psi_k + O(\delta t^3)
$$

全局误差 $O(\delta t^2)$，与单自旋验证所用阶数一致（那里 $\delta t = \pi/60$ 已验证）。

### 3.2 单步细化

1. **$\mathcal A$ 半步**：
   - 站点 $i \ge 2$：单体门 $u_i = \exp(-i\frac{\delta t}{2} h_i(t_k))$，Liouville 形式 $u_i \otimes u_i^*$ 逐点作用（bond 维不变）；
   - 站点 1：半个 $Q$ 步（见下方说明）。
2. **$\mathcal B$ 全步**：所有键的两体门。$u_{\rm bond} = \exp(-i\delta t\, J \sigma_z \otimes \sigma_z)$（$4\times4$），Liouville 门 $u_{\rm bond} \otimes u_{\rm bond}^*$（$16 \times 16$）。奇/偶键可交换，分两层作用；每次作用后对空间键做 SVD 截断到 $\chi_s$（cutoff $10^{-10}$ 起步）。**键 $(1,2)$ 的门作用在 $B$ 与 $A^{[2]}$ 上，记忆腿 $m$ 留在 $B$ 侧不参与 SVD 截断对象**——截断的是 $(m, \mu^1)$ 合并腿 vs 其余，或等价地把 $m$ 当站点 1 的"额外物理指标"。
3. **$\mathcal A$ 半步**：同 1，时间取 $t_{k+1/2}$ 或按 Strang 对称取值。

**边界浴步**（$Q$ 作用在 $B$ 上）：

$$
B'^{\nu}_{n, a} = \sum_{\lambda, \mu, i} Q(\nu; n)(\lambda; i)\, B^{\lambda}_{i, a}
= \sum_{\lambda, \mu, i} f^{\mu}_{in}\, U^{\lambda\mu\nu}\, B^{\lambda}_{i, a}
$$

实现上拆成两个缩并（避免显式构造 $Q$）：

1. 系统侧：$\tilde B^{\nu}_{\mu, a} = \sum_\lambda U^{\lambda\mu\nu} B^{\lambda}_{\cdot, a}$（这里 $B$ 的记忆腿先视作索引 $\mu$ 的同伴——即把 $B^{\lambda}_{i,a}$ 看作 $(\lambda, i, a)$ 三指标张量，$U$ 作用 $\lambda$）；
2. 记忆侧：$B'^{\nu}_{n, a} = \sum_{\mu, i} f^{\mu}_{in}\, \tilde B'^{\nu}_{\mu(i), a}$——按 $\mu = (s,s')$ 分组做 4 次 $\chi_b \times \chi_b$ 矩阵乘。

**半步 $Q$**：$\mathcal A$ 组里的浴步需要和单体项平分。最干净的做法是把 $Q$ 的定义改为 $u = \exp(-i\frac{\delta t}{2} h_1)$ 的半步版本（$f$ 不变——IF 的 $\delta t$ 是离散化步长，不能对半劈），即**浴记忆推进仍是整步，只有系统单体幺正部分取半步**。这是与标准 TEMPO 实践一致的折中；一阶精度损失局限在单体项与浴的对易子上，仍属 $O(\delta t^2)$ 家族。实现时两个方案都写出来，用 $N=1$ 极限（§5 M0）仲裁。

**记忆腿不增长**：因为 $f$ 是收敛的均匀张量，$B' $ 的记忆腿仍是 $\chi_b$ 维——与 PT-TEMPO 每步增长再截断不同，这里**记忆键维全程恒定**，没有任何截断决策。这是 uniTEMPO 嫁接的最大红利。

### 3.3 周期结构与 Floquet 稳态

驱动周期 $T_d = 2\pi/\omega_d$ 含 $M = T_d / \delta t$ 个时间步（选 $\delta t$ 使 $M$ 为整数；$\delta t = \pi/60$ 时 $\omega_d = 2.5$ 给 $M = 48$，$\omega_d = 10$ 给 $M = 12$）。单周期传播子

$$
\mathcal T = \prod_{k=1}^{M} \mathcal U(t_k)
$$

是**时间无关**的线性映射（作用在增广 MPS 上）。频闪稳态：

$$
\Psi_\star = \lim_{p \to \infty} \mathcal T^p\, \Psi_0
$$

两档实现：

1. **幂迭代**：直接反复作用 $\mathcal T$，每步正常截断，监控 $\lVert \Psi_{p+1} - \Psi_p \rVert$ 与观测量的周期收敛。朴素但稳，且顺路拿到暂态曲线；
2. **KrylovKit `eigsolve`**：把增广 MPS 当抽象向量（定义加法和内积），对线性映射 $\mathcal T$ 求主本征对。顺便拿**次主本征值 → Floquet 弛豫谱**（弛豫率、渐近衰减时间），这是幂迭代给不了的物理。难点：MPS 的规范自由度使"内积"不直接对应 Hilbert–Schmidt 范数，先把 MPS 拉到 canonical form 再做。

---

## 4. 观测量

| 观测量                                        | 定义                                          | 物理                          |
| ------------------------------------------ | ------------------------------------------- | --------------------------- |
| 能量密度剖面                                     | $\langle h_i \rangle$，$h_i$ 为键/点能量算符        | 浴冷却 vs 驱动加热的空间分布            |
| 边界热流                                       | $\hat j_{1,2} = i[h_1, h_2]$ 的期望值（键能流）      | challenge 核心量的时域版           |
| 频闪稳态热流 $j(\omega_d)$                       | 稳态下 $\langle \hat j_{1,2} \rangle$ 对驱动频率的扫描 | 多体共振：$n\omega_d$ 匹配链内激发时流增强 |
| $\langle \sigma_z^i \sigma_z^j \rangle$、磁化 | 常规 MPO 收缩                                   | 序参量、关联长度                    |
| 频率分辨热流 $\bar j(\omega)$                    | 双时关联的 Fourier 变换                            | challenge 的正餐，见 §7 二期       |

热流算符的显式形式附录B

---

## 5. 实现方案

### 5.1 技术栈（Julia，复用 `tracks/mps/env_floquet/`）

| 组件                      | 选择                        | 理由                                                                                                                                                                                                             |
| ----------------------- | ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| IF 均匀张量 $f$、$v_l$、$v_r$ | **UniformTEMPO.jl**（已装）   | 同一 $(S, \eta, \delta t, \mathrm{tol})$ 下 $f$ 与单自旋验证完全一致。**首个编码任务：从 `uniTEMPO()` 返回的 process-tensor 对象里把 $f^\mu$、$v_l$、$v_r$ 挖出来**（其公开 API `evolve` 是单自旋专用，需读源码确认内部存储格式；挖不出来就按 Link24 自己重写 iTEBD 收缩，工作量约 200 行） |
| 空间 MPO-MPS、两体门、SVD      | **ITensorMPS.jl**         | harness 已有 `/using-itensors` 技能；`siteind` 用 4 维 Liouville 指标；`apply` 加 `maxdim/cutoff` 即 TEBD                                                                                                                  |
| 周期映射本征求解                | **KrylovKit.jl**          | 抽象向量接口，适合 MPS                                                                                                                                                                                                  |
| 对照工具                    | XDiag.jl（封闭系统 ED）、现有单自旋脚本 | 验证                                                                                                                                                                                                             |

### 5.2 数据结构

```julia
struct AugmentedMPS
    B::ITensor        # 边界张量: (μ¹, m, a₁)
    bulk::MPS         # 站点 2..N: (μⁱ, a_{i-1}, a_i)
    vl::Vector{ComplexF64}   # 记忆左边界 (cap)
    # vr 只在初始化用
end

struct UniformIF
    f::NTuple{4, Matrix{ComplexF64}}  # f^μ, μ=(↑↑, ↑↓, ↓↑, ↓↓)
    vl::Vector{ComplexF64}
    vr::Vector{ComplexF64}
    χb::Int
end
```

### 5.3 伪代码

```julia
# 一次性
if_  = build_if(S=σz, δt=π/60, bcf=ohmic_T0(α, ωc), tol=1e-7)   # → f, vl, vr (χ_b=41)
Ψ    = init_augmented(ρ0, if_.vr)                                # χ_s = 1 积态

M    = round(Int, 2π/(ωd*δt))
for period in 1:P
    for k in 1:M
        t = k*δt
        apply_onsite_half!(Ψ, t)          # 单体门, i≥2
        bath_step!(Ψ.B, if_.f, u_half(h1(t)))   # §3.2 边界 Q 半步
        apply_bonds!(Ψ, J; maxdim=χs, cutoff=1e-10)   # 奇层+偶层, SVD 截断
        apply_onsite_half!(Ψ, t + δt/2)
        bath_step!(Ψ.B, if_.f, u_half(h1(t + δt/2)))
    end
    if period % check_every == 0
        ρ = cap(Ψ, if_.vl)
        record(observables(ρ));  check_trace(ρ)
    end
end
```

### 5.4 复杂度

| 项             | 每步成本                                                          | 备注                      |
| ------------- | ------------------------------------------------------------- | ----------------------- |
| 两体门（$N-1$ 个键） | $O(N\, \chi_s^2\, d_L^3)$，$d_L = 4$                           | 与标准 TEBD 相同             |
| 边界浴步          | $O(4\, \chi_b^2\, \chi_s\, d_L + 16\, \chi_b\, \chi_s\, d_L)$ | $\chi_b = 41$ 恒定，不随时间增长 |
| 存储            | $O(N\, \chi_s^2\, d_L) + O(\chi_b\, \chi_s\, d_L)$            | 边界张量是唯一带 $\chi_b$ 的项    |
| 一周期           | $M \times$ 上两行                                                | $M = 12$–$48$           |

对照 Fux23：那里的记忆键维 $\xi$ 以**乘积** $\eta \le \chi_s \xi$ 进入所有空间键；这里记忆腿只挂在边界张量上，空间键从不承载 $\chi_b$。这是"边界浴 + uniTEMPO"组合相对 PT-TEMPO 嫁接的结构性优势。

---

## 6. 风险与开放问题

1. **$\chi_s$ 的暂态增长（首要风险）**。驱动链加热，算符空间纠缠在暂态可能快速增长；好在目标稳态本身往往低纠缠（非积分链驱动至无穷温：$\rho_\star \propto \mathbb 1$，MPO 键维 1；边界 $T=0$ 浴 + 驱动竞争出的非热稳态预期也是有限关联长度）。策略：幂迭代直达稳态，暂态 $\chi_s$ 扫 64/128/256 看收敛；若暂态不可行，改 KrylovKit 直接狙稳态本征矢。
2. **Liouville 门非幺正**。截断误差控制不如纯态 TEBD 干净。监控：每周期检查 $\mathrm{tr}\,\rho$、$\chi_s$ 截断权重累计、以及 §7 M1 的对照点。
3. **半步 $Q$ 的约定**（§3.2）是个真正的实现决策，$N=1$ 仲裁。
4. **加热 vs 可观测窗口**。非积分模型在边界 $T=0$ 浴下稳态非平凡（冷却-加热平衡），这正是要研究的物理；但也意味着稳态 $\rho_\star$ 的纠缠结构事先未知，$\chi_s$ 需求只能数值回答——这本身就是 Tier 2 要产出的标度数据。
5. **本征映射的规范问题**（§3.3 档 2）：Krylov 方法需要定义良好的内积；MPS 先 canonicalize。若卡住，退回幂迭代 + 对 $\mathcal T - \mathbb 1$ 做 inverse iteration。

---

## 7. 里程碑（Tier 2 内部拆分）

| 里程碑                    | 内容                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | 通过判据                                                                                                                                             |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **M0** 接线验证            | $N=1$：从 UniformTEMPO.jl 挖出 $(f, v_l, v_r)$，走增广 MPS 全流程                                                                                                                                                                                                                                                                                                                                                                                                                         | 曲线与已验证的图 2 exact 逐点一致（max $\lvert\Delta\rvert \lesssim 10^{-6}$，同算法应到机器精度差异）                                                                     |
| **M1** 极限对照            | (a) $\alpha = 0$ 封闭链 vs XDiag ED（$N \le 16$）；(b) $J = 0$ 有浴、$h_z = 0$、$h_x = 0.5$、$A = 1$（恰为论文的 $\frac{\Omega}{2}\sigma_x + \epsilon_d\cos(\omega_d t)\sigma_z$，$\Omega = \epsilon_d = 1$）、$\alpha = 0.05$、$\omega_c = 2.5$：**只算站点 1 的 $\langle\sigma_z(t)\rangle$**，直接与 Mickiewicz et al. (PRL 136, 200201) 图 2 的已验证数据对照（`tracks/mps/results/20260727-195949-mickiewicz2026-fig2/` 下 `ours_omega_d_2.5.csv` / `ours_omega_d_10.csv` 及 Zenodo CSV，$\omega_d = 2.5$ 与 $10$ 两个点） | (a) ED 级一致；(b) max $\lvert\Delta\rvert \lesssim 10^{-6}$（与 M0 同算法，理应到机器精度）                                                                       |
| **M2** 冷却验证            | 无驱动、弱 $\alpha$、$T=0$ 边界浴：长时稳态应逼近链基态                                                                                                                                                                                                                                                                                                                                                                                                                                            | $\langle H_{\rm sys} \rangle_\star \to E_0^{\rm DMRG} + O(\alpha)$ 修正；给出 $\alpha$ 依赖                                                             |
| **M3** 高频 Redfield 一致性 | 驱动开启，取**高频** $\omega_d = 20\, h_x$：沿用 M1(b) 的单位制 $h_x = 0.5$、$A = 1$，即 $\omega_d = 10$（恰为论文图 2 右板的快驱动点，$N=1$ 极限已由该板验证 RM 到 $1.2\times10^{-5}$），$J$ 取 $0.5$ 量级；对同一 $N$（先 $N = 2, 3$，再 $N$ 到 Redfield 窗口上限 6），把增广 MPS 的暂态曲线与稳态同 `2026-07-28-redfield-benchmark-manybody-ising.md` 的 Liouvillian 结果对照                                                                                                                                                                             | 偏差落在 Redfield 自身误差预算内：$O(\alpha)$（Born 二阶）+ $O(A^2/\omega_d^2) \sim 10^{-2}$（Magnus 截断，可通过加密到 $\omega_d = 40\, h_x$ 再降一档）；不一致则说明增广 MPS 实现有误或截断不足 |
| **M4a** 图 3 复刻（单自旋）    | ✅ 完成（2026-07-29）：附录 B 协议（NESS 暂态 + M 个 t' 起点 S 左乘插入 + 复数双时关联 + 数值积分），六组参数对照 Zenodo：谱形 L2（ω≤10）0.15%–11%、主峰位置全对、δ 峰权重 c_1≈0.098–0.139；能量平衡 Ī=P̄ <1%、图 5 总流 <5%。结果 `results/20260729-augmps-m4a/`，见审计笔记 §6.6 |
| **M4b** 多体热流谱          | 同附录 B 协议推广到 $N = 2..6$（$S = \sigma_z^1$ 不变，公式原样成立）；周期映射主本征矢作稳态引擎（解决慢模问题）；与 $N=1$ 结果对比找多体效应                                                                                                                                                                                                                                                                                                                                                                                     | 给出峰位移动、谱权重重分布、$\chi_s(\omega_d, N)$ 标度数据；与 challenge #123 目标对齐                                                                                   |

**关于被替换的原 M3（暴力有限记忆 IF 对照）**：原方案是对 $N = 2$–$3$ 不用均匀张量、逐路径显式求和截断 IF 的独立实现，用于抓增广 MPS 的接线错误。现判定其边际价值低——接线正确性已由 M0/M1(b) 对论文数据的逐点对照保证（单杂质 IF 是同一份代码路径），而 M3 换成 Redfield 对照后同时覆盖**多体接线**（$J \neq 0$ 的键门、站点 $\ge 2$ 的门作用）与**物理内容**（高频极限两方法必须汇合），一份算力两处验证。若 M3 出现系统性不一致且排查无果，原暴力 IF 方案作为后备调试手段保留。

### M3 执行结果（2026-07-28，通过；误差预算有重要概念修正）

实现：`tracks/mps/solutions/src/redfield_ising.jl`（多体 Redfield Liouvillian，Bohr 频率形式，无久期近似；Γ 用 SpecialFunctions 的 `expinti/expint`，约定与已验证单自旋脚本一致）+ `tracks/mps/solutions/test/m3_redfield_check.jl`。参数 h_x=0.5, A=1, ω_d=10, J=0.5, h_z=0.3，浴 α=0.05, ω_c=2.5。数据 `tracks/mps/results/20260728-augmps-m3/`。

| 检查                                                                 | 结果                                                                                                           | 判据            |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ | ------------- |
| N=1 Liouvillian vs 已验证 RM 数据列                                      | $6.7\times10^{-16}$                                                                                          | 接线 ✓（同一公式）    |
| 健康检查（所有 N）                                                         | max Re $\lambda(\mathcal L) \le 0$，tr 守恒到 $10^{-14}$                                                         | ✓             |
| 暂态 max $\lvert\Delta\langle\sigma_z\rangle\rvert$（峰值在 $t\approx2$） | 0.15–0.21，**对 N=2,3,6 逐位相同**                                                                                 | 见下面的预算修正      |
| 稳态 $\lvert\Delta\langle\sigma_z\rangle\rvert$                      | N=2：0.0096（t=150 vs 零本征矢）；N=3：0.056；N=6：0.0085（t=60 两曲线差）                                                    | $O(\alpha)$ ✓ |
| 频闪帧 $\lvert\Delta\,\mathrm{tr}(H_0\rho)\rvert$                     | 0.06（N=2,3）                                                                                                  | $O(\alpha)$ ✓ |
| NESS 结构                                                            | 两侧都弛豫到 AFM 型近基态（如 N=3：ours $(-0.62,+0.41,-0.59)$ vs RM $(-0.68,+0.46,-0.63)$ vs ED 基态 $(-0.55,+0.34,-0.55)$） | ✓             |

**概念修正（重要）**：M3 原判据里"$N=1$ 极限已由论文右板验证 RM 到 $1.2\times10^{-5}$"被误用——$1.2\times10^{-5}$ 是**我方 RM 代码 vs 作者 Zenodo RM 数据**的验证数，不是 exact-vs-RM 的物理一致数。实测同参数 N=1：exact vs RM 的暂态差本身就有 0.08（hz=0）至 0.19（hz=0.3），即 Born 二阶 + Markov + 一阶 Magnus 在 $t\sim2$–$3$ 的本征暂态误差。多体暂态偏差（0.15–0.21）与此完全同量级且 N 无关 → 源自单体 RM 近似误差，**不是**多体接线缺陷。真正的接线判据是晚时一致性（$\lesssim 0.04$–$0.06$，$O(\alpha)$ 内）与稳态结构。

**待办**：N=6 的 t=150 稳态对照（uniTEMPO 长程，宜上集群）；ω_d=20 加密点（验证偏差 ∝ A²/ω_d² 收缩，进一步区分 Magnus 截断与实现误差）。

### M0/M1 执行结果（2026-07-28，全部通过）

实现：`tracks/mps/solutions/augmented_tempo.jl`（增广 MPS 模块，纯数组实现，约定与 UniformTEMPO.jl 严格对齐）+ `tracks/mps/solutions/m0_m1_checks.jl`（驱动），数据在 `tracks/mps/results/20260728-augmps-m0m1/`。

| 检查                                         | 结果                                                                                                                                          | 判据                                     |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| M0（$N=1$，$\omega_d=2.5$，$t$ 到 200）         | max $\lvert\Delta\rvert = 7.5\times10^{-14}$                                                                                                | $\lesssim 10^{-6}$ ✓                   |
| M1(b)（$N=4$，$J=0$）站点 1 vs 论文               | $1.3\times10^{-13}$（$\omega_d=2.5$）、$5.0\times10^{-14}$（$\omega_d=10$）                                                                      | $\lesssim 10^{-6}$ ✓                   |
| M1(b) 站点 4 vs 单自旋幺正参考                      | $\sim 3\times10^{-3}$                                                                                                                       | Trotter 阶 ✓（两套离散方案的 $O(\delta t^2)$ 差） |
| M1(a)（$\alpha=0$，$N=10$，$t=5$）vs Krylov ED | max $\lvert\Delta\langle\sigma_z\rangle\rvert = 2.1\times10^{-3}$，$\lvert\Delta E\rvert = 5.9\times10^{-3}$，tr $\rho^2$ 漂移 $2\times10^{-4}$ | Trotter 阶 ✓                            |

实现中抓到并修复的三个 bug（均有单元测试仲裁）：SVD 解构拿到的是 $V$ 不是 $V^\dagger$（Julia `U,s,Vt = svd(M)` 第三项是 $V$）；kron 约定镜像（cap 出的 $\rho$ 站点 1 是最快指标，Julia `kron` 最后因子最快，site_op 需映射到位置 $N+1-i$）；`AugMPS` 需可变结构。

**M4 风险预警（实测数据）**：驱动链 Liouville 空间纠缠增长极快——$N=10$、$A=1$、$\omega_d=2.5$ 下 $\chi_s$ 在 $t \approx 5$（不到一个驱动周期）就触顶 256。§6 风险 1 是真实约束：M4 的 $j(\omega_d)$ 扫描需要 (i) 直奔频闪稳态而非长暂态、(ii) $\chi_s$ 收敛序列与聚积丢弃权重的系统记录、(iii) 或 Krylov 狙稳态本征矢。

**M4 机制验证（2026-07-28，详见审计笔记 §6.5）**：键流算符 $j_{i,i+1} = J h_x(\sigma_y^i\sigma_z^{i+1} - \sigma_z^i\sigma_y^{i+1})$ 已加进模块（`current_bond/current_profile/site_energies/op2`），ED 逐点对照 8.5e-5、带浴积分连续性 1.5%、无驱动极限 ~1e-8 全部通过；NESS 判据是逐站点 $ \bar\jmath_{i,i+1} - \bar\jmath_{i-1,i} = \bar s_i$ + 全局 $\bar s_1 - \bar\jmath_{1,2} = \bar P$。N=3 首扫：$\bar P(\omega_d=2.5)=+0.062$（强泵浦）→ 0.005（5）→ ~1e-4（10，RM 极限）→ 20 未收敛。**定位澄清（2026-07-29）**：键流是**体系内部**观测量，它验证的是附录 B 中式 (B.10) 的**积分形式** $\bar I = \bar P$（总流 = 驱动功率），不是论文图 3 的频率分辨密度 $\bar j(\omega)$；后者需要双时关联函数，是 M4a/M4b 的目标（见附录 B 与 §7 里程碑表）。**新风险（实测）**：T=0 Ohmic 浴 γ∝ω 导致小 Bohr 频率慢模衰减极慢且非单调，高频 NESS 流（~1e-4）被 ~1e-3 暂态残余掩盖——周期映射主本征矢从"可选优化"升级为 M4 的**必要引擎**（与论文计算协议一致：他们也是用 Floquet 传播子主本征矢定稳态）。

---

## 8. 与既有路线的关系

本方案 = 路线 A（uniTEMPO 嫁接进链）的**边界浴特化**，避开了路线 A 的两个工程痛点：增广 MPS 收缩序列重写（这里记忆腿永远只在边界张量上，cap 只在测量时发生一次）和 $\chi_s \xi$ 乘积瓶颈（$\chi_b$ 不进空间键）。路线 B（共浴集体耦合）的 IF 空间 MPO 化与本方案正交，留作 Tier 3；届时本代码的体部 TEBD 骨架可直接复用，只需把"边界张量 $B$"换成"逐站点记忆腿 + 空间记忆 MPO"。

---

## 附录 B：频率分辨热流密度 $\bar j(\omega)$ 的推导（按 Mickiewicz et al. 原文改正，2026-07-29）

出处：Mickiewicz, Link & Strunz, PRL **136**, 200201 (2026)（arXiv:2511.08754v3），主文 Eq. (10)–(11) 与 End Matter "Heat current density" 节 Eq. (17)–(25)。浴关联函数与谱密度约定见 Redfield 文档附录 A。

### B.1 改正说明（此前处理的偏差）

此前的做法（审计笔记 §6.5）：定义**体系内部键流** $j_{i,i+1} = J h_x(\sigma_y^i\sigma_z^{i+1} - \sigma_z^i\sigma_y^{i+1})$，再用能量平衡 $\bar P = \bar s_1 - \bar\jmath_{1,2}$ 推断浴耗散。两处偏差：

1. 论文的目标观测量是**浴模式分辨**的热流密度 $\bar j(\omega)$（哪个频率的浴模在被加热）——键流是体系内部量，给不出模式分辨，且在 $N=1$（图 3 的对象）根本无定义。
2. 能量平衡给出的只是**积分总量** $\bar I = \int \bar j(\omega) d\omega$（式 (B.10)），此前把它当作了热流密度本身。

键流与功率平衡本身没错，保留为体系侧辅助观测量与全局一致性检验；但 M4 的目标量必须改为式 (B.1) 的定义。

### B.2 定义与 $T=0$ 推导

定义（论文 Eq. 10）：给定频率的浴模能量变化率

$$
j(t, \omega) = \sum_\lambda \omega_\lambda \frac{d}{dt}\langle b_\lambda^\dagger(t) b_\lambda(t)\rangle \, \delta(\omega - \omega_\lambda) \tag{B.1}
$$

Heisenberg 运动方程（$H = H_S(t) + S\otimes B + H_B$）：

$$
\dot b_\lambda = i[H, b_\lambda] = -i\omega_\lambda b_\lambda - i g_\lambda S(t)
\;\Rightarrow\;
b_\lambda(t) = b_\lambda(0) e^{-i\omega_\lambda t} - i g_\lambda \int_0^t ds\, e^{-i\omega_\lambda(t-s)} S(s) \tag{B.2}
$$

代入 $\langle n_\lambda(t) \rangle = \langle b_\lambda^\dagger(t) b_\lambda(t) \rangle$ 展开四项。因子化初态 $\rho_{SB}(0) = \rho_S(0) \otimes |0\rangle\langle 0|$（$T=0$）下：含单个初始浴算符的交叉项为零（$b_\lambda(0)|0\rangle = 0$、$\langle 0|b_\lambda^\dagger(0) = 0$），真空项 $\langle b_\lambda^\dagger(0)b_\lambda(0)\rangle = 0$，只剩双积分项：

$$
\langle n_\lambda(t) \rangle = g_\lambda^2 \int_0^t\!\!\int_0^t ds\, ds'\, e^{-i\omega_\lambda(s - s')} \langle S(s) S(s') \rangle \tag{B.3}
$$

（有限 $T$ 时交叉项与 $\langle b^\dagger b\rangle = n_B$ 不为零，给出论文 Eq. (17) 的 $(1+2n_B)\sin$ 结构；本文档只需 $T=0$。）

对 $t$ 求导：只有积分边界贡献，两项互为共轭（$\langle S(s)S(t)\rangle = \langle S(t)S(s)\rangle^*$）：

$$
\frac{d}{dt}\langle n_\lambda(t) \rangle = 2 g_\lambda^2\, \mathrm{Re} \int_0^t ds\, e^{-i\omega_\lambda(t-s)} \langle S(t) S(s) \rangle \tag{B.4}
$$

连续极限（谱密度约定 $J(\omega) = \sum_\lambda g_\lambda^2 \delta(\omega-\omega_\lambda)$，见 Redfield 文档附录 A.1）：

$$
\boxed{\; j(t, \omega) = 2\omega J(\omega)\, \mathrm{Re} \int_0^t ds\, e^{-i\omega(t-s)} \langle S(t) S(s) \rangle \qquad (T=0) \;} \tag{B.5}
$$

与论文 Eq. (17) 核对：$\mathrm{Re}[e^{-i\omega(t-s)} C] = \mathrm{Im}[( \sin\omega(t-s) + i\cos\omega(t-s)) C]$，$n_B = 0$ 时逐字一致。

**物理读法**：热流密度完全由浴谱密度 $J(\omega)$ 与体系耦合算符的**双时关联函数**决定。双时关联是过程张量的原生能力（IF 记忆自动跨过两次插入，参见 uniTEMPO 多时关联方法 arXiv:2603.04970），主方程则很难算准（论文引 [66,67]）——这正是挑战 #123 选 IF 路线的根本原因。

### B.3 Floquet 稳态与周期平均（论文 Eq. 18–24）

周期平均（论文 Eq. 11）：$\bar j(\omega) = \frac{1}{T_d}\int_t^{t+T_d} dt' j(t', \omega)$。$t \to \infty$ 的准稳态下与观察时间无关：

$$
\bar j(\omega) = 2\omega J(\omega)\, \mathrm{Re} \int_0^\infty d\tau\, e^{-i\omega\tau}\, \bar C(\tau), \qquad
\bar C(\tau) = \frac{1}{T_d} \int_t^{t+T_d} dt'\, \langle S(t'+\tau) S(t') \rangle \tag{B.6}
$$

计算上把 $\bar C$ 拆成衰减部与渐近部：

$$
\bar C(\tau) = \bar C_{\rm decay}(\tau) + \bar C_{\rm asym}(\tau), \qquad
\bar C_{\rm asym}(\tau) = \frac{1}{T_d}\int_t^{t+T_d} dt'\, \langle S(t+\tau)\rangle \langle S(t)\rangle \tag{B.7}
$$

$\langle S(t)\rangle$ 是 $T_d$ 周期实函数 ⇒ $\bar C_{\rm asym}(\tau) = \sum_{n\ge 0} c_n \cos(n\omega_d \tau)$（$c_n$ 为实非负系数），代入 (B.6) 给出 **$\delta$ 峰贡献**（论文 Eq. 24）：

$$
\bar j_{\rm asym}(\omega) = \pi\, \omega J(\omega) \sum_{n=0}^\infty c_n\, \delta(\omega - n\omega_d) \tag{B.8}
$$

图 3 下板（横场 $\sigma_z$ 驱动）在**奇数倍** $n\omega_d$ 处的尖峰即此；纵场（$\sigma_x$ 驱动，上板）连续谱的峰在共振条件 $n\omega_d \pm \Omega$ 处增强，$\omega_d \to$ 大时整体压向 0（回平衡）。

### B.4 总量与能量平衡恒等式（已有结果的位置）

总热流（论文 Eq. 25）：

$$
\bar I = \int_0^\infty d\omega\, \bar j(\omega) \tag{B.9}
$$

能量守恒给出恒等式（NESS 下驱动注入 = 浴耗散）：

$$
\bar I = \bar P, \qquad \bar P = \frac{1}{T_d}\int_t^{t+T_d} dt' \left\langle \frac{\partial H_S}{\partial t'} \right\rangle = -A\omega_d\, \overline{\sin(\omega_d t)\, \langle M_z(t)\rangle} \tag{B.10}
$$

已有的 M4 机制验证（审计笔记 §6.5：$\bar P(\omega_d)$ 首扫、逐站点连续性、无驱动极限）验证的正是 (B.10) 的右端——它作为 M4a/b 的**全局一致性检验**保留，不再是目标观测量。

### B.5 计算协议与多体推广

论文的数值协议（主文 + End Matter）：

1. **稳态**：Floquet 传播子 $Q_F$（一个驱动周期的 Trotter 乘积）的**主本征矢**给出频闪稳态 $\Psi_\star$——不做长暂态（与我们慢模实测得出的必要引擎一致）。
2. **双时关联**：从 $\Psi_\star$ 出发，在时刻 $t'$ 插入 $S$（超算符插入），用微运动传播子 $Q_n$ 演化 $\tau$，读出 $\langle S(t'+\tau) S(t')\rangle$；对 $t'$ 作周期平均得 $\bar C(\tau)$。
3. **积分**：$\bar C_{\rm decay}$ 数值积分到 $\tau_{\max}$（需覆盖关联衰减时间）；$\bar C_{\rm asym}$ 的 $c_n$ 由周期 $\langle S(t)\rangle$ 的傅里叶级数给出，按 (B.8) 加 $\delta$ 峰。

多体推广（边界浴的决定性优势）：$S = \sigma_z^1$ 不变，(B.5)–(B.8) **原样成立**，只是 $\langle S(t)S(s)\rangle$ 变成多体链边界自旋的双时关联。增广 MPS 实现 = 站点 1 的 Liouville 腿上施加 $S$ 左乘映射（$B$ 张量的局域操作）→ 同一 Trotter/浴步传播 $\tau$ → 站点 1 用 $S$ 余矢量读出；浴记忆由记忆腿自动携带跨过两次插入，无需改动 IF。

### B.6 M4a 验证目标（Zenodo 数据清单）

记录 19593671（已下载至 `tracks/mps/results/20260727-195949-mickiewicz2026-fig2/zenodo/`）：

| 数据                                                      | 内容                                                      | 用途                                 |
| ------------------------------------------------------- | ------------------------------------------------------- | ---------------------------------- |
| `heat_current_longitudinal_..._ω_d_{2.5,5,10}_....csv`  | 图 3 上板（$\sigma_x$ 驱动）$\bar j(\omega)$，网格 0.005:0.005:15 | M4a 对照                             |
| `heat_current_transversal_..._ω_d_{1,1.5,2}_....csv`    | 图 3 下板（$\sigma_z$ 驱动）$\bar j(\omega)$                   | M4a 对照（$\delta$ 峰在奇数倍 $n\omega_d$） |
| `total_heat_current_{longitudinal,transversal}_....csv` | 图 5 $\bar I(\omega_d)$                                  | 积分总量对照，交叉验证 (B.10)                 |

参数统一：$\Omega = \epsilon_d = 1$、$\alpha = 0.05$、$\omega_c = 2.5$、$\delta t = \pi/60$、$\chi = 235$。注意单位制映射：论文 $\frac{\Omega}{2}\sigma_x$ ⇒ 我们的 $h_x = 0.5$；论文 $\delta$ 峰画法是把 $c_n$ 权重画成有限高竖线（fig_3.jl 里 `plot!([ω_d,ω_d],[data,5])`），对照时应比较**权重**而非视觉高度。
