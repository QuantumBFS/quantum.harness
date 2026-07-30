# Frozen-data escrow manifest

**Freeze date:** 2026-07-30

**Generation-code revision:** [`26234d49bddd6005398d35361ff98b5efbba6b88`](https://github.com/Luka3519/quantum.harness/commit/26234d49bddd6005398d35361ff98b5efbba6b88)

**Integrity file:** [`data_manifest.sha256`](data_manifest.sha256)

**Integrity-file SHA-256:** `0e75176346026faa118cdd8abe0af53d0a555bf192d315c0f7c6040b5f6a8cac`

The generation revision is the first committed snapshot of the code used for
the frozen runs. This submission only relocates that implementation into the
registered team directory and updates repository-relative job paths; it does
not alter the algorithms or frozen numerical values.

## Published datasets

| Dataset | Files | Bytes | SHA-256 tree digest |
|---|---:|---:|---|
| `track_a_20260727` | 489 | 158254 | `2b62aba4b833d677d62806f277bf409ed9740546fa026ee90bfed73393c2097b` |
| `track_a_large_20260728` | 212 | 60586 | `3d8be845faf51dd49b9a89e0081b2f799c55e99fe7c27f892811d8b3ac7778da` |
| `clock_production_20260729` | 82 | 47539 | `62adfbe29861a9b58fb919f1c141c449c2ab4710f9557356a3c3b68983648160` |
| `nn_large_20260730` | 83 | 163120 | `b90c35fdab8d3bf9833e2933273a993273e4c572dee01f09bc758f14784bdfe4` |
| `nn_v3_20260730` | 48 | 111568 | `6ee4e59197eb759149f961d340df7708f485ed2d9d777570719d08a9cb56bdde` |
| `track_a_cutoff_analysis_20260730` | 4 | 18791 | `f6ea9fde0f546f9116da624f7c86209e366f499aaa2afd52e5908371e2b30dcb` |
| **Total** | **918** | **559858** | See the integrity-file hash above |

A dataset tree digest is the SHA-256 of its sorted
`<file-sha256><two spaces><relative-path>\n` records. The integrity file
contains all 918 records and uses paths relative to this solution directory.
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
- `nn_large_20260730` is a completed partial nearest-neighbor control
  snapshot with 20 cells: four seeds at each of
  \(L=64,128,256,512,1024\). Every cell contains `summary.csv`, `blocks.csv`,
  `metadata.txt`, and `manifest.json`; \(L=2048,4096\) were still running at
  publication time.
- `nn_v3_20260730` is an independently added higher-statistics
  nearest-neighbor snapshot with 16 completed cell triplets: eight seeds at
  each of \(L=64,128\). Its registered \(L=256\) cells are not present in the
  published snapshot.
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
