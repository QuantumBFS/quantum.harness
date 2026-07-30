# PQMC 构型到 CPMC 路径桥接：正式设计

状态：已确认，待实现
日期：2026-07-30

## 1. 研究目标

本项目研究半满、无物理符号问题的二维 Hubbard 模型中，UHF
constrained-path (CP) 人工节点以及有限 walker 抽样是否造成系统误差。

核心实验是：

1. 用 ALF projector QMC (PQMC) 产生完整辅助场路径和无约束参考能量；
2. 将同一条完整路径按 CP 的时间和格点顺序强制重放，计算逐步热浴概率、
   walker 权重、节点和 population-control 风险；
3. 用 MATLAB CPMC-Lab 独立计算直接 UHF-CP 能量；
4. 用集群 C++ 重放结果比较全部路径、人工节点允许路径和低 proposal
   路径的能量；
5. 定量判断能量偏差来自硬节点、有限总体谱系灭绝，还是两者之外的误差。

本设计只针对以下固定参数点作受控数值论证，不宣称结论对其他尺寸、填充、
试探波函数或 HS 分解自动成立。

## 2. 固定模型与算法约定

Hamiltonian 为

```text
H = -t Σ_<ij>,σ (c†_iσ c_jσ + h.c.) + U Σ_i n_i↑ n_i↓ .
```

固定设置：

| 项目 | 数值或约定 |
|---|---|
| 晶格 | 4×4 square |
| 边界 | x、y 方向均为 PBC |
| hopping | t=1 |
| interaction | U=4 |
| 粒子数 | N↑=N↓=8 |
| HS | 实数二值 Hirsch spin HS |
| Trotter | 对称 K/2–V–K/2 |
| Δτ | 0.05 |
| ALF 中央窗口 | Beta=1 |
| 数值 | double precision、oneMKL |
| 精确有限尺寸能量 | E₀=−13.62192 |

实现统一采用粒子–空穴对称的相互作用形式：

```text
H_ph = K + U Σ_i (n_i↑−1/2)(n_i↓−1/2)
H    = H_ph + U Nsite/4            （半满固定粒子数）

cosh(gamma)=exp(Δτ U/2)

e^{−Δτ U(n↑−1/2)(n↓−1/2)}
  = e^{−Δτ U/4} (1/2) Σ_{x=±1} e^{gamma x(n↑−n↓)} .
```

ALF、C++ 和 MATLAB 必须记录自己内部使用的是 `H` 还是 `H_ph`，并在输出
原始 Hubbard 能量时统一加回 `U Nsite/4`。HS 的构型无关常数可在归一化概率
中约去，但在验证绝对 determinant weight 时必须由 contract 明确包含或明确
剔除。

Qin、Shi、Zhang 的 UHF+spin-HS 基准为 `−13.478(2)`，但该数值已经外推到
`Δτ→0`。固定 `Δτ=0.05` 的桥接计算不要求逐点等于该数值；文献值复现另作
时间步外推。

## 3. 三种波函数角色

必须区分投影初态、PQMC 左边界和 CP 约束态。

记：

```text
|I⟩ = ALF 构造的非相互作用行列式；
|T⟩ = UHF(Ueff=4) 共线 Néel 行列式。
```

4×4 PBC 是 open shell。ALF 使用 `Delta=0.01` 的实数弱二聚化只为选择确定的
非相互作用边界行列式，传播 Hamiltonian 仍为均匀 Hubbard Hamiltonian。
因此 `|I⟩` 必须从 ALF 导出，MATLAB 和 C++ 禁止各自重新对角化均匀 hopping
矩阵来猜测占据轨道。

UHF `|T⟩` 也只生成一次，由 C++ 和 MATLAB 共用；文件记录 UHF 参数、Néel
方向、列规范和 SHA-256。

### 3.1 ALF free/free 主参考 ensemble

```text
right ket = |I⟩
left bra  = ⟨I|
D_II(X)   = p(X) ⟨I|B(X)|I⟩
```

用途：

- 提供标准半满 sign-free PQMC 真值；
- 给出不含 UHF 人工节点的物理构型质量；
- 判断 CP 丢失区域在物理 PQMC 测度中的质量和能量贡献。

### 3.2 ALF free/UHF 桥接 ensemble

```text
right ket = |I⟩
left bra  = ⟨T|
D_TI^ALF(X) = p(X) ⟨T|V_L K ... V_1 K|I⟩
```

用途：

- 以与 UHF importance-sampled CP 相同的场变量提供桥接样本；
- 避免从 `D_II` 到 `D_TI` 的高方差重加权；
- 计算无约束 UHF-mixed 投影、离散 support 限制和实际 CP 动态覆盖的差异。

ALF 内部的 `V K` 切口与 CP 的 `K/2–V–K/2` 对称切口不能逐构型混同。
对相同 bitstring 另定义

```text
D_TI^CP(X) =
  p(X) ⟨T|K^(1/2) V_L K ... V_1 K^(1/2)|I⟩ .
```

两者仅相差确定的边界切口，但 UHF 左边界使该因子依赖于构型。C++ 必须同时
计算二者：`D^ALF` 校验 ALF archive，`D^CP` 才进入 CP 路径概率、节点和
support 分析。需要把 ALF 样本转换到 CP 对称测度时，使用
`r_cut(X)=D^CP(X)/D^ALF(X)` 做带符号自归一化重加权，并报告其 ESS。

