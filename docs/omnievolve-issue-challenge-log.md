# OmniEvolve Issue 挑战记录

> 目标：使用 OmniEvolve 框架优先完成两个赛题，并持续记录可复盘、可汇报的证据。
>
> - Phase 1A：#117 Lennard–Jones Cluster Optimization
> - Phase 1B：#71 Occam's Circuit

## 当前状态

| 赛题 | 状态 | 当前最好结果 | 下一步 |
|---|---|---|---|
| #117 Lennard–Jones | 框架链路已打通；完成基线 + 第 1 代 3 个候选后人工停止 | score 0.9834066；E = −173.134317；最好力范数 3.0×10⁻⁴；未到 E_GM = −173.928427 | 先用短预算跨越 LJ38 双漏斗；LJ38 仅是官方 Rung 1，之后转向大 N 单组分 record hunt |
| #71 Occam's Circuit | 3 代烟测完成；4 个 mystery 官方训练集/测试输入已接入 | practice-add-n4：100% accuracy、17 gates、score 0.966 | 建立无隐藏真值的 mystery 训练一致性 + 门数评估，再逐实例进化与生成预测 |

## 比赛注册与官方范围

- 注册 PR：`QuantumBFS/quantum.harness#181`，状态 OPEN；团队 `quantumevolve`，
  同一 PR 覆盖 #117 与 #71。
- #71 带 `accepted` 标签；#117 当前为开放 challenge，但未带 `accepted` 标签。
- #117 官方目标是打破单组分 Lennard–Jones 记录。LJ38 是已知困难基准，
  只用于训练与效率比较，不能把复现已知 E_GM 当作最终 catch。
- #71 官方最终交付包含 4 个 mystery 电路、测试输出预测、搜索脚本和方法说明。

## 可复现实验

### Phase 1A

- 数据库：`challenges/omnievolve/.omnievolve/lj_glm52_parent_smoke3.db`
- 日志：
  - `challenges/omnievolve/.omnievolve/runs/phase1a_glm52_parent_smoke3.out.log`
  - `challenges/omnievolve/.omnievolve/runs/phase1a_glm52_parent_smoke3.err.log`
- 实验 ID：`2b0f3b84971242c2`
- 人工停止点：第 1 代完成，基线 + 3 个进化候选均已评估。
- GLM 调用：Director 3 次、Coder 3 次，共 33,951 tokens。

结果摘要：

| 候选 | score | E | force norm | force evals | 结论 |
|---|---:|---:|---:|---:|---|
| baseline | 0.9834066 | −173.134317 | 5.2×10⁻⁴ | 218,233 | 合法，但困在同一能量盆地 |
| gen1-a | 0.9834066 | −173.134317 | 5.2×10⁻⁴ | 187,063 | 合法；计算量降低约 14% |
| gen1-b | 0.9834066 | −173.134317 | 5.2×10⁻⁴ | 185,721 | 合法；计算量降低约 15% |
| gen1-c | 0.9834066 | −173.134317 | 3.0×10⁻⁴ | 229,781 | 合法；局部收敛更好，但未跨漏斗 |

### Phase 1B

- 数据库：`challenges/omnievolve/.omnievolve/occam_glm52_smoke3_retry.db`
- 日志：
  - `challenges/omnievolve/.omnievolve/runs/phase1b_glm52_smoke3_retry.out.log`
  - `challenges/omnievolve/.omnievolve/runs/phase1b_glm52_smoke3_retry.err.log`
- 实验 ID：`fb4415a8286647d7`
- 3 代，11 个候选，104,937 tokens，记录成本 $0.104937。
- 最佳：100% test accuracy，23 gates，score 0.954。

## 环境与配置

### 已确认配置

- LLM：`openai/qwen3.8-max-preview`
- API base：阿里云百炼 Token Plan OpenAI-compatible `/compatible-mode/v1`
- 代码存储：CAS。框架默认、示例配置和所有随仓库发布的任务配置均为
  `code_backend = "cas"`；只有明确需要 Git ancestry/worktree 时才单独覆盖为 `git`。
- Windows 执行：`trusted_subprocess`；仅运行受信候选。
- 模型最大输出：`max_tokens = 4096`。
- 本地竞赛运行暂时关闭 `embedding_gate`，保留 AST gate。
- API key 只保存在 gitignored `.env`，本记录不保存密钥。

### Windows 特殊处理

- `.agents/skills` 的 Git symlink 在 Windows 被检出为普通文本文件。
- 解决：改为 `.agents\skills -> ..\skills` directory junction。
- `omnievolve.exe` Windows launcher 无法创建进程。
- 解决：使用 `.venv\Scripts\python.exe -u -m omnievolve.cli ...`。

## 框架问题与解决方案

### F-01：任务被错误命名为 `initial_code`

- 症状：LJ38 的生成结果变成排序、memoization、prefix sum 等通用代码。
- 根因：CLI 对文件任务使用 `task_path.stem`，Director 只看到 `Task: initial_code`。
- 解决：
  - 从初始 Python 模块 docstring 提取任务契约；
  - 在实验启动时保存到引擎；
  - 同时注入 Director 与 Coder；
  - 即使没有父代码也能保留任务上下文。
- 验证：Director 后续明确提出 FCC/二十面体模板、双尺度扰动和 adaptive reheating。

### F-02：未达到最终门槛的高分候选不能成为父代

- 症状：LJ 基线 score 0.9834 且物理结果有效，但因 `passed=False` 无法被选为父代，Coder 没有 Current Code。
- 根因：父代查询和 best-candidate 查询错误地要求 `er.passed = 1`。
- 解决：改为选择 `status='completed' AND primary_score IS NOT NULL` 的候选。
- 语义：`passed` 表示达到赛题目标；`primary_score` 表示可用于连续优化的适应度。
- 验证：第 1 代候选保留完整 LJ 脚本、`lj_ref` 和 `candidate_result.json` 契约。

### F-03：`embedding_gate=false` 没有关闭向量索引器

- 症状：一次本地 Qwen embedding 初始化约耗时 28 分钟，看起来像进化卡死。
- 根因：CLI 无条件构造 `VectorIndexer`，忽略 novelty 配置。
- 解决：只有 `settings.novelty.embedding_gate=true` 时才构造向量索引器。
- 当前策略：Windows 本地竞赛运行先关闭 embedding gate；需要 RAG 时再单独做性能评估。

### F-04：Coding Plan 请求超时

- 症状：初次 Occam 运行出现长请求和 120 秒超时。
- 根因：输出 token 上限过大，Coding Plan 端点长推理延迟高。
- 解决：heavy/light 均使用 `openai/glm-5.2`，`max_tokens=4096`。
- 验证：Phase 1B 重跑没有 API timeout。

### F-05：SQLite 并发压力测试偶发锁冲突

- 症状：完整/组合回归中 `test_concurrency_stress` 偶发 `database is locked`。
- 特征：失败项单独立即复跑通过；其他 854 或 188 项通过。
- 当前判断：Windows 临时目录下 WAL 初始化竞争的 flaky test，不是本次提示/选择逻辑回归。
- 待办：若竞赛长跑出现真实 DB 锁，再为 PRAGMA 初始化增加 retry/backoff。

### F-06：LJ38 完整评估反馈过慢

- 症状：每个候选约 137–139 秒，3 候选/代约 7 分钟，策略迭代速度过慢。
- 解决：
  - 新增 `LennardJonesSearchEvaluator`；
  - 通过 `LJ_TIME_BUDGET_SEC=35` 控制候选预算；
  - 搜索阶段超时 50 秒，冠军仍由原 `LennardJonesEvaluator` 做 140 秒完整复核。
- 验证：短预算基线墙钟 33.94 秒、评估 32.02 秒，仍得到
  E = −173.134317、score = 0.9834066；力评估数从 218,233 降到 63,214。
- 测试：评估器预算与完整复核配置测试共 2 项通过；相关定向测试合计 34 项通过。

### F-07：未显式配置的运行会悄悄回到 Git 后端

- 症状：两个赛题 TOML 已写 `code_backend = "cas"`，但新建配置或遗漏
  `[storage]` 覆盖时仍会使用框架默认 Git，在 Windows 再次触发 plumbing/worktree 问题。
- 根因：`StorageSettings.code_backend` 的默认值仍是 `git`，示例配置也没有展示该字段。
- 解决：将框架默认、示例配置和随仓库发布的任务配置统一切为 CAS；Git 改为显式 opt-in。
- 验证：`TestStorageSettings.test_defaults` 固定默认值为 `cas`，并运行配置定向回归。

### F-08：Windows 原生 `make help` 依赖缺失的 POSIX 工具

- 症状：`make help` 立即报错：找不到 `grep`。
- 根因：Makefile 的帮助目标依赖 `grep | sort | awk`，但当前 Windows shell 没有这些命令。
- 当前绕行：直接读取 Makefile 的 `INSTALLABLE` 与目标；OmniEvolve 使用其自带
  `.venv\Scripts\python.exe` 运行，不依赖该帮助目标。
- 后续修复：把 `help` 改成跨平台脚本，或明确要求从 Git Bash/WSL 调用。

### F-09：Occam 集成只有 practice 数据，无法进入正式 mystery

- 症状：框架可在加法/乘法 practice 上得分，但目录中没有 mystery-A/B/C/D，
  无法产生比赛要求的四组电路与预测。
- 根因：初始集成只复制了带公开真值的两个 practice。
- 解决：从官方 `occam-circuit-data-v1` release 下载并校验
  `sha256=c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b`，
  接入四个 mystery 的 `train.csv`、`test_inputs.csv` 和 commitment；不引入隐藏输出。
- 待验证：评估器需要支持“无 test truth”模式，以训练一致性 + 门数驱动进化，
  并明确把最终 hidden-test 成绩标记为未验证。

### F-10：竞赛模型端点切换

- 变更前：`openai/glm-5.2` + 智谱 Coding Plan。
- 变更后：`openai/qwen3.8-max-preview` + 阿里云百炼 Token Plan
  OpenAI-compatible endpoint。
- 密钥处理：只保存在 gitignored `challenges/omnievolve/.env`，不进入本记录。
- 验证：OpenAI-compatible `chat/completions` 返回 HTTP 200，响应模型名为
  `qwen3.8-max-preview`，最小请求正常结束。

### F-11：更新 OmniEvolve 主线

