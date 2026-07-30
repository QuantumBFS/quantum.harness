"""Validated, immutable inputs for the PRB manuscript."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Mapping


@dataclass(frozen=True)
class Benchmark:
    slug: str
    c_eff: float
    standard_error: float
    ci95: tuple[float, float]
    target: float
    exact_c: float | None
    widths: tuple[int, ...]
    gates: tuple[str, ...]
    source_hashes: Mapping[str, str]


@dataclass(frozen=True)
class LearningResult:
    candidate_phi_pi: float
    xy_bracket: tuple[float, float]
    entanglement_c_eff: float
    entanglement_standard_error: float
    entanglement_ci95: tuple[float, float]
    casimir_c_eff: float
    casimir_standard_error: float
    casimir_ci95: tuple[float, float]
    alpha: float
    alpha_stable: bool
    estimator_agrees: bool
    central_charge_published: bool
    claim_reasons: tuple[str, ...]
    summary_sha256: str
    widths: tuple[int, ...]
    streams: int
    elapsed_s: float
    source_hashes: Mapping[str, str]


@dataclass(frozen=True)
class PaperData:
    clean: Benchmark
    nishimori: Benchmark
    weak: Benchmark
    learning: LearningResult


def load_paper_data(repo_root: Path) -> PaperData:
    """Load all manuscript values through the report's hash-gated adapters."""

    root = Path(repo_root).resolve()
    sources = _load_integrated_sources(root)
    models = sources.load_all_models(root)
    if tuple(model.slug for model in models) != (
        "clean-ising",
        "nishimori-ising",
        "weak-self-dual",
    ):
        raise ValueError("unexpected benchmark model order")

    clean, nishimori, weak = (_benchmark(model) for model in models)
    open_result = sources.load_learning_mit(root)
    if open_result.central_charge_published:
        raise ValueError("learning-MIT source unexpectedly publishes a central charge")
    if open_result.estimator_agrees:
        raise ValueError("learning-MIT source unexpectedly reports estimator agreement")
    if open_result.alpha is None:
        raise ValueError("learning-MIT anisotropy estimate is missing")

    learning = LearningResult(
        candidate_phi_pi=open_result.candidate_phi_pi,
        xy_bracket=open_result.xy_bracket,
        entanglement_c_eff=open_result.entanglement_c_eff,
        entanglement_standard_error=open_result.entanglement_standard_error,
        entanglement_ci95=open_result.entanglement_interval,
        casimir_c_eff=open_result.casimir_c_eff,
        casimir_standard_error=open_result.casimir_standard_error,
        casimir_ci95=open_result.casimir_interval,
        alpha=open_result.alpha,
        alpha_stable=open_result.alpha_stable,
        estimator_agrees=open_result.estimator_agrees,
        central_charge_published=open_result.central_charge_published,
        claim_reasons=open_result.claim_reasons,
        summary_sha256=open_result.summary_sha256,
        widths=open_result.widths,
        streams=open_result.streams,
        elapsed_s=open_result.elapsed_s,
        source_hashes=MappingProxyType(dict(open_result.provenance)),
    )
    return PaperData(clean, nishimori, weak, learning)


def _benchmark(model: object) -> Benchmark:
    failed = [
        gate.name
        for gate in model.gates
        if gate.required and not gate.passed
    ]
    if failed:
        raise ValueError(
            f"{model.slug}: required benchmark gates failed: {', '.join(failed)}"
        )
    table_name = "free_energies" if model.slug == "clean-ising" else "finite_size"
    width_key = "L" if model.slug == "clean-ising" else "width"
    widths = tuple(int(row[width_key]) for row in model.tables[table_name])
    return Benchmark(
        slug=model.slug,
        c_eff=model.estimate,
        standard_error=model.standard_error,
        ci95=model.ci95,
        target=model.target,
        exact_c=model.exact_estimate,
        widths=tuple(dict.fromkeys(widths)),
        gates=tuple(gate.name for gate in model.gates if gate.required),
        source_hashes=MappingProxyType(dict(model.provenance)),
    )


def _load_integrated_sources(repo_root: Path) -> ModuleType:
    path = (
        repo_root
        / "tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/sources.py"
    )
    if not path.is_file():
        raise ValueError(f"integrated source adapter is missing: {path}")
    name = "_prb_integrated_sources"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load integrated source adapter: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