对于满足半满二分晶格粒子–空穴配对条件的 `|I⟩` 和 UHF `|T⟩`，
`D_TI(X)` 可逐构型非负，但该性质不得假定。正式运行前必须验证：

1. `|I⟩`、`|T⟩` 的粒子–空穴配对残差；
2. 初始 overlap `⟨T|I⟩` 为正且远离零；
3. pilot 中 `sign(D_TI)`；
4. 多条独立 ALF 链的 mean sign 和能量一致性。

若高精度复核后出现真实负 `D_TI`，则当前“半满无符号问题”的主实验停止；
先修正边界的粒子–空穴配对，或把该数据另列为 sign-reweighted 扩展，不得与
主结果混合。

即使 `D_TI≥0`，UHF overlap 的零面仍可能分隔局域 ALF 更新的状态空间。
因此 free/UHF 只作桥接 ensemble，不能取代 free/free 主参考。

ALF 的 free/UHF 实现不能只替换一个通用 `Ham_Trial`。补丁必须分别载入四个
实矩阵：

```text
WF_R(up)=I_up       WF_R(down)=I_down
WF_L(up)=T_up       WF_L(down)=T_down .
```

轨道文件包含 site 顺序、spin 顺序、列顺序、浮点格式和 SHA-256。导入后分别
检查列正交性，并用只改变 determinant 正规范的列变换固定
`det(T↑†I↑)det(T↓†I↓)>0`。若 ALF 的 `Calc_Fl` 或同类优化通过粒子–空穴关系
重建另一 flavor，free/UHF 模式先禁用该重建并显式传播两个 flavor；只有逐
构型 determinant 测试证明等价后才允许重新启用。

两格点和 2×2 测试必须直接乘矩阵验证 `WF_L、WF_R` 的 spin block、field
符号和列规范，防止一个边界被 stock 初始化逻辑静默覆盖。

### 3.3 MATLAB CPMC

```text
initial walker             = |I⟩
importance/constraint bra  = ⟨T|
mixed-estimator bra        = ⟨T|
```

CPMC 是 open-ended random walk，没有 ALF 意义下被显式传播的左边界。
这一角色配置与 Qin 等人的算法相同：非相互作用态用于投影初态，UHF 用于
importance、constraint 和 mixed estimator。

## 4. 首要前置门槛：确定共同投影长度

当前 `Theta=10、Beta=1、Δτ=0.05` 对应 420 层。free/UHF 边界可能需要更长
投影才能消除边界的 spin/symmetry contamination。后续构型档案、C++ replay
和 MATLAB CP 不再硬编码 420，而使用本节确定的共同长度。

### 4.1 候选投影长度

固定 `Beta=1、Δτ=0.05`，按顺序扫描：

| Theta | Ltrot=(2Theta+Beta)/Δτ |
|---:|---:|
| 10 | 420 |
| 12 | 500 |
| 14 | 580 |
| 16 | 660 |
| 18 | 740 |
| 20 | 820 |

`Theta_max=20` 是硬上限，不再测试更长投影。每个 Theta 必须先完成本点的
统计精度验收，才能检查其能量值并决定停止或进入下一个 Theta。

### 4.2 每个 Theta 先独立控制统计误差

对当前 Theta：

- 使用六条独立单线程链；
- 第一批每条链使用 `NBin=7、NSweep=2000`；
- 每条链第一个 bin 作为 equilibration 丢弃，因此该设置实际给出 36 个 retained
  bins，而不是 42 个独立测量；
- 合并六链 retained bins，计算 block/chain-aware 的 `σ_E`；
- 若 `σ_E>0.005`，只增加当前 Theta 的 bins，不查看该点是否“接近
  −13.62”，也不进入下一个 Theta；
- 直到 `σ_E≤0.005` 后才冻结本点估计并检查能量值；
- bins 不设机械上限；`Theta=20` 也必须先满足 `σ_E≤0.005`。

这个下限来自已有 free/free 测试：`Theta=10`、36 个 retained bins 得到
`σ_E=0.00935`。按独立 bin 的反平方根缩放，`σ_E=0.005` 约需 126 个
retained bins，亦即每链约 21 个。首轮扩充可取每链 23 个 retained bins
（丢弃第一个 bin 时 `NBin=24`），但这只是工作量起点；正式停止完全由实际
误差棒决定。

Theta 扫描的验收量是 ALF 自身在中央测量窗口给出的、已转换到原始 Hubbard
Hamiltonian convention 的 total energy；这一前置测试不依赖尚未实现的 C++
endpoint replay。endpoint UHF mixed energy 在后续验证阶段补做，两者的全样本
均值若超出统计误差和有限 `Δτ` 预算则停止桥接分析。

### 4.3 值判断、停止规则与 Theta=20 回退

只有当前点满足以下统计与数值完整性条件后，才执行能量值判断：

- `σ_E(Theta)≤0.005`；
- 无非有限 observable；
- Green-function precision 显著小于统计误差；
- mean sign 与预期的非负权重一致；
- 六链 leave-one-chain-out 结果稳定；
- 不同初始辅助场链收敛到相同能量。