- 更新前：submodule `92c5f95`。
- 更新后：submodule `78cbba5`，快进 4 个提交。
- 上游内容：代码后端与 CLI 加固、可复现实验矩阵、统计/反作弊/回放组件和 CI 修复。
- 合并：stash 恢复仅在 `StorageSettings.code_backend` 注释处冲突；新旧两侧均为
  `cas`，采用新版注释，未改变行为。
- 验证：CAS、CLI、Agent、选择器、上下文和两题评估器定向回归 85 passed。

### F-12：Qwen Coder 在 4096 输出预算下连续超时

- 症状：Occam 首批中 Director 约 49 秒成功；随后 Coder 连续触发 120 秒
  OpenAI client timeout/retry，没有产生进化候选。
- 判断：端点与鉴权正常，瓶颈是长代码生成的服务延迟。
- 排查：降到 2048 后仍在 120 秒超时；把请求窗口增至 300 秒后仍超时，
  说明输出上限和客户端窗口不是根因。
- 根因：Token Plan 的 `qwen3.8-max-preview` 是 thinking-only，默认
  `reasoning_effort=xhigh`；其默认推理预算远大于进化代码任务所需。
- 反例：通用文档说明部分 Qwen 可关闭 thinking，但该专用端点明确拒绝
  `enable_thinking=false`，返回 `The value ... is restricted to True`。
- 处理：OmniEvolve 新增 `ModelsSettings.request_timeout`、
  `ModelsSettings.enable_thinking` 和 `ModelsSettings.reasoning_effort`，
  网关透传 provider-specific `extra_body`；两题使用 `max_tokens=4096`、
  `request_timeout=300`、`reasoning_effort=low`，以 run5 数据库重启。
- 官方依据：`qwen3.8-max-preview` 支持 `low / medium / xhigh`；
  low 映射约 4096 thinking tokens，默认 xhigh。
- 证据：`phase1b_occam_qwen38_gen1.err.log`；run1 基线仍有效，
  17 gates、score 0.9660。
- 回归：配置、CLI、LLM gateway 相关测试 92 passed。

## Qwen 正式运行

- LJ 数据库：`challenges/omnievolve/.omnievolve/lj_qwen38_search35_run5.db`
- Occam 数据库：`challenges/omnievolve/.omnievolve/occam_qwen38_gate17_run5.db`
- 原则：新模型使用新数据库，不与 GLM 历史候选混合；先各跑 1 代确认有效候选，
  再按提升与成本决定放量。

### Run5 首批证据（运行中）

| 赛题 | 实验 ID | 已评估 | 当前最好 | 结论 |
|---|---|---:|---|---|
| Occam practice-add-n4 | `192e68f3a4a84a1d` | 基线 + 2 进化候选 | 100% train/test，17 gates，score 0.966 | 链路成功；两个候选均保持基线，尚未减门 |
| LJ38 search35 | `cd5f13c290ad4b1e` | 基线 + 1 进化候选 | 基线 E = −173.134317，score 0.9834066 | 链路成功；首个候选 E = −172.230710，低于基线质量 |

日志：

- `challenges/omnievolve/.omnievolve/runs/phase1b_occam_qwen38_gen1_run5.out.log`
- `challenges/omnievolve/.omnievolve/runs/phase1b_occam_qwen38_gen1_run5.err.log`
- `challenges/omnievolve/.omnievolve/runs/phase1a_lj_qwen38_gen1_run5.out.log`
- `challenges/omnievolve/.omnievolve/runs/phase1a_lj_qwen38_gen1_run5.err.log`

## 评估器与赛题观察

### #117 Lennard–Jones

- 评估器能独立重算能量和力范数，能识别篡改或无效输出。
- 当前基线与 3 个进化候选全部合法，但都停在 E = −173.134317。
- 当前瓶颈已经从“框架生成错误任务”转为真实赛题问题：“如何从当前盆地进入窄而深的 FCC 漏斗”。
- 单候选约 137–139 秒，3 候选/代约 7 分钟；盲目跑 10 代成本太高。
- 下一轮应先缩短评估反馈，或采用两阶段评估：
  1. 短预算筛掉没有跨漏斗迹象的策略；
  2. 只对有希望的候选运行完整预算。

### #71 Occam's Circuit

- 评估器已验证 practice-add-n4 与 practice-mul-n4。
- 当前最佳 23 gates 且准确率 100%，说明功能链路稳定。
- 多个候选保持同分，当前进化缺少“减少门数”的有效压力或结构性变异。
- 下一轮重点：
  - 固定功能正确性为硬约束；
  - 将 gate count 改善作为主要差异信号；
  - 针对 ripple-carry adder、乘法部分积共享、布尔重写分别设计 Director hints。
- 已发现的确定改进：`build_adder` 原来每个高位全加器使用 7 门；
  复用 `t = x XOR y` 后，进位可写成 `(x AND y) OR (t AND carry)`，
  每个高位降为 5 门，4-bit adder 理论上从 23 门降到 17 门。
- 实测：practice-add-n4 保持 100% train/test accuracy，17 gates，
  score 从 0.954 提升到 0.966。practice-mul-n4 仍为 98 gates、score 0.804。

## 测试记录

- 初始回归：97 passed。
- 全量回归：854 passed、9 skipped、1 个 SQLite 并发压力项偶发失败；单独复跑通过。
- 上下文与 Agent 定向测试：16 passed。
- 上下文 + 引擎端到端：23 passed。
- 配置 + 上下文 + 引擎端到端：55 passed。
- 选择器、存储、Agent、引擎组合：188 项中 187 直接通过；唯一 SQLite 压力项单独复跑通过。

## 决策记录

1. 先完成 #117 与 #71，不扩展到后续三个赛题。
2. CAS 是 Windows 竞赛运行的默认代码后端。
3. 烟测只用于证明链路；链路打通后，不再机械扩大代数。
4. LJ38 下一步先改善反馈周期和跨漏斗策略，再做长跑。
5. Occam 下一步直接优化门数，不重复验证已经稳定的 23-gate 功能基线。
6. 所有新 bug、证据、修复与赛题结论继续追加到本文件。
7. CAS 是框架级默认值；Git 后端只在明确需要 ancestry/worktree 时启用。

## 待办

- [ ] 为 LJ38 设计短预算筛选 + 完整预算复核的渐进评估。
- [x] 为 LJ38 建立 35 秒搜索评估器，并保留完整复核评估器。
- [ ] 将 LJ38 的有效结构变异写入 task-specific Director hints。
- [ ] 为 Occam 增加门数导向的结构变异与停滞策略。
- [ ] 为 Occam 增加 mystery 的无隐藏真值评估模式并逐实例运行。
- [ ] LJ38 闭环稳定后选择大 N 单组分前沿目标，记录 incumbent 来源与 ΔE。
- [ ] 分别建立正式竞赛数据库，避免复用 smoke DB。
- [ ] 运行正式实验并周期性写入本文件。
- [ ] 汇总最终提交物、对比表与反思材料。

## 2026-07-28：从链路烟测切换到赛题实攻

### F-13：LJ38 的 fcc 种子几何构造错误

- 分类：赛题算法 / 初始代码。
- 症状：run5 的基线与两个变体反复停在 E ≈ −173.134317，无法触及
  LJ38 的 fcc 全局极小。
- 根因：
  1. 旧代码以一个已占据的 fcc 原子为球心按距离取 38 个格点；
  2. 原子中心的径向壳层数为 1+12+6+24，取 38 会从最后一个 24 重壳层
     任意丢掉 5 点，破坏 Oₕ 对称性；
  3. conventional fcc 晶格常数也写错，最近邻间距被压到约 0.890。
- 修复：以 fcc 八面体空隙为中心，使用正确晶格常数
  a=√2·2^(1/6)，严格选择 6+8+24 三个完整壳层。
- 结果：L-BFGS 从该种子以 14 次函数评估达到
  E=−173.928426590491，‖F‖=9.73×10⁻⁵，独立验证器 `catch=true`。
- 研究依据：
  - Doye、Miller、Wales：LJ38 是双漏斗景观，GM 是 fcc 截角八面体，
    宽二十面体漏斗导致随机弛豫更易误入：
    https://arxiv.org/abs/cond-mat/9808265
  - Doye、Wales、Miller：basin-hopping 的势能面变换能扩大可跨越漏斗的
    温区：https://arxiv.org/abs/cond-mat/9806020
  - Doye：压缩变换可使 LJ38 势能面更受 GM 漏斗支配，并可采用两阶段
    basin-hopping：https://arxiv.org/abs/cond-mat/0001066
- 边界：这个结构先验解决的是 LJ38 训练梯级，不等同于完成 #117 的大 N
  无偏 record hunt；大 N 仍需形态多样的增长、重排和独立复核。

### F-14：Occam mystery 不应再用 SoP 盲记忆

- 分类：赛题分析 / 数据语义。
- 方法：按题面 LSB-first 约定，把输入均分成 x、y，在全部训练行上穷举
  常见整数函数族；要求整行输出 100% 精确一致。
- 识别结果：

| 实例 | 结构 | 全训练命中 | 初始门数 | 固定 20% 留出 |
|---|---|---:|---:|---:|
| mystery-A | 8-bit x+y → 9 bit | 2000/2000 | 37 | 100% |
| mystery-B | 7-bit \|x−y\| → 7 bit | 1500/1500 | 51 | 100% |
| mystery-C | 6×6-bit x·y → 12 bit | 1200/1200 | 247 | 100% |
| mystery-D | x²+y²，x/y 各 5 bit → 11 bit | 400/400 | 344 | 100% |

- 修复：`initial_code.py` 新增绝对差、平方和结构化综合；平方时复用
  xᵢxⱼ=xⱼxᵢ 的部分积。输出宽度严格截断/补零。
- 评估：`OCCAM_INSTANCE=mystery-A..D`；官方隐藏 test 未公开时，从官方
  train 固定拆出候选不可见的 20% 验证集。此分数只用于本地进化，最终
  hidden-test 仍明确标记为未验证。
- 下一目标：A/B 继续压门；C/D 优先改为阵列乘法、carry-save tree、
  Wallace/Dadda 或按列压缩，避免串行移位相加的高门数。

### F-15：run5 正式收口

- Occam：实验 `192e68f3a4a84a1d` 正常完成；基线+4 个候选全部 100%
  train/test，最好 17 gates、score 0.966，未超过基线。
