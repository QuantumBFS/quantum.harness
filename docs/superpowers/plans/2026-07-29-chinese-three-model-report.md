# Chinese Three-Model Central-Charge Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a fully localized Simplified Chinese HTML/PDF edition of the existing three-model central-charge report while preserving the English edition.

**Architecture:** Keep `analysis.sources` and the typed report blocks as the shared scientific data boundary. Add an explicit locale contract, a separate contextual Chinese content model, locale-aware renderers and comparison plots, and atomic per-language build/verification paths. English remains the default and retains its current filenames.

**Tech Stack:** Python 3, pytest, Matplotlib, NumPy, ReportLab, Pillow, pypdf, HTML/CSS, frozen JSON/CSV/PNG model artifacts.

## Global Constraints

- The English artifacts remain `output/html/three-model-central-charge-report.html` and `output/pdf/three-model-central-charge-report.pdf`.
- The Chinese artifacts are `output/html/three-model-central-charge-report-zh.html` and `output/pdf/three-model-central-charge-report-zh.pdf`.
- The Chinese edition uses Simplified Chinese and `lang="zh-CN"`.
- All reader-facing plot text is Chinese; formal bibliographic data and executable Rust/Python code remain in their original form.
- Both editions load the same frozen model results through `analysis/sources.py`; numerical values must never be independently retyped.
- The current Nishimori evidence is explicitly limited to `L = 4, 6, 8, 10, 12, 14`.
- Missing CJK fonts, changed source fingerprints, missing localized images, or failed verification abort publication.
- A Chinese-only build cannot modify the English artifacts.
- Keep the default command behavior English-only for backward compatibility.
- Use test-driven development and commit after each independently testable task.

---

## File Structure

### New files

- `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/locale.py`
  Defines immutable English and Chinese locale metadata and language lookup.
- `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/report_model_zh.py`
  Builds the complete contextual Simplified Chinese `ReportDocument`.
- `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/source_plots_zh.py`
  Reconstructs all 17 model-specific figures with Chinese labels from frozen
  processed/raw data, without running Monte Carlo.
- `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_locale.py`
  Tests language lookup and fixed-label completeness.
- `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_report_model_zh.py`
  Tests Chinese structure, scientific values, terminology, code preservation, and current width declaration.
- `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_localized_plots.py`
  Tests deterministic Chinese generation of all 21 report figures.
- `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_bilingual_build.py`
  Tests `en`, `zh`, and `all` build behavior and publication isolation.

### Modified files

- `analysis/comparison_plots.py`
  Accepts locale metadata, discovers a CJK plot font, and localizes four comparison charts.
- `analysis/html_renderer.py`
  Uses locale metadata for HTML language, chrome, numbering, labels, and result strip.
- `analysis/pdf_renderer.py`
  Uses locale metadata for all visible labels and uses CJK fonts for all Chinese prose styles.
- `analysis/verify_outputs.py`
  Verifies the appropriate section titles and labels for each locale.
- `build_report.py`
  Adds `--language en|zh|all`, isolated plot directories, output names, and atomic locale builds.
- `tests/conftest.py`
  Adds Chinese plot/report fixtures without changing the English fixture.
- `tests/test_renderers.py`
  Preserves English regression tests and adds focused renderer checks that belong beside existing tests.
- `README.md`
  Documents bilingual build commands, outputs, data scope, and font behavior.
- `Makefile`
  Adds explicit English, Chinese, and all-language build targets and safe cleanup paths.

---

### Task 1: Define the Locale Contract

**Files:**

- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/locale.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_locale.py`

**Interfaces:**

- Consumes: no project-local interface.
- Produces: `ReportLocale`, `EN_LOCALE`, `ZH_LOCALE`, and `get_locale(language: str) -> ReportLocale`.

- [ ] **Step 1: Write failing locale-contract tests**

```python
import pytest

from analysis.locale import EN_LOCALE, ZH_LOCALE, get_locale


