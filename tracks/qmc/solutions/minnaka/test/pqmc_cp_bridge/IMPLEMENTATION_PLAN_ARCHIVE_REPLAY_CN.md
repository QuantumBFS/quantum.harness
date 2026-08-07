# ALF 构型档案与 C++ 稳定重放实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在第一阶段冻结的共同投影长度上，从 ALF free/free 与 free/UHF 链保存稀疏、可校验的完整辅助场路径，并用 oneMKL/C++ 稳定重放每条路径，输出物理权重、CP proposal、节点、prefix 瓶颈和能量诊断。

**Architecture:** ALF 增加一个独立 archive 模块；每次导出先冻结当前辅助场，再从左右边界只读重建中央和端点 estimator，然后写带 CRC32 的 append-only 二进制记录。C++ 将现有单一 trial 的 `PathEvaluator` 拆成 initial determinant、UHF guide 和双边物理 estimator 三个角色，以 signed-log、QR 尺度和线性求解完成最长 820 层路径的流式 replay。Python 只负责 pilot 自相关、均匀抽样、训练/held-out 分割和风险参考曲线，不重新计算矩阵物理量。

**Tech Stack:** ALF 2.4 Fortran、Intel MPI、C++17、Intel `icpx`、oneMKL BLAS/LAPACK、Python 3、NumPy/Matplotlib、`unittest` 与现有 C++ 测试框架。

## 2026-07-30 生产执行修订

下列生产参数替代本文后面最初按六链、每 ensemble 10000 条和抽取 3000
条 replay 的工作量估计；文件格式、物理定义和验证门槛不变。

- 每个 ensemble 使用 128 条独立单线程链；
- 每链热化 2000 sweep，归档 stride 为 pilot 测得的 239 sweep；
- 每链保留 8 条，首批每个 ensemble 共 1024 条；
- 首批 2048 条全部进行 C++ replay；
- TI 的 chain 0–63 只用于冻结风险阈值，64–127 为 held-out；
- 新生产使用
  `sample_id=(ensemble_code<<60)|(chain_id<<49)|local_sequence`，
  其中 `0≤chain_id<256`、`local_sequence<2^52`；
- MATLAB CPMC-Lab 只给出直接 UHF-CP 基准，不执行路径重放。

## Global Constraints

- 强制读取 `test/pqmc_cp_bridge/results/selected_projection.json`；不得重新选择 Θ 或硬编码 420 层。
- 模型固定为 4×4 square、PBC×PBC、t=1、U=4、N↑=N↓=8、Δτ=0.05、实数二值 Hirsch spin HS。
- `status=max_theta_fallback` 时仍执行，但所有输出 metadata 必须携带该状态。
- 右初态只允许使用 ALF 导出的 `I`；UHF guide/左边界只允许使用第一阶段冻结的 `T`。
- ALF online bin energy 只用于链统计，禁止作为 sweep 末态路径的 estimator。
- 字段顺序固定为 physical-time-slice-major、slice 内 site-major；bit 1 表示 +1，bit 0 表示 −1。
- 普通 replay 不安装 Eigen/OpenBLAS；继续使用 oneMKL。
- 所有长乘积均使用 sign+log|value|；禁止把累计 log scale `exp` 回 double。
- 128 条链的原始 archive 分开写、永久保留；任何分析选择都在离线完成。
- 初始 archive 目标为每个 ensemble 1024 条有效记录；首批全部 replay。
- 训练链固定为 chain 0–63；held-out 链固定为 chain 64–127。
- 新生产的 `chain_id` 必须满足 `0≤chain_id<2048`；全局 `sample_id`
  使用 11-bit chain 编码；旧档案的 `sample_id` 继续作为 opaque ID
  向后兼容，
  `(ensemble_code<<60) | (chain_id<<52) | local_sequence`，其中
  `local_sequence` 在单条 append-only archive 内严格递增且小于 `2^52`。
- 不修改或删除第一阶段 calibration raw runs。

---

## 文件结构与责任

```text
test/pqmc_cp_bridge/
├── contracts/
│   ├── archive_format.json
│   ├── field_order.json
│   ├── model.json
│   └── replay_contract.json
├── patches/
│   └── alf-path-archive.patch
├── scripts/
│   ├── archive_contract.py
│   ├── prepare_archive_run.py
│   ├── run_archive_pilot.py
│   ├── estimate_archive_stride.py
│   ├── run_archive_production.py
│   ├── select_replay_samples.py
│   ├── analyze_prefix_risk.py
│   └── verify_archive_replay.py
├── tests/
│   ├── test_archive_contract.py
│   ├── test_archive_selection.py
│   ├── test_prefix_risk.py
│   └── test_real_archive.py
├── archives/
│   ├── II/
│   └── TI/
├── replay/
│   ├── manifests/
│   ├── bulk/
│   ├── prefixes/
│   └── traces/
└── results/
    ├── archive_summary.json
    ├── replay_summary.csv
    ├── replay_validation.json
    ├── prefix_reference.json
    └── strata_contract.json
```

ALF patch 源和 build 逻辑仍放在 `test/alf_hirsch_binary/`；C++ 源仍放在
`test/cpmc_path_audit/`。桥接目录只保存 contract、运行脚本、索引和结果。

---

### Task 1：冻结 archive/replay 输入 contract

**Files:**

- Create: `test/pqmc_cp_bridge/scripts/archive_contract.py`
- Create: `test/pqmc_cp_bridge/tests/test_archive_contract.py`
- Create: `test/pqmc_cp_bridge/contracts/model.json`
- Create: `test/pqmc_cp_bridge/contracts/field_order.json`
- Create: `test/pqmc_cp_bridge/contracts/replay_contract.json`

**Interfaces:**

- Consumes:
  `load_selected_projection(path: Path) -> dict`，
  `trial_manifest.json` 和第一阶段 executable hashes。
