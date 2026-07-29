# 下一阶段研究计划

更新时间：2026-07-29

## 当前判断

外围的低成本候选已经清理得足够充分：

- `Sp(2n,R)` 等明显失败族有精确反例；
- 标准 Hermitian AZ 表完成第一轮；
- `U(p,q)` 连续相位由初等恒等式闭合，但不产生新无符号类；
- 自拟的共享 `J1` 旋转双锥被任意小角解析反例关闭。
- 15 个新半群候选的 139.2 万权重筛选已完成；图扩展、逐片换规范和双向分块耦合均被淘汰；
- 得到严格全非负路径半群：三对角 Metzler 生成元对任意维数、深度满足
  `det(I+D)>=1`；
- 得到排斥 `t-V` 局部键门的精确两场 TN 高斯分解；正 `kappa` 时场传播子非对称，
  三站点重叠键不存在固定共同 Hermitian 化度量；
- 证明连续 TN 半群在恒等元的切锥只能是三对角 Metzler，因此仅靠无穷小 TN 动能无法
  直接容纳环、分支或远邻 hopping；
- 进一步证明数守恒 TN 高斯算符在 Fock 基中的矩阵元全为非负子式，故任意正和也无法
  表示普通非相邻 hopping 的占据依赖符号；无 ancilla 的直接正和路线已关闭；
- 把条件放宽到各粒子数扇区独立固定符号规范后，证明普通 hopping 图全扇区无挫折当且
  仅当各连通分量为路径；2–6 站点全连通图穷举只有 `N!/2` 个标号路径幸存；
- 两个不同旋转 split-contraction cones 的完整并集也被任意小角两层解析反例关闭。
- BDI/AII/DIII/CII 七个自然数守恒半群锥已完成 14 万权重初筛；四个非平凡放松项出现
  负权或复权，三个零失败项分别约化到已知 split/Kramers 机制。
- graded monomial 已约化到已知 `su(1|1)` 顶点和 Majorana reflection positivity；
  奇数阶 fixed-partition block-TN 虽有严格正性证明，但最自然的局域闭包已由两站点、
  三 flavor、两层精确反例 `det(I+XR)=-2` 关闭。
- R01 fixed Klein-Hodge/Fock 变换的六模式重叠锥已由 24 个 bridge 坐标的 exact-zero
  证书关闭；结论只针对该固定变换和双 parity-block Metzler 条件。

接下来不应继续增加同分布随机扫描。TN 路径、graded monomial、odd block-TN、R01
fixed transform、有限 Klein-circuit Fock–CP 和 tensor-square 直接物理提升均已得到
明确边界。edge-electric gauge/cocycle 的 GF(2) 符号抵消虽然成立，却被迫形成
system-size Wilson string；这一简单 ansatz 也已关闭。下一主线进入
**non-induced exterior cone**，从六模式重叠块直接要求 Fock-sector 正锥不来自普通
单粒子矩阵的外幂。modified-Gauss-law 只在出现具体正 transfer matrix 时重开。
Majorana 宇称猜想保留为独立支线，不再阻塞新机制搜索。
“复 Majorana 简洁矩阵语言”作为必要支撑工具：做到足以可靠排重、判断 Spin/Pfaffian
分支和检验候选。

## 主线 A：发现新的物理无符号类

### 为什么不只继续列举 Lie 群

对一个群要求 `det(I+g)>=0` 对所有元素、逆元和任意乘积都成立，条件非常强。当前经典群
扫描显示，自然候选通常：

- 很快出现低维精确反例；
- 或由共轭/Kramers 谱配对解释；
- 或退化为已知 split-orthogonal 恒等分支。

已知的重要扩展来自“群 + 单向半正定锥”形成的半群，而不是更多群名。因此这里的“新类”
优先指不约化到现有 split-orthogonal、Majorana/Kramers 或 2024 contraction-semigroup
条件的结构化半群，同时必须能由实际 HS 时间片产生。

### 当前候选池

按优先级研究：

1. **spinor-Metzler 与非诱导 exterior cone**：直接在 Fock/Spin 表示中寻找正锥，
   要求它不是任意单粒子非负矩阵通过外幂表示的平凡提升；
2. **Fock–CP / Choi 正锥**：把六模式 Fock 空间识别为 `End(C^8)`，先枚举固定的局域
   tensorization/Klein/Clifford 变换；对固定变换编译条件完全正 SDP，并逐个锚定 R01
   的 bridge hopping/pairing 坐标；**identity 与深度不超过 2 的连续 Klein 电路已
   完成，520 个单元的 bridge 全部在线性 Hermiticity 门归零，一般 non-Klein 变换开放**；
