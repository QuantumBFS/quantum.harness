# 两周期电荷响应与延迟比较报告

## 1. 目的与范围

本次计算不是复现 arXiv:2308.03756 的完整自旋-电荷关联分析，而是针对 Fig. 5c 所展示的电荷输运现象，直接检验以下问题：当不同闭合泵浦环路在每个周期内只穿过一次 nominal gapless segment 时，电荷响应延迟是否对环路形态、起始点、旋转方向和时间参数化保持为约四分之一周期。

所有曲线均使用

```text
L = 8, t = 1, U = 7.25, T = 50,
2 continuous cycles, 500 midpoint-Magnus steps per cycle.
```

第二周期连续承接第一周期末态，中间没有重置为基态。图中使用

\[
Q_{\rm oriented}(t)=\mathrm{direction}\times Q(t),
\]

因此理想的正、反向泵浦都显示为正的定向电荷，便于直接比较曲线形状。`direction=+1` 表示 \(\phi\) 增大、逆时针（CCW）；`direction=-1` 表示 \(\phi\) 减小、顺时针（CW）。

## 2. 环路与 gapless segment

三条环路均为

\[
\delta(\phi)=\delta_0\cos\phi,\qquad
\Delta(\phi)=\Delta_{\rm center}+\Delta_0\sin\phi.
\]

工作判据采用 nominal segment

\[
\delta=0,\qquad |\Delta|<U/2=3.625.
\]

有限 \(t\) 下真实临界线端点不严格等于 \(U/2\)，因此该线段只用于统一筛选和标记。三个内侧交点和外侧交点均离端点足够远，不影响“每周期只穿过一次线段”的分类。

| 图例颜色 | 环路 | \(\delta_0\) | \(\Delta_0\) | \(\Delta_{\rm center}\) | 在线段内的交点 | 在线段外的另一个 \(\delta=0\) 交点 |
|---|---|---:|---:|---:|---:|---:|
| 蓝 | wide shifted | 1.20 | 3.00 | 1.50 | \((0,-1.50)\) | \((0,4.50)\) |
| 橙 | reference | 0.90 | 3.00 | 2.85 | \((0,-0.15)\) | \((0,5.85)\) |
| 绿 | compact | 0.55 | 2.00 | 2.40 | \((0,0.40)\) | \((0,4.40)\) |

参数空间图中的箭头表示 CCW（`direction=+1`）；CW 沿相反方向运行。

## 3. 主图读法

主图 `two_cycle_charge_response.png` 的列和标记含义如下：

- 左列：CW，`direction=-1`，\(\phi\) 随时间减小。
- 右列：CCW，`direction=+1`，\(\phi\) 随时间增大。
- 同色 `X`：该曲线到达 nominal gapless segment 的时刻；每条曲线在两个周期内各有两个 `X`。
- 同色三角：第一周期中自动检测到的明显电荷响应 onset。
- 同色点线：gapless crossing 的时间位置。
- 同色虚线：第一周期 response onset 的时间位置。
- 黑色虚线 \(t/T=1\)：第一、第二周期的分界。

响应 onset 由边界电流 \(|J(t)|=|dQ/dt|\) 提取：先用宽度 \(0.02T\) 的窗口平滑，再从 crossing 到下一次 crossing 的区间内，寻找首次持续至少 \(0.01T\)、超过该区间峰值 20% 的时刻。延迟误差带使用 10%、20%、30% 三个阈值。

## 4. 第一行：改变环路形态

第一行固定 \(\phi_0=0\)、uniform \(\phi\) clock，只改变环路几何。legend 中依次写明方向和 \((\delta_0,\Delta_0,\Delta_{\rm center})\)。

| 曲线 | 方向 | crossing \(t/T\) | onset 延迟 \(\tau/T\) | 第一周期定向电荷 | 第二周期定向电荷 |
|---|---|---:|---:|---:|---:|
| 蓝 wide shifted | CW | 0.25 | 0.001 | 0.202 | 0.823 |
| 蓝 wide shifted | CCW | 0.75 | 0.001 | 1.018 | 0.350 |
| 橙 reference | CW | 0.25 | 0.111 | 0.281 | 0.224 |
| 橙 reference | CCW | 0.75 | 0.353 | 1.013 | 0.287 |
| 绿 compact | CW | 0.25 | 0.285 | 0.735 | 0.343 |
| 绿 compact | CCW | 0.75 | 0.307 | 1.043 | 0.680 |