- Produces:
  `ArchiveContract`、`ReplayContract`、`validate_contracts(...)` 和三个
  immutable JSON contract。

- [ ] **Step 1：写失败的 gate 测试**

测试必须拒绝：

```python
selected["ltrot_star"] != (2*selected["theta_star"] + beta)/dt
selected["nfield_star"] != 16*selected["ltrot_star"]
trial_manifest hash 不匹配
ALF/C++ site map 不是双射
field spin sign 不是 up:+gamma/down:-gamma
未知 status
```

并验证 `target_reached` 与 `max_theta_fallback` 都可进入本阶段，但后者设置
`strict_ground_state_claim_allowed=False`。

- [ ] **Step 2：运行并确认失败**

Run:

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_archive_contract.py
```

Expected: FAIL，因为模块和 contract 不存在。

- [ ] **Step 3：实现 exact contract**

`field_order.json` 必须明确：

```json
{
  "storage_order": "time_slice_major_then_alf_site",
  "physical_time_direction": "right_boundary_to_left_boundary",
  "alf_slice_to_cp_step": "cp_step = alf_slice - 1",
  "slice_split": "K/2-V-K/2",
  "up_exponent": "+gamma*x",
  "down_exponent": "-gamma*x",
  "plus_one_bit": 1,
  "minus_one_bit": 0,
  "bit_order_within_byte": "least_significant_bit_first",
  "byte_order": "little_endian",
  "hs_measure_per_site": 0.5,
  "hs_constant_per_slice": "exp(-dt*U*(N_up+N_down)/2)"
}
```

`replay_contract.json` 还必须由 selected projection 计算并保存：

```text
right_projector_slices = theta_star/dt
measurement_window_slices = beta/dt
left_projector_slices = theta_star/dt
center_slice = right_projector_slices + measurement_window_slices/2
```

`central_*` 在 propagation boundary `center_slice` 上计算单点 two-sided
estimator；它是中央窗口的 checkpoint，不冒充第一阶段 online window
average。`endpoint_*` 使用全部 `Ltrot*` 层。

该方向先作为 candidate contract；Task 4 的两格点/2×2 测试通过后才写
`validated=true`。

- [ ] **Step 4：运行测试并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_archive_contract.py
```

Expected: PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/contracts \
  test/pqmc_cp_bridge/scripts/archive_contract.py \
  test/pqmc_cp_bridge/tests/test_archive_contract.py
git commit -m "test: define PQMC path archive contract"
```

---

### Task 2：定义 append-only archive 二进制格式和双语言读取测试

**Files:**

- Create: `test/pqmc_cp_bridge/contracts/archive_format.json`
- Create: `test/pqmc_cp_bridge/scripts/path_archive.py`
- Modify: `test/pqmc_cp_bridge/tests/test_archive_contract.py`
- Create: `test/cpmc_path_audit/include/archive_reader.hpp`
- Create: `test/cpmc_path_audit/src/archive_reader.cpp`
- Create: `test/cpmc_path_audit/tests/test_archive_reader.cpp`

**Interfaces:**

```python
class ArchiveReader:
    header: ArchiveHeader
    def records(self) -> Iterator[ArchiveRecord]: ...
    def scan(self) -> ArchiveScan: ...
```

```cpp
struct ArchiveHeader;
struct ArchiveRecordView;
class ArchiveReader {
public:
    explicit ArchiveReader(std::string path);
    const ArchiveHeader& header() const noexcept;
    bool read(ArchiveRecordView& record);
};
```

**Binary layout**

Header 固定 256 bytes，小端：

```text
char[8] magic = "QHPATH01"
uint32 version = 1
uint32 endian_marker = 0x01020304
uint32 header_bytes = 256
uint32 record_bytes
uint32 lx, ly, n_up, n_down, ltrot, nsites, nfield, payload_bytes
double hopping, interaction, dt, beta, theta
uint8 ensemble_code       # 1=II, 2=TI
uint8 bit_order_code      # 1=LSB first
uint8 time_order_code     # 1=right to left
uint8 reserved
char[64] selected_projection_sha256_hex
char[64] trial_manifest_sha256_hex
reserved zero padding
```

Record 固定长度：

```text
uint64 sample_id
uint32 chain_id
uint32 bin_id
uint64 sweep_id
uint32 ltrot
uint32 nfield
int8 frozen_sign
uint8 endpoint_present
uint16 flags
double central_ekin
double central_epot
double central_etot
double central_npart
int8 endpoint_sign
uint8[7] padding
double endpoint_logabs_d
double endpoint_ekin
double endpoint_epot
double endpoint_etot
uint8[payload_bytes] fields
uint32 crc32
zero padding to 64-byte record boundary
```

`endpoint_sign/endpoint_logabs_d` 表示该 record 所属 ensemble 的完整
`D_LI=p(X) C_HS det(L^T B_tilde(X) I)`，已经包含 `2^−Nfield` 与
构型无关 HS 常数；不得只保存裸 endpoint overlap。`endpoint_present=0`
时这些 endpoint 数值字段写 canonical quiet NaN。

字段名中的 `endpoint` 是二进制格式的历史命名。长路径的
`endpoint_sign/endpoint_logabs_d` 必须在 `center_slice` 用左右两段 UDV
稳定传播后拼接计算，并同时累计左右尺度；禁止用 420 层单边传播后的裸
`U_L†U_R` 作为精度 oracle。`endpoint_ekin/epot/etot` 仍是末端局域能量
诊断，不作为长路径 determinant 验证门槛。TI ensemble 中 ALF 会把
`⟨T|I⟩` 归一为 1；与使用原始轨道的 C++ 比较时，必须用
`trial_manifest.json` 中两个 spin overlap determinant 的对数和恢复该常数。

CRC32 使用 IEEE polynomial `0xEDB88320`，覆盖从 `sample_id` 到 fields
payload 的所有 bytes，不覆盖 CRC 自身和尾部 padding。header 不保存可变
record count；reader 通过文件长度和 CRC 扫描，崩溃后的不完整尾记录必须被
识别而不读入。

- [ ] **Step 1：写 Python golden-byte 测试**

手工构造 Ltrot=2、Nsite=2 的 4-bit path，验证：

- `[-1,+1,+1,-1]` 的 payload byte 为 `0b00000110`；
- header/record size 与 JSON format 一致；
- 单 bit corruption 触发 CRC error；
- 完整记录后附半条记录时，scan 返回 `truncated_tail=True`；
- ensemble、hash、Ltrot 不匹配时拒绝。

- [ ] **Step 2：写 C++ 读取失败测试**

让 C++ reader 读取 Python 生成的 golden archive，并检查所有字段和 bit
解码。实现前应因接口缺失而编译失败。

- [ ] **Step 3：实现 Python writer/reader 与 C++ reader**

Python writer 只用于 golden tests 和修复工具；生产 archive 必须由 ALF
直接写。C++ reader 流式返回 payload view，不一次加载全部 archive。

- [ ] **Step 4：双向运行测试**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_archive_contract.py
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
make -C test/cpmc_path_audit test
```

