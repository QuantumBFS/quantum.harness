# Observer Ceff 交付摘要

## 一句话成果

本项目把 Born 采样、随机转移矩阵、Gaussian Majorana 演化、量子隐藏历史滤波、有限尺寸中心荷拟合和信息序全局检验连接成一条可复现计算链，并形成代码、数据、HTML、PDF 与上游 PR 的完整交付。

## 核心成果

- Clean Ising 得到 \(c=0.4999966194\)，完成几何与 Casimir 归一化标定。
- Nishimori 生产计算覆盖 \(L=6,8,\ldots,16\)，约化修正模型得到
  \(c=0.4474\pm0.0164\)。
- Weak self-dual 形成首轮生产坐标与 \(L=24\) 独立扩展坐标，完整测量有限尺寸收敛方向。
- 105/105 个生产单元完成 manifest 与 SHA-256 校验。
- 61/61 项科学和工程测试通过。
- confusion 与 erasure 两类信息损失通道完成全协方差单调序检验。
- measurement-RG 局域统计亏损得到闭式 TV 结果
  \(\delta_1=0.3535533906\) 与 \(\delta_2=0.1035533906\)。

## 最具辨识度的创新

### 1. 观察者分辨率成为可计算变量

传统轨迹计算以完整测量记录为输入。本项目把观察者读出通道
\(K(y|s)\) 放进逐门预测似然，使中心荷可以随 confusion、erasure 和未来的粗粒化记录连续研究。

### 2. 精确 oracle 与可扩展滤波器互相认证

短轨迹由精确分支枚举给出基准，生产轨迹由 fully-adapted particle filter 扩展。每一步先吸收当前观察，再采样潜在测量符号，从而集中粒子权重并提升长轨迹效率。

### 3. Gaussian 生产引擎

完整自旋态用于逐门认证，Majorana 协方差用于生产。粒子状态内存从指数振幅表示转为 \(O(P L^2)\)，直接支持更大周长和更多滤波粒子。

### 4. 跨周长配对降方差

所有周长共享嵌套随机数，有限尺寸普适差分获得完整协方差矩阵，再通过 GLS 一次映射到中心荷。这种设计把计算预算集中到普适 \(1/L\) 系数。

### 5. 全局信息序统计

所有分辨率点在同一个协方差度量中投影到非增锥，并由多元参数 bootstrap 给出通道级统计量，形成 confusion 与 erasure 的统一信息序诊断。

### 6. 精确 measurement-RG 见证

对全部经典随机后处理进行优化，得到局域量子优先与记录优先流程之间的精确 TV/KL 距离，使 measurement-RG 讨论从示意图升级为可验证数值对象。

## 公开交付

- 官方 PR：<https://github.com/QuantumBFS/quantum.harness/pull/272>
- 官方 fork 分支：<https://github.com/JunkaiWang-TheoPhy/quantum.harness/tree/codex/qmc-ranger-open-criticality-122>
- 公共独立仓库：<https://github.com/JunkaiWang-TheoPhy/observer-ceff-122>
- PDF：output/pdf/technical-report.pdf
- 数据表：results/central_charge_estimates.csv
- 机器摘要：results/submission_summary.json
