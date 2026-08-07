# 低秩 Hessian 引导的中性原子量子门标定

本项目复现并扩展 Liu 等人在 ¹⁷¹Yb 中性原子平台上完成的低秩
Hessian 门标定。核心问题是：面对几十到几百维的激光脉冲、有限次
shot 和模型—装置失配，能否只沿少数高灵敏度方向完成高效闭环优化？

面向读者的主报告是 [`report.html`](report.html)。它按“问题与已有实验
答案 → 三项工作 → 共同结论与下一步”组织，不要求读者预先了解本项目
的内部图号、运行编号或文件布局。

## 项目完成的三项工作

1. **抽象 4×4 门矩阵上的有限-shot 标定。** 在 40 维控制空间中，
   Hessian 给出 15 个可辨识主方向。使用同一有限-shot、同一更新规则
   和同一隐藏装置集合，15 维搜索达到 90.625% 的目标成功率，固定查询
   上限为 66；包含额外平坦方向的 40 维模型空间为 25%，原始 40 维
   坐标为 0% observed，两者查询上限均为 166。query-only 接口也为
   Bayesian optimization 等无导数方法提供了可扩展入口。
2. **振幅鲁棒 CZ 脉冲与 Hessian 搜索方向。** 独立优化得到 400 个相位
   参数、门误差 2.23×10⁻⁹ 的等效脉冲，并恢复出十维主 Hessian 空间。
   在相同初始脉冲误差 2.40×10⁻³ 下，Hessian 坐标经 5 次一维扫描进入
   1−F≤10⁻⁵；Chebyshev 基需要 25 次，另外两个低维参数化在给定预算
   内没有达到该阈值。
3. **Cold_Atom Gate Simu_Platform 数字孪生实验。** 平台显式传播
   |0⟩、|1⟩、|r⟩、|r′⟩、erasure 和双 Rydberg 泄露扇区，并加入有限
   blockade、42 μs 寿命、AOM 响应、Doppler、位置涨落、激光能量噪声、
   线宽及频率噪声。21.7 分钟的有限-shot 闭环把观测门误差由
   0.01735±0.00058 降至最佳 0.00807±0.00040；最终精确 raw/no-loss
   fidelity 分别为 0.993586/0.997617。

这三层结果分别回答“有限-shot 查询是否节省”“正确敏感方向能否从
物理脉冲中得到”和“加入实验误差后能否继续闭环”。它们使用不同模型
和误差定义，构成逐层增加物理真实性的证据链，不合并成一个统计量。

## 从哪里开始

- [`report.html`](report.html)：完整、可离线阅读的项目报告。
- [`report.json`](report.json)：报告的结构化源文件。
- [`AI_CONTEXT.md`](AI_CONTEXT.md)：保留内部图号映射、假设、来源和
  验收边界的机器可读审计记录；不是面向外部读者的主叙事。
- [`source/`](source/)：脉冲、数字孪生和报告图表生成代码。
- [`data/`](data/)：有限-shot 记录、优化结果、Hessian 和运行清单。
- [`references/`](references/)：Liu 论文、相关工作和引用说明。

## 复现

以下命令从本目录运行；Python 3.12、CPU 即可。完整数字孪生的参考运行
耗时 21.7 分钟，其余验证通常在数分钟内完成。

```bash
python3 -m venv .venv
.venv/bin/pip install -r source/reproduce/requirements.txt
.venv/bin/pip install -e 'source/simulator[test]'

JAX_ENABLE_X64=true JAX_PLATFORM_NAME=cpu \
  .venv/bin/python -m unittest discover \
  -s source/reproduce/tests -p 'test_*.py'

.venv/bin/python -m pytest -q \
  source/simulator/tests/test_s3b_waveforms.py \
  source/simulator/tests/test_s3c_stochastic.py \
  source/simulator/tests/test_s4a_dynamic_noise.py \
  source/simulator/tests/test_s4b_psd_stark.py \
  source/simulator/tests/test_s8_yb171_profile.py

MPLCONFIGDIR=/tmp/liu-project-report-mpl \
  .venv/bin/python source/build_project_report_assets.py
python3 ../../skills/report/render_report.py .
```

重新运行完整数字孪生：

```bash
PYTHONPATH=source/simulator/src \
MPLCONFIGDIR=/tmp/liu-digital-twin-mpl \
  .venv/bin/python -u source/liu_2026_complete_digital_twin.py \
  --theory-dir data/figures3_4 \
  --paper-figure4 figures/reference/Paper_Figure_4.png \
  --output-dir data/digital_twin-rerun
```

抽象 4×4 有限-shot 基准位于仓库
`tracks/qcs/solutions/gpt-5.6/core-sim-to-real/`。从仓库根目录运行：

```bash
cd tracks/qcs/solutions/gpt-5.6
python tools/validate_team_package.py --strict-closure
python3 -m venv .venv
.venv/bin/pip install -r core-sim-to-real/requirements.txt
.venv/bin/python core-sim-to-real/code/attempt50_result_audit.py --verify-only
.venv/bin/python core-sim-to-real/run_challenge.py --mwe
```

## 证据边界

- 本项目生成的是软件黑箱与数字孪生数据，不是真实实验测量。
- 振幅鲁棒脉冲是满足论文约束的等效重新优化，不是作者未公开的相位数组。
- 实测复 AOM 传递函数、完整 MQDT pair table、原始 shots 和装置噪声谱未
  公开；报告明确标注了替代模型和由此产生的不确定性。
- 当前结果支持在完整前向模型中联合优化 400 维脉冲并重新求 Hessian；
  这是下一阶段工作，不被写成已经完成的结果。

主要来源：Genyue Liu et al., *High-fidelity neutral atom gates leveraging
low-rank Hessian optimization*, arXiv:2606.05060v1 (2026)；Evered et al.,
*High-fidelity parallel entangling gates on a neutral-atom quantum computer*,
Nature 622, 268–272 (2023)；Quantum Harness Issue #113。