Expected: Python/C++ 对同一 golden bytes 全部 PASS。

- [ ] **Step 5：提交**

```bash
git add test/pqmc_cp_bridge/contracts/archive_format.json \
  test/pqmc_cp_bridge/scripts/path_archive.py \
  test/pqmc_cp_bridge/tests/test_archive_contract.py \
  test/cpmc_path_audit/include/archive_reader.hpp \
  test/cpmc_path_audit/src/archive_reader.cpp \
  test/cpmc_path_audit/tests/test_archive_reader.cpp
git commit -m "feat: add versioned auxiliary-field archive format"
```

---

### Task 3：在 ALF 中实现冻结 estimator 和 archive writer

**Files:**

- Create: `test/alf_hirsch_binary/patches/alf-path-archive.patch`
- Modify: `test/alf_hirsch_binary/scripts/build.sh`
- Modify through patch:
  `test/alf_hirsch_binary/ALF/Prog/Makefile`
- Create through patch:
  `test/alf_hirsch_binary/ALF/Prog/Path_archive_mod.F90`
- Modify through patch:
  `test/alf_hirsch_binary/ALF/Prog/main.F90`
- Modify through patch:
  `test/alf_hirsch_binary/ALF/Prog/Hamiltonian_main_mod.F90`
- Modify through patch:
  `test/alf_hirsch_binary/ALF/Prog/Hamiltonians/Hamiltonian_Hubbard_Plain_Vanilla_smod.F90`
- Modify: `test/alf_hirsch_binary/tests/test_binary_hirsch.py`

**New QMC namelist inputs**

```fortran
Logical :: Archive_paths = .false.
Integer :: Archive_stride = 0
Integer :: Archive_after_sweep = 0
Integer :: Archive_ensemble = 0      ! 1=II, 2=TI
```

`Archive_paths=.true.` 时要求 rank-per-chain=1、binary Hirsch、Projector、
`Archive_stride>0`，并验证 archive hash sidecar。默认值保持 stock 行为。

**New Hamiltonian callback**

```fortran
procedure, nopass :: Frozen_scalars => Frozen_scalars_base
```

Plain Vanilla override：

```fortran
subroutine Frozen_scalars(GR, Ekin, Epot, Etot, Npart)
```

使用与 `Obser` 完全相同的 `GRC=I−GRᵀ`、bond counting 和原始 Hubbard
`U n↑n↓` convention，但不修改 `Obs_scal`。

**Frozen evaluation algorithm**

在每个完整 forward+backward sweep 结束、下一次 field update 开始前：

1. 当前 `nsigma%f(:,1:Ltrot)` 已冻结；
2. 临时 `udvr` 从 `WF_R` reset，严格沿 stock `Stab_nt/Nwrap` 分段调用只读
   `WRAPUR` 直到 center；禁止把最长 820 层压成一次未稳定传播；
3. 临时 `udvl` 从 `WF_L` reset，沿相同稳定化边界反向分段调用只读
   `WRAPUL` 直到 center；
4. 对显式 flavor 调用 `CGR`，必要时执行 stock reconstruction；
5. `Symm=.true.` 时先用 `Hop_mod_Symm` 转换，再调用 `Frozen_scalars`；
6. 另从 `WF_R` 按相同 `Stab_nt/Nwrap` 分段只读传播到 Ltrot，结合 `WF_L`
   和 UDV scales 计算所属 ensemble 完整 `D_LI` 的 sign+logabs，包括
   `2^−Nfield` 和 HS constant；
7. 用 endpoint Green 调用 `Frozen_scalars`；
8. 验证 chain/sequence 位宽，按全局编码生成 `sample_id`，bit-pack
   `nsigma%i(site,slice)` 并写一条 record；
9. 不改变 `GR、Phase、udvst、Obs_scal` 或 RNG state。

- [ ] **Step 1：写失败的 stock-off 回归**

`Archive_paths=.false.` 时，相同 seed 的 binary free/free smoke 必须与 archive
patch 前的 `Ener_scal、confout_0` byte-identical。

- [ ] **Step 2：写真实 archive smoke 测试**

Ltrot 较短的 2×2 和正式形状的 4×4 smoke 分别检查：

- archive record 数等于满足 `after/stride` 的 sweep 数；
- fields 与同一时刻冻结的 debug `confout` 一致；
- `central_etot=central_ekin+central_epot`；
- particle number 正确；
- TI 使用四个明确的左右 spin blocks；
- 开关 archive 不改变最终 `confout_0`，说明未消耗 RNG；
- 文件中断恢复只追加更大的 local sequence/sample_id，不覆盖旧记录。

