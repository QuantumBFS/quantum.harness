# MATLAB CPMC 直接 UHF-CP 基准实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **2026-07-30 范围修正：** MATLAB CPMC-Lab 只运行直接
> UHF-constrained CP 并给出独立能量基准，不接收或重放 ALF/PQMC
> 构型。所有已保存 PQMC 构型的完整路径重放、逐步 proposal、节点和 prefix
> 诊断均由 oneMKL/C++ 程序在集群执行。下文旧的 `fixed_horizon`、
> MATLAB 路径/谱系归因任务不再属于当前执行计划；保留文字仅作历史设计记录。

**Goal:** 用共享 free 初态 `I` 和 UHF guide/constraint `T` 运行官方
CPMC-Lab 的 production CP，得到直接 UHF-CP 能量及误差棒；与 C++ 集群重放
产生的路径诊断只在最终分析层比较，不混用执行流程。

**Architecture:** MATLAB 只消费 `I/T` 轨道和直接 CP 参数，输出独立
`.mat` 与汇总 JSON。ALF 构型档案只进入集群 C++ replayer。

**Tech Stack:** MATLAB、官方 CPMC-Lab 2.0、Python 3、MATLAB v7 `.mat`、
`unittest`。

## Global Constraints

- 模型固定为 4×4 square、PBC×PBC、t=1、U=4、N↑=N↓=8、Δτ=0.05、real binary spin HS。
- 强制读取第二阶段四个入口：
  `selected_projection.json`、`trial_manifest.json`、`field_order.json`、
  `strata_contract.json`。
- `Phi_init=I`；`Phi_trial=T`；mixed-estimator bra 与 constraint bra 都是 T。
- fixed-horizon 每个独立粒子系统都从 I、`O=O0`、`w=1` 重启并恰好传播 Ltrot* 层。
- production 只在 run 开始从 I 初始化，平衡至少 Ltrot* 层后开放式继续。
- production rolling window 不得冒充 fixed-I path。
- primary PC-fragility strata 固定对应 `Nw=1000,itv_pc=5`；同一组
  reference-free interval growth 基准和阈值必须同时用于 ALF TI 路径与
  MATLAB fixed-horizon terminal paths，不能各自按本数据重定标。
- 直接 CP 能量只取 MATLAB CPMC-Lab，不使用 C++ population simulation。
- production 算法的 proposal、constraint、QR、combing 和 mixed energy 公式不改变；诊断不得消耗额外 RNG。
- walkers 和同一 population 中的 lineage 不是独立统计样本；误差单位是独立 MATLAB run/particle system。
- CPMC-Lab 官方源码和 tarball 不提交；只提交 patch、hash 和本项目自有 wrapper。
- CP 能量是非变分的；低于精确值不自动表示更准确。
- `max_theta_fallback` 时执行全部技术流程，但最终结论只限 Θ=20、Ltrot=820、Δτ=0.05。

---

## 文件结构与责任

```text
test/pqmc_cp_bridge/
├── matlab/
│   ├── apply_cpmc_patch.sh
│   ├── read_orbitals.m
│   ├── validate_bridge_opts.m
│   ├── run_cpmc_bridge.m
│   └── run_cpmc_smoke.m
├── patches/
│   └── cpmc-lab-mixed-diagnostics.patch
├── scripts/
│   ├── cpmc_config.py
│   ├── run_fixed_horizon_grid.py
│   ├── run_production_cp.py
│   ├── run_proposal_check.py
│   ├── parse_cpmc_results.py
│   ├── pc_fragility.py
│   ├── energy_decomposition.py
│   ├── cross_reweight.py
│   └── make_final_report.py
├── tests/
│   ├── test_cpmc_config.py
│   ├── test_cpmc_patch.py
│   ├── test_cpmc_results.py
│   ├── test_pc_fragility.py
│   └── test_energy_decomposition.py
├── runs/matlab_cp/
│   ├── package/
│   ├── smoke/
│   ├── fixed_horizon/
│   ├── proposal_only/
│   └── production/
└── results/
    ├── cpmc_run_index.json
    ├── fixed_horizon_summary.csv
    ├── production_summary.csv
    ├── genealogy_summary.csv
    ├── energy_decomposition.json
    ├── causal_scan.json
    ├── final_report.md
    └── final_figure.png
```

---

### Task 1：冻结 CPMC 参数、site permutation 和运行状态机

**Files:**

- Create: `test/pqmc_cp_bridge/scripts/cpmc_config.py`
- Create: `test/pqmc_cp_bridge/tests/test_cpmc_config.py`
- Create: `test/pqmc_cp_bridge/contracts/cpmc_run_contract.json`

**Interfaces:**

```python
@dataclass(frozen=True)
class CpmcContract:
    lx: int
    ly: int
    n_up: int
    n_down: int
    dt: float
    ltrot: int
    nfield: int
    stabilize_every: int
    energy_every: int
    primary_pc_every: int

def load_cpmc_contract(root: Path) -> CpmcContract
def production_parameters(contract, nwalkers: int) -> dict
def fixed_horizon_parameters(contract, nwalkers: int,
                             pc_every: int, seed: int) -> dict
```

**Frozen starting grid**

```text
stabilize_every = 5
energy_every = 5
primary_pc_every = 5
production Nw = 1000
production N_blksteps = 20
production N_eqblk = ceil(Ltrot*/20)
production initial N_blk = 50
fixed-horizon Nw grid = 100, 500, 1000
fixed-horizon PC grid at Nw=1000 = 5, 20, 40
independent fixed systems per wave = 20
```