随后判断：

```text
energy_ok(Theta) =
    |E(Theta)−E₀| ≤ 0.005 .
```

选择算法固定为：

```text
for Theta in [10,12,14,16,18,20]:
    增加 MC 规模，直到 sigma_E(Theta)≤0.005
    然后检查 energy_ok(Theta)

    if energy_ok(Theta):
        Theta*=Theta
        status=target_reached
        stop

if Theta=20 仍不满足 energy_ok:
    Theta*=20
    status=max_theta_fallback
    继续后续统一参数运行

Ltrot*=(2Theta*+Beta)/Δτ
Nfield=16 Ltrot* .
```

相邻 Theta 的差值和趋势仍报告，但不再作为选择前必须通过的额外等价性门槛。
这个规则回答的是“在最大 Theta=20 的预算内，何时得到误差棒受控且落入指定
能量窗口的最短投影长度”，不构成严格的 Theta→∞ 收敛证明。

若进入 `max_theta_fallback`，仍按 `Theta*=20、Ltrot*=820` 运行
free/free、C++ replay 和 MATLAB CP；同时把 Hamiltonian convention、左右
边界、estimator 和有限 `Δτ` 检查列为并行诊断。后续结果必须标明基准能量
门槛未通过，不能把该偏差自动归因于 CP 遍历性。

### 4.4 共同长度契约

确定 `Ltrot*` 后：

- ALF free/free 使用同一个 `Theta*、Ltrot*`；
- ALF free/UHF 使用同一个 `Theta*、Ltrot*`；
- C++ 对每条路径完整重放 `Ltrot*` 层；
- MATLAB 可达性实验的每个粒子系统都从 `|I⟩` 重启并恰好传播
  `Ltrot*` 层；
- MATLAB 生产 CP 至少平衡 `Ltrot*` 层，然后继续运行以降低能量统计误差。

生产 CP 的任意 rolling window 起点是已经携带更早历史的 walker，并不等于
`|I⟩`。因此它不能直接验证由固定 `|I⟩` 计算的 `Q_prop`。若分析 production
run 的 window，必须同时保存窗口起点 determinant，并以该 determinant 为条件重放；
完整 ALF bitstring 的命中测试只在“从 `|I⟩` 重启”的有限时长实验中进行。

### 4.5 计算量和执行位置

已有 free/free 基线在 `Theta=10` 下以六条并行单线程链运行
`NBin=7、NSweep=2000`，实测 wall time 约 416 秒，单链内存小于 90 MB。
因此：

- `Theta=10` 达到每链约 23 个 retained bins 预计约 24 分钟；
- 成本近似随 `Ltrot` 增长，`Theta=20` 的同等最小统计量预计约 47 分钟；
- 若六个 Theta 全部运行且每点 23 个 retained bins 已足够，顺序执行的最低
  wall time 约 3.5 小时；
- 任一点若仍有 `σ_E>0.005`，其追加统计会增加实际时间。

这已经超过本项目的十分钟本地计算阈值。截至设计日期，仓库中没有
`skills/using-slurm/profiles/active.toml`，不能假装集群已配置。当前按用户已
确认的六个本地单线程任务执行，并在 run metadata 中记录
`local-compute deviation`；只占六个物理核，逐 Theta 完成后立即分析，禁止
一次性盲目启动全部投影点。若正式运行前补齐 active cluster profile，则可把
同样的六条独立链原样提交到集群，不改变统计设计。

## 5. 为什么完整路径是主分析对象

对精确传播子和固定左右边界：

```text
E(s) =
⟨L|e^{−(Theta_total−s)H} H e^{−sH}|R⟩
──────────────────────────────────────
       ⟨L|e^{−Theta_total H}|R⟩ .
```

因为 `H` 与 `e^{−τH}` 对易，辅助场求和后的能量不依赖插入位置。端点、中央
或其他充分投影位置都可给出能量。

因此主问题是：

> 把 ALF 的完整 `Ltrot*` 层字段按正确顺序作为一条从 `|I⟩` 出发的 CP
> 历史，标准 UHF-CP 是否能够完整生成并保留它？

C++ 主输出使用完整路径：

```text
Q_prop,Ltrot*
Q_CP,Ltrot*
W_stock,Ltrot*、W_phys,Ltrot*
first constraint rejection
minimum q
minimum halfK ratio
prefix barrier
population-control interval survival
endpoint UHF mixed energy
```

中央测量窗口仍保留为 checkpoint，用于回答 walker 在 ALF 中央测量时是否已经
被节点淘汰，并与 two-sided estimator 对齐。

上述插入位置等价只在对全部辅助场加权求和后成立，不逐构型成立。有限二阶
Trotter 下，物理 `H` 与离散传播矩阵也不严格对易；中央和端点差异作为
`O(Δτ²)` 诊断保留。

## 6. 辅助场档案

ALF 每次测量不全部保存。先用短 pilot 估计能量、辅助场以及 replay score 的
综合自相关时间。

初始 pilot：

```text
ExportStride=5 sweeps
```

正式间隔：

```text
ExportStride=max[20, ceil(5 τ_int,max)] .
```

`τ_int,max` 至少覆盖：

- total energy；
- 总 HS 场和 staggered HS 场；
- `log Q_prop,final`；
- prefix barrier；
- near-node count。