- [ ] **Step 3：实现 Fortran CRC32、packing 和 writer**

`Path_archive_mod.F90` 只负责格式、CRC 和写入。不得在该模块复制 Hubbard
能量公式；能量通过 `ham%Frozen_scalars` 获取。

- [ ] **Step 4：实现只读 frozen evaluator**

临时 UDV 对象每次导出后 deallocate。若 frozen 计算改变在线 `GR` 或下一次
更新结果，测试必须失败。

- [ ] **Step 5：更新 patch application**

`build.sh` 依次识别：

```text
hirsch-binary.patch
free-uhf-boundary.patch
alf-path-archive.patch
```

最终允许的 dirty files 精确为 patch 涉及的文件集合。新模块必须在 `main.o`
之前编译和链接。

- [ ] **Step 6：构建、测试并提交**

```bash
./test/alf_hirsch_binary/scripts/build.sh
./test/alf_hirsch_binary/scripts/test.sh
```

Expected: stock、mixed-boundary 和 archive tests 全部 PASS。

Commit:

```bash
git add test/alf_hirsch_binary/patches/alf-path-archive.patch \
  test/alf_hirsch_binary/scripts/build.sh \
  test/alf_hirsch_binary/tests/test_binary_hirsch.py
git commit -m "feat: archive frozen ALF auxiliary-field paths"
```

---

### Task 4：验证 ALF time/site/field 方向

**Files:**

- Create: `test/pqmc_cp_bridge/tests/test_real_archive.py`
- Create: `test/pqmc_cp_bridge/scripts/validate_field_order.py`
- Modify: `test/pqmc_cp_bridge/contracts/field_order.json`

**Interfaces:**

- Consumes: 2-site、2×2 fixed `confin_0`，ALF frozen archive，第一阶段轨道。
- Produces:
  `field_order_validation.json` 和带 `validated=true` 的
  `field_order.json`。

- [ ] **Step 1：准备非回文 fixed paths**

至少使用两个 time slice，并选择既不满足 time reversal、也不满足 site
reversal 的 bit pattern。禁止用全 +1、全 −1 或回文路径验证方向。

- [ ] **Step 2：独立直接乘矩阵**

Python/NumPy 分别计算四种候选：

```text
time forward/site forward
time reverse/site forward
time forward/site reverse
time reverse/site reverse
```

每种都使用 `K/2–V–K/2`、up `+gamma*x`、down `−gamma*x`。只有一个候选
必须同时匹配 ALF endpoint signed-log determinant 和 frozen energy，
容差 `1e-10`。

- [ ] **Step 3：验证 4×4 site permutation**

从 `site_map.dat` 逐行验证 ALF coordinate 与 CPMC row-major
`cpp_site=y*Lx+x`；即便当前恰好相同，也保存显式 permutation。

- [ ] **Step 4：运行并冻结 contract**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_real_archive.py
```

Expected: 恰好一个方向 PASS；随后原子写 `validated=true`。

- [ ] **Step 5：提交**

```bash
git add test/pqmc_cp_bridge/tests/test_real_archive.py \
  test/pqmc_cp_bridge/scripts/validate_field_order.py \
  test/pqmc_cp_bridge/contracts/field_order.json
git commit -m "test: validate ALF path time and site ordering"
```

---

### Task 5：实现 archive pilot、自相关和正式 stride

**Files:**

- Create: `test/pqmc_cp_bridge/scripts/prepare_archive_run.py`
- Create: `test/pqmc_cp_bridge/scripts/run_archive_pilot.py`
- Create: `test/pqmc_cp_bridge/scripts/estimate_archive_stride.py`
- Create: `test/pqmc_cp_bridge/tests/test_archive_selection.py`

**Interfaces:**

```python
def integrated_autocorrelation_time(values: Sequence[float]) -> float
def choose_export_stride(tau_values: Mapping[str, float]) -> int
def required_sweeps(target_records: int, stride: int,
                    chains: int, burn_sweeps: int) -> int
```

`integrated_autocorrelation_time` 使用 Geyer initial-positive-sequence：
配对自相关和第一次非正后截断；输出单位为 sweeps，不把 export record index
误当 sweep。

- [ ] **Step 1：写合成 AR(1) 测试**

白噪声 `tau≈0.5`；固定 seed 的 AR(1) 数据在统计容差内接近解析
`0.5+rho/(1-rho)`。`choose_export_stride` 必须严格返回：

```text
max(20, ceil(5*max(tau_values.values())))
```

- [ ] **Step 2：实现 pilot runner**

对 II、TI 各运行六链：

```text
Archive_stride=5 sweeps
Archive_after_sweep=2000
NSweep=4000
NBin=1
```

每链得到约 400 个 pilot records。运行仍从第一阶段相同 `I/T` 和 Θ* 开始。

- [ ] **Step 3：声明 replay score 的硬依赖**

pilot stride 最终还需要 `logQ_final、prefix barrier proxy、near-node count`。
本任务实现的 `estimate_archive_stride.py` 在这些列缺失时必须 hard stop，
不能先用能量选一个临时正式 stride。Task 9 完成后，Task 12 用 bulk replay
生成 `archive_pilot_scores.csv`，再一次性从以下序列选最大 τ：

```text
frozen Etotal
sum x
sum (-1)^(x+y) x
logQ_final
minimum detrended prefix logQ
near-node count
```

- [ ] **Step 4：计算 production 工作量**

目标为每个 ensemble 至少 10000 records。六链使用相同 stride 时：

```text
production_sweeps_per_chain =
    burn_sweeps + stride*ceil(10000/6)
```

`burn_sweeps=2000`，实际保存数允许略高于 10000。

- [ ] **Step 5：运行单元测试并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_archive_selection.py
```