若 Nw=500 与 1000 的 production 能量差超过 combined 2σ，追加 Nw=2000；
否则不运行 2000。每个需要比较的 production 点先把独立-run 误差控制到
`≤0.005`。

- [ ] **Step 1：写 contract 失败测试**

拒绝：

- Ltrot/nfield 与 selected projection 不符；
- CPMC site map 不是 `r=y*Lx+x` 的显式 permutation；
- trial hash 或 strata hash 不符；
- fixed-horizon steps 不是恰好 Ltrot；
- production equilibration steps 小于 Ltrot；
- PC/stabilize/measure interval 非正。

- [ ] **Step 2：写 grid 测试**

检查 Θ*=10 和 Θ*=20 时：

```text
fixed steps = 420 或 820
production N_eqblk = 21 或 41
production equilibration steps = 420 或 820
```

- [ ] **Step 3：实现并写 JSON**

`cpmc_run_contract.json` 保存输入四个 contract 的 SHA-256 和
`strict_ground_state_claim_allowed`。

- [ ] **Step 4：运行并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_cpmc_config.py
```

Expected: PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/cpmc_config.py \
  test/pqmc_cp_bridge/tests/test_cpmc_config.py \
  test/pqmc_cp_bridge/contracts/cpmc_run_contract.json
git commit -m "test: define mixed-boundary CPMC run contract"
```

---

### Task 2：建立官方 package copy + patch 的可复现机制

**Files:**

- Create: `test/pqmc_cp_bridge/matlab/apply_cpmc_patch.sh`
- Create: `test/pqmc_cp_bridge/patches/cpmc-lab-mixed-diagnostics.patch`
- Create: `test/pqmc_cp_bridge/tests/test_cpmc_patch.py`

**Interfaces:**

```text
apply_cpmc_patch.sh
  --source .external/cpmc-lab/CPMC_Lab_20160129
  --destination test/pqmc_cp_bridge/runs/matlab_cp/package
```

- [ ] **Step 1：写失败的 provenance test**

验证：

- 官方 package root 由 `find ... -name CPMC_Lab.m` 定位；
- source tree SHA-256 manifest 与已记录值一致；
- destination 不存在时复制，存在且 hash 一致时复用；
- destination 有未知修改时停止；
- patch 可正向应用一次、可反向验证已应用；
- `.external` source 在操作前后 byte-identical。

- [ ] **Step 2：建立空 patch skeleton 并确认测试失败**

测试应因 patch 未提供新 `varargin/opts` 接口而失败。

- [ ] **Step 3：实现 copy/apply/hash**

脚本不得 `git reset` 官方目录；只操作明确的 destination。输出：

```text
runs/matlab_cp/package_manifest.json
```

包含 source tree hash、patch hash、MATLAB version 和文件列表。
MATLAB executable 按 `command -v matlab`、项目已记录绝对路径的顺序发现；
两者都不存在时 hard stop，不猜测安装路径。

- [ ] **Step 4：运行静态测试并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_cpmc_patch.py
```

Expected: patch provenance 部分 PASS，功能接口测试仍等后续 task。

Commit:

```bash
git add test/pqmc_cp_bridge/matlab/apply_cpmc_patch.sh \
  test/pqmc_cp_bridge/patches/cpmc-lab-mixed-diagnostics.patch \
  test/pqmc_cp_bridge/tests/test_cpmc_patch.py
git commit -m "build: prepare reproducible CPMC-Lab patching"
```

---

### Task 3：分离 Phi_init、Phi_trial 与可复现 RNG

**Files:**

- Modify patch target: `CPMC_Lab.m`
- Modify patch target: `initialization.m`
- Create: `test/pqmc_cp_bridge/matlab/read_orbitals.m`
- Create: `test/pqmc_cp_bridge/matlab/validate_bridge_opts.m`
- Create: `test/pqmc_cp_bridge/matlab/run_cpmc_smoke.m`
- Modify: `test/pqmc_cp_bridge/tests/test_cpmc_patch.py`

**Backward-compatible signature**

```matlab
function [E_ave,E_err,savedFileName,diag] = CPMC_Lab( ...
    Lx,Ly,Lz,N_up,N_dn,kx,ky,kz,U,tx,ty,tz, ...
    deltau,N_wlk,N_blksteps,N_eqblk,N_blk, ...
    itv_modsvd,itv_pc,itv_Em,suffix,varargin)