每条保存记录包含：

```text
sample_id
ensemble = II or TI
chain_id, bin_id, sweep_id
Ltrot, tau_export
bit-packed auxiliary fields
frozen sign
frozen central Ekin、Epot、Etotal
frozen endpoint overlap/energy（若该 ensemble 定义）
CRC
```

ALF sweep 过程中在不同 slice 累积的 online energy 对应一系列不断变化的
构型，不能贴到 sweep 末尾导出的单一 bitstring 上。每次 export 必须：

1. 完成当前 sweep 后冻结完整辅助场 `X`；
2. 不做任何 field update，重新建立稳定化堆栈；
3. 在 contract 指定的中央 slice/window 计算 `frozen` estimator；
4. 需要端点 estimator 时，再对同一个 `X` 独立重放计算；
5. 然后才写字段和 estimator。

原有 online bin energy 继续用于 Markov 链均值和误差，但只写 chain-level
统计文件，禁止作为单路径标签或 ALF/C++ 同构型比较值。

字段采用 time-slice-major、同一 slice 内 site-major。`+1` 为 bit 1，`−1`
为 bit 0。元数据必须保存 ALF site coordinates 及 ALF→CP site permutation，
禁止读取端猜测。

`field_order.json` 还必须显式保存：

- ALF slice index 到从右边界 `|I⟩` 出发的 CP propagation index 的映射；
- 每层是 `K/2–V–K/2` 还是与相邻层合并后的表示；
- spin-up 对 `+gamma x`、spin-down 对 `−gamma x` 的符号；
- HS 构型无关常数和 bit/endian convention。

读取器不得假定 ALF 数组下标递增就是物理虚时递增；该方向通过两格点和 2×2
短路径的逐矩阵乘积测试确定。

生产阶段 128 条链分别写 append-only 文件。无论当前 sweep 是否改变构型都按固定 stride
保存；禁止只保存 accepted configuration，禁止在 ALF 在线按节点或能量筛选。

首批每链保存 8 条、每个 ensemble 共 1024 条，并全部 replay；若尾部统计或
低概率层样本不足，再沿同一 append-only archive 增加批次。原始档案一直保留。

## 7. C++ 强制重放器

现有 `test/cpmc_path_audit` 扩展为可变尺寸、可变路径长度的稳定 replay 内核。

### 7.1 分离 initial 和 guide

接口从单一 trial 改为：

```text
PathEvaluator(model, initial_state=I, guide_trial=T, ...)
```

物理权重计算器显式输出：

```text
D_II^CP(X)=p(X)⟨I|K^(1/2)V_LK...V_1K^(1/2)|I⟩
D_TI^CP(X)=p(X)⟨T|K^(1/2)V_LK...V_1K^(1/2)|I⟩
D_II^ALF(X)=p(X)⟨I|V_LK...V_1K|I⟩
D_TI^ALF(X)=p(X)⟨T|V_LK...V_1K|I⟩ .
```

summary 中原有 `D_II、D_TI` 专指 CP 对称切口；`D_alf_II、D_alf_TI`
专指 ALF 归档切口。`boundary_cut_log_ratio=log|D^CP/D^ALF|` 单独保存，
不得吸收到试探态归一化常数中。

为避免 reference-energy 和 HS 常数混淆，contract 进一步定义：

```text
tau       = Ltrot Δτ
p(X)      = 2^(−Nfield)
O_m       = ⟨T|B_tilde(x_m)…B_tilde(x_1)|I⟩
S_ref     = Σ_l E_ref(l) Δτ

D_TI^H(X) = p(X) exp(−tau U Npar/2) O_Ltrot
W_phys(X) = W_stock(X) exp(−S_ref)

D_TI^H(X) = O_0 Q_prop(X) W_phys(X)       （全过程 alive）
```

`B_tilde` 只含 `K/2–exp[±gamma x]–K/2` 的一体矩阵。stock CPMC-Lab 每层
使用 `fac_norm=[E_ref(l)−U Npar/2]Δτ`；`E_ref(l)` 在运行中会更新，所以每层
都必须保存，不能用一个最终 `E_T` 代替 `S_ref`。若 C++ 内部传播 `H_ph`，
则先按第 2 节的常数移位转换到同一个 `D_TI^H` 再比较。

恒等式中的 `W_stock` 指沿该字段历史累积、尚未被 population control 重置的
raw path weight。MATLAB 的 `pop_cntrl.m` 会把当前 population weight 重置为
1；该数组不能直接代入恒等式。诊断结构必须另存不受重置影响的
`logW_path`，walker 被复制时一并继承。

逐层测试同时验证 `Q_prop`、`W_stock`、`S_ref`、`O_m` 和上述 signed-log
恒等式。
禁止只比较去掉未知整体常数后的相关系数。

### 7.2 节点后的处理

stock CPMC-Lab 的一个完整 slice 有三类 constraint 检查：

1. 第一个 `halfK` 后的 overlap ratio `r_K,pre`；
2. 每个 site 的两个 potential 候选及所选分支概率 `q_site`；
3. 第二个 `halfK` 后的 overlap ratio `r_K,post`。

