# quantumevolve — #232 & #233 Noncommutative Polynomial Optimization

## Team

| | |
|---|---|
| **Team name** | quantumevolve |
| **Members** | 結凪 (UynajGI) |
| **PR** | [QuantumBFS/quantum.harness#181](https://github.com/QuantumBFS/quantum.harness/pull/181) |

## Challenges

| | #232 | #233 |
|---|---|---|
| **Issue** | [#232](https://github.com/QuantumBFS/quantum.harness/issues/232) | [#233](https://github.com/QuantumBFS/quantum.harness/issues/233) |
| **出题人** | Jie Wang (AMSS CAS) & Jin-Guo Liu (HKUST-GZ) | Jie Wang & Jin-Guo Liu |
| **Track** | `polyopt` | `polyopt` + `ed`（验证） |
| **目标** | β(G) 精确闭合证书（upper = lower） | PXP 链谱间隙 SDP 证书 |
| **结果** | ✅ **25 个精确闭合** | ❌ 全部 score=0 |

---

## #232：量子图参数 β(G) 的严格上界证书

### 问题

利用 moment-SOS / SOHS（Sums of Hermitian Squares）层级，对量子图参数 β(G)
（Lovász ψ 函数的非对易推广）给出严格上界证书。
目标图来自 [arXiv:2310.00612](https://arxiv.org/abs/2310.00612) Table 4。

"精确闭合"= 证明 upper = lower = α(G)（独立数）。

### 方法

1. **OmniEvolve 进化**：从 level-1 SOHS 松弛开始，LLM 逐步添加更高次基词收紧上界
2. **人工精确有理化**：对数值最优解做 Fraction 舍入 + LDL 验证
3. **独立验证器**：`verify_dual_certificate.py` 用纯 Fraction 算术重建代数，
   225 条仿射恒等式 + 45 个正 LDL 主元

### 结果

| 指标 | 值 |
|------|-----|
| DB 数 | 3（graph33 + bell×2） |
| 总评估 | 45 |
| Token | ~392K |
| 精确闭合常数 | **25 个** |
| Hope signal | atlas#878 gap=10⁻⁸ |
| 文献上界收紧 | graph33: 2.0013 → 2.0000169 |
| 量子优势发现 | comp(C₇), Clebsch 图（β > α） |

### 进化轨迹（graph33）

```
gen=0  score=0.500  upper=2.00249  ← 种子（degree-2）
gen=2  score=0.875  upper=2.00046  ← LLM 添加三次基词
gen=9  score=0.916  upper=2.00017  ← 最高分（degree-3 最优）
后续手工 degree-4 → upper=2.0000169 → 精确有理化
```

### 精确闭合的 25 个图

利用无限族结构批量闭合：
- Kₙ 完全图：α=1, level-1 即闭合
- Kₘ,ₙ 完全二部图：α=max(m,n), level-1 闭合
- C₂ₖ 偶圈：α=k, level-1 闭合
- 其他高对称图（Petersen, Schläfli, Shrikhande, Rook, Hypercube 等）

### 关键发现

- **AI+人类协同是正确模式**：AI 搜索基词组合 → 人工精确有理化 → AI 验证
- **graph33 精确闭合结构性不可能**：奇异对偶 + 无理最优解（含 √5）
- **Solver 选择**：SCS（ADMM）在奇异问题上正确，Clarabel（内点法）报假阴性

---

## #233：PXP Rydberg 链谱间隙证书

### 问题

为 PXP（Rydberg blockade）链给出 SDP 证书，认证谱间隙 E₁−E₀ 的下界。
H = Σ P_{i-1} σˣ_i P_{i+1}，N=8 时 Fibonacci 约束 Hilbert 空间 dim=55。

官方目标：不使用 ED，用 SDP/LMI 给出 certified_gap / ED_gap 最大比值（1.0 = 完美）。

### 方法

- SDP：max γ s.t. H + M − (E0_lb + γ)·I ≽ 0, M ≽ 0
- 种子 E0_lb：Gershgorin 圆盘定理（E0 ≥ −n，非常松）
- 反作弊：递归调用链分析（AST BFS），禁止一切谱计算原语

### 结果

| 指标 | 值 |
|------|-----|
| DB 数 | 6（v1→v4 + v5/v6） |
| 总评估 | 63+ |
| Token | ~1.29M |
| 反作弊拦截 | 8+（eigvalsh/eigh/eigsh/solve/inv） |
| **合法候选最高分** | **0.0000** |

### 反作弊演进（核心技术贡献）

| 版本 | LLM 作弊方式 | 拦截 |
|------|-------------|------|
| v1→v2 | 直接 `np.linalg.eigvalsh(H)` | ✅ regex 函数体 |
| v3 | 移到辅助函数（inverse iteration） | ❌ 绕过 |
| v4 | — | ✅ AST BFS 递归调用链 + 扩大禁令 |

LLM 表现出的绕过创造力：
1. 直接对角化 → 被拦截
2. 辅助函数隐藏 → 绕过 v2
3. Inverse iteration（用 solve）→ 被 v4 拦截
4. 手写 Lanczos + Sturm bisection → 理论合法但被禁令覆盖

### 失败原因

- **数学层面不可能**：单层 SDP 在 55×55 上无法给出正 certified_gap
  （E0_lb=−8 太松，需要 level-2 NPA ~3025×3025 SDP）
- **合法策略空间极窄**：禁止所有谱计算原语后只剩 cvxpy SDP
- **进化停滞**：Gen 5-6 出现 no-op

---

## Materials

### #232

| 文件 | 说明 |
|------|------|
| `initial_code.py` | CHSH 控制种子（验证管线用） |
| `evaluator.py` | 评估器（exact certificate 为硬门） |
| `verify_candidate.py` | 独立验证器（Q(√2) 精确算术） |
| [graph33/](graph33/) | graph33 进化子项目 |
| [graph33/README.md](graph33/README.md) | graph33 详细说明 |
| [certificates/](certificates/) | **25 个精确闭合证书**（JSON） |
| [c5_oddhole/](c5_oddhole/) | C₅ odd-hole 不等式实验 |
| [atlas669/](atlas669/) | atlas#669 hope signal |
| [batch2_closure.py](batch2_closure.py) | 批量闭合脚本 |
| [extended_closure.py](extended_closure.py) | 扩展闭合脚本 |
| [high_sym_closure.py](high_sym_closure.py) | 高对称图闭合 |
| [结果：graph33 证书](../../results/quantumevolve-graph33/) | 数值+精确证书 |
| [结果：闭合报告](../../results/quantumevolve-232-closures/) | 闭合 report |

### #233

| 文件 | 说明 |
|------|------|
| [rydberg-gap-233/](rydberg-gap-233/) | #233 子项目 |
| [rydberg-gap-233/README.md](rydberg-gap-233/README.md) | 详细说明 |
| [rydberg-gap-233/pxp_ed_gap.py](rydberg-gap-233/pxp_ed_gap.py) | ED 参考（验证用） |
| [rydberg-gap-233/pxp_gap_certificate.py](rydberg-gap-233/pxp_gap_certificate.py) | SDP 证书尝试 |
| [rydberg-gap-233/certified_gaps.json](rydberg-gap-233/certified_gaps.json) | 证书结果 |
| `challenges/omnievolve/examples/rydberg_gap/initial_code.py` | 种子代码 |
| `challenges/omnievolve/examples/rydberg_gap/evaluator.py` | 评估器 |
| `challenges/omnievolve/examples/rydberg_gap/verify_gap.py` | 验证器（v4 反作弊） |

### 报告

| 文件 | 说明 |
|------|------|
| [详细报告 #232](../../../qcs/solutions/quantumevolve/reports/challenge_report_232_polyopt.md) | 逐题分析 |
| [详细报告 #233](../../../qcs/solutions/quantumevolve/reports/challenge_report_233_rydberg_gap.md) | 逐题分析 |
| [完整比赛报告](../../../docs/final_competition_report.md) | 691 行总报告 |

## Run

```bash
cd challenges/omnievolve

# #232 Polyopt (graph33)
.venv/Scripts/omnievolve.exe run examples/polyopt/initial_code.py \
    -e examples.polyopt.evaluator:PolyoptEvaluator \
    -c configs/polyopt.toml --gens 20 --trusted

# #233 Rydberg Gap
.venv/Scripts/omnievolve.exe run examples/rydberg_gap/initial_code.py \
    -e examples.rydberg_gap.evaluator:RydbergGapEvaluator \
    -c configs/rydberg_gap.toml --gens 20 --trusted
```

## Fast verification (local)

```bash
cd tracks/polyopt/solutions/quantumevolve

# CHSH 控制（验证管线工作）
python -m pytest test_verifier.py -q
python verify_candidate.py initial_code.py

# graph33 证书验证
cd graph33
python verify_dual_certificate.py
python test_theta_relaxation.py
```

---

*quantumevolve · 2026-07-30*
# quantumevolve — fast certified Bell-sandwich evolution

This directory registers team **quantumevolve** for
[challenge #232](https://github.com/QuantumBFS/quantum.harness/issues/232).
It deliberately avoids an HPC-first workflow.

The root seed is a seconds-scale CHSH control problem:

- `initial_code.py` supplies an exact SOHS upper certificate and an imperfect
  explicit two-qubit strategy.
- `verify_candidate.py` reduces the noncommutative operator identity exactly
  over Q(√2), independently evaluates the strategy, and exposes the certified
  upper-minus-lower gap.
- `evaluator.py` makes exact certificate validity a hard tier boundary; invalid
  candidates receive diagnostic residuals but cannot outrank a valid sandwich.
- `config.toml` runs a single local candidate per generation with an 8-second
  verification timeout.

The CHSH seed only validates the research machinery.  Challenge progress begins
when the same candidate/verifier contract is instantiated for a catalogued open
state-polynomial Bell constant.  Numerical solver status alone will never count
as success: promoted results require an exact rational SOHS identity and an
explicit matching finite-dimensional strategy.

Evaluator `passed` means a candidate is a valid sandwich and may remain an
evolutionary parent. The separate `closed` metric is the research success gate
(`upper - lower <= 1e-8`).

## Fast verification

From this directory:

```text
python -m pytest test_verifier.py -q
python verify_candidate.py initial_code.py
```

The first evolution target is the explicit strategy angle pair.  It gives a
continuous gap signal while the exact certificate gate proves that the
evaluation pipeline is working before any larger SDP is introduced.

The real campaign now lives in `graph33/`. It targets the unresolved
seven-observable state-polynomial constant from Table 4 of arXiv:2310.00612
and evolves sparse higher-degree moment bases. The CHSH files remain here as a
regression control.
