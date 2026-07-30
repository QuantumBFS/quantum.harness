# 三角晶格横场 Ising 模型的 merge–unmerge loop 量子蒙特卡洛：算法实现与精确对角化 benchmark

**参考文献**：W. Xu & X.-F. Zhang, *Loop Algorithm for Quantum Transverse Ising Model in a Longitudinal Field*, arXiv:2409.17835v2
**参考代码**：[AGXFzhang/QTIM_loop](https://github.com/AGXFzhang/QTIM_loop/blob/main/TIM_TL.jl)（1D 链）
**本工作**：将上述 SSE + merge–unmerge loop 算法推广到**三角晶格**（Julia 实现），并与精确对角化（ED）系统对比能量与磁化强度。

---

## 1. 模型与晶格

哈密顿量（Pauli 矩阵 $\sigma$）：

$$
H=\underbrace{J\sum_{\langle ij\rangle}\sigma_i^z\sigma_j^z-B\sum_i\sigma_i^z}_{H_d}\;-\;\Gamma\sum_i\sigma_i^x
$$

- 三角晶格：$L_x\times L_y$（本 benchmark 用 $3\times4$，$N=12$），周期边界；最近邻键取三个方向 $e_1=(1,0),\ e_2=(0,1),\ e_3=(-1,1)$，键数 $N_b=3N$，配位数 $z=6$。
- $J=1$（反铁磁，阻挫），横向场 $\Gamma$、纵向场 $B$ 可变。**无符号问题**（$\sigma^z$ 基下 stoquastic）。

---

## 2. SSE 展开与权重

配分函数按 Taylor 级数展开并插入 $M-n$ 个恒等算符（截断 $M$ 动态调整，无系统误差）：

$$
Z=\sum_{\alpha}\sum_n\frac{\beta^n}{n!}\langle\alpha|(-H)^n|\alpha\rangle
=\sum_{n\le M}\frac{\beta^n(M-n)!}{M!}\sum_{\alpha,\{v_u\}}\prod_u\langle\alpha_u|(-H'_{v_u})|\alpha_{u+1}\rangle .
$$

按文献 Eq.(2)，把 $-\Gamma\sum_i\sigma_i^{(0)}$（常数算符，$\sigma^{(0)}=\mathbb I$）也并入 $H$，即模拟的哈密顿量为 $H_{\rm sim}=H-\Gamma N$。算符分解与矩阵元（$s\in\{0,1\}$，$\sigma^z=2s-1$）：

| 算符 | 类型编码 | 矩阵元（权重） |
|---|---|---|
| 键对角 $-H_b$（含平移）| $1\!:\!4$ | $w_b(s_i,s_j)=-J\sigma_i^z\sigma_j^z+\frac{B}{z}(\sigma_i^z+\sigma_j^z)+C_b$ |
| 单体非对角 $\Gamma\sigma^x$ | $6=[1\,0],\ 7=[0\,1]$ | $\Gamma$ |
| 单体常数 $\Gamma\mathbb I$ | $5=[0\,0],\ 8=[1\,1]$ | $\Gamma$ |

平移常数 $C_b=|J|+2|B|/z+\varepsilon$（$\varepsilon=0.5$）保证全部键权重非负。类型编码 $=5+s_{\rm in}+2s_{\rm out}$。

**对角更新**（与参考代码一致）：逐槽位尝试插入/删除，Metropolis 概率

$$
P(\mathbb I\to H_v)=\min\!\Big(1,\frac{\beta\,{\rm opn}\,w_v}{M-n}\Big),\qquad
P(H_v\to\mathbb I)=\min\!\Big(1,\frac{M-n+1}{\beta\,{\rm opn}\,w_v}\Big),
$$

其中 ${\rm opn}=N_b+N$ 为可插入位置数；对角更新只直接插删**常数**单体算符，非对角算符仅靠 loop 更新产生/消灭。扫描到非对角算符时翻转传播组态 `conf`。

---

## 3. merge–unmerge loop 更新（三角晶格推广）

文献的核心创新：横场 Ising 没有自旋交换项，常规 loop 构造失效；通过**合并–拆分**让虫头（worm）能在空间移动。分三步：

### 3.1 Merge
把每个**单体算符**（常数或非对角）合并到一条相邻键上，变成四腿顶点（腿序：$1,2$=两个端点的入腿，$3,4$=出腿）：

- **1D 参考代码**：随机选左右 2 条键之一；
- **三角晶格（本工作）**：从该格点的 **6 条相邻键中均匀随机选 1 条**（`site_bonds` 表：3 条前向 + 3 条反向）。

合并后键上"无辜"端点入=出，算符所在端点：常数算符入=出，非对角算符入≠出（同时翻转 `conf` 完成虚时传播）。所有顶点（键算符 + 合并算符）用标准链接表（`link`/`ft`/`lt`，虚时周期边界）连接。

### 3.2 Loop（start–run–stop）
虫头从随机一个合并算符出发，边移动边翻转路径上的自旋：

- **起始腿**：常数合并算符 4 腿任选；非对角合并算符只能选**活跃端**（入≠出那个端点）的 2 腿，否则产生非法算符。起始即翻转该腿并切换算符类型（常数↔非对角）。
- **键算符**：只允许直穿或反弹。以热浴概率 $w_b(v_{\rm new})/w_b(v_{\rm old})$ 接受翻转并直穿，否则反弹（原路返回，不翻转）。
- **常数合并算符**：总是直穿；以 $P_s/2$ 概率停止（$P_s=1/2$）。
- **非对角合并算符**：从其余三腿等概率穿出；**从活跃端腿进入时**以 $P_s$ 概率停止。
- 每步启动虫链次数 = 合并算符数 $n_m$（保证每个算符平均被访问）。

> ⚠️ **实现要点（调试记录）**：判断非对角合并算符的活跃端必须在**翻转进入腿之前**读取 `opcfg`——先翻转会颠倒"可停止腿"的判断，轻微破坏细致平衡（表现为 $n_{\rm off}$ 比精确值低 2.4%）。本代码已修正。

### 3.3 Unmerge
虫链结束后：常数合并算符随机保留键的一端（与 merge 的均匀选择互逆，维持细致平衡）；非对角合并算符保留活跃端——**非对角算符借此跳到相邻格点**，实现空间维度的移动。最后从 `opcfg` 恢复物理组态 `conf`。

---

## 4. 观测量估计式

记 $n$ 为非恒等算符总数，$n_{\rm site}$ 为单体算符（常数+非对角）数。

**能量**：$E=-\partial\ln Z/\partial\beta$，注意 $-H=\sum_b A_b+\sum_i\Gamma(\sigma_i^x+\mathbb I)-N_bC_b$，得

$$
\boxed{\;\langle H\rangle=-\frac{\langle n\rangle}{\beta}+N_bC_b+\Gamma N\;}
$$

（$+\Gamma N$ 来自常数算符项 $\Gamma\mathbb I$ 并入 $H_{\rm sim}$；$J=0$ 极限已数值验证此常数。）

**横向磁化强度**：对 $\Gamma$ 求导，$\partial\ln Z/\partial\Gamma=\langle n_{\rm site}\rangle/\Gamma=\beta\langle\sum_i(\sigma_i^x+\mathbb I)\rangle$，得

$$
\boxed{\;m_x=\frac{1}{N}\Big\langle\sum_i\sigma_i^x\Big\rangle=\frac{\langle n_{\rm site}\rangle}{\beta\Gamma N}-1\;}
$$

**纵向磁化强度**（对角量，虚时平均）：沿算符列表传播组态，对 $M$ 个虚时槽位平均，

$$
m_z=\frac{1}{N}\Big\langle\sum_i\sigma_i^z\Big\rangle,\qquad
m_z^2=\Big\langle\Big(\frac{1}{N}\sum_i\sigma_i^z\Big)^2\Big\rangle .
$$

统计：50 个 bin 估计误差棒。

---

## 5. 热化与退火（重要）

在深有序相（小 $\Gamma$，clock 有序），键算符翻转接受率低、虫链短，从随机组态出发容易**滞留于亚稳态**（实测个别种子在 $\Gamma=0.2$ 卡在无序态，$E$ 偏高 5%）。解决方案——**量子退火式热化**：热化阶段令 $\Gamma$ 从顺磁区（$\Gamma_0=2$，混合快、基态唯一）线性降到目标值（前 80% 步数），后 20% 恒 $\Gamma$ 继续热化，体系绝热跟随进入有序相。截断 $M$ 在热化中按 $1.25\,\langle n\rangle$ 自适应增长。低 $\Gamma$ 点采用 istp=40000、mstp=100000，其余 istp=20000、mstp=30000。

---

## 6. 正确性检验

### 6.1 $J=0$ 极限（解析可解）
$H=-\Gamma\sum_i\sigma_i^x-\Gamma N$（模拟系），单点精确解给出每点 $\langle n_{\rm off}\rangle=\beta\Gamma\tanh\beta\Gamma$，$\langle n_{\rm const}\rangle=\beta\Gamma$。$3\times3,\ \beta=20,\ \Gamma=1$：

| 算符数 | QMC | 精确值 |
|---|---|---|
| $n_{\rm off}$ | 179.94 | 180 |
| $n_{\rm const}$ | 179.99 | 180 |
| $n_{\rm bond}$ | 270.08 | 270 |

且 $E/N=-1.0000$（QMC）对 $-1.0000$（解析/ED），$m_x=1.0000$ 对 $1.0000$。参考 1D 原代码同测试亦通过。

### 6.2 与 ED 的系统对比（$3\times4$ 三角晶格）

**(a) $\Gamma$ 扫描**（$B=0,\ \beta=20$，17 个点）——能量、横向磁化、$m_z^2$ 全部落在 ED 曲线上，偏差均 $\le 2.2\sigma$（绝大多数 $<1.5\sigma$）。

**(b) 温度扫描**（$\Gamma=0.8,\ B=0$，$\beta=1\!\sim\!30$）——从高温顺磁到基态全温区吻合（$\le1.9\sigma$）。

**(c) 纵向场 $B$ 扫描**（$\Gamma=0.8,\ \beta=20$）——merge–unmerge 的核心场景（有限 $B$ 下线算法失效），$E$、$m_x$、$m_z$ 全部吻合（$\le1.6\sigma$）。

代表性数据（$\beta=20,\ B=0$）：

| $\Gamma$ | $E/N$ (QMC) | $E/N$ (ED) | $m_x$ (QMC) | $m_x$ (ED) |
|---|---|---|---|---|
| 0.2 | $-1.0625\pm0.0008$ | $-1.0632$ | $0.3519\pm0.0038$ | $0.3517$ |
| 0.6 | $-1.2391\pm0.0014$ | $-1.2391$ | $0.5087\pm0.0030$ | $0.5081$ |
| 1.0 | $-1.4766\pm0.0016$ | $-1.4767$ | $0.6681\pm0.0023$ | $0.6683$ |
| 1.4 | $-1.7725\pm0.0014$ | $-1.7711$ | $0.7958\pm0.0014$ | $0.7935$ |
| 2.0 | $-2.2746\pm0.0022$ | $-2.2791$ | $0.8841\pm0.0013$ | $0.8861$ |
| 3.0 | $-3.2020\pm0.0027$ | $-3.1990$ | $0.9449\pm0.0010$ | $0.9436$ |

**结论：merge–unmerge loop 算法在三角晶格上的推广完全正确，能量与磁化强度（横向/纵向）与精确对角化在误差棒内一致。**

---

## 7. 代码与数据文件

| 文件 | 说明 |
|---|---|
| `TIM_tri_QMC.jl` | 三角晶格 SSE + merge–unmerge loop QMC（中文注释）。用法：`julia TIM_tri_QMC.jl Lx Ly J Gamma B beta istp mstp seed [Gamma_start]`，输出 `E,E_err,mx,mx_err,mz,mz_err,mz2,mz2_err` |
| `TIM_tri_ED.jl` | 精确对角化（全谱，有限温）。用法：`julia TIM_tri_ED.jl Lx Ly J Gamma B beta1 beta2 dbeta` |
| `qmc_gscan_final.csv` / `ed_gscan.csv` | $\Gamma$ 扫描数据 |
| `qmc_tscan.csv` / `ed_tscan.csv` | 温度扫描数据 |
| `qmc_bscan.csv` / `ed_bscan.csv` | 纵向场扫描数据 |
| `fig_gscan.png` / `fig_tscan.png` / `fig_bscan.png` | 对比图 |

### 相对 1D 参考代码的改动清单
1. 晶格：1D 环 → 三角晶格（$e_{1,2,3}$ 三方向建键，`site_bonds` 记录每点 6 条关联键）；
2. merge 键选择：2 选 1 → **6 选 1**；
3. 纵向场按配位数分摊：$B/2$ → $B/z$（$z=6$）；
4. 能量估计式补 $+\Gamma N$ 常数项（$J=0$ 检验确认）；
5. 测量：增加 $m_x$（算符计数）、$m_z$、$m_z^2$（虚时平均）与 binning 误差；
6. 增加 $\Gamma$ 退火热化以克服有序相亚稳态；
7. 修正移植 bug：非对角合并算符的停止判断须在翻转进入腿**之前**读取活跃端。