- LJ38：实验 `cd5f13c290ad4b1e` 生成 5 个候选、完成 5 次评估，但都未达到
  GM 硬门，因此 `best_candidate=None`；编排器最终保留 `running` 状态，
  属于“无 passed 候选时实验终态未落盘”的框架问题。
- LJ run5 最好仍为 E=−173.134317005829；另一个候选退化到
  E=−172.230710160403。

## Run6（已启动）

| 赛题 | 实验 ID | 新基线 | 状态 |
|---|---|---|---|
| Occam mystery-A | `0b4a41f5fecd4314` | 100% train/holdout，37 gates，score 0.926 | 基线通过，Coder 进化中 |
| LJ38 Oₕ seed | `edf7ca179abe46a2` | E=−173.928426590491，14 evals，score 1.0 | 基线通过，Coder 进化中 |

日志：

- `challenges/omnievolve/.omnievolve/runs/run6_occam_mystery_a_gen1.out.log`
- `challenges/omnievolve/.omnievolve/runs/run6_occam_mystery_a_gen1.err.log`
- `challenges/omnievolve/.omnievolve/runs/run6_lj38_oh_gen1.out.log`
- `challenges/omnievolve/.omnievolve/runs/run6_lj38_oh_gen1.err.log`

回归：

- 模型配置、CLI、LLM gateway、LJ 评估器定向测试：68 passed。
- Occam 四套 mystery 的候选可见 80% / 隔离 20% 端到端验证：全部
  train_acc=1.0、holdout_acc=1.0。

### Run6 首批进化候选

- Occam mystery-A：首个候选保持 100% train/holdout 与 37 gates，未减门。
- LJ38：前两个候选都保持 E=−173.928426590058，并把 `n_force_evals`
  从基线 14 降到 10。
- 新问题：LJ search score 在命中 GM 后恒为 1.0，不能识别 14→10 的效率提升。
- 修复：下一实验版本采用分层主分——未命中 GM 严格低于 0.99；命中后
  `score=0.99+0.01/(1+n_evals/100)`，保证能量正确性优先、评估次数只负责
  GM 内部破同分。新增回归测试，3 passed。

## 2026-07-28：按 issue 重定向正式 100+ 轮 campaign

### Issue #117 学习结论

来源：https://github.com/QuantumBFS/quantum.harness/issues/117

- LJ38 只是 Rung 1 工具训练，不是正式猎场；N≤201 已被无偏
  conformational-space annealing 完整复现。
- 正式单组分前沿应优先 N=310–1000 或 1001–1610。选靶证据按 issue：
  1. icosahedral / decahedral / fcc motif crossover；
  2. E(N) 一阶差分或局部插值异常；
  3. 只有单一来源、未被独立无偏搜索复现的记录。
- 310–561 与 562–1000 的多数记录来自 2004 年 lattice construction +
  genetic algorithm；晶格先验强，但会漏掉假设形态族之外的结构。
- catch 的四道验证门：全对 full-pair LJ 势、严格力与 Hessian、第二优化器+
  小扰动复现、Kiessling 平均对能必要条件。最终只能声称 improvement，
  不能声称 optimality。
- 关键来源：
  - 官方 310–561 表：https://doye.chem.ox.ac.uk/jon/structures/LJ/LJ310-561.html
  - 官方 562–1000 表：https://doye.chem.ox.ac.uk/jon/structures/LJ/LJ562-1000.html
  - Kiessling 必要条件：https://arxiv.org/abs/2305.10600
  - 无偏 CSA 至 N≤201：https://arxiv.org/abs/cond-mat/0307690
  - large-N lattice+GA：https://doi.org/10.1021/jp037780t

### LJ 大 N 靶点审计：选择 N=924

- `frontier_audit.py` 从两张官方表读取 677 条 N=310–1000 记录，先用
  −2992.783729449165 修正 issue 已说明的 N=447 表格笔误，再计算
  `E(N) − [E(N−1)+E(N+1)]/2`。
- N=924 的正残差为 +0.903146，是修正 N=447 后全区间最大值：
  - E(923)=−6552.722600
  - E(924)=−6558.225148
  - E(925)=−6565.533988
- 这只是“值得审计”的信号，可能是合法壳层/motif 效应，不等于记录有错。
- 下载并哈希官方坐标：
  - 923：`7c1529...52ee`
  - 924：`b4196b...7dea`
  - 925：`f930fb...eb1`
- 用 exact all-pairs reference kernel 独立复算后，官方六位坐标的 N=924
  能量为 −6558.225147820547、力范数 5.83×10⁻³。
- L-BFGS 会因 float64 能量变化过小提前停在最大原子力约 10⁻⁶；
  加入 force-driven FIRE 后达到：
  - E=−6558.225147857513
  - ‖F‖=4.07×10⁻⁹
  - max atom force=6.19×10⁻¹⁰
  - Kiessling 邻点单调条件通过
- 相对官方表格值 ΔE=−1.4249×10⁻⁷，未超过记录；当前结论是
  **strict match/audit，不是 catch**。

### Issue #71 学习结论

来源：https://github.com/QuantumBFS/quantum.harness/issues/71

- 目标是 partial truth table 上最小一致电路；排行榜严格先按 hidden-test
  exact accuracy，再以 gate count 破同分。
- issue 明确允许且鼓励 hybrid 路线：符号/LLM 识别算术语义，再做结构化或
  exact synthesis；因此当前的 add / absdiff / mul / sumsq 识别合法。
- BDD/MPS 对加法和绝对差为线性规模，但乘法对任意变量序都可能指数大；
  C/D 应优先 circuit-level carry-save、Wallace/Dadda、SAT/ABC，而不是期待
  简单 BDD sifting 自动解决。
- 交付必须包含四个 `mystery-*.txt`、四份预测 test outputs、搜索脚本和
  pitch README。
- 关键来源：
  - challenge data release：
    https://github.com/QuantumBFS/quantum.harness/releases/tag/occam-circuit-data-v1
  - Boolean-function MPS/BMP：https://arxiv.org/abs/2505.01930
  - tensor-train recovery：https://arxiv.org/abs/2401.02592
  - partial MCSP hardness：https://eccc.weizmann.ac.il/report/2022/119/
- 2026-07-28 检查 release API 时仍只有原始 `occam-circuit.zip`，未看到
  Day-5 hidden outputs 新资产；最终准确率继续标记未验证。

### F-16：单实例 Occam pipeline 会掩盖跨题回退

- 症状：只在 mystery-A 上跑 100 轮，A 已是 issue 给出的 37-gate reference，
  同时模型完全可以破坏 B/C/D 而评分不变。
- 处理：新增 `OccamCircuitSuiteEvaluator`，每个候选连续生成并隔离验证 A–D。
- 评分：`0.99*min_test_acc + 0.01*(1-total_gates/1000)`；四题 exact 是
  passed 硬门，门数只在全对时破同分。
- 联合基线：A/B/C/D 分别 37/51/247/344 gates，总计 679，
  train/20% holdout 全部 100%，score=0.99321。

### F-17：trusted backend 把嵌套 mount 压平成 basename

- 症状：联合基线首跑找不到 `datasets/mystery-A/train.csv`。
- 根因：`TrustedSubprocessBackend` 对所有 mount 只取
  `Path(target).name`；嵌套目录被丢弃，且同名文件会互相覆盖。
- 修复：suite mount 使用实例前缀的唯一平面文件名，例如
  `mystery-A_train.csv` / `mystery-A_test_outputs.csv`。
- 证据：错误实验 `7e215e1164fa4aec` 被判 failed；修复后实验
  `1ec5a8e43b884174` 基线 passed。
- 正式提交仍应切隔离 backend；trusted 模式只用于本机可信候选开发。

### F-18：100 轮不能用一次盲跑代替十轮审计

- 新增 `scripts/competition_campaign.py`：
  - 累计目标按 10、20、…、110 调用 `run --resume --gens <累计代数>`；
  - 每十轮写 `.omnievolve/reports/<challenge>/generation-NNN.md`；
  - 最近十轮完成评估少于 5、passed<50%、score 非有限即停机；
  - Occam best 还必须保持四题 train/holdout exact；
  - LJ924 best 还必须保持 max atom force<10⁻⁸ 与单调条件。
- 停机后不自动跨过错误；修复 evaluator/pipeline 后从已验证 best 开新实验。

## 正式 100+ 轮 campaign

### Occam 四题联合

- 实验：`1ec5a8e43b884174`
- DB：`.omnievolve/occam_suite_qwen38_100plus_v2.db`
- 目标：110 generations，population=1，stagnation gate=1000。
- 首批日志：`.omnievolve/runs/occam_suite_g001_010.*.log`
- 控制器日志：`.omnievolve/runs/occam_campaign_controller.*.log`
- 提交物已生成到 `tracks/qcs/solutions/quantumevolve/`：
  四个 netlist、四份预测 CSV、manifest、构建脚本、README。

### LJ924 前沿

- 实验：`be407cb6501546db`
- DB：`.omnievolve/lj924_frontier_qwen38_100plus.db`
- 目标：110 generations，population=1，严格 full-potential verifier。
- 首批日志：`.omnievolve/runs/lj924_frontier_g001_010.*.log`
- 控制器日志：`.omnievolve/runs/lj924_campaign_controller.*.log`
- 当前 seed 明确为 `unbiased=false`；后续进化目标包括 923→924 growth、
  925→924 shrink、surface relocation、以及跨 icosa/deca/fcc motif seeds。

回归：双赛题 evaluator、配置和 CLI 定向测试 54 passed。

### F-19：`run --resume` 为 trusted sandbox 生成新 UUID，导致评估外键失败

- 症状：两条 campaign 都在创建 generation 1 候选后、插入
  `evaluation_run` 时触发 `FOREIGN KEY constraint failed`；候选停留在
  `pending`，没有评估记录。
- 排除：先用互斥锁排除了重复控制器并发；在全新 DB 单控制器复现，证明不是
  API 变慢或风控，也不是并发写入。
- 根因：CLI 每次启动都会构造新的 `TrustedSubprocessBackend`，其
  `environment_version_id` 是随机 UUID；`EvolutionEngine.resume()` 没有恢复
  原实验的 evaluator/environment scope，于是旧 best 对父代选择不可见，新
  evaluation 又引用了未登记的 environment UUID。
- 修复：resume 从最新 completed evaluation 恢复原 evaluator/environment
  scope，拒绝 evaluator 版本漂移，并重新执行版本完整性检查。
