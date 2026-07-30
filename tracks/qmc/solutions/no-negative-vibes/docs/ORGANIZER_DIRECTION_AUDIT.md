# 主办方候选方向完成度审计

更新时间：2026-07-28

## 结论

主办方列出的方向没有全部确认完。我们已经完成了经典群与标准 Hermitian AZ 表的第一轮
系统筛查，理论闭合了 `U(p,q)` 的中心相位规律，解析关闭了 Majorana 和 split-contraction
两种旋转双锥候选，并得到一个可严格证明的全非负路径半群；但以下核心问题仍然开放：

1. TN/DQMC 表述的完整引用链排重；
2. `arXiv:1601.01994v2` 复 Majorana 条件的简洁矩阵定理；
3. BDI/AII/DIII/CII 的完整 BdG/Pfaffian 半群锥；
4. 新得到的奇数阶 positive-monomial / block-TN 半群的文献排重与局域 HS 映射；
5. 超出普通一维开放链的新物理模型与 HS 映射。

TN 与 2024 条件的代数排重已完成：整个 TN 类同时包含 `+D/-D`，因此不能属于固定实
收缩锥；在 Majorana 表示中也不存在满足 2024 条件的固定 `J_2`，包括固定复正交换基。
TN 还已有排斥 `t-V` 键门的精确非对称辅助场分解；但连续 TN、TN 高斯正和和逐粒子数
独立符号规范都已证明无法把普通 hopping 图推广到环或真正分支，所以它仍未产生新
Hamiltonian。