```

`varargin` 为空时保持 stock 初始化和三个输出调用兼容；非空时只能包含一个
`opts` struct。

**Required opts**

```matlab
opts.Phi_init
opts.Phi_trial
opts.rng_seed
opts.mode                 % production|fixed_horizon|proposal_only
opts.total_steps
opts.diagnostics
opts.output_dir
opts.run_id
opts.contract_hashes
```

- [ ] **Step 1：写 MATLAB 轨道读取测试**

`read_orbitals.m` 读取四个 `.dat`，按 `site_map.dat` 从 ALF order 排到 CPMC
row-major，验证 shape、finite、orthonormality 和 SHA-256。

- [ ] **Step 2：写 mixed 初始化测试**

断言：

```text
Phi(:,:,i) = Phi_init
Phi_T = Phi_trial
O(i) = O0 = det(Tup'*Iup)*det(Tdn'*Idn) > 1e-10
w(i) = 1
```

初始 `E_ref(0)` 固定为 `real(E_mix(T,I))`，通过 stock `measure` 公式计算。

- [ ] **Step 3：实现 RNG contract**

有 `opts.rng_seed` 时使用：

```matlab
rng(opts.rng_seed,'twister')
```

无 opts 时保留 stock time-based seed。诊断开关不得改变 RNG call 次数。

- [ ] **Step 4：做 backward-compatible smoke**

运行官方 `sample.m` 参数的小 smoke，以及 mixed `I/T`、8 walkers、2 steps
smoke。二者都必须成功保存 `.mat`。

- [ ] **Step 5：提交**

```bash
git add test/pqmc_cp_bridge/patches/cpmc-lab-mixed-diagnostics.patch \
  test/pqmc_cp_bridge/matlab/read_orbitals.m \
  test/pqmc_cp_bridge/matlab/validate_bridge_opts.m \
  test/pqmc_cp_bridge/matlab/run_cpmc_smoke.m \
  test/pqmc_cp_bridge/tests/test_cpmc_patch.py
git commit -m "feat: separate CPMC initial and guide determinants"
```

---

### Task 4：记录 halfK/site proposal、路径概率和 E_ref

**Files:**

- Modify patch target: `halfK.m`
- Modify patch target: `V.m`
- Modify patch target: `stepwlk.m`
- Modify patch target: `stblz.m`
- Modify patch target: `CPMC_Lab.m`
- Modify: `test/pqmc_cp_bridge/tests/test_cpmc_patch.py`

**Diagnostic walker state**

每个 walker：

```matlab
diag_state.logQ_prop
diag_state.logW_path
diag_state.logW_ratio
diag_state.log_orbital_scale
diag_state.orbital_scale_sign
diag_state.alive
diag_state.first_rejection_kind
diag_state.first_rejection_step
diag_state.first_rejection_site
diag_state.min_q
diag_state.min_halfk_ratio
diag_state.path_bits_uint64
diag_state.eref_sum
```

Ltrot*×16 fields 按第二阶段相同 LSB-first contract 存入
`ceil(nfield/64)` 个 `uint64`。只有 `fixed_horizon/proposal_only` 的记录可标
`history_origin=I`；production rolling history 必须写
`history_origin=rolling_population` 和 window 起点 step，禁止进入 fixed-I
路径质量或 strata 闭合计算。

**Modified signatures**

```matlab
[phi,w,O,inv_up,inv_dn,event] = halfK(...)
[phi,O,w,inv_up,inv_dn,event] = V(...)
[phi,w,O,E,W,diag_state] = stepwlk(...,diag_state,global_step,opts)
[Phi,O,qr_event] = stblz(...)
```

- [ ] **Step 1：写单 walker fixed-random 测试**

给 V 提供显式 `u_random`，验证两个候选 ratio、positive clipping、
`q_selected`、field 和 weight factor 与 C++ M=1 完全一致。
production 调用仍由 `stepwlk` 预先取得一个 `rand` 并传入，RNG 次数不变。

- [ ] **Step 2：区分 pre/post halfK**

`stepwlk` 显式传入 event kind；kill 时记录 first rejection，但 stock
production 仍把 `w=0`。

- [ ] **Step 3：累计三个 weight**

每层：

```text
fac_norm(l) = [E_ref(l) − U*Npar/2] dt
logW_path += fac_norm + log(half/site importance factors)
logW_ratio += log(half/site importance factors)
eref_sum += E_ref(l) dt
```

alive path 验证：

```text
logW_phys = logW_path − eref_sum
D_TI = O0 * Q_prop * W_phys
```

- [ ] **Step 4：QR scale 诊断**

`stblz` 返回每 spin `det(R)` 的 sign/logabs，累积到
`log_orbital_scale`，用于直接 endpoint overlap 复核；stock `Phi/O` 更新不变。

- [ ] **Step 5：与 C++ 逐 event 对比**

使用同一 2-site/2×2 fixed path，比较 halfK ratio、两个 site ratio、selected
q、logQ、logW、E_ref sum 和 absolute identity，容差 `1e-10`。

- [ ] **Step 6：提交**

```bash
git add test/pqmc_cp_bridge/patches/cpmc-lab-mixed-diagnostics.patch \
  test/pqmc_cp_bridge/tests/test_cpmc_patch.py
git commit -m "feat: trace CPMC proposal and path weights"
```

---

### Task 5：为 population control 增加 parent tree 和不可变 tags

**Files:**

- Modify patch target: `pop_cntrl.m`
- Modify patch target: `CPMC_Lab.m`
- Create: `test/pqmc_cp_bridge/scripts/pc_fragility.py`
- Create: `test/pqmc_cp_bridge/tests/test_pc_fragility.py`

**Modified signature**

```matlab
[Phi,w,O,diag_state,pc_event] = pop_cntrl( ...
    Phi,w,O,diag_state,N_wlk,N_sites,N_par,global_step)