- 回归：现有 resume E2E 改为用第二个、UUID 不同的 sandbox 实例恢复；连同
  两题 evaluator 定向测试共 4 passed。
- 污染的 v2/v3 DB 保留作故障证据，不继续使用；从已验证 generation 0 在新
  DB 重开。

## 正式 campaign 更正（F-19 修复后）

### Occam 四题联合

- 实验：`4c38233d4c1642d0`
- baseline candidate：`580bce6012414d5f`
- DB：`.omnievolve/occam_suite_qwen38_100plus_v4.db`
- baseline：四题 train/20% deterministic holdout 全精确，679 gates，
  score=0.99321。

### LJ924 前沿

- 实验：`84204321eb674fe6`
- baseline candidate：`de2ccd640bd44a99`
- DB：`.omnievolve/lj924_frontier_qwen38_100plus_v3.db`
- baseline：E=−6558.225147857513，严格力门与 Kiessling 单调必要条件通过。

### F-20：Occam C/D 的大范围“压缩”重复破坏算术语义

- 证据：v4 generation 2/3 分别把总门数压到 423/420；A=37、B=50 仍正确，
  但 C=180、D=156/153 且 train/holdout 都为 0%。这不是 hidden-test 不确定性，
  而是已知乘法和平方和电路被错误替换。
- 处理：停止 v4 Occam batch，保留 generation 1 的 verified best（678 gates）。
  初始代码的任务契约改为四题 exact hard gate，并限制 C/D 只能做逐位可解释的
  等价局部优化；同时把全局 commutative CSE 与 output-reachability dead-gate
  elimination 固化为安全基线。
- 验证：新基线仍为 A/B/C/D train 与 deterministic holdout 100%，门数
  37/50/247/344（总计 678）；suite evaluator 测试 2 passed。
- 审计隔离：campaign 报告与 subprocess log 按 experiment ID 分目录/命名，避免
  重跑与失败实验混写。

## Occam 安全重跑（F-20 后）

- 实验：`bf5b3b9dc44e4c29`
- baseline candidate：`fd7abb1bca234353`
- DB：`.omnievolve/occam_suite_qwen38_100plus_v5.db`
- 目标：在保持四题精确的前提下完成至少 110 generations；每十轮单独固化报告。

### F-21：D 的 344→144 gate 压缩经全域验证，不是 holdout 拟合

- v5 generation 1 报告 A/B/C/D gate 数为 37/50/247/144，总计 478；联合
  train 与 deterministic holdout 仍均为 100%。
- 由于 D 的改变量很大，额外在 evaluator 外独立枚举：
  - C：6+6 输入位的全部 4096 个输入，对 x·y 逐条完全一致（247 gates）；
  - D：5+5 输入位的全部 1024 个输入，对 x²+y² 逐条完全一致（144 gates）。
- 因而 D 的 200-gate 减少为真实的函数等价改写；其候选继续作为 v5 的 best，
  后续仍受四题 exact 硬门与每十轮健康检查约束。

### F-22：C 的 CSA 改写第二次失败，进入受保护 kernel 稳定阶段

- v5 generation 2 把 C 从 247 降到 168 gates，但 C 的 train/holdout 均为 0；
  D=144 仍正确。代码审计显示它把 shift-add 乘法替换为列式 CSA reducer，
  却没有正确处理最高位/进位。
- 处理：停止 v5，采用已全域验证的 478-gate best 为新基线，并在 Fast Loop
  增加 challenge-scoped `OCCAM_PROTECTED_MULTIPLIER` guard：稳定阶段把候选的
  `Netlist`、位变量、加法器、shift-add multiplier 与 `build_multiplier` 从已审计
  parent 回填；D、A、B 和外围综合仍可演化。
- 回归：guard 单测、resume E2E、Occam suite evaluator 共 4 passed。

## Occam 受保护 kernel 重跑（F-22 后）

- 实验：`61f394620d80438d`
- baseline candidate：`9ae1b637dd9d43cf`
- DB：`.omnievolve/occam_suite_qwen38_100plus_v6.db`
- baseline：A/B/C/D=37/50/247/144，total=478，四题精确；目标仍为至少 110
  generations，并且每十轮写独立审计报告。

### F-23：multiplier guard 首版传入空 base_code，未实际保护普通 mutation

- 症状：v6 generation 1 的候选加入递归常量化简，`zero()` 与 `gate()` 互相调用
  导致 `RecursionError`；本应回填的 `Netlist` 没有回填。
- 根因：Fast Loop 的 `base_code` 只在 crossover/fusion 时赋值，普通 mutation 为
  `None`，guard 因而直接放行。这个是 guard 接线缺陷，不是模型或 evaluator 问题。
- 修复：guard 回填源改为 `base_code or parent_codes[0]`，并用实际失败候选复现：
  修复后包含 `_try_simplify` 的候选代码会被替换掉。guard 单测保持通过。

## Occam v7（F-23 修复后）

- 实验：`75928d504f8c40e2`
- baseline candidate：`d40d690092b04315`
- DB：`.omnievolve/occam_suite_qwen38_100plus_v7.db`
- baseline：478 gates、四题精确；目标保持 110 generations。

### F-24：`compute_budget_sec=0` 被误解为零秒硬预算，制造了“假完成” checkpoint

- 症状：Occam v8 第 5 代的首次恢复命令返回成功，并把 experiment checkpoint
  写到 generation 5；但 `candidate` 表中最高只有 generation 4，因而没有可审计的
  候选或 completed evaluation。
- 根因：`EvolutionEngine` 将 TOML 中的 `compute_budget_sec=0` 原样交给
  `BudgetState`。后者把任何数字都视为硬上限，故恢复的预算在开始前已经 exhausted；
  `resume()` 随后仍由 `finalize()` 写入了当前 generation 的 checkpoint。
- 修复：引擎把零规范化为 `None`（不限计算时长）；恢复循环在每代前后计数，若没有
  新候选则回退 current generation，拒绝写入假进度。campaign 控制器也改为只认可
  同时存在 candidate 与 completed evaluation 的 generation。
- 回归：`test_resume_continues_from_checkpoint` 显式覆盖 `compute_budget_sec=0`，
  通过（1 passed）。修复后重新运行 v8 generation 5，候选表与 completed evaluation
  均存在，passed，score=0.99522，478 gates。

## Occam v8（F-24 后继续）

- 实验：`51ff3624c1fc41a2`
- DB：`.omnievolve/occam_suite_qwen38_100plus_v8.db`
- 已验证 generation 0、3、4、5 均通过四题 exact，当前 best=0.99522（478 gates）。
- generation 1、2 是已记录的语义失败样本；不计入“通过”结果。下一次从 generation 6
  继续，并仅在 generation 10 产生第一份十轮审计报告。

### F-25：桌面工具会话不适合作为长期 campaign 的父进程

- 观察：单代 Qwen 调用可持续数分钟，而桌面工具层有单次调用时限；由会话派生的
  detached 子进程也不能保证跨会话存活。此前因此出现“数据库已有部分结果但控制器
  未返回”的不确定状态。
- 处理：新增 `scripts/run_occam_v8_campaign.cmd`，并创建 Windows 计划任务
  `OmniEvolveOccamV8`。任务已启动，之后每小时触发；每次控制器至多运行十个
  已验证 generation，互斥锁防止重入。
- 保证：每个子代仍写独立 campaign log；第 10、20、… 代仅在 candidate 和
  completed evaluation 均存在、且健康门通过时才写 Markdown 总结。任务不是
  fire-and-forget：后续以任务状态、数据库和报告三者核验。

### LJ924 停止审计（generation 51–60）

- 既有报告显示本批只有 4 个 completed evaluation，虽其中 3 个 passed，但不满足
  “最近十轮至少 5 个完成评估”的健康门，故已正确停止。
- checkpoint 被写至 60、而实际最高 candidate generation=59；这同属 F-24 的旧
  假进度，不能用作完成轮次。
- 后续动作：先定位 LJ 的候选稀疏（多数 generation 没有 candidate）原因，并从
  generation 59 的已验证 best / 严格 baseline 恢复；在该问题修复前不把 LJ 继续
  计入 100 轮目标。

## LJ924 v4（F-25 后重开）

- 配置：`configs/lennard_jones_frontier.toml` 现指向
  `.omnievolve/lj924_frontier_qwen38_100plus_v4.db`；保留 strict full-potential
  evaluator、力阈值和 Kiessling 单调必要条件。
- 修复：关闭 AST novelty gate。LJ 候选大多是同一求解器骨架上的不同几何搜索策略，
  用代码树相似度淘汰它们会把真正需要物理 evaluator 区分的探索错误地变成空轮。
- 启动：Windows 计划任务 `OmniEvolveLJ924V4Seed` 已于 2026-07-28 09:53 本地时间
  运行，执行初始 strict baseline 与 generation 1。完成后以 v4 数据库确认 candidate
  和 completed evaluation 再创建后续十代 campaign；不沿用 v3 的假 checkpoint。

### v4 首代实时审计

- 实验 ID：`a0fe16ace166424a`。
- 证据：`scripts/campaign_status.py` 读取 v4 DB 后显示 generation 0 为 completed/
  passed（score=1.0000000007648515），generation 1 已有 candidate 且 evaluator 状态
  为 running。这证明新颖性门调整后候选不会在评估前消失。
- 后续：已创建 `scripts/run_lj_v4_campaign.cmd` 与计划任务
  `OmniEvolveLJ924V4`；其每次最多推进十个 durable generations，并按 10、20、…
  写带实验 ID 的报告。首代完成后再由该控制器接续，避免与 seed 并发。

### F-26：checkpoint 报告边界错误会制造提前健康门

- 症状：Occam v8 从 generation 5 恢复后，控制器在 durable generation 6 时就写了
  `generation-010.md`，generation 7 时又尝试 `generation-020.md` 并因“最近十轮
  完成数不足”停止。这两份报告的标题与实际数据库代数不一致，不能作为十轮审计。
- 根因：`competition_campaign.py` 外层 checkpoint 循环只用一次 `if completed <
  checkpoint`，单次只推进一代后就无条件写报告；`--max-subprocesses > 1` 并未形成
  到 checkpoint 的内层推进循环。
- 修复：改成 `while completed < checkpoint`，只在真正抵达 10、20、… 后写报告；
  subprocess 数上限仍在内层生效。删除两份错误报告并通过 `py_compile`，已从 v8
  generation 7 重启 Occam 任务。