3. **局域 gauge 投影与 overlap 2-cocycle**：在四格方环和两个共享边方环上，把费米
   交换符号的局域抵消写成 `GF(2)` 可行性问题；**edge-electric affine ansatz 已精确
   消号，但在 `2 x L` 上需要读取其余全部 `L-1` 条竖边，因此因 Wilson string 降级**；
4. **Majorana 宇称分辨半群**：把当前 period-4 数值规律写成精确命题，重放互补扇区
   的最小负例，并从 2016 reflection-positivity 证明判断受保护扇区是否真有乘法闭包；
5. **tensor-square 表示提升半群**：一般恒正定理保留；四模式 HS 已约化到 split
   `O(2,2)`，`m>=3` 直接提升又有行列条带。只有出现非条带局域拼接才重开；
6. **非平凡 ancilla 编码或宇称串 hopping**：两站点排斥键门证明正和可实现相互作用，
   但普通远邻 hopping 被扇区符号 no-go 关闭；简单 Fock ancilla 投影/偏迹仍保持矩阵元
   非负，也无效。下一步必须显式改变物理 Hilbert 空间/规范约束，或使用相关宇称串；
7. **非平凡耦合的分块半群**：各子系统分别有不同的 `J1,J2`，允许受限跨块耦合，但整体
   不存在一个把它直接约化到已知类的固定全局 `J1,J2`；
8. **AZ 幸存结构的完整 BdG/Pfaffian 锥**：自然数守恒 metric-cone 已筛完；下一轮必须
   允许真实 pairing，并用 Pfaffian/Spin trace 而非只看 determinant，再逐项排除已知
   Majorana/Kramers/2024 半群；
9. **物理约束产生的受限锥交集**：不是任意两个正锥的并集，而是某个 Hamiltonian/HS
   分解实际可达、且在乘法下闭合的子集；
10. **伪酉相位消除后的剩余结构**：只有当 HS 标量前因子能物理地消去中心 `U(1)` 相位，
   并有额外机制控制剩余 `Z2` 符号时才继续。

### 候选进入计算前的硬门槛

每个候选必须先写清：

```text
矩阵定义
乘法/时间层闭包
与所有已知类的区别
候选 Hamiltonian 与 HS 来源
实际物理权重是 determinant、Pfaffian 还是 Spin trace
```

缺少物理来源或闭包的候选不进入大扫描。

### 发现漏斗

```text
候选卡与已知类排重
→ 2/4/6 维对抗性反例搜索
→ 失败则精确化最小反例
→ 存活则扩大到 10^6 个结构化样本
→ 证明半群闭包与非负性
→ 完整 Hamiltonian/HS 映射
```

随机扫描只负责淘汰；“新类”必须由一般证明和物理映射完成。

## 支线 B：复 Majorana 的必要矩阵表述

### 要解决的问题

对复反对称单粒子矩阵 `A_l`，区分三种对象：

```text
D = product_l exp(A_l),
determinant = det(I + D),
p = Tr_Spin(product_l exp(gamma^T A_l gamma / 4)).
```

它们满足 `p^2=det(I+D)`，但 determinant 看不到 `p` 的正负分支。目标是把 2016 Majorana
reflection/Kramers positivity 与 2024 contraction-semigroup 条件整理成不依赖算符口语的
矩阵定理，明确：

1. 输入矩阵、固定结构 `J1,J2` 和所有不等式；
2. `J1` 对称与反对称两种情形的规范块形式；
3. determinant、Pfaffian、Spin trace 各自能证明什么；
4. 平方根分支如何从恒等元连续选取；
5. 半群乘法闭包、边界零点和严格内部正性。

### 时间盒与交付

- 一页 theorem statement，不引用未定义的物理术语；
- determinant、Pfaffian、Spin trace 的关系和分支表；
- 与 2016 MTR、2016 positivity、2024 半群条件的可执行排重检查；
- `4/8` Majorana 回归测试。

这项工作限定为支撑主线的基础设施；除非推导中出现真正超出现有条件的新闭包结构，否则
不把“完整重写所有已知证明”作为近期主任务。

### 停止条件

- 若完全等价于现成定理：作为主办方要求的“clean matrix formulation”整理完成，不冒充新类；
- 若发现条件缺口：先用现有 Fock oracle 搜索最小反例，再决定证明还是淘汰；
- 在一般定理没有写清前，不做大规模随机扫描。

## 与主线同步：具体 Hamiltonian 与 HS 可达子集

### 已完成的基线

已经为两个模型完整写出：

```text
相互作用 Hamiltonian
→ Hubbard--Stratonovich 分解
→ 每个辅助场构型的 A_l
→ A_l 满足的矩阵条件
→ 逐构型权重
```

- 掺杂开放 Hubbard 链；
- 单 flavor 排斥 `t-V` 开放链。

二者的时间片都由 TN 开放路径动能和正对角 HS 因子组成，小系统全部辅助场构型已穷举。
但开放一维无符号是已知事实，所以它们只是新候选的物理基线。

