# Wu–Carrasquilla VMCRG 论文复现

论文：Phys. Rev. Lett. 119, 220602 (2017)，arXiv:1707.08683。

项目的最新结果、当前边界、下一步和完整工作树统一记录在
[`PROJECT_STATUS_AND_ROADMAP.md`](PROJECT_STATUS_AND_ROADMAP.md)。继续实验前应先读取该文件。

项目现在使用根目录的 `reproduce.py` 作为统一入口。物理实现仍按功能拆分在
`src/vmcrg_ref/`，统一入口只负责固定参数、执行顺序、输出目录和验证，避免复制算法代码。

神经网络代码的完整调用关系和实现声明见
[`docs/neural_challenge.md`](docs/neural_challenge.md)。核心代码不是单文件：
实验编排位于 `scripts/neural_challenge.py`，采样与优化位于
`src/vmcrg_ref/hybrid_neural.py`，神经能量位于 `src/vmcrg_ref/neural_energy.py`。

论文直接复现和固定点敏感性研究使用不同入口：`full` 严格从论文采用的
`K_nn=0.436` 出发，并固定在第二轮 RG 系综测量 Table I；`fixed-point-*`
和 `table1-v5-repeat` 研究完整 13 维固定点选择造成的系统误差，不能替代
论文直接流程，也不能把两类结果混合汇总。

## 当前边界

- Supplementary Material 明确给出筛选后保留的 13 个偶算符，因此 13 项主流程有文献坐标依据。
- 原始 26 项完整坐标和预筛选输入耦合没有公开，因此 `candidate26` 只能称为候选敏感性实验，不能称为严格论文复现。
- 神经网络是研究扩展，不属于原论文结果。`neural-easy` 只保留为单训练种子
  可行性入口；最终二维基础挑战确认必须使用锁定的五种子入口：
  `python reproduce.py neural-confirm --preset formal --output-root <新目录>`。
  方法和验收标准见 `docs/neural_challenge.md`。
- 神经优化中的均匀块自旋是变分参考分布，不代表微观模型处于无限高温。
  物理温度由输入的无量纲耦合 `K` 决定。非均匀参考若只提供样本而不提供
  `log p_ref`，不能用于恢复重整化哈密顿量。

## 环境

在 PowerShell 中进入本目录：

```powershell
cd "C:\Users\11597\Desktop\蒙特卡洛重整化群"
```

统一入口会自动设置 `PYTHONPATH=src`，不需要手动配置。

## 1. 运行全部测试

```powershell
python reproduce.py test
```

## 2. 单轮论文 RG

以下命令使用论文的 `L=45` 参数，并在优化后自动执行轨迹分析和独立冻结偏置验证：

```powershell
python reproduce.py paper --coupling 0.436 --rounds 1
```

默认参数：

- `L=45`
- 13 个已发表偶算符
- 3000 variational steps
- 每步 20 sweeps
- 16 walkers
- `mu=5e-5`

输出位于：

```text
output/reproduction/paper_L45_K0p4360000/rg1/
```

其中：

- `summary.json`：重整化耦合；
- `trajectory.npz`：完整优化轨迹；
- `convergence.json`：后 20% 轨迹收敛分析；
- `frozen_validation.json`：冻结偏置独立验证。

## 3. 连续三轮论文 RG

```powershell
python reproduce.py paper --coupling 0.436 --rounds 3
```

每轮使用上一轮的重整化耦合作为新的微观哈密顿量，并使用新的随机种子。每轮都执行独立冻结验证。

正式计算前可只检查将要执行的命令：

```powershell
python reproduce.py paper --coupling 0.436 --rounds 3 --dry-run
```

## 4. 论文级端到端流程

先用 smoke 模式验证全部程序连接。它只使用极少样本，结果没有物理意义：

```powershell
python reproduce.py full --preset smoke --output-root output/smoke_full
```

正式 `L=45` 流程：

```powershell
python reproduce.py full --preset formal --output-root output/paper_L45_formal
```

它依次执行：

1. 五轮 13 项 VMCRG；
2. 每轮轨迹分析和冻结偏置验证；
3. 在第二轮冻结系综测量论文 Eqs. 16–17 的协方差；
4. 解 `A=T^T B`，得到 13 维偶 Jacobian 和 5 维奇 Jacobian；
5. 对 16 个独立运行做 run-level bootstrap；
6. 输出主本征值、`y_t`、`y_h`、`nu`、`eta`、`beta`、`gamma`、`alpha`；
7. 比较论文估计量 `S0(sigma)S0(sigma')` 的 biased/unbiased 自相关；
8. 生成 `paper_report.json` 和 `paper_results.png`。