def test_locale_lookup_is_explicit_and_complete():
    assert get_locale("en") is EN_LOCALE
    assert get_locale("zh") is ZH_LOCALE
    assert ZH_LOCALE.html_lang == "zh-CN"
    assert ZH_LOCALE.output_suffix == "-zh"
    assert ZH_LOCALE.labels["contents"] == "目录"
    assert ZH_LOCALE.labels["figure"] == "图"
    assert ZH_LOCALE.labels["table"] == "表"
    assert ZH_LOCALE.labels["section"] == "第"
    assert EN_LOCALE.output_suffix == ""


def test_locale_lookup_rejects_unknown_language():
    with pytest.raises(ValueError, match="unsupported report language"):
        get_locale("fr")


def test_locales_define_all_renderer_labels():
    required = {
        "technical_report", "abstract", "contents", "section",
        "figure", "table", "interpretation_limit",
        "clean_result", "nishimori_result", "weak_result",
        "footer_date", "header_title", "header_team",
    }
    assert required <= EN_LOCALE.labels.keys()
    assert required <= ZH_LOCALE.labels.keys()
```

- [ ] **Step 2: Run the tests and confirm the missing-module failure**

Run:

```bash
cd tracks/qmc/solutions/卧龙凤雏/integrated-report
.venv/bin/python -m pytest tests/test_locale.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'analysis.locale'`.

- [ ] **Step 3: Implement immutable locale metadata**

Create the module with this public shape:

```python
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Tuple


@dataclass(frozen=True)
class ReportLocale:
    code: str
    html_lang: str
    output_suffix: str
    plot_directory: str
    labels: Mapping[str, str]
    section_titles: Tuple[str, ...]
    pdf_subject: str
    pdf_creator: str


EN_SECTION_TITLES = (
    "Executive Summary",
    "Conceptual Foundation",
    "Shared Computational Architecture",
    "Clean Ising Model",
    "Nishimori Random-Bond Ising Model",
    "Weak Self-Dual Majorana Network",
    "Cross-Model Comparison",
    "Error and Sensitivity Analysis",
    "Implementation and Reproducibility",
    "Conclusions",
    "Appendices",
)

ZH_SECTION_TITLES = (
    "执行摘要",
    "概念基础",
    "共享计算架构",
    "纯净 Ising 模型",
    "Nishimori 随机键 Ising 模型",
    "弱自对偶 Majorana 网络",
    "跨模型比较",
    "误差与敏感性分析",
    "实现与可复现性",
    "结论",
    "附录",
)
```

Use `MappingProxyType` for both label mappings. English values reproduce all
current renderer strings. Chinese values use:

```python
{
    "technical_report": "技术报告",
    "abstract": "摘要",
    "contents": "目录",
    "section": "第",
    "figure": "图",
    "table": "表",
    "interpretation_limit": "解读边界",
    "clean_result": "纯净 Ising 蒙特卡洛",
    "nishimori_result": "Nishimori",
    "weak_result": "弱自对偶",
    "footer_date": "冻结数据报告 · 2026 年 7 月 29 日",
    "header_title": "中心荷的三条验证路径",
    "header_team": "卧龙凤雏团队",
}
```

`get_locale` must normalize only surrounding whitespace and lowercase:

```python
def get_locale(language: str) -> ReportLocale:
    key = language.strip().lower()
    try:
        return {"en": EN_LOCALE, "zh": ZH_LOCALE}[key]
    except KeyError as error:
        raise ValueError(f"unsupported report language: {language}") from error
```

- [ ] **Step 4: Run the focused and existing tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_locale.py tests/test_report_model.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the locale contract**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/locale.py \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_locale.py
git commit -m "feat: define bilingual report locale contract"
```

---

### Task 2: Make the HTML and PDF Renderers Locale-Aware

**Files:**

- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/html_renderer.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/pdf_renderer.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_renderers.py`

**Interfaces:**

- Consumes: `ReportLocale`, `EN_LOCALE`, and the existing `ReportDocument`.
- Produces:
  - `render_html(report: ReportDocument, destination: Path, locale: ReportLocale = EN_LOCALE) -> Path`
  - `render_pdf(report: ReportDocument, destination: Path, locale: ReportLocale = EN_LOCALE) -> Path`
  - `_register_fonts(locale: ReportLocale) -> Dict[str, str]`

- [ ] **Step 1: Add failing renderer-localization tests**

Add a compact two-section Chinese report fixture directly in
`test_renderers.py`, using one paragraph, one table, and one figure from an
existing fixture image. Assert:

```python
html = render_html(chinese_report, tmp_path / "zh.html", ZH_LOCALE).read_text("utf-8")
assert '<html lang="zh-CN">' in html
assert '<div class="toc-title">目录</div>' in html
assert "第 01 节" in html
assert "<strong>图 1.</strong>" in html
assert "<strong>表 1.</strong>" in html
assert "解读边界" in html
assert "Contents" not in html
assert "Interpretation limit" not in html

