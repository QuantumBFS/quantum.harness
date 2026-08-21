# 技术报告：二维横场 Ising 模型有限温张量网络（METTS）基准研究

> 项目名称：2D_TN_Challenge —— 二维有限温张量网络基准
> 作者：`{{Jing Yang , Peng Peng / 2D-TN-Team}}`
> 报告版本：`{{AUTO:REPORT_VERSION}}`　生成日期：`{{AUTO:REPORT_DATE}}`
> Git 提交：`{{AUTO:GIT_COMMIT_SHORT}}`（分支 `{{AUTO:GIT_BRANCH}}`，工作区 `{{AUTO:GIT_WORKTREE_STATUS}}`）
> 运行编号：`{{AUTO:RUN_ID}}`

<!-- 占位符约定：{{AUTO:...}} 由脚本从 data/processed/ 与 data/manifests/ 自动填充，禁止手改；
     {{TODO:...}} 为待人工填写项。渲染后运行 check_report.py --fail-on-unresolved-auto 检查。 -->

---

## 1. 摘要与主要结论

本项目在 $10\times10$ 开放边界（OBC）正方晶格横场 Ising 模型上，以 **METTS（最小纠缠典型热态）为主路线**实现二维有限温张量网络算法，并保留 PEPO 路线作为探索性对照；以无符号问题的 QMC 作为同尺寸数值精确基准完成全部验证。模型哈密顿量

$$H=-J\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z-h\sum_i\sigma_i^x,\qquad J=1,$$

计算点取量子临界点 $h_c/J\approx 3.044$ 附近的 $h/J\in\{2.5,\,3.0,\,3.5\}$（覆盖铁磁侧、临界区、顺磁侧），温度窗口 $\beta J\in[0.1,\,1.0]$（量子临界扇区）。计算自由能密度 $f$、内能密度 $u$、比热 $C$（加分项：均匀磁化率 $\chi$），并按 §5 的误差定义与 §6 的收敛协议完成 QMC 锚定的精度验证；同时在同等精度标准下系统记录时间–内存–精度关系，并与 tanTRG / MPO-LTRG 基线对比。

主要结论：

1. 自由能密度：`{{AUTO:SUMMARY_FREE_ENERGY_RESULT}}`
2. 内能密度：`{{AUTO:SUMMARY_INTERNAL_ENERGY_RESULT}}`
3. 比热：`{{AUTO:SUMMARY_SPECIFIC_HEAT_RESULT}}`
4. 与 QMC 的一致性：`{{AUTO:SUMMARY_QMC_AGREEMENT_RESULT}}`
5. 低温可达性（最大稳定 $\beta J$）：`{{AUTO:SUMMARY_LOWEST_TEMPERATURE_RESULT}}`
6. 精度–代价表现：`{{AUTO:SUMMARY_PERFORMANCE_RESULT}}`

---

## 2. 研究目标与交付物验收标准

### 2.1 研究目标

以 METTS 为主路线将有限温张量网络方法推进到二维，并在存在数值精确有限尺寸参考数据的基准上，系统验证其**正确性**（vs QMC / ED）、**收敛性**（样本数 / 键维数 / 虚时步长 / 环境维数）、**低温稳定性**（最大可达 $\beta J$）与**资源开销**（时间–内存–精度权衡）。PEPO 路线作为探索性对照一并实现与验证，用于评估两条路线在同一基准上的相对优劣。最终目标是在诚实的、QMC 锚定的 accuracy-vs-cost 对比下接近或超过 tanTRG 基准（Ref. [6]）。

### 2.2 必选交付物

| # | 交付物 | 验收标准 | 对应章节 | 状态 |
|---:|---|---|---|---|
| 1 | 热力学曲线 $f(T),\,u(T),\,C(T)$ | 覆盖 $\beta J\in[0.1,1.0]$，三个横场 | §8.1–8.3 | `{{AUTO:DELIVERABLE_THERMO_STATUS}}` |
| 2 | 收敛分析（含图） | METTS：样本数收敛 + 统计误差分析；PEPO（探索）：≥3 个 $D$ | §6, §8.5 | `{{AUTO:DELIVERABLE_CONVERGENCE_STATUS}}` |
| 3 | QMC 参考验证 | 同一 $10\times10$ OBC；报告 $u$、$C$ 相对误差与低温可达性 | §8.6 | `{{AUTO:DELIVERABLE_QMC_STATUS}}` |
| 4 | 源代码 + 技术文档 + 一键测试脚本 | 单命令复现基准结果 | §10 | `{{AUTO:DELIVERABLE_REPRODUCIBILITY_STATUS}}` |

### 2.3 加分项

| # | 交付物 | 验收标准 | 对应章节 | 状态 |
|---:|---|---|---|---|
| 5 | tanTRG 对比 | 同 $h$ 下比较精度、耗时、内存（注意键维数口径差异） | §8.7 | `{{AUTO:BONUS_TANTRG_STATUS}}` |
| 6 | 均匀磁化率 $\chi(T)$ | 温度曲线 + 与 QMC 比较 | §8.4 | `{{AUTO:BONUS_SUSCEPTIBILITY_STATUS}}` |
| 7 | 小尺寸 ED 校验 | $4\times4$ 精确对角化 sanity check 通过 | §4.6 | `{{AUTO:BONUS_ED_STATUS}}` |
| 8 | 多尺寸分析 | 有限尺寸效应或尺寸外推 | §8.8 | `{{AUTO:BONUS_FINITE_SIZE_STATUS}}` |

---

## 3. 模型定义

### 3.1 哈密顿量与单位约定

$$H=-J\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z-h\sum_i\sigma_i^x,\qquad J=1.$$

- $\sigma_i^{x,z}$ 为格点 $i$ 上的 Pauli 算符，$\langle i,j\rangle$ 为正方晶格最近邻键；
- 自然单位 $k_{\mathrm B}=\hbar=1$，能量以 $J$ 为单位，$\beta=1/T$；
- 该模型为 stoquastic（无符号问题），QMC 可提供数值精确的有限尺寸基准，使本报告所有断言可检验（Ref. [9, 10]）。

### 3.2 晶格、边界与参数

| 参数 | 符号 | 数值 | 备注 |
|---|---|---|---|
| 晶格尺寸 | $L_x\times L_y$ | $10\times10$ | 正方晶格 |
| 格点总数 | $N=L_xL_y$ | $100$ | 希尔伯特空间维数 $2^{100}\approx1.27\times10^{30}$ |
| 最近邻键数 | $N_b$ | $L_x(L_y-1)+L_y(L_x-1)=180$ | OBC |
| 边界条件 | — | 开放边界（OBC） | |
| 耦合常数 | $J$ | $1$ | 能量单位 |
| 横场 | $h/J$ | $\{2.5,\ 3.0,\ 3.5\}$ | 见 §3.4 |
| 量子临界点（参考值） | $h_c/J$ | $\approx3.044$ | Ref. [9] |
| 逆温范围 | $\beta J$ | $[0.1,\,1.0]$ | 即 $T/J\in[1.0,10.0]$ |
| 逆温网格 | — | `{{AUTO:BETA_GRID}}` | 默认等间隔 $0.1:0.1:1.0$；如加密须记录 |
| 网格点数 | $N_\beta$ | `{{AUTO:N_BETA_POINTS}}` | TN 与 QMC 须在**完全相同**的 $\beta$ 点取值 |

