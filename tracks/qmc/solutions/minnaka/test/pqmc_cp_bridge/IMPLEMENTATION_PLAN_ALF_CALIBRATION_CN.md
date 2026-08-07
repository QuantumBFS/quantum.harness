# ALF free/UHF 投影长度标定：实施计划

> **执行要求：** 按任务顺序实施；每个任务先写失败测试，再写最小实现，再运行测试并单独提交。执行本计划时使用 `superpowers:executing-plans`。本计划只覆盖第一阶段：生成统一边界轨道、实现 ALF free/UHF、扫描 Θ 并确定 `selected_projection.json`。构型档案、C++ 完整路径 replay 和 MATLAB CPMC 属于第二、三阶段，必须消费本阶段冻结的投影长度，不在本计划中提前实现。

## 目标

在固定的 4×4 PBC、半满、t=1、U=4、二值 Hirsch spin HS、
Δτ=0.05、Beta=1 条件下，实现可验证的 ALF free/UHF projector-QMC，
并按已确认的规则从 Θ=10,12,14,16,18,20 中选择共同投影长度。

每个 Θ 必须先把总能量误差控制到 `σ_E≤0.005`，然后才允许检查
`|E−(−13.62192)|≤0.005`。如果 Θ=20 在误差达标后仍不满足能量窗口，
输出 `status=max_theta_fallback` 并以 Θ*=20 继续后续阶段。

## 架构

边界态只生成一次：

1. ALF 的 stock `Ham_Trial` 生成弱二聚化 free determinant `I`；
2. 一个 rank-1 bootstrap 运行从 ALF 内存直接导出 `I↑、I↓`；
3. 现有 `test/cpmc_path_audit` 的 oneMKL UHF 求解器读取 `I`，求解
   UHF(Ueff=4) 的 `T↑、T↓`，并利用 determinant gauge 使每个自旋的
   `det(TσᵀIσ)>0`；
4. ALF mixed-boundary 模式载入 `T` 作为左边界，保留内建 `I` 作为右边界；
5. mixed 模式强制显式传播两个 flavor，禁用当前半满代码的单-flavor
   粒子—空穴重构。

扫描由一个可恢复的 Python 控制器驱动。每个统计批次包含六条独立、
单 rank、单线程链；每条链丢弃第一个 bin。控制器只在当前 Θ 的统计和数值
完整性门槛全部通过后公开并判断该点能量。

## 技术栈

- ALF 2.4，固定 commit `ff5600df97877ef1d080432d0068e157ff520ecd`
- Intel Fortran、Intel MPI、oneMKL
- C++17、`icpx -qmkl=sequential`
- Python 3 标准库；绘图沿用仓库已有 Matplotlib 环境
- `unittest` 与现有 C++ 测试可执行文件

## 固定物理与统计契约

| 项目 | 固定值 |
|---|---:|
| lattice | 4×4 square |
| boundary | PBC × PBC |
| t | 1 |
| U | 4 |
| N↑, N↓ | 8, 8 |
| HS | real binary Hirsch spin |
| Δτ | 0.05 |
| Beta | 1 |
| Θ candidates | 10, 12, 14, 16, 18, 20 |
| Ltrot | `(2Θ+Beta)/Δτ` |
| chains per batch | 6 |
| MPI ranks per chain | 1 |
| threads per rank | 1 |
| first batch | NBin=7, NSweep=2000 |
| discarded bins | first bin of every independent chain |
| target uncertainty | σ_E≤0.005 |
| target energy | E₀=−13.62192 |
| energy window | absolute difference ≤0.005 |

ALF `Ener_scal` 必须报告原始 Hubbard Hamiltonian
`H=K+U Σ_i n_i↑n_i↓` 的能量。分析器同时验证 `E=K+V`；不得在扫描脚本
中静默加入或减去常数。

## 输出布局

```text
test/pqmc_cp_bridge/
├── DESIGN_CN.md
├── IMPLEMENTATION_PLAN_ALF_CALIBRATION_CN.md
├── assets/
│   └── trials/
│       ├── trial_I_up.dat
│       ├── trial_I_down.dat
│       ├── trial_T_up.dat
│       ├── trial_T_down.dat
│       ├── site_map.dat
│       ├── uhf_metadata.json
│       └── trial_manifest.json
├── scripts/
│   ├── bridge_config.py
│   ├── prepare_alf_chain.py
│   ├── run_alf_batch.py
│   ├── alf_statistics.py
│   ├── calibrate_projection.py
│   └── plot_theta_scan.py
├── tests/
│   ├── test_bridge_config.py
│   ├── test_prepare_alf_chain.py
│   ├── test_alf_statistics.py
│   ├── test_calibrate_projection.py
│   └── test_real_alf_boundary.py
├── runs/
│   └── alf_projection/
├── results/
│   ├── theta_scan.csv
│   ├── theta_scan.json
│   ├── theta_scan.png
│   ├── selected_projection.json
│   ├── calibration_report.md
│   └── provenance.json
└── .gitignore
```