因此形式存活定义为所有 `r_K,pre>0、q_site>0、r_K,post>0`。`Q_prop` 只累积随机
选择的 `q_site`；两个 halfK ratio 是确定传播的 weight factor，进入 `W` 而
不进入 `Q_prop`。

若任一 halfK ratio 不正，或强制路径所选字段满足 `q_site=0`：

- `alive=false`；
- 记录 first rejected slice、site 以及 `pre-halfK/site/post-halfK` 类型；
- `Q_CP` 永久记为零；
- 但无约束矩阵传播继续到路径末端；
- 继续计算最终 `D_II、D_TI` 和局域能量。

这用于识别“中途被 CP 杀死、但最终仍有重要物理贡献”的路径。

### 7.3 数值稳定硬要求

- 复用现有 `DenseMatrix` 接口并链接 oneMKL 的 BLAS/LAPACK；不新增 Eigen 或
  OpenBLAS 依赖；
- 所有 overlap、determinant、`D`、`Q_prop`、`W` 使用
  `sign+log|value|`；
- 热浴归一化使用 `logaddexp`；
- Green function 和 local energy 使用线性求解，不显式求逆；
- QR/UDV 保存尺度和 determinant sign；
- 禁止通过 `exp(accumulated_log_scale)` 重构巨大 overlap；
- 所有 prefix 均可输出，但普通 bulk replay 只保存紧凑摘要；
- 稳定化间隔 1、5、10 的物理结果必须一致；
- 节点判定必须经过不同稳定化间隔或更高精度复核。

### 7.4 每条路径的摘要

```text
sign/log|D_II|
sign/log|D_TI|
alive
full logQ_prop、full logW_stock、full logW_phys
first rejected event
minimum pre/post-halfK ratio 及位置
minimum selected q 及位置
每 slice 和每 PC interval 的 surprisal
minimum normalized UHF overlap
minimum singular value/principal angle
prefix probability barrier
PC weight valley 和后续 recovery
E_2s^I
E_mix^T
```

逐 site 完整 trace 只为硬节点、最高风险 1%、最高风险 0.1% 及 matched
controls 生成。

## 8. 可抽样性的分级定义

### 8.1 形式可达

```text
alive(X)=1
  当且仅当每个 pre/post-halfK ratio>0，
  且每个 potential 子步的所选分支 q_j>0。
```

`alive=0` 是标准 UHF constraint 下的硬支持集缺失。物理 free/free 无负权重
不保证 UHF guide 对所有 prefix 都给出正概率。

### 8.2 完整路径概率

```text
Q_prop(X)=Π_site events q_j
Q_CP(X)=1_alive(X) Q_prop(X) .
```

只有在关闭 population control、每条 walker 使用独立 RNG 并从同一 `|I⟩`
独立启动时，`R_ind` 次有限时长尝试至少命中一次的概率才严格为：

```text
P_hit,ind=1−(1−Q_CP)^R_ind
         ≈1−exp(−R_ind Q_CP) .
```

这个无 resampling 实验只验证 proposal 概率；对完整长 bitstring 通常只给出
理论等待量，对较短 prefix 做实际频率校验。

有 combing 的 `fixed_horizon` 粒子系统中，histories 共享祖先，`Q_prop` 不是
最终 population inclusion probability，genealogical ESS 也不能代入上述
Bernoulli 公式。此时对目标路径或 stratum 只报告跨独立粒子系统实测的：

```text
P_incl,k(Nw) =
  出现至少一个 k 类末端 walker 的独立系统数
  ───────────────────────────────────
               独立系统总数 .
```

完整 bitstring 命中只作补充；open-ended production rolling history 不参与
固定 `|I⟩` 的命中验证，除非同时保存并重放 window 起点 determinant。

### 8.3 中途概率瓶颈

原始 `logQ_m` 随长度单调减小，不能直接用其最小值。用训练数据的同长度
参考曲线去趋势：

```text
d_m(X)=logQ_m(X)−median_train[logQ_m|alive]
B_Q(X)=−min_m d_m(X).
```

`B_Q` 大但 final deficit 普通，表示路径曾经历很深的相对概率谷底，后续虽
恢复为普通路径，但有限 walker 谱系可能已经消失。

### 8.4 Population-control 生存

MATLAB 每次 combing 前记录：

```text
g_r=log(mean_i w_i).
```

C++ 对固定路径计算同一 PC 区间的 log weight growth `u_r`。单个已经实现该
路径的 lineage 的归一化期望子代为：

```text
a_r=exp(u_r−g_r).
```

记录：

```text
min log a_r
first a_r<1
count(a_r<1)
Π_r min(1,a_r)
谷底后的最大 recovery
```

`a_r≪1` 且以后恢复很大，是 early-extinction/late-blooming 的直接候选。
只在真实 population-control 时点评价；PC 间的暂时低权重若已恢复，不会被
combing 淘汰。

其中 `Π_r min(1,a_r)` 只是跨区间 retention proxy，不是 combing 下的精确
存活概率。精确谱系统计必须使用在第 `r` 次 combing 前已经可观测的 prefix
predicate `k_r`：

1. 在 combing 前按当前 determinant 和当前 prefix 指标判定 `k_r`；
2. 当场给满足条件的 lineage 分配不可变 tag；
3. 复制继承 tag，死亡则 tag 消失；
4. parent/offspring tree 直接给出后续时刻 `s` 的存活率。

