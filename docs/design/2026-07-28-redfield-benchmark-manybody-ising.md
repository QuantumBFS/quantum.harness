# 多体基准推导：驱动斜场 Ising 链 + 边界浴的 Redfield 主方程

日期：2026-07-28
状态：推导稿（benchmark 用，与 `2026-07-28-floquet-unitempo-manybody-ising.md` 配套）
参考：`tracks/mps/results/20260727-195949-mickiewicz2026-fig2/report.html` 的推导节（单自旋版），本文是其多体 + 纵场驱动推广。

---

## 1. 设定

$N$ 自旋 $1/2$ 链，驱动加在**纵场**上：

$$
H_{\rm sys}(t) = \sum_{i=1}^{N-1} J\, \sigma_z^i \sigma_z^{i+1} + \sum_{i=1}^N \left[ h_z(t)\, \sigma_z^i + h_x\, \sigma_x^i \right]
$$

$$
h_z(t) = h_z + A\cos(\omega_d t)
$$

左端点耦合零温 Ohmic 玻色浴：

$$
H_{SB} = \sigma_z^1 \otimes B, \qquad J(\omega) = \alpha\,\omega\, e^{-\omega/\omega_c}, \qquad T = 0
$$

浴关联函数（bcf）：

$$
\eta(s) = \langle B(s) B(0) \rangle = \frac{\alpha\, \omega_c^2}{(1 + i\omega_c s)^2}
$$

初态因子化 $\rho_{\rm tot}(0) = \rho_0 \otimes \rho_B$。记耦合算符 $S = \sigma_z^1$。

**与单自旋情形的结构对应**：驱动 $\parallel$ 耦合轴（都沿 $\sigma_z$），这是后面一切化简的根源。

---

## 2. Born 二阶：含时 Redfield 方程

相对 $H_{\rm sys}(t) + H_B$ 取相互作用图景，$H_I(t) = S(t) \otimes B(t)$，其中