compact 的两个方向分别得到 \(0.285T\) 和 \(0.307T\)，最接近论文中的四分之一周期现象；wide shifted 则在 crossing 后几乎立即出现显著电流。因此 \(T/4\) 对环路形态并不普适。

## 5. 第二行：改变起始点

第二行固定 reference 环路和 uniform clock，只改变初态对应的 \(\phi_0\)。legend 同时给出起始点的 \((\delta,\Delta)\) 坐标。

| 颜色 | \(\phi_0\) | 起点 \((\delta,\Delta)\) | CW \(\tau/T\) | CCW \(\tau/T\) | CW 两周期电荷 | CCW 两周期电荷 |
|---|---:|---:|---:|---:|---:|---:|
| 蓝 | 0 | \((0.900,2.850)\) | 0.111 | 0.353 | 0.281, 0.224 | 1.013, 0.287 |
| 橙 | \(1/8\) cycle | \((0.636,4.971)\) | 0.108 | 0.410 | 0.305, 0.246 | 0.985, 0.280 |
| 绿 | \(1/2\) cycle | \((-0.900,2.850)\) | 0.119 | 0.353 | 0.933, 0.298 | 0.327, 0.186 |
| 品红 | \(5/8\) cycle | \((-0.636,0.729)\) | 0.108 | 0.410 | 1.003, 0.330 | 0.275, 0.161 |

相对于 crossing 测量后，CW 延迟集中在 \(0.108T\)–\(0.119T\)，CCW 延迟为 \(0.353T\)–\(0.410T\)。这说明起始点对延迟的影响小于方向和路径形态，但并非严格不变量；更明显的起始点依赖出现在每周期累计电荷中。

## 6. 第三行：改变沿路时间参数化

第三行固定 reference 环路和 \(\phi_0=0\)，只改变沿同一几何环路运动的时钟：

- 蓝 uniform：\(\phi=\phi_0+\mathrm{direction}\,2\pi t/T\)。
- 橙 arclength：在 \((\delta,\Delta)\) 平面中保持近似恒定弧长速度。
- 绿 modulated：令 \(s=t/T\)，使用
  \[
  p(s)=s-\frac{0.5}{2\pi}\sin(2\pi s),
  \]
  因而 \(dp/ds=1-0.5\cos(2\pi s)\in[0.5,1.5]\)，始终缓慢、单调且不反向。

| 曲线 | CW \(\tau/T\) | CCW \(\tau/T\) | CW 两周期电荷 | CCW 两周期电荷 |
|---|---:|---:|---:|---:|
| 蓝 uniform | 0.111 | 0.353 | 0.281, 0.224 | 1.013, 0.287 |
| 橙 arclength | 0.121 | 0.293 | 0.029, 0.049 | 1.011, -0.042 |
| 绿 modulated | 0.087 | 0.469 | 0.149, 0.004 | 1.012, 0.173 |

即使几何环路完全相同、运动始终缓慢，按实验时间定义的延迟仍会随时钟改变。CCW 的范围达到 \(0.293T\)–\(0.469T\)，所以四分之一周期不可能是时间重参数化不变量。

## 7. 数值检查与结论

- 16 条主轨迹的最大范数漂移为 \(1.13\times10^{-13}\)。
- reference、CCW、uniform 轨迹从每周期 500 步加密到 1000 步后，延迟由 \(0.3530T\) 变为 \(0.3525T\)。
- 同一加密检查中，第一周期电荷由 1.0128 变为 1.0019；延迟结论对时间步已经稳定。
- 完整回归测试为 65 passed。

最终结论是：扫描中确实存在接近 \(T/4\) 的电荷响应延迟，但它只出现在部分环路构型中。它不是路径、方向或时间参数化不变量；对起始点相对较不敏感，但也不是严格不变量。第二周期与第一周期显著不同，说明穿过小能隙/无隙区域后产生的激发和历史依赖是 Fig. 5c 类长时间响应的重要组成部分。

## 8. 文件

- `figures/two_cycle_charge_response.png`：六面板主图，逐条显示方向、构型、crossing 和 onset。
- `figures/compared_parameter_loops.png`：三条环路、方向及 nominal gapless segment。
- `figures/response_delay_comparison.png`：所有轨迹的延迟及阈值误差带。
- `response_delay_summary.csv`：16 条曲线的完整数值。
- `traces/*.npz`：逐时间点的 \(Q(t)\)、电流、相位、crossing 和 onset。

生成命令：

```bash
/tmp/challenge36-quspin-venv/bin/python scripts/analyze_response_delay.py \
  --output results/response_delay --period 50 --steps-per-cycle 500
```