```text
S_k(r→s) =
  在 s 时刻仍有后代的已标记 lineage 数
  ─────────────────────────────────
       r 时刻 combing 前的已标记 lineage 数 .
```

误差按独立粒子系统给出，不能把同一 population 内的 tagged walkers 当作
独立样本。依赖完整末端路径的 stratum 不能回看赋给已灭绝 lineage；若要测其
生存概率，必须保存预先选定的 prefix determinant，并从该状态运行多次独立
continuation。`a_r` 只用于定位候选灭绝区间，不能替代 `S_k`。

### 8.5 最终标签

每条路径使用四个可解释标签，不压成单一总分：

```text
support             = alive/dead
proposal percentile = final-Q_prop percentile
prefix risk         = B_Q percentile
PC fragility        = min a_r / retention / recovery percentile
```

## 9. MATLAB CPMC-Lab

直接 CP 能量必须来自 MATLAB CPMC-Lab，不自行实现新的 C++ population CP。
MATLAB 不读取、不重放 ALF/PQMC 构型；构型重放只由集群上的 C++ 程序执行。

Stock CPMC-Lab 将 free `Phi_T` 同时用作初态、约束和测量 bra。增加向后兼容的
可选结构：

```text
opts.Phi_init
opts.Phi_trial
opts.rng_seed
opts.diagnostics
opts.mode = production
```

正式设置：

```text
Phi_init  = ALF 导出的 |I⟩
Phi_trial = 共用 UHF |T⟩
O0        = det(T↑†I↑) det(T↓†I↓)
w0        = 1
```

固定轨道规范使 `O0>0`，并检查 `|O0|` 不接近零。`V.m`、`halfK.m` 和
`measure.m` 继续使用 UHF `Phi_trial`。

正式只运行 `production`：run 开始时从 `|I⟩` 初始化，至少投影共同长度
`Ltrot*` 后进入开放式测量，扫描 walker 数和独立 seed，直到直接 CP 能量
误差棒满足目标。若本地计算未及时完成，阶段性分析可引用 Qin 等人的
`−13.478(2)`，但必须标注为文献对照而非本次运行结果。

诊断扩展：

- `V.m` 返回所选字段、两个候选 ratio、`q_selected` 和 branching factor；
- `halfK.m` 返回 pre/post kinetic overlap ratio 和 kill flag；
- walker 累积路径标签、`logQ_prop` 和不被 population control 重置的
  `logW_path`；
- 每层保存实际 `E_ref(l)`，从而重构 `S_ref` 和 `W_phys`；
- `pop_cntrl.m` 返回 parent index 和 offspring count；
- measurement 输出各预定义路径类别的加权质量；
- 记录祖先数、genealogical ESS、weight ESS 和谱系灭绝。

生产能量算法本身不改变。

## 10. 能量重构与系统误差分解

### 10.1 free/free PQMC

ALF 已按 `D_II^ALF` 抽样：

```text
E_PQMC=mean_II[E_2s^I].
```

禁止再次乘 `D_II`。

对预注册且互斥完备的路径 strata `k`，同时报告物理 free/free 测度下的质量和
能量：

```text
p_II,k = mean_II[1_k]
E_II,k = mean_II[1_k E_2s^I] / p_II,k

E_PQMC = Σ_k p_II,k E_II,k .
```

尤其必须给出 `alive/dead`、低 final-Q、深 prefix barrier 和 PC-fragile
类别的 `p_II,k`，以及删除类别后的反事实能量
`(E_PQMC−p_II,k E_II,k)/(1−p_II,k)`。这才回答“CP 欠覆盖的区域在严格物理
PQMC 测度中是否重要”，不能用 TI 测度的质量代替。

### 10.2 free/UHF 无约束 bridge

记 `s_TI^ALF=sign[D_TI^ALF]`。ALF 实际按 `|D_TI^ALF|` 更新时，
其自身无约束 bridge 估计一律使用：

```text
E_TI,all =
  mean_|TI,ALF|[s_TI^ALF E_mix^T]
  ───────────────────────
       mean_|TI,ALF|[s_TI^ALF] .
```

只有 pilot 已逐构型证明 `s_TI=+1` 后，才把它简写为普通 mean。该无约束结果
应在共同投影长度下恢复 `−13.62192`，统计误差不大于 0.005；同时报告 mean
sign。后续所有 TI 条件均值遵循同一 sign-reweight 规则。

### 10.3 CP 对称切口和 support-restricted 参考

TI archive 的抽样密度是 `|D_TI^ALF|`，而 CP 的目标权重是
`D_TI^CP`。定义

```text
w_cut(X) =
  sign[D_TI^CP(X)]
  exp(log|D_TI^CP(X)| − log|D_TI^ALF(X)|).
```

因此 CP 对称切口的任意估计量都必须用 `w_cut` 自归一化；不能把 ALF
archive 中等权平均的频率直接称为 CP 目标质量。特别地，

```text
E_CP,support =
    Σ_|TI,ALF| w_cut 1_alive E_mix^T
    ─────────────────────────────────
         Σ_|TI,ALF| w_cut 1_alive .
```

同时报告 `w_cut` 的 ESS、最大归一化权重和最高 1% 权重占比；若 ESS
不足，该结果只作诊断，不作系统误差定量。

