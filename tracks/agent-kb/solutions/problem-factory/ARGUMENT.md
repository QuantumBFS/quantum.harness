# The argument — why these results are correct, and why they are useful

> **中文摘要**：本文论证问题工厂两点。**① 结果正确**——求解器过 Bethe 精确解与独立 ED 栈（XDiag）双重验证；判题尺子盲测回认人工精选题集 5/5、杀对照 3/3（含我们自己 Day-1 的偏科题）；gate 生成时冻结，生成侧的判断只作先验不作门禁。**② 结果有用**——首飞 5 卡三种死法被三种独立机制检出（会杀题的筛子才有说服力）；学习闭环让第二轮预算浪费 29%→0%、零死亡；启发式库（10 条）随卡增长，是 issue 点名的交付物。全部结论可一条命令复现（README § Reproduce，已在干净房间全新 clone 验证）。

## 0. The claim under test

Issue #133 bets that problem *selection*, not solving, is the bottleneck of
autonomous research. That claim cannot be tested by agents debating which
problems are good — debate drifts into plausible vagueness. So this factory
replaces judgment-by-debate with **judgment by experiment**: every candidate
problem flies through a rocket-test pipeline and is killed or passed by frozen,
machine-checkable gates. This document is the evidence that the verdicts are
*correct* (§1) and that the system is *useful* (§2).

## 1. Correctness — why the numbers can be trusted

| Layer | Evidence | Where |
|---|---|---|
| Solver physics | ED converges to the Bethe-ansatz ground state E/N = −0.443147 at Δ=1; gap closes ~1/L as required | `pf/ed.py`, oracles in `pf/static_fire.py` |
| Independent stack | Sawtooth closed-form anchors reproduced to 1e-8–1e-10, cross-checked with XDiag (an independent Julia ED stack) | `tests/test_sawtooth.py`, `scripts/xdiag_crosscheck.jl` |
| The judge itself | Calibration gate re-derives the hand-curated #124–#128 quality class **blind**: 5/5 curated accepted, 3/3 controls rejected — including our own Day-1 biased card; held-out test 1/1 pos + 2/2 neg | `run_calibration.py`, `calibration/` |
| Gate discipline | Kill criteria are frozen at generation time (`gate.frozen: true`); generator judgments are recorded as priors (`quality_rationale`, `value_claim`), never used as vetoes; the pipeline re-judges every card independently | `INTERFACE.md` §2, `pf/cards.py` |
| Reproducibility | A fresh clone + fresh venv runs the whole suite green (verified 2026-07-30); a demo rerun reproduces `results/` byte-identically | README § Reproduce |

## 2. Usefulness — what the system demonstrates

1. **Teeth in both directions.** First flight: 1 survivor / 1 deferred / 3
   dead — and the three deaths are caught by *three independent mechanisms*:
   fingerprint dedup, a first-principles oracle (the Bethe energy catches a 4×
   unit-convention error), and a signal-to-noise kill threshold. A filter that
   never kills proves nothing; a filter that kills for one reason proves one
   thing. (`results/report.md`)
2. **The loop closes.** Round 2's fleet was licensed card-by-card by round-1
   heuristics: budget wasted on no-signal launches dropped **29% → 0%** with
   zero deaths, and a deferred card was relaunched at larger sizes on the
   library's own advice. The heuristics library (10 entries, `heuristics/`)
   and its growth curve are a deliverable the issue names explicitly, not an
   implementation detail. (`results/learning_loop.md`)
3. **Generalization beyond the calibration class.** Held-out quality classes
   work end-to-end: issue #112 (map class) solved at reconnaissance scale with
   all six analytic anchors green; issue #148 (TFIM-2D) correctly returned
   *deferred* with a QMC routing recommendation — the factory knows when **not**
   to launch, which is the whole point of a selection system. (`briefs/`)
4. **Meta-level evidence.** Every disagreement between the generator's declared
   priors and the experimental verdicts is logged. That disagreement curve is
   exactly the calibration data issue #133 asks for: *can an agent pick its own
   research problems well?*

## 3. What is not claimed (yet)

- The cards flown so far are hand-seeded. The literature-mining generator
  (teammate's skills) integrates through the frozen `INTERFACE.md` contract —
  cards in, telemetry back, dry-run protocol in §8.
- Issue #133's Tier 2/3 (five new problems solved and peer-reviewed) is future
  work. What this submission delivers is the pipeline, the frozen gates, and
  the evidence trail that makes those tiers meaningful.

## 4. Pointers

Reproduce: README § Reproduce (5 prompts) · Design rationale:
`docs/design/problem-generation.md` · Day-by-day provenance: `log.md` ·
Generator contract: `INTERFACE.md`