主办方原始清单见
[challenge #121](https://github.com/QuantumBFS/quantum.harness/issues/121)。

## 状态标准

- **已关闭**：命题范围明确，并有精确证明或精确反例。
- **第一轮完成**：固定表示下完成系统扫描和排重，但不能代表所有维数、所有表示或所有物理权重。
- **部分完成**：已有 oracle、样本或局部结论，主命题仍未解决。
- **未开始**：尚无专用生成器、协议和可复核结论。

## 逐项对照

| 主办方候选方向 | 当前状态 | 已经完成 | 还缺什么 |
|---|---|---|---|
| `Sp(2n,R)` 与其他经典群 | **`Sp(2,R)`、`Sp(4,R)` 已关闭；整张经典群表第一轮完成** | 90 万次扫描；`Sp(2/4,R)` 有精确负权证书；`SL`、`SU(p,q)` 等自然候选完成淘汰或已知机制归类 | 不声称穷尽所有秩、表示和子群；只有出现精确嵌入反例的族可直接推广关闭 |
| split unitary `U(n,n)` 的相位约束 | **理论闭合；新颖性低** | 已证明 `conj(w)=det(D)^(-1)w`，即 `arg(w)=arg(det D)/2 mod pi`；中心相位可遍历圆周，剩余符号也可正可负 | 需要在报告中明确它是排重/符号缓解结论，不是新单 flavor 无符号类 |
| AZ 十重对称类周期表 | **标准 Hermitian `4 x 4` 第一轮完成** | 72 万次扫描；六类精确失败；BDI、AII、DIII、CII 约化到已知 split-orthogonal/Kramers 机制 | 不是完整 BdG/Pfaffian 分类；未覆盖任意表示、非 Hermitian Majorana 生成元和各类的半群锥 |
| 每个幸存群项的半群锥推广 | **数守恒自然锥第一轮完成；完整 BdG 仍开放** | 除 15 族、139.2 万权重和 TN 严格证明外，新完成 BDI/AII/DIII/CII 七族、14 万权重专用协议；三个幸存者均保留已知 split/Kramers 对称，BDI 两面锥有解析反例，另三个放松项有 80 位复权 | DIII/CII 数值反例尚待符号化；完整非 Hermitian Majorana、pairing、Pfaffian/Spin-trace 锥不在本轮覆盖内 |
| 复 Majorana positivity 的简洁矩阵表述 | **部分完成，主命题未解决** | 有直接 Fock/Spin 迹 oracle、固定 `J1,J2` 的规范块表示、行列式平方交叉检查和精确反例库 | 尚未把 `1601.01994v2` 的全部复条件压缩为主办方要求的简单 determinant/Pfaffian 矩阵定理 |
| AI 自拟结构化生成元集合 | **取得两个严格恒正矩阵机制候选** | TN 路径之外，新得到奇数阶 positive-monomial / block-TN 循环因子化定理；偶阶路由、moving metric、双向 reciprocal 和 near-commuting 均有反例 | 两类都必须完成文献优先权与新物理映射，不能把已知矩阵数学本身冒充首创 |
| 具体 Hamiltonian 与 HS 分解 | **已有精确非对称算法映射，Hamiltonian 创新性未闭合** | 除两个密度 HS 基线外，已证明 `t-V` 局部键门是两个非对称 TN 高斯传播子的精确正和；重叠键无固定共同 Hermitian 度量 | 开放一维无符号本身已知；普通环/分支又被交换符号 no-go 关闭，需转向配对、相关 hopping 或非平凡 gauge/ancilla 编码 |

## 大规模候选覆盖表

累计 `4,044,000` 个主权重，另加 640 条宇称分辨 Majorana 历史，不等于穷尽候选空间。
当前覆盖应这样理解：

| 候选池 | 是否已有大规模扫描 | 当前判断 |
|---|---|---|
| 15 个经典群/李代数族 | **是：900,000** | 低维精确反例可嵌入的整族已关闭；不需要继续堆同类样本 |
| 标准 Hermitian AZ 十类 | **是：720,000** | 固定 `4 x 4` 表第一轮完成；不是任意表示或完整 BdG/Pfaffian 分类 |
| 共享 `J1`、旋转 `J2` 的 Majorana 双锥 | **是：700,000** | 已由任意小夹角解析反例关闭，不需继续随机扫 |
| 15 个路径/图/混合锥/分块半群 | **是：1,392,000** | 朴素图扩展和完整旋转 split-cone 并集关闭；TN 路径存活并已证明 |
| BDI/AII/DIII/CII 幸存结构的数守恒半群锥 | **是：140,000** | 自然 PSD/metric-cone 第一轮完成；非平凡放松均失败，零失败者均约化到已知 split/Kramers |
| 12 个激进路由/表示/范数候选 | **是：192,000** | odd monomial、odd block-TN、fixed norm 和 reciprocal 严格幸存；四个放松失败；`D_4` 约化到已知 split |
| Majorana 宇称分辨 | **是：640 条历史** | canonical convention 下的 period-4 数值猜想；互补扇区有 float64 负权，尚无任意精度重放 |
| 完整复 Majorana 非 Hermitian/配对生成元 | **否** | 只扫过一个旋转双锥切片；主办方要求的复矩阵定理仍未完成 |
| 比 TN 更大的主子式/外幂锥半群 | **部分完成** | odd monomial 是新的 `P0` 乘法半群候选；非诱导 exterior-cone 仍未开始 |
| 物理可达的受限锥交集 | **否** | 必须从具体 Hamiltonian/HS 反推，不能用无物理来源的整锥随机矩阵代替 |
| 非平凡 gauge/ancilla、宇称串相关 hopping | **第一版完成** | edge-electric Gauss law 加 affine link phase 在四/六模式上精确消号；`2 x L` 中央 hop 被证明需要全部其他竖边，形成 Wilson string。modified-Gauss projected cone 仍开放 |
| 配对/Majorana/Pfaffian 物理模型 | **否** | 现有 determinant AZ 扫描不能替代 Pfaffian/Spin-trace 权重检查 |

所以仍有大候选池，但不应立刻把每一行各采一百万个任意矩阵。下一轮合理的大扫对象是：

1. `complex-Majorana-structured-v1`：在复矩阵定理写清后，对物理允许的 pairing/HS
   子空间做 Spin-trace 与 Pfaffian 联合扫描；
2. 对 odd monomial / block-TN 做完整文献排重和局域 HS 反推；
3. 只有上述某个结构化候选在小维对抗搜索中存活，才扩大到 `10^6` 量级。

odd monomial 已给出一个更大搜索空间中的严格 `P0` 候选；非诱导外幂锥仍处在定义
候选阶段。第一版 edge-electric 物理编码已有精确 Wilson-string 障碍，只有
modified-Gauss projected cone 写出正 transfer matrix 后才值得大扫。

## 哪些结论可以直接对外说

可以说：

- `Sp(2n,R)` 的普遍恒非负性已由低维精确嵌入反例排除；
- 当前规范下的标准 Hermitian AZ 十类没有产生新类；
- 共享 `J1`、允许时间层使用不同旋转 `J2` 的完整 Majorana 双锥并集不是无符号类；
- 任意小非零夹角都有精确两层 Majorana Fock 负权。
- 三对角 Metzler 路径生成元给出严格全非负半群，因此 `det(I+D)>=1`；
- TN 类不约化到固定 Kramers、split/contraction metric 或 Wei 2024 Majorana 条件；
- 排斥 `t-V` 键门有精确非对称 TN 高斯正和实现；
- 对普通 hopping，连续 TN、TN 正和及逐粒子数独立符号规范都只能保留开放路径；
- 两个不同旋转 split-contraction cones 的完整并集对任意非平凡主夹角都有两层负权。
- 标准 `4 x 4` 数守恒 AZ 自然半群锥已完成 14 万权重初筛：非平凡放松全部失败，
  三个零失败者均是已知 split/Kramers 机制。

不能说：

- “主办方给出的所有候选已经验证完”；
- “整个 AZ 十重分类在所有 QMC 表述下已经完成”；
- “复 Majorana 的开放矩阵表述已经解决”；
- “我们已经发现新的物理无符号类”；目前 TN 数学成立，但一维物理基线已知。

## 推荐顺序

1. 排重 odd monomial / block-TN 的 `P0` 与 generalized-permutation 文献；
2. 为离散 odd grade 反推局域可采样 HS，并继续 TN 的物理映射；
3. 在 canonical convention 下证明或推翻 Majorana 受保护宇称公式；
4. 复 Majorana 已知条件继续整理为 determinant、Pfaffian、Spin-trace 三层支撑语言。
