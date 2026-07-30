# Bilingual report maintenance

- `track_a_report_zh.md` and `track_a_report_en.md` are a paired report.
- When changing conclusions, numerical values, tables, figure references, or
  captions in either file, inspect the other file and apply the corresponding
  change unless the difference is intentionally language-specific.
- Chinese figures use `figures/<name>.svg`; English figures use the matching
  `figures/<name>_en.svg`.
- Regenerate both figure sets with
  `python3 ../scripts/plot_cutoff_report.py ..` from this directory.