### F-27：incomplete rewrite 不能让 Occam multiplier guard 失效

- 症状：修复 F-26 后，v8 generation 8 的模型候选遗漏受保护函数；Fast Loop 记录
  `Occam multiplier guard skipped: protected block missing`，候选评估失败（score=0）。
  因此该候选不具备 C/D arithmetic kernel 仍受保护的证据。
- 根因：guard 遇到任一 protected block 缺失时直接返回 model 的完整重写，恰好绕过了
  保护逻辑。
- 修复：缺块时改为用已审计 parent 重组模块，只接受候选中的 `build_adder` /
  `build_absdiff` 两个明确安全的 A/B 函数；C/D 核、输入处理和 dispatch 均保持 parent。
- 验证：新增“incomplete rewrite”回归测试；multiplier guard 与 Occam suite evaluator
  共 4 passed。
- 重跑：禁用并停止 v8 任务。`occam_circuit.toml` 改指 v9 DB，任务
  `OmniEvolveOccamV9Seed` 已启动，从已全域验证的 478-gate baseline 和 generation 1
  重新开始。v8 留作失败证据，不计入 100+ 轮目标。

### F-28：seed 与 campaign 不能并行启动

- 症状：Occam v9 seed 已实际完成 generation 1，但在它完成前启动的 campaign controller
  持续读取 `experiment_status=running`、durable generation=0，形成无效等待。
- 原因：seed 的最终状态和 checkpoint 是在 `finalize()` 末尾写入；并行 controller 在这段
  时间内只会轮询旧状态。虽然最终会可见，但这会让启动顺序不可审计。
- 处理：停止等待中的 controller，确认 v9 DB 为 completed、generation 1 已有 completed
  evaluation 后再独立启动。以后 seed task 完成并经 `campaign_status.py` 确认后，才启动
  对应 campaign。
- v9 generation 1 结果：candidate 与 completed evaluation 均已落盘；A/B 的安全区优化
  未保持 exact（score=0.52001），故 failed。C/D protection 没有失守；baseline 仍为通过
  的 478-gate best。

### F-29：旧控制器进程可在代码修复后继续写无效报告

- 观察：LJ v4 在实际 generation 2 时存在 `generation-010.md`；其 supervisor log
  证明报告由 F-26 修复前启动的 controller 写入，后者进程仍驻留旧代码。
- 处理：删除该唯一无效报告，确认两个 seed 实验均 completed 后，再启动新的 Occam v9
  与 LJ v4 scheduled task。新进程从磁盘读取修复后的 `while completed < checkpoint`
  控制器，不复用旧进程。
- 原则：代码修复后必须重启运行中的 campaign controller；仅改文件不会改变已加载的
  Python 进程。

### F-30：hourly scheduled task 与手动触发会留下并发 controller

- 证据：进程表中出现两个 Occam 和两个 LJ `competition_campaign.py` 实例；它们互相持有
  campaign lock / 轮询 DB，导致任务状态与数据库进度脱节。
- 处理：精确终止四个明确命名的 campaign 进程，停止并删除两个 hourly task，删除两个
  已验证为遗留的 experiment lock 文件；未触碰其他 Python/CAS 进程。
- 新机制：创建 `OmniEvolveOccamV9Batch` 与 `OmniEvolveLJ924V4Batch` 一次性任务，
  每个任务只跑一个最多十个 durable generation 的批次；确认报告和进程退出后才能启动
  下一批。两个干净批次已启动。

### F-31：无信息增益的慢调用不继续凑轮次

- Occam v10 到 generation 8 的 best 仍是经过全域验证的 478-gate baseline；有效候选
  主要复现 baseline，失败候选则破坏 A/B exact，没有出现小于 478 且四题正确的结构。
- 结构审计：A 的 37 gates 使用 LSB half-adder（2 gates）加 7 个 5-gate full-adder，
  已是该门集下的标准紧 ripple 实现；B 的构造原始计数为 51，现有全局 CSE 已降到 50。
  因而继续自由 whole-program LLM rewrite 的预期收益很低。
- 决策：停止正在执行的 generation 9–10 慢调用，DB 保持在 durable generation 8；
  478-gate 解继续作为合法提交基线。后续只有在出现可全域证明的 A/B 局部综合候选时才
  恢复 Occam 昂贵 evolve，不用重复失败调用凑“100 轮”。优先把计算投入 LJ 的独立形态
  搜索，因为那里仍存在明确的物理目标 ΔE>0。

### F-32：LJ 改用坐标空间结构搜索，首次独立 basin 试验未改进 incumbent

- 将 `frontier_initial_code.py` 改为比较两个 issue 指向的独立形态来源：向 LJ923
  最优 top/bridge 表面位点加原子，以及从 LJ925 删除最弱束缚原子；只优化粗能量较好的
  seed，并始终保留 published LJ924 incumbent 作回退。
- 本地单进程试跑 60.8s（无 LLM 调用）：923-growth 粗能量
  −6555.571329936；925-shrink 粗能量 −6558.218405555。
- 925-shrink 经 L-BFGS + strict FIRE 后得到 E=−6558.225147857513，与 incumbent
  相同。它是独立来源收敛到同一 basin 的有意义复核，但 ΔE=0，不构成 catch。
- 决策：不把相同自由 LLM 改写扩成 100 次；后续若继续 LJ，应扩展多个 removal/site
  候选或新的 icosa/deca/fcc motif，而不是重复 polish 同一坐标。

### F-33：多 basin 筛选暴露两处验收缺陷，现已恢复严格 baseline

- 多种子试验比较了 2 个 LJ923-growth 位点与 4 个 LJ925-shrink 位点。三个
  shrink seed 均收敛到 incumbent basin；其余 seed 明显更差，没有发现
  ΔE<0 的新结构。
- 首次试验错误地把约 10⁻¹² 量级的浮点差异标成 improvement，且 FIRE 因时间
  预算退出后没有再次检查 max atom force。修复后要求能量至少改善 10⁻⁸，且
  max atom force<10⁻⁸，二者同时满足才允许标记 `verified-improvement`。
- 第二次试验发现直接回退官方 `924.TXT` 仍会失败：文本坐标的有限精度使
  max atom force≈6.73×10⁻⁴。历史 artifact 审计确认，合法 baseline 必须先
  L-BFGS+FIRE 重最小化。
- 已恢复每次运行开头的严格 baseline 重构。回归结果：
  E=−6558.225147857513，force norm=4.07×10⁻⁹，
  max atom force=6.19×10⁻¹⁰，`verify_frontier.py valid=true`；
  evaluator 单测 1 passed。后续失败结构只回退到该高精度 baseline。

### F-34：Kiessling 条件已计算但未接入 valid，炸散原子被误报 passed

- LJ v6 generation 1 把原子炸散到 min distance≈144.61，得到
  E≈−4.38×10⁻¹³、max atom force≈1.81×10⁻¹⁴。它不是束缚的 LJ924
  cluster，且 `monotonicity_ok=false`，却被旧 verifier 标记 `valid=true`。
- 根因：`verify_frontier.py` 计算了
  v(923)≤v(924)≤v(925)，但构造 `valid` 时漏掉 `monotonic_ok`。
  evaluator 也完全信任 `valid`，没有做第二层检查。
- 修复：verifier 的 strict gate 现同时要求 finite、min distance、claimed
  energy 一致、max atom force<10⁻⁸、Kiessling monotonicity；evaluator
  升级为 `lj924-frontier@1.1.0` 并再次拒绝 `monotonicity_ok=false`。
- 回归：2 个 evaluator tests passed；历史严格 baseline 仍为 valid=true，
  同一炸散 artifact 现为 valid=false。v6 generation 1 不计入有效轮次，
  后续从 generation 0 best 在新数据库重开。

### F-35：LJ v7 首个十轮批次完成，未发现能量 catch

- 实验 `8e8e06bcbb1f4c3a` 的 generation 1–10 已全部产生 candidate 与
  completed evaluation；8/10 passed，pipeline 健康。
- best 保持 generation 0 严格 baseline：
  E=−6558.225147857513，max atom force=6.19×10⁻¹⁰，
  ΔE 仅约 9.1×10⁻¹³ 浮点差异，不构成提升。
- 路线分类：925→924 shrink/回退占多数，surface relocation + basin hopping
  占两轮；generation 6、7 的非束缚/缺失结果被 verifier 拒绝。严格可验证的
  真实能量改善为 0 轮。
- generation 5 曾连续四次返回 no-candidate；控制器正确把 checkpoint 留在 4。
  增加 budget/shutdown 诊断后重新调用成功生成并评估 generation 5，没有伪造空轮。

### F-36：十轮边界与报告累计统计修复

- 控制器达到 generation 10 并写报告后，旧逻辑会进入下一个 checkpoint，
  再运行一代才检查 `max_subprocesses`，因此额外执行了合法的 generation 11。
- 修复：在每次启动子进程之前检查整次 controller 的 invocation budget；
  后续不会从 10 溢出到 11。已落盘的 generation 11 保留为下一批首轮。
- 报告原先读取 `experiment.total_tokens/total_compute_sec`，这些字段会被每次
  resume 的局部统计覆盖。现改为从 append-only `llm_call_ledger` 与 completed
  `evaluation_run` 求和，并新增本批 search-mode、真实改善、verifier 拒绝分类。
- generation-010 报告已原位重生成：累计 58,347 tokens、累计 evaluator
  compute 1,865.8s，8/10 passed，真实能量改善 0。

### F-37：checkpoint 的 `--gens` 错当全局搜索周期，偶发四连 forced-backprop 空轮

- 症状：LJ v7 在 generation 5 与 15 都出现四次立即 no-candidate；没有 LLM
  调用、没有 evaluator 运行，checkpoint 分别正确停在 4 与 14。
- 根因：campaign 每次用 `--gens <下一代>` 限制单次 resume；CLI 同时把
  `EvolutionConfig.max_generations` 改成该值。MCTS 用
  `generation/max_generations` 计算进度，因而每次 resume 都误判为 100% 后期，
  以 50% 概率执行 forced-backprop；四次连续触发即形成约 6.25% 的空轮。
- 修复：新增稳定的 `search_horizon_generations`，从 TOML 的全局 110 代目标
  构造；`--gens` 只改变本次停止位置，不改变 MCTS 进度分母。
- 回归：config builder 与 resume checkpoint 两项测试通过；resume 到
  generation 3 时 MCTS progress 明确为 3/110，而不是 1.0。