pdf = render_pdf(chinese_report, tmp_path / "zh.pdf", ZH_LOCALE)
text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf).pages)
assert "摘要" in text
assert "目录" in text
assert "中文段落用于检查字体和文本提取" in text
assert "Figure" not in text
assert "Table" not in text
```

Retain the existing calls without a locale to prove English remains the
default.

- [ ] **Step 2: Run the renderer tests and confirm signature/label failures**

Run:

```bash
.venv/bin/python -m pytest tests/test_renderers.py -q
```

Expected: new tests fail because both render functions accept only two
arguments and fixed English labels remain.

- [ ] **Step 3: Localize HTML chrome without changing report blocks**

Add `locale: ReportLocale = EN_LOCALE` to `render_html` and pass it into
`_figure` and `_table`. Replace fixed strings with `locale.labels` and set:

```python
f'<html lang="{html.escape(locale.html_lang)}">'
f'<div class="section-kicker">{_section_label(locale, section_number)}</div>'
f'<div class="toc-title">{html.escape(locale.labels["contents"])}</div>'
```

Implement:

```python
def _section_label(locale: ReportLocale, number: int) -> str:
    if locale.code == "zh":
        return f"第 {number:02d} 节"
    return f"Section {number:02d}"
```

Use locale labels for the hero eyebrow, abstract, ARIA navigation label,
result strip, figure/table prefixes, interpretation limit, and footer. Change
the CSS font stacks to:

```css
--serif: "Songti SC", "STSong", "Noto Serif CJK SC", Iowan Old Style, Georgia, serif;
--sans: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", Inter, sans-serif;
```

Do not translate block content inside the renderer.

- [ ] **Step 4: Register and apply CJK fonts throughout the Chinese PDF**

Pass `locale` through `render_pdf`, `_styles`, `_title_page`, `_figure`,
`_table`, and `_header_footer`. Use an `onPage` closure:

```python
def on_page(canvas, document):
    _header_footer(canvas, document, locale, fonts)
