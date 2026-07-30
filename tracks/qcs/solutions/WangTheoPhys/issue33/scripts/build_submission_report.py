#!/usr/bin/env python3
"""Build the reproducible VQETape reviewer evidence package.

All numerical claims originate in committed JSON reports under ``outputs/``.
The only curated annotations are the Slurm job-level NVML values already
recorded in ``outputs/tensorcircuit-ng-baseline-findings.md``.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import math
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import Any

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
SUBMISSION = ROOT / "submission"
PDF_DIR = SUBMISSION / "output" / "pdf"
EVIDENCE_COMMIT = "748c5e974573e11a22e639dfe76ff00be9819f78"
EVIDENCE_COMMIT_TIME = "2026-07-30T17:59:47+08:00"
PR_URL = "https://github.com/QuantumBFS/quantum.harness/pull/263"
ISSUE_URL = "https://github.com/QuantumBFS/quantum.harness/issues/33"

NAVY = colors.HexColor("#15233B")
BLUE = colors.HexColor("#2563EB")
CYAN = colors.HexColor("#0891B2")
GREEN = colors.HexColor("#15803D")
AMBER = colors.HexColor("#B45309")
RED = colors.HexColor("#B91C1C")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#526074")
PALE = colors.HexColor("#F3F6FA")
GRID = colors.HexColor("#D7DEE8")
WHITE = colors.white


@dataclass(frozen=True)
class BenchmarkRow:
    implementation: str
    slurm_job: str
    compile_s: float
    first_s: float
    warm_ms: float
    warm_mad_ms: float
    objective_s: float
    host_rss_mib: float
    nvml_mib: int
    energy_abs_error: float
    gradient_rel_l2_error: float
    correctness_passed: bool
    source_json: str


def read_json(name: str) -> dict[str, Any]:
    path = OUTPUTS / name
    if not path.is_file():
        raise FileNotFoundError(f"missing canonical evidence: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def mib(byte_count: int | float) -> float:
    return float(byte_count) / 1024**2


def objective(compile_s: float, first_s: float, warm_s: float) -> float:
    return compile_s + first_s + 100.0 * warm_s


def load_evidence() -> tuple[list[BenchmarkRow], dict[str, Any]]:
    tc = read_json("tensorcircuit-ng-rtx3090-matched-n10-d4.json")
    sv = read_json("vqetape-gpu-rtx3090-statevector-n10-d4.json")
    tn = read_json("vqetape-gpu-rtx3090-direct-tn-n10-d4.json")
    sp = read_json("vqetape-gpu-rtx3090-spatial-n10-d4.json")
    fig2 = read_json("tensorcircuit-ng-fig2-rtx3080-smoke-n6-l3-run.json")
    ansatz = read_json("vqetape-ansatz-report.json")

    rows: list[BenchmarkRow] = []
    t = tc["timings"]
    rows.append(
        BenchmarkRow(
            implementation="TensorCircuit-NG / OMECo",
            slurm_job="23020496",
            compile_s=t["compile_seconds"],
            first_s=t["first_execute_seconds"],
            warm_ms=1000.0 * t["warm_seconds_median"],
            warm_mad_ms=1000.0 * t["warm_seconds_mad"],
            objective_s=objective(
                t["compile_seconds"],
                t["first_execute_seconds"],
                t["warm_seconds_median"],
            ),
            host_rss_mib=mib(tc["memory"]["peak_rss_bytes"]),
            nvml_mib=int(tc["memory"]["nvml_job_peak_mib"]),
            energy_abs_error=tc["correctness"]["energy_abs_error"],
            gradient_rel_l2_error=tc["correctness"][
                "gradient_relative_l2_error"
            ],
            correctness_passed=bool(tc["correctness"]["tolerance_passed"]),
            source_json="outputs/tensorcircuit-ng-rtx3090-matched-n10-d4.json",
        )
    )

    candidates = [
        ("VQETape / statevector", sv, "candidate", 272, "23015042"),
        ("VQETape / direct TN", tn, "candidate", 274, "23015037"),
        ("VQETape / spatial block-2", sp, "candidate", 274, "23015038"),
    ]
    for label, payload, field, nvml_value, job in candidates:
        c = payload[field]
        rows.append(
            BenchmarkRow(
                implementation=label,
                slurm_job=job,
                compile_s=c["compile_seconds"],
                first_s=c["first_execute_seconds"],
                warm_ms=1000.0 * c["warm_seconds_median"],
                warm_mad_ms=1000.0 * c["warm_seconds_mad"],
                objective_s=objective(
                    c["compile_seconds"],
                    c["first_execute_seconds"],
                    c["warm_seconds_median"],
                ),
                host_rss_mib=mib(c["peak_rss_bytes"]),
                nvml_mib=nvml_value,
                energy_abs_error=payload["correctness"]["energy_abs_error"],
                gradient_rel_l2_error=payload["correctness"][
                    "gradient_relative_l2_error"
                ],
                correctness_passed=bool(
                    payload["correctness"]["tolerance_passed"]
                ),
                source_json=f"outputs/{Path(payload_source(payload)).name}",
            )
        )

    if not all(row.correctness_passed for row in rows):
        raise RuntimeError("a matched benchmark failed its correctness tolerance")
    if not fig2["correctness"]["tolerance_passed"]:
        raise RuntimeError("the Fig. 2 structural smoke failed correctness")

    tc_row, _, _, spatial = rows
    derived = {
        "objective_win_percent": 100.0
        * (tc_row.objective_s - spatial.objective_s)
        / tc_row.objective_s,
        "host_rss_reduction_percent": 100.0
        * (tc_row.host_rss_mib - spatial.host_rss_mib)
        / tc_row.host_rss_mib,
        "warm_slowdown_factor": spatial.warm_ms / tc_row.warm_ms,
        "statevector_warm_slowdown_factor": rows[1].warm_ms / tc_row.warm_ms,
        "device_memory_delta_mib": spatial.nvml_mib - tc_row.nvml_mib,
        "fig2": {
            "nqubits": fig2["protocol"]["ansatz"]["nqubits"],
            "depth": fig2["protocol"]["ansatz"]["depth"],
            "parameter_count": fig2["protocol"]["ansatz"]["parameter_count"],
            "first_s": fig2["timings"]["first_value_and_grad_seconds"],
            "warm_ms": 1000.0
            * fig2["timings"]["warm_value_and_grad_seconds_median"],
            "energy_abs_error": fig2["correctness"]["energy_abs_error"],
            "gradient_rel_l2_error": fig2["correctness"][
                "gradient_relative_l2_error"
            ],
            "gpu": "NVIDIA RTX 3080",
            "slurm_job": "23027373",
        },
        "ansatz": ansatz["derived"],
    }
    return rows, derived


def payload_source(payload: dict[str, Any]) -> str:
    job = str(payload["hpc_runtime"]["slurm_job_id"])
    by_job = {
        "23015042": "vqetape-gpu-rtx3090-statevector-n10-d4.json",
        "23015037": "vqetape-gpu-rtx3090-direct-tn-n10-d4.json",
        "23015038": "vqetape-gpu-rtx3090-spatial-n10-d4.json",
    }
    return by_job[job]


def fmt_e(value: float) -> str:
    return f"{value:.2e}"


def write_tsv(rows: list[BenchmarkRow]) -> Path:
    path = SUBMISSION / "vqetape-matched-benchmark.tsv"
    fields = list(asdict(rows[0]).keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, delimiter="\t", fieldnames=fields, lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    return path


def status_text(rows: list[BenchmarkRow], d: dict[str, Any]) -> str:
    tc, statevector, _, spatial = rows
    return f"""VQETape issue #33 submission status