`runs/`、编译产物和大体积结果在本地保留但 gitignore。代码、测试、设计、
小型 JSON/CSV 摘要和最终图可以提交。不得删除或覆盖
`test/alf_hirsch_binary/results` 的既有 free/free 基线。

---

## Task 1：冻结桥接配置和投影长度状态机

**Files**

- Create: `test/pqmc_cp_bridge/scripts/bridge_config.py`
- Create: `test/pqmc_cp_bridge/tests/test_bridge_config.py`
- Create: `test/pqmc_cp_bridge/.gitignore`

**Interfaces**

```python
@dataclass(frozen=True)
class PhysicalConfig:
    lx: int
    ly: int
    hopping: float
    interaction: float
    n_up: int
    n_down: int
    dt: float
    beta: float
    exact_energy: float

def approved_config() -> PhysicalConfig
def theta_candidates() -> tuple[int, ...]
def ltrot(theta: float, config: PhysicalConfig) -> int
def energy_ok(energy: float, config: PhysicalConfig) -> bool
def validate_config(config: PhysicalConfig) -> None
```

- [ ] **Step 1：写失败测试**

测试：

```python
def test_fixed_projection_grid():
    cfg = approved_config()
    assert theta_candidates() == (10, 12, 14, 16, 18, 20)
    assert [ltrot(x, cfg) for x in theta_candidates()] == [
        420, 500, 580, 660, 740, 820
    ]

def test_energy_window_is_absolute_005():
    cfg = approved_config()
    assert energy_ok(-13.62192 + 0.005, cfg)
    assert not energy_ok(-13.62192 + 0.0050001, cfg)
```

还要拒绝非半满、非 PBC、非正 `dt`，并检查 `2Θ+Beta` 可被 `dt` 整除到
整数层，误差小于 `1e-12`。

- [ ] **Step 2：运行并确认失败**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_bridge_config.py
```

Expected: `ModuleNotFoundError` 或接口缺失。

- [ ] **Step 3：实现最小不可变配置**

所有物理常数只在 `bridge_config.py` 定义一次。运行脚本不得重新硬编码
Θ 列表、精确能量或误差阈值。

- [ ] **Step 4：运行测试并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_bridge_config.py
```

Expected: PASS.

Commit:

```bash
git add test/pqmc_cp_bridge/.gitignore \
  test/pqmc_cp_bridge/scripts/bridge_config.py \
  test/pqmc_cp_bridge/tests/test_bridge_config.py
git commit -m "test: define ALF projection calibration contract"
```

---

## Task 2：为共享轨道定义可跨 Fortran/C++/MATLAB 的格式

**Files**

- Create: `test/cpmc_path_audit/include/trial_io.hpp`
- Create: `test/cpmc_path_audit/src/trial_io.cpp`
- Create: `test/cpmc_path_audit/tests/test_trial_io.cpp`
- Modify: `test/cpmc_path_audit/include/trial.hpp`
- Modify: `test/cpmc_path_audit/src/trial.cpp`

**Matrix file contract**

每个 `.dat` 文件均为纯 ASCII，便于 Fortran list-directed read：

```text
16 8
<row 0: 8 values, each %.17e>
...
<row 15: 8 values, each %.17e>
```

不在矩阵文件内放注释。语义、坐标、spin、列顺序、来源 commit、UHF 参数、
矩阵 SHA-256 和 gauge 信息放在 `trial_manifest.json`。`site_map.dat` 每行：

```text
alf_site_1based  cpp_site_0based  x  y
```

**Interfaces**

```cpp
Matrix read_real_orbitals(const std::string& path,
                          std::size_t rows, std::size_t cols);
void write_real_orbitals(const std::string& path, const Matrix& orbitals);
double orthonormality_residual(const Matrix& orbitals);
double particle_hole_projector_residual(const Matrix& up,
                                        const Matrix& down,
                                        const HubbardModel& model);
double orient_overlap_positive(Matrix& trial, const Matrix& initial);
```

`orient_overlap_positive` 只允许将 trial 最后一列乘以 `−1`；不旋转占据
子空间。完成后返回的每个 spin determinant 必须严格为正且大于 `1e-10`。

- [ ] **Step 1：写失败的格式和规范测试**

覆盖：