这个量只删除有限 `Δτ` 离散传播中实际出现 `q=0` 的路径。它不是自动等同于
无限 walker、无限运行时间的 CP 稳态：当节点两侧 overlap 都为正时，跨区
路径可以有 `q>0`，但其概率随接近节点而极小，且混合时间可能随
`Δτ→0` 发散。因此必须把 `E_CP,support`、有限预算的可见路径结果和 MATLAB
长时间 CP 结果三者分别报告。

### 10.4 从 free/free 交叉重构

作为独立一致性检查：

```text
r(X)=D_TI(X)/D_II(X)

E_TI =
  Σ_II r E_mix^T
  ───────────────
      Σ_II r .
```

同一套 free/free 样本还给出每个 stratum 的 TI 映射：

```text
p_TI,k = Σ_II r 1_k / Σ_II r
E_TI,k = Σ_II r 1_k E_mix^T / Σ_II r 1_k .
```

因此 `p_II,k、E_II,k` 回答严格物理测度中的重要性，
`p_TI,k、E_TI,k` 回答与 UHF importance distribution 和 CP mixed estimator
直接对应的重要性；两者不得混写。

必须报告：

```text
ESS_r=(Σr)²/Σr²
最大归一化权重
最高 1% 权重占比
```

若 ESS 太低，只把它作为诊断，不替代 free/UHF bridge ensemble。

### 10.5 有限 walker MATLAB CP

对预先冻结的路径 strata，定义：

```text
p_TI,k          = free/UHF ALF 中的目标质量
E_TI,k          = free/UHF ALF 中该层的条件 mixed energy
p_CP,k(Nw)      = fixed_horizon 末端的 walker-weight 质量
E_CP,k(Nw)      = fixed_horizon 末端该层的条件 mixed energy

E_CP,fixed      = Σ_k p_CP,k E_CP,k
E_TI,all        = Σ_k p_TI,k E_TI,k

E_CP,fixed−E_TI,all
  = Σ_k (p_CP,k−p_TI,k) E_TI,k
  + Σ_k p_CP,k (E_CP,k−E_TI,k) .
```

第一项是类别频率/质量欠覆盖贡献，第二项是类别内部条件分布改变的贡献。
`Σ_k p_CP,k E_TI,k` 只作为“仅替换类别频率”的反事实量，不能冒充直接 CP
能量。要求分层恒等式在 held-out 数据上复现 `fixed_horizon` 的直接 MATLAB
ratio estimator，并要求 `E_CP,fixed` 与独立 production 能量一致。production
rolling window 不用于这套 fixed-`|I⟩` 分层恒等式。单独寻找一个事后 cutoff
使能量碰巧相等，不视为因果证据。

## 11. 因果判别

扫描 MATLAB 的 walker 数、独立 seed 和 population-control interval。

| 观察 | 解释 |
|---|---|
| `q=0` 类别随 Nw 增加仍不出现 | UHF 人工节点的硬支持缺失 |
| `q>0、a_r≪1` 类别随 Nw 增大或 PC 变稀而恢复 | 有限总体谱系灭绝 |
| final Q 很低但加权类别覆盖正确 | 单条 micro-path 稀有，不是系统误差 |
| MATLAB 覆盖随 Nw 和运行时间稳定，但只停留在一个节点连通域 | 节点诱导的动态非遍历性 |
| MATLAB 的各 strata 和条件能量收敛到 support 参考，而 `E_CP,support≠E_TI,all` | 硬 constraint bias |
| 频率项解释主要偏差且 within-stratum 项受控 | 欠覆盖对系统误差的定量解释 |
| support 与 TI-all 一致但 production CP 仍偏离 | 动态混合或 population-control，而非硬支持缺失 |

允许对正 overlap 区域内的小概率分支使用概率抬升，但必须使用精确 residual
weight 保持 target/proposal 恒等式。给原本负 overlap 的分支非零概率会引入
constraint release 和符号，必须单独标记。

## 12. 统计方案

- ALF 误差按连续 sweep block 或原有 bin bootstrap；
- 六链做 leave-one-chain-out；
- MATLAB 误差按独立 run 和时间 block；
- walkers 不作为独立样本；
- strata 阈值在训练链冻结，在 held-out 链评估；
- top 1% 尾部若自相关修正后的有效样本少于约 100，只报告探索性结果并增加
  构型；
- 所有自归一化重加权报告 ESS 和最大权重占比。

## 13. 验证顺序

1. 两格点/2×2 短路径逐层验证 halfK/site constraint、`Q_prop`、`W_stock`、
   `S_ref` 和绝对 `D` 恒等式；
2. 验证 ALF 导出的 `|I⟩`、UHF `|T⟩`、四个左右 spin block 和
   site/time permutation；
3. 完成 free/UHF Theta 扫描，以 `target_reached` 或
   `max_theta_fallback` 确定 `Theta*、Ltrot*`；
4. 在 `Theta*` 上把 free/free 和 free/UHF 的 `σ_E` 都控制到
   `≤0.005`，并分别记录是否满足能量窗口；
5. 对真实长路径验证 signed-log 稳定性和稳定化间隔一致性；
6. 对冻结且不再更新的同一构型比较 ALF 与 C++ 的 `D^ALF`、能量和 Green
   function；另行保存 `D^CP/D^ALF`，不得拿 `D^CP` 直接校验 ALF archive；