在此基础上，已经为未平移的局部相互作用 `V n_i n_(i+1)` 推导出精确恒等式

```text
exp(-dt h_b) = [Gamma(B_+) + Gamma(B_-)]/2,
```

其中 `B_+/-` 都是可逆非对称 TN 矩阵。三站点上两条重叠键的四个场传播子不存在任何非零
共同实对称 intertwiner，所以不是一个固定全局换基下的 Hermitian 场集合。完整推导见
`TN_PHYSICAL_MAPPING_FRONTIER.md`。它解决了“抽象 TN 是否能由真实 HS 场产生”，但没有
解决“是否得到新 Hamiltonian”。

随后只允许加入物理上能产生的 hopping、pairing 或辅助场顶点，检查可达子集是否：

- 仍只是已有 Majorana/Kramers/半群类；
- 自动避开旋转双锥的秩一零权边界；
- 形成一个更小但可证明闭合的新锥或锥交集。

### 下一轮交付

- 请合作者/出题人复核已完成的 TN/2024 非包含证明；
- **已完成**普通三站点远邻 hopping 的 TN 高斯正和最小解析障碍；
- 一个非平凡 gauge/ancilla 编码或宇称串相关 hopping 的候选卡与可执行生成器；
- 现有 `kappa` 辅助场族的权重方差、条件数和更新代价基准；
- 明确的“已知一维重述 / 约化到 2024 / 真正值得继续”判断。

## 备线：公共收缩度量或受限锥交集

旋转完整双锥失败的根本原因是不同时间层没有共同的收缩度量。新得到的 split-cone 两层
公式 `16[1-q^2 sin^2(theta)]` 进一步表明任意非平凡主夹角都失败。新的数学候选必须比“共享
实结构 `J1`”更强，例如：

- 两套条件存在同一个正定或不定度量，使所有时间层同时收缩；
- 只取两个锥的物理可达交集；
- 对生成元范数、层数和离秩亏边界距离给出联合下界。

每个候选先写清封闭性和物理来源，再运行 oracle；不再从任意旋转矩阵开始盲搜。

## 执行顺序

1. **已完成**：`U(p,q)` 相位律、TN 路径严格证明、两个 HS 基线、139.2 万权重筛选、
   TN 对固定 Kramers/split/2024 条件的代数排重，以及精确非对称 `t-V` 键门分解。
2. **已完成**：`AZ-survivor-cones-v1` 的 14 万权重筛选；自然数守恒放松没有新幸存者。
3. **已完成**：graded monomial 已知类排重；odd fixed-partition block-TN 定理确认，
   以及其自然局域 crossed-partition 闭包的精确 `-2` 反例。
4. **协作完成**：R01 fixed Klein-Hodge/Fock 的六模式数守恒和 BdG bridge 坐标由
   exact-zero 证书关闭。
5. **已完成第一轮**：六模式 Fock–CP 的 13 个 depth-2 Klein 电路、20 种切分和
   数守恒/BdG 两族共 520 个单元；所有 bridge 在进入 SDP 前已归零。
6. **已完成物理闭环**：tensor-square 得到四模式方形 hopping 加排斥作用的正系数
   HS；最小模型属于 split `O(2,2)`，一般维数有条带非局域障碍。
7. **已完成第一版**：四/六模式 edge-electric gauge-cocycle `GF(2)` 消号成功；
   `2 x L` 中央跳跃的 affine phase 含全部其他竖边，局域可扩展性失败。
8. **立即开始**：non-induced exterior cone，尝试直接在六模式 Fock sectors 中越过
   连续路径、Fock 矩阵元和逐扇区规范三个 no-go。
9. **并行支线**：Majorana 宇称 period-4 猜想的精确重放和最小维证明/反例。
10. **按需补足**：完成 complex-Majorana/BdG 候选所需的 Pfaffian 与 Spin-trace 分支工具。
11. 只有未证明候选存活到至少 `10^6` 个结构化样本且没有已知类约化后，才扩大计算或上超算。

近期精力分配：

```text
45%  non-induced exterior cone
20%  modified-Gauss projected cone（仅限具体正 transfer matrix）
20%  non-Klein Fock–CP/Choi 结构
15%  Majorana 宇称与 Pfaffian/Spin-trace 支撑工具
```

## 两人协作建议

| 角色 | 近期任务 | 交付 |
|---|---|---|
| 数学/代码 | 新半群候选、已知类排重、对抗性反例搜索 | candidate definition + oracle |
| 物理/文献 | 为同一候选写 Hamiltonian 与 HS 分解 | candidate card + 可达矩阵 |

复 Majorana 工具由数学/代码侧按主候选需要补齐。两条线在“逐时间片 `A_l` 的明确公式”
处汇合；在此之前不需要超算。