```

`pc_event`：

```matlab
pc_event.parent_index
pc_event.offspring_count
pc_event.log_mean_weight
pc_event.unique_ancestors_before
pc_event.unique_ancestors_after
pc_event.weight_ess_before
pc_event.genealogical_ess_after
```

- [ ] **Step 1：写 deterministic combing 测试**

给出 fixed `u0` 代替内部 rand，手算 parent/offspring。production 仍每次
combing 只调用一次 `rand`。

- [ ] **Step 2：实现诊断继承**

所有 path bits、logQ、logW_path、prefix metrics、tags 和 ancestor ID 按
`parent_index` 复制；stock `w` 仍重置为 1，但 `logW_path` 不重置。

- [ ] **Step 3：实现 realized PC interval fragility**

在 combing 前：

```text
Delta S_ref,r = sum_interval E_ref(l) dt
g_phys,r = log(mean_i w_i) − Delta S_ref,r
u_phys,i,r = Delta(logW_path_i − eref_sum_i)
log a_realized,i,r = u_phys,i,r − g_phys,r
```

每 lineage 记录：

```text
min_log_a
first_interval_log_a_lt_0
count_log_a_lt_0
sum_min_0_log_a
largest_recovery_after_valley
```

`exp(sum_min_0_log_a)` 只标为 retention proxy。
这里减去共同的 `E_ref` 增量，使结果不依赖 population normalization。
`log a_realized` 用于解释该独立 system 的实际 combing；跨 ALF/MATLAB
分层所需的冻结基准在 Task 11 注册，二者不得混用。

- [ ] **Step 4：实现 immutable prefix tags**

从 `strata_contract.json` 载入每个 PC slice 的预注册 predicate。combing 前
满足 predicate 的 lineage 首次获得 tag；复制继承，死亡消失。保存每个独立
system 的：

```text
tagged_before
tagged_with_descendant_at_end
S_k(r_to_end)
```

不得根据最终路径回填已经死亡 lineage 的标签。

- [ ] **Step 5：Python 单元测试**

验证一个 late-blooming lineage 在第一次 combing 灭绝时：

- retention proxy 很小；
- descendant survival 为 0；
- 后续其他 lineage 的 recovery 不会错误归给它。

- [ ] **Step 6：提交**

```bash
git add test/pqmc_cp_bridge/patches/cpmc-lab-mixed-diagnostics.patch \
  test/pqmc_cp_bridge/scripts/pc_fragility.py \
  test/pqmc_cp_bridge/tests/test_pc_fragility.py
git commit -m "feat: record CPMC population genealogy"
```

---

### Task 6：实现 fixed_horizon、proposal_only 和 production 三模式

**Files:**

- Modify patch target: `CPMC_Lab.m`
- Create: `test/pqmc_cp_bridge/matlab/run_cpmc_bridge.m`
- Modify: `test/pqmc_cp_bridge/tests/test_cpmc_patch.py`

**Mode semantics**

`fixed_horizon`：

```text
初始化一次 Nw walkers，全部为 I
传播恰好 opts.total_steps=Ltrot*
末步 mixed energy 在末步 population control 前测量
保存 terminal weighted population、path bits、strata metrics、PC tree
不进入 open-ended measurement blocks
```

`proposal_only`：

```text
每 walker 从 I 独立开始
关闭 population control
传播 opts.total_site_events 指定的短 prefix
只统计预注册 target prefixes 的命中
```

`production`：

```text
从 I 初始化一次
先完成 N_eqblk*N_blksteps ≥ Ltrot* 的 equilibration
再按 stock block loop 测量
保存 block energy 和可选 rolling diagnostics
rolling path 的起点不标为 I
```

- [ ] **Step 1：写 mode reset 测试**

连续两个 fixed systems 必须重新得到相同 `Phi_init/O0/w=1`；production
block 之间不得重置 population。

- [ ] **Step 2：写 terminal-before-PC 测试**

当 Ltrot* 可被 `itv_pc` 整除时，terminal estimator 必须使用最后一次
combing 前的 `w`，不能使用重置后的全 1。

- [ ] **Step 3：写 diagnostics on/off 等价测试**

相同 seed、free/free `Phi_init=Phi_trial`、短 run：

```text
diagnostics=false
diagnostics=true
```

两者的 fields、block energy、final Phi/w/O 必须 byte-identical 或
`maxabs<1e-13`；证明诊断未改变算法或 RNG。

- [ ] **Step 4：保存 MATLAB v7 outputs**

大 path bits/parent arrays 分 run 保存，避免单个大 `.mat`。每个 run 的
summary `.mat` 至少包含 contract hashes、mode、seed、parameters、E_ref
schedule、terminal estimator、wall time 和 data filenames。

- [ ] **Step 5：运行 smoke 并提交**

```bash
test/pqmc_cp_bridge/matlab/apply_cpmc_patch.sh \
  --source .external/cpmc-lab/CPMC_Lab_20160129 \
  --destination test/pqmc_cp_bridge/runs/matlab_cp/package
matlab -batch "run('test/pqmc_cp_bridge/matlab/run_cpmc_smoke.m')"
```

Expected: 三种 mode 的 tiny smoke 全部 PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/patches/cpmc-lab-mixed-diagnostics.patch \
  test/pqmc_cp_bridge/matlab/run_cpmc_bridge.m \
  test/pqmc_cp_bridge/tests/test_cpmc_patch.py
git commit -m "feat: add fixed-horizon CPMC diagnostics"
```

---

### Task 7：实现 MATLAB 输出解析和独立-run 统计

**Files:**

- Create: `test/pqmc_cp_bridge/scripts/parse_cpmc_results.py`
- Create: `test/pqmc_cp_bridge/tests/test_cpmc_results.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class RunEstimate:
    run_id: str
    seed: int
    energy: float
    terminal_weight: float
    strata_mass: dict[str, float]

def load_cpmc_run(path: Path, contract: CpmcContract) -> RunEstimate
def independent_run_estimate(runs: Sequence[RunEstimate]) -> Estimate
def block_and_run_error(blocks_by_run) -> float
```

