# 正矩阵成果的 Hamiltonian 再评价：设计说明

日期：2026-07-30
状态：已获用户批准，进入执行
分支：`codex/positive-hamiltonian-reappraisal`

## 1. 目标改写

本轮不再把“矩阵正性定理本身必须数学新颖”当作硬门槛。真正的目标是：

> 从全部既有正性机制中构造可扩展、可采样的 Hermitian Hamiltonian，并找到至少一类
> 不能被现有常规手段直接模拟、且物理上尚未被充分研究的 QNC 体系。

已知矩阵定理可以产生新的物理模型；反过来，一个新矩阵恒等式若只对应自由、可积、
stoquastic、静态扇区或简单平方模型，也不算积极成果。

## 2. 两层积极成果

### 主成果

满足以下六个条件的 Hamiltonian 家族：

1. 给出显式、随系统尺寸 `L` 定义的 Hermitian `H_L`；
2. 说明支撑、体数、耦合缩放和热力学极限；
3. 给出任意历史深度的非负权证明与实际 QMC 顶点；
4. 排除直接 Jordan-Wigner、局域符号规、stoquastic/worldline/SSE、
   自由费米子/matchgate、静态扇区、偶 flavor 平方和简单固定基变换；
5. 给出非平凡可观测量或相结构问题；
6. 完成定向文献核对，确认模型或其可模拟区间未被充分研究。

### 加分成果

在主成果之外，再证明正性机制本身不是已知 TN、Kramers、Majorana reflection、
split orthogonal、公共收缩范数、三角因子化或共轭平方的换皮。

数学机制的新颖性是加分项，不再是一票否决项。

## 3. 评价流水线

每个旧候选依次经过以下 gates：

1. `HAMILTONIAN`：是否有显式 `H_L`，而不只是单粒子矩阵集合；
2. `SCALING`：是否可控制 `||H_L||/L`、支撑和 ancilla 密度；
3. `QMC`：是否有逐配置非负权和多项式代价的更新/测量接口；
4. `EXCLUSION`：传统模拟方法是否有明确的排除证书，而不是口头判断；
5. `PHYSICS`：是否有不被正性强行冻结的可观测量和参数区；
6. `LITERATURE`：是否有可引用的模型级空白。

任何候选都可以保留在较低层级；只有六关全部通过才记作 QNC 主成果。

## 4. 非冲突研究边界

### 本分支拥有

- 固定 partition 的 odd block-TN 全局同步 Hamiltonian；
- odd positive-monomial / graded-monomial 的物理模型再评价；
- 固定加权 `l_infinity` 收缩类的 Hamiltonian 化；
- reciprocal-parabolic 三角类的 Hermitian 化或 no-go；
- 上述候选的传统方法排除协议、候选总账和文献卡。

### 仅登记，不执行

- ZiboJin 的 `work/zibo/representation-cones`：
  exterior cones、seed61、oddcycle seeds `117/132/147`、共同 metric、
  joint-pair/coupled-tail 与 oddcycle Hamiltonian portfolio；
- ZiboJin 的 `work/zibojin/tensor-square-phase-diagram`：
  `m=3,4` ED/DQMC、低温稳定化与相图。

本分支不会运行 tensor-square 相图扫描，不会延伸 oddcycle seed/joint-pair，
也不会重新搜索 exterior exact cards。协作者结果只作为排重输入。

## 5. 首轮优先级

1. **R1 fixed-partition odd block-TN**：已有任意深度证明和 Hermitian 工厂；
   自然局域化虽被 `det(I+XR)=-2` 关闭，但全局同步 synthetic route 尚未做
   extensivity、可采样性和传统方法排除。
2. **R2 fixed weighted `l_infinity`**：允许稠密有符号生成元；先判断强衰减保护
   是否仍容许非平凡有限密度物理。
3. **R3 reciprocal-parabolic**：先做 Hermitian 化/no-go，防止把单向三角装饰
   误当成新动力学。
4. **R4 graded/odd monomial**：底层 cycle 公式已知，但可能产生未被研究的
   离散 route Hamiltonian；优先查静态扇区和 JW/stoquastic 约化。

## 6. 证据纪律

- “没找到变换”不等于“不可模拟”；每种排除必须有有限尺寸精确证书、
  一般代数论证或清楚的条件性声明。
- 小尺寸 ED 只能发现约化或反例，不能单独证明热力学新颖性。
- 文献检索在 Hamiltonian 固定后进行，避免用宽泛关键词替代模型级排重。
- 已关闭路线保留反例与停止条件，不重复投入扫描预算。
- draft PR 是持续更新的研究记录；结论随证据升级，不预先宣称发现。

## 7. 首个交付

本次 bootstrap PR 同时提交：

- 这份已批准设计；
- 精确到文件和测试的执行计划；
- 覆盖全部旧成果的再评价总账；
- R1 odd block-TN 的首份 Hamiltonian 化审计与下一步可证伪问题。