7. free/free 全样本恢复严格 PQMC；
8. free/UHF 全样本恢复无约束 mixed 投影；
9. 验证 MATLAB `production` 直接 UHF-CP 能量；PQMC 构型可达性只由
   集群 C++ 重放验证；
10. 验证 II/TI 路径质量、support、类别频率项和类别内部项的分解；
11. 最后才做低概率、prefix barrier、PC fragility 和辅助场 pattern 分析。

权重恒等式、场顺序、非有限数或真实负权重等数值完整性门槛失败时，不进入
后续大规模构型分析。`Theta=20` 时能量仍在窗口外不属于停止条件：按
`max_theta_fallback` 继续，但结论降级为固定有限投影长度的诊断。

## 14. 文件布局

```text
test/pqmc_cp_bridge/
├── DESIGN_CN.md
├── contracts/
│   ├── model.json
│   ├── field_order.json
│   └── site_map.json
├── orbitals/
│   ├── phi_free.*
│   ├── phi_uhf_u4.*
│   └── hashes.json
├── runs/
│   ├── alf_ii/
│   ├── alf_ti/
│   └── matlab_cp/
├── archives/
│   ├── ii/
│   └── ti/
├── replay/
├── analysis/
└── results/
```

ALF 源码修改仍由 `test/alf_hirsch_binary/` 中的可复现 patch 管理；
C++ 内核仍位于 `test/cpmc_path_audit/`。桥接目录只保存共同 contract、运行入口、
档案索引、分析和最终结果，不复制两套源码。

## 15. 最终验收

进入构型归因分析前必须同时满足以下运行门槛：

1. free/UHF 已按顺序完成每个实际测试 Theta 的 `σ_E≤0.005`；
2. `Theta*` 已按以下二者之一冻结：
   - `target_reached`：首个满足 `|E−(−13.62192)|≤0.005` 的 Theta；
   - `max_theta_fallback`：Theta=20 仍不满足能量窗口，固定
     `Theta*=20、Ltrot*=820`；
3. free/free 在 `Theta*` 上也达到 `σ_E≤0.005`；
4. free/UHF 权重符号和链间混合已验证；
5. C++ 长路径无 `inf/NaN`，稳定化间隔结果一致；
6. alive 路径满足包含 `S_ref` 和 HS 常数的绝对权重恒等式；
7. ALF/C++ 同构型比较使用冻结构型 estimator；
8. MATLAB 两种模式使用同一 `|I⟩、|T⟩、Δτ、site/time order`，并记录
   halfK rejection 和实际 genealogy；
9. `p_II,k、E_II,k、p_TI,k、E_TI,k、p_CP,k、E_CP,k` 的分解在 held-out
   数据上闭合；
10. 所有 run、轨道和源代码均有 hash 与可复现参数记录。

若状态为 `target_reached`，且 free/free 与 free/UHF 在共同长度上都满足能量
窗口并通过上述验证和因果判别，项目允许支持的最强结论为：

> 在固定 4×4、PBC、U=4、半满、spin-HS 和 UHF(Ueff=4) 约束下，
> free/free 物理 PQMC 测度中存在有非忽略质量和能量贡献、但被标准 CP 硬排除
> 或被有限 walker 严重欠覆盖的路径类别；TI bridge 与 MATLAB 的频率/条件
> 能量分解可定量解释 CP 能量偏差，并可通过 walker 数和 population-control
> 扫描区分人工节点偏差与有限总体谱系灭绝。

若状态为 `max_theta_fallback`，所有后续程序和分析仍照常运行，但结论必须
限定为 `Theta=20、Ltrot=820、Δτ=0.05` 的有限投影结果；在未解决基准能量
偏差前，不把它表述为严格基态的 CP 系统误差。

若欠覆盖 strata 的质量或能量贡献不足以解释 MATLAB CP 偏差，则应报告
“在当前统计量和诊断定义下未找到该机制的充分证据”，不得通过事后改变阈值
强行得到预设结论。

不能仅由某条路径的 final Q 很低、一次 MATLAB 运行未命中相同 bitstring，或
事后删除某个尾部使能量相等，就宣称普遍的数学不可约性破缺。

## 16. 参考

- M. Qin, H. Shi, S. Zhang, *Benchmark study of the two-dimensional Hubbard
  model with auxiliary-field quantum Monte Carlo method*, Phys. Rev. B 94,
  085103 (2016), https://arxiv.org/abs/1605.09421
- M. Qin, *Diagnosing ergodicity in Constrained Path Auxiliary Field Quantum
  Monte Carlo*, QuantumBFS/quantum.harness issue 90,
  https://github.com/QuantumBFS/quantum.harness/issues/90
- H. Shi, S. Zhang, *Symmetry in Auxiliary-Field Quantum Monte Carlo
  Calculations*, Phys. Rev. B 88, 125132 (2013),
  https://arxiv.org/abs/1307.2147
- H. Nguyen, H. Shi, J. Xu, S. Zhang, *CPMC-Lab: A Matlab Package for
  Constrained Path Monte Carlo Calculations*, Comput. Phys. Commun. 185,
  3344 (2014).
