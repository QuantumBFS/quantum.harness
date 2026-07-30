# Domain Database

本数据库保存 validator 和实验生成器所需的结构化、可追溯记录；它不是论文 PDF 的重复存储。

## Records

`surface_code_instances.jsonl` 每行字段：

- `instance_id`：稳定且不携带答案的 ID；
- `schema_version`；
- `distance`、`rounds`、`basis`；
- `sites`：稳定 `site_id`、Stim qubit、`data|ancilla` 角色及坐标顺序；
- `checks`：稳定子类型、support 与边界类型；
- `logical_support`；
- `provenance`：Stim 版本、生成器 Git commit、生成器源码 SHA-256 和 Stim circuit SHA-256。

`policy_cases.jsonl` 每行字段：

- `case_id`、`schema_version`、`distance`、`rounds`、`n_sites`；
- `site_id`、确定性 loss/reload 边界、`policy` 和 reload 参数；
- `expected`：有效性、missing/reload boundary arrays 或错误码；
- `provenance`：Challenge #66 控制项、论文模型或本研究构造。

`benchmark_families.json` 冻结完整参数笛卡尔积和来源。具体坐标、checks 与 logical support 由 `export_geometry.py` 从 Stim circuit 导出到 `surface_code_instances.jsonl`；该文件只有在 SCNet locked environment 中生成并通过 oracle 后才能进入数据库，不能用手写占位记录冒充。

`cost_sensitivity_families.json` 在查看 discovery 分析前冻结 headline
slice 的 reload delay、reset error 和 reload failure 单因素及组合成本。理想
reload 与 `none` 直接引用 discovery 的同 seed 结果；文件只列出必须新增的
非理想 reload cells，避免重复模拟基线。

`confirmation_families.json` 将 `topics.md` 的 headline slice 固化为 8 个
物理点和 5 个策略，并使用与 discovery 域分离的 seed。它同时固定 1,000 次
logical failure、20,000,000 shots 上限和配对区间精度门，禁止在看到 discovery
结果后改点或改 seed。

## Provenance rules

- 代码几何由冻结的 generator 生成，并与 Stim rotated-memory circuit 的 qubit/check 坐标交叉核对。
- 文献事实只引用 `.knowledge/INDEX.md` 中的 citation key。
- 人工 fixture 明确标记 `synthetic-validator-fixture`，不伪装成实验数据。
- private holdout records 在 `research/benchmark/private/`，受 `.gitignore` 保护，不列出 labels 或 seeds。