- 16×8 矩阵写入再读回，最大误差 `<1e-16`；
- shape 不匹配、非有限值、额外数值均拒绝；
- 正交矩阵残差 `<1e-12`；
- 人为翻转最后一列后，`orient_overlap_positive` 恢复正 overlap；
- 4×4、UHF(Ueff=4) 的粒子—空穴 projector 残差 `<1e-10`；
- 非平凡 ALF→C++ site permutation 往返后矩阵不变。

- [ ] **Step 2：运行并确认链接失败**

```bash
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
make -C test/cpmc_path_audit build/test_trial_io
```

Expected: missing header/symbol failure.

- [ ] **Step 3：实现严格读取、写入和残差**

粒子—空穴残差使用占据 projector：

```text
R_PH = max|P↓ − (1 − S P↑ S)|
S_ii = (−1)^(x_i+y_i)
Pσ   = Φσ Φσᵀ .
```

这项检查同时适用于 ALF 的 bipartite free determinant 和 Néel UHF。

- [ ] **Step 4：运行全部 C++ 单元测试**

```bash
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
make -C test/cpmc_path_audit test
```

Expected: 新旧测试全部 PASS。

- [ ] **Step 5：提交**

```bash
git add test/cpmc_path_audit/include/trial_io.hpp \
  test/cpmc_path_audit/src/trial_io.cpp \
  test/cpmc_path_audit/include/trial.hpp \
  test/cpmc_path_audit/src/trial.cpp \
  test/cpmc_path_audit/tests/test_trial_io.cpp
git commit -m "feat: add shared trial orbital contract"
```

---

## Task 3：扩展 ALF 以导出 free 边界并载入 UHF 左边界

**Files**

- Create: `test/alf_hirsch_binary/patches/free-uhf-boundary.patch`
- Modify: `test/alf_hirsch_binary/scripts/build.sh`
- Modify: `test/alf_hirsch_binary/tests/test_binary_hirsch.py`
- Modify upstream through patch only:
  `test/alf_hirsch_binary/ALF/Prog/Hamiltonians/Hamiltonian_Hubbard_Plain_Vanilla_smod.F90`

**New ALF parameters**

```fortran
Integer :: Trial_boundary_mode = 0
Logical :: Export_trial_orbitals = .false.
```

语义：

- `Trial_boundary_mode=0`：stock free/free；
- `Trial_boundary_mode=1`：stock free right + file-loaded UHF left；
- 其他值：立即 `error stop`。

固定运行目录文件名：

```text
trial_T_up.dat
trial_T_down.dat
trial_I_up.dat
trial_I_down.dat
site_map.dat
```

**ALF implementation invariants**

1. 先执行现有 `Ham_Trial` 的 free determinant 构造，得到未缩放的 `I`；
2. `Export_trial_orbitals=.true.` 时仅由 group rank 0 导出原始 `I` 和 site map；
3. mixed 模式分别读取 `T↑、T↓`，不得用一个矩阵覆盖两个 spin；
4. 对四个矩阵检查 shape、finite 和 `ΦᵀΦ≈1`；
5. 分别计算 `det(T↑ᵀI↑)`、`det(T↓ᵀI↓)`，两者都必须正且 `>1e-10`；
6. 调用 `WF_overlap` 前后都记录 overlap；其 normalization factor 写入 `info`；
7. mixed 模式设置 `Calc_Fl=(.true.,.true.)`，使 `N_FL_eff=2`；
8. free/free 保留 stock 单-flavor reconstruction，作为性能基线；
9. `info` 必须明确打印 boundary mode、两个 overlap、两个正交残差和
   `Explicit flavor propagation: T/F`。

- [ ] **Step 1：先写真实可执行失败测试**

在 `test_binary_hirsch.py` 中增加：

- mode 1 缺少 `trial_T_*.dat` 时必须非零退出；
- 非正交、错误 shape、NaN 轨道必须非零退出；
- mode 0 的 `N_FL_eff=1`，mode 1 的 `N_FL_eff=2`；
- mode 1 的 `info` 显示 `WF_R=free`、`WF_L=UHF`；
- `Export_trial_orbitals=.true.` 生成两个 16×8 free 文件和 16 行 site map；
- 导出文件重新读取后 `max|I↑−I↓|<1e-14` 且正交残差 `<1e-12`。

- [ ] **Step 2：运行并确认失败**

```bash
./test/alf_hirsch_binary/scripts/test.sh
```

Expected: 新 mixed-boundary 测试失败，旧 binary-Hirsch 测试仍通过。

- [ ] **Step 3：实现第二个增量 patch**

