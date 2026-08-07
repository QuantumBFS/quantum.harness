# Issue 71 张量网络实验结果

结论：题面提示的 MPS/BDD 方向对结构诊断很有效，但本次严格
train-only 的连续 MPS/ALS 没有精确恢复 A/B/C/D 中任何一个函数，
也没有产生可提交的挑战电路。

## 运行与证据

- warmup pilot：Slurm 42645。
- train-only unfolding rank：42681，16/16 cells 成功。
- continuous MPS：42698，64/64 cells 成功。
- `afterok` 哈希汇总：42747。
- MPS→共享 ROBDD→门网表：42790，4/4 cells 成功。
- 所有随机流从根种子 42 稳定派生。
- 每次提交前均记录 `sinfo`、`squeue` 和 n006 的
  `State`、`CfgTRES`、`AllocTRES`。

完整记录见 `submission_record.json` 与
`distill-job-42790/distill_submission_record.json`。

## 精确 TT 秩诊断

下表是完整算术真值张量在相应变量序下，各输出位、各 cut 的最大
Boolean TT rank。它只在训练和模型冻结后的 audit 阶段计算。

| 实例 | blocked LSB/MSB | interleaved LSB/MSB | 解释 |
|---|---:|---:|---|
| A：加法 | 255 / 255 | 3 / 3 | 按位交错把 carry 暴露为小状态 |
| B：绝对差 | 128 / 128 | 5 / 5 | 按位交错把 borrow/比较状态暴露出来 |
| C：乘法 | 62 / 62 | 61 / 61 | 一维链序无法消除乘法高秩瓶颈 |
| D：平方和 | 19 / 19 | 30 / 30 | blocked 顺序反而更适合两个独立平方子函数 |

## Train-only 连续 MPS

模型选择只使用训练集内部 80/20 划分：先最大化 validation exact，
再最大化 validation bit，随后最小化 validation RMSE，最后偏好较小 χ。
完整真值准确率没有参与选择。

| 实例 | 训练选择的顺序、χ | float64 参数 | validation exact / bit | full exact / bit | 冻结模型 SHA-256 前缀 |
|---|---|---:|---:|---:|---|
| A | interleaved MSB，8 | 13,032 | 0.2225 / 0.87861 | 0.23730 / 0.87882 | `aaaa0b9f` |
| B | interleaved LSB，8 | 8,344 | 0.61333 / 0.93190 | 0.64178 / 0.93243 | `66dd77e3` |
| C | interleaved LSB，8 | 11,232 | 0.05000 / 0.78785 | 0.17383 / 0.81724 | `00adc239` |
| D | blocked MSB，4 | 2,552 | 0.20000 / 0.88750 | 0.34277 / 0.90146 | `d1a50f33` |

64 个 MPS 配置中，完整定义域 exact 的模型数为 0。高 bit accuracy
不能替代逐行 exact；这些模型不是挑战候选。

## 实际 MPS→BDD→电路转换

每个实例仅使用上表由 train validation 选出的冻结模型。完整枚举其
阈值函数，bottom-up hash 成共享多输出 ROBDD，再把每个节点转换成
简化 MUX 的 AND/OR 网表。独立严格解析器已在完整定义域证明序列化
网表与对应 MPS 阈值函数完全等价。

| 实例 | ROBDD 非终端节点 | 网表门数 | 对真值错误行 | 网表 SHA-256 前缀 |
|---|---:|---:|---:|---|
| A | 13,454 | 27,262 | 49,984 / 65,536 | `15311b03` |
| B | 4,057 | 8,362 | 5,869 / 16,384 | `25e903c1` |
| C | 3,476 | 7,143 | 3,384 / 4,096 | `7845c251` |
| D | 727 | 1,479 | 673 / 1,024 | `442557c7` |

这些是“近似 MPS 的精确电路”，不是“算术真值的精确电路”；
四个 artifact 均明确标记 `challenge_candidate=false`。

## 可复现产物

- 主 JSON：`summary-rank42681-mps42698/summary.json`
  （SHA-256 `e8b35a5d43f1617484ccbd9d240d1952b8f423c514a412461f06c4c629256d84`）。
- 图：`summary-rank42681-mps42698/tn-results.png`。
- 64 个冻结 MPS：`mps-job-42698/cells/`。
- 16 组 rank 诊断：`rank-job-42681/cells/`。
- 四个 ROBDD/netlist 报告和网表：`distill-job-42790/cells/`。