Expected: PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/prepare_archive_run.py \
  test/pqmc_cp_bridge/scripts/run_archive_pilot.py \
  test/pqmc_cp_bridge/scripts/estimate_archive_stride.py \
  test/pqmc_cp_bridge/tests/test_archive_selection.py
git commit -m "feat: choose decorrelated ALF archive stride"
```

---

### Task 6：为 C++ 增加 signed-log、LU solve 和稳定 overlap

**Files:**

- Create: `test/cpmc_path_audit/include/signed_log.hpp`
- Create: `test/cpmc_path_audit/src/signed_log.cpp`
- Modify: `test/cpmc_path_audit/include/dense_matrix.hpp`
- Modify: `test/cpmc_path_audit/src/dense_matrix.cpp`
- Modify: `test/cpmc_path_audit/include/walker.hpp`
- Modify: `test/cpmc_path_audit/src/walker.cpp`
- Create: `test/cpmc_path_audit/tests/test_signed_log.cpp`
- Modify: `test/cpmc_path_audit/tests/test_dense_matrix.cpp`

**Interfaces:**

```cpp
struct SignedLog {
    int sign;
    double log_abs;
};
SignedLog signed_log_product(SignedLog a, SignedLog b);
SignedLog signed_log_determinant(const Matrix& a);
double logaddexp(double a, double b);
Matrix solve(const Matrix& a, const Matrix& b);
SignedLog Walker::overlap_signed_log(const TrialState& bra) const;
double Walker::overlap_ratio(const TrialState& bra,
                             const Walker& before) const;
```

- [ ] **Step 1：写 overflow/underflow 失败测试**

构造 QR scales `exp(±1000)` 的等价 walker；旧 `Walker::overlap()` 必须出现
非有限或下溢，新 API 必须返回有限 `log_abs` 和正确 sign。

- [ ] **Step 2：写 solve 测试**

验证 `A*solve(A,B)=B`，singular matrix 报错；在 production local energy
路径中禁止调用 `inverse()`。

- [ ] **Step 3：实现 signed-log determinant 和 ratio**

determinant 用 LU pivot sign 与 `Σlog|U_ii|`；overlap ratio 在相邻归一化
walker 的 signed-log 中相减，不重构绝对 overlap。

- [ ] **Step 4：运行全套 C++ 测试**

```bash
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
make -C test/cpmc_path_audit test
```

Expected: 全部 PASS，无现有接口静默改变。

- [ ] **Step 5：提交**

```bash
git add test/cpmc_path_audit/include/signed_log.hpp \
  test/cpmc_path_audit/src/signed_log.cpp \
  test/cpmc_path_audit/include/dense_matrix.hpp \
  test/cpmc_path_audit/src/dense_matrix.cpp \
  test/cpmc_path_audit/include/walker.hpp \
  test/cpmc_path_audit/src/walker.cpp \
  test/cpmc_path_audit/tests/test_signed_log.cpp \
  test/cpmc_path_audit/tests/test_dense_matrix.cpp
git commit -m "feat: stabilize long-path determinant arithmetic"
```

---

### Task 7：分离 initial determinant 与 UHF guide

**Files:**

- Modify: `test/cpmc_path_audit/include/path_evaluator.hpp`
- Modify: `test/cpmc_path_audit/src/path_evaluator.cpp`
- Modify: `test/cpmc_path_audit/include/path_diagnostics.hpp`
- Modify: `test/cpmc_path_audit/src/path_diagnostics.cpp`
- Modify: `test/cpmc_path_audit/tests/test_path_evaluator.cpp`
- Modify: `test/cpmc_path_audit/tests/test_batch_replay.cpp`

**New constructor**

```cpp
PathEvaluator(HubbardModel model,
              TrialState initial_state,
              TrialState guide_trial,
              std::vector<std::size_t> site_order,
              ProposalKind proposal,
              std::size_t stabilization_interval);
```

`initial_state()` 必须建立 `Walker::from_trial(initial_state_)`；所有 overlap
ratio、constraint 和 local mixed energy 使用 `guide_trial_`。

**Step kinds**

```cpp
enum class StepKind { PreHalfK, Site, PostHalfK, JointSlice };
enum class RejectionKind { None, PreHalfK, Site, PostHalfK };
```

- [ ] **Step 1：写角色分离失败测试**

用不同的 `I` 与 `T`：

- initial walker 与 I 完全相同；
- `O0=det(T↑ᵀI↑)det(T↓ᵀI↓)`；
- 把 guide 换成 spin-flipped UHF 会改变 proposal，但不改变直接物理
  `D_II`；
- pre/post halfK rejection 分别可被构造并准确标记。

- [ ] **Step 2：重构 PathSummary**

至少包含：

```cpp
bool alive;
RejectionKind first_rejection_kind;
std::size_t first_rejection_slice;
std::size_t first_rejection_site;
double log_q_prop;
double log_w_ratio;
double min_selected_q;
double min_halfk_ratio;
```

一旦 rejected：

- `alive=false`；
- `log_q_prop=-inf`；
- CP weight 字段不再更新；
- walker 仍按强制字段无约束传播到末端。

- [ ] **Step 3：保留旧 2×2 行为**

所有旧调用改成 `initial=guide=trial`；旧 enumeration 的 summed-path identity
保持原容差。

- [ ] **Step 4：运行并提交**

```bash
make -C test/cpmc_path_audit test
```

Expected: PASS。

Commit:

```bash
git add test/cpmc_path_audit/include/path_evaluator.hpp \
  test/cpmc_path_audit/src/path_evaluator.cpp \
  test/cpmc_path_audit/include/path_diagnostics.hpp \
  test/cpmc_path_audit/src/path_diagnostics.cpp \
  test/cpmc_path_audit/tests/test_path_evaluator.cpp \
  test/cpmc_path_audit/tests/test_batch_replay.cpp
