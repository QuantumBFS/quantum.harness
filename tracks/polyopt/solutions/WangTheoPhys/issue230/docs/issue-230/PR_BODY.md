## Ranger certified frontier for Issue #230

| | |
|---|---|
| Team | Ranger — Chenxi Wan, Yedi Shen, Junkai Wang |
| Challenge | #230: certified thermodynamic energy-density bounds vs. Bethe ansatz |
| Formal status | Validated hope signal; literature-record comparison is the next proof gate |

### Headline certificate

For the spin-1/2 XXX normalization

$$
h=(XX+YY+ZZ)/4,\qquad e_{\mathrm B}=\frac14-\log 2,
$$

the strongest self-contained payload proves

$$
\boxed{-0.443976567\le e_0\le
-0.4428702958784947210360110613724028607783}.
$$

The exact width is

$$
0.0011062711215052789639889386275971392217,
$$

and the interval contains the independently outward-rounded Bethe enclosure.
The lower endpoint is a depth-47, bond-6, native-U(1)-blocked RG dual; the upper
endpoint is an exact rational bond-32 MPS contraction over a 1,000-site block
with explicit boundaries. The public verifier reconstructs every proof object.

### Why this advances the certified stack

- **Native U(1) RG:** D=6, depth=12 contracts from 93,329 dense variables to
  6,882 charge-block variables — 7.4% retained and 13.6x compression — while
  dense/block objective, derivative, Hessian, lift, and slack equivalence remain
  regression-tested.
- **Solver-to-proof recovery:** strict/zero-margin interpolation, rational
  reconstruction, exact target repair, and charge-block LDL convert numerical
  duals into independently replayable mathematical witnesses.
- **Exact thermodynamic upper engine:** integer FLINT contraction extends the
  same rational MPS from 1,000 to 16,000 sites and reduces its independently
  measured upper gap by 3.20x.
- **Sprint-extension prototype:** fixed-point residuals, RDM Hermiticity/trace/PSD,
  local-spectrum bounds, staged D10/D14 promotion, and saved-dual direct freeze
  concentrate deep certification on physically valid, reproducible candidates.
  These research-workspace prototypes are provenance-documented separately and
  are outside the current formal self-contained certificate package.
- **Calibration frontier:** 27 compact certificates cover nine anisotropies and
  three levels, allowing endpoint-by-endpoint analysis of symmetry, RG depth,
  and upper construction.

### Challenge requirements

Issue #230 defines success as Bethe containment at every level plus improvement
over the best normalization-matched published rigorous Heisenberg-chain bound at
the top computable level. It separately defines valid but wider intervals and
constraint-family profiling as a useful **hope signal**. Every published level
passes containment, and this PR delivers that complete calibration dataset. The
`3e-4` sprint target is an internal engineering gate; the official record gate
is the literature comparison above.

### Audited deliverables

- Chinese technical report: Markdown, LaTeX, and visually audited PDF;
- exact-decimal `certificate-summary.csv` and `record-gate.json`;
- SHA-256 `DATA_MANIFEST.txt`;
- 1k–16k `upper-contraction-frontier.csv` with provenance;
- `SPRINT_EXTENSION_PROVENANCE.txt` defining the research-prototype boundary;
- four paired PDF/PNG evidence figures;
- independent verifier, certificate schema, tests, and reproduction commands.

The fast implementation/equivalence suite completes with `118 passed` and five
expected numerical-solver accuracy warnings in candidate-generation tests. All
27 compact certificates audit successfully, with monotone lower and upper
envelopes.

The selected level-47 payload has SHA-256
`1f7c684b3c2f62506f9b30f11e80197045f26a3cfcf464b608f1d2cab998e0c7`.
Its full clean-checkout verification completed with `PASS` in 2256.59 seconds,
with peak memory 180,289,536 bytes. Bethe values are reserved for the final
containment test, preserving an auditable separation between search and proof.
`DATA_MANIFEST.txt` uses a documented four-column format and is validated by
`tests/test_delivery.py`.

### Reproduce

```bash
cd tracks/polyopt/solutions/WangTheoPhys/issue230
python3 -m venv .venv
.venv/bin/pip install -e . pytest
.venv/bin/pytest -q --ignore=tests/test_published_outputs.py
.venv/bin/xxzcert verify \
  outputs/final/xxx_best/level_47_rg_d6_mps_d32_block_1000.json
```

Delivers the hope-signal calibration objective of #230 and establishes a
reusable proof-producing foundation for the normalization-matched record gate.
