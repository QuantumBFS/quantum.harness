# Liu-2026 Figure 4 实验数字孪生

状态：成功；本地总运行时间 1301.7 s（21.7 min），低于 55 min 硬限制。

数据类别：**Cold_Atom Gate Simu_Platform 生成的有限-shot 数字孪生结果**。
它不是实验测量；本提交包统一称其为“平台数字孪生数据”。

## 主要结果

| 指标 | 数值 |
|---|---:|
| 有限-shot 闭环初始 CZ error | 0.01735 ± 0.00058 |
| 第 9 个方向后的最佳观测 error | 0.00807 ± 0.00040 |
| 完成 10 个方向后的观测 error | 0.00851 ± 0.00041 |
| exact open-system final raw fidelity | 0.9935862 |
| exact open-system final no-loss fidelity | 0.9976167 |
| 1 kHz combined-noise raw fidelity（16 contexts） | 约 0.99225 |
| 1 kHz combined-noise no-loss fidelity（16 contexts） | 约 0.99628 |

第 9 与第 10 个检查点的 exact open-system fidelity 在 10⁻¹⁵ 内相同；末步
观测回升来自有限-shot 波动，而不是门动力学真实退化。

## 模型

- 5 个相互独立的 ¹⁷¹Yb dimers；每个 dimer 传播一个双原子模型。
- 每原子显式态：`0, 1, r, r_prime, erasure`。
- 302 nm 同一复光场驱动 `1↔r` 与 `0↔r_prime`。
- Ω₀/(2π)=6.0 MHz，Rydberg splitting 16.1 MHz，门时长 0.55 μs。
- pair sectors 包含 `rr`、`rr_prime/r_prime_r`、`r_prime_r_prime`。
- 42 μs Rydberg lifetime；90% effective decay 进入 erasure。
- 加入 2.7 μK Doppler、热位置/R⁻⁶ interaction、pulse-energy noise、
  Lorentzian linewidth、准静态频偏和 OU 频率噪声。

在线控制器只读取有限-shot fidelity estimate。exact channel、状态、隐藏噪声、
梯度和 Hessian 只写入离线 validator 区域。

## 物理发现

平台预测的单项 raw error 增量为：

- Doppler：1.06×10⁻³；
- 1 kHz linewidth + phase/frequency noise：4.81×10⁻⁴；
- thermal position / varying blockade：2.07×10⁻⁴；
- laser amplitude：6.29×10⁻⁵；
- exact lifetime/erasure 增量：4.40×10⁻³。

这些不是论文误差柱的转录。Doppler 和 phase-noise 均高于论文值，说明当前
等价重优化波形、有效 pair model 和产品级噪声先验比 Liu 装置更敏感。

线宽扫描给出的 total raw error：

- 0.1 kHz：7.44×10⁻³；
- 1 kHz：8.47×10⁻³；
- 10 kHz：1.18×10⁻²；
- 300 kHz：1.37×10⁻¹。

因此，频率转换激光的产品目录线宽不能直接当成锁定后装置线宽；若有效
302 nm linewidth 到达数百 kHz，该门会明显失去高保真区。

## 关键边界

1. Figure 4a 的一阶 AOM fit 到达 20 MHz 搜索上界，raster MSE=0.0873。
   这表明 gain + one-pole low-pass 不足以完整描述论文的幅相失真；真实装置
   仍需要测得的复传递函数、ringing/chirp 或 IQ cross-coupling。
2. B₀ 是按论文 finite-blockade 单项误差标定的 effective R⁻⁶ 模型，不是
   Liu 的 MQDT pair table。
3. 作者未公开 AR waveform 数组；这里使用约束相同的等价重优化波形。
4. 在线查询用 4 个固定隐藏环境，最终消融用 16 个环境。1 kHz 两个独立
   16-context 集合相差约 7×10⁻⁴，说明 stochastic mean 尚有有限样本不确定度。
5. 有限 shots 在环境平均后批量抽样，没有逐 shot 重传播；这是满足一小时
   预算的明确近似。

## 文件

- `figs/digital_twin_summary.png`：波形、闭环、误差消融和线宽扫描。
- `data/result.json`：完整机器结果及 validator-only 指标。
- `data/closed_loop_scans.csv`：50 个有限-shot 查询。
- `data/closed_loop_trajectory.csv`：逐 Hessian 方向轨迹。
- `data/error_budget.csv`：平台噪声消融。
- `data/linewidth_sweep.csv`：0.1–300 kHz 线宽扫描。
- `data/waveforms.npz`：ideal/before/after/command 复波形。
- `data/mwe_timing.json`：三点 MWE 计时证据。

## 重跑

```bash
PYTHONPATH="Sim-to-real-simulation/Cold_Atom Gate Simu_Platform/src" \
MPLCONFIGDIR=/tmp/liu-digital-twin-mpl \
Sim-to-real-reproduction-run/.venv/bin/python -u \
tracks/qcs/solutions/liu_2026_complete_digital_twin.py \
  --theory-dir tracks/qcs/results/20260730-153032-liu-fig1-4-local-delivery/fig234-theory \
  --paper-figure4 tracks/qcs/results/20260730-153032-liu-fig1-4-local-delivery/fig234-theory/paper_figure4.png \
  --output-dir tracks/qcs/results/20260730-175720-liu-digital-twin
```