git commit -m "refactor: separate AFQMC initial and guide states"
```

---

### Task 8：实现 D_II、D_TI、双边能量和绝对权重恒等式

**Files:**

- Create: `test/cpmc_path_audit/include/physical_path.hpp`
- Create: `test/cpmc_path_audit/src/physical_path.cpp`
- Create: `test/cpmc_path_audit/tests/test_physical_path.cpp`

**Interfaces:**

```cpp
struct LocalEnergy {
    double kinetic;
    double interaction;
    double total;
    double particle_number;
};

struct PhysicalPathResult {
    SignedLog d_ii;
    SignedLog d_ti;
    SignedLog endpoint_overlap_ii;
    SignedLog endpoint_overlap_ti;
    LocalEnergy central_ii;
    LocalEnergy central_ti;
    LocalEnergy endpoint_i;
    LocalEnergy endpoint_t;
};

PhysicalPathResult evaluate_physical_path(
    const HubbardModel& model,
    const TrialState& initial,
    const TrialState& guide,
    FieldView fields,
    std::size_t ltrot,
    std::size_t center_slice,
    std::size_t stabilization_interval);
```

C++17 接口固定使用以下轻量 view，不保留第二套 pointer/count 重载：

```cpp
FieldView{const std::uint8_t* packed, std::size_t nfield}
```

**Weight convention**

```text
tau = Ltrot*dt
log C_HS = −tau*U*(N_up+N_down)/2
log p(X) = −Nfield*log(2)
D_LI = p(X) C_HS det(Lᵀ B_tilde(X) I)
```

CP alive path：

```text
logW_phys = logW_ratio + log C_HS
logW_stock = logW_ratio + S_ref + log C_HS
D_TI = O0 * Q_prop * W_phys
```

其中 `logW_ratio` 已包含每 site 的 `0.5*(r_+^+ + r_-^+)`，因此不得再额外
加入 `log p(X)`。`S_ref=Σ E_ref(l)dt` 由显式 schedule 输入；standalone
validation 使用 constant schedule，物理 `W_phys` 对 schedule 不变。

- [ ] **Step 1：写 M=1/M=2 exact tests**

2-site 和 2×2 使用 Fock oracle 验证：

- direct `D_II、D_TI`；
- central 与 endpoint local energy；
- alive path 的 signed-log identity residual `<1e-10`；
- 改变 constant `E_ref` 只改变 `W_stock、S_ref`，不改变 `W_phys、D`；
- dead path 仍有 finite direct D 和 energy。

- [ ] **Step 2：实现双边稳定传播**

中央 estimator 分别构造右半路径 `B_center...B_1 I` 和左半路径
`LᵀB_L...B_center+1`；每个 stabilization interval 保存 QR determinant
sign/log scale。Green function通过 LU solve，不显式 inverse。

- [ ] **Step 3：实现 Hamiltonian convention tests**

逐路径同时报告 `H_ph` 和 raw Hubbard energy 的常数差，并断言 raw
`E=K+UΣn↑n↓` 与 ALF contract 相同。

- [ ] **Step 4：运行并提交**

```bash
make -C test/cpmc_path_audit test
```

Expected: PASS。

Commit:

```bash
git add test/cpmc_path_audit/include/physical_path.hpp \
  test/cpmc_path_audit/src/physical_path.cpp \
  test/cpmc_path_audit/tests/test_physical_path.cpp
git commit -m "feat: evaluate absolute PQMC path weights"
```

---

### Task 9：实现 bulk archive replay 和 prefix 二进制输出

**Files:**

- Create: `test/cpmc_path_audit/include/archive_replay.hpp`
- Create: `test/cpmc_path_audit/src/archive_replay.cpp`
- Modify: `test/cpmc_path_audit/src/main.cpp`
- Create: `test/cpmc_path_audit/tests/test_archive_replay.cpp`
- Create: `test/pqmc_cp_bridge/scripts/run_bulk_replay.py`

**CLI**

```text
cpmc_audit replay-archive \
  --archive-index archive_index.json \
  --sample-manifest samples.csv \
  --selected-projection selected_projection.json \
  --trial-manifest trial_manifest.json \
  --field-order field_order.json \
  --summary-output replay_summary.csv \
  --prefix-output replay_prefix.qhpfx \
  --eref-mode constant \
  --eref-value <initial mixed energy> \
  --stabilize-every 5
```

`archive_index.json` 列出每个 ensemble 六条链、合计十二个 archive 的绝对
路径、ensemble、chain、header hash 和有效 record 数。CLI 先验证 manifest 中每个全局 `sample_id`
恰好映射到一个 index entry，再打开对应 archive；未知、重复或跨 ensemble
冲突的 ID 均 hard stop。`run_bulk_replay.py` 读取同一 contract，分别调度 II/TI
并合并为一个按 `sample_id` 排序的 summary/prefix 索引。

**Bulk summary columns**

```text
sample_id,ensemble,chain,bin,sweep
sign_d_ii,logabs_d_ii,sign_d_ti,logabs_d_ti
sign_d_alf_ii,logabs_d_alf_ii,sign_d_alf_ti,logabs_d_alf_ti
boundary_cut_log_ratio_ii,boundary_cut_log_ratio_ti
alive,first_rejection_kind,first_rejection_slice,first_rejection_site
log_q_prop,log_w_ratio,log_w_stock,log_w_phys,s_ref
identity_log_residual
min_selected_q,min_selected_q_slice,min_selected_q_site
min_halfk_ratio,min_halfk_slice,min_halfk_kind
min_normalized_overlap,min_sigma,min_principal_angle
central_ii_ekin,central_ii_epot,central_ii_etot
central_ti_ekin,central_ti_epot,central_ti_etot
endpoint_i_etot,endpoint_t_etot
alf_frozen_etot,alf_endpoint_etot
```

**Prefix format**

每条选中路径每个 slice 保存：

```text
sample_id, slice, logQ, logW_ratio, logW_phys,
log_normalized_overlap, sigma_min, min_q_in_slice, alive_after_slice
```

使用固定小端 `QHPFX01` 二进制和 CRC，不写数百万行 CSV。

- [ ] **Step 1：写 golden archive → summary 测试**

用 Task 2 的小 archive 验证 sample filtering、顺序、字段解码和 prefix
record count。

- [ ] **Step 2：实现流式 replay**

一次只持有一条 path 和一个 walker；普通 bulk 不保留逐 site trace。每完成
约 5% 路径打印并 flush，summary 每条追加后可恢复。

- [ ] **Step 3：实现稳定化一致性 mode**

同一 manifest 可用 `--stabilize-every 1,5,10` 运行；comparison 工具要求：

```text
D logabs difference < 1e-9
energy difference < 1e-9
Q/W identity residual < 1e-9
alive/rejection classification identical
```

不一致路径标记 `numerically_ambiguous`，不得进入 support 结论。

- [ ] **Step 4：运行并提交**

```bash
make -C test/cpmc_path_audit test
```

Expected: PASS。

Commit:

```bash
git add test/cpmc_path_audit/include/archive_replay.hpp \
  test/cpmc_path_audit/src/archive_replay.cpp \
  test/cpmc_path_audit/src/main.cpp \
  test/cpmc_path_audit/tests/test_archive_replay.cpp \
  test/pqmc_cp_bridge/scripts/run_bulk_replay.py
