# Ideas Session — 2026-07-30 09:28

## Phase 1 — 第四天重新审视 Problem Factory

**用户：** 阅读 `tracks/agent-kb/README.md`。现在是第四天，感到挫败。一个讲座的意见与用户一致：纯粹提出一个问题并评价问题好坏，可能不太对。

**导师初步回应：** 先阅读赛道 README，重点查看赛道目标、评分标准、第四天交付要求，并判断问题出在任务定义、交互闭环还是展示方式。

**赛道 README 要点：** agent-kb 的交付物应是更有能力的研究 agent、更好的科学知识库，或测量其推理、工具使用、检索与 grounding 的 evaluation；当前选择 #133 problem factory，目标是生成、求解并发布 autoresearch problems，并以 #112 作为复现锚点。

**进一步阅读：** `solutions/problem-factory/README.md`、`~/problem-factory-guide.md`、`docs/design/problem-generation.md`、`log.md`、`~/code/hackathon-journal.md`。

**发现：**

1. 当前系统不只是“生成问题后主观打分”。现有闭环包括：文献提取 → 分解图 → 边界探测 → 结晶并冻结 gate → 反向筛查不可判问题 → static fire → hop experiment → survivor/deferred/dead → 死因沉淀为 heuristics。
2. v3 文档明确写道：通过反向筛查不代表问题好，只代表“配被实验判决”；问题好坏不能由 agent 讨论决定。
3. 但当前 README 和演示最醒目的输出仍是“5 张卡，1 survivor / 1 deferred / 3 dead”。因此外部听众很容易把它理解为一个自动题目筛选器，而不是能够改善科研过程的学习闭环。
4. 更重要的实质缺口已经被 Day 2 日志直接指出：`decisiveness ≠ value`。当前实验能判断某个预定义观测量是否出现显著信号，但不能判断这个信号是否新颖、重要、解释了不一致、推进了知识边界，或值得投入后续科研资源。
5. 当前 heuristics 库如果只记录失败标签，还没有展示这些经验会反过来改变下一轮问题生成、减少预算浪费或提高后续求解成功率。因此“学习”闭环尚未被实证。
6. #112 的完整求解、独立交叉验证、知识卡/oracle/dispatcher 回写，其实比五卡筛选更符合赛道目标：一次科研运行暴露 agent 的知识发现缺口，随后机制性修复 harness，使未来 agent 更有能力。这可能成为重新定位的核心证据。

## 用户进一步澄清

**用户：** 给定一个大方向后，现有论文通常已经提出许多公认开放问题。研究者不需要凭空再生成问题，而应在这些问题上做出更多进展；新实验数据和新认识出现之后，新的问题才自然产生。关于科学价值，队友提出用信息论判断问题好坏。

**概念转折：** 用户质疑的不只是“如何给候选问题评分”，而是“问题生成是否应该作为科研过程中的独立前置模块”。更自然的时序可能是：文献中的开放问题 → 选择可推进的前沿 → 设计区分性实验 → 新数据/新认识 → 暴露新问题。信息论在其中更适合评价实验或下一步行动的预期信息增益，而不是独立定义科学价值。

**导师进一步分析：** 科研的自然时序应是 `K_t + experiment → K_{t+1}`，新问题来自更新后知识中的未解释残差或新边界。队友的信息论方案需要区分结果 surprisal、观察后的 posterior KL、以及行动执行前的 expected information gain；其中 EIG 最适合在竞争性假设和有限预算下选择下一步实验，但不能单独代表科学价值。建议把系统从 Problem Generator + Judge 重定位为 sequential scientific decision system：文献/专家给出重要方向，信息增益选择研究行动，现有 static fire/probe 验证行动，知识库保存更新，新问题从结果中长出。#112 中失谐不对称现象可作为该闭环的具体例子。

## 话题切换 — 整个 harness 的运行流程

**用户：** 询问当前是否在使用 harness，随后要求忽略 `tracks/agent-kb` 的 Python 文件，解释整个 harness 项目的运行流程。

**只读探索范围：** 根 `AGENTS.md`、`README.md`、`Makefile`、`Ion.toml`/`Ion.lock`、代表性 workflow/method/software/cluster/report skills、`.knowledge/`、`scripts/`、challenge/results/report 生命周期。未深入 `tracks/agent-kb` Python 实现。

**核心发现：** harness 不是单一可执行应用，而是三层 AI 科研编排系统：`AGENTS.md` 与 `SKILL.md` 是控制面和行为约定；`.knowledge/` 与 TOML/JSON manifests 是知识及数据契约；Makefile、数值脚本、报告脚本、SSH/Slurm 脚本是执行面。主 orchestrator 是读取这些 skill 后操作工具的 agent，而不是一个中央 Python 程序。