保留 `hirsch-binary.patch` 不变。`free-uhf-boundary.patch` 只包含本任务的
增量，便于在当前已应用 binary patch 的 checkout 上安全应用。

`build.sh` 按顺序处理两个 patch：

```text
hirsch-binary.patch
free-uhf-boundary.patch
```

每个 patch 的状态只能是“可正向应用”或“可反向验证为已应用”；其他状态
立即停止。最终 dirty file 集合仍只能包含 Plain Vanilla Hamiltonian 源文件。

- [ ] **Step 4：构建并运行旧回归**

```bash
./test/alf_hirsch_binary/scripts/build.sh
./test/alf_hirsch_binary/scripts/test.sh
```

Expected: stock four-valued、binary free/free 和错误 U 检查全部 PASS。

- [ ] **Step 5：提交**

```bash
git add test/alf_hirsch_binary/patches/free-uhf-boundary.patch \
  test/alf_hirsch_binary/scripts/build.sh \
  test/alf_hirsch_binary/tests/test_binary_hirsch.py
git commit -m "feat: add ALF free-UHF projector boundaries"
```

---

## Task 4：从 ALF free 轨道生成唯一的 UHF 资产

**Files**

- Modify: `test/cpmc_path_audit/src/main.cpp`
- Modify: `test/cpmc_path_audit/README.md`
- Create: `test/pqmc_cp_bridge/scripts/bootstrap_trials.py`
- Create: `test/pqmc_cp_bridge/tests/test_real_alf_boundary.py`

**New C++ command**

```text
cpmc_audit export-uhf \
  --lx 4 --ly 4 --t 1 --u 4 --dt 0.05 --n-up 8 --n-down 8 \
  --initial-up trial_I_up.dat \
  --initial-down trial_I_down.dat \
  --site-map site_map.dat \
  --output-dir assets/trials
```

该命令输出 `trial_T_up.dat`、`trial_T_down.dat` 和 `uhf_metadata.json`；
`bootstrap_trials.py` 再用 Python
`hashlib` 计算四个矩阵和 site map 的 SHA-256，合并为最终
`trial_manifest.json`。不为写 hash 在 C++ 中另行实现密码学库。

manifest 至少包含：

```json
{
  "format_version": 1,
  "site_order": "ALF exported; explicit site_map.dat",
  "trial_right": "ALF stock free, Delta=0.01",
  "trial_left": "collinear Neel UHF",
  "uhf_u": 4.0,
  "mixing": 0.2,
  "tolerance": 1e-12,
  "scf_iterations": 0,
  "scf_residual": 0.0,
  "orthonormality_residuals": {},
  "particle_hole_residuals": {},
  "spin_overlap_determinants": {},
  "sha256": {}
}
```

- [ ] **Step 1：写 CLI 失败测试**

测试 command 的必需参数、错误 site map、零 overlap/rank deficiency 和
metadata 字段；负 overlap 应由规定的列翻转修正，而不是拒绝。
再加 4×4 实例测试，要求：

- UHF SCF 收敛；
- 每 spin 粒子数为 8；
- Néel staggered magnetization 为正；
- `det(TσᵀIσ)>1e-10`；
- 四个轨道正交残差 `<1e-11`；
- free 和 UHF 的粒子—空穴残差 `<1e-10`。

- [ ] **Step 2：实现 `export-uhf`**

必须读取 ALF 导出的 `I`；不得从均匀 hopping 或另一个弱二聚化矩阵重新
生成 free occupied subspace。先根据 `site_map.dat` 把 `I` 从 ALF row order
排列到 C++ row-major order，求解和定规后再逆排列回 ALF order；不得假定两者
天然相同。写文件前固定每个 spin 的 overlap sign。

- [ ] **Step 3：实现 bootstrap**

`bootstrap_trials.py`：

1. 在临时 run 目录准备 rank-1、`NSweep=2、NBin=1` 的 free/free 输入；
2. 设置 `Export_trial_orbitals=.true.`；
3. 运行冻结的 ALF executable；
4. 把 ALF 导出文件复制到 `assets/trials`；
5. 调用 `cpmc_audit export-uhf`；
6. 再准备 mode 1 smoke，复制 `T` 文件并运行；
7. 解析 `info`，确认两个 flavor 显式计算和 mean sign 非负；
8. 原子写入最终 manifest。

若 `assets/trials` 已存在，只有全部 SHA-256 与 manifest 匹配才允许复用；
否则停止，不静默覆盖。

- [ ] **Step 4：运行 bootstrap 和真实 mixed smoke**

```bash
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
make -C test/cpmc_path_audit all
/usr/bin/python3 test/pqmc_cp_bridge/scripts/bootstrap_trials.py
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_real_alf_boundary.py
```