Generated from committed evidence snapshot: {EVIDENCE_COMMIT}

MATCHED PROTOCOL
Hardware: one NVIDIA RTX 3090, Slurm node c05r05
Workload: open-boundary TFIM, n=10, L=4, plus state, RZZ then RX, seed=33, complex64
Correctness: all four matched implementations pass energy and full-gradient tolerances

PASS - AMORTIZED TIME OBJECTIVE
TensorCircuit-NG compile + first + 100 warm: {tc.objective_s:.4f} s
VQETape spatial compile + first + 100 warm: {spatial.objective_s:.4f} s
VQETape spatial improvement: {d['objective_win_percent']:.1f}%

PASS - HOST PROCESS MEMORY
TensorCircuit-NG peak RSS: {tc.host_rss_mib:.1f} MiB
VQETape spatial peak RSS: {spatial.host_rss_mib:.1f} MiB
VQETape spatial reduction: {d['host_rss_reduction_percent']:.1f}%

FAIL - SUBSEQUENT WARM RUNTIME
TensorCircuit-NG warm median: {tc.warm_ms:.4f} ms
VQETape statevector warm median: {statevector.warm_ms:.4f} ms
VQETape spatial warm median: {spatial.warm_ms:.4f} ms
Best VQETape warm kernel is {d['statevector_warm_slowdown_factor']:.2f}x slower than TensorCircuit-NG.

INCONCLUSIVE - DEVICE MEMORY
Sampled Slurm job NVML peaks are {tc.nvml_mib}-{spatial.nvml_mib} MiB, effectively tied at this size.

PARTIAL - PAPER FIGURE 2
The exact SU(4) find/execute protocol and safe JSON path artifact are implemented.
An RTX 3080 N=6,L=3 correctness smoke passed. The formal N=32,L=16 H200-scale run is not complete.

BOTTOM LINE
The repository, tests, baseline, data trail, and review package are complete.
The literal challenge criterion is only partially met because warm runtime and device-memory superiority are not established.
"""


def markdown_report(rows: list[BenchmarkRow], d: dict[str, Any]) -> str:
    tc, statevector, direct, spatial = rows
    table_rows = "\n".join(
        "| {0} | {1:.4f} | {2:.4f} | {3:.4f} | {4:.4f} | {5:.1f} | {6} | {7} |".format(
            row.implementation,
            row.compile_s,
            row.first_s,
            row.warm_ms,
            row.objective_s,
            row.host_rss_mib,
            row.nvml_mib,
            "PASS" if row.correctness_passed else "FAIL",
        )
        for row in rows
    )
    a = d["ansatz"]
    f = d["fig2"]
    return f"""# VQETape Technical Report

