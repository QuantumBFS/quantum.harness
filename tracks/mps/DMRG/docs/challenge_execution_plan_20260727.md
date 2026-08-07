# VMCRG 神经网络挑战：当前基线与执行树

> 最新统一路线图见
> [`../PROJECT_STATUS_AND_ROADMAP.md`](../PROJECT_STATUS_AND_ROADMAP.md)。
> 本文件保留本轮优化器诊断的详细历史记录。

日期：2026-07-27

## 最终目标

本项目包含两个必须分开验收的目标。

### A. 论文级复现

在二维 `45x45` Ising 模型上，按 PRL 119, 220602 及 Supplementary
Material 的定义复现：

1. `3x3` 多数规则粗粒化；
2. 13 个已发表偶算符和 5 个已发表奇算符；
3. 变分偏置求重整化哈密顿量；
4. 临界点两侧的 RG 流；
5. Table I 的偶、奇主本征值及误差；
6. 有偏与无偏 Metropolis 的临界自相关比较。

“论文级复现”要求独立随机种子的统计区间覆盖论文结果。候选原始 26 项
没有公开完整坐标，因此不能把 26 到 13 的候选重构称为严格复现。

### B. 二维神经网络基础挑战

在相同二维 `45x45`、`b=3` 设置中，用平移、D4、Z2 对称的神经能量
替代固定 13 项偏置表达，并同时满足：

1. 冻结模型后的块自旋分布与均匀参考等价；
2. 独立样本投影得到的完整耦合向量满足预注册误差门槛；
3. 五个独立训练种子均通过，不能只选择成功种子；
4. 相比无偏和线性偏置对照，积分自相关时间显著下降；
5. 所有验收均使用训练外样本。

三维自旋玻璃属于后续困难挑战。二维目标全部通过前，不进入三维。

## 已确认结果

| 项目 | 状态 | 证据 |
|---|---|---|
| 2D Ising、Metropolis、局部增量 | 通过 | 全测试套件 |
| 13 偶 + 5 奇算符坐标、符号和归一化 | 通过 | Supplement 对照测试 |
| Table I 三套独立 RG2 映射 | 统计复现通过 | 论文值同时落入分层 bootstrap 95% CI |
| Table I 汇总点估计 | 已得到 | `lambda_e=3.01430`，`lambda_o=7.84600` |
| L=90 临界慢化对照 | 通过 | `tau_biased=4.98`，`tau_unbiased=475.55` |
| 神经能量 D4/Z2/平移对称与局部能差 | 通过 | 确定性测试 |
| 监督 identity-RG 表示能力 | 通过 | 13 项投影 `Linf=1.068e-4` |
| `b=3` 单种子冻结分布 | 通过 | 最大等价界 `0.002773 < 0.02` |
| `b=3` 单种子完整耦合投影 | 未通过 | `Linf=0.001808 > 0.001` |
| 随机 identity-RG 完整耦合投影 | 未通过 | `Linf=0.001613 > 0.001` |
| 冻结监督模型的 VMCRG 梯度实现 | 通过 pilot | Metropolis 与 importance oracle 一致 |
| Robbins-Monro 驻点稳定性 | 通过 pilot | 冻结验证与完整 13 项投影同时 PASS |
| 五种子纯神经正式确认 | 未开始 | 必须等待单种子硬门槛通过 |
| 神经模型 Table I | 不适用 | Table I 是论文基线，不是神经挑战替代指标 |

论文表中 `L=45` biased 点值是 `3.045` 和 `7.858`。当前三映射分层
bootstrap 区间分别为 `[2.93837, 3.05357]` 和
`[7.76379, 7.90248]`，均覆盖论文点值。它是统计意义复现，不是相同随机
轨迹或逐位复现。临界流的方向已有试验结果，但 `0.4365` 端点的独立重复
不够稳健，因此不把临界区间搜索标成最终完成。

## 当前代码结构

```text
reproduce.py
├─ 统一命令入口、参数检查、拒绝覆盖旧结果
├─ paper / full / jacobian / autocorrelation
└─ neural-* 实验入口

src/vmcrg_ref/
├─ ising.py                 二维 Ising 晶格
├─ blockspin.py             3x3 多数规则
├─ operators.py             13 偶 + 5 奇已发表算符
├─ candidate_operators.py   原始 26 项候选重构
├─ multi.py / fast.py       多算符 Metropolis 与编译加速
├─ multi_optimizer.py       论文线性 VMCRG 优化
├─ paper_observables.py     Jacobian、临界指数、自相关
├─ neural_energy.py         D4/Z2/平移对称神经能量
└─ hybrid_neural.py         神经偏置采样与随机优化

scripts/
├─ neural_challenge.py                      b=3 神经主实验
├─ neural_identity_control.py               identity-RG 随机对照
├─ neural_supervised_identity.py            表示能力认证
├─ neural_identity_gradient_diagnostic.py   冻结梯度根因诊断
├─ neural_identity_optimizer_certification.py 新优化器稳定性认证
├─ measure_paper_jacobian.py                Table I 测量
└─ compare_paper_autocorrelation.py         临界慢化测量

tests/
└─ 92 项确定性测试
```