Expected: PASS，并生成七个 trial asset。

- [ ] **Step 5：提交**

```bash
git add test/cpmc_path_audit/src/main.cpp \
  test/cpmc_path_audit/README.md \
  test/pqmc_cp_bridge/scripts/bootstrap_trials.py \
  test/pqmc_cp_bridge/tests/test_real_alf_boundary.py
git commit -m "feat: bootstrap shared free and UHF trials"
```

---

## Task 5：实现参数化、不可覆盖的六链批次运行器

**Files**

- Create: `test/pqmc_cp_bridge/scripts/prepare_alf_chain.py`
- Create: `test/pqmc_cp_bridge/scripts/run_alf_batch.py`
- Create: `test/pqmc_cp_bridge/tests/test_prepare_alf_chain.py`

**Interfaces**

```python
def make_parameters(*, theta: int, nbin: int, nsweep: int,
                    boundary: str) -> str
def deterministic_seed(master_seed: int, theta: int,
                       batch: int, chain: int) -> int
def prepare_batch(root: Path, ..., chains: int = 6) -> dict
```

CLI:

```text
run_alf_batch.py
  --ensemble TI|II
  --theta 10
  --batch 0
  --nbin 7
  --nsweep 2000
  --run-root test/pqmc_cp_bridge/runs/alf_projection
  --master-seed 900090
  --executable test/alf_hirsch_binary/run/binary/bin/ALF.binary.out
```

**Run directory**

```text
runs/alf_projection/TI/theta_010/batch_000/
├── batch_manifest.json
├── batch_state.json
└── chain_0 ... chain_5/
```

- [ ] **Step 1：写失败的输入测试**

覆盖：

- Θ 到 Ltrot 的六个映射；
- `NBin=7、NSweep=2000、Beta=1、Dtau=0.05`；
- TI 设置 mixed mode，II 设置 free/free；
- 六个 seed 在所有 Θ/batch/chain 组合中唯一、正且可由相同 master seed 重现；
- 目标目录含任何 ALF raw output 时拒绝覆盖；
- TI 每条链复制并验证 `trial_T_up/down.dat` hash。

- [ ] **Step 2：实现准备器**

不修改 `test/alf_hirsch_binary/scripts/prepare_inputs.py` 的固定基线行为；
新桥接运行完全由本任务的参数化脚本管理。

- [ ] **Step 3：实现并发运行器**

用 `subprocess.Popen` 启动六个：

```text
mpirun -np 1 ALF.binary.out
```

环境固定：

```text
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1
I_MPI_PIN=1
```

优先使用物理 CPU `0,2,4,6,8,10`；若机器可用 CPU 集不包含这些编号，
从当前 affinity 中选六个不同 CPU 并记录，禁止假定。

每 20 秒打印并 flush：

```text
theta=10 batch=0 complete_bins=17/42 live_chains=6 wall=...
```

每条链完成后立即记录 return code、wall time、binary hash、parameter hash
和完整 bin 数。六条都成功才原子地把 `batch_state.json` 标记为 complete。

- [ ] **Step 4：用 mock executable 测试恢复和失败传播**

测试部分链失败、部分链提前结束、重复启动 complete batch 和中断后 resume。
complete batch 必须只读复用；incomplete batch 不得把残缺 bin 混入统计。

- [ ] **Step 5：运行测试并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_prepare_alf_chain.py
```

Expected: PASS.

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/prepare_alf_chain.py \
  test/pqmc_cp_bridge/scripts/run_alf_batch.py \
  test/pqmc_cp_bridge/tests/test_prepare_alf_chain.py
git commit -m "feat: add resumable six-chain ALF batches"
```

---

## Task 6：实现 chain-aware 能量估计和完整性门槛

**Files**

- Create: `test/pqmc_cp_bridge/scripts/alf_statistics.py`
- Create: `test/pqmc_cp_bridge/tests/test_alf_statistics.py`

**Interfaces**

```python
@dataclass(frozen=True)
class EnergyEstimate:
    mean: float
    sigma_bin: float
    sigma_replica: float
    sigma: float
    retained_bins: int
    replicas: int
    loo_min: float
    loo_max: float
    mean_sign: float
    negative_sign_bins: int
    precision_ready: bool
    hard_failure: str | None

def parse_replica(run_dir: Path, expected: dict) -> ReplicaData
def estimate_energy(replicas: Sequence[ReplicaData]) -> EnergyEstimate
def choose_additional_nbin(estimate: EnergyEstimate,
                           chains: int = 6,
                           target: float = 0.005) -> int
```

