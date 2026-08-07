# Cold-Atom Gate Simulation Platform

[![CI](https://github.com/thy10817/Sim-to-real-simulation/actions/workflows/cold-atom-gate-platform-ci.yml/badge.svg)](https://github.com/thy10817/Sim-to-real-simulation/actions/workflows/cold-atom-gate-platform-ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/Code%20License-MIT-yellow.svg)](LICENSE)

面向中性原子光镊量子计算的实验数字孪生与闭环控制 benchmark 平台。
当前以 Cs-133 为主，同时提供 Rb-87 多能级与 Liu-2026 Yb-171 四能级
参考配置。物种差异只存在于数据 profile，不进入 backend 条件分支。平台
接收普通实验脉冲、外部优化波形、校准电路或闭环控制器，通过可替换的物理
后端、噪声模型、SPAM/损失模型和有限 shot 观测，模拟真实实验中控制器
能够看到的结果。

项目位于共享仓库的独立工作区：
[Cold_Atom Gate Simu_Platform](https://github.com/thy10817/Sim-to-real-simulation/tree/main/Cold_Atom%20Gate%20Simu_Platform)。
它不会改变仓库内 `core-sim-to-real/`、`robustness/` 或 `reproduce/` 的
科学假设和证据边界。

> 当前定位是“可扩展、可验证的研究平台”，不是已经校准到某一台 Cs 装置的
> 完整数字副本。当前通过 129 项物理、接口和仓库回归；真实装置的完整
> MQDT 表、横向磁场 mixing 和实测传递函数仍需冻结。

## 核心设计

平台严格隔离两个边界：

- `platform.public`：控制器可用。只能提交实验程序、消耗预算并读取有限-shot
  counts、相机信号、retention、时间戳和资源账本。
- `platform.oracle`：验证者专用。可读取精确概率或真值，用于离线验收，不能
  传给被 benchmark 的闭环控制器。

高保真 CZ、普通对称 CZ、任意单比特门或未来三比特协议都通过同一实验程序
接口进入平台；优化波形是输入，不是模拟器内部的特殊门原语。

## 已实现能力

| 层 | 当前能力 |
|---|---|
| 原子模型 | reduced `|0>,|1>,|r>`、可配置有限多能级、严格区分整数主量子数 $n$ 与 MQDT 有效主量子数 $\nu$、从量子数编译的 Cs/Rb ARC 数据、Yb/实验数据表、Evered-2023 Rb-87 八能级与 Liu-2026 Yb-171 四能级参考 profile |
| 三维物理环境 | Jones vector 到 $\sigma^\pm/\pi$、三维磁场与原子位置、pair-specific $H_\mathrm{pair}$、有效幂律和 ARC/PairInteraction/MQDT 导出表的严格插值接口 |
| 控制 | 常数/采样/解析波形，并行通道，局域/全局寻址，硬件增益、延迟、一阶带宽和组合传递图 |
| Hamiltonian | 共享 actuator 多跃迁、复数相对 Rabi、动态 Stark、静态单原子混合、对角/非对角 pair coupling |
| 噪声 | 通用单/多光子有效波矢 Doppler、热位置、Rabi/Stark/blockade 相关变化、脉冲能量、激光线宽、相位/频率 PSD/CSD、Zeeman、trap/DC Stark、衰减与退相干 |
| 时间层级 | shot 内轨迹、shot 间准静态变量、多原子共同/局域模式、iteration 漂移 |
| 观测 | fluorescence、分类、retention/loss、混淆矩阵、有限-shot 原始结果 |
| 表征 | Rabi、Ramsey、任意 SU(2)、conditional Ramsey、Bell parity、SSB 和 CZ 相关估计 |
| 闭环 | ask/tell 控制协议、参数规范化、有限预算、不可回滚 token、进程隔离和 block-aware 统计 |
| 波形基线 | Jandura–Pupillo 开源 CZ 回放、Fromonteil amplitude-robust Protocol I/II、SciPy ensemble objective |

完整边界和局限见[研究总览](RESEARCH_OVERVIEW.md)。

## 快速开始

```powershell
git clone https://github.com/thy10817/Sim-to-real-simulation.git
Set-Location "Sim-to-real-simulation\Cold_Atom Gate Simu_Platform"
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -e ".[test]"
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider
```

Linux/macOS 将最后两条命令中的 `.\.venv\Scripts\python` 换成
`.venv/bin/python`。

最小单原子 π 脉冲：

```python
import math

from cs_tweezer_sim import create_reduced_platform
from cs_tweezer_sim.profiles import reduced_validation_profile
from cs_tweezer_sim.programs import rotation_program

omega = 2.0 * math.pi  # rad/us
profile = reduced_validation_profile(n_atoms=1, blockade_rad_per_us=0.0)
platform = create_reduced_platform(profile, seed=7)
program = rotation_program(
    n_atoms=1,
    atom=0,
    angle_rad=math.pi,
    phase_rad=0.0,
    rabi_rad_per_us=omega,
    initial_bitstring="0",
)
result = platform.public.execute(program, shots=128)
print(result.counts)
```

完整实验决定量见[门实验参数规范](docs/GATE_EXPERIMENT_PARAMETER_SCHEMA_ZH.md)。
更多入口见[接口功能总览](docs/API_REFERENCE.md)及自动生成的
[完整公开 API 清单](docs/_generated/PUBLIC_API.md)。

## 工作区结构

```text
Cold_Atom Gate Simu_Platform/
├── src/
│   ├── cs_tweezer_sim/          # 通用模拟平台
│   └── cs_tweezer_pulse_design/ # 可选的鲁棒波形设计工具
├── tests/                       # 物理机制、接口和回归测试
├── scripts/                     # 冻结验收、数据导出和文档工具
├── data/                        # 小型可复现输入、来源和哈希
├── results/                     # 保留的不可变机器结果，包括失败验收
├── docs/                        # API、架构、计划、报告和文献笔记
├── references/local/            # 本机论文与截图，不进入 Git
├── RESEARCH_OVERVIEW.md         # 整个研究问题的唯一总入口
└── pyproject.toml               # 安装、依赖和测试配置
```

## 开发与验收

```powershell
.\.venv\Scripts\python -m pip install -e ".[test]"
.\.venv\Scripts\python scripts\generate_api_reference.py --check
.\.venv\Scripts\python scripts\check_repository_hygiene.py
.\.venv\Scripts\python -m pytest tests -q -p no:cacheprovider
.\.venv\Scripts\python -m pip wheel . --no-deps -w dist
```

各阶段 `run_*_acceptance.py` 会生成或验证不可变结果。历史失败运行不会被删除
或改写；详情见[研究文档导航](docs/README.md)和
[结果目录说明](results/README.md)。

## 数据与许可证

- 本项目原创代码采用 [MIT License](LICENSE)。
- 上游波形、原子数据、论文和第三方软件保留各自许可，见
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
- 论文 PDF、页面截图及需再次确认再分发权利的 NIST 排版 PDF 不进入公共
  Git 历史。来源、版本和 SHA-256 保留在仓库中，可用
  `python scripts/fetch_atomic_references.py` 下载并核验到本机。

参与开发前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)；科研结论与当前
证据强度以 [RESEARCH_OVERVIEW.md](RESEARCH_OVERVIEW.md) 为准。
