# Table I 直接论文流程：独立 RG2 映射复现协议 v1

## Material Passport

- Schema: 9
- Artifact Type: code experiment plan
- Version Label: `paper_table1_map_repeats_v1`
- Status: preregistered before the three formal runs
- Paper: Wu and Carrasquilla, Phys. Rev. Lett. 119, 220602 (2017)
- Scope: `L=45`、已发表 13 个偶算符和 5 个奇算符、Table I biased 结果

## 要解决的问题

单一 RG2 映射的 Jacobian 置信区间只包含蒙特卡洛抽样误差，不能覆盖“变分优化得到哪个
RG2 映射”的随机性。固定点校准会改变研究对象，不能代替论文从 `K_nn=0.436` 直接执行
两轮 RG 的流程。因此本协议独立重复整个 RG1→RG2 映射，再分层汇总映射间和映射内误差。

## 冻结设计

每个 repeat 完整独立，固定参数为：

- 初始二维 Ising：`L=45`，`K_nn=0.436`；
- 两轮 RG，每轮 3000 个变分步，每步 20 sweeps，16 walkers；
- 学习率 `mu=5e-5`；
- 不使用 Newton 固定点校准，不复用旧映射；
- RG1 输出的完整 13 维耦合作为 RG2 输入；
- 仅 RG2 通过硬门槛后，才允许 Table I 测量；
- Table I：16 个独立 run，每个 `10^6` 测量 sweeps，间隔 1 sweep；
- Jacobian bootstrap：2000 次 run-level 重采样。

三个 repeat 的全部 RG、冻结验证、Jacobian 和 bootstrap 随机流在以下清单中预先冻结：

- `config/paper_table1_repeat1.json`
- `config/paper_table1_repeat2.json`
- `config/paper_table1_repeat3.json`

论文未公开 Table I 的热化长度、随机种子和完整测量日程。本协议采用 5000 sweeps 的
Jacobian 热化和 500 sweeps 的冻结验证热化；它们是实现选择，不冒充论文原始参数。

## RG2 硬门槛

`scripts/assess_paper_rg_gate.py` 同时要求：

1. 耦合、漂移和冻结矩 z 分数都是完整的 13 维有限向量；
2. 后 20% 轨迹可以分块估计统计误差；
3. 后 20% 平均协方差正定；
4. 从 90% 到 100% 轨迹的 13 个耦合分量最大绝对漂移不超过 `0.001`；
5. 冻结偏置使用至少 16 个独立 run、每个至少 1000 sweeps；
6. 13 个目标矩在 family alpha `0.05` 的双侧 Bonferroni 检验下全部通过。

阈值是预注册的实现验收标准，不是论文发表的阈值。任何一项失败，命令以非零状态停止，
保留 `rg2/gate_report.json`，并且不创建 Jacobian 结果。禁止根据失败结果修改阈值后续跑。

## 执行顺序

先只检查命令：

```powershell
python reproduce.py paper-table1-repeat --repeat 1 --dry-run
python reproduce.py paper-table1-repeat --repeat 2 --dry-run
python reproduce.py paper-table1-repeat --repeat 3 --dry-run
python reproduce.py paper-table1-assess --dry-run
```

正式执行：

```powershell
python reproduce.py paper-table1-repeat --repeat 1
python reproduce.py paper-table1-repeat --repeat 2
python reproduce.py paper-table1-repeat --repeat 3
python reproduce.py paper-table1-assess
```

repeat 必须依次执行并保留所有中间结果。失败 repeat 不自动重试，也不能进入汇总。

## 汇总方法和最终验收

`paper-table1-assess` 读取三个通过硬门槛的 `jacobian.npz`，执行 10000 次分层 bootstrap：

1. 有放回抽取三个 RG2 映射；
2. 在每个被抽取映射内，有放回抽取 16 个独立 MC run；
3. 合并充分统计量，重新构造 `A`、`B` 和 `T=B^{-1}A^T`；
4. 每次重新求偶、奇最大本征值。

另行报告只重采样 run 和只重采样映射的分布，作为非可加的不确定性敏感性分解。最终通过
条件是：全部 bootstrap 数值稳定，并且论文 `L=45` biased 值 `3.045`、`7.858` 同时落入
同一个 pooled hierarchical 95% 区间。未通过时结论是“当前直接流程不能在预注册标准下复现
Table I”，不能用神经网络或后处理修补该结论。