**误差定义**

1. 每个独立 chain-run 丢弃第一个 bin；
2. 总能量使用 ALF ratio estimator `Σ Ener_scal / Σ sign`；
3. 在每个 replica 内分别以 block size `1,2,4,...` 分块，不跨 replica；
4. 只保留总 block 数至少 12 且每个参与 replica 至少有 2 个 block 的层级；
5. `sigma_bin` 取所有合法层级 delete-one-block jackknife error 的最大值；
6. 同一 chain slot 在不同 batch 的 retained segment 合并为一个 replica，
   但 blocking 不跨 segment 边界；以六个 replica 的 numerator/denominator
   总和做 delete-one-replica jackknife，得到 `sigma_replica`；
7. 扫描停止使用：

```text
sigma = max(sigma_bin, sigma_replica)
```

不得只报告 pooled-bin error。

**完整性门槛**

```text
sigma ≤ 0.005
all observables finite
E = K + V within 1e-10 for every bin
particle number = 16 within 1e-10
negative sign bins = 0
mean sign ≥ 0.999999
max Green precision ≤ min(1e-8, 0.01 sigma)
max |E_leave_one_replica − E| ≤ 3 sigma
all six chains in every batch use distinct seeds
```

真实负 sign、轨道 hash 不一致、层数错误、NaN 或能量 convention 错误属于
`hard_failure`，立即停止整个扫描。统计不足或 leave-one-replica 不稳定只要求
追加当前 Θ 的统计。

- [ ] **Step 1：写解析和误差失败测试**

用合成 ALF 文件覆盖：

- unit sign 下 ratio mean；
- 人为相关数据使 blocked error 大于 naive pooled error；
- chain offset 使 replica error 成为最终 `sigma`；
- 丢弃每个 replica 的第一个 bin；
- 一个负 sign 触发 hard failure；
- `E≠K+V`、Ltrot 错、Theta 错、seed 重复均被拒绝；
- 输入顺序变化不改变结果。

- [ ] **Step 2：实现纯函数统计内核**

所有统计函数不启动 ALF、不写生产目录，便于确定性测试。JSON 浮点输出使用
17 位有效数字。

- [ ] **Step 3：定义追加规模**

每次追加一个新的六链独立 batch。设当前总 retained bins 为 `N`：

```text
growth = clip((sigma/0.005)^2 − 1, 0.5, 3.0)
additional_retained_per_chain = max(6, ceil(N growth / 6))
next_NBin = 1 + additional_retained_per_chain
```

第一项 `1` 是新 chain 的 equilibration bin。此公式只决定下一批工作量；
停止仍只由实测 `sigma` 决定，不设总 bin 上限。

- [ ] **Step 4：运行测试并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_alf_statistics.py
```

Expected: PASS.

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/alf_statistics.py \
  test/pqmc_cp_bridge/tests/test_alf_statistics.py
git commit -m "feat: add chain-aware ALF energy statistics"
```

---

## Task 7：实现 Θ 扫描状态机

**Files**

- Create: `test/pqmc_cp_bridge/scripts/calibrate_projection.py`
- Create: `test/pqmc_cp_bridge/tests/test_calibrate_projection.py`

**State files**

```text
results/theta_scan.json
results/theta_scan.csv
results/selected_projection.json
```

`selected_projection.json` 的 schema：

```json
{
  "schema_version": 1,
  "ensemble_used_for_selection": "TI",
  "theta_star": 10,
  "ltrot_star": 420,
  "nfield_star": 6720,
  "dt": 0.05,
  "beta": 1.0,
  "sigma_target": 0.005,
  "energy_target": -13.62192,
  "energy_tolerance": 0.005,
  "status": "target_reached",
  "ti_estimate": {},
  "ii_confirmation": null,
  "trial_manifest_sha256": "",
  "alf_binary_sha256": "",
  "completed_at": ""
}
```

- [ ] **Step 1：写 mock runner 的状态机测试**

至少覆盖：

1. Θ=10 第一批 sigma 大，追加后 sigma 达标且 energy 通过，选择 10；
2. Θ=10 sigma 达标但能量失败，Θ=12 通过；
3. 所有点能量失败，Θ=20 返回 `max_theta_fallback`；
4. Θ=20 sigma 未达标时继续追加，不允许提前 fallback；
5. hard failure 时停止且不写 selected projection；
6. resume 时跳过 complete batch 和已冻结的 Θ；
7. 在 sigma 达标前，日志不打印 energy 值，状态机也不调用 `energy_ok`。

- [ ] **Step 2：实现 TI 选择循环**

伪代码必须直接对应：

