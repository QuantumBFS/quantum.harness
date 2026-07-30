# VMCRG 项目现状、结果总结与后续路线图

更新时间：2026-07-27

这是本项目当前唯一的总状态入口。历史推导、阶段协议和单次实验报告继续保留，
但判断“完成了什么、下一步做什么”时，以本文件和对应结果 JSON 为准。

## Material Passport

| 字段 | 内容 |
|---|---|
| Schema | 9 |
| 类型 | 项目状态与实验路线图 |
| 验证状态 | VERIFIED |
| 证据来源 | 本地代码、确定性测试、冻结验证和结果 JSON |
| 当前阶段 | 二维纯神经 VMCRG 优化器认证 |

## 1. 最终要达到什么

项目有三个层级，必须依次完成，不能混在一起声明。

### 目标 A：统计意义复现原论文

在二维 `45x45` Ising 模型上复现：

1. Metropolis 蒙特卡洛；
2. `3x3` 多数规则粗粒化；
3. 13 个偶算符、5 个奇算符；
4. 变分偏置和重整化哈密顿量；
5. RG Jacobian、Table I 主本征值和临界指数；
6. biased/unbiased 临界慢化对照。

验收含义是：独立运行的统计区间覆盖论文值。由于作者未公开随机种子、完整
热化日程和原始代码，不追求逐轨迹或逐比特一致。

### 目标 B：完成二维神经网络基础挑战

在二维 `45x45`、`b=3` 条件下，用平移、D4、Z2 对称的纯神经能量表示
重整化哈密顿量，并满足：

1. 固定线性偏置严格为零；
2. 冻结模型后的块自旋分布与均匀参考分布等价；
3. 神经能量在训练外样本上通过表示能力和变分目标验证；
4. 从随机初始化可以稳定收敛，不能依赖监督 checkpoint；
5. 五个独立种子均通过，不能挑选成功种子；
6. 相比无偏和线性 VMCRG，积分自相关时间显著降低；
7. 神经输出能作为下一轮 RG 的微观哈密顿量输入。

第 7 项很重要。当前代码的微观哈密顿量仍是 13 项线性模型，因此目前只支持
“线性输入到神经输出”的单轮 RG，尚不支持完整的“神经输入到神经输出”多轮
RG。这个结构性缺口必须在后续补齐。

### 目标 C：三维自旋玻璃困难挑战

在 `45x45x45` 三维自旋玻璃中研究转变温度。它需要三维晶格、无序耦合、
复制平均、温度扫描和三维神经能量。二维目标全部通过前，不进入这一阶段。

## 2. 当前总体结论

| 工作包 | 状态 | 结论 |
|---|---|---|
| 论文的二维基础算法 | 已完成 | 代码和确定性测试通过 |
| Table I | 统计复现通过 | 论文值位于分层 bootstrap 95% 区间内 |
| 临界慢化 | 通过 | biased 自相关时间显著下降 |
| 原始 26 项坐标 | 仅候选重构 | 公开材料没有给出完整原始 26 项 |
| 神经网络表示能力 | 通过 | 可以表示精确 13 项 identity-RG 哈密顿量 |
| 旧 Adam 随机 identity RG | 未通过 | 正确解附近发生噪声驱动漂移 |
| 梯度、符号和采样器诊断 | 通过 | 未发现实现错误 |
| Robbins-Monro checkpoint 稳定性 | 通过 pilot | 正确解经过随机更新后仍通过硬门槛 |
| Robbins-Monro 随机初始化收敛 | 未执行 | 当前唯一直接下一步 |
| 单轮 `L=45,b=3` 纯神经 RG | 未完成 | 旧结果的 13 项投影略超门槛 |
| 多轮神经到神经 RG | 尚未实现 | 微观神经哈密顿量接口缺失 |
| 五种子正式认证 | 未执行 | 等待单种子和多轮能力通过 |
| 三维自旋玻璃 | 未开始 | 不在当前阶段 |

