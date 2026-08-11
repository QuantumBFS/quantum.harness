# U=0 Rice-Mele 多体陈数计算简报

## 1. 目的与范围

本次计算在现有 spinful Rice-Mele 精确对角化模型上，固定 $U=0$，使用
Fukui-Hatsugai-Suzuki（FHS）离散规范方法扫描 $(\phi,\theta)$ 参数环面，计算 many-body
Chern number。计算目标是先验证无相互作用极限的拓扑基准，不涉及 Hubbard 相互作用扫描。

参数为

$$
L=6,\quad t=1,\quad \delta_0=0.5,\quad \Delta_0=0.3,\quad
N_\uparrow=N_\downarrow=3.
$$

泵浦路径采用

$$
\delta(\phi)=\delta_0\cos\phi,\qquad
\Delta(\phi)=\Delta_0\sin\phi.
$$

## 2. 算法与流程

### 2.1 共享多体基底

使用 QuSpin 的 `spinful_fermion_basis_1d`，固定半填充粒子数扇区
$(N_\uparrow,N_\downarrow)=(3,3)$。Hilbert 空间维数为

$$
\binom{6}{3}^2=400.
$$

整个环面只创建一个 basis 对象，并在所有 Hamiltonian 中复用。basis ordering 使用 SHA-256
指纹检查，避免不同网格点的本征矢分量因基底顺序不同而产生无意义 overlap。

### 2.2 Hamiltonian 与边界 twist

内部跃迁和交错势沿用上一阶段的格点奇偶与符号约定。共同电荷 twist 只加入跨越周期边界
的 hopping：$c^\dagger_{L-1}c_0$ 乘 $e^{+i\theta}$，反向项乘
$e^{-i\theta}$，两个自旋分量使用相同 twist。

每个网格点都构造复数 Hermitian Hamiltonian，用 Hermitian sparse eigensolver
`eigsh(k=2, which="SA")` 计算最低两个本征值及归一化基态，并记录

$$
\Delta(\phi,\theta)=E_1-E_0.
$$

### 2.3 嵌套网格与缓存

依次使用 $5\times5$、$10\times10$、$20\times20$ 网格，不重复包含 $2\pi$
端点。网格坐标用约分后的 `Fraction` 作为缓存键，因此加密时旧顶点能被精确识别：

$$
(m,n)_N\longrightarrow(2m,2n)_{2N}.
$$

顶点基态、最低两个能量和 gap 可以复用；由于邻接关系改变，每级网格的 link 和 plaquette
flux 重新计算。计算量为 25、75、300 个新增点，共 400 个唯一对角化点；若三级独立重算，
则需要 525 次。

### 2.4 FHS 离散陈数

相邻基态定义规范化 link：

$$
U_\phi(m,n)=\frac{\langle\psi_{m,n}|\psi_{m+1,n}\rangle}
{|\langle\psi_{m,n}|\psi_{m+1,n}\rangle|},
$$

$$
U_\theta(m,n)=\frac{\langle\psi_{m,n}|\psi_{m,n+1}\rangle}
{|\langle\psi_{m,n}|\psi_{m,n+1}\rangle|}.
$$

按 $(\phi,\theta)$ orientation 计算 plaquette flux：

$$
F_{mn}=\operatorname{Arg}\left[
U_\phi(m,n)U_\theta(m+1,n)
U_\phi(m,n+1)^{-1}U_\theta(m,n)^{-1}
\right],
$$

最终

$$
C=\frac{1}{2\pi}\sum_{m,n}F_{mn}.
$$

程序拒绝非有限或不大于 $10^{-12}$ 的相邻 overlap，并检查 plaquette flux 未触及
principal-branch 边界。另对每个网格点施加独立随机 $U(1)$ 相位，验证 flux 和陈数不变。
Qi-Wu-Zhang 两能带非零曲率夹具用于独立验证 plaquette orientation。

## 3. 核心数值结果

| 网格 | $C_{\rm raw}$ | 最近整数 | 网格最小 gap | 最小 overlap | 最大 $|F_{mn}|$ | 新增/累计对角化 |
|---|---:|---:|---:|---:|---:|---:|
| $5\times5$ | -2.0000000000 | -2 | 0.93714184 | 0.29077142 | 2.14514511 | 25 / 25 |
| $10\times10$ | -2.0000000000 | -2 | 0.84118314 | 0.45313819 | 0.89517351 | 75 / 100 |
| $20\times20$ | -2.0000000000 | -2 | 0.60000000 | 0.83592809 | 0.26809370 | 300 / 400 |

所有网格的 Hamiltonian Hermiticity error 为 0；link 模长误差不超过
$3.4\times10^{-16}$；随机规范变换误差不超过 $5.5\times10^{-15}$。

## 4. 结论

三个嵌套网格稳定给出

$$
C=-2.
$$

符号由当前边界 twist 和 plaquette orientation 约定决定，其幅值 (|C|=2) 与两个自旋分量
各贡献一个同向电荷泵的无相互作用 benchmark 一致。随网格加密，最大 plaquette flux 明显
降低且最小 overlap 增大，说明离散 FHS 结果的数值可靠性改善。

$5\times5$ 网格没有采到控制最小 gap 的关键位置，因此其 0.9371 只能称为离散网格
最小值。$20\times20$ 网格包含 $\phi=\pi/2,3\pi/2$，得到 0.6000，是本次扫描中更可靠的
gap 结果，但仍不应在未做连续优化时宣称为严格连续环面全局最小值。

## 5. 复现与产物

运行命令：

```bash
cd /home/chenshuo/hackson/challenge36/hubbard-pump
/tmp/challenge36-quspin-venv/bin/python run_rice_mele_chern.py
```

主要产物：

- `run_rice_mele_chern.py`：扫描和 FHS 实现；
- `test_rice_mele_chern.py`：算法与物理 benchmark 测试；
- `results/rice_mele_chern.json`：机器可读数值结果。

最终自动化验证为 18 项测试全部通过。测试与正式扫描的合并后验证总耗时约 14.8 秒，其中
测试耗时约 8.8 秒。