```python
for theta in theta_candidates():
    ensure_first_batch(theta, nbin=7, nsweep=2000)
    while True:
        estimate = analyze_all_complete_batches(theta)
        if estimate.hard_failure:
            abort()
        if estimate.precision_ready:
            break
        run_additional_batch(theta, choose_additional_nbin(estimate))

    reveal_and_record_energy(theta, estimate)
    if energy_ok(estimate.mean):
        select(theta, "target_reached")
        break
else:
    select(20, "max_theta_fallback")
```

每完成一个 batch 或 Θ 都原子更新状态，允许 Codex/用户中断后从同一目录
继续。

- [ ] **Step 3：运行测试并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_calibrate_projection.py
```

Expected: PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/calibrate_projection.py \
  test/pqmc_cp_bridge/tests/test_calibrate_projection.py
git commit -m "feat: add adaptive projection calibration"
```

---

## Task 8：在 Θ* 处完成独立 free/free 确认

**Files**

- Modify: `test/pqmc_cp_bridge/scripts/calibrate_projection.py`
- Modify: `test/pqmc_cp_bridge/tests/test_calibrate_projection.py`

**规则**

TI 选出 Θ* 后，II 也必须在同一个 Θ*、Ltrot* 下运行六链批次，并独立追加
统计直到 `σ_E,II≤0.005`。随后：

- 若 II 满足精确能量窗口，把结果写入 `ii_confirmation`；
- 若 II 不满足，仍保留 Θ*，但把整体状态改为
  `reference_confirmation_failed`；
- 该状态不阻止后续技术性 replay，但禁止把后续能量差归因于 CP 遍历性。

- [ ] **Step 1：增加 II 确认失败测试**

覆盖 II 误差追加、II 能量失败、II hard failure 和 resume。

- [ ] **Step 2：实现 II 路径**

II 使用同一个通用 batch runner 和统计器，只把 boundary mode 改成 free/free。
不得复用旧 `test/alf_hirsch_binary/results` 的 Θ=10 数据作为正式确认，因为
旧数据的误差为约 0.00935，大于当前门槛。

- [ ] **Step 3：运行状态机测试并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_calibrate_projection.py
```

Expected: PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/calibrate_projection.py \
  test/pqmc_cp_bridge/tests/test_calibrate_projection.py
git commit -m "feat: confirm selected projection with free boundaries"
```

---

## Task 9：端到端 smoke、数值等价回归和运行文档

**Files**

- Create: `test/pqmc_cp_bridge/scripts/test.sh`
- Create: `test/pqmc_cp_bridge/README.md`
- Modify: `test/pqmc_cp_bridge/tests/test_real_alf_boundary.py`

- [ ] **Step 1：加入 free/free 重构等价测试**

不依赖两次随机 MC 恰好走同一路径。读取 ALF 导出的 free `I`，对若干固定的
2×2 和 4×4 binary path 用独立 Python 直接乘矩阵，比较：

```text
显式计算 up/down 两个 determinant 与 Green function
只计算 down、再使用 ALF 粒子—空穴公式重构 up
```

比较总 weight、两个 spin Green function、Ekin、Epot 和 Etotal，容差
`1e-10`。这验证 stock single-flavor reconstruction 和 mixed 模式显式双
flavor 所使用的 convention 等价，而不引入 RNG 分支漂移。

- [ ] **Step 2：加入 2×2 direct matrix 边界测试**

固定一个短二值 field path。C++ evaluator 和独立 Python/NumPy 直接乘积都
读取 ALF 导出的 `I`、同一 `T` 和 `site_map.dat`，分别计算：

```text
det(T↑ᵀ B↑ I↑) det(T↓ᵀ B↓ I↓)
```

两套实现的 signed-log residual 必须 `<1e-10`。测试还要从 ALF patch 的
`Hirsch lambda` 和 up/down `g` 约定构造 HS 矩阵；反转 time order 或
spin-HS 符号后结果必须明显不等，避免错误实现“碰巧通过”。

- [ ] **Step 3：统一测试入口**

`scripts/test.sh` 顺序运行：

```text
bridge Python unit tests
cpmc_path_audit C++ tests
ALF binary-Hirsch regressions
trial bootstrap validation
real free/UHF smoke
```

- [ ] **Step 4：写 README**

README 只提供：

- 固定模型和左右边界；
- build/test/bootstrap 命令；
- calibration/resume 命令；
- 输出文件解释；
- `selected_projection.json` 如何被第二、三阶段消费；
- 本地六核运行的预计时间和停止方式。

- [ ] **Step 5：运行全部测试并提交**

```bash
./test/pqmc_cp_bridge/scripts/test.sh
```