### F-38：LJ generation 11–20 全部合法但策略塌缩，改为候选特异性 basin

- v7 generation 11–20 为 10/10 passed，仍无真实能量改善；9 轮最终最好
  basin 为同一个 925-shrink-2，1 轮为 925-shrink-1。pipeline 正确性健康，
  但搜索多样性不足，故不盲跑 21–30。
- 修复：evaluator 1.2 把 candidate ID 作为确定性 `LJ_FRONTIER_RUN_KEY`；
  initial code 用其 SHA-256 种子选择不同的弱束缚原子与替代 top/bridge 位点，
  每个候选强制先筛两个独立 surface-relocation basin，再比较 growth/shrink。
- 本地对照：candidate-A 与 candidate-B 产生不同的 atom/site 序列。一次完整
  运行实际优化了两个 relocation、一个 shrink、一个 growth seed，最终仍回退
  incumbent；E=−6558.225147857513、max atom force=6.19×10⁻¹⁰、valid=true。
- 可观测性：新增 `attempted_modes`，verifier/evaluator/report 会固化实际筛选过
  的所有 seed，不再只记录最终回退 basin。相关 evaluator/config 测试 4 passed。
- 按“pipeline 异常修好后从 best 重跑”的规则，v7 的 20 轮保留为审计证据，
  有效多样化 campaign 从全新 v8 数据库重新计数。

### F-39：Occam C 获得真实改进，247→191 gates

- 不再继续无提升的 LLM 长跑，改为手写并证明 6×6 multiplier 的 carry-save
  column compression：36 个 partial product 按权重列用 full adder 压缩到两行，
  最后只做一次 ripple addition。
- 独立全域验证覆盖 64×64=4,096 个输入对，全部满足输出等于 x·y；渲染后
  C 为 191 gates，比旧 C=247 减少 56。
- 首次命令误用了单实例 `OccamCircuitEvaluator`，只验证
  practice-add-n4；v11 因 evaluator scope 错误作废。随后在新 v12 DB 使用
  `OccamCircuitSuiteEvaluator` 完整验证。
- 四题结果：A/B/C/D=37/50/191/144，总门数 478→422；
  train 与 candidate-hidden holdout 全部 100%，score 0.99522→0.99578。
- 正式提交 netlist、predictions、manifest 已由 `build_submission.py` 重生成；
  C 电路 SHA-256=`3426f78d...a2ef38c`。新增 exhaustive multiplier
  回归测试并与 suite evaluator、protected multiplier guard 合计 5 passed。

### F-40：Occam 自动 evolve 不是“尚未提升”，而是反馈闭环与搜索空间配置错误

- v12 generation 1 实际完成过一次候选：Director 建议优化 A/B，Coder 延迟
  150.9s；候选把 B 从 50 改成 53 gates，且 B 的 train/test accuracy 均降为
  0，四题总门数 425、suite score 0.00575。evaluator 正确拒绝，422 best 未丢。
- 数据库证据说明自动 evolve 的生成—验证—淘汰链路能工作，但旧 prompt 只给
  源码和近似 score，没有把 A/B/C/D=37/50/191/144 的可行动反馈交给
  Director/Coder；它是在不知道瓶颈数值的情况下盲改。
- 旧稳定保护器还会把 C/D 与公共加法核恢复成 parent，实际只允许搜索 A/B，
  锁死了 335/422 gates 的主要空间。保护现改为显式
  `OCCAM_PROTECT_MULTIPLIER=1` 才启用；默认允许 C/D 候选进入完整四题
  evaluator，错误候选淘汰，已审计的 422 parent 始终可回退。
- fast loop 现把 parent 的 exact pass、primary score、总门数和四题分门数作为
  `VERIFIED PARENT FITNESS` 同时交给 Director/Coder，并明确“同门数或更高不算
  提升”。反馈、guard、exhaustive multiplier 与 suite evaluator 共 16 tests
  passed，ruff clean；随后从 generation 1 的 422 best 继续十轮批次。

### F-41：population=4 将慢模型调用放大四倍，撤回伪多样化

- 修复反馈闭环时曾把 `population_size` 从 1 调为 4，希望增加候选多样性；但
  OmniEvolve 的 `_step_generation` 会在一代内串行执行全部 candidate slots，
  不是并行采样。
- 当前 Qwen Coder 一次完整代码生成曾因超时/重试累计 1,109s；population=4
  会把单代最坏延迟放大到接近一小时，而且 generation checkpoint 只在四个
  slots 全部结束后写入，看起来像“评估完成却卡住”。
- 已停止该批次并恢复 `population_size=1`。多样性改由跨代 failed-direction、
  exact 分题反馈和 MCTS parent selection 提供；多发三次慢调用不再冒充搜索质量。

### F-42：中断窗口使 controller 与 resume 对“当前代”认知分叉

- v12 generation 2 的候选已写入并完成 evaluator，但进程在代末 checkpoint
  前中断；数据库因此同时存在 `MAX(candidate.generation)=2` 与
  `checkpoint.generation=1`。
- 旧 controller 用前者计算下一目标 `--gens 3`，而 EvolutionEngine.resume
  用后者恢复，导致子进程实际重复运行 generation 2 再运行 3。慢模型调用会被
  无意义重复。
- controller 现与 resume 统一，以 `experiment.checkpoint_data.generation`
  为唯一代际权威；候选/评估行只作审计证据。新增缺失、损坏 checkpoint 回退
  测试。v12 保留为故障审计，从当前 422 best 在干净 v13 数据库重新计数。

### F-43：anti-cheat 把说明 evaluator 契约的 docstring 当作窥题

- 干净 v13 baseline 在 sandbox 前被拒绝，唯一 finding 是
  `forbidden_literal`；命中源并非读隐藏答案，而是模块 docstring 中说明“完整
  四题 evaluator 淘汰式验证”。
- 旧 scanner 遍历所有字符串常量，无法区分不可执行的模块/类/函数 docstring
  与 `open("test_hidden.py")` 一类运行时路径，因此合法的任务说明会 fail closed。
- 修复后跳过 AST 认可的 docstring 常量，但继续扫描所有运行时字符串与无参数
  文件系统发现调用。新增回归同时证明 evaluator/hidden-test 说明可用、真实
  `open('test_hidden.py')` 仍被拒绝。v13 作废，v14 重新建立 422 baseline。

### F-44：失败历史只传 thought、不传结果，连续两代重复破坏 D

- v14 generation 1 与 2 的 Director 分别提出 CSE 和专用 squarer，思路文本
  不同，但两个 Coder 最终都把 D 从 144 改成 182 gates，并使
  `mystery-D_test_acc=0`；suite score 均为 0.0054，422 best 未丢。
- 原因不是 evaluator：它正确拒绝了两次。缺口在 `_load_sibling_summaries`，
  下一代只看到前代 thought，不知道具体是哪个实例失准、门数如何变化，所以
  “avoid failed direction”没有可操作证据。
- sibling context 现携带 passed、score、总门数，以及 A/B/C/D 分题 accuracy
  与 gates；LJ 同时携带 energy/max force。新增回归固定
  `D_acc=0, D_gates=182` 会进入下一代 Director/Coder prompt。批次从 v14
  checkpoint 2 的 422 best 继续。

### F-45：Director 指定优化 C，Coder 却第三次只改坏 D

- v14 generation 3 的 thought 明确提出为 C 使用 radix-4 Booth multiplier，
  但 AST 对比证明 `_multiply_bits` 未变化，唯一业务变化仍是 `_square_bits`；
  D 再次变为 182 gates、accuracy=0。三代 `_square_bits` 源码 hash 不同，
  因此不是候选缓存，而是 Coder 的目标错位。
- 原 LLM Critic 没有父代码的符号级 diff，未识别“思路 C、实际 D”的不一致。
  新增 Occam component-scope gate：从 fenced JSON 的 `thought` 字段提取明确
  A/B/C/D 目标，恢复非目标组件与运行契约；C-only 还不能暗改 C/D 共用
  `_add_bits`。允许范围内的改动仍须通过完整 suite evaluator。
- 回归证明 risk note 中提到“不要破坏 D”不会把 D 误识别为目标，且 C-only
  候选对 `_square_bits` 的修改会恢复为 parent。后续从 checkpoint 3 继续。

### F-46：scope 修复后的原样 parent 被错误计作有效代

- v14 generation 4 的 scope gate 正确恢复了越界 D 改动，四题重新全精确；
  但 candidate artifact hash 与 generation 0 baseline 完全相同，门数仍 422。
  旧引擎仍创建候选并把 checkpoint 推到 4，形成“通过但没有发生进化”的伪轮次。
- fast loop 现拒绝与 audited parent 字节级相同的候选并回滚 MCTS select；
  run/resume 统一通过 `_run_generation_until_candidate` 在同一代有界重试。连续
  no-op 不创建 candidate，最终 checkpoint 留在上一代。
- 新端到端回归用始终返回 `x=0` parent 的 Coder，证明总候选只含 baseline、
  `total_generations=0`、checkpoint generation=0。后续有效十轮统计不再包含
  完全重复 parent。v14 generation 1–4 保留为故障证据，按“修复后从 best
  重跑”规则在 v15 重新计数。

### X-06：D 的双平方联合 carry-save 压缩正确但更贵

- 假设：把 x²、y² 的所有对角项和交叉项放进同一列系统，联合 carry-save
  压缩后只做一次最终加法，可能省掉“两棵 square + 一次 add”的重复进位。
- 结果：5+5 输入的 1,024 种组合全枚举正确，但渲染网表为 149 gates，当前
  独立 squarer 方案为 144 gates，回归 +5。
- 理解：联合列的瞬时拥塞需要更多 full-adder 压缩，超过了省下的独立最终
  carry propagation。该路线淘汰，未进入 initial code 或 best。

### F-47：Occam v15 首次由自动 evolve 产生可验证提升

- 干净实验 `c669938c6fc4458a` 从四题全精确的 422-gate parent 开始；generation 1
  通过完整 suite evaluator，A/B/C/D=`37/50/176/144`，总门数 `422→407`，
  score `0.99578→0.99593`。
- 改进全部来自 C（6×6 乘法器）`191→176`，A、B、D 保持逐题 100% train/test
  accuracy；因此不是失败候选的低门数假象，也不是重复 parent。