git commit -m "feat: stream ALF archives through CPMC replay"
```

---

### Task 10：实现均匀抽样、prefix 去趋势和预注册 strata

**Files:**

- Create: `test/pqmc_cp_bridge/scripts/select_replay_samples.py`
- Create: `test/pqmc_cp_bridge/scripts/analyze_prefix_risk.py`
- Create: `test/pqmc_cp_bridge/tests/test_prefix_risk.py`
- Create: `test/pqmc_cp_bridge/results/strata_contract.json`

**Interfaces:**

```python
def stratified_sample(index, per_chain: int, seed: int) -> list[int]
def prefix_reference(training_prefixes) -> list[float]
def prefix_barrier(logq, reference) -> tuple[float, int]
def assign_static_strata(summary, thresholds) -> dict
```

- [ ] **Step 1：写 selection 失败测试**

每个 ensemble 的每条 chain 精确选择 500 条，即每 ensemble 3000、全体
6000；按 bin/sweep 均匀分位点选择，并用固定 seed 解决并列。不得按能量、
alive 或 replay score 选择。

- [ ] **Step 2：写 barrier 测试**

训练链 0–2 的 alive path 在每个 slice 计算 median `logQ_m`：

```text
d_m = logQ_m - median_train(m)
B_Q = -min_m d_m
```

验证给所有 path 加同一线性长度趋势不会改变 `B_Q`。

- [ ] **Step 3：冻结 static thresholds**

仅用 TI training chains 冻结：

```text
q01 = alive final logQ 的 1st percentile
b99 = alive B_Q 的 99th percentile
n99 = alive near-node count 的 99th percentile
```

每条路径保留四个独立标签：

```text
support = alive/dead/ambiguous
proposal_percentile
prefix_risk_percentile
near_node_percentile
```

另生成互斥的 primary static strata：

```text
dead_support
alive_low_final_q
alive_deep_prefix_not_low_q
alive_regular_static
```

PC fragility 在第三阶段加入，不在这里伪造。

- [ ] **Step 4：运行测试并提交**

```bash
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_prefix_risk.py
```

Expected: PASS。

Commit:

```bash
git add test/pqmc_cp_bridge/scripts/select_replay_samples.py \
  test/pqmc_cp_bridge/scripts/analyze_prefix_risk.py \
  test/pqmc_cp_bridge/tests/test_prefix_risk.py \
  test/pqmc_cp_bridge/results/strata_contract.json
git commit -m "feat: preregister CP path risk strata"
```

---

### Task 11：生成 selected full traces

**Files:**

- Modify: `test/cpmc_path_audit/include/batch_replay.hpp`
- Modify: `test/cpmc_path_audit/src/batch_replay.cpp`
- Modify: `test/cpmc_path_audit/src/main.cpp`
- Create: `test/pqmc_cp_bridge/scripts/select_full_traces.py`
- Modify: `test/cpmc_path_audit/tests/test_batch_replay.cpp`

**Trace selection**

离线、冻结 threshold 后选择：

```text
所有 dead/ambiguous（若数量过大，全部 ambiguous + dead 的均匀最多 500）
proposal 最低 1%
prefix barrier 最高 1%
两者的最高风险 0.1%
每类按 chain/energy 分位匹配的 controls
```

普通路径不写逐 site trace。

- [ ] **Step 1：写 deterministic matched-control 测试**

相同输入、seed 和 threshold 必须产生 byte-identical manifest；control 与
case 的 ensemble、chain split、frozen energy decile 相同。

- [ ] **Step 2：扩展 trace 内容**

每个 pre-halfK/site/post-halfK event 输出：

```text
两个候选 signed overlap ratio
positive-clipped ratios
q_selected 和 weight factor
累积 logQ/logW
normalized overlap
sigma_min/principal angle
Green local density
direct-vs-Sherman-Morrison ratio residual
```

- [ ] **Step 3：运行测试并提交**

```bash
make -C test/cpmc_path_audit test
/usr/bin/python3 -m unittest -v \
  test/pqmc_cp_bridge/tests/test_prefix_risk.py
```

Expected: PASS。

Commit:

```bash
git add test/cpmc_path_audit/include/batch_replay.hpp \
  test/cpmc_path_audit/src/batch_replay.cpp \
  test/cpmc_path_audit/src/main.cpp \
  test/cpmc_path_audit/tests/test_batch_replay.cpp \
  test/pqmc_cp_bridge/scripts/select_full_traces.py
