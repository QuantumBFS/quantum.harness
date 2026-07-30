# Challenge 66 Autoresearch 工作流规范

状态：`frozen-for-autoresearch`
版本：`1.0`
日期：`2026-07-28`
挑战：[QuantumBFS/quantum.harness#66](https://github.com/QuantumBFS/quantum.harness/issues/66)

用户确认记录：2026-07-28 设置目标“执行 进行autoresearch”，确认按本文件启动。后续任何会改变物理模型、主指标、holdout、统计判据或最终验收门的修改都必须记录为 protocol override。

本文件是后续 autoresearch 的可修改执行合约，不是学习路线。用户设置目标前可以直接修改参数、预算和验收门；目标一旦启动，所有影响结论的定义必须冻结并写入运行清单。

autoresearch 的编排顺序固定为：

```text
topics -> db -> validator -> run -> done
```

- `topics` 冻结第 1--5 节的研究问题、模型和实验矩阵；
- `db` 建立 attempt、Slurm job、artifact、metric 和 claim 的可追溯记录；
- `validator` 在候选实现之前冻结第 7--8 节的测试、负向控制、score 和 sealed holdout；
- `run` 按第 9、11、12 节在独立 worktree 和 SCNet 作业中迭代；
- `done` 只在第 10 节发表级验收门和一次性 holdout 均通过后进入。

不得跳过或倒置这些阶段。

## 1. 可直接设置的研究目标

> 构建一个可复现的旋转表面码电路级 Monte Carlo benchmark，在 `d=3,5`、`T=d,2d` 下，统一模拟 Pauli 数据错误、测量错误、动态原子丢失、缺失掩码与原子重装；使用带 erasure 信息的基线解码器，比较不重装、立即重装、周期重装和缺失比例阈值触发重装。量化逻辑错误率、缺失原子占用、重装次数、延迟/初始化代价，给出“帮助、无显著差异、有害”三区域图，并导出有版本、无标签泄露、可供未来解码器使用的数据。所有运行任务必须通过 SCNet 的 Slurm 作业执行；本机仅编辑和管理文件。不得认领 Challenge、提交 PR 或训练神经网络解码器。

## 2. 要回答的问题

主问题：在给定 `p`、`p_m`、`p_loss`、码距、存储时间及 reload 成本时，主动重装是否降低逻辑错误率？降低多少？

次问题：

1. 不重装造成的空位累积何时开始支配逻辑失败？
2. 理想零成本下，立即重装是否逐路径不劣于周期重装？若不是，原因是什么？
3. 加入 reload delay、reset error 或 reload failure 后，最佳策略如何变化？
4. 哪些策略在统计上不可区分，哪些策略在逻辑性能与开销上形成 Pareto 前沿？
5. decoder-ready 数据是否足以让未来解码器只用 `syndrome + loss/reload history + metadata` 预测 logical outcome？

预注册假设：

- H1：固定 `T` 时，随 `p_loss` 增大，不重装策略的平均空位数和逻辑错误率上升。
- H2：在理想、无额外错误且下一轮前完成重装的模型中，主动重装在中高损失区间优于不重装。
- H3：加入非零延迟或 reset error 后，立即重装不一定最优，最优策略随成本权重改变。
- H4：只用 `d=3,5` 得到的是有限尺寸结果或 pseudo-threshold，不足以声称渐近阈值。

反例和不显著结果同样是有效结果，不得为了支持假设修改采样范围或删点。

## 3. 范围与禁止项

必做：

- rotated surface-code memory，`d in {3,5}`；
- `T in {d,2d}`，同时运行 memory-X 与 memory-Z；
- 独立的 `p`、`p_m`、`p_loss`；
- 空位跨轮持续，直到 reload 完成；
- erasure-aware MWPM 或等价的有文献依据的基线解码器；
- 四类 reload 策略、统计比较、开销和数据接口；
- 理想 reload 基线，以及 reload delay/reset error 的敏感性分析。

核心范围之外：

- 神经网络、GNN 或其他 learned decoder；
- 为认领挑战创建 issue、分支、PR 或外部推送；
- 未验证基线前加入相关丢失、原生 Rydberg gate schedule、code deformation 或逻辑块搬移；
- 仅凭 `d=3,5` 宣称真正的 loss threshold；
- 在本机安装运行依赖、执行测试、模拟或 validator。

相关丢失可以作为核心结果完成后的扩展，因为 Perrin 等人的结果表明其结构会显著改变解码效果；扩展结果不得与独立丢失基线混在同一结论中。

## 4. 冻结的物理与事件语义

### 4.1 最小噪声模型

对每个 shot、round、site、event type 使用可寻址随机流：

```text
u = RNG(master_seed, shot_id, round, site_id, event_type)
```

事件类型至少拆分为 `data_pauli`、`measurement_flip`、`loss`、`reload_reset`、`reload_success`。策略不能通过少抽或多抽随机数改变其他事件。所有策略共享同一份外生噪声计划，用 common random numbers 做成对比较。

- `p`：活跃数据原子每轮的 Pauli 错误概率；默认 depolarizing，`X/Y/Z` 等概率。
- `p_m`：有效稳定子测量结果翻转概率。
- `p_loss`：每个活跃原子每轮的独立丢失概率。
- `p_reset`：新原子初始化错误概率，理想基线为 `0`。
- `p_reload_fail`：一次重装失败概率，理想基线为 `0`。
- `L_reload`：从检测到恢复可参与电路的完整轮数，理想基线为 `0`。

若实际 Stim 电路在门级注入噪声，必须在 `MODEL.md` 中给出上述每轮参数到每个电路位置概率的转换；禁止同时在轮级和门级重复注入同一错误。

### 4.2 丢失、检测、掩码与重装

必须用状态机实现，而不是散落的布尔判断：

```text
ACTIVE -> LOST_UNDETECTED -> LOST_DETECTED -> RELOADING -> ACTIVE
```

每个状态转换记录 `(shot, site, gate_or_round, cause, policy)`。基线在轮末检测本轮丢失；丢失发生后的无效门和检测延迟窗口必须在模型说明中逐项列出。

`missing_mask[t, q] = 1` 表示站点 `q` 在第 `t` 轮的定义时刻没有可用原子。定义时刻固定为“该轮 syndrome extraction 开始前”。若需要门级 mask，另存数组，不得偷偷改变这一主定义。

reload 只恢复物理载体并初始化为规定状态，不恢复丢失前的未知量子态。初始化状态按数据/辅助原子的电路角色确定并写入 manifest。

### 4.3 策略定义

- `none`：存储实验期间不重装。
- `immediate`：检测到丢失即请求重装；在 `L_reload` 后恢复对应站点。
- `periodic(R)`：在固定轮界 `R, 2R, ...` 对当前所有已检测空位请求重装，`R in {1,d,2d}`。
- `threshold(theta)`：轮末已检测空位数达到 `ceil(theta * N_sites)` 时重装所有已检测空位，`theta in {0.02,0.05,0.10}`。

`periodic(1)` 与理想 `immediate` 在特定时间语义下可能等价。若等价，它们必须逐 shot 输出相同结果；若不等价，报告必须明确是哪一个时序定义造成差异。

策略在时刻 `t` 的决定只能读取 `<= t` 的事件。未来丢失、最终 logical label 和 holdout 参数均不可见。

## 5. 实验矩阵

### 5.1 核心发现网格

```text
d          = {3, 5}
T          = {d, 2d}
basis      = {X, Z}
(p, p_m)   = {(1e-4,1e-4), (1e-3,1e-3), (3e-3,3e-3),
              (1e-3,3e-3), (3e-3,1e-3)}
p_loss     = {0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2}
policy     = {none, immediate, periodic(1), periodic(d), periodic(2d),
              threshold(0.02), threshold(0.05), threshold(0.10)}
ideal      = {L_reload=0, p_reset=0, p_reload_fail=0}
```

先完成小规模 pilot 以验证运行时间和事件频率，但 pilot 不得用于最终显著性结论。

### 5.2 操作成本敏感性

从发现网格中预先选择低、中、高三个 `p_loss` 区域，再运行：

```text
L_reload       = {0, 1, 2}
p_reset        = {0, 1e-3, 1e-2}
p_reload_fail  = {0, 1e-3, 1e-2}
```

一次只改变一类成本，最后再运行少量组合点。若核心网格未通过验收，不得先做扩展。

### 5.3 采样规则

- discovery：每格先运行 `20,000` shots，然后按 2 倍递增。
- 每格在累计至少 `400` 次 logical failure，或达到 `2,000,000` shots 时停止。
- 用于标题结论的 confirmation 点要求累计至少 `1,000` 次 logical failure；最多 `20,000,000` shots。
- 达到上限仍不满足精度时标为 `inconclusive_at_budget`，不得报告为“没有差异”。
- 单个错误率使用 95% Wilson 区间；策略差值使用按 `shot_id` 配对的 bootstrap 区间。
- 多策略、多参数比较使用 Benjamini-Hochberg 控制 FDR `q=0.05`。

若零失败，必须报告基于总 shots 的单侧 95% 上界，不能写成错误率等于零。

## 6. 输出与 decoder-ready 数据

每个不可变运行生成：

```text
manifest.json
shots-00000.npz
aggregates.parquet
run.log
checksums.sha256
```

NPZ shard 至少包含：

- `syndrome` 或 `detection_events`：`uint8[shots, ...]`；
- `missing_mask`：`uint8[shots, T+1, N_sites]`；
- `reload_mask`：`uint8[shots, T+1, N_sites]`；
- `logical_observable`：`uint8[shots, N_observables]`；
- `decoder_prediction`：`uint8[shots, N_observables]`；
- `shot_id`：全局唯一整数。

manifest 至少记录：

- `schema_version`、Git commit、环境 lock hash、容器 hash；
- `d`、`T`、basis、全部噪声参数；
- 策略名、参数和完整时序语义；
- site/check 的稳定排序与坐标映射；
- master seed、shot 范围、Slurm job/array ID；
- decoder 名称、版本、权重构造方法；
- 运行时间、CPU/GPU/内存资源、退出状态。

供未来模型读取的输入视图不得包含 `logical_observable`、`decoder_prediction`、隐藏物理错误链或未来事件。label 单独保存，并由 loader 明确选择训练/评估模式。

## 7. 必须通过的验证

### 7.1 正向与不变量测试

1. `p=p_m=p_loss=0`：所有策略均为零 logical failure、空 missing mask、零 reload。
2. `p_loss=0`：固定 seed 时，改变策略不得改变 syndrome、detection events 或 logical-failure count；要求逐 shot、逐 bit 相同。
3. 单一确定性丢失：`none` 必须保持缺失到结束；`immediate` 必须严格按 `L_reload` 恢复。
4. `none` 的缺失数单调不减。
5. 独立轮级 loss 下，`none` 应满足 `E[M_t]=N*(1-(1-p_loss)^t)`，Monte Carlo 结果须落在预注册置信带内。
6. 等价时序下，`periodic(1)` 与 `immediate` 逐 shot 相同。
7. 两个事件流在时刻 `t` 前相同，则策略在 `t` 前的决策必须相同，用于验证因果性。
8. 相同 manifest 在相同环境重复运行，原始数组与聚合结果 hash 相同。

### 7.2 Schema 与负向测试

validator 必须拒绝：

- 越界或不存在的坐标；
- 对从未丢失的站点执行 reload；
- 同一站点重复 reload 或非法状态转换；
- mask 长度、site 顺序、round 语义或 schema version 不匹配；
- NaN、负概率、`p>1`、非法 `d/T/R/theta`；
- candidate 读取 logical label、未来事件或 sealed holdout；
- 预先硬编码 seed/答案的 `cheater` 实现；
- 能运行但给出已知错误结果的 `wrong-answer` 实现；
- 超时实现；
- 写出工作目录、联网或尝试读取禁止路径的 `env-escape` 实现。

对 label 做替换或移除时，decoder prediction 必须保持不变；否则视为标签泄露。

### 7.3 独立交叉检查

- 小码距、短轮数 fixture 使用独立的朴素实现或可枚举计算核对。
- 至少一个参数切片用第二种实现路径复算，而不是复用同一个 sampler 的包装层。
- 聚合器用人工构造的 shot arrays 检查错误率、Wilson 区间和配对差值。

## 8. Autoresearch 评分合约

科学结果本身不作为优化分数。尤其不能奖励“更低 logical error”，因为 agent 可以通过降低噪声、丢弃失败 shots 或读取 label 作弊。

### 8.1 主指标

validator 在固定 SCNet 节点、固定 CPU 数、固定环境和 sealed workload 上计算：

```text
q3 = validated decoded shots / median_wall_seconds  (d=3)
q5 = validated decoded shots / median_wall_seconds  (d=5)
score = sqrt(q3 * q5)
```

每项运行 3 次取中位数。只有全部 guard metrics 通过时 score 有效；任一硬门失败则 `score=0`，该尝试记为失败。

### 8.2 Guard metrics

- 第 7 节全部必需测试通过；
- sealed fixture 与 oracle 的事件、mask、reload accounting 和 logical outcome 一致；
- 两次固定 seed 运行 bit-for-bit 可复现；
- 峰值 RSS 不超过 `16 GiB`；
- 单次 validator wall time 不超过 `45 min`；
- 不读取 holdout、label 或未来事件，不联网，不写出尝试 worktree；
- schema、manifest、日志和 checksum 完整；
- 相对当前 incumbent 的逻辑结果不得发生未解释的统计偏移。

候选 score 至少提高 `2%` 才替换 incumbent；低于 incumbent 但满足所有正确性门的实现可以保留为研究分支，不能覆盖最佳版本。

### 8.3 查询预算与 holdout

- 最多 `24` 次开发 validator 查询；每次尝试消耗一次，无论成功、崩溃或超时。
- 每次尝试使用独立 Git worktree，并在提交 Slurm 前先写 `LOG.md`：假设、改动、预期影响、作业 ID。
- dev seeds 可见；holdout seeds、fixture 和参数切片对 candidate 不可见。
- 只有 dev gate、科学验收清单和报告草稿均完成后，运行一次 sealed holdout。
- holdout 失败即停止并如实报告，不得查看后继续调参。

当前工作区的 `.git` 为空目录，不是有效 Git 仓库。启动 autoresearch 前必须先建立有效的本地 Git 历史；这属于版本管理，不是本机研究计算，也不得连接到 PR 提交流程。

## 9. 分阶段执行与阶段验收

### 阶段 A：冻结问题和模型

产物：`MODEL.md`、事件状态机、坐标定义、参数矩阵、预注册假设。
验收：每个变量有单位和作用时刻；`immediate`、`periodic(1)` 的关系无歧义；用户确认发表级 acceptance gate。

### 阶段 B：建立资料库与可追溯依据

产物：四篇核心文献笔记、claim-to-source 表、引用校验和。
验收：每项模型选择区分“文献事实”“挑战要求”“本研究假设”；没有用静态-loss 阈值替代动态电路结论。

### 阶段 C：实现 generator、policy、decoder 和 schema

产物：可安装源码、固定环境、最小 fixture、CLI、数据示例。
验收：所有运行均由 SCNet Slurm 作业完成；第 7.1 的确定性测试通过；输出可由独立 loader 读取。

### 阶段 D：建立 validator

产物：sealed fixtures、oracle、负向样例、资源限制和 score 输出。
验收：正确 baseline 通过；`cheater`、`wrong-answer`、`timeout`、`env-escape` 和本课题非法 reload 样例全部被拒绝。

### 阶段 E：发现网格

产物：核心参数网格、逻辑错误曲线、缺失占用曲线、reload 开销、初步区域图。
验收：每个单元格满足采样规则或明确标为预算内不确定；无静默失败或缺失点。

### 阶段 F：确认实验与成本敏感性

产物：预选关键点的高统计量复算、独立 seed 复现、Pareto 和成本敏感性。
验收：标题结论达到 confirmation 规则；所有比较使用配对区间和 FDR 控制。

### 阶段 G：一次性 holdout 与结题

产物：holdout 结果、最终数据、可复现命令、短报告。
验收：holdout 全部硬门通过，报告中的每个数字能追溯到 manifest 和 checksum。

## 10. 发表级最终验收门

必须同时满足：

1. Challenge #66 的全部 mandatory targets、四类策略、指标和数据接口完成。
2. 所有必需正向、负向、因果、复现和环境隔离测试通过。
3. 核心网格无未解释缺失；关键结论有预注册统计检验和置信区间。
4. 至少一个独立实现切片和一次独立 seed 复现支持主结论。
5. 逻辑错误、reload 次数、missing occupancy 和 wall-clock/round overhead 同时报告。
6. “帮助”定义为相对 `none` 的配对 logical-error 差值经 FDR 校正后 95% 上界 `<0`；“有害”定义为下界 `>0`；其余为“无显著差异”。
7. “最佳策略”只在明确的成本函数或 Pareto 意义下陈述。成本函数使用
   `J = p_L + lambda_r * reloads/(N_sites*T) + lambda_t * extra_rounds/T`，并报告多个 `lambda_r, lambda_t`，不得冒充唯一硬件真值。
8. `d=3,5` 只报告有限尺寸或 pseudo-threshold。若要声称渐近阈值，必须另行预注册并加入至少 `d=7,9`。
9. decoder-ready 数据通过 label 隔离测试，schema 有版本，所有公开 shard 有 checksum。
10. sealed holdout 只运行一次且通过；最终报告同时披露阴性和不确定结果。

## 11. 停止条件

成功结束：第 10 节全部满足，holdout 通过，结果和复现包完成。

立即停止并报告：

- sealed holdout 失败；
- 发现数据泄露、未来信息、随机流不公平或物理模型与 manifest 不一致；
- 三次独立复现仍出现无法解释的逻辑结果偏移；
- 集群环境或输入数据变化使冻结合约失效。

预算停止：

- 24 次 validator 查询用尽；
- 连续 5 个有效尝试未使主分数提高至少 2%；
- 用户设定的 Slurm 配额或项目截止时间耗尽；
- confirmation 达到最大 shots 后仍精度不足，此时保留 `inconclusive_at_budget` 结论。

崩溃、超时和调度后程序失败均记为一次失败尝试，不得静默重跑。纯 Slurm 基础设施故障可以重新提交，但必须保留原 job ID、退出原因和重新提交记录。

## 12. SCNet 执行规范

已验证的当前事实：

```text
SSH alias: scnet
login host: login02
scheduler: Slurm (/opt/gridview/slurm/bin/sbatch)
partition: dzagnormal
nodes seen on 2026-07-28: 9
GRES seen per node: gpu:NVIDIAA80080GBPCIeLC:8
```

执行规则：

- 本机不得运行 Python 测试、依赖安装、benchmark、validator 或 Monte Carlo。
- 所有运行由 `sbatch` 提交；登录节点不得直接执行研究程序。
- 首个作业只做环境探测，记录 OS、CPU、GPU、module、Python、文件系统和 Slurm 限制。
- 现有 harness 的 SCNet profile 与实测资源不一致，在修正并通过 guardrail 前不得直接激活。
- `dzagnormal` 的 QOS 实测强制每个作业至少申请 1 张 GPU（首次 CPU-only probe 被 `QOSMinGRES` 拒绝）；baseline 仍以 CPU 实现为准，但 Slurm 资源请求必须包含 `--gres=gpu:1`。GPU 是否参与计算由 profiler 和结果等价性决定，不能据此改写物理模型。
- 每个 job 固定环境 hash、资源、超时、输出目录；作业数组的每个 index 对应不可变 manifest。
- 先提交最小 fixture job，再提交 discovery array，最后提交 confirmation；不得一次性投放未经验证的全网格。
- `squeue`/`sacct` 状态和 exit code 写入研究数据库。`COMPLETED` 之外的状态不能进入聚合结果。
- 集群绝对工作路径须由首次探测产生并冻结；删除或覆盖集群数据前必须单独核对目标。

## 13. 最终交付物

- 可复现 simulator、reload policies、baseline decoder 和 CLI；
- 完整测试与独立 validator；
- 环境 lock/container、Slurm scripts 和资源报告；
- 核心及确认数据、manifest、checksum；
- logical-error 曲线、空位时间曲线、开销图和策略区域图；
- decoder-ready 示例与 schema；
- 简短研究报告，明确限制、阴性结果和可复现步骤；
- 不包含 challenge claim、PR 或外部提交。

## 14. 文献依据与适用边界

1. T. M. Stace, S. D. Barrett, A. C. Doherty, “Thresholds for topological codes in the presence of loss,” arXiv:0904.3556 (2009). 静态、位置已知的 loss 可通过 super-stabilizer 和路径绕行处理；纯 loss 的理想 50% 结果来自方格 bond percolation。它不能直接证明动态累积丢失或带噪 reload 的安全性。
2. J. Vala, K. B. Whaley, D. S. Weiss, “Quantum Error Correction of a Qubit Loss in an Addressable Atomic System,” arXiv:quant-ph/0510021 (2005). QND 检测空位、补入初始化原子可把 loss 转成位置已知的擦除/标准错误；其示例使用四比特 GBP code，不是表面码 benchmark。
3. F. Kobayashi, S. Nagayama, “Erasure-tolerance scheme for the surface codes on neutral atom quantum computers,” arXiv:2404.12656. 在不补充、擦除持续累积的模型中，有效码距下降，只出现有限尺寸 pseudo-threshold，渐近擦除阈值为零；其 k-shift/code-deformation 方案不等同于本挑战的原位 reload。
4. H. Perrin, G. Roger, G. Pupillo, “Correlated Atom Loss as a Resource for Quantum Error Correction,” arXiv:2603.24237v2 (2026). Rydberg CZ 可产生相关丢失；loss graph 和后验概率更新可利用 delayed-erasure 相关性，在其模型中将 loss threshold 从约 3.2% 提高到 4%，并将逻辑错误最多降低一个数量级。该结果说明 decoder/model mismatch 很重要，但不是 reload-policy 的直接答案。