$$
S(t) = U_{\rm sys}^\dagger(t)\, S\, U_{\rm sys}(t), \qquad U_{\rm sys}(t) = \mathcal T \exp\left(-i\int_0^t H_{\rm sys}(t')\, dt'\right)
$$

Born 近似（$\rho_{\rm tot}(t) \approx \rho_I(t) \otimes \rho_B$）+ 二阶展开，对浴取迹后：

$$
\frac{d\rho_I}{dt} = -\int_0^t ds\,\left\{ \eta(s)\, [S(t),\, S(t-s)\, \rho_I(t)] - \eta^*(s)\, [S(t),\, \rho_I(t)\, S(t-s)] \right\}
$$

这个核是**时间非局域且非平稳**的：$S(t)$ 和 $S(t-s)$ 各自依赖含时哈密顿量的完整演化史，直接数值处理需要对每个 $(t, s)$ 反复传播 $N$ 体演化——不可行。出路是 Floquet–Magnus。

---

## 3. Floquet–Magnus 约化

### 3.1 傅里叶分量与 kick 算符

按驱动谐波展开：

$$
H_{\rm sys}(t) = H_0 + H_{+1} e^{i\omega_d t} + H_{-1} e^{-i\omega_d t}
$$

$$
H_0 = \sum_{i=1}^{N-1} J\, \sigma_z^i \sigma_z^{i+1} + \sum_{i=1}^N \left[ h_z\, \sigma_z^i + h_x\, \sigma_x^i \right], \qquad H_{\pm 1} = \frac{A}{2} \sum_{i=1}^N \sigma_z^i
$$

一阶 Floquet–Magnus（van Vleck）修正：

$$
H_F^{(1)} = \sum_{n \neq 0} \frac{[H_{-n},\, H_n]}{2n\omega_d} = 0
$$

因为 $H_{+1}$ 与 $H_{-1}$ 都 $\propto \sum_i \sigma_z^i$，互相对易。于是**一阶有效哈密顿量就是时间平均**：

$$
H_F = H_0 + O(A^2/\omega_d^2)
$$

含时部分全部收进 kick 算符：

$$
K(t) = \exp\left(-i\, \frac{A}{\omega_d} \sin(\omega_d t) \sum_{i=1}^N \sigma_z^i \right)
$$

系统演化分解为 $U_{\rm sys}(t) = K(t)\, e^{-i H_F t}$（准确到一阶）。

### 3.2 关键对易关系：核变为平稳

因为驱动轴与耦合轴平行：

$$
[K(t),\, S] = 0
$$

所以相互作用图景的耦合算符在 kick 坐标系里**严格与时间无关地化简**：

$$
S(t) = K(t)\, e^{i H_F t}\, S\, e^{-i H_F t}\, K^\dagger(t) = e^{i H_F t}\, S\, e^{-i H_F t} \equiv S_F(t)
$$

代回 §2 的核：被积函数只依赖时间差 $s$，不再依赖 $t$。再取标准 Redfield 上限 $t \to \infty$（浴记忆有限），得到**静态有效模型的时不变 Redfield 方程**——全程不需要久期近似。

### 3.3 观测量的微运动修正

kick 坐标系与实验室系的密度矩阵差一个 $K(t)$。凡与 $K$ 对易的观测量——$\sigma_z^i$、$\sigma_z^i \sigma_z^{i+1}$、链的能量密度——**对微运动免疫**，可直接在有效模型里测。不对易的观测量（横向磁化、热流算符 $\hat j_{i,i+1}$，含 $\sigma_y$ 分量）需要变换：

$$
\langle O \rangle_{\rm lab}(t) = \mathrm{tr}\left[ O\, K(t)\, \rho_K(t)\, K^\dagger(t) \right] = \mathrm{tr}\left[ K^\dagger(t)\, O\, K(t)\, \rho_K(t) \right]
$$

$K^\dagger O K$ 是把每个站点的 $\sigma_x, \sigma_y$ 绕 $z$ 轴旋转角度 $2(A/\omega_d)\sin(\omega_d t)$，逐周期有界、周期平均后常可忽略——但逐时刻比较曲线时必须算上。

---

## 4. 静态有效模型的 Redfield 生成元

### 4.1 Born 二阶（Redfield）方程

$$
\frac{d\rho}{dt} = -\int_0^\infty ds\,\left\{ \eta(s)\, [S,\, S(-s)\rho] - \eta^*(s)\, [S,\, \rho\, S(-s)] \right\}
$$

$$
S(-s) = e^{-i H_F s}\, S\, e^{i H_F s}
$$

定义

$$
\mathcal A = \int_0^\infty ds\, \eta(s)\, S(-s), \qquad \mathcal B = \int_0^\infty ds\, \eta^*(s)\, S(-s)
$$

则耗散生元

$$
R\rho = -[S,\, \mathcal A \rho] + [S,\, \rho\, \mathcal B]
$$

### 4.2 Bohr 频率分解（多体实操形式）

对 $H_F$ 做 ED：$H_F |a\rangle = E_a |a\rangle$，$a = 1, \dots, 2^N$。记 $\omega_{ab} = E_a - E_b$，$S_{ab} = \langle a | \sigma_z^1 | b \rangle$。则

$$
S(-s) = \sum_{a,b} S_{ab}\, e^{-i\omega_{ab} s}\, |a\rangle\langle b|
$$

代入 $\mathcal A$：

$$
\mathcal A = \sum_{a,b} S_{ab}\, \Gamma(-\omega_{ab})\, |a\rangle\langle b|, \qquad \mathcal B = \sum_{a,b} S_{ab}\, \Gamma(-\omega_{ab})^*\, |a\rangle\langle b|
$$

其中单边傅里叶变换（解析式见附录）：

$$
\Gamma(\omega) = \int_0^\infty ds\, e^{i\omega s}\, \eta(s)
$$

**非久期形式不要求对 Bohr 频率去简并**——$\mathcal A$ 直接按矩阵元累加即可，这正是我们不分离久期项的好处（代价：不保证完全正性，见 §6）。

### 4.3 Liouville 超算符的 kron 组装（列主序 vec）

与单自旋完全同构，只是矩阵尺寸换成 $2^N$：

$$
R = -(\mathbb 1 \otimes S\mathcal A) + (S^T \otimes \mathcal A) + (\mathcal B^T \otimes S) - ((S\mathcal B)^T \otimes \mathbb 1)
$$

$$
\mathcal L = -i\, (\mathbb 1 \otimes H_F - H_F^T \otimes \mathbb 1) + R
$$

演化 $\rho(t) = e^{\mathcal L t} \rho(0)$。健康检查三件套：本征值全部 $\mathrm{Re} \le 0$；$\mathrm{tr}$ 守恒到机器精度；$\mathcal A$、$H_F$ 厄米性。

### 4.4 速率与平衡性

跃迁速率 $\gamma(\omega) = 2\,\mathrm{Re}\,\Gamma(\omega) = 2\pi J(\omega)\Theta(\omega)$（$T=0$ 只有发射）。对静态 $H_F$，只要 $S = \sigma_z^1$ 在能量基下充分连接（$h_x \neq 0$ 时 Ising 链各对称扇区之间连通），Redfield 稳态 = $H_F$ 的**基态**。

---

## 5. Redfield–Magnus 的结构性预言（benchmark 的物理靶子）

把上面串起来，主方程对本系统给出一个非常强的预言：

1. $H_F = H_0$ **不含驱动振幅 $A$ 和频率 $\omega_d$**（一阶恒为零，修正 $O(A^2/\omega_d^2)$）；
2. $T = 0$ 浴 + 静态 $H_F$ ⇒ 稳态 $\approx H_0$ 的基态，**与 $\omega_d$、$A$ 无关**；
3. 基态不携带热流 ⇒ **稳态热流 $j(\omega_d) \approx 0$**；
4. 暂态曲线 $\langle \sigma_z^i(t) \rangle$ 对所有驱动参数只有微运动级别的差别。

这正是单自旋图 2 结论的多体放大版：RM 曲线在两个 $\omega_d$ 下完全相同，而精确解在慢驱动下有持续相干振荡。多体情形精确 uniTEMPO 会给出驱动泵能 vs 边界浴冷却竞争出的**非平衡稳态**（$j(\omega_d) \neq 0$，多体共振结构）——凡是 RM 预言"没有"而 uniTEMPO 给出"有"的，就是非马尔可夫/高阶 Floquet 物理的定量度量。benchmark 的价值正在于这个零基线。

---

## 6. 数值实现方案

### 6.1 尺寸预算

Liouville 空间维数 $4^N$，超算符 $\mathcal L$ 尺寸 $4^N \times 4^N$（复数 16 字节/元）：

| $N$ | $2^N$（Hilbert） | $4^N$（Liouville） | $\mathcal L$ 存储 | 可行性 |
|---|---|---|---|---|
| 2 | 4 | 16 | 4 KB | 平凡 |
| 4 | 16 | 256 | 1 MB | 平凡 |
| 6 | 64 | 4096 | 268 MB | 笔记本可，$e^{\mathcal L t}$ 稠密指数变慢 |
| 8 | 256 | 65536 | 69 GB | 不可行（稠密） |

实操窗口 $N \le 6$；$N = 6$ 起改用 `expm_multiply`（Krylov 指数作用，不显式存 $e^{\mathcal L t}$）或直接对 $\mathcal L$ 稀疏化（$R$ 在能量基下是稠密的，稀疏收益有限，Krylov 是正路）。

### 6.2 流程

```julia
H_F = build_ising(N, J, h_z, h_x)            # 2^N × 2^N
E, V = eigen(Hermitian(H_F))                 # ED 一次
S  = V' * σz1 * V                            # 能量基下的耦合算符
Γm = [Γ(-(E[a]-E[b])) for a in 1:2^N, b in 1:2^N]   # expint/expinti, 附录公式
A  = V * (S .* Γm) * V'                      # 回到计算基
Bm = V * (S .* conj.(Γm)) * V'
R  = -(I⊗(S0*A)) + (S0'⊗A) + (Bm'⊗S0) - (((S0*Bm)')⊗I)   # S0 = 计算基 σz1
L  = -1im*(I⊗H_F - H_F'⊗I) + R
ρ(t) = expm_multiply(L, t, vec(ρ0))
```

检查清单沿用单自旋复刻的教训：先看 $\mathrm{eigvals}(\mathcal L)$ 的实部符号再跑长时间；kron 一律用闭式（不逐基填列）；$\Gamma$ 的符号用大 $\omega$ 渐近 $\sim +\omega_c/\omega$ 自检。

### 6.3 与 uniTEMPO 的对比清单

| 观测量 | RM 预言 | uniTEMPO 角色 |
|---|---|---|
| $\langle\sigma_z^i(t)\rangle$ 暂态 | 单调弛豫到基态值 | 慢驱动下持续振荡（图 2 型失效） |
| 稳态能量 $\langle H_{\rm sys}\rangle_\star$ | $E_0(H_0)$，与 $(\omega_d, A)$ 无关 | 加热修正 $\Delta E(\omega_d, A)$ |
| 稳态热流 $j(\omega_d)$ | $\approx 0$ | 非零，多体共振峰 |
| $\langle\sigma_x^i\rangle$ 等横向量 | 基态值 + 微运动 | 需比较 kick 修正后的逐时刻曲线 |
| 弱耦合极限 $\alpha \to 0$ | 渐近精确 | 两方法必须汇合——**一致性检查点** |

---

## 附录 A：浴关联函数 $\eta(t)$ 的完整推导与谱密度约定

### A.1 模型与谱密度约定

浴与耦合取

$$
H_B = \sum_\lambda \omega_\lambda b_\lambda^\dagger b_\lambda, \qquad H_{SB} = S \otimes B, \qquad B = \sum_\lambda g_\lambda (b_\lambda + b_\lambda^\dagger)
$$

**谱密度定义（本文档与全部代码的统一约定）**：

$$
J(\omega) = \sum_\lambda g_\lambda^2\, \delta(\omega - \omega_\lambda)
$$

注意这里**没有** $1/\pi$ 归一因子（部分文献用 $\mathcal J = J/\pi$，换算时当心）。取 Ohmic 谱 + 指数截断：

$$
J(\omega) = \alpha\, \omega\, e^{-\omega/\omega_c} \qquad (\omega \ge 0)
$$

无量纲耦合 $\alpha$（Kondo 惯例），截断 $\omega_c$。本文档数值一律 $\alpha = 0.05$、$\omega_c = 2.5$（论文参数，单位 $\Omega = 1$）。温度取 $T = 0$（浴初态为真空，$n_B(\omega) = 0$）。

### A.2 浴关联函数的定义与 $T=0$ 推导

浴关联函数（自由浴、热初态）定义为

$$
\eta(t) = \langle B(t) B(0) \rangle_B = \int_0^\infty d\omega\, J(\omega) \left[ \coth\frac{\omega}{2T} \cos\omega t - i \sin\omega t \right]
$$

$T = 0$ 时 $\coth \to 1$，三角函数合成指数：

$$
\eta(t) = \int_0^\infty d\omega\, \alpha \omega\, e^{-\omega/\omega_c} e^{-i\omega t}
= \alpha \int_0^\infty d\omega\, \omega\, e^{-\omega(1/\omega_c + it)}
$$

用 $\int_0^\infty \omega e^{-\omega s} d\omega = s^{-2}$（$s = 1/\omega_c + it$，$\mathrm{Re}\, s > 0$）得闭式

$$
\eta(t) = \frac{\alpha\, \omega_c^2}{(1 + i\omega_c t)^2}
$$

这就是 UniformTEMPO 离散化所用的 bcf（`bcf = t -> α*ω_c^2/(1+im*ω_c*t)^2`）。显式实虚部：

$$
\mathrm{Re}\, \eta(t) = \alpha\omega_c^2\, \frac{1 - \omega_c^2 t^2}{(1 + \omega_c^2 t^2)^2}, \qquad
\mathrm{Im}\, \eta(t) = -\alpha\omega_c^2\, \frac{2\omega_c t}{(1 + \omega_c^2 t^2)^2}
$$

性质：$\eta(0) = \alpha\omega_c^2$（$=0.3125$ 于论文参数）；包络 $|\eta(t)| = \alpha\omega_c^2/(1+\omega_c^2 t^2)$ 幂次衰减，记忆时间 $\tau_B \sim 1/\omega_c = 0.4$；$\mathrm{Re}\,\eta$ 在 $\omega_c t = 1$ 处变号（这是 $e^{-\omega/\omega_c}$ 截断的特征，$T=0$ 相干性的体现）。

### A.3 半傅里叶变换 $\Gamma(\omega)$：从 $\eta(t)$ 到 Redfield 速率

Redfield 生成元需要

$$
\Gamma(\omega) = \int_0^\infty ds\, e^{i\omega s}\, \eta(s)
$$

代入 $\eta(s) = \int_0^\infty d\omega' J(\omega') e^{-i\omega' s}$（$T=0$）并用分布恒等式

$$
\int_0^\infty ds\, e^{i\Omega s} = \pi\, \delta(\Omega) + i\, \mathrm{P}\frac{1}{\Omega}
$$

得

$$
\Gamma(\omega) = \int_0^\infty d\omega' J(\omega') \left[ \pi\,\delta(\omega - \omega') + i\, \mathrm{P}\frac{1}{\omega - \omega'} \right]
= \pi J(\omega) + i\, \mathrm{P}\!\!\int_0^\infty d\omega'\, \frac{J(\omega')}{\omega - \omega'}
$$

即（$T=0$）

$$
\mathrm{Re}\,\Gamma(\omega) = \pi\, \alpha\, \omega\, e^{-\omega/\omega_c}\quad (\omega > 0), \qquad \mathrm{Re}\,\Gamma(\omega) = 0\quad (\omega < 0)
$$

负频率为零正是 $T=0$ 细致平衡（浴只能吸收能量不能放出）。主值积分的显式求值见附录 B。数值锚点（论文参数）：$\mathrm{Re}\,\Gamma(1) = \pi \cdot 0.05 \cdot e^{-0.4} \approx 0.10534$。

有限 $T$ 时 $\eta(s)$ 含 $\coth$ 因子，相应 $\mathrm{Re}\,\Gamma(\omega) = \pi J(\omega)[n_B(\omega)+1]$（$\omega>0$，放 + 吸）、$\mathrm{Re}\,\Gamma(\omega) = \pi J(|\omega|)\,n_B(|\omega|)$（$\omega<0$，仅吸），二者之比 $e^{-\omega/T}$ 即细致平衡。本文档只用 $T=0$。

## 附录 B：$\Gamma(\omega)$ 解析式（照搬单自旋推导）

实部（耗散）：

$$
\mathrm{Re}\,\Gamma(\omega) = \pi\,\alpha\,\omega\, e^{-\omega/\omega_c}\, \Theta(\omega) = \pi J(\omega)\,\Theta(\omega)
$$

虚部（Lamb shift）：

$$
\mathrm{Im}\,\Gamma(\omega) = \alpha\left[-\omega_c + \omega\, g(\omega)\right]
$$

$$
g(\omega) = e^{-\omega/\omega_c}\, \mathrm{Ei}(\omega/\omega_c) \quad (\omega > 0), \qquad g(\omega) = -e^{|\omega|/\omega_c}\, E_1(|\omega|/\omega_c) \quad (\omega < 0)
$$

$\omega \to 0$ 时 $\omega g(\omega) \to 0$，$\mathrm{Im}\,\Gamma(0) = -\alpha\omega_c$。Julia 实现用 SpecialFunctions.jl 的 `expinti`（Ei，主值）与 `expint`（$E_1$）。符号自检：大 $\omega$ 渐近 $\mathrm{Im}\,\Gamma \sim +\alpha\omega_c^2/\omega$。