正式模式计算量很大。执行前必须先检查：

```powershell
python reproduce.py full --preset formal --output-root output/paper_L45_formal --dry-run
```

Table I 明确给出 `L=45` 使用 16 个独立运行和约 `10^6` MC sweeps，但没有公开热化长度、随机种子和全部测量日程。本实现把这些未公开选择完整写入结果 JSON，不能把它们伪装成论文原参数。

## 5. 单独计算 Jacobian 和临界指数

输入必须是第二轮 RG 的输出目录：

```powershell
python reproduce.py jacobian `
  --input output/reproduction/paper_L45_K0p4360000/rg2
```

矩阵使用线性方程求解，不显式计算 `B^-1`。输出为 `paper_jacobian.json/.npz`。

## 6. 单独计算临界慢化

```powershell
python reproduce.py autocorrelation `
  --input output/reproduction/paper_L45_K0p4360000/rg2
```

输出为 `paper_autocorrelation.json/.npz`。

## 7. 查看候选 26 项坐标

```powershell
python reproduce.py derive26
```

## 8. 候选 26→13 敏感性实验

默认同时运行二体第 13 项的两种并列选择：`(5,0)` 和 `(4,3)`。

```powershell
python reproduce.py candidate26 --coupling 0.436
```

输出分别位于：

```text
output/reproduction/candidate26_L45_K0p4360000/axis5/
output/reproduction/candidate26_L45_K0p4360000/generic43/
```

这里的 `0.436` 是用户指定值，不是论文公开的预筛选参数。即使两套结果都筛出已发表的 13 项，也只能说明结果对该坐标歧义不敏感。

## Table I 映射不确定性正式入口

不要再用单个 RG2 映射判断 Table I 是否复现。当前正式入口独立重建三套
`K_nn=0.436 → RG1 → RG2` 映射；RG2 的完整 13 维耦合稳定性和 13 个冻结目标矩
全部通过硬门槛后，才会运行 `16 × 10^6` sweeps 的 Jacobian 测量：

```powershell
python reproduce.py paper-table1-repeat --repeat 1 --dry-run
python reproduce.py paper-table1-repeat --repeat 1
python reproduce.py paper-table1-repeat --repeat 2
python reproduce.py paper-table1-repeat --repeat 3
python reproduce.py paper-table1-assess
```

任一 repeat 的 `rg2/gate_report.json` 为 `FAIL` 时会立即停止，不会运行高成本
Jacobian。三个通过的 repeat 使用分层 bootstrap 汇总，协议见
`docs/paper_table1_map_replication_protocol_v1.md`。

## 常用参数

```powershell
python reproduce.py paper --help
python reproduce.py full --help
python reproduce.py jacobian --help
python reproduce.py autocorrelation --help
python reproduce.py candidate26 --help
python reproduce.py paper-table1-repeat --help
python reproduce.py paper-table1-assess --help
```

已有输出默认不会被覆盖。需要重跑时应指定新的 `--output-root`，保留旧结果以便审计。

## 代码位置

- `src/vmcrg_ref/ising.py`：二维 Ising 模型；
- `src/vmcrg_ref/blockspin.py`：`3×3` 多数规则；
- `src/vmcrg_ref/operators.py`：论文确认的 13 个偶算符和 5 个奇算符；
- `src/vmcrg_ref/multi.py`、`fast.py`：有偏 Metropolis；
- `src/vmcrg_ref/multi_optimizer.py`：Supplement Eq. S1–S3 随机优化；
- `src/vmcrg_ref/paper_observables.py`：Jacobian、临界指数和自相关统计；
- `src/vmcrg_ref/candidate_operators.py`：原始 26 项候选重构；
- `scripts/measure_paper_jacobian.py`：偶、奇 RG 矩阵与 bootstrap；
- `scripts/assess_paper_rg_gate.py`：RG2 完整耦合向量和冻结矩硬门槛；
- `scripts/assess_paper_table1_repeats.py`：跨 RG2 映射的分层 bootstrap；
- `scripts/compare_paper_autocorrelation.py`：论文临界慢化对照；
- `scripts/assemble_paper_report.py`：结果汇总和绘图；
- `scripts/neural_challenge.py`：完整神经基础挑战；
- `scripts/neural_confirmation.py`：五训练种子、每模型 32 条消融链和分层 bootstrap 确认；
- `scripts/`：底层运行、验证和分析脚本；
- `tests/`：确定性测试。
