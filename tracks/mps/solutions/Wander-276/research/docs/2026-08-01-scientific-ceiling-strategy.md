# 如何抬高 *Chaos of Quantum Geometry* 的科学上限

Date: 2026-08-01

Authoring agent: [Codex]

## 2026-08-04 封存结果 closeout

封存的 $N=14$ 主检验已经完成独立 hash/source 审计并显式解盲。Adjacent sparse 的物理中位数为 $0.301529$，complete-realization 95% 区间为 $[0.291527,0.312061]$；collapsed 与 Hodge 97.5% prediction intervals 分别为 $[0.111789,0.111852]$ 和 $[0.112344,0.112513]$。Central sparse 的对应结果为 $0.374993$、$[0.368980,0.380473]$，而两个 null 区间分别为 $[0.111338,0.111353]$ 和 $[0.111333,0.111348]$。两个主 sector 都拒绝两个冻结的 separable covariance null，选择 `cohomological_non_gaussian_class`。

因此 `Independent model/operator class` 门槛已经从设计层面升级为封存验证后的有限尺寸结果：generic fixed-charge cubic $\mathcal N=2$ SYK 通过 exact/coexact cohomological response 实现了独立于 Kapit--Mueller/Laughlin 的保护机制，并在同一个 four-channel protocol 下保留结构记忆。`Asymptotic Geometric ETH` 仍未建立；完整 nonseparable entrywise covariance matching 也仍未完成。当前组合使 PRL 成为有逻辑依据的首投尝试，但 PRX Quantum 仍需要更强的 QIS consequence/capability，Nature Physics 仍需要受控大 $N$ 定律、BPS 新预测或同等级的广泛概念后果。

## 2026-08-02 状态更新：两个上限门槛已经分化

这份路线图中的一个关键前提已经改变。`Independent model/operator class` 不再是“没有”：当前 v7 工作使用 generic fixed-charge cubic $\mathcal N=2$ SYK 的 harmonic cohomology，实现了与 Kapit--Mueller/Laughlin $B^\dagger B$ parent 不同的 $H=\{Q,Q^\dagger\}$ 保护机制。其响应严格分成正交 exact/coexact 分支；$N=8,10,12$ 的 12 个 size/sector/panel 组都拒绝冻结的 collapsed 与 Hodge-separable Gaussian null。这里的新贡献不是再次发现 SYK Berry-curvature chaos，而是用同一个 gauge-invariant four-channel 统计量对不同保护复形进行 pre-outcome prediction test。

`Asymptotic Geometric ETH` 仍然没有建立。即使封存的 $N=14$ 验证重复 pilot 分支，它也只把结论升级成受预注册保护的有限尺寸 cross-mechanism response class；它不能给出大 $N$ 集中定理、受控指数或 thermodynamic limit。两个主题因此都重要，但不是“做完两个 checkbox 就自动中好杂志”：独立机制回答“不是单个 parent 的巧合”，渐近理论回答“这是不是一个真正的普适律”。

### 按期刊官方标准重新判断