Expected: PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/test.sh \
  test/pqmc_cp_bridge/README.md \
  test/pqmc_cp_bridge/tests/test_real_alf_boundary.py
git commit -m "test: verify ALF mixed-boundary calibration"
```

---

## Task 10：执行正式 TI 扫描和 II 确认

本任务是长计算。当前没有
`skills/using-slurm/profiles/active.toml`，按已确认的本地偏离执行六个并发
单线程 chain；不同时运行多个 Θ。

- [ ] **Step 1：记录运行前资源和版本**

```bash
git status --short
lscpu
free -h
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
ifort --version | head -1
icpx --version | head -1
mpirun --version | head -1
```

写入 `results/provenance.json`，并记录：

- ALF upstream commit；
- 两个 patch SHA-256；
- ALF/C++ executable SHA-256；
- trial manifest SHA-256；
- CPU affinity；
- `local-compute deviation`。

- [ ] **Step 2：构建、测试和 bootstrap**

```bash
./test/alf_hirsch_binary/scripts/build.sh
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
make -C test/cpmc_path_audit all
./test/pqmc_cp_bridge/scripts/test.sh
/usr/bin/python3 test/pqmc_cp_bridge/scripts/bootstrap_trials.py
```

Expected: 全部 PASS，trial hash 固定。

- [ ] **Step 3：启动可恢复扫描**

```bash
/usr/bin/python3 -u \
  test/pqmc_cp_bridge/scripts/calibrate_projection.py \
  --run-root test/pqmc_cp_bridge/runs/alf_projection \
  --results-root test/pqmc_cp_bridge/results \
  --master-seed 900090
```

预期最低 wall time：

- 如果 Θ=10 第一轮扩充后通过：约 25–35 分钟；
- 如果扫描到 Θ=20：最低约 3.5 小时；
- replica-aware 误差若较大，追加批次会继续增加时间。

运行时每 20 秒查看进度，每个 batch 结束立即检查：

- return code；
- 完整 bin 数；
- mean sign；
- Green precision；
- 当前 `sigma_bin、sigma_replica、sigma`。

在 `sigma≤0.005` 前不报告或据能量值决定下一步。

- [ ] **Step 4：验证最终选择文件**

```bash
/usr/bin/python3 - <<'PY'
import json
from pathlib import Path
p = Path("test/pqmc_cp_bridge/results/selected_projection.json")
d = json.loads(p.read_text())
assert d["theta_star"] in [10, 12, 14, 16, 18, 20]
assert d["ltrot_star"] == int((2*d["theta_star"] + d["beta"]) / d["dt"])
assert d["nfield_star"] == 16*d["ltrot_star"]
assert d["ti_estimate"]["sigma"] <= 0.005
assert d["ii_confirmation"]["sigma"] <= 0.005
print(d["status"], d["theta_star"], d["ltrot_star"])
PY
```

- [ ] **Step 5：提交小型结果，不提交 raw run**

```bash
git add test/pqmc_cp_bridge/results/theta_scan.csv \
  test/pqmc_cp_bridge/results/theta_scan.json \
  test/pqmc_cp_bridge/results/theta_scan.png \
  test/pqmc_cp_bridge/results/selected_projection.json \
  test/pqmc_cp_bridge/results/calibration_report.md \
  test/pqmc_cp_bridge/results/provenance.json
git commit -m "results: calibrate common PQMC projection length"
```

---

## Task 11：第一阶段验收

- [ ] 所有 Python、C++、ALF 测试通过；
- [ ] trial free 轨道确实由 ALF 导出；
- [ ] UHF 只生成一次，并被 ALF/C++ 后续共同消费；
- [ ] 两个 spin 的 overlap determinant 分别为正；
- [ ] mixed 模式 `N_FL_eff=2`，未使用单-flavor reconstruction；
- [ ] 每个 Θ 的值判断发生在 `σ_E≤0.005` 之后；
- [ ] Θ=20 也没有统计量机械上限；
- [ ] TI 选出的 Θ* 和 II 确认使用相同 Ltrot*；
- [ ] `selected_projection.json` 包含 Θ*、Ltrot*、Nfield*、状态和全部 hash；
- [ ] raw runs 保留在本地，未被覆盖或错误提交；
- [ ] 若状态不是 `target_reached`，报告明确限制后续因果归因。

最终交付时只报告：

1. `Θ*、Ltrot*、E_TI±σ_TI、E_II±σ_II、status`；
2. 一张 Θ 扫描图；
3. `selected_projection.json` 和 calibration report 的路径；
4. 第二阶段应读取的唯一 contract 路径。