## 2026-07-27 根因诊断

冻结已通过监督认证的 identity-RG 模型后：

- Metropolis 梯度的 L2 均值：`0.003456`；
- 该估计的 L2 标准误尺度：`0.003065`；
- importance oracle 的真实残余梯度 L2：`8.931e-5`；
- Metropolis 与 oracle 的最大差异 z 值：`2.163`，低于
  Bonferroni 门槛 `3.925`；
- 均匀对均匀零假设通过；
- 接受率：`0.999432`；
- importance reweighting 有效样本比例：`0.999962`。

结论：没有证据表明采样器、梯度符号或归一化错误。现行随机梯度噪声约为
真实残余梯度的 34 倍。固定学习率 Adam 在驻点附近继续更新，会造成参数
随机游走；这是当前首要问题。

## 2026-07-27 新优化器稳定性认证

从监督认证 checkpoint 出发，运行 200 次 Robbins-Monro SGD 更新，每次
累积 2 个独立梯度批次，总计 6400 walker-sweeps。学习率从 `0.02` 按
`power=0.75` 递减到 `0.0059994`。训练外结果：

- 冻结分布验证：`PASS`；
- 最大算符等价界：`0.011307 < 0.02`；
- excess patch-TV 上界：`0.003328 < 0.02`；
- 完整 13 项投影：`PASS`；
- 最大耦合误差：`0.0005489 < 0.001`；
- 相对 L2 误差：`0.0016116 < 0.005`。

这证明新优化器不会像固定学习率 Adam 一样立即离开正确驻点。它只证明
稳定性，尚未证明从随机初始化能够收敛。

## 工作分解树

```text
二维 VMCRG + 神经网络挑战
├─ 0. 证据与代码基线
│  ├─ 文献与 Supplement 固化                         [完成]
│  ├─ 89 项原测试                                    [完成]
│  └─ identity 梯度 oracle 诊断                       [完成 pilot]
├─ 1. 修正随机变分优化
│  ├─ 预注册梯度累积和 Robbins-Monro 学习率
│  ├─ identity RG checkpoint 稳定性                 [完成 pilot]
│  ├─ identity RG 随机初始化收敛                    [下一步]
│  └─ identity RG 独立种子重复
├─ 2. 真实 b=3 单轮神经 RG
│  ├─ L=45 冻结分布门槛
│  ├─ 13 项完整投影门槛
│  └─ candidate26 残差仅作诊断，不修改主门槛
├─ 3. 二维基础挑战正式确认
│  ├─ 五个独立训练种子
│  ├─ 无偏/线性/纯神经三臂对照
│  ├─ 自相关时间与置信区间
│  └─ 统一正式报告
├─ 4. 论文级基线补全
│  ├─ 临界 RG 流
│  ├─ Table I 偶、奇本征值
│  └─ 论文 Fig. 2 自相关
└─ 5. 三维自旋玻璃
   └─ 仅在 1--4 全部通过后另行设计                 [当前不进入]
```

## 下一步的预注册修改

只修改优化器，不改网络架构、算符坐标、投影门槛或结果：

1. 多个 MC 批次先累积梯度，再执行一次参数更新；
2. 使用满足随机逼近条件的递减学习率；
3. 保留后段 Polyak 参数平均；
4. 每个阶段冻结参数，用独立链检查完整 13 项矩和投影；
5. 先过 identity RG，再运行昂贵的 `L=45, b=3`。

禁止用结果相关的人工耦合修正、挑选成功种子或改变验收阈值。

当前已实现为可选的 `robbins_monro_sgd`；原有实验仍默认使用 `adam`，
旧协议和旧结果不会被静默改变。第一道门槛从监督认证 checkpoint 出发，
只检验随机优化是否保持正确解；通过后再进行随机初始化收敛实验。

## 可复核命令

```powershell
python reproduce.py test
python reproduce.py neural-identity-gradient `
  --preset pilot `
  --output output/neural_identity_gradient_pilot_v2

python reproduce.py neural-optimizer-stability `
  --preset pilot `
  --output output/neural_optimizer_stability_pilot_v2
```

本次已经完成的直接脚本输出为：

```text
output/neural_identity_gradient_pilot_v1/
```