- [Physical Review Letters 的官方标准](https://journals.aps.org/prl/authors/publish/policies-and-practices-physical-review-letters-july-2013)要求工作构成一个领域中的重大进展或具有跨子领域影响，并且以广泛物理读者能理解的方式说明问题与主要成就。若 $N=14$ 封存检验通过全部门禁，当前组合——能谱沉默、量子几何替代诊断、独立拓扑与 SUSY 保护机制、精确 response-complex identity、无事后拟合的验证——已经形成一个可信的 PRL 尝试，而不是只有“多算了一个尺寸”。这仍是投稿判断，不是录用保证。
- [PRX Quantum 的官方 acceptance criteria](https://journals.aps.org/prxquantum/about)要求至少体现 exceptional advance、exceptional connection、exceptional capability 或 exceptional insight；其[官方 scope](https://journals.aps.org/prxquantum/scope)明确包含 many-body quantum information、fundamental physics、verification/validation 与 benchmarking。当前工作的最佳匹配是 exceptional connection：把 BPS/SUSY cohomology、FQH parent geometry、随机矩阵高阶响应和 fail-closed computational validation 连接起来。要让它成为强 PRX Quantum 稿，而不是可尝试稿，需要把诊断明确连接到 quantum information observable、verification protocol 或参数空间信息传输后果。
- [Nature Physics 的官方 scope](https://www.nature.com/nphys/submission-guidelines/about/aims)要求最高质量和显著性的广泛物理结果；其[审稿流程说明](https://www.nature.com/nphys/editorial-policies/peer-review)也明确只有最可能满足一般兴趣标准的稿件才会送外审。当前有限尺寸结果即使封存成功，也不足以把 Nature Physics 当作现实首投目标。合理的抬档条件是：受控大 $N$ 定律、一个参数无关的 geometric echo/holonomy/OTOC 后果，或对 BPS black-hole microstates 给出 seed paper 之外的新定理或预测；三者至少完成一个，最好完成两个。

### 当前最诚实的期刊上限

| 完成状态 | 科学含义 | 投稿判断 |
|---|---|---|
| 已完成 $N=8,10,12$ pilot 与封存 $N=14$ 主检验 | 独立 cohomological 机制 + outcome-blind finite-size falsification；两个主 sector 均拒绝两个冻结 null | PRL 是合理首投；PRX Quantum 可尝试但需强化 QIS consequence |
| 再完成 full nonseparable covariance control 或可推导尺度律 | 排除“只是遗漏两点协方差”的主要替代解释，进入机制性 universality | 强 PRL / 实质性 PRX Quantum |
| 再加局域 SUSY parent 或参数无关动力学/拓扑后果 | 跨保护、局域性与独立物理后果形成统一原则 | 强 PRX；Nature Physics 成为高风险但有逻辑依据的目标 |
| 建立大 $N$ concentration theorem 并产生 BPS/black-hole 新预测 | Asymptotic Geometric ETH 与原始物理动机闭环 | Nature Physics/PRX 级真正高上限，仍无录用保证 |

判断方法不是数关键词，而是问审稿人最难提出的替代解释还剩什么。现在最主要的替代解释已经从“只属于 Kapit--Mueller”变成“当前 null 没有匹配完整 nonseparable entrywise covariance”；最主要的量词缺口则仍是“$N\le14$ 不能决定 $N\to\infty$”。因此下一轮最值钱的工作不是立即堆 $N=16,18$，而是先导出或构造更强的 covariance-complete null，再用新增尺寸区分一个冻结的大 $N$ 预测。

## 结论先行

这篇工作的科学上限，不由还能多算几个粒子决定，而由论文标题中最强的量词决定。当前最稳妥的主张是：在一个 Kapit--Mueller bosonic Laughlin 精确零模家族中，能谱完全沉默时，非阿贝尔量子几何仍表现出局域 Jacobi 型相关和朝协方差匹配 Wick 零假设收敛的有限尺寸流，同时保留可分辨的非高斯结构记忆。要提高上限，需要把“一个构造中的有限尺寸观察”至少升级为以下三者之一：一个可推导的机制、一个跨模型的普适类、一个可检验的新后果。单纯扩大同一模型的 Monte Carlo 样本、增加曲率统计量或把随机矩阵维数推得更高，只会提高精度，不会改变主张的逻辑等级。

最优研究组合是：现有 PRL 包不继续等待，保持其聚焦并进入投稿；随后以“机制优先、独立模型复现、可观测后果”为三个升级阶段发展一篇更高上限的后续工作。若只能选择一个下一步，应先做同一精确保护框架中的第二局域算符类，并同时推导以有效通道数为尺度的四点连通量衰减律。它最便宜，也最直接判断当前结果究竟是 Geometric ETH 普适性，还是仅属于密度型变形的特殊性质。

## 一、先学会区分“算得更多”和“知道得更多”

当前摘要中最弱的一句话可以抽象成：

> 在一个工程化的精确简并拓扑 parent family 上，我们观察到五个粒子数的有限尺寸流。

提高科学上限，本质上是改写这句话中的四个语法部件：

| 维度 | 当前状态 | 真正的升级 |
|---|---|---|
| 名词 | 一个 Kapit--Mueller 家族 | 一类精确简并流形、两种不同保护机制、或 SUSY/BPS 扇区 |
| 动词 | 数值观察 | 推导、证明、预测、分类 |
| 量词 | \(N=3,\ldots,7\) 的有限尺寸趋势 | 受控渐近律、跨模型数据塌缩、或有假设的定理 |
| 后果 | 一个新的诊断量 | 对慢驱动、参数回波、Wilson 传输、OTOC 或简并解除交叉的参数无关预测 |

一个新计算如果不改变这四项中的任何一项，它通常只是精度工作。精度工作可能是投稿审计所必需的，却很少提高期刊上限。

可以把科学主张分成五级：

1. **存在性：** 能谱沉默时，几何仍然非平凡。
2. **非冗余性：** 几何混沌与能谱混沌、Chern 数和秩可以独立变化。
3. **机制性：** 局域响应通道为何产生 Jacobi 相关和特定的非高斯修正。
4. **普适性：** 同一律跨算符类、模型或精确简并机制成立。
5. **后果性：** 该几何律决定一个独立可计算的动力学、输运或信息论效应。

现有论文已经可靠达到第二级，并且凭借精确 transported-kernel identity 进入了第三级的一部分。PRX 级别的自然目标是完整的第三级加第四级，或第三级加第五级。更宽领域的顶级期刊通常需要第四级和第五级至少有一个非常强，并且故事重新回到 BPS/黑洞问题或一个足够普遍的多体原则。实验不是硬门槛；没有机制、普适性和后果才是门槛。

## 二、六种真正能提高上限的杠杆

### 1. 从有限尺寸拟合升级为可推导的尺度律

当前 \(\delta_4\) 随 \(D\) 单调下降，并且有限尺寸信息偏好零截距的 \(1/D\) 形式，但五个尺寸不能区分严格趋零和很小的平台。下一步不应只是把 \(N=8\) 接在曲线上，而应先问：为什么尺度变量应当是 \(D\)，而不是外部空间维数、可达响应秩、通道参与率或某个相关长度？

理论目标是把响应写成受局域性和算符代数约束的协方差变形随机通道，

$$X_a\simeq\sum_b(C_{\mathrm{op}}^{1/2})_{ab}G_bC_R^{1/2}+\delta X_a,$$

然后在清楚写明的混合假设下，证明或推导连通四点量随有效独立通道数 \(M_{\mathrm{eff}}\) 抑制，例如给出 \(\delta_4\) 的上界、主导阶或可检验系数。这样，\(N=8\) 的作用才是区分理论预言，而不是帮助选择一个好看的拟合函数。

成功后的摘要动词会从“观察到下降”变为“推导并验证一个有限尺寸律”。即使最后得到非零平台，只要平台由局域可达代数决定并能跨算符类预测，它仍然是一种 deformed Geometric ETH 普适类，而不是失败。

### 2. 从单一密度变形升级为算符类普适性或分类

这是性价比最高的下一步。保持同一个精确零模 projector、相同粒子数序列和相同统计流程，只更换保护家族的生成元：从当前类型扩展到键、流或更长程但仍准局域的一体生成元。精确 transported-kernel 定理使这些方向无需重新解决完整 resolvent 问题，因此计算资源主要用于零模 frame 和相同的 panel aggregation。

关键结果不是“第二条曲线也下降”，而是下面两个互斥且都科学上有价值的分支：

- 不同算符类在以 \(M_{\mathrm{eff}}\) 或可达秩重标度后塌缩到同一曲线：支持一个受局域协方差变形的普适 Geometric ETH。
- 密度、键和流变形趋向不同的极限，但差异由可达算符代数或守恒律预测：得到 operator-class geometric phases 的分类。

第二个分支不比第一个差。真正糟糕的是只看到不同曲线，却没有能解释差异的结构变量。

### 3. 从一个工程化 parent family 升级为独立精确简并机制

这是抬高 PRX 上限最直接的方式。第二个模型必须消除第一模型最可能的替代解释，而不是仅仅改一个晶格参数。候选按目标分成三类：

- **近期最稳健：continuum LLL pseudopotential Laughlin 零模。** 它可以回答现象是否依赖 Kapit--Mueller 长程跳跃和晶格构造。若相同的白化四点律出现在 continuum torus 上，主张从“某个晶格 parent”升级为“Laughlin 零模流形”。
- **拓扑上限最高：Moore--Read 或 Read--Rezayi quasihole parent。** 这些流形本身具有非阿贝尔编织结构。可以研究确定的拓扑 braid representation 与局域随机曲率能否共存，并把“固定 Chern”升级为“固定非阿贝尔拓扑数据与混沌几何分离”。已有 lattice Moore--Read parent Hamiltonian 可以通过耦合变化移动和编织 quasiholes，这给出了自然参数空间。[Manna et al.](https://arxiv.org/abs/1807.11222)
- **与 seed paper 联系最强：SUSY/cohomological zero modes。** 构造 \(Q(\lambda)^2=0\)、\(H(\lambda)=\{Q,Q^\dagger\}\) 的精确零模流形，比较结构化和混沌超荷下的 Berry curvature。二维 supersymmetric lattice fermion 的零模可由 cohomology 精确描述，为此提供现成理论语言。[Huijse and Schoutens](https://arxiv.org/abs/0903.0784)

选择原则很简单：如果目标是尽快增强当前 PRL 的自然性，先做 continuum LLL 或第二个 FQH parent；如果目标是发展一篇真正回到黑洞/BPS 动机的后续论文，应优先 SUSY/cohomological 模型。不要同时搭建三个新平台，因为那会把理论问题稀释成软件工程。

### 4. 从“诊断”升级为“产生后果的定律”

Geometric ETH 最容易被质疑为“又一个看起来像随机矩阵的统计量”。最强回应不是更多随机矩阵图，而是证明它控制一个独立响应。

最自然的对象是小参数回路。沿 \((\lambda^a,\lambda^b)\) 平面走一个面积为 \(\mathcal A\) 的小矩形，简并子空间中的 holonomy 满足

$$U_{\square}=\exp\!\left(iF_{ab}\mathcal A+O(\mathcal A^{3/2})\right).$$

因此返回概率、\(\operatorname{Tr}U_{\square}\) 的矩、连续随机小回路的非阿贝尔扩散，以及非高斯修正，都可以由曲率二点和四点 cumulant 预测。若能从现有 \(X_a\) 的 Wick/connected decomposition 推出一个无额外拟合参数的 geometric echo 或 Wilson-loop 统计，并在独立数值演化中验证，论文就从“定义一个 chaos diagnostic”升级成“发现一个控制参数空间动力学的统计定律”。

第二条桥梁是绝热规范势。\(X_a\) 正是 AGP 的 fiber-to-complement block；AGP 已被证明对可积性破缺和量子混沌敏感。[Pandey et al.](https://arxiv.org/abs/2004.05043) 可以尝试推导简并 projector 版本的 Kubo/AGP identity，并比较轻微解除简并后的谱统计交叉。重点必须是一个推导出来的 crossover relation，而不是两张相关性图。

第三条桥梁是 generalized/full ETH。标准 ETH 的二点信息不足以决定 OTOC，高阶矩阵元相关和 free cumulants 才是关键。[Foini and Kurchan](https://arxiv.org/abs/1803.10658)；[Pappalardi, Foini, and Kurchan](https://arxiv.org/abs/2204.11679)；[Pappalardi, Fritzsch, and Prosen](https://arxiv.org/abs/2303.00713) 当前四通道残差可以被明确解释为简并几何版本的 connected free cumulant；若能证明它决定一个参数空间 OTOC 或 echo correction，就把 “Geometric ETH” 从命名提升为真正与 full ETH 同构的框架。

### 5. 从固定 Chern 反例升级为 topology-constrained random process

现有受控结果证明了完整能谱和 \(C_1\) 固定并不决定非阿贝尔 Wilson holonomy，但 ambient conjugation 是人为设计的，并且 holonomy 仍非 CUE。更高上限的版本应在自然物理 moduli 上研究 \(U(D)\) holonomy 的分解：拓扑约束控制 determinant/\(U(1)\) 扇区，而 traceless \(SU(D)\) 扇区是否趋向一个 Brownian、free-unitary 或 covariance-deformed 过程。

一个值得追求的定理结构是：固定 Chern 数约束 \(\det U_\gamma\)，但在满足局域混合条件时，\(SU(D)\) holonomy 的低阶 cumulants 按独立规律衰减。数值上应使用 twist、interaction metric、quasihole position 或超对称 coupling 等自然参数，而不是仅使用 ambient orbit。若在 Moore--Read 或 \(\mathcal N=2\) SYK/SUSY 零模中实现，这条路线可直接承接 seed paper 关于 moduli-space topology 和大 Chern 数的主线。[Chen et al.](https://arxiv.org/abs/2604.23287)

### 6. 从正面现象升级为必要性、充分性和 no-go 边界

高水平理论论文不一定需要所有结果都“更随机”。一个严格的失败边界同样能提高上限，例如：证明有限范围、守恒律或低可达秩必然保留某个非高斯 cumulant；证明某类 frustration-free deformation 永远不可能达到完整 CUE；或者证明拓扑只约束 central sector 而不能约束 traceless curvature。这样的 no-go theorem 会把当前的“deformed”从有限尺寸不完美变成一个新 universality class 的定义特征。

设计计算时要包含干预而不只是对照：固定 \(P\) 改变 \(PHP\)、固定能谱改变 \(P(\partial H)Q\)、固定拓扑改变局域连接、固定 covariance 改变高阶 cumulant。只有这种“保持其他量不变”的实验，才能回答必要性和充分性。

## 三、三条完整路线及其取舍

### 路线 A：机制优先——第二算符类加尺度理论

这是推荐的下一步，也是单位计算资源信息增益最高的路线。

**核心问题：** \(\delta_4\) 的下降是简单局域算符经过巨大外部通道混合后的中央极限定律，还是当前密度型变形的特殊性质？

**理论工作：** 推导可达支持、左右协方差和 connected four-point tensor 的有限 \((D,M,m)\) 结构；定义从协方差谱得到的 \(M_{\mathrm{eff}}\)；给出 \(\delta_4(M_{\mathrm{eff}})\) 的主导预测或上界。

**数值工作：** 在完全相同的 \(N=3,\ldots,7\) kernel 上运行固定的 bond/current panels；保持 whitening、Gaussian null、bootstrap 和阈值不变；比较按 \(D\) 和按 \(M_{\mathrm{eff}}\) 的 collapse；只有在两个候选渐近行为在 \(N=8\) 上给出可分辨差异时才启动 \(N=8\)。

**成功主张：** “一类精确保护多体流形遵循由可达通道数控制的 covariance-deformed Geometric ETH。”

**失败后的可发表主张：** “局域算符代数定义不同的 geometric universality classes。”

**上限判断：** 足以明显稳固 PRL；若理论结果具有一般性并且跨算符类 collapse 成功，可成为 PRX 结构的核心，但单靠它通常还不足以支撑 Nature Physics 级别的广泛物理影响。

### 路线 B：普适性优先——第二种精确简并机制

**核心问题：** Geometric ETH 是 Laughlin/Kapit--Mueller 构造的性质，还是精确简并多体流形的一般现象？

**近期版本：** continuum LLL Laughlin 或独立 CFT lattice parent，复用同一 gauge-invariant cumulant pipeline。

**高风险高回报版本：** Moore--Read/Read--Rezayi 非阿贝尔 quasiholes，或 SUSY/cohomological zero modes。前者把拓扑编织与几何混沌放在同一框架中，后者把工作直接送回 BPS 黑洞动机。

**成功主张：** “不同物理保护机制在 whitened response space 中共享同一几何统计律，而 central/topological data 保持模型特异。”

**失败后的价值：** 若 FQH 成功而 SUSY 失败，或反之，结果会定位 Geometric ETH 的适用条件；这比盲目声称普适更有理论价值。

**上限判断：** 独立模型复现加共同尺度变量是最清楚的 PRX 升级；若同时产生 BPS/黑洞新结论，则有资格把 Nature Physics 作为高风险目标，而不依赖实验。

### 路线 C：后果优先——geometric echo、AGP 或 topology-constrained holonomy

**核心问题：** 几何 cumulant 除了诊断混沌，还决定什么？

**理论工作：** 从小回路展开或慢驱动 Kubo 公式导出可观测量，明确二点项、Wick 项和 connected four-point correction；给出不从验证数据重新拟合的预测。

**数值工作：** 用独立的有限回路或时变 coupling 演化验证预测；构造结构化和混沌 family，在相同能谱/拓扑约束下比较回波扩散；必要时加入受控简并解除来连接普通 level statistics 和 OTOC。

**成功主张：** “Geometric ETH 决定简并多体流形中的参数空间信息扩散/非阿贝尔回波。”

**风险：** 如果最终只有 AGP、OTOC 和 \(R_4\) 的经验相关，这条路线不会抬高上限；必须有 identity、sum rule 或参数无关预测。

**上限判断：** 一个清楚的新后果能显著扩大受众，并给 PRX 级故事提供第二条腿；若再与 BPS moduli 或非阿贝尔任意子结合，可能成为最有辨识度的长线方向。

## 四、超算应该如何使用

超算的价值不是“把所有尺寸都算一遍”，而是让互相竞争的理论预言变得可分辨。每个大任务提交前，必须能回答三句话：

1. 如果成功，摘要中哪一个名词、动词或量词会变强？
2. 它消灭哪一个具体替代解释？
3. 如果失败，是否会自动落入另一个事先定义的科学分支？

推荐的计算顺序是：

1. 复用 \(N=3,\ldots,7\) kernels，完成第二 bond/current 算符类。它检验 universality，成本远低于新模型。
2. 同时完成 \(M_{\mathrm{eff}}\) 理论和无需高阶数据拟合的曲率/四点预测。只有理论能区分候选趋势后，才决定是否需要 \(N=8\)。
3. 若算符类 collapse 成功，选择一个独立自然机制。以近期论文为目标选 continuum LLL；以长线高上限为目标选 SUSY/cohomological 或 Moore--Read。
4. 在普适结构明确后，推导并验证小回路 geometric echo。这样后果建立在一个稳定定律上，而不是建立在单个模型的漂亮图上。

明确的止损条件：

- 第二算符类不 collapse 时，不继续用更多尺寸强迫单一 \(1/D\) 拟合；转向 operator-class classification。
- \(N=8\) 只有在零极限与平台模型对该点作出可分辨预测时才值得做；否则它只是更昂贵的第六个点。
- 独立模型若无法维持精确简并、固定 nullity 和开隙，就不能承担“exact-degeneracy universality”的主张；应保留为解除保护的 crossover 对照。
- 动力学路线若不能得到参数无关关系，就暂不进入主论文。

## 五、如何预判审稿人的真正 objections

把审稿人想象成依次提出五个问题：

1. **这是数值或 gauge artifact 吗？** 现有 frame invariance、solver residual、结构化 control 和 fail-closed audit 已经较好解决。
2. **这只是有限尺寸拟合吗？** 需要理论尺度变量、额外判别尺寸或严格界。
3. **这只属于 Kapit--Mueller/这个生成元吗？** 需要第二算符类和独立模型。
4. **为什么会出现这个统计律？** 需要 locality/accessibility/mixing 的机制。
5. **除了新统计量，它改变了什么物理？** 需要 geometric echo、topology-constrained process、AGP/OTOC bridge 或 BPS 新预测。

当前最值得花资源的是第二到第四个问题，而不是继续加固已经很强的第一个问题。

## 六、期刊上限与项目组织

现有 v5 Letter 已经是一个聚焦、可审计、适合立即尝试 PRL 的包。继续把所有长线路线塞进当前 Letter 会损害它的中心悖论，也会延迟一个已经形成闭环的结果。因此建议采用“双轨制”：

- **当前论文：** 冻结 v5，完成作者元数据和公开归档后投稿 PRL。它的主张保持为 exact spectral silence 加 protected deformed Geometric ETH，并明确有限尺寸与单模型边界。
- **上限论文：** 以路线 A 为起点；若跨算符类成立，进入路线 B；若得到共同定律，再做路线 C。这样每一步都能单独形成科学分支，失败不会摧毁整个项目。

大致的上限映射不是录用保证，而是主张结构判断：

| 新增内容 | 主张升级 | 合理上限 |
|---|---|---|
| 仅增加 \(N=8\)、样本数或曲率图 | 更精确的同一观察 | 不改变期刊层级 |
| 第二算符类加理论尺度律 | 机制或 operator-class classification | 强化 PRL；广义定理可触及 PRX |
| 独立精确简并模型加共同 collapse | 跨机制普适性 | PRX 成为实质性目标 |
| 普适律加参数无关动力学/拓扑后果 | 新原则和新预测 | 强 PRX；更广期刊的必要条件之一 |
| 回到 SUSY/BPS 并产生 seed paper 之外的新定理或预测 | 统一 condensed matter 与 black-hole microstates | Nature Physics 级高风险上限，不要求实验但要求广泛概念影响 |

## 七、以后独立判断研究方向的方法

每当出现一个新想法，先做“摘要句测试”，不要先写代码。把成功结果写成一句话，并检查它改变的是哪一个部件：

> 我们在【什么对象】上【观察/推导/证明】了【多大范围成立的规律】，它【排除了什么替代解释】并【预测了什么新后果】。

如果新想法只能填入“多算了一个尺寸”或“又画了一种分布”，它的科学信息增益通常低。若它能把“一个模型”改成“一类模型”，把“观察”改成“推导”，把“有限尺寸”改成“共同尺度律”，或者增加一个不能由原数据自动保证的新后果，它才真正提高上限。

最后再做“反事实测试”：假如结果与预期相反，是否仍能形成清楚结论？好的研究设计至少有两个可发表分支；坏的设计只有在曲线朝想要的方向走时才有故事。当前项目的最好反事实正是：统一 collapse 对应 Geometric ETH，稳定分裂对应 operator-class geometric phases，非零平台对应 locality-protected deformed ETH。这样超算不是用来赌博，而是用来在有限个理论分支之间做决定。

## 参考文献与原始来源

- [Y. Chen et al., *Chaos of Berry curvature for BPS microstates*](https://arxiv.org/abs/2604.23287)
- [E. Kapit and E. Mueller, *Exact Parent Hamiltonian for Quantum Hall States in a Lattice*](https://arxiv.org/abs/1005.3282)
- [P. Pandey et al., *Adiabatic Eigenstate Deformations as a Sensitive Probe for Quantum Chaos*](https://arxiv.org/abs/2004.05043)
- [L. Foini and J. Kurchan, *Eigenstate thermalization hypothesis and out of time order correlators*](https://arxiv.org/abs/1803.10658)
- [S. Pappalardi, L. Foini, and J. Kurchan, *Eigenstate thermalization hypothesis and free probability*](https://arxiv.org/abs/2204.11679)
- [S. Pappalardi, C. Fritzsch, and T. Prosen, *General Eigenstate Thermalization via Free Cumulants in Quantum Lattice Systems*](https://arxiv.org/abs/2303.00713)
- [M. B. Hastings and X.-G. Wen, *Quasi-adiabatic continuation of quantum states*](https://arxiv.org/abs/cond-mat/0503554)
- [S. Manna et al., *Non-Abelian quasiholes in lattice Moore--Read states and parent Hamiltonians*](https://arxiv.org/abs/1807.11222)
- [L. Huijse and K. Schoutens, *Supersymmetry, lattice fermions, independence complexes and cohomology theory*](https://arxiv.org/abs/0903.0784)