```

For `zh`, try the existing macOS candidates in deterministic order:

```python
(
    (Path("/System/Library/Fonts/STHeiti Medium.ttc"), 0),
    (Path("/System/Library/Fonts/Hiragino Sans GB.ttc"), 0),
    (Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"), 0),
)
```

Register the first usable font as `IntegratedCJK`. If none succeeds, raise:

```python
raise RuntimeError("no usable CJK font found for Chinese PDF rendering")
```

For Chinese output set `body`, `bold`, `italic`, `serif`, `serif_bold`, and
`cjk` to `IntegratedCJK`; keep `mono="Courier"` so executable code remains
monospaced. English keeps the existing font mapping.

Localize title-page labels, result-strip names, section kickers, figure/table
prefixes, interpretation limits, header/footer strings, document subject, and
creator. Set CJK fonts with `canvas.setFont(fonts["body"], size)` in the
Chinese header/footer.

- [ ] **Step 5: Run renderer and English regression tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_renderers.py tests/test_locale.py -q
```

Expected: all pass, including deterministic English PDF bytes.

- [ ] **Step 6: Commit localized renderers**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/html_renderer.py \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/pdf_renderer.py \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_renderers.py
git commit -m "feat: localize HTML and PDF report renderers"
```

---

### Task 3: Generate All 21 Report Figures in Chinese

**Files:**

- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/comparison_plots.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/source_plots_zh.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_localized_plots.py`

**Interfaces:**

- Consumes: `Sequence[ModelResult]`, `ReportLocale`.
- Produces:
  - `build_comparison_plots(models, output_dir, locale: ReportLocale = EN_LOCALE) -> Dict[str, Path]`
  - `build_chinese_source_plots(repo_root: Path, output_dir: Path) -> Dict[Tuple[str, str], Path]`

- [ ] **Step 1: Write failing localized-plot tests**

Use a monkeypatch around each plotting function or inspect Matplotlib axes
before `_save` closes the figure. Assert the Chinese call uses these exact
reader-facing strings:

```python
ZH_SHORT_NAMES = ("纯净 Ising", "Nishimori", "弱自对偶")

expected = {
    "中心荷或有效中心荷",
    "三种中心荷验证",
    "估计值及 95% 置信区间",
    "基准目标值",
    "（估计值 − 目标值）/ 标准误",
    "相对各模型基准值的偏差",
    "名义 95% 区间",
    "95% 区间半宽",
    "报告精度",
    "记录的端到端运行时间（秒）",
    "冻结工作流运行时间",
    "精度与运行时间相关，但并不等价",
    "必需科学门控覆盖情况",
    "通过必需门控",
    "模型专属的其他检查",
    "通过",
    "不适用",
    "失败",
}
```

Also build twice into two temporary directories and assert corresponding PNG
bytes are identical. Assert an English call still produces the existing
English labels.

Add a second test that calls `build_chinese_source_plots`, requires exactly the
17 stable `(model_slug, filename)` keys listed below, verifies every file is a
valid PNG of useful size, and confirms deterministic bytes across two builds:

```python
expected = {
    ("clean-ising", "free_energy_scaling.png"),
    ("clean-ising", "central_charge_comparison.png"),
    ("clean-ising", "energy_vs_k.png"),
    ("clean-ising", "integration_convergence.png"),
    ("clean-ising", "fit_stability.png"),
    ("clean-ising", "replica_diagnostics.png"),
    ("nishimori-ising", "free_energy_fit.png"),
    ("nishimori-ising", "central_charge_bootstrap.png"),
    ("nishimori-ising", "fit_window_stability.png"),
    ("nishimori-ising", "sampling_stability.png"),
    ("nishimori-ising", "nishimori_energy_identity.png"),
    ("nishimori-ising", "negative_bond_frequency.png"),
    ("weak-self-dual", "finite-size-scaling.png"),
    ("weak-self-dual", "residuals.png"),
    ("weak-self-dual", "fit-stability.png"),
    ("weak-self-dual", "convergence-ess.png"),
    ("weak-self-dual", "self-duality.png"),
}
assert set(paths) == expected
assert all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in paths.values())
assert all(path.stat().st_size > 20_000 for path in paths.values())
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
MPLCONFIGDIR=/tmp/integrated-report-mpl \
  .venv/bin/python -m pytest tests/test_localized_plots.py -q
```

Expected: failure because `build_comparison_plots` does not accept a locale.

- [ ] **Step 3: Add locale-specific chart copy**

Define a `PlotCopy` frozen dataclass or immutable dictionaries containing all
titles, axes, legends, category names, state labels, and short model names.
Select copy by `locale.code`. Replace every fixed English string in the four
plot functions, including `PASS`, `N/A`, and `FAIL`.

The numeric arrays, colors, axes limits, marker types, confidence intervals,
and output basenames remain identical across languages.

- [ ] **Step 4: Add explicit Chinese plot-font discovery**

For `zh`, select the first usable font from the same CJK candidates as the PDF
and construct `matplotlib.font_manager.FontProperties(fname=str(path))`.
Apply its family name through `rcParams["font.family"]`. Set:

```python
plt.rcParams["axes.unicode_minus"] = False
```

Raise `RuntimeError("no usable CJK font found for Chinese plots")` if discovery
fails. Keep the current DejaVu Sans style for English.

- [ ] **Step 5: Reconstruct the 17 model-specific figures from frozen data**

`source_plots_zh.py` reads only the approved result directories:

```python
CLEAN_RUN = Path("tracks/qmc/results/clean-ising-20260729-120302")
NISHIMORI_RUN = Path("tracks/qmc/results/nishimori-ising-20260729-refinement1")
WEAK_RUN = Path("tracks/qmc/results/weak-self-dual-20260729-154737")
```

Load clean data from `processed/free_energies.csv`,
`processed/central_charge_fits.csv`, `processed/energy_vs_k.csv`,
`processed/diagnostics.csv`, and `processed/analysis_metadata.json`. Recover
the nested-grid central charge deterministically by applying the clean Ising
fit design matrix `[L, 1/L, 1/L³]` at `L_min=6` to the stored nested
free-energy column `g_mc_65`, then convert the fitted `1/L` coefficient
`β₁` with `c = 6β₁/π`; because the fit is linear, this equals the mean of the
corresponding fitted bootstrap draws. Load Nishimori data from
`processed/summary.json`,
`processed/central_charge_bootstrap.csv`, and `processed/free_energy.csv`.
Load weak-self-dual data from `processed/summary.json`,
`processed/finite_size.csv`, and `processed/fit_variants.csv`.

Reproduce the plotting mathematics, limits, target bands, error bars, and
stable filenames in the three existing model `analysis/plots.py` modules. Do
not rerun any Rust binary or resample Monte Carlo trajectories. Replace every
reader-facing title, axis, tick label, legend, and annotation with Simplified
Chinese. Mathematical symbols such as `L`, `K`, `c_eff`, `γ₁`, `ESS`, and
z-scores remain symbols.

Write files beneath:

```text
generated/zh/clean-ising/
generated/zh/nishimori-ising/
generated/zh/weak-self-dual/
```

Use fixed figure dimensions, DPI, metadata, ordering, and the shared explicit
CJK font helper so repeated builds are byte deterministic.

- [ ] **Step 6: Run plot tests and inspect generated glyph warnings**

Run:

```bash
MPLCONFIGDIR=/tmp/integrated-report-mpl \
  .venv/bin/python -W error::UserWarning -m pytest \
  tests/test_localized_plots.py tests/test_comparison_plots.py -q
```

Expected: all tests pass without missing-glyph warnings.

- [ ] **Step 7: Commit localized plots**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/comparison_plots.py \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/source_plots_zh.py \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_localized_plots.py
git commit -m "feat: localize all three-model report charts"
```

---

### Task 4: Author the Complete Chinese Scientific Content Model

**Files:**

- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/report_model_zh.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_report_model_zh.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/conftest.py`

**Interfaces:**

- Consumes: the shared block classes from `analysis.report_model`,
  `Sequence[ModelResult]`, and Chinese plots under `generated/zh`.
- Produces: `build_report_zh(models: Sequence[ModelResult]) -> ReportDocument`.

- [ ] **Step 1: Write failing Chinese report-model tests**

```python
from analysis.locale import ZH_SECTION_TITLES
from analysis.report_model import CodeBlock
from analysis.report_model_zh import build_report_zh


def test_chinese_report_has_complete_structure(models):
    report = build_report_zh(models)
    assert tuple(section.title for section in report.sections) == ZH_SECTION_TITLES
    assert report.title == "中心荷的三条验证路径"
    assert "纯净 Ising、Nishimori 无序与弱自对偶 Majorana 动力学" in report.subtitle


def test_chinese_report_preserves_frozen_science(models):
    text = build_report_zh(models).plain_text()
    for value in ("0.498739", "0.499424", "0.456469", "0.444107"):
        assert value in text
    assert "0.522" in text
    assert "0.464" in text
    assert "L = 4, 6, 8, 10, 12, 14" in text
    assert "已完成 L = 16" not in text


def test_chinese_model_is_detailed_and_has_no_placeholders(models):
    text = build_report_zh(models).plain_text()
    assert len(text) >= 18000
    for placeholder in ("TBD", "TODO", "FIXME", "lorem ipsum", "待补充"):
        assert placeholder.lower() not in text.lower()


def test_code_remains_traceable_to_original_sources(models):
    report = build_report_zh(models)
    code = "\n".join(
        block.code
        for section in report.sections
        for block in section.blocks
        if isinstance(block, CodeBlock)
    )
    assert "for site in 0..L:" in code
    assert "for replica in disorder_replicas:" in code
    assert "Gamma = vacuum_covariance(L)" in code
```

Add a fixture that builds Chinese comparison plots in `generated/zh` and then
returns `build_report_zh(models)`.

- [ ] **Step 2: Run the focused tests and confirm the missing-module failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_report_model_zh.py -q
```

Expected: collection fails because `analysis.report_model_zh` does not exist.

- [ ] **Step 3: Build the Chinese document skeleton and source checks**

Import the shared `Paragraph`, `Equation`, `Figure`, `Table`, `Callout`,
`CodeBlock`, `PageBreak`, `Section`, and `ReportDocument` classes. Implement
the same exact model-set guard as English:

```python
required = {"clean-ising", "nishimori-ising", "weak-self-dual"}
if set(indexed) != required:
    raise ValueError("中文版综合报告必须且只能包含三个已批准模型")
```

Return the eleven sections in `ZH_SECTION_TITLES` order. Keep slugs unchanged
so navigation and downstream lookup remain stable.

- [ ] **Step 4: Translate all eleven sections contextually**

Port every English block from `report_model.py` into the corresponding Chinese
section. Preserve:

- every `Equation.expression` and equation number;
- every source-derived f-string value and numeric precision;
- every table row carrying parameters, gates, estimates, intervals, or hashes;
- every `CodeBlock.code` string exactly;
- every figure basename and block order;
- all source paths and provenance identifiers;
- bibliography title, journal, volume, page, and year fields.

Translate section titles, paragraphs, equation explanations, figure alt text,
captions, interpretation limits, table titles/columns/notes, callout text, code
titles, and code explanations. Use the approved first-use form for key terms:

```text
中心荷（central charge）
有效中心荷（effective central charge，c_eff）
有限尺寸标度（finite-size scaling）
淬火无序（quenched disorder）
分层配对自助法（hierarchical paired bootstrap）
Rao–Blackwell 化条件熵估计量
```

Translate `PASS`, `Required`, and explanatory gate-status prose as “通过” and
“必需”, while leaving stable internal gate names in code/provenance contexts.

All comparison figures in the Chinese model point to
`Path("generated/zh/<basename>.png")`. Every model-specific figure points to
`Path("generated/zh/<model-slug>/<basename>.png")`. No English-labeled frozen
PNG is embedded in the Chinese report.

- [ ] **Step 5: Make the current Nishimori scope explicit**

In the Nishimori parameter table and finite-size discussion include this exact
declaration:

```text
本报告当前使用的圆柱宽度为 L = 4, 6, 8, 10, 12, 14；更大宽度的模拟尚未纳入本版冻结数据。
```

Do not claim results for `L=16` or `L=18`.

- [ ] **Step 6: Run Chinese model and shared source tests**

Run:

```bash
MPLCONFIGDIR=/tmp/integrated-report-mpl \
  .venv/bin/python -m pytest \
  tests/test_report_model_zh.py tests/test_report_model.py tests/test_sources.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit the Chinese content model**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/report_model_zh.py \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_report_model_zh.py \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/conftest.py
git commit -m "feat: author Chinese three-model scientific report"
```

---

### Task 5: Add Locale-Specific Verification and Atomic Build Modes

**Files:**

- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/verify_outputs.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/build_report.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_bilingual_build.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_renderers.py`

**Interfaces:**

- Consumes: `get_locale`, `build_report`, `build_report_zh`, locale-aware
  comparison plots, `build_chinese_source_plots`, and locale-aware renderers.
- Produces:
  - `verify_html(path: Path, locale: ReportLocale = EN_LOCALE) -> VerificationResult`
  - `verify_pdf(path: Path, locale: ReportLocale = EN_LOCALE) -> VerificationResult`
  - `build(repo_root: Path = DEFAULT_REPO_ROOT, language: str = "en") -> BuildResult`
  - `build_all(repo_root: Path = DEFAULT_REPO_ROOT) -> Tuple[BuildResult, BuildResult]`

- [ ] **Step 1: Write failing verifier and build-mode tests**

Test locale-specific output paths and isolation:

```python
def test_chinese_build_writes_only_chinese_outputs(repo_root):
    english_html = repo_root / "output/html/three-model-central-charge-report.html"
    english_pdf = repo_root / "output/pdf/three-model-central-charge-report.pdf"
    before = (english_html.read_bytes(), english_pdf.read_bytes())

    result = build(repo_root, language="zh")

    assert result.html.name == "three-model-central-charge-report-zh.html"
    assert result.pdf.name == "three-model-central-charge-report-zh.pdf"
    assert result.html_verification.passed
    assert result.pdf_verification.passed
    assert (english_html.read_bytes(), english_pdf.read_bytes()) == before


def test_all_build_returns_english_then_chinese(repo_root):
    results = build_all(repo_root)
    assert [item.language for item in results] == ["en", "zh"]
    assert all(item.html.exists() and item.pdf.exists() for item in results)
```

Extend `BuildResult` with `language: str`. Add verifier tests requiring Chinese
section titles, `lang="zh-CN"`, headline values, at least 20 images, extracted
Chinese PDF text, and absence of fixed English chrome.

- [ ] **Step 2: Run the new tests and confirm API failures**

Run:

```bash
MPLCONFIGDIR=/tmp/integrated-report-mpl \
  .venv/bin/python -m pytest \
  tests/test_bilingual_build.py tests/test_renderers.py -q
```

Expected: failures because `build` has no language argument and verifiers are
English-only.

- [ ] **Step 3: Parameterize artifact verification**

Replace fixed `SECTION_TITLES` use with `locale.section_titles`. Retain the
shared headline values. Chinese HTML checks additionally require
`<html lang="zh-CN">`, `目录`, `图 1.`, and `表 1.`. Chinese PDF checks require
extractable `摘要`, `目录`, and every Chinese section title.

Make PDF page limits locale-specific:

```python
minimum_pages, maximum_pages = (25, 45) if locale.code == "zh" else (25, 35)
```

This allows natural Chinese reflow while still detecting missing or runaway
content.

- [ ] **Step 4: Implement atomic per-language builds**

Resolve a locale with `get_locale(language)`, reject `all` in the single-build
function, and select the model builder:

```python
report_builder = build_report_zh if locale.code == "zh" else build_report
plot_dir = PACKAGE_ROOT / "generated" / locale.plot_directory
stem = f"three-model-central-charge-report{locale.output_suffix}"
```

Generate plots, build the report, render both temporary outputs with the
locale, verify both with the locale, recheck the source fingerprint, then
atomically replace only that locale's destinations. Return:

For `zh`, call `build_chinese_source_plots(root, plot_dir)` before building the
content model. The generated directory must contain all 21 localized plots
(four comparison plus seventeen model-specific). English continues to use the
approved frozen model-specific PNGs and the existing four generated comparison
plots.

```python
BuildResult(
    language=locale.code,
    html=html_output,
    pdf=pdf_output,
    html_verification=html_result,
    pdf_verification=pdf_result,
)
```

Implement `build_all` as ordered calls for `en` then `zh`. The CLI parser uses
`choices=("en", "zh", "all")`; `all` invokes `build_all`, and each result is
printed with its language.

- [ ] **Step 5: Run bilingual build tests**

Run:

```bash
MPLCONFIGDIR=/tmp/integrated-report-mpl \
  .venv/bin/python -m pytest \
  tests/test_bilingual_build.py tests/test_renderers.py -q
```

Expected: all pass.

- [ ] **Step 6: Run the entire package test suite**

Run:

```bash
MPLCONFIGDIR=/tmp/integrated-report-mpl \
  .venv/bin/python -m pytest -q
```

Expected: all tests pass; no English regression fails.

- [ ] **Step 7: Commit bilingual build and verification**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/verify_outputs.py \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/build_report.py \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_bilingual_build.py \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_renderers.py
git commit -m "feat: build and verify bilingual report artifacts"
```

---

### Task 6: Document, Build, and Visually Verify the Chinese Edition

**Files:**

- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/README.md`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/Makefile`
- Create/update generated artifact:
  `output/html/three-model-central-charge-report-zh.html`
- Create/update generated artifact:
  `output/pdf/three-model-central-charge-report-zh.pdf`

**Interfaces:**

- Consumes: completed bilingual build pipeline.
- Produces: documented commands, final Chinese HTML/PDF, rendered QA images,
  hashes, and final verification evidence.

- [ ] **Step 1: Add build targets and safe cleanup**

Keep `build` equivalent to English. Add:

```make
build-en:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python build_report.py --language en

build-zh:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python build_report.py --language zh

build-all:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python build_report.py --language all
```

Update `.PHONY`. Extend `clean-generated` only with explicit report-package
paths such as `generated/en/*.png`, `generated/zh/*.png`, and
`tmp/pdfs/three-model-central-charge-report-zh-*.png`. Do not delete anything
under `tracks/qmc/results`.

- [ ] **Step 2: Document bilingual behavior**

Update the README introduction to say the package builds English and Simplified
Chinese editions. Document:

```bash
make build-en
make build-zh
make build-all
```

List all four stable outputs. State that the Chinese report uses current
Nishimori widths `L = 4, 6, 8, 10, 12, 14`, and that larger-width simulations
are not part of this frozen dataset. Explain that Chinese PDF/plot builds
require a detected CJK font and fail explicitly otherwise.

- [ ] **Step 3: Run the full automated suite**

Run:

```bash
cd tracks/qmc/solutions/卧龙凤雏/integrated-report
MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python -m pytest -q
```

Expected: every test passes.

- [ ] **Step 4: Build both language editions from the same source state**

Run:

```bash
MPLCONFIGDIR=/tmp/integrated-report-mpl \
  .venv/bin/python build_report.py --language all
```

Expected: four output paths are reported; both verifiers pass; Chinese PDF page
count is between 25 and 45.

- [ ] **Step 5: Verify determinism and file identity boundaries**

Record SHA-256 hashes, build `--language zh` again, and verify:

- the two Chinese hashes are unchanged;
- the two English hashes are unchanged by the Chinese-only build;
- neither HTML contains network dependencies;
- the Chinese HTML embeds at least 20 PNGs.

Use:

```bash
shasum -a 256 \
  output/html/three-model-central-charge-report.html \
  output/pdf/three-model-central-charge-report.pdf \
  output/html/three-model-central-charge-report-zh.html \
  output/pdf/three-model-central-charge-report-zh.pdf
```

- [ ] **Step 6: Render every Chinese PDF page**

Use the PDF skill's Poppler workflow:

```bash
mkdir -p tmp/pdfs/three-model-central-charge-report-zh
pdftoppm -png -r 130 \
  ../../../../../output/pdf/three-model-central-charge-report-zh.pdf \
  tmp/pdfs/three-model-central-charge-report-zh/page
```

Adjust the relative output path from the package root if necessary by resolving
it with `pwd` before running. Create contact sheets in bounded groups, inspect
every page, then inspect suspicious pages individually at original resolution.
Check all Chinese glyphs, tables, equations, code blocks, captions, page
headers/footers, and image labels.

- [ ] **Step 7: Inspect the self-contained Chinese HTML**

Open the local `-zh.html` through the in-app browser. Check desktop and narrow
viewport layouts, table horizontal scrolling, contents navigation, all
embedded plots, Chinese labels, and absence of broken images. If the in-app
browser is unavailable, record the tool failure and perform deterministic DOM,
asset, and screenshot checks with the best available local renderer.

- [ ] **Step 8: Fix visual defects and rerun relevant checks**

For any discovered defect, first add a regression assertion where practical,
then make the smallest renderer/content/style adjustment. Rerun the focused
test, the full suite, the bilingual build, and the affected visual inspection.
Do not alter scientific values to solve layout problems.

- [ ] **Step 9: Commit documentation and verified artifacts**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report/README.md \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/Makefile \
  output/html/three-model-central-charge-report-zh.html \
  output/pdf/three-model-central-charge-report-zh.pdf
git commit -m "docs: publish verified Chinese central-charge report"
```

- [ ] **Step 10: Perform final repository verification**

Run:

```bash
git status --short
git log -8 --oneline
MPLCONFIGDIR=/tmp/integrated-report-mpl \
  tracks/qmc/solutions/卧龙凤雏/integrated-report/.venv/bin/python \
  -m pytest tracks/qmc/solutions/卧龙凤雏/integrated-report/tests -q
```

Expected: clean worktree and all tests pass. Report the final Chinese paths,
page count, embedded-image count, test count, current Nishimori width scope,
visual-QA result, and four SHA-256 hashes.
