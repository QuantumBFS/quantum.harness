# ALF PQMC–CP 路径桥接

固定模型为 4×4 方格 PBC、半满、t=1、U=4、实二值 Hirsch spin
辅助场、Δτ=0.05、Beta=1。ALF 的右边界 `I` 是内建弱二聚化自由费米
试探态；TI 扫描的左边界 `T` 是 Ueff=4 的 Néel UHF，II 确认使用
free/free。所有轨道、site map 和 gauge 由
`assets/trials/trial_manifest.json` 唯一冻结。

执行边界：MATLAB CPMC-Lab 只运行直接 UHF-CP 能量；ALF/PQMC 保存的
6720-bit 构型只送入集群上的 oneMKL/C++ replayer。MATLAB 不承担构型重放。

权重边界也严格区分：ALF 归档权重采用其内部的 `V K` 时间片切口，
C++ 的 `D_II、D_TI` 采用与 CP 相同的 `K/2–V–K/2` 对称切口。replay
summary 同时输出 `logabs_d_alf_*` 和 `logabs_d_*`，前者只用于逐构型验证
ALF 归档，后者用于 CP 可达性、节点和后续重加权；二者之差由
`boundary_cut_log_ratio_*` 显式记录。

生产归档使用 II、TI 各 128 条独立单线程链；每链热化 2000 sweep 后，
按已测得的 239-sweep 间隔保存 8 条完整路径，因此每个 ensemble 首批
得到 1024 条路径。首批全部由集群 C++ 重放，不再固定抽取“六链各
500 条”。风险阈值只用 chain 0–63 冻结，chain 64–127 留出检验。

## 构建与测试

```bash
cd /home/minnaka/code/QuanHarness
test/pqmc_cp_bridge/scripts/test.sh
```

测试顺序为 C++/oneMKL、桥接 Python 单元测试、ALF 二值场回归、共享边界
校验和真实六链 TI 烟雾运行。

## 标定或恢复

```bash
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
/usr/bin/python3 -u \
  test/pqmc_cp_bridge/scripts/calibrate_projection.py
```

同一命令可恢复中断的批次。每批包含六条单 rank、单线程独立链；每 20 秒
报告完整 bin 数。首次批次使用 `NBin=7, NSweep=2000`，每条链首 bin
丢弃。只有总能量误差 `σ_E≤0.005` 后才判断能量是否落入
`−13.62192±0.005`。本机六链烟雾测试约 2 秒；正式首批预计为十几分钟量级，
实际耗时由运行中进度决定。可用 `Ctrl-C` 停止，完整批次会被只读复用。

## 主要输出

- `results/theta_scan.json`：逐批状态、未达精度的盲化统计和已达精度能量；
- `results/theta_scan.csv`：TI/II 已冻结点的简表；
- `results/selected_projection.json`：后续构型归档、C++ replay 和 MATLAB
  CPMC 唯一允许消费的 Θ*、Ltrot*、总场数与二进制/轨道哈希；
- `runs/alf_projection/`：可恢复的 ALF 原始链目录，不提交 Git。

若 II free/free 确认失败，状态记为 `reference_confirmation_failed`；后续
技术性 replay 可以继续，但不能把能量差归因于 CP 遍历性。

## 生产结果

128 链构型归档、2048 条 C++ 重放、最差 1% 抽样效率和详细 heat-bath
分析见 `PRODUCTION_RESULTS_CN.md`。本地 archive index 已改写为相对路径：

```text
test/pqmc_cp_bridge/archives/cluster_production_128/archive_index.json
```

重新生成抽样效率结果和图：

```bash
/usr/bin/python3 test/pqmc_cp_bridge/scripts/summarize_sampling_efficiency.py \
  --strata test/pqmc_cp_bridge/results/cluster_production_128/replay_strata.csv \
  --archive-root test/pqmc_cp_bridge/archives/cluster_production_128 \
  --output-json test/pqmc_cp_bridge/results/cluster_production_128/sampling_efficiency_summary.json \
  --output-csv test/pqmc_cp_bridge/results/cluster_production_128/worst_efficiency_1pct.csv \
  --plot-prefix test/pqmc_cp_bridge/results/cluster_production_128/sampling_efficiency_patterns
```
