# \(\Delta=1\) XXZ/XXX：从微观链到 Burgers 的闭环审计

## 最终判决

下列等式型闭环是**错误的**：

\[
\boxed{
\text{Kharkov 确定性标量 Burgers}
=
\text{两个随机 Burgers 模的噪声平均磁化方程}
}
\]

能够成立的是一个有明确断点的有效理论链：

\[
\begin{aligned}
\text{微观 XXX 链}
&\xrightarrow[\text{精确}]{\text{连续性方程}}
\text{GHD 无限准粒子层级}\\
&\xrightarrow[\text{近似}]{I_2\simeq\kappa I_0}
(m,\phi)\text{ 两模 NLFH}\\
&\xrightarrow[\text{长时固定点假设}]{\lambda_m=\lambda_\phi,\ D_m=D_\phi}
u_\pm=m\pm\phi\text{ 两个反手性随机 Burgers 模}\\
&\xrightarrow[\text{观测定义}]{}
m=(u_++u_-)/2.
\end{aligned}
\]

Kharkov 的路径则是

\[
\text{弱畴壁线性响应轨迹}
\xrightarrow{\text{PDE learning}}
U_t+aUU_x=D_{\rm cl}U_{xx}.
\]

公开数据证明最后这个方程是高精度的**有限时间、单轨迹代理模型**，
但没有证据把两条路径之间的虚线提升为等号。

## 1. 哪些步骤是严格的

### 1.1 微观连续性方程

在各向同性点

\[
H=J\sum_j\mathbf S_j\cdot\mathbf S_{j+1}
\]

直接计算 Heisenberg 对易子可得

\[
\dot S_j^z=j_{j-1}^z-j_j^z,
\qquad
j_j^z=J\left(S_j^xS_{j+1}^y-S_j^yS_{j+1}^x\right).
\]

因此纵向磁化守恒是精确的。它只给出

\[
\partial_t m+\partial_xj_m=0,
\]

并没有给出 \(j_m\) 是 \(m\) 的局域函数。继续演化电流会产生三点、
四点和更长程算符，所以从微观链到单场 PDE 必须加入闭合。

### 1.2 两模在固定点上的代数对角化

两模二次 Euler 通量取

\[
j_m=g\,m\phi,
\qquad
j_\phi=\frac g2(m^2+\phi^2).
\]

定义

\[
u_+=m+\phi,\qquad u_-=m-\phi,
\]

则

\[
j_m+j_\phi=\frac g2u_+^2,
\qquad
j_m-j_\phi=-\frac g2u_-^2.
\]

因此，在两个扩散常数相同且噪声也变换到正则基以后，

\[
\partial_tu_++g u_+\partial_xu_+
=D\partial_x^2u_++\partial_x\eta_+,
\]

\[
\partial_tu_--g u_-\partial_xu_-
=D\partial_x^2u_-+\partial_x\eta_-.
\]

