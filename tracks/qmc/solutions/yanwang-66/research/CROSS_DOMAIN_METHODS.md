# Cross-Domain Methods

Date: 2026-07-29

## Scope and conclusion

本笔记评估密码学、网络安全、分布式系统、数据库、信号处理、可靠性工程、运筹优化
和形式化验证方法能否改善 Challenge #66 的选择性事件记录、回放、因果解码、重装
策略和研究审计。结论分为两层：

- 这些方法不能把丢失的未知量子态变成可加载的经典快照，也不能绕过 loss QEC。
- 它们可以显著改善事件记录的完整性、模拟确定性回放、输入因果性、实验预注册和
  多节点 artifact 的可审计性。

## Candidate evaluation

| Method | Original use | Transfer to Challenge #66 | Decision |
|---|---|---|---|
| Minimal deterministic record/replay | ReVirt 只记录非确定输入，逐指令重放被入侵虚拟机 | 记录 manifest、counter-addressed RNG、观测 loss/reload 事件和环境版本；由此重建全部 mask 和 simulator output | Adopt as validator/replay design |
| Hash chain / Merkle append-only log | 安全审计日志、Certificate Transparency | 对 immutable shard、manifest 和 Slurm phase 建立有序 commitment，检测删除、替换和重排 | Conditional adoption at artifact level |
| Commit-then-reveal | 密码学 commitment 和公平协议 | 运行前承诺 matrix/manifest/seed family，结果冻结后揭示允许公开的 seed，抑制事后挑选参数 | Adopt for expensive confirmation runs |
| Forward-secure logging/signatures | 主机被攻陷后仍保护此前日志 | 若 validator threat model 包含计算节点或密钥事后泄露，可保护已完成 phase | Defer until an adversarial-node threat is declared |
| VRF / verifiable randomness | 可验证且不可预测的伪随机输出 | validator 可证明 sealed noise plan 来自预承诺 key/address，而不是为结果挑选 | Defer; current reproducible SplitMix stream is sufficient for a non-adversarial benchmark |
| Provenance/dependency graph | BackTracker 等系统从 OS 事件图回溯攻击根因 | 把观测 interaction/loss/syndrome 组织成因果图，用于相关丢失扩展和 failure attribution | Future extension after independent-loss baseline |
| Information-flow/taint tracking | 检测不可信输入如何传播到敏感 sink | 为 decoder 字段标注 observed/public/hidden/future，验证 prediction 不依赖 label 或未来事件 | Adopt as anti-leak validator concept |
| Reed-Solomon/erasure-coded storage | 存储系统的数据损坏恢复 | 可保护大型实验 shard 的磁盘可靠性，但不能恢复量子态 | Infrastructure-only, not a scientific method |
| Zero-knowledge proof of execution | 在不暴露 witness 时证明计算正确 | 理论上可证明 simulator 遵守模型，但为浮点、PyMatching 和大规模 Monte Carlo 构造电路成本过高 | Reject for core scope |
| Blockchain | 多方不互信下的公共共识日志 | 本项目没有需要全局共识的参与方；signed/Merkle manifest 已覆盖实际需求 | Reject |
| Homomorphic encryption | 对密文执行计算 | 解决数据机密性，不解决量子 loss、decoder correctness 或 replay | Reject unless a future data-privacy requirement appears |

## Recommended design changes

### 1. Replay contract

定义版本化 `replay trace`，但不逐事件重复保存可由 RNG 重建的数据。最小记录应为：

- canonical request and geometry hash;
- source commit and environment lock hash;
- `master_seed`, shot range and event-address schema version;
- policy and reload configuration;
- only externally observed or manually injected event overrides;
- expected artifact root hash.

验证器从 trace 重建公开 arrays，要求与 artifact bitwise 一致。这与 ReVirt 的关键
原则相同：确定性部分重新执行，只记录非确定边界输入。

### 2. Artifact-level tamper evidence

不要为数百万个 loss event 分别签名。应在现有 checksum 基础上按 shard/phase 建立：

```text
entry_hash = H(schema || sequence || previous_hash || payload_hash)
phase_root = MerkleRoot(entry_hashes)
```