git commit -m "feat: trace selected long-path node events"
```

---

### Task 12：运行 pilot、production archive 和每 ensemble 3000-path replay

**Files:**

- Create: `test/pqmc_cp_bridge/scripts/run_archive_production.py`
- Create: `test/pqmc_cp_bridge/scripts/verify_archive_replay.py`
- Create: `test/pqmc_cp_bridge/results/archive_summary.json`
- Create: `test/pqmc_cp_bridge/results/replay_validation.json`

- [ ] **Step 1：运行全部短测试**

```bash
./test/alf_hirsch_binary/scripts/build.sh
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
make -C test/cpmc_path_audit test
/usr/bin/python3 -m unittest discover -v \
  -s test/pqmc_cp_bridge/tests -p 'test_*.py'
```

Expected: 全部 PASS。

- [ ] **Step 2：执行 II/TI pilot**

```bash
/usr/bin/python3 -u \
  test/pqmc_cp_bridge/scripts/run_archive_pilot.py \
  --selected-projection \
  test/pqmc_cp_bridge/results/selected_projection.json
```

先用 replay CLI 生成 pilot score，再运行：

```bash
/usr/bin/python3 \
  test/pqmc_cp_bridge/scripts/estimate_archive_stride.py
```

输出 II/TI 各自 τ，并取二者所有 observable 的最大值计算共同 stride。

- [ ] **Step 3：执行 production archive**

```bash
/usr/bin/python3 -u \
  test/pqmc_cp_bridge/scripts/run_archive_production.py \
  --target-records-per-ensemble 10000
```

六条链并发、两个 ensemble 顺序运行。每 20 秒 flush 进度；每条 archive
完成后立即 CRC scan。不得在 archive failure 后继续 replay。

- [ ] **Step 4：选择每 ensemble 3000 条并 replay**

```bash
/usr/bin/python3 \
  test/pqmc_cp_bridge/scripts/select_replay_samples.py \
  --per-chain 500

/usr/bin/python3 -u \
  test/pqmc_cp_bridge/scripts/run_bulk_replay.py \
  --archive-index test/pqmc_cp_bridge/archives/archive_index.json \
  --sample-manifest test/pqmc_cp_bridge/replay/manifests/initial_6000.csv \
  --stabilize-every 5
```

manifest 含 II 和 TI 各 3000 条；wrapper 分 ensemble 调度后生成 6000 条
合并 summary。然后对同一 manifest 用 interval 1、10 运行 summary-only
consistency replay。

- [ ] **Step 5：验证 ALF/C++ 同构型**

`verify_archive_replay.py` 必须检查：

```text
ALF endpoint sign/logD 与 C++ 同一 record 的 D_alf,LI residual < 1e-8（逐条硬门槛）
ALF frozen Etotal/C++ central energy residual 的 95% 分位 < 1e-8
alive identity residual 的 99% 分位 < 1e-9
超过逐条能量/identity 门槛的数值病态样本比例 ≤ 5%
stabilize 1/5/10 的 D、energy、classification 一致
所有必需输出 finite；允许 dead path 的 logQ=-inf
```

数值病态路径进入 `numerically_ambiguous_sample_ids` 并自动生成 full trace，
不进入 support 结论；任何 determinant、contract、field-order 或分位数层面的
系统性失败都停止。endpoint mixed energy 只作诊断，不参与稳定化硬门槛。

- [ ] **Step 6：完成 prefix reference 和 strata**

```bash
/usr/bin/python3 \
  test/pqmc_cp_bridge/scripts/analyze_prefix_risk.py
/usr/bin/python3 \
  test/pqmc_cp_bridge/scripts/select_full_traces.py
```

随后运行 selected full traces。

- [ ] **Step 7：提交代码和小型摘要**

raw archives、prefix binaries 和大 CSV 不提交。提交 contract、hash、统计摘要
和小图：

```bash
git add test/pqmc_cp_bridge/scripts/run_archive_production.py \
  test/pqmc_cp_bridge/scripts/verify_archive_replay.py \
  test/pqmc_cp_bridge/results/archive_summary.json \
  test/pqmc_cp_bridge/results/replay_validation.json \
  test/pqmc_cp_bridge/results/prefix_reference.json \
  test/pqmc_cp_bridge/results/strata_contract.json
git commit -m "results: validate ALF paths against CPMC replay"
```

---

## Phase-2 验收门槛

- [ ] `selected_projection.json` 和 trial hashes 全程一致；
- [ ] field time/site/spin order 由非对称短路径唯一验证；
- [ ] II/TI 各至少 10000 条 CRC-valid archive records；
- [ ] archive export 未改变 ALF RNG trajectory；
- [ ] 每个 record 的 estimator 来自冻结构型，而非 online sweep average；
- [ ] 每个 ensemble 初始 replay 样本为六链各 500 条；
- [ ] C++ initial=I、guide=T，角色未混用；
- [ ] D_II、D_TI 包含明确的 2^−Nfield 和 HS 常数；
- [ ] alive path 的绝对 signed-log identity residual 99% 分位 `<1e-9`，
  且逐条超限路径明确标为 numerical ambiguity；
- [ ] dead path 仍完成无约束传播并输出 D 和能量；
- [ ] stabilizer 1/5/10 的物理输出一致；
- [ ] ALF-cut endpoint weight 逐条 residual `<1e-8`；frozen energy 的
  95% 分位 residual `<1e-8`；
- [ ] prefix reference 只用 chains 0–2，chains 3–5 未参与 threshold；
- [ ] full trace 只为预注册风险路径和 matched controls 生成；
- [ ] `max_theta_fallback` 状态在全部结果中保留。

本阶段结束后，第三阶段只允许读取以下四个入口：

```text
results/selected_projection.json
assets/trials/trial_manifest.json
contracts/field_order.json
results/strata_contract.json
```
