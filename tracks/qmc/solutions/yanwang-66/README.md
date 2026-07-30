# Dynamic atom reloading for loss-tolerant surface-code memory

## 评委入口（Start here）

> ### [▶ 直接打开自包含 HTML 技术报告（建议首先阅读）](https://htmlpreview.github.io/?https://github.com/Thatht137/quantum.harness/blob/challenge/qmc-atom-reload-surface-code/tracks/qmc/solutions/yanwang-66/report/report.html)
>
> 核心结论、4 张矢量图、独立种子确认、因果配对设计、证据边界与复核命令均集中在此。

[GitHub 可读结果摘要](RESULTS.md) · [HTML 源文件 / 离线下载](report/report.html) · [机器可读汇总](results/summary.json) · [Challenge #66](https://github.com/QuantumBFS/quantum.harness/issues/66)

## Team yanwang

| | |
|---|---|
| **Members** | 王介人、何思成、赵志轩 |
| **Contributor for #66** | 何思成 |
| **Track** | Quantum Monte Carlo / circuit simulation |
| **Challenge** | Addresses #66 — How much does atom reloading help loss-tolerant surface-code memory? |

## Headline result

> **Across 179.2 million discovery cell-shots, active atom-reload policies
> produce 502 provisional helpful and zero harmful FDR classifications among
> 1,960 paired comparisons. A separate-seed confirmation reaches the registered
> precision target in all 32/32 comparisons.**

This is a direct paired test, not a comparison between unrelated simulation
batches. Every reload policy sees the same counter-addressed Pauli,
measurement, loss and reload-outcome streams for each shot. The result therefore
isolates the decision to reload from random trajectory luck.

| Quantity | Verified result |
|---|---:|
| Discovery cell-shots | `179,200,000` |
| Discovery paired comparisons | `1,960` |
| Helpful / no difference / harmful | `502 / 1,458 / 0` |
| Independent confirmation cell-shots | `12,800,000` |
| Confirmation precision | `32 / 32` |
| Precision fraction | `1.0` (required: `0.8`) |
| Accepted engineering volume | `192,000,000 cell-shots` |
| Sealed holdout | `0 / 1`, unspent |

Discovery and confirmation are independent evidence streams; the 192 million
total describes accepted engineering volume and is not pooled as one
statistical sample.

## Scientific interpretation

- **Strong parameter-region signal.** After 20,000-resample paired intervals
  and Benjamini-Hochberg correction over all 1,960 comparisons, 25.6% favor
  active reload and none are classified harmful at the highest verified
  Discovery phase.
- **Independent precision success.** All 32 policy-versus-none comparisons in
  the independent-seed headline slice meet the frozen interval-width target.
- **Conservative final gate.** The formal deadline disposition remains
  `inconclusive_at_deadline`: only 81/2,240 Discovery cells and 4/40
  confirmation cells reached the deliberately high logical-failure count
  target.
- **Claim boundary.** The evidence supports the existence of useful reload
  regions. It does not identify one policy as universally optimal and does not
  turn finite `d=3,5` data into an asymptotic threshold claim.

## What is new

1. **Dynamic loss is part of the decoder model.** Missing sites generate
   round-dependent super-stabilizers and an erasure-aware matching graph; the
   mask is not merely logged beside an unchanged no-loss decoder.
2. **Reload policies are compared causally.** Counter-addressed common random
   numbers preserve external events across `none`, `immediate`, `periodic(R)`
   and `threshold(theta)`.
3. **Recovery is auditable.** Checkpoints, append-only shot ranges, atomic
   publication and SHA-256 manifests prevent preempted Slurm jobs from
   contaminating accepted evidence.
4. **Decoder inputs are future-proof.** The versioned data contract separates
   syndrome + loss/reload history + metadata from the final logical label, so
   future learned decoders can use the same benchmark without label leakage.

## Why we trust the baseline

1. **Frozen physics.** The round timeline, reload semantics, policy thresholds,
   noise matrix and stopping rules were fixed before the large grid.
2. **Independent oracles.** Exhaustive small-geometry graph checks and a
   separate policy state-machine oracle test the simulator outside its own
   implementation path.
3. **Causal isolation.** Prefix-causality and label-poison tests reject access
   to future loss or final logical outcomes.
4. **Negative controls.** Wrong-answer, timeout, environment-escape,
   background-process and hard-coded candidates all fail closed.
5. **Exact replay.** The accepted candidate reached
   `185.979924557991` validated decoded shots/s and reproduced immutable shard
   hashes under the locked environment.
6. **Independent seed.** The confirmation stream is separate from Discovery
   and passes its precision gate in every comparison.

## Model and policies

- Rotated surface-code memory at `d={3,5}`, memory-X/Z and `T={d,2d}`.
- Per-round data Pauli errors, measurement flips and stochastic atom loss.
- Site state machine:
  `ACTIVE -> LOST_UNDETECTED -> LOST_DETECTED -> RELOADING -> ACTIVE`.
- Policies: `none`, `immediate`, `periodic(1|d|2d)` and
  `threshold(0.02|0.05|0.10)`.
- Baseline decoder: loss-history-conditioned erasure-aware MWPM.
- Statistics: paired 95% bootstrap intervals and BH FDR `q=0.05`.

Reload restores a fresh carrier, not the unknown quantum state held by the
lost atom. This distinction is enforced in the event model and report.

## Included artifacts

| Path | Role |
|---|---|
| `report/report.html` | Standalone judge-facing report with embedded vector figures |
| `report/report.json` | Structured four-section challenge report |
| `RESULTS.md` | Compact scientific result and claim boundary |
| `results/summary.json` | Machine-readable public headline numbers and hashes |
| `results/*/*.parquet` | Verified compact cell/comparison aggregates |
| `src/reload_qec/` | Simulator, policy, decoder, analysis and artifact pipeline |
| `tests/` | Core, Discovery, confirmation and sensitivity contracts |
| `research/reference/` | Independent graph and policy oracles |
| `research/DATA_SCHEMA.md` | Decoder-ready input/label separation and boundary semantics |
| `research/MODEL.md` | Frozen physical and timing model |
| `research/SCIENCE_GATE.md` | Deadline gate audit |
| `slurm/` | Reproducible SCNet/xh5 batch entry points |

Large per-shot arrays stay on the cluster. Their original artifact names and
digests remain in the committed analysis manifests; the compact files included
in this PR have directly runnable subset checksum lists.

## Compact verification

From `tracks/qmc/solutions/yanwang-66` in the locked Python environment:

```bash
python3 -m pytest \
  tests/test_experiment_core.py \
  tests/test_discovery_contract.py \
  tests/test_confirmation_contract.py

(cd results/discovery-phase-3 && sha256sum -c included-checksums.sha256)
(cd results/confirmation-phase-5 && sha256sum -c included-checksums.sha256)

python3 ../../../../skills/report/render_report.py report
```

The report was generated by the repository's `challenge-report` / `report`
pipeline and is self-contained after rendering.

## Honest boundary

The highest verified Discovery artifact is a post-deadline supplement. It
strengthens the public signal but does not retroactively change the frozen
deadline disposition. Cost sensitivity was not started because the registered
Discovery prerequisite did not complete, and the sealed holdout was not
queried. No `d=7,9` experiment was run, so no asymptotic threshold is claimed.

The result is nevertheless concrete: it advances Challenge #66 from an open
engineering question to a reproducible benchmark with broad positive
finite-size signals, independent precision confirmation, compact public
aggregates, and a clear route to a decisive future stopping run.