误差定义：

```text
sigma_block = 最大合法 time-block jackknife error
sigma_run = delete-one-independent-run jackknife error
sigma = max(sigma_block, sigma_run)
```

walkers 不进入误差样本数。

- [ ] **Step 1：写 synthetic `.mat` 测试**

覆盖：

- shape/hash/mode 错误；
- per-walker SEM 被禁止；
- run-to-run offset 使 `sigma_run` 大于 pooled block error；
- terminal ratio 使用 `ΣwE/Σw`；
- PC 后全 1 权重不会覆盖 terminal pre-PC weights。

- [ ] **Step 2：实现 parser 和 CSV index**

每解析一个 run 原子更新 `results/cpmc_run_index.json`；重复 run_id/seed
拒绝。

- [ ] **Step 3：运行并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_cpmc_results.py
```

Expected: PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/parse_cpmc_results.py \
  test/pqmc_cp_bridge/tests/test_cpmc_results.py
git commit -m "feat: analyze independent CPMC runs"
```

---

### Task 8：实现 fixed-horizon 与 production 自适应运行器

**Files:**

- Create: `test/pqmc_cp_bridge/scripts/run_fixed_horizon_grid.py`
- Create: `test/pqmc_cp_bridge/scripts/run_production_cp.py`
- Create: `test/pqmc_cp_bridge/tests/test_cpmc_results.py`

**Production stopping rules**

每个 Nw point 第一 wave 为六个独立 seed，每 run：

```text
N_blksteps=20
N_eqblk=ceil(Ltrot*/20)
N_blk=50
itv_modsvd=5
itv_pc=5（PC scan 时为 20 或 40）
itv_Em=5
```

然后：

1. 若最后 25 blocks 与最前 25 blocks 的差超过 combined 2σ，增加
   `ceil(Ltrot*/20)` equilibration blocks，使用新 seed 全部重跑；
2. 稳态后，若 `sigma_E>0.005`，追加六个新 independent runs；
3. 达标后冻结该 Nw/PC point；
4. 先完成 Nw=500、1000；若差超过 combined 2σ，再运行 2000；
5. Nw=100 用于展示有限 population 趋势，不决定是否追加 2000。

**Fixed-horizon stopping rules**

每个 `(Nw,itv_pc)` 第一 wave 20 independent systems。每 system 恰好 Ltrot*
steps。若 terminal energy `sigma>0.005`，或预期位于 CP support 内的任一主
stratum（排除按定义 `q=0` 的 `dead_support`）有 terminal 非零质量的独立
system 数少于 20，则每次追加 20 systems，最多先到 100。到 100 仍稀少的
support stratum 只报告 upper bound/探索性结果；`dead_support` 直接报告
`p_CP=0` 和其 ALF 参考质量，不会触发无限扩样。

- [ ] **Step 1：写 mock MATLAB runner 状态机测试**

覆盖 resume、失败 run 隔离、production drift restart、2000 walkers 的条件
触发、fixed wave 扩充和 hash mismatch hard stop。

- [ ] **Step 2：实现单任务运行与进度**

每个 MATLAB process 单核运行；每 30 秒 tail 当前 block/system 进度。
当前无 active Slurm profile，因此默认逐 run 本地执行；开始正式 grid 前用
8 walkers×20 steps timing probe 估算总 wall time。若预计超过 10 分钟，
先把 fixed、production、proposal-only 三部分的预计 wall time 和磁盘量报告
给用户确认；确认后把 `accepted_walltime_estimate` 写入 run contract，再开始
正式 grid。没有 cluster profile 时不得伪装远程提交。

- [ ] **Step 3：实现 resume**

只有 summary `.mat`、data files 和 hash 全部完整的 run 才标记 complete；
中断 run 使用新 run_id 重跑，不拼接 RNG trajectory。

- [ ] **Step 4：运行单元测试并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_cpmc_results.py
```

Expected: PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/run_fixed_horizon_grid.py \
  test/pqmc_cp_bridge/scripts/run_production_cp.py \
  test/pqmc_cp_bridge/tests/test_cpmc_results.py
git commit -m "feat: orchestrate fixed and production CPMC runs"
```

---

### Task 9：验证 proposal probability 与短 prefix 命中率

**Files:**

- Create: `test/pqmc_cp_bridge/scripts/run_proposal_check.py`
- Modify: `test/pqmc_cp_bridge/tests/test_cpmc_results.py`

**Target selection**

从 TI training paths 预先选 20 条：

```text
5 regular
5 low-final-Q
5 deep-prefix
5 near-node
```

对每条只测试满足 `R*Q_prefix≥20` 的最长 prefix，`R=100000` independent
proposal walkers；prefix 长度可停在任意 site event，不要求完整 slice。

- [ ] **Step 1：写 binomial contract 测试**

对已知 q 序列，理论：

```text
Q_prefix = product(q_j)
P_hit = 1-(1-Q_prefix)^R
```

实际命中 count 与 `Binomial(R,Q_prefix)` 的 4σ 区间比较。完整 Ltrot*
bitstring 只报告 logQ 和理论等待数，不要求实际重复。

- [ ] **Step 2：运行 no-PC proposal-only**

关闭 resampling，每条 walker 独立从 I 开始。测试只验证 proposal，不与
fixed-horizon genealogy 混合。