所以目前不能宣称整个神经挑战完成。可以严谨地说：

> 原论文的核心二维数值结果已经达到统计复现；神经网络架构和新优化器的
> checkpoint 稳定性已经通过，但随机初始化收敛、真实 `b=3` 单轮结果、
> 多轮神经 RG 和五种子确认仍未完成。

## 3. 已有代码

```text
reproduce.py
├─ 所有正式命令的统一入口
├─ 参数检查
├─ 拒绝覆盖已有结果
└─ 测试、论文实验和神经实验编排

src/vmcrg_ref/
├─ ising.py                 二维 Ising 晶格
├─ blockspin.py             3x3 多数规则
├─ operators.py             13 偶 + 5 奇已发表算符
├─ candidate_operators.py   原始 26 项候选重构
├─ multi.py / fast.py       多算符 Metropolis 与编译加速
├─ multi_optimizer.py       论文线性 VMCRG 优化
├─ paper_observables.py     Jacobian、临界指数和自相关
├─ neural_energy.py         D4/Z2/平移对称神经能量
└─ hybrid_neural.py         神经偏置采样、Adam、Robbins-Monro SGD

scripts/
├─ neural_challenge.py
│  └─ 训练、冻结验证、13 项投影、消融、自相关
├─ neural_supervised_identity.py
│  └─ 精确 identity-RG 表示能力认证
├─ neural_identity_gradient_diagnostic.py
│  └─ Metropolis / importance oracle / uniform null 梯度对照
├─ neural_identity_optimizer_certification.py
│  └─ 新优化器 checkpoint 稳定性认证
├─ measure_paper_jacobian.py
│  └─ Table I 测量
└─ compare_paper_autocorrelation.py
   └─ 论文临界慢化测量

tests/
└─ 当前 94 项确定性测试
```

关键入口：

```powershell
python reproduce.py test
python reproduce.py neural-identity-gradient --help
python reproduce.py neural-optimizer-stability --help
python reproduce.py neural-replacement --help
python reproduce.py full --help
```

## 4. 已有论文复现结果

### 4.1 Table I

三套独立 RG2 映射的汇总点估计：

| 指标 | 当前结果 | 论文 `L=45` biased 值 | 分层 bootstrap 95% CI |
|---|---:|---:|---:|
| `lambda_even` | 3.01430 | 3.045 | `[2.93837, 3.05357]` |
| `lambda_odd` | 7.84600 | 7.858 | `[7.76379, 7.90248]` |

两个论文值都位于置信区间内，因此属于统计意义复现通过。

证据：

```text
output/reproduction/paper_table1_map_repeats/pooled_assessment.json
```

### 4.2 临界慢化

`L=90` 正式对照：

| 指标 | 结果 |
|---|---:|
| `tau_biased` | 4.9809 |
| `tau_unbiased` | 475.5463 |
| 配对比值 | 0.01069 |
| 判定 | PASS |

证据：

```text
output/reproduction/paper_fig2_L90_map_v1/
  rg2_continuation1/paper_autocorrelation.json
```

### 4.3 仍然存在的论文复现边界

- Supplement 公开了筛选后的 13 项，但没有公开原始 26 项完整坐标；
- 原始 26→13 只能称为候选敏感性实验；
- 临界流方向已有结果，但 `0.4365` 端点的独立重复不够稳健；
- 不能把固定点校准实验与论文直接 RG2 流程混成同一个结果。

## 5. 已有神经网络结果

### 5.1 网络结构

当前纯神经模型：

- 半径 3；
- hidden size 32；
- 内部 `3x3` 精确保留；
- 外部距离 2、3 使用 D4 shell；
- 精确平移、D4 和 Z2 对称；
- 无输出常数项；
- 纯神经实验中 13 项线性偏置严格为零。

核心代码：

```text
src/vmcrg_ref/neural_energy.py
src/vmcrg_ref/hybrid_neural.py
```