记录连续 sequence、shot range 和 previous root。它能检测 shard 删除、替换和重排。
但若 commitment 与 artifact 始终由同一可改写目录保存，它只提供一致性检查，不提供
强独立见证；更强保证需要独立签名者、远程时间戳或只追加存储，需另行授权。

### 3. Pre-run commitment

在提交昂贵的 confirmation/holdout 作业前冻结：

```text
commitment = SHA256(canonical_manifest || seed_material || random_salt)
```

将 commitment、Git commit、Slurm job ID 和时间写入审计记录。公开实验结束后可揭示
manifest/salt 复核；sealed holdout 不揭示 seed，由独立 validator 验证并签署结果。
低熵 seed 必须加高熵 salt，否则 commitment 可能被枚举。

### 4. Decoder information-flow policy

为 schema 字段声明来源与最早可见边界：

```text
observed_now | observed_history | public_metadata | hidden_fault | label | future
```

decoder 只允许前三类。现有 label-poison 和 prefix-causality tests 应继续作为行为验证；
字段标注是额外的静态审计信息，不能替代测试。

### 5. Causal graph as a separate physics extension

网安 provenance graph/attack graph 的迁移对象不是“攻击者”，而是错误传播：

```text
interaction -> possible loss mechanism -> observed loss set
            -> invalid stabilizer -> detection events -> decoder edges
```

该图可帮助相关-loss mechanism attribution，与 Perrin 的 loss graph 思路相容。它会
改变 decoder/model surface，因此不能进入冻结的 independent-loss core baseline；应
独立版本、单独 validator，并报告移除图上下文后的 ablation。

## Practical priority

1. 先完成当前 pilot/discovery 正确性门，不改冻结物理模型。
2. 在 schema/validator 中增加 replay trace 和字段信息流分类。
3. 在 confirmation 前加入 manifest commitment；只有发生跨节点传输或审计需求时，
   再把现有 flat checksums 升级为 shard-level hash chain/Merkle root。
4. 核心结果完成后，才实验 causal loss graph。
5. 不为当前 challenge 实现 blockchain、FHE 或通用零知识执行证明。

## Sources

- Dunlap et al., “ReVirt: Enabling Intrusion Analysis Through Virtual-Machine Logging and Replay,” OSDI 2002: https://www.usenix.org/legacy/events/osdi02/tech/dunlap.html
- Schneier and Kelsey, “Secure Audit Logs to Support Computer Forensics,” ACM TISSEC 1999, DOI: https://doi.org/10.1145/317087.317089
- Ma and Tsudik, “A New Approach to Secure Logging,” ACM TOS 2009, DOI: https://doi.org/10.1145/1502777.1502779
- Crosby and Wallach, “Efficient Data Structures for Tamper-Evident Logging,” USENIX Security 2009: https://www.usenix.org/legacy/event/sec09/tech/full_papers/crosby.pdf
- King and Chen, “Backtracking Intrusions,” SOSP 2003, DOI: https://doi.org/10.1145/945445.945466
- RFC 9162, Certificate Transparency Version 2.0: https://www.rfc-editor.org/rfc/rfc9162
- RFC 9381, Verifiable Random Functions: https://www.rfc-editor.org/rfc/rfc9381
- NIST SP 800-92, Guide to Computer Security Log Management: https://csrc.nist.gov/pubs/sp/800/92/final

## Broader field evaluation

### Distributed systems and databases

| Method | Useful transfer | Boundary | Decision |
|---|---|---|---|
| Chandy-Lamport distributed snapshot | 从多个控制/测量 stream 取得因果一致的经典 telemetry cut；避免把不同 round boundary 的事件拼成一个伪快照 | 它不能快照纠缠量子态；marker algorithm 只适用于经典 channel/process state | Adopt the consistent-boundary concept, not a quantum snapshot claim |
| Lamport logical clocks / partial order | 用 `(shot, round, boundary, site, sequence)` 表达 happens-before，而不是依赖节点 wall clock | 当前单进程 simulator 已有 round/site 地址；主要用于未来硬件或分布式采集 | Conditional adoption for multi-stream traces |
| Write-ahead logging and ARIES-style recovery | 保存 checkpoint 加有序 delta，重建 simulator/pipeline state；失败作业可审计到最后完整 shard | 只能 redo/undo 经典软件状态，不能撤销物理 loss 或 measurement | Adopt for artifact pipeline only |
| State-machine replication/consensus | 可复制控制状态并容忍节点故障 | 项目没有在线多副本控制面，也没有共识参与方 | Reject for core scope |