- [ ] **Step 3：输出并提交**

输出 `results/proposal_check.csv`，列出 path、prefix events、logQ、expected、
observed 和 z-score。

```bash
git add test/pqmc_cp_bridge/scripts/run_proposal_check.py \
  test/pqmc_cp_bridge/tests/test_cpmc_results.py
git commit -m "test: validate CPMC short-prefix probabilities"
```

---

### Task 10：实现 II、TI、support 和 cross-reweight 估计

**Files:**

- Create: `test/pqmc_cp_bridge/scripts/cross_reweight.py`
- Create: `test/pqmc_cp_bridge/scripts/energy_decomposition.py`
- Create: `test/pqmc_cp_bridge/tests/test_energy_decomposition.py`

**Interfaces:**

```python
def ii_strata_estimates(rows, labels) -> dict
def ti_sign_reweighted(rows, labels) -> dict
def support_restricted_ti(rows) -> Estimate
def cross_reweight_ii_to_ti(rows) -> ReweightEstimate
```

**Required estimators**

II：

```text
p_II,k = mean(1_k)
E_II,k = mean(1_k E_2s^I)/p_II,k
E_PQMC = sum_k p_II,k E_II,k
```

TI：

```text
E_TI,all = sum(s_TI E_mix^T)/sum(s_TI)
p_TI,k = sum(s_TI 1_k)/sum(s_TI)
E_TI,k = sum(s_TI 1_k E_mix^T)/sum(s_TI 1_k)
E_CP,support = sum(s_TI 1_alive E_mix^T)/sum(s_TI 1_alive)
```

II→TI：

```text
r = D_TI/D_II
E_TI,cross = sum(r E_mix^T)/sum(r)
ESS_r = (sum r)^2/sum(r^2)
```

所有计算在 signed-log 中完成。报告最大归一化 weight 和 top 1% weight
share；ESS 太低时 cross 结果只标 diagnostic。

- [ ] **Step 1：写 exact synthetic closure tests**

构造四个互斥 strata，验证：

```text
sum p = 1
sum p_k E_k = direct energy
删除 stratum k 的反事实能量公式
sign reweight ratio
support restriction
cross ESS
```

- [ ] **Step 2：实现 chain-aware bootstrap**

ALF 以 chain 为 bootstrap unit；threshold 只从 chains 0–2 读取，最终报告
只在 chains 3–5 评估，同时给 all-chain 精度附录。

- [ ] **Step 3：运行并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_energy_decomposition.py
```

Expected: PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/cross_reweight.py \
  test/pqmc_cp_bridge/scripts/energy_decomposition.py \
  test/pqmc_cp_bridge/tests/test_energy_decomposition.py
git commit -m "feat: reconstruct II and TI path energies"
```

---

### Task 11：加入 PC fragility 并完成 fixed-horizon 能量分解

**Files:**

- Modify: `test/pqmc_cp_bridge/scripts/pc_fragility.py`
- Modify: `test/pqmc_cp_bridge/scripts/energy_decomposition.py`
- Modify: `test/pqmc_cp_bridge/tests/test_pc_fragility.py`
- Modify: `test/pqmc_cp_bridge/tests/test_energy_decomposition.py`
- Create: `test/pqmc_cp_bridge/results/pc_strata_contract.json`

**PC reference/threshold registration**

先在 primary `Nw=1000,itv_pc=5` 的 fixed-horizon training systems 前一半，
对每个 PC interval 冻结 reference-free population growth：

```text
g_ref,r = median_training_systems[
  log(mean_i w_i before combing) − Delta S_ref,r
]
```

保存每个 `g_ref,r` 的 system 数、IQR 和 contract hash。随后从第二阶段 C++
prefix 的 `logW_phys` 计算每条 ALF TI training path 的
`u_phys,r=Delta logW_phys`，并定义跨数据集共用的静态指标：

```text
log a_static,r = u_phys,r − g_ref,r
f01 = 1st percentile of min_r log a_static,r among alive TI training paths
r99 = 99th percentile of recovery_after_valley among alive TI training paths
```

对 MATLAB terminal path 也使用自己的 `u_phys,r` 与同一个 `g_ref,r`，而不是
该 system 自己的 `g_phys,r`。这样 `p_TI,k` 与 `p_CP,k` 使用同一分类函数；
Task 5 的 `log a_realized` 只用于实际谱系灭绝证据。ALF chains 3–5 和
MATLAB held-out seeds 均不参与 reference/threshold。primary complete strata
扩展为：

```text
dead_support
alive_low_final_q
alive_deep_prefix_not_low_q
alive_pc_fragile_not_previous
alive_regular
```

- [ ] **Step 1：写 five-strata closure test**

每条 path 恰好属于一类；空类保留 p=0、E=NaN，不从分解中静默删除。
另验证给全部 `E_ref` 加常数时，`g_ref、u_phys、log a_static` 均不变。

- [ ] **Step 2：冻结并应用共同 PC reference**

`pc_fragility.py` 必须按上述顺序生成 `pc_strata_contract.json`，再把同一
`g_ref/f01/r99` 应用于 ALF TI training/held-out summary 和 MATLAB
fixed-horizon paths。输出同时保留：

```text
min_log_a_static       # 跨数据集分层
min_log_a_realized     # MATLAB 实际 combing 诊断
```