### 5.2 精确 identity-RG 监督认证

identity RG 中精确关系是：

```text
V_min = -H + constant
```

监督模型结果：

| 指标 | 结果 | 门槛 |
|---|---:|---:|
| 最大耦合误差 | 0.0001068 | ≤0.001 |
| 相对 L2 误差 | 0.0004244 | ≤0.005 |
| 全局投影 R² | 0.99999971 | 越接近 1 越好 |
| 判定 | PASS | — |

这证明网络架构、13 项坐标、符号、归一化和投影关系正确。

证据：

```text
output/neural_supervised_identity_formal_v1/
  supervised_identity_report.json
```

### 5.3 旧随机优化结果

固定学习率 Adam 的 identity RG：

| 指标 | 结果 | 门槛 |
|---|---:|---:|
| 冻结分布 | PASS | — |
| 最大耦合误差 | 0.001613 | ≤0.001 |
| 相对 L2 误差 | 0.007344 | ≤0.005 |
| 总判定 | FAIL | — |

旧 `L=45,b=3` 单种子：

| 指标 | 结果 | 门槛 |
|---|---:|---:|
| 最大分布等价界 | 0.002773 | ≤0.02 |
| patch-TV 上界 | 0.002143 | ≤0.02 |
| 最大 13 项投影误差 | 0.001808 | ≤0.001 |
| 相对 L2 误差 | 0.008485 | ≤0.005 |
| 投影 R² | 0.999043 | — |
| 总判定 | FAIL | — |

这些结果说明分布压平有效，但固定学习率优化不能稳定满足完整耦合向量门槛。

### 5.4 根因诊断

冻结监督模型后，比较三种梯度：

1. VMCRG Metropolis 梯度；
2. importance reweighting oracle；
3. uniform-vs-uniform 零假设。

结果：

| 指标 | 结果 |
|---|---:|
| Metropolis 梯度 L2 均值 | 0.003456 |
| Metropolis L2 标准误尺度 | 0.003065 |
| oracle 真实残余梯度 L2 | `8.93e-5` |
| Metropolis 与 oracle 最大差异 z | 2.163 |
| Bonferroni 门槛 | 3.925 |
| 判定 | 两者统计一致 |

随机梯度噪声约为真实残余梯度的 34 倍。固定学习率 Adam 在这种情况下仍会
进行近似固定幅度的坐标更新，所以会在驻点附近随机游走。没有证据表明问题
来自 Metropolis、梯度符号或归一化。

证据：

```text
output/neural_identity_gradient_pilot_v1/
  identity_gradient_diagnostic.json
```

### 5.5 Robbins-Monro checkpoint 稳定性

已经实现：

- 不按坐标除以梯度噪声的普通 SGD；
- `0.5 < decay_power <= 1` 的 Robbins-Monro 学习率；
- 多批次梯度累积；
- 后半段 Polyak 参数平均；
- 旧 Adam 仍保持为默认选项。

checkpoint pilot：

| 指标 | 结果 | 门槛 |
|---|---:|---:|
| 更新次数 | 200 | — |
| 梯度累积 | 2 | — |
| walker-sweeps | 6400 | — |
| 学习率 | `0.02 → 0.005999` | — |
| 最大算符等价界 | 0.011307 | ≤0.02 |
| patch-TV 上界 | 0.003328 | ≤0.02 |
| 最大耦合误差 | 0.0005489 | ≤0.001 |
| 相对 L2 误差 | 0.0016116 | ≤0.005 |
| 判定 | PASS | — |

它证明新优化器不会立即离开正确驻点，但还没有证明从随机初始化能够收敛。

证据：

```text
output/neural_identity_optimizer_stability_pilot_v1/
  optimizer_stability_report.json
```

## 6. 唯一直接下一步：随机初始化 identity-RG 收敛

### 6.1 要回答的问题