工程上最有用的组合是“boundary checkpoint + append-only delta”。每个 delta 必须带
逻辑边界和前序 hash；重建时拒绝 gap、duplicate 或跨边界重排。当前固定形状 mask
仍是公开 decoder 接口，稀疏 delta 是可验证的存储/回放来源，不能成为第二套模糊语义。

### Signal processing and probabilistic inference

| Method | Useful transfer | Boundary | Decision |
|---|---|---|---|
| Hidden Markov model / Bayesian filtering | 从带误报、漏报或延迟的 loss observations 在线估计 `ACTIVE/LOST/RELOADING` belief | 冻结 baseline 在轮末完美揭示 loss，不需要额外 hidden-state estimator | High-value extension for imperfect detection |
| Factor graph / sum-product | 把局部 gate、候选 loss mechanism、syndrome 和边权组织为概率图，传播软信息 | 需要独立验证 hyperedge/correlation 处理，不能静默替换 MWPM | Future decoder comparison after baseline |
| Kalman filter | 连续线性高斯系统中的递推状态估计 | carrier state 和 syndrome 是离散、非高斯且带拓扑约束；直接套用会模型失配 | Reject for baseline; use discrete Bayesian models instead |
| Bayesian smoothing | 实验结束后结合前后观测推断历史 loss time | 会使用某一时刻之后的信息，不能驱动在线 reload policy；decoder 是否可用取决于冻结因果合约 | Offline diagnostics only unless model is versioned |

用户提出的“只记录有意义的信息”在这里对应 sufficient observation，而不是任意压缩。
是否有意义必须由生成模型验证：移除该字段会损失哪些后验信息，新增字段是否在决策
时真实可见。不能根据最终 logical label 反向选择记录字段。

### Reliability engineering and operations research

| Method | Useful transfer | Boundary | Decision |
|---|---|---|---|
| Condition-based maintenance | 根据观测到的 vacancy/health 触发修复，对应 threshold reload | 机械维护经验参数不能直接成为量子 reload 参数 | Adopt as policy-analysis framework |
| Scheduled preventive maintenance | 固定周期维修，对应 `periodic(R)` | 只是策略同构，不自动证明最优周期 | Already represented in core benchmark |
| Checkpoint-interval optimization | 平衡 checkpoint 开销与故障后损失，启发 `reload interval` 的成本权衡 | checkpoint 保存进度，而 reload 不保存丢失量子态；经典公式不能直接套用 | Use analogy and cost structure only |
| MDP | 在完全可观测 occupancy/state 下最小化长期 logical-risk 与 reload cost | 精确状态空间随站点数指数增长，需要对称性或聚合状态 | Future exact optimizer on small instances |
| POMDP | 在检测延迟/误报下，用 belief state 决定何时 reload | 会增加模型、参数和验证面；不能替代预注册四类策略结果 | High-value post-core extension |
| Survival/hazard modelling | 从硬件 telemetry 估计 site/round-dependent loss hazard 和 reload failure risk | 当前模型冻结为独立常数 `p_loss`; 硬件数据缺失时不可凭空拟合 | Future hardware-calibration layer |

该领域最可能改善 challenge 的不是新增一个任意 heuristic，而是建立一个小规模动态
规划 oracle：在 `d=3`、短 `T` 和聚合 occupancy state 上求成本函数的最优动作，再
测量 `none/immediate/periodic/threshold` 距 oracle 的 regret。它是策略参考上界，不是
新的 headline baseline，也不能用不同物理模型与现有策略比较。

### Formal verification, testing, and process mining

| Method | Useful transfer | Boundary | Decision |
|---|---|---|---|
| Temporal logic / model checking | 穷举检查 loss/reload 状态机、边界 `T`、失败重试、阈值计数和 causal policy invariants | 不能证明数值 decoder 或物理模型真实，只证明形式规格内的状态行为 | Conditional adoption with high validator value |
| Model-based/property testing | 从状态机生成合法/非法 event sequences，与生产实现和独立 oracle 对照 | 随机 fuzz 不能替代穷举 corner fixtures | Adopt; current policy cases are an initial form |
| Process mining/conformance checking | 从实际 event log 检查是否符合允许的 transition model，定位缺失或乱序事件 | 不应从最终成功日志反向学习并放宽规范 | Adopt for artifact validation concept |
| Fault injection/chaos testing | 注入确定性单 loss、reload failure、timeline shift 和进程失败 | 只能验证已注入故障族，不能证明未知故障不存在 | Already adopted; expand by risk, not volume |