Nw 与 PC interval 扫描沿用 primary static labels；只让 realized survival
随算法参数变化，避免每个点重定义“脆弱路径”。

- [ ] **Step 3：实现 fixed-horizon quantities**

每个 independent system 先计算：

```text
p_CP,k = sum_terminal(w 1_k)/sum_terminal(w)
E_CP,k = sum_terminal(w 1_k E_mix)/sum_terminal(w 1_k)
E_CP,fixed = sum_terminal(w E_mix)/sum_terminal(w)
```

然后对 independent systems bootstrap。

- [ ] **Step 4：实现偏差分解**

held-out 数据验证：

```text
Delta_frequency =
  sum_k (p_CP,k-p_TI,k) E_TI,k

Delta_within =
  sum_k p_CP,k (E_CP,k-E_TI,k)

E_CP,fixed-E_TI,all =
  Delta_frequency+Delta_within
```

closure residual 必须 `<1e-10`（逐点代数）且 bootstrap summary 一致。
`sum p_CP,k E_TI,k` 只标为 frequency-only counterfactual。这里的
`p_TI,k/E_TI,k` 来自 ALF TI held-out chains，`p_CP,k/E_CP,k` 来自 MATLAB
held-out systems；二者都使用 Step 2 的 static labels。

- [ ] **Step 5：genealogy survival**

对每个 immutable prefix tag 报告跨 independent systems 的
`S_k(r→end)`、Wilson interval 和 tagged system count；不能把 tagged walkers
当独立样本。

- [ ] **Step 6：提交**

```bash
git add test/pqmc_cp_bridge/scripts/pc_fragility.py \
  test/pqmc_cp_bridge/scripts/energy_decomposition.py \
  test/pqmc_cp_bridge/tests/test_pc_fragility.py \
  test/pqmc_cp_bridge/tests/test_energy_decomposition.py \
  test/pqmc_cp_bridge/results/pc_strata_contract.json
git commit -m "feat: decompose finite-walker CPMC bias"
```

---

### Task 12：执行正式 MATLAB grid

**Files:**

- Create: `test/pqmc_cp_bridge/results/cpmc_run_index.json`
- Create: `test/pqmc_cp_bridge/results/fixed_horizon_summary.csv`
- Create: `test/pqmc_cp_bridge/results/production_summary.csv`
- Create: `test/pqmc_cp_bridge/results/genealogy_summary.csv`

- [ ] **Step 1：运行完整 smoke**

```bash
test/pqmc_cp_bridge/matlab/apply_cpmc_patch.sh \
  --source .external/cpmc-lab/CPMC_Lab_20160129 \
  --destination test/pqmc_cp_bridge/runs/matlab_cp/package
matlab -batch "run('test/pqmc_cp_bridge/matlab/run_cpmc_smoke.m')"
/usr/bin/python3 -m unittest discover -v \
  -s test/pqmc_cp_bridge/tests -p 'test_*.py'
```

Expected: MATLAB/C++/Python contract tests全部 PASS。

- [ ] **Step 2：执行 timing probe**

运行 8 walkers×20 steps，记录 walker-step/s；估算全部 fixed/production grid
以及 proposal-only 的 wall time和磁盘量。按 Task 8 的 cost gate 报给用户；
只有 `accepted_walltime_estimate` 已写入 contract 才继续 Step 3。当前无
active Slurm profile，因此确认后按本机单线程进程路线执行并写
`local-compute deviation`。

- [ ] **Step 3：运行 fixed-horizon primary grid**

```bash
/usr/bin/python3 -u \
  test/pqmc_cp_bridge/scripts/run_fixed_horizon_grid.py \
  --nwalkers 100,500,1000 \
  --pc-every 5 \
  --systems-per-wave 20
```

随后运行 PC scan：

```bash
/usr/bin/python3 -u \
  test/pqmc_cp_bridge/scripts/run_fixed_horizon_grid.py \
  --nwalkers 1000 \
  --pc-every 20,40 \
  --systems-per-wave 20
```

runner 按 Task 8 规则自动扩展 wave。

- [ ] **Step 4：运行 production**

```bash
/usr/bin/python3 -u \
  test/pqmc_cp_bridge/scripts/run_production_cp.py \
  --nwalkers 100,500,1000 \
  --pc-every 5
```

若 500/1000 未收敛，runner 自动追加 2000；随后：

```bash
/usr/bin/python3 -u \
  test/pqmc_cp_bridge/scripts/run_production_cp.py \
  --nwalkers 1000 \
  --pc-every 20,40
```

- [ ] **Step 5：fixed vs production gate**

在 Nw=1000、PC=5：

```text
|E_fixed-E_production| ≤
2*sqrt(sigma_fixed^2+sigma_production^2)
```

若失败，停止路径类别因果归因，报告“共同 Ltrot* 下 CP 尚未忘记初态”；
不通过延长 production rolling window 来伪造 fixed-I 等价。

- [ ] **Step 6：运行 proposal-only**

```bash
/usr/bin/python3 -u \
  test/pqmc_cp_bridge/scripts/run_proposal_check.py \
  --independent-walkers 100000
```

- [ ] **Step 7：提交小型摘要**

```bash
git add test/pqmc_cp_bridge/results/cpmc_run_index.json \
  test/pqmc_cp_bridge/results/fixed_horizon_summary.csv \
  test/pqmc_cp_bridge/results/production_summary.csv \
  test/pqmc_cp_bridge/results/genealogy_summary.csv \
  test/pqmc_cp_bridge/results/proposal_check.csv
git commit -m "results: run mixed-boundary CPMC grid"
```