在不知道精确答案、只使用 VMCRG 随机梯度的情况下，Robbins-Monro 优化器
能否从随机神经网络收敛到已知的 identity-RG 精确解？

这是进入 `L=45,b=3` 前的强制门槛。

### 6.2 需要新增的代码

计划新增：

```text
scripts/neural_identity_random_convergence.py
tests/test_neural_identity_random_convergence.py
reproduce.py neural-identity-random
```

这些入口目前尚未实现，不能直接运行。

### 6.3 预注册 pilot 参数

| 参数 | 固定值 |
|---|---:|
| 晶格 | `15x15` |
| block size | 1 |
| 模型 | radius-3 multiscale MLP, hidden 32 |
| 初始化 | 随机，输出权重为零 |
| walkers | 8 |
| optimizer updates | 1000 |
| 每梯度块 sweeps | 5 |
| gradient accumulation | 2 |
| target samples/梯度块 | 32 |
| 初始学习率 | 0.02 |
| decay scale | 250 |
| decay power | 0.75 |
| 参数平均起点 | 第 500 次更新 |
| 总 walker-sweeps | 80000 |
| 训练、验证、投影随机流 | 相互独立 |

### 6.4 pilot 硬门槛

必须同时满足：

1. 固定线性偏置的 L∞ 范数为 0；
2. 冻结分布验证 `PASS`；
3. 最大算符等价界 ≤0.02；
4. excess patch-TV 上界 ≤0.02；
5. 13 项投影最大误差 ≤0.001；
6. 13 项投影相对 L2 误差 ≤0.005；
7. 所有结果来自训练外样本。

如果失败：

- 不改变阈值；
- 不人工修正耦合；
- 不挑选 checkpoint；
- 不立即尝试多组学习率；
- 冻结失败模型，用现有 gradient oracle 判断是未收敛还是随机估计误差；
- 根据预注册诊断另立下一份实验协议。

如果通过：

- 使用两个全新随机种子重复相同 pilot；
- 三个 pilot 均通过后，进入正式 identity 认证。

## 7. 后续执行计划

### 阶段 N1：随机初始化 identity-RG

```text
N1.1 实现统一入口和协议锁定测试
N1.2 执行单种子 pilot
N1.3 冻结模型并运行分布、投影、gradient oracle
N1.4 使用两个新种子独立重复
N1.5 三个 pilot 一致后进入 formal
```

正式 identity 参数采用相同无量纲日程：

- 16 walkers；
- 3000 updates；
- 每块 20 sweeps；
- accumulation 2；
- target samples 32；
- learning rate 0.02；
- decay scale = `steps/4 = 750`；
- decay power 0.75；
- 后 50% 参数平均；
- 每个种子 1,920,000 walker-sweeps。

正式模式至少完成三个独立训练种子。

### 阶段 N2：单轮 `L=45,b=3` 纯神经 RG

只有 N1 通过后执行：

1. 从 13 项近似固定点输入开始；
2. 固定线性偏置为零；
3. 使用相同 Robbins-Monro 比例日程；
4. 冻结后运行 16 条独立验证链；
5. 运行 20000 构型投影；
6. 同时投影到 13 项和 candidate26，记录 RG 产生的基底外项；
7. 运行 held-out 变分目标消融；
8. 不再把 13 项投影误差单独当成神经表示失败的唯一证据。

这里必须区分两个问题：

- 13 项投影是否接近原截断固定点；
- 神经网络是否学到了 13 项之外的真实 RG 相互作用。

由于神经网络的目的就是提高表示能力，candidate26 中的稳定非零项不能通过
后处理删除；应作为神经模型超出 13 项基底的物理结果报告。

### 阶段 N3：实现神经到神经的多轮 RG

当前缺少的核心接口：

```text
H_micro(sigma) = U_phi(sigma)
H_eff(sigma) = U_phi(sigma) + V_theta(tau(sigma))
```

需要实现：