最小形式模型只需要有限站点和有限轮数，不需要模拟量子振幅。建议状态变量为
`carrier_state`, `reload_due`, `boundary`, `revealed_history`，检查：

```text
ACTIVE cannot complete reload
RELOADING cannot receive a duplicate request
policy output is prefix-causal
none occupancy is pathwise monotone
ideal immediate == periodic(1)
every loss remains in the append-only event history
```

### Causal inference and experimental design

- Common random numbers 对应同一 shot 的潜在结果耦合，当前 counter-addressed RNG 已
  正确采用，可降低 policy difference 方差。
- 在 simulator 中有随机化噪声计划时，直接 paired comparison 比复杂 observational
  causal adjustment 更可信，不需要 propensity score。
- 若未来使用真实硬件历史比较不同 policy，policy assignment 可能受到设备健康状态
  影响，届时才需要 sequential causal inference/off-policy evaluation；不能把观察相关
  性直接写成 reload 的因果收益。
- Sequential testing 可以节省 shots，但 stopping rule 和多重比较必须预注册；当前
  discovery 的 failure target/cap 已承担这个角色，不应另加未冻结的 bandit 选点。

## Broader-method priority

1. **现在有用且不改变物理模型**：event boundary/partial order、replay delta、字段信息
   流分类、状态机 model-based tests、process conformance checks。
2. **核心 benchmark 完成后优先研究**：小规模 MDP policy oracle；带 detection error
   或 delay 的 HMM filter/POMDP；相关 loss 的 factor graph。
3. **需要真实硬件数据后再研究**：hazard calibration、digital-twin parameter update、
   observational policy evaluation。
4. **不采用**：把分布式 snapshot、数据库 rollback 或 Kalman filter描述成未知量子态
   的通用 save/load。

## Additional sources

- Chandy and Lamport, “Distributed Snapshots: Determining Global States of Distributed Systems,” ACM TOCS 1985, DOI: https://doi.org/10.1145/214451.214456
- Lamport, “Time, Clocks, and the Ordering of Events in a Distributed System,” CACM 1978, DOI: https://doi.org/10.1145/359545.359563
- Mohan et al., “ARIES: A Transaction Recovery Method Supporting Fine-Granularity Locking and Partial Rollbacks Using Write-Ahead Logging,” ACM TODS 1992, DOI: https://doi.org/10.1145/128765.128770
- Kalman, “A New Approach to Linear Filtering and Prediction Problems,” 1960, DOI: https://doi.org/10.1115/1.3662552
- Rabiner, “A Tutorial on Hidden Markov Models and Selected Applications in Speech Recognition,” Proceedings of the IEEE 1989, DOI: https://doi.org/10.1109/5.18626
- Kschischang, Frey, and Loeliger, “Factor Graphs and the Sum-Product Algorithm,” IEEE Transactions on Information Theory 2001, DOI: https://doi.org/10.1109/18.910572
- Kaelbling, Littman, and Cassandra, “Planning and Acting in Partially Observable Stochastic Domains,” Artificial Intelligence 1998, DOI: https://doi.org/10.1016/S0004-3702(98)00023-X
- Jardine, Lin, and Banjevic, “A Review on Machinery Diagnostics and Prognostics Implementing Condition-Based Maintenance,” MSSP 2006, DOI: https://doi.org/10.1016/j.ymssp.2005.09.012
- Young, “A First Order Approximation to the Optimum Checkpoint Interval,” CACM 1974, DOI: https://doi.org/10.1145/361147.361115
- Lamport, “The Temporal Logic of Actions,” ACM TOPLAS 1994, DOI: https://doi.org/10.1145/177492.177726
- van der Aalst et al., “Process Mining Manifesto,” BPM Workshops 2011, DOI: https://doi.org/10.1007/978-3-642-28108-2_19
