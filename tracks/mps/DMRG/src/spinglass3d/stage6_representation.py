"""Physical Route C/B representation comparison for Stage 6."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import shutil
import time
import tomllib

import numpy as np

from .backend import BackendCase
from .bias import BiasRoute, OverlapBias
from .checkpoint import TrainingCheckpoint
from .jax_biased_backend import JaxBiasedPairBackend
from .jax_vmcrg_backend import JaxVMCRGSamplingBackend
from .jax_vmcrg_backend import build_uniform_target_tokens, decode_token_codes
from .equilibration import observable_iat_ess
from .linear_bias import LinearFeatureBasis
from .science_pilot import (
    SciencePilotSpec,
    load_science_checkpoint,
)
from .pilot import _build_case
from .stage6 import load_terminal_science_manifest
from .templates import TemplateEncoder
from .tensor_train import LocalTensorTrain, SymmetricLocalTT
from .vmcrg import (
    CheckpointContext,
    FrozenEvaluation,
    ImprovementAssessment,
    TrainingStep,
    FrozenRouteBatch,
    VMCRGProtocol,
    VMCRGTrainer,
    classify_tt_improvement,
    evaluate_frozen_bias,
    evaluate_frozen_linear,
)


TRACK_ROOT = Path(__file__).resolve().parents[2]


def _exact_keys(value: object, expected: set[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{name} keys differ from the frozen protocol")
    return value


def _integer(value: object, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _positive(value: object, name: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (result < 0.0 if allow_zero else result <= 0.0):
        raise ValueError(f"{name} is outside its finite positive domain")
    return result


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(f"{name} must be a nonempty string array")
    result = tuple(value)
    if len(result) != len(set(result)):
        raise ValueError(f"{name} entries must be unique")
    return result


def _integers(value: object, name: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a nonempty integer array")
    result = tuple(_integer(item, name, 1) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"{name} entries must be unique")
    return result


@dataclass(frozen=True)
class Stage6RepresentationConfig:
    source: Path
    pilot_config: Path
    length: int
    target_temperature: float
    rg_level: int
    train_j: int
    validation_j: int
    test_j: int
    templates: tuple[str, ...]
    cube_routes: tuple[str, ...]
    cross_routes: tuple[str, ...]
    chis: tuple[int, ...]
    initializations: int
    c1_steps: int
    c2_steps: int
    c3_steps: int
    draw_count: int
    sweeps_per_batch: int
    linear_learning_rate: float
    tt_learning_rate: float
    gradient_clip: float
    canonicalize_every: int
    momentum: float
    checkpoint_every: int
    equilibration_sweeps: int
    proposal_measurement_sweeps: int
    wall_budget_seconds: float
    measurement_cadence: int
    bootstrap_replicates: int
    material_regression: float
    initialization_seed: int
    evaluation_seed: int
    bootstrap_seed: int

    @property
    def disorder_count(self) -> int:
        return self.train_j + self.validation_j + self.test_j


@dataclass(frozen=True)
class PhysicalTrainingResult:
    bias: OverlapBias
    trainer: VMCRGTrainer
    records: tuple[TrainingStep, ...]
    checkpoint: Path
    target_temperature_index: int


@dataclass(frozen=True)
class PhysicalFrozenSample:
    batch: FrozenRouteBatch
    actual_wall_seconds: float
    sweeps_per_j: int


@dataclass(frozen=True)
class PhysicalCandidateAssessment:
    template: str
    route: str
    chi: int
    initialization_index: int
    initialization_hash: str
    parameter_count: int
    split: str
    proposal: ImprovementAssessment
    wall: ImprovementAssessment

    def __post_init__(self) -> None:
        if self.template not in {"cube", "cross"}:
            raise ValueError("physical candidate template is invalid")
        if self.route not in {"C", "B"}:
            raise ValueError("physical candidate route is invalid")
        if self.route == "C" and self.template != "cube":
            raise ValueError("physical Route C is cube-specific")
        if self.chi not in {2, 4, 8} or self.initialization_index < 0:
            raise ValueError("physical candidate rank or initialization is invalid")
        if not self.initialization_hash or self.parameter_count < 1:
            raise ValueError("physical candidate identity is incomplete")
        if self.split not in {"validation", "test"}:
            raise ValueError("physical candidate assessment split is invalid")

    @property
    def passed(self) -> bool:
        return (
            self.proposal.classification == "PASS"
            and self.wall.classification == "PASS"
        )


@dataclass(frozen=True)
class RepresentationValidationSelection:
    classification: str
    template: str | None
    route: str | None
    chi: int | None
    initialization_index: int | None
    initialization_hash: str | None
    parameter_count: int | None
    passing_initializations: tuple[int, ...]
    reason: str

    def __post_init__(self) -> None:
        if self.classification not in {"VALIDATION_SELECTED", "SCIENTIFIC_NEGATIVE"}:
            raise ValueError("representation validation classification is invalid")
        selected = self.classification == "VALIDATION_SELECTED"
        values = (
            self.template,
            self.route,
            self.chi,
            self.initialization_index,
            self.initialization_hash,
            self.parameter_count,
        )
        if selected != all(value is not None for value in values):
            raise ValueError("representation validation selection is incomplete")
        if selected and not self.passing_initializations:
            raise ValueError("selected representation has no passing initializations")
        if not self.reason:
            raise ValueError("representation validation reason is missing")


@dataclass(frozen=True)
class RepresentationSelection:
    classification: str
    template: str | None
    route: str | None
    chi: int | None
    initialization_index: int | None
    initialization_hash: str | None
    parameter_count: int | None
    validation_initializations: tuple[int, ...]
    test_passed: bool
    reason: str

    def __post_init__(self) -> None:
        if self.classification not in {"PASS", "SCIENTIFIC_NEGATIVE"}:
            raise ValueError("representation selection classification is invalid")
        if not self.reason:
            raise ValueError("representation selection reason is missing")

    def as_pilot_selection(self) -> dict[str, object]:
        return {
            "classification": self.classification,
            "route": self.route,
            "template": self.template,
            "chi": self.chi,
            "selected_initialization": self.initialization_index,
            "initialization_hash": self.initialization_hash,
            "parameter_count": self.parameter_count,
            "validation_initializations": list(self.validation_initializations),
            "test_passed": self.test_passed,
            "mps_beats_conditioned_linear": self.classification == "PASS",
            "held_out_metric": "whole_j_uniform_target_q_moment_mse",
            "fair_budgets": ["proposal", "wall"],
            "reason": self.reason,
        }


def load_equilibrated_physical_case(
    spec: SciencePilotSpec,
    output: str | Path,
) -> BackendCase:
    """Restore one passing unbiased science cell as a physical training start."""

    manifest = load_terminal_science_manifest(spec, output)
    progress = manifest.get("progress")
    if not isinstance(progress, dict) or progress.get("phase") != "complete":
        raise ValueError("science cell is not complete physical input")
    checkpoint_index = progress.get("checkpoint_index")
    if isinstance(checkpoint_index, bool) or not isinstance(checkpoint_index, int):
        raise ValueError("science cell terminal checkpoint index is invalid")
    checkpoint = (
        Path(output)
        / "checkpoints"
        / f"checkpoint-{checkpoint_index:09d}"
    )
    backend_case = _build_case(spec.calibration_spec)
    from .jax_backend import JaxParallelTemperingBackend

    backend = JaxParallelTemperingBackend(backend_case)
    restored = load_science_checkpoint(
        backend,
        checkpoint,
        expected_spec_sha256=spec.sha256,
    )
    if restored.phase != "complete" or restored.measurement_completed != spec.measurement_sweeps:
        raise ValueError("science checkpoint does not contain the completed measurement phase")
    return BackendCase(
        spins=backend.spins,
        bonds=backend.case.bonds,
        betas=backend.case.betas,
        seed=backend.case.seed,
    )


def _initial_sampling_bias(
    route: BiasRoute,
    tt: SymmetricLocalTT,
    basis: LinearFeatureBasis,
) -> OverlapBias:
    if route is BiasRoute.C_LINEAR_PLUS_TT:
        zero_tt = SymmetricLocalTT(
            LocalTensorTrain([np.zeros_like(core) for core in tt.model.cores]),
            tt.encoder,
        )
        return OverlapBias(
            route,
            basis,
            np.zeros(len(basis.features), dtype=np.float64),
            zero_tt,
        )
    return OverlapBias(route, None, np.empty(0, dtype=np.float64), tt)


def _latest_training_checkpoint(root: Path) -> Path | None:
    candidates = sorted(
        path
        for path in root.glob("step-*")
        if path.is_dir()
        and (path / "metadata.json").is_file()
        and (path / "model.npz").is_file()
        and (path / "state.npz").is_file()
    )
    return candidates[-1] if candidates else None


def train_physical_route(
    cases: tuple[BackendCase, ...],
    j_ids: tuple[str, ...],
    *,
    kind: str,
    route: BiasRoute | str,
    chi: int,
    initialization_seed: int,
    protocol: VMCRGProtocol,
    draw_count: int,
    sweeps_per_batch: int,
    target_temperature: float,
    hashes: dict[str, str],
    j_split: dict[str, tuple[str, ...]],
    checkpoint_root: str | Path,
    checkpoint_every: int,
    resume: bool,
) -> PhysicalTrainingResult:
    """Train one real Route C/B bias with complete sampler checkpoints."""

    if not cases or len(cases) != len(j_ids) or len(j_ids) != len(set(j_ids)):
        raise ValueError("physical training requires one unique ordered J ID per case")
    if checkpoint_every < 1:
        raise ValueError("physical training checkpoint cadence must be positive")
    encoder = TemplateEncoder(kind, conditioned=True, rg_level=1)
    selected_route = BiasRoute(route)
    if selected_route is BiasRoute.C_LINEAR_PLUS_TT and kind != "cube":
        raise ValueError("Route C conditioned linear comparator is cube-specific")
    basis = LinearFeatureBasis.cube_v1()
    model = LocalTensorTrain.random(encoder.token_count, int(chi), initialization_seed)
    tt = SymmetricLocalTT(model, encoder)
    initial_bias = _initial_sampling_bias(selected_route, tt, basis)
    raw_backends = tuple(
        JaxBiasedPairBackend(case, initial_bias, required_platform="cpu")
        for case in cases
    )
    reference_betas = cases[0].betas
    if any(not np.array_equal(case.betas, reference_betas) for case in cases[1:]):
        raise ValueError("physical representation cases must share one selected ladder")
    temperature_index = int(
        np.argmin(np.abs(1.0 / reference_betas - float(target_temperature)))
    )
    adapter = JaxVMCRGSamplingBackend(
        j_ids=j_ids,
        backends=raw_backends,
        draw_count=int(draw_count),
        target_temperature_index=temperature_index,
        sweeps_per_batch=int(sweeps_per_batch),
        seed=int(initialization_seed) + 1_000_003,
    )
    effective_protocol = protocol
    if selected_route is BiasRoute.B_CONDITIONED_TT:
        effective_protocol = VMCRGProtocol(
            c1_steps=0,
            c2_steps=protocol.c1_steps + protocol.c2_steps + protocol.c3_steps,
            c3_steps=0,
            linear_learning_rate=protocol.linear_learning_rate,
            tt_learning_rate=protocol.tt_learning_rate,
            gradient_clip=protocol.gradient_clip,
            canonicalize_every=protocol.canonicalize_every,
            momentum=protocol.momentum,
        )
    context = CheckpointContext(
        beta=adapter.target_beta,
        hashes=hashes,
        j_split=j_split,
        rg_level=1,
    )
    root = Path(checkpoint_root)
    root.mkdir(parents=True, exist_ok=True)
    trainer = VMCRGTrainer(
        effective_protocol,
        basis,
        tt,
        adapter,
        route=selected_route,
        checkpoint_context=context,
        failure_checkpoint_root=root / "failures",
    )
    if resume:
        latest = _latest_training_checkpoint(root)
        if latest is None:
            raise FileNotFoundError("no complete physical training checkpoint is available")
        trainer.restore(TrainingCheckpoint.load(latest), context=context)
    elif _latest_training_checkpoint(root) is not None:
        raise FileExistsError("physical training checkpoints exist; explicit resume required")

    records: list[TrainingStep] = []
    while trainer.step_index < trainer.maximum_steps:
        record = trainer.step()
        records.append(record)
        if (
            trainer.step_index % int(checkpoint_every) == 0
            or trainer.step_index == trainer.maximum_steps
        ):
            checkpoint = root / f"step-{trainer.step_index:06d}"
            trainer.checkpoint_from_context().save(checkpoint)
            complete = sorted(
                path
                for path in root.glob("step-*")
                if path.is_dir() and (path / "metadata.json").is_file()
            )
            for stale in complete[:-2]:
                shutil.rmtree(stale)
        print(
            f"representation route={selected_route.value} template={kind} chi={chi} "
            f"step={trainer.step_index}/{trainer.maximum_steps} "
            f"gradient={record.clipped_gradient_norm:.6g}",
            flush=True,
        )
    latest = _latest_training_checkpoint(root)
    if latest is None:
        raise RuntimeError("physical training completed without a checkpoint")
    return PhysicalTrainingResult(
        bias=trainer.sampling_bias(),
        trainer=trainer,
        records=tuple(records),
        checkpoint=latest,
        target_temperature_index=temperature_index,
    )


def sample_frozen_physical_route(
    cases: tuple[BackendCase, ...],
    j_ids: tuple[str, ...],
    bias: OverlapBias,
    *,
    target_temperature_index: int,
    split: str,
    budget_kind: str,
    equilibration_sweeps: int,
    proposal_measurement_sweeps: int,
    wall_budget_seconds: float,
    measurement_cadence: int,
    seed: int,
) -> PhysicalFrozenSample:
    """Draw one immutable held-out route batch under proposal or wall matching."""

    if not cases or len(cases) != len(j_ids) or len(j_ids) != len(set(j_ids)):
        raise ValueError("frozen physical sampling requires unique whole-J cases")
    if split not in {"validation", "test"}:
        raise ValueError("frozen physical sampling split is invalid")
    if budget_kind not in {"proposal", "wall"}:
        raise ValueError("frozen physical sampling budget is invalid")
    if equilibration_sweeps < 0 or proposal_measurement_sweeps < 1:
        raise ValueError("frozen physical sweep counts are invalid")
    if measurement_cadence < 1 or wall_budget_seconds <= 0.0:
        raise ValueError("frozen physical cadence and wall budget must be positive")
    if not 0 <= int(target_temperature_index) < cases[0].betas.size:
        raise ValueError("frozen physical target temperature is outside the ladder")
    backends = tuple(
        JaxBiasedPairBackend(case, bias, required_platform="cpu")
        for case in cases
    )
    for backend in backends:
        backend.run_sweeps(int(equilibration_sweeps))
    proposed_before = tuple(backend.proposed_changes for backend in backends)
    accepted_before = tuple(backend.accepted_changes for backend in backends)
    rng = np.random.default_rng(seed)
    rows_by_j: list[list[np.ndarray]] = [[] for _ in backends]
    started = time.perf_counter()
    sweeps_per_j = 0

    def one_round() -> None:
        nonlocal sweeps_per_j
        for index, backend in enumerate(backends):
            backend.run_sweeps(int(measurement_cadence))
            codes = backend.token_codes[
                :, int(target_temperature_index), :
            ].reshape(-1)
            pool = decode_token_codes(codes, backend.token_count)
            selected = int(rng.integers(0, pool.shape[0]))
            rows_by_j[index].append(pool[selected].copy())
        sweeps_per_j += int(measurement_cadence)

    if budget_kind == "proposal":
        while sweeps_per_j < int(proposal_measurement_sweeps):
            one_round()
    else:
        while True:
            one_round()
            if time.perf_counter() - started >= float(wall_budget_seconds):
                break
    actual_wall = time.perf_counter() - started
    biased = np.asarray(rows_by_j, dtype=np.int8)
    if biased.ndim != 3 or biased.shape[1] < 2:
        raise ValueError("frozen physical sampling produced too few retained draws")
    target = build_uniform_target_tokens(
        biased,
        bias.tt.encoder.q_token_indices,
        rng,
    )
    proposal_count = sum(
        backend.proposed_changes - before
        for backend, before in zip(backends, proposed_before, strict=True)
    )
    accepted_count = sum(
        backend.accepted_changes - before
        for backend, before in zip(backends, accepted_before, strict=True)
    )
    if proposal_count < 1:
        raise ValueError("frozen physical sampling made no proposals")
    q_indices = np.asarray(bias.tt.encoder.q_token_indices, dtype=np.int64)
    summaries: list[dict[str, float | int | str]] = []
    for rows in biased:
        series = np.mean(rows[:, q_indices], axis=1, dtype=np.float64)
        elapsed = max(actual_wall / len(j_ids), np.finfo(float).eps)
        if series.size < 4:
            # The FFT/Sokal estimator needs four retained draws.  Tiny smoke or
            # wall-matched batches still need finite, fail-closed metadata, so
            # count the whole short chain as one effective observation.
            summaries.append(
                {
                    "samples": int(series.size),
                    "tau_int": float(series.size / 2.0),
                    "window": 0,
                    "window_rule": "short_chain_conservative",
                    "ess": 1.0,
                    "elapsed_seconds": float(elapsed),
                    "ess_per_second": float(1.0 / elapsed),
                }
            )
        else:
            summaries.append(observable_iat_ess(series, elapsed))
    batch = FrozenRouteBatch(
        target=target,
        biased=biased,
        j_ids=j_ids,
        split=split,
        budget_kind=budget_kind,
        proposal_count=int(proposal_count),
        wall_seconds=(
            float(wall_budget_seconds)
            if budget_kind == "wall"
            else max(actual_wall, np.finfo(float).eps)
        ),
        acceptance=float(accepted_count / proposal_count),
        iat=max(float(summary["tau_int"]) for summary in summaries),
        ess=min(float(summary["ess"]) for summary in summaries),
    )
    return PhysicalFrozenSample(
        batch=batch,
        actual_wall_seconds=actual_wall,
        sweeps_per_j=sweeps_per_j,
    )


def conditioned_linear_bias(training: PhysicalTrainingResult) -> OverlapBias:
    """Extract the frozen Route C linear comparator with an exactly zero TT."""

    if (
        not isinstance(training, PhysicalTrainingResult)
        or training.bias.route is not BiasRoute.C_LINEAR_PLUS_TT
        or training.bias.basis is None
        or training.bias.tt.encoder.kind.value != "cube"
    ):
        raise ValueError("conditioned linear control requires trained cube Route C")
    zero_tt = SymmetricLocalTT(
        LocalTensorTrain(
            [np.zeros_like(core) for core in training.bias.tt.model.cores]
        ),
        training.bias.tt.encoder,
    )
    return OverlapBias(
        BiasRoute.C_LINEAR_PLUS_TT,
        training.bias.basis,
        training.bias.coefficients,
        zero_tt,
    )


def evaluate_physical_sample(
    sample: PhysicalFrozenSample,
    bias: OverlapBias,
    *,
    linear_control: bool,
    initialization_hash: str | None = None,
) -> FrozenEvaluation:
    """Convert one frozen physical sample into the shared evaluation schema."""

    if not isinstance(sample, PhysicalFrozenSample) or not isinstance(bias, OverlapBias):
        raise TypeError("physical sample and bias are required")
    if linear_control:
        if (
            bias.route is not BiasRoute.C_LINEAR_PLUS_TT
            or bias.basis is None
            or np.any(
                np.concatenate(
                    [np.asarray(core).reshape(-1) for core in bias.tt.model.cores]
                )
                != 0.0
            )
        ):
            raise ValueError("linear evaluation requires an exactly zero-TT control")
        return evaluate_frozen_linear(
            bias.basis,
            bias.coefficients,
            bias.tt.encoder,
            sample.batch,
        )
    if not initialization_hash:
        raise ValueError("MPS evaluation requires its initialization hash")
    return evaluate_frozen_bias(
        bias,
        sample.batch,
        initialization_hash=initialization_hash,
    )


def assess_physical_candidate(
    baseline: tuple[FrozenEvaluation, ...],
    candidate: tuple[FrozenEvaluation, ...],
    *,
    template: str,
    chi: int,
    initialization_index: int,
    parameter_count: int,
    seed: int,
    bootstrap_replicates: int,
    material_regression: float,
) -> PhysicalCandidateAssessment:
    """Apply paired whole-J tests under both frozen fairness budgets."""

    baseline_by_budget = {item.budget_kind: item for item in baseline}
    candidate_by_budget = {item.budget_kind: item for item in candidate}
    budgets = ("proposal", "wall")
    if (
        len(baseline_by_budget) != len(baseline)
        or len(candidate_by_budget) != len(candidate)
        or set(baseline_by_budget) != set(budgets)
        or set(candidate_by_budget) != set(budgets)
    ):
        raise ValueError("physical comparison requires one evaluation per fair budget")
    route_names = {item.route_name for item in candidate}
    splits = {item.split for item in (*baseline, *candidate)}
    initialization_hashes = {item.initialization_hash for item in candidate}
    if (
        {item.route_name for item in baseline} != {"linear"}
        or len(route_names) != 1
        or next(iter(route_names)) not in {"C", "B"}
        or len(splits) != 1
        or len(initialization_hashes) != 1
        or None in initialization_hashes
    ):
        raise ValueError("physical comparison identities or splits are inconsistent")
    route = next(iter(route_names))
    split = next(iter(splits))
    assessments: dict[str, ImprovementAssessment] = {}
    for budget_index, budget in enumerate(budgets):
        control = baseline_by_budget[budget]
        model = candidate_by_budget[budget]
        if control.j_ids != model.j_ids:
            raise ValueError("physical comparison requires identical ordered J IDs")
        if budget == "proposal" and control.proposal_count != model.proposal_count:
            raise ValueError("physical proposal budgets do not match")
        if budget == "wall" and not math.isclose(
            control.wall_seconds,
            model.wall_seconds,
            abs_tol=1e-12,
            rel_tol=0.0,
        ):
            raise ValueError("physical wall budgets do not match")
        assessments[budget] = classify_tt_improvement(
            control.primary_metric_by_j - model.primary_metric_by_j,
            other_metric_regression=(
                model.other_metric_by_j - control.other_metric_by_j
            ),
            seed=int(seed) + 17 * budget_index,
            bootstrap_replicates=int(bootstrap_replicates),
            material_regression=float(material_regression),
        )
    return PhysicalCandidateAssessment(
        template=template,
        route=route,
        chi=int(chi),
        initialization_index=int(initialization_index),
        initialization_hash=str(next(iter(initialization_hashes))),
        parameter_count=int(parameter_count),
        split=split,
        proposal=assessments["proposal"],
        wall=assessments["wall"],
    )


def select_validation_candidate(
    candidates: tuple[PhysicalCandidateAssessment, ...],
    config: Stage6RepresentationConfig,
) -> RepresentationValidationSelection:
    """Select the cheapest stable family, preserving Route C as primary."""

    if not isinstance(config, Stage6RepresentationConfig):
        raise TypeError("representation config is required")
    expected = {
        (template, route, chi, initialization)
        for template in config.templates
        for route in (
            config.cube_routes if template == "cube" else config.cross_routes
        )
        for chi in config.chis
        for initialization in range(config.initializations)
    }
    observed = {
        (item.template, item.route, item.chi, item.initialization_index)
        for item in candidates
    }
    if len(observed) != len(candidates) or observed != expected:
        raise ValueError("validation candidate matrix is incomplete or duplicated")
    if any(item.split != "validation" for item in candidates):
        raise ValueError("model selection may consume validation evidence only")

    families: list[tuple[str, str, int, int, tuple[PhysicalCandidateAssessment, ...]]] = []
    for template, route, chi in sorted({key[:3] for key in expected}):
        members = tuple(
            sorted(
                (
                    item
                    for item in candidates
                    if (item.template, item.route, item.chi)
                    == (template, route, chi)
                ),
                key=lambda item: item.initialization_index,
            )
        )
        parameter_counts = {item.parameter_count for item in members}
        if len(parameter_counts) != 1:
            raise ValueError("representation family parameter counts are inconsistent")
        if all(item.passed for item in members):
            families.append(
                (template, route, chi, next(iter(parameter_counts)), members)
            )

    primary = [family for family in families if family[1] == "C"]
    fallback = [family for family in families if family[1] == "B"]
    eligible = primary if primary else fallback
    if not eligible:
        return RepresentationValidationSelection(
            classification="SCIENTIFIC_NEGATIVE",
            template=None,
            route=None,
            chi=None,
            initialization_index=None,
            initialization_hash=None,
            parameter_count=None,
            passing_initializations=(),
            reason="no preregistered family passed both budgets in every initialization",
        )
    template, route, chi, parameter_count, members = min(
        eligible,
        key=lambda value: (value[3], value[2], value[0]),
    )
    chosen = members[0]
    return RepresentationValidationSelection(
        classification="VALIDATION_SELECTED",
        template=template,
        route=route,
        chi=chi,
        initialization_index=chosen.initialization_index,
        initialization_hash=chosen.initialization_hash,
        parameter_count=parameter_count,
        passing_initializations=tuple(
            item.initialization_index for item in members
        ),
        reason=(
            "lowest-parameter passing Route C family"
            if route == "C"
            else "Route C failed; lowest-parameter passing Route B fallback"
        ),
    )


def finalize_representation_selection(
    validation: RepresentationValidationSelection,
    test: PhysicalCandidateAssessment | None,
) -> RepresentationSelection:
    """Open the test split once for the deterministic validation selection."""

    if validation.classification == "SCIENTIFIC_NEGATIVE":
        if test is not None:
            raise ValueError("test evidence cannot rescue a failed validation selection")
        return RepresentationSelection(
            classification="SCIENTIFIC_NEGATIVE",
            template=None,
            route=None,
            chi=None,
            initialization_index=None,
            initialization_hash=None,
            parameter_count=None,
            validation_initializations=(),
            test_passed=False,
            reason=validation.reason,
        )
    if test is None or test.split != "test":
        raise ValueError("selected representation requires one held-out test assessment")
    expected = (
        validation.template,
        validation.route,
        validation.chi,
        validation.initialization_index,
        validation.initialization_hash,
        validation.parameter_count,
    )
    observed = (
        test.template,
        test.route,
        test.chi,
        test.initialization_index,
        test.initialization_hash,
        test.parameter_count,
    )
    if observed != expected:
        raise ValueError("test assessment does not match the frozen validation choice")
    passed = test.passed
    return RepresentationSelection(
        classification="PASS" if passed else "SCIENTIFIC_NEGATIVE",
        template=validation.template,
        route=validation.route,
        chi=validation.chi,
        initialization_index=validation.initialization_index,
        initialization_hash=validation.initialization_hash,
        parameter_count=validation.parameter_count,
        validation_initializations=validation.passing_initializations,
        test_passed=passed,
        reason=(
            validation.reason + "; held-out test passed both budgets"
            if passed
            else validation.reason + "; held-out test failed at least one budget"
        ),
    )


def load_stage6_representation_config(
    path: str | Path,
) -> Stage6RepresentationConfig:
    """Load the exact physical comparison protocol without silent reductions."""

    source = Path(path).resolve()
    with source.open("rb") as handle:
        raw = tomllib.load(handle)
    _exact_keys(
        raw,
        {
            "schema_version",
            "stage",
            "scope",
            "sources",
            "physical",
            "split",
            "models",
            "training",
            "evaluation",
            "seeds",
        },
        "Stage 6 representation top level",
    )
    if raw["schema_version"] != 1 or raw["stage"] != "stage6" or raw["scope"] != (
        "physical_conditioned_vmcrg_representation_comparison"
    ):
        raise ValueError("Stage 6 representation identity is invalid")
    sources = _exact_keys(raw["sources"], {"stage6_pilot"}, "representation sources")
    physical = _exact_keys(
        raw["physical"],
        {"length", "target_temperature", "rg_level"},
        "representation physical",
    )
    split = _exact_keys(
        raw["split"],
        {"train_j", "validation_j", "test_j"},
        "representation split",
    )
    models = _exact_keys(
        raw["models"],
        {"templates", "cube_routes", "cross_routes", "chis", "initializations"},
        "representation models",
    )
    training = _exact_keys(
        raw["training"],
        {
            "c1_steps",
            "c2_steps",
            "c3_steps",
            "draw_count",
            "sweeps_per_batch",
            "linear_learning_rate",
            "tt_learning_rate",
            "gradient_clip",
            "canonicalize_every",
            "momentum",
            "checkpoint_every",
        },
        "representation training",
    )
    evaluation = _exact_keys(
        raw["evaluation"],
        {
            "equilibration_sweeps",
            "proposal_measurement_sweeps",
            "wall_budget_seconds",
            "measurement_cadence",
            "bootstrap_replicates",
            "material_regression",
        },
        "representation evaluation",
    )
    seeds = _exact_keys(
        raw["seeds"],
        {"initialization", "evaluation", "bootstrap"},
        "representation seeds",
    )
    pilot_value = sources["stage6_pilot"]
    if pilot_value != "config/hard_goal/stage6_pilot_v1.toml":
        raise ValueError("representation protocol must bind the fixed Stage 6 pilot")
    pilot = (TRACK_ROOT / str(pilot_value)).resolve()
    fixed = {
        "physical.length": (physical["length"], 12),
        "physical.target_temperature": (physical["target_temperature"], 1.10),
        "physical.rg_level": (physical["rg_level"], 1),
        "split.train_j": (split["train_j"], 32),
        "split.validation_j": (split["validation_j"], 16),
        "split.test_j": (split["test_j"], 16),
        "models.templates": (models["templates"], ["cube", "cross"]),
        "models.cube_routes": (models["cube_routes"], ["C", "B"]),
        "models.cross_routes": (models["cross_routes"], ["B"]),
        "models.chis": (models["chis"], [2, 4, 8]),
        "models.initializations": (models["initializations"], 2),
        "training.c1_steps": (training["c1_steps"], 24),
        "training.c2_steps": (training["c2_steps"], 48),
        "training.c3_steps": (training["c3_steps"], 0),
        "training.draw_count": (training["draw_count"], 16),
        "training.sweeps_per_batch": (training["sweeps_per_batch"], 4),
        "training.linear_learning_rate": (training["linear_learning_rate"], 0.01),
        "training.tt_learning_rate": (training["tt_learning_rate"], 0.002),
        "training.gradient_clip": (training["gradient_clip"], 0.1),
        "training.canonicalize_every": (training["canonicalize_every"], 8),
        "training.momentum": (training["momentum"], 0.9),
        "training.checkpoint_every": (training["checkpoint_every"], 4),
        "evaluation.equilibration_sweeps": (evaluation["equilibration_sweeps"], 512),
        "evaluation.proposal_measurement_sweeps": (
            evaluation["proposal_measurement_sweeps"],
            1024,
        ),
        "evaluation.wall_budget_seconds": (evaluation["wall_budget_seconds"], 600.0),
        "evaluation.measurement_cadence": (evaluation["measurement_cadence"], 4),
        "evaluation.bootstrap_replicates": (evaluation["bootstrap_replicates"], 2000),
        "evaluation.material_regression": (evaluation["material_regression"], 0.0),
        "seeds.initialization": (seeds["initialization"], 2026073601),
        "seeds.evaluation": (seeds["evaluation"], 2026073602),
        "seeds.bootstrap": (seeds["bootstrap"], 2026073101),
    }
    for name, (actual, expected) in fixed.items():
        if actual != expected:
            raise ValueError(f"{name} differs from the frozen value {expected!r}")
    momentum = _positive(training["momentum"], "training.momentum", allow_zero=True)
    if momentum >= 1.0:
        raise ValueError("training.momentum must lie in [0,1)")
    material = _positive(
        evaluation["material_regression"],
        "evaluation.material_regression",
        allow_zero=True,
    )
    return Stage6RepresentationConfig(
        source=source,
        pilot_config=pilot,
        length=_integer(physical["length"], "physical.length", 3),
        target_temperature=_positive(physical["target_temperature"], "target temperature"),
        rg_level=_integer(physical["rg_level"], "physical.rg_level", 1),
        train_j=_integer(split["train_j"], "split.train_j", 1),
        validation_j=_integer(split["validation_j"], "split.validation_j", 1),
        test_j=_integer(split["test_j"], "split.test_j", 1),
        templates=_strings(models["templates"], "models.templates"),
        cube_routes=_strings(models["cube_routes"], "models.cube_routes"),
        cross_routes=_strings(models["cross_routes"], "models.cross_routes"),
        chis=_integers(models["chis"], "models.chis"),
        initializations=_integer(models["initializations"], "models.initializations", 2),
        c1_steps=_integer(training["c1_steps"], "training.c1_steps"),
        c2_steps=_integer(training["c2_steps"], "training.c2_steps", 1),
        c3_steps=_integer(training["c3_steps"], "training.c3_steps"),
        draw_count=_integer(training["draw_count"], "training.draw_count", 1),
        sweeps_per_batch=_integer(training["sweeps_per_batch"], "training.sweeps_per_batch", 1),
        linear_learning_rate=_positive(training["linear_learning_rate"], "linear learning rate"),
        tt_learning_rate=_positive(training["tt_learning_rate"], "TT learning rate"),
        gradient_clip=_positive(training["gradient_clip"], "gradient clip"),
        canonicalize_every=_integer(training["canonicalize_every"], "canonicalize every", 1),
        momentum=momentum,
        checkpoint_every=_integer(training["checkpoint_every"], "checkpoint every", 1),
        equilibration_sweeps=_integer(evaluation["equilibration_sweeps"], "evaluation equilibration", 1),
        proposal_measurement_sweeps=_integer(
            evaluation["proposal_measurement_sweeps"],
            "proposal measurement sweeps",
            1,
        ),
        wall_budget_seconds=_positive(evaluation["wall_budget_seconds"], "wall budget"),
        measurement_cadence=_integer(evaluation["measurement_cadence"], "measurement cadence", 1),
        bootstrap_replicates=_integer(evaluation["bootstrap_replicates"], "bootstrap replicates", 1),
        material_regression=material,
        initialization_seed=_integer(seeds["initialization"], "initialization seed", 1),
        evaluation_seed=_integer(seeds["evaluation"], "evaluation seed", 1),
        bootstrap_seed=_integer(seeds["bootstrap"], "bootstrap seed", 1),
    )