这个对角化是精确代数；但“两模已经足够”和“系数流到上述固定点”不是
从有限次微观对易子得到的定理。原论文明确把无限 GHD 层级压缩到两模称为
近似，并用数值/RG 支持 long-time two-Burgers decoupling。
[De Nardis、Gopalakrishnan、Vasseur 2023](https://arxiv.org/abs/2212.03696v5)

## 2. 为什么奇数累积量相消，但这还没有解释完整分布

在零磁化、无限温平衡态，自旋翻转把磁流和磁化转移
\(\mathcal M\) 变号，而初态与 Hamiltonian 不变。因此

\[
P(\mathcal M)=P(-\mathcal M),
\qquad
\kappa_{2n+1}(\mathcal M)=0.
\]

这条结论由对称性直接保证，不需要先假设 two-Burgers。

two-Burgers 给出一个相容的机制。若 \(X_+\) 是一个 Baik--Rains
手性模，而 \(X_-\) 是独立的反射副本，则

\[
\kappa_n(X_-)=(-1)^n\kappa_n(X_+).
\]

对于 \(M=c(X_++X_-)\)，独立性给出

\[
\kappa_n(M)
=c^n[1+(-1)^n]\kappa_n(X_+).
\]

所以：

\[
\text{skewness}(M)=0,
\qquad
\text{excess kurtosis}(M)
=\frac12\text{excess kurtosis}(X_+).
\]

Baik--Rains 过剩峰度约为 \(0.29\)，因此两个独立反手性模预测

\[
\mathcal Q_{\rm 2B}\simeq0.145.
\]

Google 的 46 比特 Floquet XXZ 实验在 \(\Delta=1\) 报告

\[
\mathcal Q_{\rm exp}=-0.05\pm0.02
\]

（晚期 cycles 16--23 的平均），同时偏度在 \(\mu\to0\) 时趋零。
实验论文自己的对照表给 NLFH 峰度 \(0.14\)，并明确指出它与观测不符。
[Rosenberg 等 2024](https://arxiv.org/abs/2306.09333)

后续量子生成函数计算把时间推进到实验和量子轨迹之外，仍看到峰度趋于零或
保持弱负，没有看到向 \(+0.145\) 收敛。
[Valli 等 2025](https://arxiv.org/abs/2409.14442)

这里的 Floquet 电路与 Kharkov 使用的连续时间 XXX 演化不是同一份数据，
所以该峰度比较检验的是两者声称共享的 \(\Delta=1\) 长波普适理论，不能用来
否定 Kharkov 在其原始平均剖面上的有限窗拟合。后者由第 5 节的公开连续时间
数据单独审计。

因此证据支持以下分层判决：

- “平衡磁化转移的奇数累积量为零”：**证明成立**；
- “相反手性解释偏度相消”：**机制相容**；
- “两个独立 Baik--Rains 模已经定量解释完整 FCS”：**在可达时间被数据否定**；
- “极限 \(t\to\infty\) 最终一定不会到 two-Burgers”：**尚不能证明**，因为
  two-Burgers 本身被表述为可能具有很长交叉时间的渐近固定点。

较新的两点函数研究发现多个无可调参数的 KPZ 关系成立，但明确把结论限定为
KPZ 的“部分涌现”。
[Takeuchi 等 2025](https://arxiv.org/abs/2406.07150)

### 2.1 已登记的分层判别不会把所有“两模”合并成一个标签

2026-07-30 冻结的生产-v2 方案将可检验结论分成：

1. `scalar_surrogate_not_rejected`：有限窗标量代理仍未被联合观测排除；
2. `independent_two_burgers_supported`：独立反手性两模同时通过剖面、电流、
   脉冲响应和复 FCS 的留出检验；
3. `coupled_two_mode_supported`：耦合两模除通过上述检验外，还相对独立两模
   改善至少 10%，并满足 \(\Delta\mathrm{BIC}\ge10\)；
4. `memory_or_more_modes_required`：所有登记的 Markov 单/两模闭合均失败；
5. `insufficient_observables`：数据或数值门不完整，不作物理选择。

两模相对标量的共同硬门是留出误差改善至少 30%，且 2,000 次、每块
10 个物理时间单位的配对 bootstrap 的 95% 区间下界严格大于零。
这些状态不改变收敛门，也不授权解盲 production B。

## 3. 为什么“把噪声平均掉”严格错误

对随机 Burgers 方程

\[
\partial_tu+\frac{\sigma g}{2}\partial_xu^2
=D\partial_x^2u+\partial_x\eta
\]

取平均，只能得到

\[
\partial_t\bar u+
\frac{\sigma g}{2}\partial_x\langle u^2\rangle
=D\partial_x^2\bar u.
\]

由于

\[
\langle u^2\rangle=\bar u^2+\operatorname{Var}(u),
\]

真实平均方程是

\[
\partial_t\bar u+
\frac{\sigma g}{2}\partial_x\bar u^2
=D\partial_x^2\bar u
-\frac{\sigma g}{2}\partial_x\operatorname{Var}(u).
\]

仅有 \(\langle\eta\rangle=0\) 并不能消掉最后的涨落通量。
对物理磁化，两模方程平均后更直接地给出

\[
\partial_t\langle m\rangle+
g\partial_x\langle m\phi\rangle
=D_m\partial_x^2\langle m\rangle,
\]

它既不是单个 Burgers 方程，也没有一般恒等式
\(\langle m\phi\rangle\propto\langle m\rangle^2\)。

所以 Kharkov 论文提出的“noise-averaged stochastic Burgers”
只能是启发式解释，不能作为严格推导。
[Kharkov 等 2021](https://arxiv.org/abs/2111.02385)

## 4. 为什么物理磁化不能有固定的标量 Burgers 通量

自旋翻转使

\[
m\mapsto-m,\qquad j_m\mapsto-j_m.
\]

任何只依赖 \(m\) 的局域 Euler 通量必须满足

\[
j_m(-m)=-j_m(m).
\]

而标量 Burgers 通量

\[
j_m^{\rm B}(m)=\frac a2m^2
\]

是偶函数。若 \(a\ne0\)，它不能是零磁化附近物理磁化的普适单场本构关系。
对一条固定方向、固定归一化的畴壁，可以把方向标签藏进 \(a\)；这正说明
它是轨迹/扇区参数，而不是仅依赖局域磁化的材料常数。

如果额外强制单手性投影 \(u_{-\sigma}=0\)，则
\(\phi=\sigma m\)、\(u_\sigma=2m\)。对于文章存储的
\(U=m/\mu\)，可条件性地得到

\[
U_t+2\sigma g\mu\,UU_x=DU_{xx},
\qquad a=2\sigma g\mu.
\]

但实际弱 Gibbs 畴壁满足 \(\phi(x,0)=0\)，从而
\(u_+(x,0)=u_-(x,0)=m(x,0)\)，并不位于单手性扇区。
所以这个映射只说明“怎样能够得到相同形式”，不构成对
\(a\simeq0.24\) 的微观计算。

## 5. Kharkov 方程真正解释了什么

弱畴壁在线性响应阶满足

\[
U_i(t)\equiv\frac{\langle S_i^z(t)\rangle}{\mu}
=2\sum_js_jC_{ij}^{zz}(t)+O(\mu),
\]

对单位阶跃求空间导数：

\[
\partial_xU(x,t)=\frac{C^{zz}(x,t)}{\chi}+O(\mu)
=4C^{zz}(x,t)+O(\mu).
\]

因此输入 PDE learning 的 sigmoid 是平衡二点传播子的累积分布。
它主要采样了一条线性响应、自相似轨迹，没有独立扫描非线性状态空间。

公开 `highT_delta=1.npy` 数据上的可复现结果是：

- 常数闭合拟合：
  \[
  a=0.23015,\qquad D_{\rm cl}=1.97155;
  \]
- 全时间窗平均剖面积分相对误差：\(0.167\%\)；
- \(t=80\ldots190\) 的前沿宽度指数：\(0.6802\)；
- 由方差定义的 moment diffusivity 指数：\(0.3372\)，接近 \(1/3\)；
- 同一确定性方程延拓后，局部宽度指数从
  \(0.665\)（\(t\simeq200\)）升到 \(0.851\)（\(t=5000\)）。

最后一点与确定性 Burgers 的解析 Riemann 解一致。公开数据是上升畴壁，
\(U_L<U_R\)，其长时解是稀疏波：

\[
U(x,t)=
\begin{cases}
U_L,&x/t<aU_L,\\
x/(at),&aU_L<x/t<aU_R,\\
U_R,&x/t>aU_R.
\end{cases}
\]

宽度最终按 \(W\sim t\) 增长，而不是 \(t^{2/3}\)。有限窗接近 \(2/3\)
是扩散 \(W\sim t^{1/2}\) 到稀疏波 \(W\sim t\) 的交叉。

这同时证明：

- Kharkov 方程作为 \(50\lesssim t\lesssim200\) 的代理模型：**成立**；
- 它自身具有渐近 KPZ 标度：**不成立**；
- 常数 \(D_{\rm cl}\) 等于 KPZ 的尺度依赖 moment diffusivity：**不成立**。

## 6. 命题级证据表

| 命题 | 判决 | 证据 |
|---|---|---|
| 微观磁化连续性方程 | 证明 | 精确对易子 |
| GHD 精确只剩 \(m,\phi\) | 未证明 | 使用 \(I_2\simeq\kappa I_0\) 闭合 |
| 固定点上 \(u_\pm\) 为反手性 Burgers | 条件证明 | 通量代数对角化 |
| 平衡奇数磁流累积量为零 | 证明 | 自旋翻转/反射对称 |
| 两个独立 Burgers 定量给出完整 FCS | 可达时间证伪 | \(0.145\) 对 \(-0.05\pm0.02\) |
| 噪声平均得到确定性 Burgers | 反证 | 缺失 \(\partial_x\operatorname{Var}(u)\) |
| 固定 \(a\) 的标量 Burgers 是物理 \(m\) 的普适闭合 | 反证 | quadratic flux 违反 spin flip |
| Kharkov 方程是有限窗高精度代理 | 数值支持 | \(0.167\%\) profile error |
| Kharkov 方程渐近为 KPZ | 反证 | 稀疏波 \(W\sim t\) |

## 7. 可以安全写进论文的结论

可以写：

> The machine-learned deterministic Burgers equation is an accurate
> trajectory-conditioned finite-window closure for the weak domain-wall
> profile. It is neither the noise average of the two-mode stochastic
> hydrodynamics nor a universal one-field constitutive equation for physical
> magnetization. The two descriptions share selected \(z=3/2\) low-order
> signatures in accessible windows, while symmetry, nonlinear averaging,
> asymptotic rarefaction, and full counting statistics distinguish them.

不能写：

> Kharkov 的方程已经由 two-Burgers 严格推导出来。

也不能写：

> 两个 Burgers 模已经完整解释了 XXZ/XXX 的所有高阶统计。

机器可读的逐命题判决和数值锚点位于
`results_closed_loop/summary.json`；运行
`python scripts/audit_closed_loop.py` 可重新生成报告。