### 3.3 热力学量定义与计算方式

配分函数 $Z(\beta)=\operatorname{Tr}\,e^{-\beta H}$，热力学期望 $\langle O\rangle=\operatorname{Tr}(Oe^{-\beta H})/Z$。

| 观测量 | 定义 | 计算方式 |
|---|---|---|
| 自由能密度 | $f=-\dfrac{\ln Z}{\beta N}$ | 张量网络直接收缩 $\ln Z$ 数值上不稳定，采用**热力学积分**：$\beta f(\beta)=-\ln 2+\displaystyle\int_0^{\beta}u(\beta')\,\mathrm d\beta'$（用到 $\beta\to0$ 时 $Z\to2^N$）。采用复合梯形积分，在比热峰附近与低温端对 $u(\beta)$ 网格局部加密，加密至相邻两轮积分估值的相对变化 $<10^{-3}$ |
| 内能密度 | $u=\langle H\rangle/N$ | 对每个 METTS 样本收缩 $\langle H\rangle$（逐键 / 逐点项求和）后做样本平均；PEPO 路线直接收缩 |
| 比热 | $C=\dfrac{\beta^2\big(\langle H^2\rangle-\langle H\rangle^2\big)}{N}$ | **方案 A（涨落公式）**：收缩 $\langle H^2\rangle$，注意大数相消；**方案 B（数值微分）**：$C=-\beta^2\,\mathrm du/\mathrm d\beta$，差分格式与平滑参数记录在案，并**与方案 A 交叉验证**。报告以方案 A 为准，方案 B 作校验 |
| 均匀磁化率（加分） | $\chi=\dfrac{\beta}{N}\sum_{i,j}\big(\langle\sigma_i^z\sigma_j^z\rangle-\langle\sigma_i^z\rangle\langle\sigma_j^z\rangle\big)$ | 有限尺寸零纵场下 $\langle\sigma_i^z\rangle=0$（$Z_2$ 对称化严格保证，见 §3.4），简化为 $\chi=\dfrac{\beta}{N}\Big\langle\Big(\sum_i\sigma_i^z\Big)^2\Big\rangle$ |

### 3.4 量子临界区域与 $Z_2$ 对称性的利用

- $h/J=2.5$：临界点以下（铁磁侧）；$h/J=3.0$：临界区内（**最重要的压力测试点**，能隙小、关联长度大、热态压缩最难）；$h/J=3.5$：临界点以上（顺磁侧）。
- **$Z_2$ 对称性：启用。** 对称算符 $\Pi=\prod_i\sigma_i^x$ 满足 $[H,\Pi]=0$。采用两层实现方式：
  1. **张量层面**：所有张量使用 $Z_2$ 量子数守恒的块稀疏表示（如 TensorKit 的 `Z2Irrep`、ITensor 的 QN 守恒模式），虚拟键按 $Z_2$ 电荷分块，同等截断精度下内存与计算量约降低一半；
  2. **采样层面（METTS 特有）**：$\sigma^z$ 乘积基坍缩使单个样本破缺 $Z_2$，但系综平均必须恢复之。采用**对偶采样**（antithetic sampling）：每个样本 $|\phi_m\rangle$ 与其 $Z_2$ 伙伴 $\Pi|\phi_m\rangle$ 成对计入系综，零额外演化代价使方差约降低一倍，并严格保证 $\langle\sigma_i^z\rangle=0$（§3.3 中 $\chi$ 的化简即依赖此性质）。
- 对称化实现的正确性由 §4.6 的 ED 校验与高温极限检验共同验证。

---

## 4. 方法描述

### 4.1 算法路线

主路线：**METTS**；探索性对照路线：PEPO（§4.2）；对照基线：QMC、tanTRG / MPO-LTRG。实现状态：`{{AUTO:ALGORITHM_IMPLEMENTATION_STATUS}}`

### 4.2 PEPO 路线（探索性对照）

PEPO 路线不作为生产路线，但完成实现与基本验证是值得的：它与 METTS 共享局域门分解、虚时演化与收缩基础设施，可在同一基准上提供独立的交叉验证，并为后续工作（变分压缩、无限尺寸推广）保留接口。

未归一化密度算符 $\rho(\beta)=e^{-\beta H}$ 以 PEPO 表示：$\beta=0$ 时 $\rho=\mathbb I$ 为乘积算符，虚时演化

$$\frac{\partial\rho}{\partial\beta}=-H\rho$$

按 Trotter–Suzuki 分解逐步施加局域门。二阶分解：

$$e^{-\Delta\beta(H_A+H_B)}=e^{-\frac{\Delta\beta}{2}H_A}\,e^{-\Delta\beta H_B}\,e^{-\frac{\Delta\beta}{2}H_A}+\mathcal O(\Delta\beta^3).$$

**实现要点**：局域门按最近邻键分解，行 / 列方向交错施加；每步演化后对 PEPO 按行重归一化以防止数值溢出；压缩采用变分优化（最小化 $\lVert\widetilde{\rho}-\rho_{\rm gate}\rVert_F^2$，交替最小二乘求解，相对变化 $<10^{-10}$ 判收敛），简单截断作为对照；观测量用逐行边界 MPS 收缩，环境维数 $\chi_{\rm env}$；演化全程监控 $\rho$ 的范数与纠缠谱以诊断缠结增长。

| 参数 | 符号 | 取值 |
|---|---|---|
| 虚时演化方案 / 步长 | — / $\Delta\beta$ | `{{AUTO:PEPO_IMAGINARY_TIME_SCHEME}}` / `{{AUTO:PEPO_DELTA_BETA}}` |
| 键维数扫描序列 | $D$ | $\{{{AUTO:PEPO_BOND_DIMENSIONS}}\}$（≥3 个，如 $4,6,8$） |
| 压缩方式 | — | `{{AUTO:PEPO_COMPRESSION_SCHEME}}` |
| 环境收缩方法 / 维数 | — / $\chi_{\rm env}$ | `{{AUTO:PEPO_CONTRACTION_METHOD}}` / `{{AUTO:PEPO_ENVIRONMENT_DIMENSION}}` |
| 截断误差阈值 | $\epsilon_{\rm trunc}$ | `{{AUTO:PEPO_TRUNCATION_TOLERANCE}}` |

### 4.3 METTS 路线（主路线）

METTS 将热平衡期望写为最小纠缠典型热态的样本平均：

$$\langle O\rangle_\beta\approx\frac{1}{M}\sum_{m=1}^{M}\frac{\langle\phi_m|e^{-\beta H/2}\,O\,e^{-\beta H/2}|\phi_m\rangle}{\langle\phi_m|e^{-\beta H}|\phi_m\rangle},$$

马尔可夫链由"测量坍缩 $\to$ 虚时演化"交替生成。坍缩基取 $\sigma^z$ 乘积基（对 Ising 型相互作用方差最小），并按 §3.4 做 $Z_2$ 对偶采样。二维化采用 PEPS（或按行映射的 MPS）表示样本态，重点控制采样方差与演化中的缠结增长。

| 参数 | 符号 | 取值 |
|---|---|---|
| 虚时演化方案 / 步长 | — / $\Delta\beta$ | `{{AUTO:METTS_IMAGINARY_TIME_SCHEME}}` / `{{AUTO:METTS_DELTA_BETA}}` |
| 样本数序列 / 生产样本数 | $M$ / $M_{\rm prod}$ | `{{AUTO:METTS_SAMPLE_COUNTS}}` / `{{AUTO:METTS_PRODUCTION_SAMPLE_COUNT}}` |
| PEPS/MPS 键维数 | $D$ | `{{AUTO:METTS_BOND_DIMENSION}}` |
| 截断阈值 | $\epsilon_{\rm trunc}$ | `{{AUTO:METTS_TRUNCATION_TOLERANCE}}` |
| 坍缩基 | — | $\sigma^z$ 乘积基（+$Z_2$ 对偶采样） |
| 独立链数 | $N_{\rm chain}$ | `{{AUTO:METTS_CHAIN_COUNT}}`（≥4，不同种子与初始态） |
| 热化样本数 | $M_{\rm warmup}$ | `{{AUTO:METTS_WARMUP_SAMPLES}}` |
| 分箱大小 | $M_{\rm bin}$ | `{{AUTO:METTS_BIN_SIZE}}` |

**采样与误差估计方案（多链一致性 + 分箱 + 自相关诊断）**：

1. **多链并行**：$N_{\rm chain}\ge4$ 条独立马尔可夫链，使用不同随机种子与不同初始乘积态；
2. **热化与稀疏化**：每条链丢弃前 $M_{\rm warmup}$ 个样本；测量间隔取 $\ge2\tau_{\rm int}$（按观测量自相关时间确定），抑制样本间自相关；
3. **链内误差**：分箱（binning）分析估计标准误差 $\sigma_{\bar O}$，bin 大小取至 SEM 进入平台期；
4. **链间一致性**：Gelman–Rubin 势尺度缩减因子 $\hat R$ 诊断链间混合，要求全部观测量 $\hat R<1.05$，否则加深采样；
5. **合成与标度验证**：各链均值合成总平均与总 SEM；在每个温度点验证 $\sigma_{\bar O}\propto1/\sqrt M$ 标度，作为样本近似有效的判据；
6. 生产样本数 $M_{\rm prod}$ 由 $\beta J=0.8$ 处达标所需样本数确定（§6.3）。

### 4.4 tanTRG / MPO-LTRG 基线

tanTRG 为当前 2D 有限温基准：在张量网络流形切空间内做最优虚时演化，复杂度为温和的 $\mathcal O(D^3)$，已在 $10\times10$ Hubbard 模型验证（Ref. [6]）。

**数据来源（双途径，以自行复算为主、文献数据为补充校验）**：

- **主要来源——自行复算**：基于 ThermoTN 开源代码（`FiniteMPS.jl` + `FiniteLattices.jl`）实现 tanTRG / MPO-LTRG，备选实现为 ITensor 的 `tdvp` / `linsolve` 模块。复算在本项目同机、同线程设置下进行（§11.3），以获得可与本方法公平对比的耗时与内存数据，这是精度–代价对比（§8.7）的必要前提；
- **补充来源——Ref. [6] 已发表数据**：用于校验复算实现的正确性与精度量级（模型与参数不同时仅作量级参照）。

基线参数：$D_{\rm MPO}=$ `{{AUTO:TANTRG_BOND_DIMENSION}}`，截断阈值 `{{AUTO:TANTRG_TRUNCATION}}`。
**公平性约定**：MPO 与 PEPO/PEPS 键维数**不可直接比较**；对比一律在"达到同等 $\epsilon_{\rm rel}$ 所需的 wall-clock 与峰值内存"层面进行，且各自在其自身键维数上先完成收敛（§6）。

### 4.5 QMC 参考基准

模型无符号问题，QMC 在同尺寸 $10\times10$ OBC 上以可忽略代价给出数值精确基准（平均符号 $=1$）。

| 参数 | 符号 | 数值 |
|---|---|---|
| 算法 | — | `{{AUTO:QMC_METHOD}}`（SSE / worm；实现 `{{AUTO:QMC_IMPLEMENTATION}}`） |
| 热化 / 测量步数 | $N_{\rm warmup}$ / $N_{\rm measure}$ | `{{AUTO:QMC_WARMUP_SWEEPS}}` / `{{AUTO:QMC_MEASUREMENT_SWEEPS}}` |
| 测量间隔 / 分箱大小 | — | `{{AUTO:QMC_MEASUREMENT_INTERVAL}}` / `{{AUTO:QMC_BIN_SIZE}}` |
| 独立种子数 | $N_{\rm seed}$ | `{{AUTO:QMC_SEED_COUNT}}` |
| 误差估计方法 | — | `{{AUTO:QMC_ERROR_ESTIMATOR}}`（blocking / jackknife / bootstrap） |
| 有效样本数 | $N_{\rm eff}$ | `{{AUTO:QMC_EFFECTIVE_SAMPLE_COUNT}}` |

**基准质量判据**：QMC 统计误差须至少比待验证 TN 误差小一个量级（$\sigma_{\rm QMC}/\epsilon_{\rm TN}\lesssim0.1$），否则须加深采样后方可作基准。参考数据文件：`{{AUTO:QMC_DATA_PATH}}`，SHA-256：`{{AUTO:QMC_DATA_SHA256}}`。

### 4.6 开发期精确对角化校验（sanity check）

在 $4\times4$ OBC（$2^{16}$ 维）上做精确对角化（ED），对以下内容做三方（ED / TN / QMC）交叉验证：哈密顿量构造、高温极限（$\beta\to0$ 时 $u\to0$、$C\to0$、$\beta f\to-\ln2$）、观测量归一化、虚时演化符号与收缩归一化、$Z_2$ 对称化实现。通过判据：$\epsilon_{\rm rel}<10^{-4}$（TN 取大 $D$、大 $M$ 极限）。状态：`{{AUTO:ED_SANITY_CHECK_STATUS}}`

---

## 5. 误差定义与统计约定

### 5.1 与 QMC 的偏差（主验证指标）

对任意观测量 $O\in\{f,u,C,\chi\}$，逐温度点定义

$$\epsilon_{\rm abs}(O;\beta)=\big|O_{\rm TN}(\beta)-O_{\rm QMC}(\beta)\big|,\qquad \epsilon_{\rm rel}(O;\beta)=\frac{\epsilon_{\rm abs}(O;\beta)}{\max\big(\big|O_{\rm QMC}(\beta)\big|,\,10^{-12}\big)}.$$

全温度窗口汇总指标（$N_T$ 个温度点）：

$$\operatorname{MAE}(O)=\frac{1}{N_T}\sum_i\epsilon_{\rm abs}(O;\beta_i),\qquad \operatorname{RMSE}(O)=\sqrt{\frac{1}{N_T}\sum_i\epsilon_{\rm abs}(O;\beta_i)^2},$$

并报告最大误差及其所在温度点。QMC 自身统计误差以平方和合成：$\epsilon=\sqrt{\epsilon_{\rm TN\text{-}QMC}^2+\sigma_{\rm QMC}^2}$（当 $\sigma_{\rm QMC}\ll\epsilon_{\rm abs}$ 时可忽略）。

### 5.2 算法内误差

| 误差来源 | 定义 / 标度 | 控制方式 |
|---|---|---|
| 截断误差 | 丢弃权重 $w=1-\dfrac{\sum_{i\le D}\lambda_i^2}{\sum_j\lambda_j^2}$（$w$ 越小越好） | 增大 $D$；在 $w\to0$ 上外推（§6.2） |
| Trotter 误差 | 二阶分解单步 $\mathcal O(\Delta\beta^3)$，全程累积 $\mathcal O(\Delta\beta^2)$ | $\Delta\beta$ 减半扫描（§6.4） |
| 环境收缩误差 | $\chi_{\rm env}$ 加倍前后 $\lvert O_{\chi}-O_{2\chi}\rvert$ | $\chi_{\rm env}$ 扫描（§6.5） |
| 统计误差（METTS / QMC） | 标准误差 $\sigma_{\bar O}=\sigma_O/\sqrt{N_{\rm eff}}$，$N_{\rm eff}=M/(2\tau_{\rm int})$ | 多链 + 分箱 + $\hat R$ 诊断（§4.3） |

### 5.3 项目精度目标与低温可达性定义

- 精度目标（对 $u$、$C$）：$\epsilon_{\rm rel}(u)<1\%$，$\epsilon_{\rm rel}(C)<3\%$。
- **最大稳定逆温**：$\beta J_{\max}:=\max\{\beta J\le1.0:\ \text{数值稳定（无发散 / 非正定范数）且 }\epsilon_{\rm rel}(u)<1\%,\ \epsilon_{\rm rel}(C)<3\%\}$。
- 比热特别提示：涨落公式为大数相消（$\langle H^2\rangle-\langle H\rangle^2$），相对误差被放大；报告 $C$ 时须同时给出 $u$ 的精度作参照（§3.3 交叉验证）。

### 5.4 报告约定

数值一律写作"最佳估计 $\pm\,1\sigma$"；相对误差以百分比报告；图中误差棒含义在每图图注中注明（统计 / 截断 / 合成）。

---

## 6. 收敛协议

### 6.1 收敛轴与扫描顺序

收敛性沿四条独立的轴分别检验（每次只动一个轴，其余固定在生产值）：虚时步长 $\Delta\beta$ → 环境维数 $\chi_{\rm env}$ → 键维数 $D$ → 样本数 $M$（METTS）。单轴收敛判据：相邻两档观测量的相对变化小于**目标精度的 1/3**（保守因子，避免多轴误差叠加超标）。

### 6.2 键维数 $D$ 收敛

- METTS：在生产样本数 $M_{\rm prod}$ 下扫描张量键维数；PEPO（探索）：至少 $D\in\{4,6,8\}$ 三档。
- 出图温度：$\beta J=0.1$ 与 $0.5$，困难低温端 $\beta J=0.8$ / $1.0$ 一并展示。
- 相邻档差 $\delta_D(O)=\lvert O(D_{\rm large})-O(D_{\rm small})\rvert$；同时在**丢弃权重 $w\to0$** 上做线性外推，报告外推值与外推不确定度。

**生产键维数规则**【工作规则 v1，后续研究中如有改进将修订】：$D_{\rm prod}$ 取同时满足以下条件的最小 $D$——
(i) 在最困难计算点（$h/J=3.0$，$\beta J=1.0$）上，相邻两档相对变化 $\delta_D(u)/|u|<0.3\%$ 且 $\delta_D(C)/|C|<1\%$（即项目精度目标的 1/3）；
(ii) 演化全程单步截断丢弃权重 $w<10^{-8}$；
(iii) 上述两条在 $h/J\in\{2.5,3.0,3.5\}$ 与 $\beta J\in[0.1,1.0]$ 的全部计算点抽查成立。

| 检查项 | 判据 | 结果 |
|---|---|---|
| $u$ 的 $D$ 收敛 | $\delta_D(u)/|u|<0.3\%$ | `{{AUTO:U_D_CONVERGENCE}}` |
| $C$ 的 $D$ 收敛 | $\delta_D(C)/|C|<1\%$ | `{{AUTO:C_D_CONVERGENCE}}` |
| 丢弃权重水平 | $\max w<10^{-8}$ @ $D_{\rm prod}$ | `{{AUTO:MAX_DISCARDED_WEIGHT}}` |

### 6.3 METTS 样本数收敛（主路线核心）

- 在 $\beta J=0.8$ 报告达到 $\epsilon_{\rm rel}(u)<1\%$、$\epsilon_{\rm rel}(C)<3\%$ 所需样本数：`{{AUTO:METTS_REQUIRED_SAMPLES_AT_BETA_08}}`。
- 须报告：$\sigma_{\bar O}$–$M$ 关系（验证 $1/\sqrt M$ 标度）、分箱大小敏感性、自相关时间 $\tau_{\rm int}$、链间 $\hat R$ 诊断、生产样本数 $M_{\rm prod}$ 及对应的总 SEM。

### 6.4 虚时步长 $\Delta\beta$ 收敛

序列 $\Delta\beta\in\{{{AUTO:DELTA_BETA_GRID}}\}$；以 $\Delta\beta$ 减半前后 $u$、$C$ 的相对变化拟合 $\mathcal O(\Delta\beta^n)$ 标度并确认阶数与理论一致（二阶分解累积 $n=2$）。结论：`{{AUTO:DELTA_BETA_CONVERGENCE_SUMMARY}}`

### 6.5 环境维数 $\chi_{\rm env}$ 收敛

序列 $\chi_{\rm env}\in\{{{AUTO:ENVIRONMENT_DIMENSION_GRID}}\}$；判据：$\chi_{\rm env}$ 加倍后观测量相对变化 $<0.1\%$。结论：`{{AUTO:ENVIRONMENT_CONVERGENCE_SUMMARY}}`

### 6.6 低温可达性汇总

| 横场 | $u$ 达标的最大 $\beta J$ | $C$ 达标的最大 $\beta J$ | 稳定性结论 |
|---:|---:|---:|---|
| $h/J=2.5$ | `{{AUTO:H25_U_BETA_MAX_VALID}}` | `{{AUTO:H25_C_BETA_MAX_VALID}}` | `{{AUTO:H25_STABILITY_CONCLUSION}}` |
| $h/J=3.0$ | `{{AUTO:H30_U_BETA_MAX_VALID}}` | `{{AUTO:H30_C_BETA_MAX_VALID}}` | `{{AUTO:H30_STABILITY_CONCLUSION}}` |
| $h/J=3.5$ | `{{AUTO:H35_U_BETA_MAX_VALID}}` | `{{AUTO:H35_C_BETA_MAX_VALID}}` | `{{AUTO:H35_STABILITY_CONCLUSION}}` |

临界点附近（$h/J=3.0$）详细分析：`{{AUTO:CRITICAL_FIELD_STABILITY_ANALYSIS}}`

---

## 7. 实验配置与数据管理

### 7.1 主实验矩阵

| 实验 ID | 横场 | 温度范围 | 主算法参数 | QMC 参考 |
|---|---|---|---|---|
| `{{AUTO:EXP_ID_H25}}` | $h/J=2.5$ | $\beta J\in[0.1,1.0]$ | `{{AUTO:PRIMARY_TN_PARAMETER_GRID}}` | `{{AUTO:QMC_REFERENCE_STATUS_H25}}` |
| `{{AUTO:EXP_ID_H30}}` | $h/J=3.0$ | $\beta J\in[0.1,1.0]$ | 同上（压力测试主点） | `{{AUTO:QMC_REFERENCE_STATUS_H30}}` |
| `{{AUTO:EXP_ID_H35}}` | $h/J=3.5$ | $\beta J\in[0.1,1.0]$ | 同上 | `{{AUTO:QMC_REFERENCE_STATUS_H35}}` |

### 7.2 配置文件

主配置文件：`{{AUTO:PRIMARY_CONFIG_PATH}}`；快照：`{{AUTO:CONFIG_SNAPSHOT_PATH}}`；SHA-256：`{{AUTO:CONFIG_SHA256}}`。

### 7.3 目录结构与数据格式

```text
2D_TN_Challenge/
├── data/
│   ├── raw/            # metts/ pepo/ qmc/ ed/ 原始输出（只读，不改写）
│   ├── processed/      # benchmark.csv, convergence.csv, summary.json
│   ├── logs/           # runs/, environment/
│   └── manifests/      # run_manifest.json, checksums.sha256
├── results/figures/    # 本报告全部图（§9）
├── results/tables/     # 自动生成的表格片段
└── docs/reports/       # report.template.md → report.md
```

主结果文件 `{{AUTO:BENCHMARK_DATA_PATH}}`：每行 = 一个方法 × 一个横场 × 一个温度点 × 一组算法参数。

| 字段 | 说明 | 字段 | 说明 |
|---|---|---|---|
| `run_id` | 运行唯一标识 | `specific_heat` | $C$ |
| `method` | `metts` / `pepo` / `qmc` / `ed` / `tantrg` | `susceptibility` | $\chi$（可空） |
| `field_h`, `beta`, `temperature` | $h/J$、$\beta J$、$T/J$ | `stderr_*` | 各观测量统计误差 |
| `Lx`, `Ly`, `boundary` | 晶格与边界 | `wall_time_s`, `peak_memory_mb` | 性能记录 |
| `bond_dimension`, `environment_dimension`, `delta_beta`, `sample_count`, `chain_id` | 算法参数 | `seed`, `git_commit`, `config_sha256` | 可复现性 |
| `free_energy_density` | $f$ | `status` | `success` / `failed` / `interrupted` |
| `internal_energy_density` | $u$ | | |

### 7.4 运行元数据（每次运行自动生成）

`{{AUTO:RUN_MANIFEST_PATH}}`，至少包含：`run_id`、ISO 8601 时间戳、`git_commit` / `git_branch` / `git_dirty`、`hostname`、`platform`、`python_version`、`config_path` + `config_sha256`、实际运行命令、随机种子、`wall_time_s`、`peak_memory_mb`、GPU 信息、`status`。全部输出文件登记 SHA-256 于 `data/manifests/checksums.sha256`。

---

## 8. 结果

> 本节数值与图一律由脚本从 `data/processed/` 自动生成，禁止手工誊抄。

### 8.1 自由能密度 $f(T)$

数据：`{{AUTO:FREE_ENERGY_TABLE_PATH}}`；图：`{{AUTO:FREE_ENERGY_FIGURE_PATH}}`（Fig. 1）。
解读：`{{AUTO:FREE_ENERGY_INTERPRETATION}}`

### 8.2 内能密度 $u(T)$

数据：`{{AUTO:ENERGY_TABLE_PATH}}`；图：`{{AUTO:ENERGY_FIGURE_PATH}}`（Fig. 2，METTS vs QMC）。
QMC 对照摘要：`{{AUTO:ENERGY_QMC_COMPARISON_SUMMARY}}`

### 8.3 比热 $C(T)$

数据：`{{AUTO:SPECIFIC_HEAT_TABLE_PATH}}`；图：`{{AUTO:SPECIFIC_HEAT_FIGURE_PATH}}`（Fig. 3，METTS vs QMC）。
估计方式与差分设置：`{{AUTO:SPECIFIC_HEAT_DIFFERENTIATION_SETTINGS}}`；方案 A/B 交叉验证：`{{AUTO:SPECIFIC_HEAT_CROSSCHECK}}`。
QMC 对照摘要：`{{AUTO:SPECIFIC_HEAT_QMC_COMPARISON_SUMMARY}}`

### 8.4 均匀磁化率 $\chi(T)$（加分）

状态：`{{AUTO:SUSCEPTIBILITY_STATUS}}`；摘要：`{{AUTO:SUSCEPTIBILITY_SUMMARY}}`；图：`{{AUTO:SUSCEPTIBILITY_FIGURE_PATH}}`（Fig. 12）。

### 8.5 收敛分析结果

- 样本数收敛（METTS，主路线）：`{{AUTO:METTS_CONVERGENCE_SUMMARY}}`，图 `{{AUTO:METTS_CONVERGENCE_FIGURE_PATH}}`（Fig. 7）。
- 键维数 $D$ 收敛（METTS 张量截断与 PEPO 探索路线）：`{{AUTO:D_CONVERGENCE_SUMMARY}}`，图 `{{AUTO:D_CONVERGENCE_FIGURE_PATH}}`（Fig. 6）。
- $\Delta\beta$ 收敛（Fig. 8）与 $\chi_{\rm env}$ 收敛（Fig. 9）：见 §6.4–6.5 结论。

### 8.6 QMC 精度验证

**可比性检查**（任何一项不匹配则比较无效）：

| 检查项 | 结果 |
|---|---|
| 哈密顿量 / $J=1$ / $h/J$ 一致 | `{{AUTO:VALIDATION_HAMILTONIAN_MATCH}}` |
| 晶格 $10\times10$ OBC 一致 | `{{AUTO:VALIDATION_LATTICE_MATCH}}` |
| 温度网格一致（或已注明插值方式） | `{{AUTO:VALIDATION_TEMPERATURE_GRID_MATCH}}` |
| 观测量归一化约定一致 | `{{AUTO:VALIDATION_NORMALIZATION_MATCH}}` |
| QMC 统计误差已记录且满足 §4.5 基准质量判据 | `{{AUTO:VALIDATION_QMC_ERRORS_AVAILABLE}}` |

**精度汇总**（按 §5.1 定义）：

| 横场 | 观测量 | MAE | RMSE | 最大绝对误差 | 最大相对误差 | 最大误差位置 |
|---:|---|---:|---:|---:|---:|---|
| $h/J=2.5$ | $u$ | `{{AUTO:H25_U_MAE}}` | `{{AUTO:H25_U_RMSE}}` | `{{AUTO:H25_U_MAX_ABS}}` | `{{AUTO:H25_U_MAX_REL}}` | `{{AUTO:H25_U_MAX_LOCATION}}` |
| $h/J=2.5$ | $C$ | `{{AUTO:H25_C_MAE}}` | `{{AUTO:H25_C_RMSE}}` | `{{AUTO:H25_C_MAX_ABS}}` | `{{AUTO:H25_C_MAX_REL}}` | `{{AUTO:H25_C_MAX_LOCATION}}` |
| $h/J=3.0$ | $u$ | `{{AUTO:H30_U_MAE}}` | `{{AUTO:H30_U_RMSE}}` | `{{AUTO:H30_U_MAX_ABS}}` | `{{AUTO:H30_U_MAX_REL}}` | `{{AUTO:H30_U_MAX_LOCATION}}` |
| $h/J=3.0$ | $C$ | `{{AUTO:H30_C_MAE}}` | `{{AUTO:H30_C_RMSE}}` | `{{AUTO:H30_C_MAX_ABS}}` | `{{AUTO:H30_C_MAX_REL}}` | `{{AUTO:H30_C_MAX_LOCATION}}` |
| $h/J=3.5$ | $u$ | `{{AUTO:H35_U_MAE}}` | `{{AUTO:H35_U_RMSE}}` | `{{AUTO:H35_U_MAX_ABS}}` | `{{AUTO:H35_U_MAX_REL}}` | `{{AUTO:H35_U_MAX_LOCATION}}` |
| $h/J=3.5$ | $C$ | `{{AUTO:H35_C_MAE}}` | `{{AUTO:H35_C_RMSE}}` | `{{AUTO:H35_C_MAX_ABS}}` | `{{AUTO:H35_C_MAX_REL}}` | `{{AUTO:H35_C_MAX_LOCATION}}` |

相对误差随 $\beta J$ 的分布见 Fig. 4–5；低温可达性见 §6.6 表。

### 8.7 性能：时间–内存–精度比较（含 tanTRG 对比）

精度–代价关系是本项目的核心科学问题之一：即便仅实现单一方法，也必须刻画该方法自身的"参数–精度–代价"标度；与 tanTRG / MPO-LTRG 的横向对比在此基础上进行。

**测试约定**（任何对比必须满足）：

| 项目 | 约定 |
|---|---|
| 格点 / 横场 / 温度 | $10\times10$ OBC，$h/J=3.0$，$\beta J\in[0.1,1.0]$ |
| 精度基准 | 同一套 QMC 参考数据 |
| 运行环境 | 同机、同线程数、同 BLAS 后端（§11.3） |
| 计时方式 | 热身 1 次后取 `{{AUTO:BENCHMARK_REPETITIONS}}` 次运行的墙钟时间中位数 |
| 内存测量 | 峰值 RSS（如 `/usr/bin/time -v` 或等价） |
| 公平性 | 各方法先在自身键维数上完成收敛（§6），再在"达到同等 $\epsilon_{\rm rel}$"的水平线上比较代价；**MPO 与 PEPS/PEPO 键维数数值不可直接比较** |

**性能结果**：

| 方法 | 控制参数 | $u$ MAE | $C$ MAE | 墙钟时间 | 峰值内存 | 最大稳定 $\beta J$ |
|---|---|---:|---:|---:|---:|---:|
| METTS（主路线） | `{{AUTO:PRIMARY_METHOD_PERFORMANCE_PARAMETERS}}` | `{{AUTO:PRIMARY_METHOD_U_MAE}}` | `{{AUTO:PRIMARY_METHOD_C_MAE}}` | `{{AUTO:PRIMARY_METHOD_WALL_TIME}}` | `{{AUTO:PRIMARY_METHOD_PEAK_MEMORY}}` | `{{AUTO:PRIMARY_METHOD_MAX_BETA}}` |
| PEPO（探索） | `{{AUTO:PEPO_PERFORMANCE_PARAMETERS}}` | `{{AUTO:PEPO_U_MAE}}` | `{{AUTO:PEPO_C_MAE}}` | `{{AUTO:PEPO_WALL_TIME}}` | `{{AUTO:PEPO_PEAK_MEMORY}}` | `{{AUTO:PEPO_MAX_BETA}}` |
| tanTRG / MPO-LTRG | `{{AUTO:COMPARISON_METHOD_PARAMETERS}}` | `{{AUTO:COMPARISON_METHOD_U_MAE}}` | `{{AUTO:COMPARISON_METHOD_C_MAE}}` | `{{AUTO:COMPARISON_METHOD_WALL_TIME}}` | `{{AUTO:COMPARISON_METHOD_PEAK_MEMORY}}` | `{{AUTO:COMPARISON_METHOD_MAX_BETA}}` |
| QMC（基准） | `{{AUTO:QMC_PERFORMANCE_PARAMETERS}}` | — | — | `{{AUTO:QMC_WALL_TIME}}` | `{{AUTO:QMC_PEAK_MEMORY}}` | $1.0$ |

标度分析（代价随 $D$ / $M$ 的增长幂律，精度随代价的衰减幂律）：`{{AUTO:SCALING_ANALYSIS}}`
比较结论：`{{AUTO:PERFORMANCE_COMPARISON_CONCLUSION}}`

### 8.8 有限尺寸分析（加分）

`{{AUTO:FINITE_SIZE_ANALYSIS}}`

---

## 9. 结果图列表

> 图统一存于 `results/figures/`，命名即下表文件名；每图图注须注明：参数（$h/J$, $D$, $M$, $\Delta\beta$, $\chi_{\rm env}$）、误差棒含义、数据来源文件。

| 图号 | 文件名 | 内容 | 必/选 |
|---:|---|---|---|
| Fig. 1 | `free_energy_vs_temperature.pdf` | 三个横场下 $f(T)$，TN vs QMC | 必选 |
| Fig. 2 | `internal_energy_vs_temperature.pdf` | $u(T)$，METTS vs QMC（带误差棒） | 必选 |
| Fig. 3 | `specific_heat_vs_temperature.pdf` | $C(T)$，METTS vs QMC（带误差棒） | 必选 |
| Fig. 4 | `relative_error_energy.pdf` | $\epsilon_{\rm rel}(u)$ 随 $\beta J$（半对数），三横场 | 必选 |
| Fig. 5 | `relative_error_specific_heat.pdf` | $\epsilon_{\rm rel}(C)$ 随 $\beta J$（半对数），三横场 | 必选 |
| Fig. 6 | `convergence_vs_bond_dimension.pdf` | 键维数收敛，$\beta J=0.1,0.5,0.8,1.0$ | 必选 |
| Fig. 7 | `convergence_vs_samples.pdf` | METTS $\sigma_{\bar O}$–$M$（双对数，验证 $1/\sqrt M$ 标度，附 $\hat R$） | 必选 |
| Fig. 8 | `delta_beta_convergence.pdf` | $\Delta\beta$ 收敛与 Trotter 阶数拟合 | 推荐 |
| Fig. 9 | `environment_convergence.pdf` | $\chi_{\rm env}$ 收敛 | 推荐 |
| Fig. 10 | `runtime_vs_error.pdf` | 精度–耗时权衡（METTS vs PEPO vs tanTRG） | 加分 |
| Fig. 11 | `memory_vs_parameter.pdf` | 峰值内存 vs 键维数 / 样本数 | 加分 |
| Fig. 12 | `susceptibility_vs_temperature.pdf` | $\chi(T)$，TN vs QMC | 加分 |

图目录实际路径：`{{AUTO:FIGURE_DIRECTORY}}`

---

## 10. 复现指南

### 10.1 环境安装

```bash
git clone {{AUTO:REPOSITORY_URL}} && cd 2D_TN_Challenge
git checkout {{AUTO:GIT_COMMIT_FULL}}
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip && python -m pip install -r requirements.txt
```

依赖锁定文件：`{{AUTO:DEPENDENCY_LOCK_FILE}}`；Julia 组件（ThermoTN 基线复算）：`julia --project=. -e 'using Pkg; Pkg.instantiate()'`。

### 10.2 一键测试

```bash
bash scripts/test_all.sh
```

依次执行：单元测试 → $4\times4$ ED sanity check → 小尺寸 METTS/PEPO 运行 → 小尺寸 QMC 运行 → 与回归基准比对 → 输出测试报告。预期结果：`{{AUTO:TEST_SUMMARY}}`

### 10.3 一键复现完整基准

```bash
bash scripts/reproduce_all.sh
# 等价分步：
# python scripts/run_metts.py          --config configs/benchmark_10x10.yaml   # METTS 主计算
# python scripts/run_qmc.py            --config configs/benchmark_10x10.yaml   # QMC 基准
# python scripts/process_results.py && python scripts/make_figures.py          # 处理 + 出图
```

预期总时长：`{{AUTO:EXPECTED_REPRODUCTION_RUNTIME}}`（在 §11 硬件上）；预期输出：§9 全部图、`data/processed/` 结果表、`data/manifests/` 校验和。

### 10.4 报告自动生成管线

```bash
python scripts/collect_environment.py     # 收集硬件/软件/Git 信息
python scripts/generate_report_data.py    # 汇总 {{AUTO:*}} 变量 → results/report_metadata.json
python scripts/render_report.py --template docs/reports/report.template.md \
    --metadata results/report_metadata.json --output docs/reports/report.md
python scripts/check_report.py --fail-on-unresolved-auto
```

### 10.5 VS Code Tasks

`.vscode/tasks.json` 预置任务链 `TN: 一键复现`（单元测试 → ED 检查 → TN 基准 → QMC 基准 → 处理出图 → 生成报告），按 `Ctrl+Shift+P` → `Tasks: Run Task` 调用；任务定义与 §10.2–10.4 命令保持同源，避免双份维护。

---

## 11. 硬件与软件环境记录

### 11.1 硬件

| 项目 | 内容 | 项目 | 内容 |
|---|---|---|---|
| 主机名 | `{{AUTO:HOSTNAME}}` | 系统内存 | `{{AUTO:SYSTEM_MEMORY}}` |
| 操作系统 | `{{AUTO:OPERATING_SYSTEM}}` | GPU | `{{AUTO:GPU_MODEL}}`（×`{{AUTO:GPU_COUNT}}`，显存 `{{AUTO:GPU_MEMORY}}`） |
| CPU | `{{AUTO:CPU_MODEL}}` | GPU 驱动 / CUDA | `{{AUTO:GPU_DRIVER_VERSION}}` / `{{AUTO:CUDA_VERSION}}` |
| 核心数 | 物理 `{{AUTO:CPU_PHYSICAL_CORES}}` / 逻辑 `{{AUTO:CPU_LOGICAL_CORES}}` | 存储 | `{{AUTO:STORAGE_TYPE}}`，临时数据峰值 `{{AUTO:PEAK_DISK_USAGE}}` |

### 11.2 软件

| 软件 | 版本 | 软件 | 版本 |
|---|---|---|---|
| Python / Julia | `{{AUTO:PYTHON_VERSION}}` / `{{AUTO:JULIA_VERSION}}` | 张量网络库 | `{{AUTO:TENSOR_NETWORK_LIBRARY_VERSION}}`（ITensor / TensorKit / quimb …） |
| Git | `{{AUTO:GIT_VERSION}}` | QMC 实现 | `{{AUTO:QMC_IMPLEMENTATION_VERSION}}` |
| NumPy / SciPy | `{{AUTO:NUMPY_VERSION}}` / `{{AUTO:SCIPY_VERSION}}` | BLAS/LAPACK 后端 | `{{AUTO:BLAS_BACKEND}}` |
| 数值后端 | `{{AUTO:TENSOR_LIBRARY_VERSION}}`（PyTorch / JAX / 无） | 编译器 | `{{AUTO:COMPILER_VERSION}}` |

### 11.3 并行与可重复性设置

| 设置 | 数值 |
|---|---|
| 全局随机种子 | `{{AUTO:GLOBAL_RANDOM_SEED}}` |
| `OMP_NUM_THREADS` / `MKL_NUM_THREADS` / `OPENBLAS_NUM_THREADS` | `{{AUTO:OMP_NUM_THREADS}}` / `{{AUTO:MKL_NUM_THREADS}}` / `{{AUTO:OPENBLAS_NUM_THREADS}}` |
| `CUDA_VISIBLE_DEVICES` | `{{AUTO:CUDA_VISIBLE_DEVICES}}` |
| 浮点精度 | `{{AUTO:FLOATING_POINT_PRECISION}}`（默认 float64） |

§8.7 的全部性能对比均在本节固定设置下进行。

---

## 12. 结论与最终验收

### 12.1 结论

1. 自由能密度：`{{AUTO:CONCLUSION_FREE_ENERGY}}`
2. 内能密度：`{{AUTO:CONCLUSION_ENERGY}}`
3. 比热：`{{AUTO:CONCLUSION_SPECIFIC_HEAT}}`
4. 临界区（$h/J=3.0$）表现：`{{AUTO:CONCLUSION_CRITICAL_REGION}}`
5. QMC 一致性：`{{AUTO:CONCLUSION_QMC_VALIDATION}}`
6. 收敛性：`{{AUTO:CONCLUSION_CONVERGENCE}}`
7. 最低稳定温度：`{{AUTO:CONCLUSION_LOWEST_TEMPERATURE}}`
8. 资源开销与 tanTRG 对比：`{{AUTO:CONCLUSION_PERFORMANCE}}`

最终验收结论（全部实验完成后填写）：`{{TODO:通过 / 有条件通过 / 未通过，及原因}}`

### 12.2 验收清单

**必选**

- [ ] METTS 有限温算法已实现并在 $10\times10$ OBC 上运行；PEPO 探索路线完成基本验证
- [ ] $f,u,C$ 覆盖 $\beta J\in[0.1,1.0]$，$h/J\in\{2.5,3.0,3.5\}$
- [ ] 与同尺寸 QMC 比较，$u$、$C$ 相对误差已报告（§5.1 定义）
- [ ] 最大稳定 $\beta J$ 已按 §5.3 定量定义报告
- [ ] METTS 样本数收敛分析完成（多链 + 分箱 + $\hat R$，§4.3 / §6.3）
- [ ] 键维数、$\Delta\beta$、$\chi_{\rm env}$ 收敛已检验（§6.2 / §6.4 / §6.5）
- [ ] 一键测试与一键复现命令可用且通过
- [ ] Git 提交、配置哈希、种子、软硬件环境已记录
- [ ] 无未解析 `{{AUTO:...}}` 占位符

**加分**

- [ ] $\chi(T)$ 已计算并与 QMC 比较
- [ ] tanTRG / MPO-LTRG 精度–代价对比完成（§8.7 测试约定下）
- [ ] $4\times4$ ED 校验通过
- [ ] 有限尺寸分析完成
- [ ] 数据与图的 SHA-256 校验和已生成

---

## 13. 参考文献

1. P. Czarnik *et al.*, *Variational tensor network renormalization in imaginary time: benchmark results in the Hubbard model at finite temperature*, Phys. Rev. B **94**, 235142 (2016). —— 变分 PEPO 粗粒化。
2. M. Zhang, H. Zhang, C. Wang, L. He, *Scalable tensor network algorithm for thermal quantum many-body systems in two dimensions*, Phys. Rev. B **111**, 075146 (2025). —— 矢量化 PEPS 热态随机重构。
3. S. R. White, *Minimally entangled typical quantum states at finite temperature*, Phys. Rev. Lett. **102**, 190601 (2009). —— METTS 原始文献。
4. E. M. Stoudenmire, S. R. White, *Minimally entangled typical thermal state algorithms*, New J. Phys. **12**, 055026 (2010). —— METTS 算法细节。
5. A. Wietek *et al.*, *Stripes, antiferromagnetism, and the pseudogap in the doped Hubbard model at finite temperature*, Phys. Rev. X **11**, 031007 (2021). —— 2D Hubbard 的 METTS 与 iPEPS 纯化。
6. Q. Li *et al.*, *Tangent space approach for thermal tensor network simulations of the 2D Hubbard model*, Phys. Rev. Lett. **130**, 226502 (2023). —— tanTRG 基准。
7. B.-B. Chen *et al.*, *Exponential thermal tensor network approach for quantum lattice models*, Phys. Rev. X **8**, 031082 (2018). —— XTRG。
8. ThermoTN 开源热张量网络代码，<https://github.com/ThermoTN>（`FiniteMPS.jl`、`FiniteLattices.jl` 等）。
9. H. W. J. Blöte, Y. Deng, *Cluster Monte Carlo simulation of the transverse Ising model*, Phys. Rev. E **66**, 066110 (2002). —— 二维横场 Ising 模型量子临界点 $h_c/J\approx3.044$。
10. A. W. Sandvik, J. Kurkijärvi, *Quantum Monte Carlo simulation method for spin systems*, Phys. Rev. B **43**, 5950 (1991)；B. Bauer *et al.* (ALPS collaboration), *The ALPS project release 2.0: open source software for strongly correlated systems*, J. Stat. Mech. P05001 (2011). —— SSE QMC 方法与实现。

---

## 附录 A：自动生成的运行记录

运行清单：`{{AUTO:RUN_TABLE}}`；元数据目录：`{{AUTO:RUN_MANIFEST_DIRECTORY}}`。

## 附录 B：文件校验和

`{{AUTO:FILE_CHECKSUM_TABLE}}`

## 附录 C：报告变量状态

未解析 `{{AUTO:...}}` 数量：`{{AUTO:UNRESOLVED_AUTO_VARIABLE_COUNT}}`；检查结果：`{{AUTO:REPORT_VALIDATION_RESULT}}`。

## 附录 D：缩略词表

| 缩写 | 全称 | 缩写 | 全称 |
|---|---|---|---|
| METTS | Minimally Entangled Typical Thermal States | SSE | Stochastic Series Expansion (QMC) |
| PEPO / PEPS | Projected Entangled Pair Operator / State | ED | Exact Diagonalization |
| tanTRG | Tangent-space Tensor Renormalization Group | SEM | Standard Error of the Mean |
| XTRG / LTRG | Exponential / Linearized Tensor RG | MAE / RMSE | Mean Absolute / Root-Mean-Square Error |
| MPO / MPS | Matrix Product Operator / State | OBC | Open Boundary Conditions |
| CTMRG | Corner Transfer Matrix Renormalization Group | RSS | Resident Set Size（峰值内存） |
