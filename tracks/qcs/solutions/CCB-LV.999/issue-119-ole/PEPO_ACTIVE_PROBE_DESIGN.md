# 49×1296 Heisenberg-PEPO active feasibility probe 设计

日期：2026-07-30

对应任务：Quantum Harness issue #119，OLE active candidate

状态：设计已批准；等待书面设计复核后进入实施计划

## 1. 目的与边界

本 probe 回答一个有限问题：

> 已在 49×648 baseline 上验证的 Heisenberg-picture PEPO 实现，能否在相同
> 49-site heavy-hex 图的 49×1296 active 电路上完成
> `Dop={384,512},χenv=64,δ=0.15` 两个确定性计算？

本 probe 只评估：

- active 输入能否被严格解析和独立小系统 oracle 验证；
- 两个目标 cell 能否在普通 CPU `batch` 节点内完成；
- wall time、peak RSS、causal-gate 数、最终 support 和实际最大虚拟键；
- `F(512,64)−F(384,64)` 的有限 `Dop` diagnostic drift。

本 probe 不评估：

- `χenv` 收敛；
- `δ=0` rescaling；
- 受控的 `Dop→∞` 外推；
- 与 BP-TN 或量子硬件的正式 agreement；
- 原计划 G6 的 production benchmark。

它不绕过 BP-TN G5 gate。BP-TN G5 未通过时，PEPO active probe 即使成功也只
能标记为 feasibility evidence。

## 2. 固定物理问题

| 项目 | 固定值 |
| --- | --- |
| interaction graph | 49-site open heavy-hex graph |
| circuit | `L=6`，145 barriers，1,296 CZ gates |
| observable | `O=Z52 Z59 Z72` |
| perturbation | `b=0.25`，`δ=0.15`，24 个 `Rz(0.3)` gates |
| target | `F=2⁻⁴⁹ Tr[O C† O C]` |
| picture | Heisenberg picture，反向演化 `C†OC` |
| dtype | complex128 |
| `Dop` | 384、512 |
| `χenv` | 64 |
| evolution cutoff | `10⁻¹²` |
| contraction cutoff | `10⁻¹²` |

`Dop` 限制 Heisenberg 算符 PEPO 演化中的虚拟键；`χenv` 限制最终闭合二维
张量网络压缩收缩的中间键。两者控制不同误差，不能合并成一个 bond dimension。

## 3. 输入选择

### 3.1 计算输入

active PEPO 使用 issue #11 attachment 的 OpenQASM2 文件：

```text
URL:
https://github.com/user-attachments/files/23483343/49Q_OLE_circuit_L_6_b_0.25_delta0.15.txt

SHA-256:
d237a273c7cc233e9d64039ad06613af17eb472b19bda12f4ce458b9c4541645

bytes:
297926
```

选择它而不直接扩展 OpenQASM3 parser 的原因：

- 现有 PEPO parser 已严格支持该 QASM2 gate subset；
- 输入审计已证明 attachment 与 tracker 当前 OpenQASM3 文件的规范化 TNQS
  gate list 完全一致；
- 计算仍同时记录当前 OpenQASM3 文件的 SHA-256
  `3748e2c026c118f9d6c7499093ea43e41a45251b6bf8d3adb6fb056f718f6cc0`
  和 canonical-equivalence 证据；
- 本 probe 不引入与数值问题无关的 QASM3 parser 扩展。

任何 hash、字节数、活动 qubit 数、layer 数、CZ 数、perturbation 数或 observable
映射变化都会在开始 PEPO 演化前停止。

### 3.2 不采用的输入路线

- 不从问题文字手工重建门序；
- 不把当前 OpenQASM3 文件临时转写后当作无 provenance 的输入；
- 不由 Julia runner 导出一个未审计的新 gate manifest；
- 不把 baseline L=3 oracle certificate 直接当作 active L=6 certificate。

## 4. Runner 设计

### 4.1 电路注册表

在 PEPO runner 中增加显式 circuit profile：

```text
baseline:
  L=3 QASM2 path/hash/bytes
  baseline oracle default

active:
  L=6 QASM2 path/hash/bytes
  active oracle default
```

命令行增加：

```text
--circuit baseline|active
```

默认值保持 `baseline`，避免改变已有命令的含义。confirmation token、protocol
document、provenance document 和 manifest 必须包含 circuit profile、QASM hash、
bytes、layers、CZ count 和 observable。

### 4.2 Array contract

`run_pepo_array_cell.py` 从 run spec 的 shared settings 读取 `circuit=active`，
并显式传给 direct runner。cell manifest 必须回显：

- `params`: `dop`、`chi_env`；
- `settings`: circuit、δ、observable、两个 cutoff；
- `provenance`: QASM2/QASM3 hashes、canonical equality、quimb commit、
  numerical-core digest；
- `result`: real/imaginary value、wall time、peak RSS；
- `diagnostics`: causal gates、support size、max realized bond、retained-tail ratio。

