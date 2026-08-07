## Team

| | |
|---|---|
| **Team name** | bosonchen |
| **Members** | @Fermichen99 |

## Challenge

| Row | |
|---|---|
| **Challenge** | Build a quantum-error-correction decoder that is at least 20× faster than the optimized Tesseract baseline on at least 80% of its benchmark configurations at p = 0.001, without worsening logical error rates on any configuration. |
| **Catalog issue** | Addresses #162 — “Decode 20× faster than Tesseract at matched accuracy (p = 0.001),” released by Jinguo Liu, Hong Kong University of Science and Technology (Guangzhou). |
| **Track** | `qcs`, chosen by the team because the issue’s Method field is `Other` and the work centers on quantum-circuit error-correction decoding. |

## Official Tesseract baseline

The baseline is intentionally limited to the unmodified official decoder. It
does not implement or evaluate a replacement decoder.

- Source: `quantumlib/tesseract-decoder`
- Pinned revision: `9c73ca0acb1a48fd1dc797f5f6deabbb5f5d3feb`
- Circuits: one representative `p=0.001` circuit from each of the surface,
  superdense-color, bivariate-bicycle, and transversal-CX families
- Presets: the official short-beam and long-beam paper configurations
- Sampling: 1000 shots, fixed sample and detector-order seeds
- Parallelism: one decoder thread and one Bazel build job

From the repository root:

```bash
python3 tracks/qcs/solutions/bosonchen/tesseract_baseline.py
```

The first run downloads the pinned official source and Bazel 8.2.1 on an Apple
Silicon Mac, builds the decoder, and then runs the baseline. Later runs can
reuse the build:

```bash
python3 tracks/qcs/solutions/bosonchen/tesseract_baseline.py --skip-build
```

Generated JSON, CSV, SVG plots, and the HTML report are written under
`tracks/qcs/results/` and remain local because result directories are
gitignored.

## Final challenge outcome

The final prototype achieved a **large 10.8×–27.9× online decoding speedup**
on representative Surface, BBC, and TransCX cases while matching all 30 paired
logical predictions. An independent audit confirmed that this improvement is
measured against the pinned, optimized upstream Tesseract implementation—not
against an artificially slow reimplementation. The final report separates
three evidence levels:

1. a reduced reproduction of Tesseract Figure 2;
2. independent-binary paired tests of correctness-preserving and aggressive
   search policies;
3. the final logical-sector prototype and its measured acceleration.

The correctness-preserving final-v6 search candidate produced no observable
prediction mismatches in 200 paired shots, but its median decode speedup was
`0.867×` and no tested configuration reached `20×`. The aggressive single-trial
candidate reached a median `32.634×` decode-only speedup but produced 11
observable prediction mismatches in the same 200-shot protocol. A held-out
syndrome-gated policy produced three optimized-only logical errors in 600
shots. These ablations explain why the final method moved beyond search-only
engineering.

The logical-sector prototype constructed complete GF(2) logical bases for
Surface, BBC, and TransCX test cases. It matched the official baseline on 30
paired shots and showed `10.8×–27.9×` online ratios. The current evidence
therefore establishes a substantial system-level acceleration in the tested
scope. A full benchmark sweep with LER confidence intervals remains the next
validation campaign; the BAR free-energy mechanism also remains conservatively
disabled when its mixing evidence is insufficient.

## Submission map

| Path | Purpose |
|---|---|
| `challenge_report/report.html` | Final self-contained report |
| `challenge_report/report.json` | Structured report source |
| `challenge_report/build_report.py` | One-command report regeneration and data assertions |
| `tesseract_baseline.py` | Pinned official baseline reproduction |
| `tesseract_tempered_worm/` | Logical-sector sampler implementation and Slurm entry points |
| `tesseract_ler_results/` | Minimal canonical machine-readable evidence |

From the repository root, regenerate the final report without running new
cluster jobs:

```bash
python3 tracks/qcs/solutions/bosonchen/challenge_report/build_report.py
```

No pull request is created by any of these commands.