**Challenge:** [QuantumBFS/quantum.harness #33]({ISSUE_URL})

**Team:** Ranger - Junkai Wang

**Pull request:** [QuantumBFS/quantum.harness #263]({PR_URL})

**Evidence snapshot:** `{EVIDENCE_COMMIT}`

**Report date:** 2026-07-30

## Executive result

VQETape is an exact, auto-evaluated VQE compiler prototype that searches tensor representation, contraction path, reverse program, checkpoint schedule, symmetry sector, classical optimizer, initialization, and ansatz growth. A controlled same-node baseline against TensorCircuit-NG 1.8.0 is complete.

On the matched RTX 3090 workload, VQETape spatial transfer is **{d['objective_win_percent']:.1f}% faster** for `compile + first + 100 warm` and uses **{d['host_rss_reduction_percent']:.1f}% less host peak RSS** than TensorCircuit-NG. This is a real but bounded win: TensorCircuit-NG still has the fastest warm kernel, and sampled device-memory peaks are tied. Therefore the literal challenge is **partially met**, not fully met.

| Requirement | Verdict | Evidence |
|---|---|---|
| Auto-iteratable and auto-evaluatable harness | PASS | Candidate search, isolated workers, exact value-gradient checks, JSON reports, 395-test regression |
| First-time / amortized time efficiency | PASS at matched `n=10,L=4` | {tc.objective_s:.4f} s TensorCircuit-NG vs {spatial.objective_s:.4f} s VQETape spatial |
| Subsequent warm runtime superiority | NOT MET | {tc.warm_ms:.4f} ms TensorCircuit-NG vs {statevector.warm_ms:.4f} ms best VQETape warm kernel |
| Host space efficiency | PASS at matched size | {tc.host_rss_mib:.1f} MiB vs {spatial.host_rss_mib:.1f} MiB |
| Device-memory superiority | NOT ESTABLISHED | sampled job peaks {tc.nvml_mib}-{spatial.nvml_mib} MiB |
| Formal TensorCircuit-NG Fig. 2 scale | OPEN | protocol plus small GPU smoke complete; `N=32,L=16` H200-scale run absent |

## Problem and protocol

The core kernel is `theta -> (E(theta), grad E(theta))` for the open-boundary transverse-field Ising model

`H = -J sum_i Z_i Z_(i+1) - g sum_i X_i`, with `J=g=1`.

The matched comparison uses one RTX 3090 on Slurm node `c05r05`, `n=10`, depth `L=4`, the plus initial state, RZZ then RX per layer, seed 33, complex64, five synchronized warm repeats, and highest JAX matmul precision. Every candidate is checked against an exact statevector value and complete gradient.

The declared selection objective is:

`T_objective = T_compile + T_first + 100 * median(T_warm)`.

## Matched RTX 3090 result

| Implementation | Compile (s) | First (s) | Warm median (ms) | Objective (s) | Host RSS (MiB) | NVML (MiB) | Correct |
|---|---:|---:|---:|---:|---:|---:|---|
{table_rows}

The spatial program crosses the selected amortized threshold because its compile time is {tc.compile_s - spatial.compile_s:.4f} s lower. It does **not** win at steady state: its warm call is {d['warm_slowdown_factor']:.2f}x slower than TensorCircuit-NG, while the statevector path is {d['statevector_warm_slowdown_factor']:.2f}x slower. The NVML samples differ by only {d['device_memory_delta_mib']} MiB and cannot support a GPU-memory superiority claim.

## System design and technical contribution

VQETape treats VQE performance as a joint compiler problem instead of optimizing a single contraction:

1. **Exact representations:** statevector, direct bra-operator-ket tensor network, and an exact spatial-transfer lowering with a bond-dimension-three TFIM MPO.
2. **Program search:** contraction path, block width, scan/unroll policy, reverse-mode residual strategy, rematerialization, and checkpoint placement.
3. **Physics-aware reductions:** an exact global-X Z2 sector is enabled only when the Hamiltonian, initial state, and ansatz preserve it.
4. **End-to-end VQE co-design:** Adam, L-BFGS-B, exact-QGT natural gradient, initialization/recycling, and adaptive ansatz growth are evaluated with compile and optimizer overhead included.
5. **Auditable execution:** candidates run in fresh processes, record machine-readable JSON, keep memory semantics separate, and fail on value-gradient tolerance violations.

Two technically meaningful results go beyond a benchmark wrapper. First, explicit contraction-tree VJPs expose logical-tape/runtime tradeoffs hidden from forward-only path scores. Second, a commutator-complete YZ/ZY adaptive pool fixes the zero-gradient failure of the original X/ZZ pool: the adaptive 10-parameter circuit reaches `{a['gradient_final_error']:.2e}` energy error, while the 14-parameter fixed control stops at `{a['fixed_final_error']:.2e}` under the audited budget.

## TensorCircuit-NG Fig. 2 protocol

The separate Fig. 2 runner encodes the paper's SU(4) ladder ansatz, `15 * L * (N-1)` parameters, TensorNetwork FiniteTFI MPO, contraction-path search, slicing configuration, and checksum-bound safe JSON path artifacts. On an {f['gpu']}, the `N={f['nqubits']},L={f['depth']}` structural smoke ({f['parameter_count']} parameters) passed with energy error `{f['energy_abs_error']:.2e}` and gradient relative L2 error `{f['gradient_rel_l2_error']:.2e}`. This validates protocol construction only; it is not the paper-comparable `N=32,L=16` result.

## Verification and provenance

- Full regression before the incremental Fig. 2 runner: `395 passed, 6 skipped in 1582.14s`; the skips are documented structural cases, with no failures.
- Targeted matched-baseline and Fig. 2 suite: `17 passed`.
- All 27 committed JSON reports parse; all `src/vqetape` Python modules compile; `git diff --check` passes.
- TensorCircuit-NG job `23020496` completed on `c05r05`, reported `cuda:0`, passed strict energy/gradient tolerances, and passed SHA256 provenance checks.
- Fig. 2 smoke job `{f['slurm_job']}` completed on an RTX 3080 and passed direct unsliced value-gradient comparison.

## Negative results and limitations

Negative results are retained because they prevent misleading optimization claims: sparse Z2 metadata can exceed the dense carry on CPU; exact natural gradient can save iterations but lose wall time; operator-Schmidt gates can reduce logical tape but lose runtime; and default GPU matmul precision failed strict spatial correctness until the TensorNetwork backend precision was mapped explicitly.

The present prototype is exact and focused on one-dimensional TFIM/longitudinal-Ising research workloads. It is not an arbitrary TensorCircuit-NG Python source transformer. It does not establish two-dimensional, deep-circuit, multi-GPU, host-offload, or formal Fig. 2 scale performance. Most importantly, the matched experiment does not meet the challenge's warm-runtime clause.

## Reproduction

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test,baseline]'
.venv/bin/python -m pytest -q

vqetape-tc-baseline \\
  --nqubits 10 --depth 4 --seed 33 --warm-repeats 5 \\
  --expected-steps 100 --contractor omeco \\
  --reference outputs/vqetape-gpu-rtx3090-statevector-n10-d4.json \\
  --output outputs/tensorcircuit-ng-rtx3090-matched-n10-d4.json

python scripts/build_submission_report.py
```

Canonical evidence remains under `outputs/`. `submission/vqetape-matched-benchmark.tsv` is the compact data export, `submission/submission-status.txt` is the literal pass/fail statement, and `submission/artifact-manifest.json` binds the review artifacts by SHA256.
"""


def report_json(rows: list[BenchmarkRow], d: dict[str, Any]) -> dict[str, Any]:
    tc, statevector, _, spatial = rows
    return {
        "title": "Challenge #33: VQETape exact VQE compiler",
        "eyebrow": "Quantum Circuit Simulation Track",
        "url": PR_URL,
        "lede": (
            f"VQETape beats TensorCircuit-NG by {d['objective_win_percent']:.1f}% "
            "on a matched 100-step amortized objective and lowers host RSS, "
            "while warm runtime and device-memory superiority remain unmet."
        ),
        "evidence_commit": EVIDENCE_COMMIT,
        "sections": [
            {
                "title": "Challenge",
                "blocks": [
                    {
                        "kind": "text",
                        "text": "Build an auto-evaluated VQE simulation harness that exceeds the TensorCircuit-NG baseline in time and space efficiency.",
                    },
                    {
                        "kind": "kv",
                        "pairs": {
                            "Issue": ISSUE_URL,
                            "Track": "qcs",
                            "Matched system": "RTX 3090; TFIM n=10, L=4",
                        },
                    },
                ],
            },
            {
                "title": "Approach",
                "blocks": [
                    {"kind": "badge", "text": "Exact simulation"},
                    {
                        "kind": "text",
                        "text": "Joint search over representation, contraction path, reverse program, checkpoints, symmetry, optimizer, initialization, and ansatz growth.",
                    },
                ],
            },
            {
                "title": "Results",
                "blocks": [
                    {
                        "kind": "verdict",
                        "status": "partial",
                        "text": f"PASS amortized objective ({spatial.objective_s:.4f} s vs {tc.objective_s:.4f} s) and host RSS; FAIL warm runtime ({statevector.warm_ms:.4f} ms best VQETape vs {tc.warm_ms:.4f} ms).",
                    },
                    {
                        "kind": "table",
                        "columns": [
                            "Implementation",
                            "Compile s",
                            "First s",
                            "Warm ms",
                            "Objective s",
                            "RSS MiB",
                        ],
                        "rows": [
                            [
                                r.implementation,
                                round(r.compile_s, 4),
                                round(r.first_s, 4),
                                round(r.warm_ms, 4),
                                round(r.objective_s, 4),
                                round(r.host_rss_mib, 1),
                            ]
                            for r in rows
                        ],
                    },
                ],
            },
            {
                "title": "Highlight",
                "blocks": [
                    {
                        "kind": "card",
                        "title": "What is innovative",
                        "text": "A differentiated contraction-program search plus exact physics-aware reductions and end-to-end ansatz/optimizer co-design, with negative results preserved.",
                    },
                    {
                        "kind": "card",
                        "title": "Boundary",
                        "text": "The literal warm-runtime and device-memory criteria are not met; formal N=32,L=16 Fig. 2 execution remains open.",
                    },
                ],
            },
        ],
    }


def html_report(markdown: str, rows: list[BenchmarkRow], d: dict[str, Any]) -> str:
    tc, statevector, _, spatial = rows
    table = "".join(
        "<tr>"
        f"<td>{html.escape(r.implementation)}</td>"
        f"<td>{r.compile_s:.4f}</td><td>{r.first_s:.4f}</td>"
        f"<td>{r.warm_ms:.4f}</td><td>{r.objective_s:.4f}</td>"
        f"<td>{r.host_rss_mib:.1f}</td><td>{r.nvml_mib}</td>"
        f"<td>{'PASS' if r.correctness_passed else 'FAIL'}</td></tr>"
        for r in rows
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VQETape Technical Report</title>
<style>
:root{{--navy:#15233b;--blue:#2563eb;--green:#15803d;--amber:#b45309;--ink:#172033;--muted:#526074;--pale:#f3f6fa;--grid:#d7dee8}}
*{{box-sizing:border-box}} body{{margin:0;background:#eef2f7;color:var(--ink);font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1080px;margin:0 auto;background:white;min-height:100vh;box-shadow:0 10px 40px #1b2b4520}}
header{{padding:68px 72px 54px;background:linear-gradient(135deg,var(--navy),#23456f);color:white}}
.eyebrow{{letter-spacing:.16em;text-transform:uppercase;font-size:12px;color:#9ee4f2}} h1{{font-size:46px;line-height:1.05;margin:.3em 0}}
.lede{{max-width:800px;font-size:20px;color:#dce9f8}} section{{padding:38px 72px;border-bottom:1px solid var(--grid)}} h2{{font-size:28px;color:var(--navy)}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}} .card{{padding:20px;border:1px solid var(--grid);border-radius:12px;background:var(--pale)}}
.number{{font-size:30px;font-weight:750;color:var(--blue)}} .pass{{color:var(--green)}} .fail{{color:#b91c1c}} .warn{{color:var(--amber)}}
table{{width:100%;border-collapse:collapse;font-size:14px}} th,td{{padding:10px 9px;border-bottom:1px solid var(--grid);text-align:right}} th:first-child,td:first-child{{text-align:left}} th{{background:var(--navy);color:white}}
code{{background:var(--pale);padding:.15em .35em;border-radius:4px}} pre{{white-space:pre-wrap;background:#101827;color:#e8eef7;padding:20px;border-radius:10px;overflow:auto}}
.boundary{{border-left:5px solid var(--amber);padding:14px 18px;background:#fff8ed}} footer{{padding:28px 72px;color:var(--muted)}}
@media(max-width:760px){{header,section,footer{{padding-left:24px;padding-right:24px}}.cards{{grid-template-columns:1fr}}h1{{font-size:36px}}}}
</style></head><body><main>
<header><div class="eyebrow">Quantum Circuit Simulation - Challenge #33</div><h1>VQETape</h1><p class="lede">Exact VQE program co-design with an audited same-node TensorCircuit-NG baseline.</p><p>Team Ranger - Junkai Wang &nbsp; | &nbsp; <a style="color:#9ee4f2" href="{PR_URL}">Pull request #263</a></p></header>
<section><h2>Executive result</h2><div class="cards">
<div class="card"><div class="number pass">{d['objective_win_percent']:.1f}%</div><b>faster amortized objective</b><br>VQETape spatial vs TensorCircuit-NG</div>
<div class="card"><div class="number pass">{d['host_rss_reduction_percent']:.1f}%</div><b>less host peak RSS</b><br>matched RTX 3090 job</div>
<div class="card"><div class="number fail">{d['statevector_warm_slowdown_factor']:.2f}x</div><b>slower best warm kernel</b><br>literal runtime clause remains open</div></div>
<p class="boundary"><b>Honest verdict: partially met.</b> The selected 100-step objective and host memory pass; warm runtime and device-memory superiority do not. The formal N=32,L=16 H200-scale Fig. 2 run is not complete.</p></section>
<section><h2>Matched RTX 3090 evidence</h2><p>Open TFIM, n=10, L=4, plus state, RZZ then RX, seed 33, complex64, five synchronized warm repeats. Objective = compile + first + 100 warm.</p>
<table><thead><tr><th>Implementation</th><th>Compile s</th><th>First s</th><th>Warm ms</th><th>Objective s</th><th>RSS MiB</th><th>NVML MiB</th><th>Correct</th></tr></thead><tbody>{table}</tbody></table></section>
<section><h2>What was built</h2><div class="cards"><div class="card"><b>Program search</b><br>Representation, contraction path, reverse program, blocks, checkpoints, and symmetry.</div><div class="card"><b>VQE co-design</b><br>Optimizer, initialization, recycling, and adaptive ansatz growth with overhead included.</div><div class="card"><b>Audit trail</b><br>Fresh workers, exact value-gradient gates, safe JSON, separated memory semantics, and negative results.</div></div></section>
<section><h2>Verification</h2><ul><li>395 passed, 6 documented structural skips; no failures.</li><li>17 targeted TensorCircuit-NG baseline/Fig. 2 tests passed.</li><li>All 27 evidence JSON files parse; source modules compile.</li><li>TensorCircuit-NG job 23020496 and Fig. 2 smoke job 23027373 completed and passed correctness.</li></ul></section>
<section><h2>Reproduce</h2><pre>python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test,baseline]'
.venv/bin/python -m pytest -q
python scripts/build_submission_report.py</pre><p>The full narrative is available in <code>vqetape-technical-report.md</code>; exact rows are in <code>vqetape-matched-benchmark.tsv</code>.</p></section>
<footer>Evidence snapshot {EVIDENCE_COMMIT} - generated 2026-07-30 - <a href="{ISSUE_URL}">Challenge #33</a></footer>
</main></body></html>"""


def register_fonts() -> tuple[str, str]:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    bold_candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    regular = next((p for p in candidates if p.is_file()), None)
    bold = next((p for p in bold_candidates if p.is_file()), None)
    if regular and bold:
        pdfmetrics.registerFont(TTFont("VQRegular", str(regular)))
        pdfmetrics.registerFont(TTFont("VQBold", str(bold)))
        return "VQRegular", "VQBold"
    return "Helvetica", "Helvetica-Bold"


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def flow_diagram(font: str, bold: str) -> Drawing:
    width, height = 475, 175
    d = Drawing(width, height)
    boxes = [
        (5, 105, 104, 48, "Protocol +\nconstraints"),
        (126, 105, 104, 48, "Candidate\ngenerator"),
        (247, 105, 104, 48, "Fresh-process\ncompile + run"),
        (368, 105, 104, 48, "Correctness +\nmetrics"),
    ]
    for x, y, w, h, label in boxes:
        d.add(Rect(x, y, w, h, rx=7, ry=7, fillColor=PALE, strokeColor=BLUE))
        a, b = label.split("\n")
        d.add(String(x + w / 2, y + 29, a, textAnchor="middle", fontName=bold, fontSize=9, fillColor=NAVY))
        d.add(String(x + w / 2, y + 16, b, textAnchor="middle", fontName=font, fontSize=8, fillColor=MUTED))
    for x in (109, 230, 351):
        d.add(Line(x + 2, 129, x + 15, 129, strokeColor=CYAN, strokeWidth=2))
        d.add(Line(x + 11, 133, x + 15, 129, strokeColor=CYAN, strokeWidth=2))
        d.add(Line(x + 11, 125, x + 15, 129, strokeColor=CYAN, strokeWidth=2))
    lower = [
        (66, 26, 110, 40, "representation / path"),
        (183, 26, 110, 40, "AD / checkpoints"),
        (300, 26, 110, 40, "optimizer / ansatz"),
    ]
    for x, y, w, h, label in lower:
        d.add(Rect(x, y, w, h, rx=6, ry=6, fillColor=colors.white, strokeColor=GRID))
        d.add(String(x + w / 2, y + 23, label, textAnchor="middle", fontName=font, fontSize=8, fillColor=INK))
    d.add(String(width / 2, 3, "Auto-evaluation feeds measured cost and validity back into selection", textAnchor="middle", fontName=font, fontSize=8, fillColor=MUTED))
    return d


def bar_chart(
    title: str,
    rows: list[BenchmarkRow],
    attr: str,
    unit: str,
    font: str,
    bold: str,
    highlight_lowest: bool = True,
) -> Drawing:
    width, height = 475, 215
    d = Drawing(width, height)
    values = [float(getattr(row, attr)) for row in rows]
    max_value = max(values) * 1.08
    left, bottom, plot_w, plot_h = 155, 30, 285, 145
    d.add(String(0, 195, title, fontName=bold, fontSize=11, fillColor=NAVY))
    d.add(Line(left, bottom, left, bottom + plot_h, strokeColor=GRID))
    d.add(Line(left, bottom, left + plot_w, bottom, strokeColor=GRID))
    best = min(values) if highlight_lowest else None
    for i, (row, value) in enumerate(zip(rows, values, strict=True)):
        y = bottom + plot_h - 26 - i * 34
        bar_w = plot_w * value / max_value
        color = GREEN if best is not None and math.isclose(value, best) else BLUE
        d.add(String(left - 8, y + 5, row.implementation.replace("TensorCircuit-NG / ", "TC-NG / ").replace("VQETape / ", "VQ / "), textAnchor="end", fontName=font, fontSize=8, fillColor=INK))
        d.add(Rect(left, y, bar_w, 17, fillColor=color, strokeColor=None))
        d.add(String(min(left + bar_w + 5, width - 40), y + 5, f"{value:.2f} {unit}", fontName=bold, fontSize=8, fillColor=INK))
    return d


def pdf_styles(font: str, bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("VQTitle", parent=base["Title"], fontName=bold, fontSize=32, leading=35, textColor=NAVY, alignment=TA_LEFT, spaceAfter=12),
        "subtitle": ParagraphStyle("VQSubtitle", parent=base["Normal"], fontName=font, fontSize=15, leading=21, textColor=MUTED, spaceAfter=18),
        "h1": ParagraphStyle("VQH1", parent=base["Heading1"], fontName=bold, fontSize=20, leading=24, textColor=NAVY, spaceAfter=12),
        "h2": ParagraphStyle("VQH2", parent=base["Heading2"], fontName=bold, fontSize=12, leading=15, textColor=BLUE, spaceBefore=8, spaceAfter=6),
        "body": ParagraphStyle("VQBody", parent=base["BodyText"], fontName=font, fontSize=9.4, leading=13.5, textColor=INK, spaceAfter=7),
        "small": ParagraphStyle("VQSmall", parent=base["BodyText"], fontName=font, fontSize=7.5, leading=10, textColor=MUTED),
        "callout": ParagraphStyle("VQCallout", parent=base["BodyText"], fontName=bold, fontSize=11, leading=15, textColor=NAVY, backColor=PALE, borderColor=BLUE, borderWidth=0.8, borderPadding=10, spaceAfter=10),
        "warn": ParagraphStyle("VQWarn", parent=base["BodyText"], fontName=bold, fontSize=9.5, leading=14, textColor=AMBER, backColor=colors.HexColor("#FFF8ED"), borderColor=AMBER, borderWidth=0.8, borderPadding=9, spaceAfter=10),
        "code": ParagraphStyle("VQCode", parent=base["Code"], fontName="Courier", fontSize=7.2, leading=9.5, textColor=colors.HexColor("#E8EEF7"), backColor=colors.HexColor("#101827"), borderPadding=9, spaceAfter=7),
        "center": ParagraphStyle("VQCenter", parent=base["BodyText"], fontName=font, fontSize=9, leading=12, alignment=TA_CENTER, textColor=MUTED),
    }


def metric_cards(rows: list[BenchmarkRow], d: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    tc, statevector, _, spatial = rows
    cards = [
        (f"<font color='#15803D' size='18'><b>{d['objective_win_percent']:.1f}%</b></font><br/><b>faster amortized objective</b><br/><font size='8'>VQ spatial vs TC-NG</font>"),
        (f"<font color='#15803D' size='18'><b>{d['host_rss_reduction_percent']:.1f}%</b></font><br/><b>less host peak RSS</b><br/><font size='8'>{spatial.host_rss_mib:.1f} vs {tc.host_rss_mib:.1f} MiB</font>"),
        (f"<font color='#B91C1C' size='18'><b>{d['statevector_warm_slowdown_factor']:.2f}x</b></font><br/><b>slower best VQ warm</b><br/><font size='8'>{statevector.warm_ms:.3f} vs {tc.warm_ms:.3f} ms</font>"),
    ]
    data = [[Paragraph(x, styles["center"]) for x in cards]]
    table = Table(data, colWidths=[55 * mm, 55 * mm, 55 * mm], rowHeights=[31 * mm])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, GRID),
        ("INNERGRID", (0, 0), (-1, -1), 0.7, GRID),
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def benchmark_table(rows: list[BenchmarkRow], styles: dict[str, ParagraphStyle]) -> Table:
    headers = ["Implementation", "Compile\n(s)", "First\n(s)", "Warm\n(ms)", "Objective\n(s)", "Host RSS\n(MiB)", "NVML\n(MiB)"]
    data: list[list[Any]] = [[p(h.replace("\n", "<br/>"), styles["small"]) for h in headers]]
    for row in rows:
        data.append([
            p(row.implementation, styles["small"]),
            f"{row.compile_s:.4f}",
            f"{row.first_s:.4f}",
            f"{row.warm_ms:.4f}",
            f"{row.objective_s:.4f}",
            f"{row.host_rss_mib:.1f}",
            str(row.nvml_mib),
        ])
    t = Table(data, colWidths=[45 * mm, 18 * mm, 17 * mm, 20 * mm, 21 * mm, 24 * mm, 19 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.4),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
        ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#ECFDF3")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def build_pdf(path: Path, rows: list[BenchmarkRow], d: dict[str, Any]) -> None:
    font, bold = register_fonts()
    styles = pdf_styles(font, bold)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="VQETape Technical Report",
        author="Ranger - Junkai Wang",
        subject="Quantum Harness Challenge #33",
    )

    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(GRID)
        canvas.line(20 * mm, 13 * mm, A4[0] - 20 * mm, 13 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont(font, 7)
        canvas.drawString(20 * mm, 8.5 * mm, "VQETape - Quantum Harness Challenge #33")
        canvas.drawRightString(A4[0] - 20 * mm, 8.5 * mm, f"{document.page}")
        canvas.restoreState()

    tc, statevector, direct, spatial = rows
    fig2 = d["fig2"]
    a = d["ansatz"]
    story: list[Any] = []

    # Page 1
    story += [Spacer(1, 18 * mm), p("QUANTUM CIRCUIT SIMULATION", styles["h2"]), p("VQETape", styles["title"]), p("Exact VQE program co-design with an audited same-node TensorCircuit-NG baseline", styles["subtitle"]), Spacer(1, 5 * mm), metric_cards(rows, d, styles), Spacer(1, 9 * mm), p("HONEST VERDICT: PARTIALLY MET", styles["h2"]), p(f"VQETape spatial transfer is <b>{d['objective_win_percent']:.1f}% faster</b> on the declared compile + first + 100-warm objective and uses <b>{d['host_rss_reduction_percent']:.1f}% less host peak RSS</b> than TensorCircuit-NG on the same RTX 3090. TensorCircuit-NG still owns the fastest warm kernel, sampled GPU memory is tied, and the formal N=32,L=16 Fig. 2 run is absent.", styles["warn"]), Spacer(1, 4 * mm), p(f"Team Ranger - Junkai Wang<br/>Challenge #33 - PR #263<br/>Evidence snapshot: {EVIDENCE_COMMIT[:12]}<br/>30 July 2026", styles["body"]), PageBreak()]

    # Page 2
    story += [p("1. Challenge and evaluation contract", styles["h1"]), p("The requested system should iterate over exact VQE implementations, auto-evaluate them, and beat the TensorCircuit-NG official baseline in space and time - including compilation, first execution, and subsequent warm execution.", styles["body"]), p("Matched physical protocol", styles["h2"]), p("Open-boundary transverse-field Ising model: H = -J sum Z_i Z_(i+1) - g sum X_i, with J=g=1. The matched run uses n=10, depth L=4, the plus initial state, RZZ then RX per layer, seed 33, complex64, and five synchronized warm repetitions on one NVIDIA RTX 3090.", styles["body"]), p("Selection objective", styles["h2"]), p("T_objective = T_compile + T_first + 100 x median(T_warm). Compilation includes the measured path-search cost. Correctness requires both energy and the complete gradient to pass 1e-5 tolerances.", styles["callout"]), p("Compiler feedback loop", styles["h2"]), flow_diagram(font, bold), p("A candidate is eligible only after exact value-gradient validation. Time, host RSS, compiler temporaries, logical residuals, modeled checkpoints, and job-level NVML samples remain separate fields; the report never relabels one as another.", styles["body"]), PageBreak()]

    # Page 3
    story += [p("2. Matched performance result", styles["h1"]), p("All rows below use the same workload and node. The green row is the VQETape candidate selected for the 100-step objective, not the fastest warm candidate.", styles["body"]), benchmark_table(rows, styles), Spacer(1, 6 * mm), bar_chart("Compile + first + 100 warm (lower is better)", rows, "objective_s", "s", font, bold), p(f"The spatial program crosses the amortized threshold at {spatial.objective_s:.4f} s versus {tc.objective_s:.4f} s. Its advantage comes from compilation: {spatial.compile_s:.4f} s versus {tc.compile_s:.4f} s.", styles["body"]), PageBreak()]

    # Page 4
    story += [p("3. Runtime and memory boundary", styles["h1"]), bar_chart("Warm value-gradient median (lower is better)", rows, "warm_ms", "ms", font, bold), bar_chart("Peak host process RSS (lower is better)", rows, "host_rss_mib", "MiB", font, bold), p(f"Warm runtime is the main unresolved challenge criterion. TensorCircuit-NG records {tc.warm_ms:.4f} ms; the fastest VQETape warm path is statevector at {statevector.warm_ms:.4f} ms ({d['statevector_warm_slowdown_factor']:.2f}x slower), while the selected spatial path records {spatial.warm_ms:.4f} ms.", styles["warn"]), p(f"Host RSS is a clear matched win ({tc.host_rss_mib:.1f} to {spatial.host_rss_mib:.1f} MiB). Sampled job-level NVML peaks are {tc.nvml_mib}, {statevector.nvml_mib}, {direct.nvml_mib}, and {spatial.nvml_mib} MiB; a 2 MiB spread is treated as tied, not as a device-memory win.", styles["body"]), PageBreak()]

    # Page 5
    verification_data = [
        ["Gate", "Evidence", "Result"],
        ["Matched correctness", "Energy + complete gradient; 1e-5 tolerance", "PASS"],
        ["Full regression", "395 passed; 6 documented structural skips", "PASS"],
        ["Incremental suite", "17 baseline and Fig. 2 tests", "PASS"],
        ["Static artifacts", "27 JSON parse; Python compile; diff check", "PASS"],
        ["TC-NG GPU run", "Slurm 23020496; cuda:0; SHA256 audit", "PASS"],
        ["Fig. 2 protocol", f"RTX 3080 N={fig2['nqubits']},L={fig2['depth']} smoke", "PASS / SMALL"],
        ["Formal Fig. 2", "N=32,L=16 on paper-comparable hardware", "OPEN"],
    ]
    vt = Table([[p(str(x), styles["small"]) for x in row] for row in verification_data], colWidths=[38 * mm, 102 * mm, 27 * mm])
    vt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE), ("GRID", (0, 0), (-1, -1), 0.4, GRID), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [p("4. Correctness and provenance", styles["h1"]), p("The baseline is useful only if it is mathematically and operationally comparable. VQETape therefore records protocol, seed, precision, value, full gradient, timing boundaries, memory semantics, node/job identity, and source checksums.", styles["body"]), vt, Spacer(1, 7 * mm), p("Fig. 2 structural smoke", styles["h2"]), p(f"The separate SU(4) runner preserves 15 x L x (N-1) parameters, TensorNetwork FiniteTFI MPO construction, find/execute separation, slicing controls, and checksum-bound JSON path artifacts. Job {fig2['slurm_job']} passed at N={fig2['nqubits']}, L={fig2['depth']} with energy error {fmt_e(fig2['energy_abs_error'])} and gradient relative L2 error {fmt_e(fig2['gradient_rel_l2_error'])}.", styles["body"]), p("This proves protocol construction and safe artifact replay. It does not reproduce the H200 N=32,L=16 timing point.", styles["warn"]), PageBreak()]

    # Page 6
    story += [p("5. Technical contribution", styles["h1"]), p("VQETape explores a cross-layer design space instead of treating contraction order as the whole problem.", styles["body"]), p("1 - Exact program representations", styles["h2"]), p("Statevector, direct bra-operator-ket tensor network, and spatial transfer with an exact bond-dimension-three TFIM MPO. Gate and Hamiltonian tensors are costed separately.", styles["body"]), p("2 - Differentiated contraction programs", styles["h2"]), p("Explicit contraction-tree VJPs, named residuals, checkpoint policies, block widths, scan/unroll choices, and exact Z2 sector compression expose runtime/tape tradeoffs hidden by forward-only FLOP scores.", styles["body"]), p("3 - End-to-end VQE co-design", styles["h2"]), p(f"Optimizer, initialization, recycling, and adaptive ansatz growth include compilation and screening overhead. A commutator-complete YZ/ZY pool reaches {a['gradient_final_error']:.2e} energy error with {a['gradient_final_parameter_count']} parameters; the {a['fixed_final_parameter_count']}-parameter fixed control stops at {a['fixed_final_error']:.2e}.", styles["body"]), p("4 - Negative results as evidence", styles["h2"]), p("Sparse symmetry metadata can cost more than the removed dense carry; exact natural gradient may save iterations but lose wall time; operator-Schmidt gates may reduce logical tape but lose executable runtime; and default GPU matmul precision failed strict correctness until the TensorNetwork backend precision was set explicitly.", styles["body"]), p("The system is an exact 1D research prototype, not a generic Python source-to-source optimizer for arbitrary TensorCircuit-NG scripts.", styles["warn"]), PageBreak()]

    # Page 7
    status_data = [
        ["Requirement", "Status", "Reviewer consequence"],
        ["Repository and harness", "COMPLETE", "Installable package, CLI/API, tests, safe artifacts"],
        ["Controlled TC-NG baseline", "COMPLETE", "Same node, protocol, seed, precision, correctness"],
        ["Amortized time", "PASS", f"{d['objective_win_percent']:.1f}% faster at matched size"],
        ["Host memory", "PASS", f"{d['host_rss_reduction_percent']:.1f}% lower peak RSS"],
        ["Warm runtime", "NOT MET", f"Best VQETape is {d['statevector_warm_slowdown_factor']:.2f}x slower"],
        ["GPU memory", "OPEN", "Sampled peaks tied; no superiority claim"],
        ["Formal Fig. 2 scale", "OPEN", "Protocol/smoke only"],
    ]
    st = Table([[p(str(x), styles["small"]) for x in row] for row in status_data], colWidths=[48 * mm, 31 * mm, 88 * mm])
    st.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE), ("GRID", (0, 0), (-1, -1), 0.4, GRID), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [p("6. Submission readiness and reproduction", styles["h1"]), st, Spacer(1, 6 * mm), p("Clean reproduction", styles["h2"]), p("python3.12 -m venv .venv<br/>.venv/bin/python -m pip install -e '.[test,baseline]'<br/>.venv/bin/python -m pytest -q<br/>python scripts/build_submission_report.py", styles["code"]), p("Reviewer entry points", styles["h2"]), p("README.md - result and fast-start navigation<br/>submission/vqetape-matched-benchmark.tsv - compact machine-readable rows<br/>submission/submission-status.txt - literal pass/fail boundary<br/>submission/vqetape-technical-report.md - full narrative<br/>submission/report.html - standalone browser report<br/>submission/artifact-manifest.json - SHA256 artifact binding", styles["body"]), p("Final conclusion", styles["h2"]), p("The basic engineering and review-delivery requirements are complete, and the project exceeds a minimal baseline wrapper in breadth, correctness discipline, and program co-design. The primary performance challenge remains partially complete until one VQETape path also beats TensorCircuit-NG warm runtime and demonstrates a defensible device-memory advantage.", styles["callout"])]

    doc.build(
        story,
        onFirstPage=footer,
        onLaterPages=footer,
        canvasmaker=partial(Canvas, invariant=1),
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(paths: list[Path]) -> Path:
    manifest = {
        "schema_version": 1,
        "generated_at": EVIDENCE_COMMIT_TIME,
        "evidence_commit": EVIDENCE_COMMIT,
        "challenge_issue": ISSUE_URL,
        "pull_request": PR_URL,
        "artifacts": [
            {
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in paths
        ],
        "canonical_evidence": [
            {
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in sorted(
                [
                    OUTPUTS / "tensorcircuit-ng-rtx3090-matched-n10-d4.json",
                    OUTPUTS / "vqetape-gpu-rtx3090-statevector-n10-d4.json",
                    OUTPUTS / "vqetape-gpu-rtx3090-direct-tn-n10-d4.json",
                    OUTPUTS / "vqetape-gpu-rtx3090-spatial-n10-d4.json",
                    OUTPUTS / "tensorcircuit-ng-fig2-rtx3080-smoke-n6-l3-run.json",
                    OUTPUTS / "vqetape-ansatz-report.json",
                ]
            )
        ],
    }
    path = SUBMISSION / "artifact-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    SUBMISSION.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    print("[1/6] loading canonical evidence", flush=True)
    rows, derived = load_evidence()
    print("[2/6] writing data and status", flush=True)
    tsv = write_tsv(rows)
    status = SUBMISSION / "submission-status.txt"
    status.write_text(status_text(rows, derived), encoding="utf-8")
    print("[3/6] writing Markdown, JSON, and HTML", flush=True)
    md_text = markdown_report(rows, derived)
    md = SUBMISSION / "vqetape-technical-report.md"
    md.write_text(md_text, encoding="utf-8")
    rjson = SUBMISSION / "report.json"
    report_payload = report_json(rows, derived)
    report_payload["evidence_git_head"] = EVIDENCE_COMMIT
    rjson.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")
    htm = SUBMISSION / "report.html"
    htm.write_text(html_report(md_text, rows, derived), encoding="utf-8")
    print("[4/6] building PDF", flush=True)
    pdf = PDF_DIR / "vqetape-technical-report.pdf"
    build_pdf(pdf, rows, derived)
    print("[5/6] writing SHA256 manifest", flush=True)
    manifest = write_manifest([tsv, status, md, rjson, htm, pdf])
    print("[6/6] complete", flush=True)
    for path in [tsv, status, rjson, md, htm, pdf, manifest]:
        print(f"  {path.relative_to(ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