run id 固定为：

```text
issue119-pepo-active-probe-dop384-512
```

## 5. Active-specific small oracle

提交完整 49-site cell 前，必须生成新的 active certificate：

```text
results/issue119-pepo-active-small-oracle/manifest.json
```

oracle 仍使用可精确求解的七 site connected crop 和局域 Pauli observable，
但从 active L=6 QASM2 输入裁剪。对 `δ=0` 和 `δ=0.15` 分别比较：

- independent dense matrix evolution；
- untruncated PEPO evolution and exact contraction。

通过条件：

```text
max absolute error ≤ 1×10⁻¹⁰
imaginary residual ≤ 1×10⁻¹⁰
```

certificate 绑定：

- active QASM2 SHA-256；
- quimb pinned commit；
- numerical-core source digest；
- crop sites、interaction edges、observable、δ modes；
- dense 与 PEPO 的两个结果。

任何 runner 或 numerical-core 修改都会使旧 certificate 失效，完整 cell 必须在
开始计算前重新校验证书。

## 6. 参数扫描与集群设计

### 6.1 Run spec

二维参数只包含两个 cells：

```text
Dop = 384, 512
χenv = 64
δ = 0.15  [shared setting]
```

使用 `scripts/parameter_scan.py plan` 生成 run spec，不手写 cell 枚举。

### 6.2 Slurm

| 项目 | 值 |
| --- | --- |
| cluster | `zyli@172.16.42.215` |
| partition | CPU `batch` |
| cells | 2 |
| CPUs/cell | 128 |
| memory/cell | 192 GiB |
| wall cap/cell | 8 h |
| GPU / bigmem / SCNet | 不使用 |

两个 128-CPU cells 不能共占同一 192-core node；由 Slurm 分配两个普通 CPU
nodes 或分批运行。baseline 实测锚点：

| baseline cell | wall | peak RSS |
| --- | ---: | ---: |
| `Dop=384,χenv=64` | 38.59 min | 21.51 GiB |
| `Dop=512,χenv=64` | 29.26 min | 43.41 GiB |

active 电路的门数约为 baseline 的两倍，并可能产生更长的 saturated-bond
阶段。probe 预计每 cell 约 1.5–4 h；8 h cap 用于容纳未建模的 operator-
entanglement 增长。预计 RSS 仍主要由 `Dop` 和固定 49-site 拓扑控制，
192 GiB/cell 提供超过 baseline 实测的 4× 余量。

提交前依次执行：

1. cluster precheck；
2. `batch` queue probe；
3. scoped rsync，仅同步 active QASM2、已批准的 PEPO 修改、run spec 和
   active oracle；
4. runner inspect-only；
5. exact Slurm `--test-only`；
6. 用户确认后真实提交。

## 7. 成功、失败与停止条件

### 7.1 Probe success

只有两个 cells 同时满足以下条件才称为“active PEPO 可计算”：

- active small oracle 通过；
- manifest `status=success`；
- `F` 的实部有限且位于 `[-1−10⁻⁸,1+10⁻⁸]`；
- `|Im F|≤10⁻⁸`；
- causal support 最终覆盖 49 sites；
- max realized bond 达到请求的 `Dop`；
- wall time≤8 h；
- peak RSS≤192 GiB；
- 无 OOM、timeout 或未捕获异常。

### 7.2 Scientific classification

probe 完成后报告：

```text
ΔDop(active) = |F(512,64) − F(384,64)|
```

但不为它预设“收敛通过”阈值。两个 `Dop` 点和单一 `χenv` 只能判断 drift
规模，不能证明双参数内部收敛。结果分类固定为：

```text
feasibility success + numerical diagnostic
```

而不是：

```text
G6 benchmark complete
```

### 7.3 Failure handling

- oracle 失败：不提交完整 cells，修复输入/实现；
- 某 cell 启动失败：提取 manifest/log，确认后只重跑该 cell；
- OOM/timeout：不自动放大资源，先报告实测进度和 cost model；
- D=384 成功而 D=512 失败：保留 384 diagnostic，不把它升级为 G6 result；
- 两点均成功：生成资源表和 `Dop` drift，是否扩展 `χenv` 或 δ=0 另行确认。

## 8. 测试与交付

实施阶段必须新增或更新：

- QASM2 active hash/bytes/protocol tests；
- `--circuit` CLI/default compatibility tests；
- active oracle stale-certificate tests；
- array settings/provenance echo tests；
- inspect-only side-effect test；
- two-cell run-spec validation；
- local PEPO test suite；
- cluster startup protocol check。

交付物：

- active QASM2 input及 manifest；
- active-specific oracle manifest/report；
- two-cell run spec；
- 每 cell manifest；
- `parameter-scan.csv`；
- active feasibility report；
- `Dop=384/512` comparison plot；
- 对“可计算”与“已收敛”的明确区分。