- generation 2 对 D 的尝试把 D 改为 148 gates 且 accuracy=0，evaluator 正确拒绝，
  407-gate generation 1 继续作为 best。该结果说明修复后的
  parent-metrics → component scope → full-suite verification → best retention 闭环已经有效。
- generation 3 又把 C 的最终加法从“对补零后的两整行做通用 ripple add”改为
  “仅在真实位存在的列生成和/进位门”，C=`176→168`、总门数 `407→399`。
  独立枚举全部 4,096 个 6×6 输入对，`failures=0`；自动 evolve 相对 422 parent
  累计净减 23 gates（5.45%）。
- 方案质量并不稳定：generation 2、5、6、7 的 D/C 改写均不精确，已被 evaluator
  拒绝；Director 文本还多次误写成 4×4，而实际实现使用 `len(A)/len(B)` 泛化到
  6×6。结论是 LLM 已提出并实现两项有效结构优化，但仍必须依赖全枚举/完整 suite
  判真，不能信任方案描述本身。
- 按批次纪律继续运行到 generation 10；第十代边界再汇总成功率、真实提升与搜索方向，
  中途只因硬故障停机。

### F-48：候选淘汰率被误当成 pipeline 故障

- v15 generation 1–10 全部各有一个 durable candidate 和 completed evaluation，
  checkpoint 连续到 10，best 399 gates 保持正确；但报告因 `passed=4/10<50%`
  标成“pipeline 异常，已停止待修”。
- `passed=false` 在进化搜索里表示 verifier 正常淘汰错误变异，不是基础设施失败。
  旧健康门把搜索质量与管线完整性混成同一个量，因而会在 evaluator 工作正常时停机。
- 健康门现检查十代 generation 覆盖、evaluation completed、primary score 有限，以及
  challenge best 的精确性/力学约束；候选 correctness 通过率仍写入报告，但只作为
  搜索统计，不触发停机。
- 回归覆盖 40% 通过率但十代完整时 `healthy=true`，以及缺失/未完成 generation 时
  `healthy=false`；相关测试 4 passed，ruff clean。修复后从 generation 10 的
  399-gate best 继续至 110。

### F-49：Occam generation 11–20 边界健康，无新增 best

- generation 11–20 连续覆盖完整，10/10 evaluation completed 且 primary score
  有限；7/10 候选四题 train/holdout 全精确，pipeline 健康并自动继续。
- 精确候选门数分布为 399 gates×6、407 gates×1；其余 3 轮 exactness 失败，
  verifier 正常淘汰。当前 best 仍为 generation 3：
  A/B/C/D=`37/50/168/144`，总计 399 gates。
- 本批说明修复后的反馈能频繁保持 399-gate 结构，但尚未突破它；按“先纯跑 100+
  轮、每十轮检查”的约定不在该边界改 prompt 或源码，继续 generation 21–30。
- 固化报告：
  `.omnievolve/reports/occam/c669938c6fc4458a/generation-020.md`。

### F-50：失败经验只在短窗口生效，旧失败会被重新发明

- 实际正向证据：generation 19 的失败以
  `passed=false, C_test_acc=0, C_gates=240` 进入下一代 sibling context，
  generation 20 随即从 C 转向 D，说明相邻代反馈闭环确实工作。
- 实际反例：generation 20 再次产生 D=127、D accuracy=0；同一失败签名此前已经
  出现在 generation 5、6、13。旧实现只查询最近 2 代并只向 agent 展示 3 条，
  全局 scratchpad 又只存最近 5 条思路的前 80 字且不存 evaluator 指标，因此不能
  识别跨十代复现的等价失败。
- 修复：sibling outcome 窗口扩到最近 10 代/最多 8 条；失败 scratchpad 扩到
  10 条，并保存 `mystery-X:test_acc,gates + attempted_direction`；Director 和
  Coder 都收到最多 4,000 字的结构化失败清单，明确禁止等价失败签名。
- 测试同时暴露旧 E2E fake Coder 每次固定返回同一码、与 no-op 拒绝语义冲突；
  fake 现按调用产生不同代码。相关 agent/context/E2E 测试 94 passed，ruff clean。
- generation 21 在候选落盘前暂停；修复后从 checkpoint 20、399-gate best 恢复。

### F-51：resume 返回值曾使用未提交 candidate generation

- 上游新增的预算耗尽回归证明：checkpoint 已停在 generation 1、resume 也在运行
  generation 2 前正确退出，但旧恢复逻辑随后用 `MAX(candidate.generation)` 覆盖
  checkpoint，结果错误报告 `total_generations=2`。
- 修复后 `experiment.checkpoint_data.generation` 是恢复与结果报告的唯一权威；
  仅对没有 checkpoint 的旧实验回退到 `MAX(candidate.generation)`。
- 上游重基分支以自身 `src` 明确加入 `PYTHONPATH` 后，agent/context/E2E 共
  95 passed，ruff clean；修复已推送到原仓库分支。

### F-52：正确但没有改进的候选被误当成成功经验

- Occam v16 实验 `99a81ee5f1514c2c` 从 399-gate exact best 重跑至 generation 10；
  0 次提升，8 次仍为 399 gates，1 次退化为 401 gates，1 次把 D 改成
  129 gates 但 accuracy=0。十代覆盖、evaluation 完整性、有限分数和 best 保留均正常，
  固化报告为 `.omnievolve/reports/occam/99a81ee5f1514c2c/generation-010.md`。
- 第 2 代的 D=129/accuracy=0 已作为结构化失败进入后续上下文且未再重复，说明
  “算错失败”反馈链有效；但其余 8 个等分候选仍以 `passed/success` 展示，agent 没有收到
  “方案正确但未改善 best”这一明确负反馈。
- 修复后 sibling history 会相对候选产生前的历史 best 标记
  `search_outcome=improved_best / no_improvement / invalid`。Director 与 Coder 均被要求把
  `no_improvement` 当作负证据，不得原样重复机制，必须提出结构上实质不同且能解释预期指标
  增益的方案。
- 回归覆盖 invalid、correct plateau、Director prompt 和 Coder prompt；相关 competition
  context/agent/E2E/Occam 测试 30 passed，ruff clean。v16 停在十代边界作为审计证据，
  修复提交并推送后从 399-gate best 建立干净实验重新计数。

### F-53：Occam v17 generation 1–10 健康，负经验促成方向多样化但尚未提升 best

- 干净实验 `8a7a7b318eae4cf3` 从 exact 399-gate baseline 开始；generation 1–10
  连续覆盖完整，10/10 evaluation completed、primary score 有限，pipeline 报告
  `healthy=true`。固化报告：
  `.omnievolve/reports/occam/8a7a7b318eae4cf3/generation-010.md`。
- 10 个候选 artifact hash 全部不同，不再是源码级 no-op；方向依次覆盖专用 squarer、
  Dadda/前缀乘法器、逐输出布尔最小化、B 的 BDD、代数恒等式、跨组件 CSE 等。
  generation 8、9 的 thought 明确总结历史 best、失败和停滞后再选新方向，说明
  `search_outcome=no_improvement` 已进入实际生成反馈。
- 搜索统计：6/10 correctness passed；门数分布为
  `399×5, 384×1, 424×1, 504×1, 3085×1, 3162×1`。四个错误候选分别破坏
  B 或 D；其中 generation 6 的 D=129/accuracy=0 此后未在本批复现。
- 真实 best 仍为 A/B/C/D=`37/50/168/144`、总计 399 gates，0 次提升。
  这说明反馈修复改善了探索多样性，但没有凭空保证优化成功；由于流水线完整、失败能淘汰、
  best 能保留且方向不再原样重复，本边界不属于需停机的 pipeline 故障，按约定自动继续
  generation 11–20。

### F-54：Occam v17 generation 11–20 健康，失败经验被引用但替代方案仍未突破

- generation 11–20 连续覆盖完整，10/10 evaluation completed、primary score 有限，
  10 个 artifact hash 全部不同；固化报告：
  `.omnievolve/reports/occam/8a7a7b318eae4cf3/generation-020.md`。
- 搜索统计：4/10 correctness passed；全部候选门数分布为
  `351×1, 382×1, 398×1, 399×4, 401×1, 502×1, 513×1`。精确候选为
  `399×3, 401×1`，真实 best 仍是 A/B/C/D=`37/50/168/144`、总计 399 gates。
- 六个错误候选均被 evaluator 淘汰：generation 11、16 破坏 C，generation 13、14
  破坏 D，generation 19、20 破坏 A。generation 20 虽报告 398 gates，但 A
  accuracy=0，因此不是提升；best retention 正常。
- 经验利用有直接证据：generation 16 明确写出“不同于失败的 Dadda-tree”，改为
  radix-4 Booth，从“压缩相同 partial products”切换到“减少 partial-product
  generation”；说明失败记录不只是落库，而是进入了新 thought。该替代实现最终仍然
  C accuracy=0、513 gates，证明“使用经验”和“产生高质量修复”是两回事。
- generation 11 仍重新提出过较早的 Dadda 方向，说明最近 8 条 sibling 摘要的有界窗口
  无法永久禁止所有旧的 `no_improvement` 机制；但本批还覆盖 A 的 ripple/CLA、C 的
  dead-gate elimination/Booth、B 的 subtract-mask、D 的 squarer 等多个结构方向，
  不是同一源码或同一机制的死循环。pipeline 完整且搜索仍有理解性差异，本边界继续运行
  generation 21–30，不因 0 次提升停机。

### F-55：停止继续烧轮次——两个赛题的“thought 多样、有效行为同质”已构成搜索失效

- 用户在 Occam v17 durable generation 23 主动终止继续运行；已停止 experiment
  `8a7a7b318eae4cf3` 的 campaign/controller/worker 全部进程，remaining=0，SQLite
  checkpoint 保留在 generation 23，可恢复但不再自动继续。
- Occam 的主要障碍不是 evaluator：它成功发现了 399-gate exact 解，也能稳定淘汰低门数
  错解。障碍是搜索表示和反馈太稀疏：Coder 以自然语言重写复杂门级网络，没有
  SAT/ABC/espresso/peephole 等可验证综合器；评分在“全精确”前几乎是悬崖，不能告诉模型
  哪个局部布尔等式错了。thought 还多次把实际 6-bit 输入说成 5-bit，导致理论门数与实现
  目标错位。结果是正确候选大量回到 399，低于 399 的候选通常破坏 A/C/D。
