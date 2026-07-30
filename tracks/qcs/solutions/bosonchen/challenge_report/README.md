# Final challenge report

This directory contains the submission-ready report for challenge issue #162.
It leads with the verified 10.8×–27.9× online decoding improvement and 30/30
paired logical-prediction agreement against a provenance-audited upstream
Tesseract baseline. It also separates this substantial current result from the
larger full-suite statistical campaign that remains future validation work.

Regenerate all report figures, the evidence manifest, `report.json`, and the
self-contained `report.html` from the canonical result JSON:

```bash
python3 tracks/qcs/solutions/bosonchen/challenge_report/build_report.py
```

Files:

- `report.html` — single-file offline report with embedded figures;
- `report.json` — structured input to the repository report renderer;
- `run.json` — compact machine-readable challenge outcome;
- `evidence_manifest.json` — source paths, hashes, binary provenance, and claim
  status;
- `assets/` — deterministic SVG inputs retained so the HTML can be regenerated.

The raw experiment JSON and the independent official-binary baseline audit
remain under `../tesseract_ler_results/`; they are not duplicated here.
