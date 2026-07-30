# 第五阶段：L=45 纯神经 VMCRG 正式多种子协议 v1

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: plan
- Origin Date: 2026-07-20
- Verification Status: VERIFIED
- Version Label: neural_replacement_formal_plan_v1

## Experiment Overview

- **目标**：检验不含13项线性偏置的神经能量，能否在二维 L=45 Ising VMCRG 中独立表示重整化哈密顿量并降低采样自相关；
- **表示**：半径3、D4/Z2 对称、32隐藏单元 shell MLP；固定线性偏置严格为零；
- **设计**：5个完全独立的训练重复；训练、验证、投影、消融、自相关和bootstrap随机流全部不同；
- **协议文件**：`config/neural_replacement_formal_v1.json`；
- **协议 SHA256**：`B735515D5C8D5014B19FDD53DA0944688204CD7522039F5BFC6CFE99F8B80171`。

## Frozen Setup

| 项目 | 冻结值 |
|---|---:|
| 晶格 | 45×45 |
| 分块 | 3×3多数规则 |
| 训练重复 | 5 |
| 每个重复变分步 | 3000 |
| walkers | 16 |
| 每步每walker sweeps | 20 |
| 每步目标样本 | 32 |
| 学习率 | 0.0005 |
| 轨迹平均开始 | 第1500步 |
| 固定线性偏置 | 全部为0 |

每个重复含960000个 walker-sweeps；5个重复共4800000个 walker-sweeps。根据 pilot 的训练吞吐量，单纯训练部分估计约2.37小时。包含验证、投影和消融后，预估总耗时约5–7小时；这是运行时间估计，不是统计结果。

## Primary Gates

五个训练重复必须全部满足：

1. 13项算符的 `abs(mean)+2SE ≤ 0.02`；
2. patch-TV 上界 `≤ 0.02`；
3. 固定点投影 L∞ 残差 `≤ 0.001`；
4. 固定点投影相对 L2 残差 `≤ 0.005`。

跨重复还必须满足：

5. 至少4/5个消融重复的平均 `ΔΩ < 0`；
6. 分层bootstrap的消融上界 `< 0`；
7. 每个重复的自相关时间配对比值上界 `≤ 0.5`；
8. 分层bootstrap自相关比值上界 `≤ 0.5`。

所有门槛同时通过才允许声明“二维 L=45 纯神经替代通过”。该结论不包含论文 Table I 本征值，也不包含三维自旋玻璃。

## Early-stop Rule

先完成5个重复的训练、冻结分布验证、13项投影和消融。若其中任一前置门槛失败，正式结论已确定为 FAIL，协议规定不再运行自相关阶段，以避免无效计算。不得修改门槛后重跑。

## Entry Command

```powershell
python reproduce.py neural-replacement-confirm --output-root output/neural_replacement_confirmation_formal_v1
```

运行前自动执行完整测试。输出目录必须为空；程序拒绝覆盖既有结果。

## Expected Outputs

| 输出 | 说明 |
|---|---|
| `run_manifest.json` | 协议、固定点输入及全部代码哈希 |
| `repeat_1` 至 `repeat_5` | 每个独立重复的模型、轨迹和链级统计 |
| `pre_autocorrelation_assessment.json` | 前置正式门槛 |
| `confirmation_report.json` | 最终多种子结论；仅在前置门槛通过后产生 |

## Monitoring

- 监测标准输出中的 `train n/3000`；
- 每个重复训练结束后必须出现非空的 `bias_model.npz`、`trajectory.npz` 和 `config.json`；
- 不对崩溃任务自动重试，不覆盖部分结果；
- 运行中不得根据梯度或中间结果改变学习率、步数或验收门槛。

## Known Risk

pilot 的绝对分布误差和固定点残差仍远高于正式门槛。正式长轨迹可能失败；该失败属于有效实验结果，不能用事后调参修补。