1. 微观神经哈密顿量 `U_phi` 的局部能差；
2. 微观神经缓存和块自旋神经偏置缓存同时更新；
3. 第一轮输出网络作为第二轮输入网络；
4. 每轮重新在相同尺寸晶格上采样；
5. 神经哈密顿量之间去除不可识别的加性常数后比较；
6. 在独立构型上测量相邻 RG 轮次的能量差和分布差；
7. 至少完成五轮 RG，判断是否接近神经函数空间中的固定点。

新增接口必须先通过：

- 神经微观能量局部差与全局重算一致；
- 编译采样器与 Python 参考采样器轨迹一致；
- identity neural-to-neural 映射不漂移；
- 一轮线性到神经结果与现有实现一致。

### 阶段 N4：二维基础挑战正式确认

执行五个完全独立的训练种子。每个模型都必须进入汇总，不能按结果筛选。

正式对照分三臂：

1. 无偏 Metropolis；
2. 论文 13 项线性 VMCRG；
3. 纯神经 VMCRG。

主要指标：

- 冻结分布等价界；
- held-out 变分目标；
- 13/26 项投影；
- 多轮固定点残差；
- 积分自相关时间；
- 训练成本和每个有效独立样本成本；
- 五种子分层 bootstrap 置信区间。

只有 N1–N4 全部通过，才能声明二维神经网络基础挑战完成。

### 阶段 N5：三维自旋玻璃

二维完成后另立新协议，至少需要：

- 三维周期晶格；
- `45x45x45` 局部更新；
- quenched disorder 样本；
- 多副本 overlap 观测量；
- 温度扫描和有限尺寸标度；
- 三维对称神经能量；
- disorder-level bootstrap；
- 过渡温度的独立验证。

二维代码不能直接改一个维度参数就用于三维。

## 8. 总工作树

```text
VMCRG 挑战
├─ A. 原论文二维复现
│  ├─ Ising / Metropolis / block spin                 [完成]
│  ├─ 13 偶 + 5 奇算符                               [完成]
│  ├─ Table I                                        [统计复现通过]
│  ├─ 临界慢化                                       [完成]
│  └─ 原始 26→13                                     [仅候选重构]
├─ B. 二维纯神经 VMCRG
│  ├─ 网络结构与局部能差                             [完成]
│  ├─ 监督 identity 表示能力                         [完成]
│  ├─ 梯度 oracle 根因诊断                           [完成]
│  ├─ Robbins-Monro checkpoint 稳定性                 [完成 pilot]
│  ├─ 随机初始化 identity 收敛                       [下一步]
│  ├─ L=45,b=3 单轮神经 RG                           [待执行]
│  ├─ 神经到神经多轮 RG                              [待实现]
│  ├─ 五独立种子                                     [待执行]
│  └─ 三臂自相关正式对照                             [待执行]
└─ C. 三维自旋玻璃
   └─ 45x45x45 转变温度                              [二维完成后]
```

## 9. 禁止事项

后续实验不得：

- 根据结果改变验收阈值；
- 用人工耦合修正补救神经投影；
- 只汇报成功随机种子；
- 在训练轨迹上执行最终验收；
- 把 candidate26 当成论文公开的原始坐标；
- 把一次神经 RG 宣称为多轮 RG；
- 在二维未完成时直接外推三维临界温度；
- 覆盖已有输出目录。

## 10. 当前应执行的顺序

```text
1. 实现随机初始化 identity-RG 入口
2. 运行 1000-update pilot
3. 汇报冻结分布、13 项投影和 gradient oracle
4. 通过后做两个独立重复
5. 进入 formal identity
6. 运行 L=45,b=3 单轮纯神经 RG
7. 实现 neural-to-neural 多轮 RG
8. 五种子与三臂自相关正式确认
9. 完成二维挑战报告
10. 再设计三维自旋玻璃
```

当前唯一直接下一步是第 1 项。