- LJ924 的问题更明显：v7 generation 1–20 虽然 thought 覆盖 surface relocation、
  Mackay growth、Marks decahedron、fcc、parallel tempering、shell rotation 等，
  但实际 verifier 行为中 14/20 都落到同一
  `independent-925-shrink-2-atom-911-tested-incumbent-retained`，全部
  `unbiased=false`，严格能量逐位等于 `-6558.225147857513`。
- 这是由 seed 的安全回退共同造成的：候选只有在先改善超过 `1e-8` 且最终
  max-atom-force `<1e-8` 时才输出新坐标；否则 `run()` 明确复制严格 incumbent。
  因此 evaluator 看见的是合法但完全相同的 incumbent，而不是各个失败 proposal 的
  rough energy、basin identity 或最小能差。效率项只在 `1e-9` 尺度打破同能量 tie，
  反而会把“更少评估后回退”当作较好候选。
- 结论：框架现在能把失败文字送回 prompt，但没有把“thought 是否真正接到执行路径”和
  “失败 proposal 离 incumbent 多远”变成行为反馈。继续堆 100 轮只会优化回退路径或生成
  新叙述，不能形成有效梯度。若以后重开，应先为 Occam 引入形式化门级局部搜索/反例定位，
  为 LJ 输出最佳非 incumbent proposal 的能量、力、motif/坐标哈希并以行为新颖性筛选，
  同时把最终 incumbent retention 与搜索学习指标分开。

### F-56：引入行为级密集反馈，并从两个严格 best 各重开 20 代

- Occam verifier 现在为每题返回 `bit_acc`、首个失败输入、expected/actual、错误输出位、
  网表指纹和完整输入输出行为指纹；suite evaluator 仍以四题全精确作为 hard pass gate，
  精确候选仍按总门数排序，但错误候选获得可区分的诊断分数。官方四题的 6-bit 操作数约束
  已写入 seed 和 Coder prompt，避免继续按 5-bit 理论门数误导实现。
- LJ924 输出契约拆成两条通道：`best_*` 始终是严格 verifier 可提交结构；
  `proposal_*` 必须暴露本轮实际搜索到的最佳非 incumbent 结构。独立 verifier 重算
  proposal energy、force、最小原子间距和 permutation-invariant 坐标指纹；隐藏 proposal
  的候选虽可保持 submission 合法，但搜索分固定降为 0.5。
- LJ 搜索评分分层：严格能量改善进入最高 tier；未改善候选按独立 proposal 的能量差、
  force residual 和是否真正不同于 submission 排序；删除旧的 `1e-9*efficiency`
  tie-break，避免选择“少算几步后更快回退 incumbent”。
- sibling context 新增 Occam counterexample/behavior signature 和 LJ proposal
  energy/force/hash/search mode；Director/Coder 明确把相同行为指纹视为 behavioral no-op，
  并要求 LJ 新策略实际接入 `run()`。针对性测试 34 passed，ruff clean；框架修复提交
  `73ab50e`，干净上游提交 `db094f2` 已推送原仓库分支
  `codex/competition-pipeline-fixes-upstream`。
- 新基线已独立验证：Occam experiment `c460de690d184e57` 为 exact 399 gates，
  behavior signature=`9fd0f6eadbc8c0ce`；LJ experiment `8ab0d946b5424f57`
  的严格 submission 为 `-6558.225147857513`，同时成功暴露 proposal
  `E=-6558.225147857487`、max force=`5.708e-6`、hash=`d35915ee446869ee`。
  两个干净 campaign 均从 generation 0 best 启动至 generation 20，并在 10/20 固化报告。

### F-57：Qwen 限额前加入跨供应商 GLM 自动 fallback

- 原 `LLMGateway` 虽有 `fallback_model`，但备用模型复用主模型的 API key/base URL，
  无法从阿里云 Qwen 切到智谱 GLM；CLI 也没有把 fallback 配置传入 gateway。
- 新增本地环境变量
  `OMNIEVOLVE_LLM_FALLBACK_MODEL/API_KEY/API_BASE`，fallback 调用使用独立凭证和端点，
  且不把 Qwen 专用 `extra_body` 传给 GLM。主模型每次重试耗尽后才切换，不主动消耗 GLM。
- GLM `openai/glm-5.2` 端点 smoke 成功：256-token 小请求返回 `content=OK`；
  16-token 请求只产生 reasoning、正文为空，因此 campaign 保持原 4096-token 输出预算。
- 相关 CLI/gateway/fallback 测试 39 passed，ruff clean；主仓提交 `13b3659`，
  干净上游提交 `6c7283d` 已推送
  `codex/competition-pipeline-fixes-upstream`。fallback 密钥只在 gitignored `.env`，
  未进入仓库、报告或日志。

### F-58：#232 快速证书评估器——区分“合法父代”和“研究目标已闭合”

- 为 `tracks/polyopt/solutions/quantumevolve/` 新增 CHSH 秒级控制问题：候选返回
  Q(√2) 上界、加权 SOHS 多项式和显式两比特测量角；独立 verifier 在
  `A_i²=B_j²=I, [A_i,B_j]=0` 下精确归约算符词，并单独计算下界策略。
- 第一版把 `upper-lower <= 1e-8` 直接作为 `passed`，导致证书残差为零但 gap
  尚未闭合的 generation 0 被标成 failed。修复后 `passed` 只表示证书和
  sandwich 合法、可继续作为父代；`closed` 才表示研究目标闭合。
- 修复后的真实 OmniEvolve 单代实验 `0ed885afd6394725`：generation 0
  `gap=0.04847094813676289, score=0.9231752188514226`；generation 1
  `gap=0, score=1.0`。两代证书均 `residual_l1=0, residual_terms=0`，
  单次候选验证约 0.21–0.29 秒。
- Qwen 周配额已耗尽，本轮 Director/Coder 均按既定配置 fallback 到
  `openai/glm-5.2`；总计 4,412 tokens、约 54 秒。说明瓶颈是 LLM 延迟，
  不是评估计算或 HPC。
- 该 CHSH 结果只是 verifier/control 的端到端校准，不作为 #232 科研成果；
  下一步必须在相同 exact-certificate contract 下换成 catalogued open
  state-polynomial Bell constant。
### F-59：Windows 报告渲染器用系统默认 GBK 读取 UTF-8 JSON

- Phase 1 报告包含英文弯引号，`render_report.py` 的无参数 `Path.read_text()`
  在 Windows 中文环境按 GBK 解码，触发 `UnicodeDecodeError`，未生成 HTML。
- 修复：report JSON、lattix scene、viewer bundle 的文本读取以及 HTML 写出全部显式
  使用 UTF-8。该修复不改变报告 schema 或页面内容，仅消除平台默认编码差异。

### F-60：#232 图 33 从控制题切换到真实状态多项式目标

- 目标锁定 arXiv:2310.00612 Table 4 的七算符图 #33：
  `β(G)=sup_ρ Σ_i⟨A_i⟩²`，边反对易、非边对易，已知下界 `α(G)=2`。
- 新 evaluator 固定图、算符代数、目标函数和评分公式；候选只能选择最多 16 个
  三次或四次 square-free 基向量。verifier 独立重建状态多项式矩矩阵的全部恒等式，
  因而 LLM 不能通过修改物理问题或放松约束获得高分。
- 完整 degree-2 基线为 `upper=2.002487136812566`，完整 degree-3 为
  `upper=2.000057479970073`。两者均强于论文 reduced hierarchy 的对应数值；
  后续仍须导出并精确验证对偶 SOHS，数值 SDP 不直接当作研究证书。
- 真实首代实验 `e77d30c4b48b45fd`：GLM 提议 5 个交叠 triples，
  `upper 2.002487136812566 → 2.0022720549588313`，
  `score 0.5000 → 0.5299`，矩阵仅由 29×29 增至 34×34。这是有效但尚小的真实提升。

### F-61：模型名列表不等于跨 endpoint fallback

- 把 `openai/glm-5.2` 直接放到 primary model router 后，网关仍使用 primary Qwen
  的 token-plan endpoint，导致 GLM 名字也收到同一配额错误。
- 正确做法是让 GLM 使用独立的 `OMNIEVOLVE_LLM_FALLBACK_*` 凭证与 endpoint；
  当前 #232 运行在 Qwen 刷新前临时把 GLM fallback endpoint 映射为 primary，
  避免每次先浪费三次 Qwen 重试。密钥只存在 gitignored `.env`，不写入日志或提交。

### F-62：GLM 推理耗尽 4096-token 输出预算后生成空源码

- #232 实验 `e77d30c4b48b45fd` 在 generation 6 得到有效 best 后，
  generation 7–15 连续九个 candidate 的 artifact hash 都是空文件的 SHA-256
  `e3b0c442...`；verifier 均以 `candidate must define build_candidate()` 正确拒绝。
- LLM ledger 显示对应多次调用恰好用满 `output_tokens=4096`，说明 GLM 把预算耗在
  reasoning、没有留下最终代码正文。该段不是搜索停滞，而是 provider 输出预算与
  structured-code contract 不匹配。
- 为避免继续烧无效轮次，后台 20 代任务在 generation 15 停止。恢复前应提高 GLM
  输出预算或让 gateway 在 `content` 为空时以更高预算重试，并在创建 candidate 前
  拒绝空 artifact。
- 修复后 #232 默认输出预算提高到 32k；gateway 在正文为空且 output token 使用率
  ≥90% 时按 2× 扩容重试，最高 128k。所有截断响应仍计入 ledger/预算；若到上限仍
  无正文则拒绝该 generation。Fast Loop 在 critic 前后各设空源码硬门，空 CAS
  artifact 不再落库。
- 真实 GLM live smoke `85cf829c083a4058` 在修复后完成一代：
  `total_tokens=3903`，candidate 非空且 `score 0.5000→0.5856`；说明修复不只通过
  stub 回归，线上 provider 也恢复了代码正文。

### F-63：恢复已完成实验时运行状态和 checkpoint 不更新

- 同一实验恢复运行到 generation 15 时，数据库仍报告 `status=completed`、
  `finished_at` 为首轮结束时间，checkpoint 仍停在 generation 1；只有 candidate
  表持续增长。CLI `status` 因而同时显示旧的 completed 状态和新的 14+ generations。
- 这会让监控误判任务已经完成，并使进程异常退出后无法从最新有效代恢复。
  后续需在 resume 开始时重新标记 running，并在每个 durable generation 后原子更新
  checkpoint；结束或显式停止时再写最终状态。
