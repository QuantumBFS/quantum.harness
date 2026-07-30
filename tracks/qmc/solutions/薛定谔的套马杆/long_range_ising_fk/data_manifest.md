# Frozen-data escrow manifest

**Freeze date:** 2026-07-30

**Generation-code revision:** [`26234d49bddd6005398d35361ff98b5efbba6b88`](https://github.com/Luka3519/quantum.harness/commit/26234d49bddd6005398d35361ff98b5efbba6b88)

**Integrity file:** [`data_manifest.sha256`](data_manifest.sha256)

**Integrity-file SHA-256:** `fe2df2015c1d71268b154135f5bb2619d347495e295f43da1331755d1311e0f6`

The generation revision is the first committed snapshot of the code used for
the frozen runs. This submission only relocates that implementation into the
registered team directory and updates repository-relative job paths; it does
not alter the algorithms or frozen numerical values.

## Published datasets

| Dataset | Files | Bytes | SHA-256 tree digest |
|---|---:|---:|---|
| `track_a_20260727` | 489 | 158453 | `8616b64d1540a615cc6fe5cc1ee81914cd88eaebf0c41ebb79b028bf9e527a69` |
| `track_a_large_20260728` | 212 | 60586 | `3d8be845faf51dd49b9a89e0081b2f799c55e99fe7c27f892811d8b3ac7778da` |
| `clock_production_20260729` | 82 | 47539 | `62adfbe29861a9b58fb919f1c141c449c2ab4710f9557356a3c3b68983648160` |
| `track_a_cutoff_analysis_20260730` | 4 | 18791 | `f6ea9fde0f546f9116da624f7c86209e366f499aaa2afd52e5908371e2b30dcb` |
| **Total** | **787** | **285369** | See the integrity-file hash above |

A dataset tree digest is the SHA-256 of its sorted
`<file-sha256><two spaces><relative-path>\n` records. The integrity file
contains all 787 records and uses paths relative to this solution directory.
From this directory, verify the escrow on a Unix-like system with:

```bash
sha256sum -c data_manifest.sha256
```

## Completeness and exclusions

- `track_a_20260727` contains exactly 96 successful `summary.csv`,
  `blocks.csv`, and `metadata.txt` cell triplets, plus frozen analysis and
  scheduler logs.
- `track_a_large_20260728` is an honest cutoff snapshot with 36 successful
  cell triplets. It has 30 central-$\beta_c$ cells and six partial-crossing
  cells; the registered large-size crossing grid is incomplete and is not
  extrapolated.
- `clock_production_20260729` contains exactly 16 successful cell triplets
  and the frozen FK comparison tables.
- `track_a_cutoff_analysis_20260730` contains the combined central data,
  competing-model fits, distinguishable-size forecast, and cutoff report.
- Local smoke tests, timing probes, superseded interim analyses, and incomplete
  pre-production runs are intentionally excluded from the public escrow.

Per-cell metadata records timestamps, host/runtime information, Slurm job and
array-cell identifiers, and validation values. Seeds, autocorrelation
estimates, convergence fields, and raw block observables are retained in the
corresponding summaries and block files.

The cell-level escrow and locked-analysis records were created locally before
the cutoff analysis. Their public packaging occurs in this submission; the
original timestamps and the immutable generation revision are retained so
that an independent adjudicator can audit the chronology.
