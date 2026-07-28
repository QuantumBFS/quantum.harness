# 文档导航

## 第一次接触这个挑战

读 [ONBOARDING.zh-CN.md](ONBOARDING.zh-CN.md)。它从行列式权重和符号问题讲起，
不要求量子蒙卡或群论基础；读完应当能解释题目在找什么、什么算证据、明天如何参与。

## 开始研究或写代码

查 [FOUNDATIONS.md](FOUNDATIONS.md)。它记录：

- split-orthogonal、Majorana/Kramers 和收缩半群等已知充分条件；
- `O(p,q)`、`Sp(2n,R)`、`SU(p,q)` 等候选的初步淘汰结果；
- 可交给自动测试的精确正、负、零证书；
- 新候选必须通过的新颖性检查；
- 数值 oracle 的正确性和可复现性要求。

随后按任务使用：

- [TOTAL_NONNEGATIVE_PATH_CLASS.md](TOTAL_NONNEGATIVE_PATH_CLASS.md)：当前严格恒正候选、证明和
  Hubbard/`t-V` 开链 HS 映射；
- [TN_NOVELTY_AUDIT.md](TN_NOVELTY_AUDIT.md)：TN 类对 Kramers、固定度量和 2024
  contraction-semigroup 的严格非归约证明；
- [TN_PHYSICAL_MAPPING_FRONTIER.md](TN_PHYSICAL_MAPPING_FRONTIER.md)：连续 TN 的开放路径
  no-go、排斥 `t-V` 键门的精确非对称辅助场分解，以及新矩阵机制与新物理模型的边界；
- [COMPOUND_GAUGE_NO_GO.md](COMPOUND_GAUGE_NO_GO.md)：比 TN 更宽的逐粒子数符号规范、
  普通 hopping 图只有开放路径幸存的图论结论，以及 2–6 站点全连通图穷举；
- [FRONTIER_SEMIGROUP_RESULTS.md](FRONTIER_SEMIGROUP_RESULTS.md)：15 族广扫、压力扫描、
  高精度反例和混合 split-cone 解析关闭；
- [AZ_SURVIVOR_CONE_RESULTS.md](AZ_SURVIVOR_CONE_RESULTS.md)：BDI/AII/DIII/CII 七个自然
  数守恒半群锥的 14 万权重筛选、80 位反例和完整 BdG 边界；
- [SPECULATIVE_STRUCTURE_RESULTS.md](SPECULATIVE_STRUCTURE_RESULTS.md)：奇数阶 monomial
  的一般证明、12 族 19.2 万权重、四类 80 位反例和 Majorana 宇称猜想；
- [SPECULATIVE_CANDIDATE_BATCH.md](SPECULATIVE_CANDIDATE_BATCH.md)：下一批
  spinor/exterior-cone 候选的定义、排重与停止条件；
- [GRADED_MONOMIAL_CANDIDATE.md](GRADED_MONOMIAL_CANDIDATE.md)：给正对角 TN 网络
  加入带 `Z2` grade 的 permutation crossing，以 scalar sign 抵消 determinant
  parity，并反推奇环吸引 spinless-fermion 模型的新候选；
- [COLLABORATOR_UPDATE.zh-CN.md](COLLABORATOR_UPDATE.zh-CN.md)：给合作者看的当前进展、结果边界和下一步；
- [ORGANIZER_DIRECTION_AUDIT.md](ORGANIZER_DIRECTION_AUDIT.md)：逐条核对主办方候选的完成状态；
- [PSEUDOUNITARY_PHASE_RESULTS.md](PSEUDOUNITARY_PHASE_RESULTS.md)：`U(p,q)` 相位定理和剩余符号；
- [NEXT_RESEARCH_PLAN.md](NEXT_RESEARCH_PLAN.md)：下一阶段主线、交付和停止条件；
- [SMALL_ANGLE_COUNTEREXAMPLE.md](SMALL_ANGLE_COUNTEREXAMPLE.md)：任意小夹角两层负权的直观与解析推导；
- [MAJORANA_CONE_RESULTS.md](MAJORANA_CONE_RESULTS.md)：直接 Spin 迹、双锥反例和小角压力测试；
- [AZ_TENFOLD_RESULTS.md](AZ_TENFOLD_RESULTS.md)：72 万次 AZ 扫描、深度三证书和已知类约化；
- [BASELINE_RESULTS.md](BASELINE_RESULTS.md)：90 万次基线扫描、淘汰表和证据边界；
- [COMPUTE_STRATEGY.md](COMPUTE_STRATEGY.md)：候选规模、吞吐基准和超算触发条件；
- [LITERATURE_GAP_2026.md](LITERATURE_GAP_2026.md)：截至 2026-07-27 的文献边界与推荐主线；
- [EXACT_CERTIFICATES.md](EXACT_CERTIFICATES.md)：人类可读的精确正、负、零测试锚点；
- [CANDIDATE_CARD.md](CANDIDATE_CARD.md)：每个新候选都复制并填写的评估模板；
- [ENVIRONMENT.md](ENVIRONMENT.md)：本机可用软件、错误环境和待定依赖；
- [KICKOFF.md](KICKOFF.md)：明日开工顺序、两到三人分工和交付标准。

## 明天组队时

先读 [../START_HERE.md](../START_HERE.md) 的“现在做到哪里”，再按三类任务分工：

1. Majorana/锥交集候选生成器、数值 oracle 与精确反例；
2. 候选矩阵类和物理 DQMC 映射；
3. 文献排重、已知类约化与精确证明。

精确测试数据的机器可读源是 `fixtures/exact_certificates.json` 和
`fixtures/majorana_trace_certificates.json`；扫描事实的唯一
机器可读源是结果目录中的 `run.json`、`parameter-scan.csv` 和逐格 manifest。文档负责解释，
不替代原始数据。
