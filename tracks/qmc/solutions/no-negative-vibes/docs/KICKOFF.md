# 明日开工板

## 已经确定，不需要重新讨论

- 研究对象是 `w = det(I + exp(A_1)...exp(A_L))` 的逐构型非负性。
- 随机扫描只能发现反例，不能证明全体非负。
- 一个合格结果必须同时说明数学条件、新颖性和具体 DQMC 物理映射。
- split-orthogonal、Majorana/Kramers、收缩半群及简单 flavor 加倍都属于优先排重对象。
- 精确证书、运行参数、软件环境和随机种子必须能复核。
- 基线 oracle 已通过测试；15 个结构族的 90 万次扫描已完成，不应无理由重复。
- 经典群中的明显失败项已有精确或确定性数值反例，详见 [BASELINE_RESULTS.md](BASELINE_RESULTS.md)。
- 标准 Hermitian AZ 十类的 72 万次扫描也已完成；六类失败、四类约化到已知机制，详见
  [AZ_TENFOLD_RESULTS.md](AZ_TENFOLD_RESULTS.md)。
- Majorana 直接 Spin-trace oracle 和 70 万个双锥权重已完成；共同 `J1` 不足以保护符号，
  并有深度二精确负分支，详见 [MAJORANA_CONE_RESULTS.md](MAJORANA_CONE_RESULTS.md)。

## 仍然开放，必须由团队讨论

- 主攻哪个候选矩阵类，备选哪个；
- 第一套物理 Hamiltonian 和 Hubbard–Stratonovich 分解；
- 小角 Majorana 解析/约束优化还是物理 HS 反向映射作为主线；
- 下一个不约化到已知收缩半群的候选生成器；
- 第一轮扩展扫描预算；
- 最终由谁负责证明、代码、物理映射和写作。

## 建议的第一个 30 分钟

1. 全员读 [START_HERE](../START_HERE.md)、[基线结果](BASELINE_RESULTS.md) 和
   [文献空白](LITERATURE_GAP_2026.md)。
2. 读 [Majorana 双锥结果](MAJORANA_CONE_RESULTS.md)，不要重复已关闭的共同 `J1` 并集命题。
3. 用 [候选评估卡](CANDIDATE_CARD.md) 比较小角解析/优化与一个具体 Hamiltonian/HS 映射。
4. 选一个主候选和一个备选；复用现有 oracle，按精确测试 → 新生成器 → 小扫描推进。

## 两到三人的并行分工

| 角色 | 第一轮交付 |
|---|---|
| 数学/排重 | 填完候选卡第 1–4 节，找到最接近的原始论文和可检验命题 |
| Oracle/测试 | 为选定候选增加精确测试和结构生成器，保持现有回归测试全绿 |
| 物理映射 | 填完候选卡第 5 节，写出 Hamiltonian、HS 分解和逐时间片矩阵 |

两人组时，数学/排重和物理映射可由一人先合并负责；不要让所有人同时改同一个文件。

## 第一轮结束时应该留下什么

- 一张已填的主候选评估卡；
- 至少一个可重复的精确或数值检验；
- 一个清楚的继续/淘汰理由；
- 若继续，下一轮只增加一个明确变量，而不是无边界扩大扫描。

## Git 约定

- 队伍内容只写在 `signfree-qmc/` 对应的 solution 目录和规定的结果目录。
- 分工分支使用 `candidate/<name>`、`oracle/<task>` 或 `physics/<model>`。
- 不改主办方 harness 的 skill、公共脚本或其他队伍目录。
- 合并前保证测试命令、随机种子和输出路径写进提交说明。
- 当前本地准备提交尚未推送；对外推送和 PR 由团队确认后进行。