---

### Task 13：因果扫描、最终图和结论强度

**Files:**

- Create: `test/pqmc_cp_bridge/scripts/make_final_report.py`
- Create: `test/pqmc_cp_bridge/results/energy_decomposition.json`
- Create: `test/pqmc_cp_bridge/results/causal_scan.json`
- Create: `test/pqmc_cp_bridge/results/final_report.md`
- Create: `test/pqmc_cp_bridge/results/final_figure.png`

- [ ] **Step 1：运行 held-out 分解**

```bash
/usr/bin/python3 \
  test/pqmc_cp_bridge/scripts/energy_decomposition.py \
  --split held-out
```

输出至少：

```text
E_PQMC
E_TI,all
E_CP,support
E_CP,fixed(Nw,pc)
E_CP,production(Nw,pc)
Delta_frequency
Delta_within
ESS_r / max weight / top1% share
closure residuals
```

- [ ] **Step 2：应用预注册判别表**

`causal_scan.json` 逐项记录 evidence：

```text
hard_support:
  dead strata 的 p_TI 与 p_II 非零，p_CP=0，且非 numerical ambiguity

finite_population_extinction:
  q>0、min_log_a 很低，覆盖随 Nw 增大或 PC 变稀恢复

micro_path_rarity_only:
  final Q 很低，但类别 p_CP 与 p_TI 一致

dynamic_nonergodicity:
  本阶段没有全局正-overlap 连通图，因此默认 status=not_identified；
  不能仅凭多个 run 未见某类路径就声称节点连通域断裂

unexplained:
  strata frequency/within terms 不能闭合 observed production bias
```

只有满足对应数据条件才设 `supported=true`。本阶段可以定量判别硬 support
缺失和有限-population 灭绝，但“正 overlap 区域内的全局动态非遍历性”需要
另做连通图/constraint-release bridge 实验；本报告把它列为未识别机制，不作
排除或证明。

- [ ] **Step 3：生成一张四 panel 图**

```text
(a) ALF II/TI、support、fixed、production energies
(b) p_TI,k 与 p_CP,k 随 Nw
(c) Delta_frequency 与 Delta_within
(d) tagged-lineage survival 随 PC interval
```

误差棒均来自 chain 或 independent run，不来自 walkers。

- [ ] **Step 4：写结论**

若 `target_reached` 且全部门槛通过，可写固定参数点的定量结论；若
`max_theta_fallback`，标题和首段必须明确“finite Θ=20 diagnostic”。

若欠覆盖 strata 不能解释 CP 偏差，报告：

```text
在当前统计量和预注册诊断下，未找到该机制足以解释系统误差的证据。
```

不得事后移动 threshold 使结果看起来闭合。

- [ ] **Step 5：最终验证并提交**

```bash
/usr/bin/python3 -m unittest discover -v \
  -s test/pqmc_cp_bridge/tests -p 'test_*.py'
/usr/bin/python3 \
  test/pqmc_cp_bridge/scripts/make_final_report.py
```

Expected: tests PASS，所有 closure residual 和 hash gate PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/make_final_report.py \
  test/pqmc_cp_bridge/results/energy_decomposition.json \
  test/pqmc_cp_bridge/results/causal_scan.json \
  test/pqmc_cp_bridge/results/final_report.md \
  test/pqmc_cp_bridge/results/final_figure.png
git commit -m "results: attribute constrained-path energy bias"
```

---

## Phase-3 验收门槛

- [ ] 官方 package source 未被修改或提交；
- [ ] patch source hash、patched runtime hash、MATLAB version 全部记录；
- [ ] `Phi_init=I`、`Phi_trial=T`、O0>0 且 hash 与 ALF/C++ 相同；
- [ ] diagnostics on/off 不改变相同 seed 的 CP trajectory；
- [ ] MATLAB 与 C++ 在短路径逐 event 的 q、W、E_ref、D identity 一致；
- [ ] `logW_path` 不被 population control 重置；
- [ ] parent/offspring tree 与 path/tag 继承一致；
- [ ] common `g_ref/f01/r99` 只由 training data 冻结，并同时标注 ALF TI 与 MATLAB fixed paths；
- [ ] `log a_static` 与 `log a_realized` 分开保存，E_ref 平移测试通过；
- [ ] fixed-horizon 每个 system 恰好 Ltrot* 并从 I 重启；
- [ ] production equilibration 至少 Ltrot*，且 block energy 无显著 drift；
- [ ] production 和 fixed-horizon energy 均使用 independent-run error；
- [ ] Nw=1000 primary point的误差不大于 0.005；
- [ ] fixed-horizon 与 production primary point 在 combined 2σ 内一致；
- [ ] proposal-only 短 prefix 频率与 Q_prop 的 binomial 预期一致；
- [ ] II/TI/support/fixed 的每个分层恒等式在 held-out data 上闭合；
- [ ] cross-reweight 报告 ESS、最大 weight 和 top1% share；
- [ ] PC survival 使用 independent systems，不用 walkers 伪造误差棒；
- [ ] walker 数和 PC interval 扫描支持或否定预注册因果判别；
- [ ] 未构建正-overlap 连通图时，dynamic nonergodicity 保持 `not_identified`；
- [ ] 结论严格限制在固定的 4×4、PBC、U=4、半满、spin-HS、UHF(Ueff=4) 参数点。
