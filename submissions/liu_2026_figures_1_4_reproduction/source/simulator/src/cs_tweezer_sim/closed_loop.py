"""Serializable ask/tell control protocol with non-rollback batch accounting.

The controller-facing dataclasses in this module contain no executor, program
factory, simulator seed, backend, or truth oracle.  A platform-side
``ClosedLoopOrchestrator`` owns those capabilities and converts parameter
requests into public finite-shot observations.

S4-E transports the same dataclasses through a separate process, but this
module remains responsible for the scientifically important parent-side
checks: canonicalization, candidate binding, compilation, execution,
non-rollback accounting, receipt validation, recommendation validation, and
sanitized failure closure.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Callable, Protocol

from .contracts import (
    Delay,
    ExperimentProgram,
    ExperimentResult,
    Measure,
    ParallelPlay,
    Play,
    Prepare,
)
from .finite_shot import (
    BernoulliArmStatistics,
    KLLUCBEvaluation,
    evaluate_kl_lucb,
)


_CANDIDATE_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.:=+@/-]{0,127}$"
)
_CONTROLLER_FAILURE_CODES = frozenset(
    {
        "controller_crashed",
        "controller_protocol_failed",
        "controller_timeout",
        "controller_transport_failed",
    }
)


def _validate_candidate_id(candidate_id: object) -> str:
    if (
        not isinstance(candidate_id, str)
        or _CANDIDATE_ID_PATTERN.fullmatch(candidate_id) is None
    ):
        raise ValueError("candidate_id is not a safe ASCII identifier")
    return candidate_id


@dataclass(frozen=True)
class PhysicalParameterSpec:
    """One public physical control parameter and its canonicalization."""

    name: str
    unit: str
    lower: float
    upper: float
    initial: float
    period: float | None = None
    quantum: float | None = None

    def __post_init__(self) -> None:
        values = (self.lower, self.upper, self.initial)
        if (
            not self.name
            or not self.unit
            or not all(math.isfinite(value) for value in values)
            or self.lower >= self.upper
            or not self.lower <= self.initial <= self.upper
            or (
                self.period is not None
                and (
                    not math.isfinite(self.period)
                    or self.period <= 0
                    or not math.isclose(
                        self.upper - self.lower,
                        self.period,
                        rel_tol=0.0,
                        abs_tol=1e-12,
                    )
                )
            )
            or (
                self.quantum is not None
                and (not math.isfinite(self.quantum) or self.quantum <= 0)
            )
        ):
            raise ValueError("physical parameter specification is invalid")
        self.canonicalize(self.initial)

    def canonicalize(self, requested: float) -> float:
        """Validate, wrap, and quantize a requested parameter value."""

        if isinstance(requested, bool):
            raise ValueError(f"{self.name} must be a real number, not bool")
        value = float(requested)
        if not math.isfinite(value):
            raise ValueError(f"{self.name} must be finite")
        if self.period is not None:
            value = self.lower + ((value - self.lower) % self.period)
            if math.isclose(
                value, self.upper, rel_tol=0.0, abs_tol=1e-12
            ):
                value = self.lower
        elif not self.lower <= value <= self.upper:
            raise ValueError(
                f"{self.name}={value} is outside [{self.lower}, {self.upper}]"
            )
        if self.quantum is not None:
            index = math.floor(
                (value - self.lower) / self.quantum + 0.5
            )
            value = self.lower + index * self.quantum
            if self.period is not None:
                value = self.lower + ((value - self.lower) % self.period)
            else:
                value = min(self.upper, max(self.lower, value))
        if not self.lower <= value <= self.upper:
            raise ValueError(f"{self.name} canonicalization left its bounds")
        return float(value)


@dataclass(frozen=True)
class CandidatePoint:
    """A controller-visible named parameter vector."""

    candidate_id: str
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        _validate_candidate_id(self.candidate_id)
        if not self.values:
            raise ValueError("candidate id and values must be non-empty")
        if not all(
            not isinstance(value, bool) and math.isfinite(float(value))
            for value in self.values
        ):
            raise ValueError("candidate values must be finite")


@dataclass(frozen=True)
class ClosedLoopProblemDescriptor:
    """JSON-serializable public problem description."""

    name: str
    parameters: tuple[PhysicalParameterSpec, ...]
    expected_outcome: str
    batch_shots: int
    max_tokens: int
    reserved_sequence_time_per_shot_us: float
    candidates: tuple[CandidatePoint, ...] = ()
    candidate_policy: str = "auto"
    recommendation_policy: str = "observed_completed_only"

    def __post_init__(self) -> None:
        if (
            not self.name
            or not self.parameters
            or not self.expected_outcome
            or self.batch_shots <= 0
            or self.max_tokens <= 0
            or not math.isfinite(
                self.reserved_sequence_time_per_shot_us
            )
            or self.reserved_sequence_time_per_shot_us <= 0
        ):
            raise ValueError("closed-loop problem descriptor is invalid")
        names = tuple(parameter.name for parameter in self.parameters)
        if len(names) != len(set(names)):
            raise ValueError("parameter names must be unique")
        ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(ids) != len(set(ids)):
            raise ValueError("candidate ids must be unique")
        if self.candidate_policy == "auto":
            object.__setattr__(
                self,
                "candidate_policy",
                "catalog_only" if self.candidates else "continuous",
            )
        if self.candidate_policy not in {"catalog_only", "continuous"}:
            raise ValueError("candidate_policy is invalid")
        if self.candidate_policy == "catalog_only" and not self.candidates:
            raise ValueError("catalog_only requires at least one candidate")
        if self.recommendation_policy != "observed_completed_only":
            raise ValueError("recommendation_policy is invalid")
        for candidate in self.candidates:
            self.canonicalize(candidate.values)

    @property
    def initial_values(self) -> tuple[float, ...]:
        return tuple(
            parameter.canonicalize(parameter.initial)
            for parameter in self.parameters
        )

    def canonicalize(
        self, values: tuple[float, ...]
    ) -> tuple[float, ...]:
        if len(values) != len(self.parameters):
            raise ValueError("candidate parameter dimension is invalid")
        return tuple(
            parameter.canonicalize(value)
            for parameter, value in zip(self.parameters, values)
        )


@dataclass(frozen=True)
class PublicBudgetView:
    """Controller-visible remaining reserved resources."""

    tokens_remaining: int
    reserved_shots_remaining: int
    reserved_scheduler_time_remaining_us: float


@dataclass(frozen=True)
class CandidateRequest:
    """One controller request; it cannot contain an arbitrary program."""

    candidate_id: str
    requested_values: tuple[float, ...]


@dataclass(frozen=True)
class PublicBatchObservation:
    """Validated public response for one reserved batch token."""

    token_index: int
    candidate_id: str
    requested_values: tuple[float, ...]
    canonical_values: tuple[float, ...]
    canonical_parameter_sha256: str
    program_sha256: str
    status: str
    failure_reason: str
    execution_id: str
    expected_outcome: str
    successes: int
    attempted_shots: int
    valid_shots: int
    retained_shots: int | None
    counts: tuple[tuple[str, int], ...]
    active_sequence_time_us: float
    reserved_scheduler_time_us: float
    request_frame_sha256: str = ""

    @property
    def raw_success_probability(self) -> float | None:
        if self.valid_shots == 0:
            return None
        return self.successes / self.valid_shots


@dataclass(frozen=True)
class ControllerRecommendation:
    candidate_id: str
    canonical_values: tuple[float, ...]
    decision_status: str
    detail: str = ""


@dataclass(frozen=True)
class ClosedLoopLedger:
    tokens_reserved: int
    reserved_shots: int
    attempted_shots: int
    valid_shots: int
    hardware_submissions: int
    active_sequence_time_us: float
    reserved_scheduler_time_us: float
    rejected_submissions: int
    failed_submissions: int
    overrun_submissions: int
    distinct_parameter_hashes: int


@dataclass(frozen=True)
class ClosedLoopRunResult:
    recommendation: ControllerRecommendation | None
    observations: tuple[PublicBatchObservation, ...]
    ledger: ClosedLoopLedger
    run_status: str = "completed"
    controller_failure_code: str = ""
    controller_exitcode: int | None = None


class AskTellController(Protocol):
    """A controller sees messages, never execution capabilities."""

    def ask(
        self,
        problem: ClosedLoopProblemDescriptor,
        budget: PublicBudgetView,
    ) -> CandidateRequest | None:
        ...

    def tell(self, observation: PublicBatchObservation) -> None:
        ...

    def recommend(self) -> ControllerRecommendation:
        ...


class PublicExecutor(Protocol):
    def execute(
        self, program: ExperimentProgram, *, shots: int
    ) -> ExperimentResult:
        ...


def _canonical_parameter_hash(
    problem: ClosedLoopProblemDescriptor,
    values: tuple[float, ...],
) -> str:
    payload = tuple(
        (parameter.name, float(value).hex())
        for parameter, value in zip(problem.parameters, values)
    )
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _request_fingerprint(request: object) -> str:
    """Hash an invalid request without reflecting its values into public JSON."""

    if type(request) is CandidateRequest:
        candidate_id = request.candidate_id
        values = request.requested_values
        payload = (
            type(candidate_id).__name__,
            candidate_id if isinstance(candidate_id, str) else "",
            tuple(repr(value) for value in values)
            if isinstance(values, tuple)
            else (type(values).__name__,),
        )
    else:
        payload = (type(request).__module__, type(request).__qualname__)
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()


def _safe_public_request(
    request: object,
) -> tuple[str, tuple[float, ...]]:
    if type(request) is not CandidateRequest:
        return "", ()
    try:
        candidate_id = _validate_candidate_id(request.candidate_id)
    except (TypeError, ValueError):
        candidate_id = ""
    values = request.requested_values
    if (
        not isinstance(values, tuple)
        or not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for value in values
        )
    ):
        return candidate_id, ()
    return candidate_id, tuple(float(value) for value in values)


def _program_payload(program: ExperimentProgram) -> tuple[object, ...]:
    payload: list[object] = [("name", program.name)]
    for operation in program.operations:
        if isinstance(operation, Play):
            pulse = operation.pulse
            payload.append(
                (
                    "play",
                    operation.channel,
                    operation.targets,
                    float(pulse.duration_us).hex(),
                    float(pulse.amplitude_rad_per_us).hex(),
                    float(pulse.phase_rad).hex(),
                    float(pulse.detuning_rad_per_us).hex(),
                )
            )
        elif isinstance(operation, ParallelPlay):
            payload.append(
                (
                    "parallel",
                    tuple(
                        (
                            play.channel,
                            play.targets,
                            float(play.pulse.duration_us).hex(),
                            float(play.pulse.amplitude_rad_per_us).hex(),
                            float(play.pulse.phase_rad).hex(),
                            float(play.pulse.detuning_rad_per_us).hex(),
                        )
                        for play in operation.plays
                    ),
                )
            )
        elif isinstance(operation, Delay):
            payload.append(
                ("delay", float(operation.duration_us).hex())
            )
        elif isinstance(operation, Prepare):
            payload.append(("prepare", operation.bitstring))
        elif isinstance(operation, Measure):
            payload.append(("measure", operation.basis))
        else:
            payload.append(
                (type(operation).__name__, repr(operation))
            )
    return tuple(payload)


def program_sha256(program: ExperimentProgram) -> str:
    """Stable-in-process digest of a public primitive program."""

    return hashlib.sha256(
        json.dumps(
            _program_payload(program), separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


class _MutableLedger:
    def __init__(self) -> None:
        self.tokens_reserved = 0
        self.reserved_shots = 0
        self.attempted_shots = 0
        self.valid_shots = 0
        self.hardware_submissions = 0
        self.active_sequence_time_us = 0.0
        self.reserved_scheduler_time_us = 0.0
        self.rejected_submissions = 0
        self.failed_submissions = 0
        self.overrun_submissions = 0
        self.parameter_hashes: set[str] = set()

    def snapshot(self) -> ClosedLoopLedger:
        return ClosedLoopLedger(
            tokens_reserved=self.tokens_reserved,
            reserved_shots=self.reserved_shots,
            attempted_shots=self.attempted_shots,
            valid_shots=self.valid_shots,
            hardware_submissions=self.hardware_submissions,
            active_sequence_time_us=self.active_sequence_time_us,
            reserved_scheduler_time_us=self.reserved_scheduler_time_us,
            rejected_submissions=self.rejected_submissions,
            failed_submissions=self.failed_submissions,
            overrun_submissions=self.overrun_submissions,
            distinct_parameter_hashes=len(self.parameter_hashes),
        )


class ClosedLoopOrchestrator:
    """Platform-side owner of compilation, execution, and resource receipts."""

    def __init__(
        self,
        problem: ClosedLoopProblemDescriptor,
        *,
        program_factory: Callable[
            [tuple[float, ...]], ExperimentProgram
        ],
        executor: PublicExecutor,
    ) -> None:
        self._problem = problem
        self._program_factory = program_factory
        self._execute_public = executor.execute
        self._catalog = {
            candidate.candidate_id: problem.canonicalize(candidate.values)
            for candidate in problem.candidates
        }
        self._private_diagnostics: list[tuple[str, str]] = []

    @property
    def private_diagnostics(self) -> tuple[tuple[str, str], ...]:
        """Platform-only exception details, never included in public results."""

        return tuple(self._private_diagnostics)

    def _audit(self, stage: str, exc: BaseException) -> None:
        self._private_diagnostics.append(
            (stage, f"{type(exc).__name__}: {exc}")
        )

    @staticmethod
    def _controller_exitcode(
        controller: AskTellController, exc: BaseException | None = None
    ) -> int | None:
        for source in (exc, controller):
            if source is None:
                continue
            value = getattr(source, "exitcode", None)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        return None

    def _controller_failure_result(
        self,
        *,
        controller: AskTellController,
        stage: str,
        exc: BaseException,
        observations: list[PublicBatchObservation],
        ledger: _MutableLedger,
    ) -> ClosedLoopRunResult:
        self._audit(stage, exc)
        code = getattr(exc, "public_code", "controller_protocol_failed")
        if code not in _CONTROLLER_FAILURE_CODES:
            code = "controller_protocol_failed"
        return ClosedLoopRunResult(
            recommendation=None,
            observations=tuple(observations),
            ledger=ledger.snapshot(),
            run_status="controller_failed",
            controller_failure_code=code,
            controller_exitcode=self._controller_exitcode(controller, exc),
        )

    def _budget_view(self, ledger: _MutableLedger) -> PublicBudgetView:
        remaining = self._problem.max_tokens - ledger.tokens_reserved
        return PublicBudgetView(
            tokens_remaining=remaining,
            reserved_shots_remaining=remaining
            * self._problem.batch_shots,
            reserved_scheduler_time_remaining_us=remaining
            * self._problem.batch_shots
            * self._problem.reserved_sequence_time_per_shot_us,
        )

    def _reserve(self, ledger: _MutableLedger) -> tuple[int, float]:
        if ledger.tokens_reserved >= self._problem.max_tokens:
            raise RuntimeError("batch-token budget exhausted")
        ledger.tokens_reserved += 1
        ledger.reserved_shots += self._problem.batch_shots
        reserved_time = (
            self._problem.batch_shots
            * self._problem.reserved_sequence_time_per_shot_us
        )
        ledger.reserved_scheduler_time_us += reserved_time
        return ledger.tokens_reserved, reserved_time

    def _failed_observation(
        self,
        *,
        token_index: int,
        request: object,
        status: str,
        reason: str,
        reserved_time: float,
        canonical_values: tuple[float, ...] = (),
        parameter_hash: str = "",
        program_hash: str = "",
        execution_id: str = "",
        attempted_shots: int = 0,
        counts: tuple[tuple[str, int], ...] = (),
        active_time: float = 0.0,
    ) -> PublicBatchObservation:
        candidate_id, requested_values = _safe_public_request(request)
        return PublicBatchObservation(
            token_index=token_index,
            candidate_id=candidate_id,
            requested_values=requested_values,
            canonical_values=canonical_values,
            canonical_parameter_sha256=parameter_hash,
            program_sha256=program_hash,
            status=status,
            failure_reason=reason,
            execution_id=execution_id,
            expected_outcome=self._problem.expected_outcome,
            successes=0,
            attempted_shots=attempted_shots,
            valid_shots=0,
            retained_shots=None,
            counts=counts,
            active_sequence_time_us=active_time,
            reserved_scheduler_time_us=reserved_time,
            request_frame_sha256=_request_fingerprint(request),
        )

    def _validate_request(
        self,
        request: object,
        bindings: dict[str, str],
    ) -> tuple[
        CandidateRequest,
        tuple[float, ...],
        str,
    ]:
        if type(request) is not CandidateRequest:
            raise ValueError("controller must return an exact CandidateRequest")
        candidate_id = _validate_candidate_id(request.candidate_id)
        if not isinstance(request.requested_values, tuple):
            raise ValueError("requested_values must be a tuple")
        canonical = self._problem.canonicalize(request.requested_values)
        parameter_hash = _canonical_parameter_hash(self._problem, canonical)

        if self._problem.candidate_policy == "catalog_only":
            expected = self._catalog.get(candidate_id)
            if expected is None or canonical != expected:
                raise ValueError("request does not match the public catalog")
        else:
            previous = bindings.get(candidate_id)
            if previous is not None and previous != parameter_hash:
                raise ValueError("continuous candidate id was rebound")
            bindings.setdefault(candidate_id, parameter_hash)
        return request, canonical, parameter_hash

    def _validate_recommendation(
        self,
        recommendation: object,
        *,
        bindings: dict[str, str],
        observations: list[PublicBatchObservation],
    ) -> ControllerRecommendation:
        if type(recommendation) is not ControllerRecommendation:
            raise ValueError(
                "controller must return an exact ControllerRecommendation"
            )
        candidate_id = _validate_candidate_id(recommendation.candidate_id)
        if (
            not isinstance(recommendation.decision_status, str)
            or not recommendation.decision_status
            or len(recommendation.decision_status.encode("utf-8")) > 128
            or not isinstance(recommendation.detail, str)
            or len(recommendation.detail.encode("utf-8")) > 512
            or not isinstance(recommendation.canonical_values, tuple)
        ):
            raise ValueError("recommendation fields are invalid")
        canonical = self._problem.canonicalize(
            recommendation.canonical_values
        )
        if canonical != tuple(recommendation.canonical_values):
            raise ValueError("recommendation values are not canonical")
        parameter_hash = _canonical_parameter_hash(self._problem, canonical)
        if self._problem.candidate_policy == "catalog_only":
            if self._catalog.get(candidate_id) != canonical:
                raise ValueError("recommendation does not match the catalog")
        elif bindings.get(candidate_id) != parameter_hash:
            raise ValueError("recommendation does not match a bound request")
        if self._problem.recommendation_policy == "observed_completed_only":
            observed = any(
                observation.status == "completed"
                and observation.candidate_id == candidate_id
                and observation.canonical_parameter_sha256 == parameter_hash
                for observation in observations
            )
            if not observed:
                raise ValueError(
                    "recommendation is not backed by a completed observation"
                )
        return ControllerRecommendation(
            candidate_id=candidate_id,
            canonical_values=canonical,
            decision_status=recommendation.decision_status,
            detail=recommendation.detail,
        )

    def run(self, controller: AskTellController) -> ClosedLoopRunResult:
        ledger = _MutableLedger()
        observations: list[PublicBatchObservation] = []
        bindings: dict[str, str] = {}
        self._private_diagnostics = []

        while ledger.tokens_reserved < self._problem.max_tokens:
            try:
                request = controller.ask(
                    self._problem, self._budget_view(ledger)
                )
            except Exception as exc:
                return self._controller_failure_result(
                    controller=controller,
                    stage="controller.ask",
                    exc=exc,
                    observations=observations,
                    ledger=ledger,
                )
            if request is None:
                break
            token_index, reserved_time = self._reserve(ledger)
            try:
                request, canonical, parameter_hash = self._validate_request(
                    request, bindings
                )
                ledger.parameter_hashes.add(parameter_hash)
            except Exception as exc:
                self._audit("candidate.validate", exc)
                ledger.rejected_submissions += 1
                observation = self._failed_observation(
                    token_index=token_index,
                    request=request,
                    status="rejected",
                    reason="invalid_candidate",
                    reserved_time=reserved_time,
                )
                observations.append(observation)
                try:
                    controller.tell(observation)
                except Exception as tell_exc:
                    return self._controller_failure_result(
                        controller=controller,
                        stage="controller.tell",
                        exc=tell_exc,
                        observations=observations,
                        ledger=ledger,
                    )
                continue

            try:
                program = self._program_factory(canonical)
                if not isinstance(program, ExperimentProgram):
                    raise TypeError(
                        "program factory must return ExperimentProgram"
                    )
                program_hash = program_sha256(program)
            except Exception as exc:
                self._audit("program.compile", exc)
                ledger.failed_submissions += 1
                observation = self._failed_observation(
                    token_index=token_index,
                    request=request,
                    status="rejected",
                    reason="program_compile_failed",
                    reserved_time=reserved_time,
                    canonical_values=canonical,
                    parameter_hash=parameter_hash,
                )
                observations.append(observation)
                try:
                    controller.tell(observation)
                except Exception as tell_exc:
                    return self._controller_failure_result(
                        controller=controller,
                        stage="controller.tell",
                        exc=tell_exc,
                        observations=observations,
                        ledger=ledger,
                    )
                continue

            ledger.hardware_submissions += 1
            try:
                result = self._execute_public(
                    program, shots=self._problem.batch_shots
                )
            except Exception as exc:
                self._audit("program.execute", exc)
                ledger.failed_submissions += 1
                observation = self._failed_observation(
                    token_index=token_index,
                    request=request,
                    status="execution_failed",
                    reason="execution_failed",
                    reserved_time=reserved_time,
                    canonical_values=canonical,
                    parameter_hash=parameter_hash,
                    program_hash=program_hash,
                )
                observations.append(observation)
                try:
                    controller.tell(observation)
                except Exception as tell_exc:
                    return self._controller_failure_result(
                        controller=controller,
                        stage="controller.tell",
                        exc=tell_exc,
                        observations=observations,
                        ledger=ledger,
                    )
                continue

            # The physical submission has happened.  Account its receipt before
            # validating it so a malformed or over-budget response cannot erase
            # already consumed resources.
            actual_shots = 0
            active_time = 0.0
            counts: tuple[tuple[str, int], ...] = ()
            receipt_errors: list[str] = []
            try:
                if not isinstance(result, ExperimentResult):
                    raise TypeError("executor returned a non-ExperimentResult")
                raw_shots = result.resources.shots
                if isinstance(raw_shots, bool):
                    raise TypeError("receipt shots cannot be bool")
                actual_shots = int(raw_shots)
                if float(raw_shots) != actual_shots:
                    raise ValueError("receipt shots are not integral")
                active_time = float(
                    result.resources.total_sequence_time_us
                )
                if actual_shots >= 0:
                    ledger.attempted_shots += actual_shots
                if math.isfinite(active_time) and active_time >= 0.0:
                    ledger.active_sequence_time_us += active_time
                counts = tuple(
                    sorted(
                        (str(key), int(value))
                        for key, value in result.counts.items()
                    )
                )
                if result.status != "completed":
                    receipt_errors.append("status")
                if actual_shots != self._problem.batch_shots:
                    receipt_errors.append("shots")
                if any(value < 0 for _, value in counts):
                    receipt_errors.append("negative_count")
                if sum(value for _, value in counts) != actual_shots:
                    receipt_errors.append("count_sum")
                if len(result.shot_outcomes) != actual_shots:
                    receipt_errors.append("shot_outcomes_length")
                if dict(Counter(result.shot_outcomes)) != dict(counts):
                    receipt_errors.append("outcome_histogram")
                if not math.isfinite(active_time) or active_time < 0:
                    receipt_errors.append("active_time")
                if active_time > reserved_time + 1e-9:
                    ledger.overrun_submissions += 1
                    receipt_errors.append("sequence_time_overrun")
            except Exception as exc:
                self._audit("receipt.parse", exc)
                receipt_errors.append("receipt_parse")
            if receipt_errors:
                ledger.failed_submissions += 1
                reason = (
                    "sequence_time_overrun"
                    if "sequence_time_overrun" in receipt_errors
                    else "invalid_receipt"
                )
                observation = self._failed_observation(
                    token_index=token_index,
                    request=request,
                    status="invalid_receipt",
                    reason=reason,
                    reserved_time=reserved_time,
                    canonical_values=canonical,
                    parameter_hash=parameter_hash,
                    program_hash=program_hash,
                    execution_id=(
                        result.execution_id
                        if isinstance(result, ExperimentResult)
                        else ""
                    ),
                    attempted_shots=max(0, actual_shots),
                    counts=counts,
                    active_time=max(0.0, active_time),
                )
                observations.append(observation)
                try:
                    controller.tell(observation)
                except Exception as tell_exc:
                    return self._controller_failure_result(
                        controller=controller,
                        stage="controller.tell",
                        exc=tell_exc,
                        observations=observations,
                        ledger=ledger,
                    )
                continue

            ledger.valid_shots += actual_shots
            retained_shots = (
                sum(
                    all(atom.retained for atom in record.atoms)
                    for record in result.shot_readouts
                )
                if result.shot_readouts
                else None
            )
            observation = PublicBatchObservation(
                token_index=token_index,
                candidate_id=request.candidate_id,
                requested_values=tuple(request.requested_values),
                canonical_values=canonical,
                canonical_parameter_sha256=parameter_hash,
                program_sha256=program_hash,
                status="completed",
                failure_reason="",
                execution_id=result.execution_id,
                expected_outcome=self._problem.expected_outcome,
                successes=dict(counts).get(
                    self._problem.expected_outcome, 0
                ),
                attempted_shots=actual_shots,
                valid_shots=actual_shots,
                retained_shots=retained_shots,
                counts=counts,
                active_sequence_time_us=active_time,
                reserved_scheduler_time_us=reserved_time,
                request_frame_sha256=_request_fingerprint(request),
            )
            observations.append(observation)
            try:
                controller.tell(observation)
            except Exception as tell_exc:
                return self._controller_failure_result(
                    controller=controller,
                    stage="controller.tell",
                    exc=tell_exc,
                    observations=observations,
                    ledger=ledger,
                )

        try:
            raw_recommendation = controller.recommend()
        except Exception as exc:
            return self._controller_failure_result(
                controller=controller,
                stage="controller.recommend",
                exc=exc,
                observations=observations,
                ledger=ledger,
            )
        try:
            recommendation = self._validate_recommendation(
                raw_recommendation,
                bindings=bindings,
                observations=observations,
            )
        except Exception as exc:
            self._audit("recommendation.validate", exc)
            return ClosedLoopRunResult(
                recommendation=None,
                observations=tuple(observations),
                ledger=ledger.snapshot(),
                run_status="invalid_recommendation",
                controller_failure_code="invalid_recommendation",
                controller_exitcode=self._controller_exitcode(controller),
            )
        return ClosedLoopRunResult(
            recommendation=recommendation,
            observations=tuple(observations),
            ledger=ledger.snapshot(),
            run_status="completed",
            controller_exitcode=self._controller_exitcode(controller),
        )


class _CatalogControllerBase:
    def __init__(self, candidates: tuple[CandidatePoint, ...]) -> None:
        if not candidates:
            raise ValueError("controller requires at least one candidate")
        ids = tuple(candidate.candidate_id for candidate in candidates)
        if len(ids) != len(set(ids)):
            raise ValueError("controller candidate ids must be unique")
        self._candidates = candidates
        self._by_id = {
            candidate.candidate_id: candidate for candidate in candidates
        }
        self._successes = {candidate.candidate_id: 0 for candidate in candidates}
        self._shots = {candidate.candidate_id: 0 for candidate in candidates}
        self._canonical: dict[str, tuple[float, ...]] = {}
        self._pending: str | None = None

    def _request(self, candidate: CandidatePoint) -> CandidateRequest:
        if self._pending is not None:
            raise RuntimeError("ask called twice without tell")
        self._pending = candidate.candidate_id
        return CandidateRequest(candidate.candidate_id, candidate.values)

    def tell(self, observation: PublicBatchObservation) -> None:
        if self._pending is None:
            raise RuntimeError("tell called without a pending request")
        if observation.candidate_id != self._pending:
            raise ValueError("observation does not match pending candidate")
        candidate_id = self._pending
        self._pending = None
        if observation.status == "completed":
            self._successes[candidate_id] += observation.successes
            self._shots[candidate_id] += observation.valid_shots
            self._canonical[candidate_id] = observation.canonical_values

    def _mean(self, candidate_id: str) -> float:
        shots = self._shots[candidate_id]
        return (
            self._successes[candidate_id] / shots
            if shots > 0
            else -math.inf
        )

    def _rank(
        self, candidates: tuple[CandidatePoint, ...]
    ) -> tuple[CandidatePoint, ...]:
        order = {
            candidate.candidate_id: index
            for index, candidate in enumerate(self._candidates)
        }
        return tuple(
            sorted(
                candidates,
                key=lambda candidate: (
                    -self._mean(candidate.candidate_id),
                    order[candidate.candidate_id],
                ),
            )
        )

    def _recommend(
        self, candidate: CandidatePoint, status: str
    ) -> ControllerRecommendation:
        canonical = self._canonical.get(
            candidate.candidate_id, tuple(candidate.values)
        )
        return ControllerRecommendation(
            candidate_id=candidate.candidate_id,
            canonical_values=canonical,
            decision_status=status,
        )


class UniformRepeatedController(_CatalogControllerBase):
    """Fixed-budget repeated evaluation of every catalog candidate."""

    def __init__(
        self,
        candidates: tuple[CandidatePoint, ...],
        *,
        repeats: int,
    ) -> None:
        super().__init__(candidates)
        if repeats <= 0:
            raise ValueError("repeats must be positive")
        self._schedule = [
            candidate
            for _ in range(repeats)
            for candidate in candidates
        ]
        self._next = 0

    def ask(
        self,
        problem: ClosedLoopProblemDescriptor,
        budget: PublicBudgetView,
    ) -> CandidateRequest | None:
        del problem
        if self._next >= len(self._schedule):
            return None
        if budget.tokens_remaining <= 0:
            return None
        candidate = self._schedule[self._next]
        self._next += 1
        return self._request(candidate)

    def recommend(self) -> ControllerRecommendation:
        if self._pending is not None:
            raise RuntimeError("cannot recommend with a pending request")
        best = self._rank(self._candidates)[0]
        return self._recommend(best, "fixed_budget")


class SuccessiveHalvingController(_CatalogControllerBase):
    """Three-stage fixed-budget elimination for a five-arm catalog."""

    def __init__(
        self, candidates: tuple[CandidatePoint, ...]
    ) -> None:
        if len(candidates) != 5:
            raise ValueError("S4-D successive halving requires five candidates")
        super().__init__(candidates)
        self._active = candidates
        self._keep_counts = (3, 2, 1)
        self._round = 0
        self._queue = list(self._active)

    def ask(
        self,
        problem: ClosedLoopProblemDescriptor,
        budget: PublicBudgetView,
    ) -> CandidateRequest | None:
        del problem
        if self._round >= len(self._keep_counts):
            return None
        if budget.tokens_remaining <= 0:
            return None
        if not self._queue:
            raise RuntimeError("successive-halving round queue is empty")
        return self._request(self._queue.pop(0))

    def tell(self, observation: PublicBatchObservation) -> None:
        super().tell(observation)
        if not self._queue:
            keep = self._keep_counts[self._round]
            self._active = self._rank(self._active)[:keep]
            self._round += 1
            if self._round < len(self._keep_counts):
                self._queue = list(self._active)

    def recommend(self) -> ControllerRecommendation:
        if self._pending is not None:
            raise RuntimeError("cannot recommend with a pending request")
        best = self._rank(self._active)[0]
        status = (
            "fixed_budget"
            if self._round == len(self._keep_counts)
            else "budget_exhausted"
        )
        return self._recommend(best, status)


class KLLUCBController(_CatalogControllerBase):
    """Batched Bernoulli KL-LUCB with a strict certification status.

    The controller first evaluates every catalog arm. It then requests the
    empirical best and the non-best arm with the largest KL upper confidence
    bound as one two-batch round. A max-token exhaustion can still return an
    empirical recommendation, but it is explicitly not called certified.
    """

    def __init__(
        self,
        candidates: tuple[CandidatePoint, ...],
        *,
        delta: float,
        epsilon: float,
    ) -> None:
        if len(candidates) < 2:
            raise ValueError("KL-LUCB requires at least two candidates")
        if (
            not math.isfinite(delta)
            or not 0.0 < delta < 1.0
            or not math.isfinite(epsilon)
            or epsilon < 0.0
        ):
            raise ValueError("KL-LUCB delta/epsilon are invalid")
        super().__init__(candidates)
        self._delta = float(delta)
        self._epsilon = float(epsilon)
        self._queue = list(candidates)
        self._queue_kind = "initial"
        self._round_index = 1
        self._certified = False
        self._last_evaluation: KLLUCBEvaluation | None = None

    @property
    def last_evaluation(self) -> KLLUCBEvaluation | None:
        return self._last_evaluation

    def _statistics(self) -> tuple[BernoulliArmStatistics, ...]:
        return tuple(
            BernoulliArmStatistics(
                candidate.candidate_id,
                self._successes[candidate.candidate_id],
                self._shots[candidate.candidate_id],
                0,
            )
            for candidate in self._candidates
        )

    def _evaluate_and_schedule(self) -> None:
        missing = tuple(
            candidate
            for candidate in self._candidates
            if self._shots[candidate.candidate_id] == 0
        )
        if missing:
            # A failed/rejected batch consumed its token. Repeating it is a
            # fresh paid request, never a free retry.
            self._queue = list(missing)
            self._queue_kind = "repair"
            return
        evaluation = evaluate_kl_lucb(
            self._statistics(),
            round_index=self._round_index,
            delta=self._delta,
            epsilon=self._epsilon,
        )
        self._last_evaluation = evaluation
        if evaluation.certified:
            self._certified = True
            self._queue = []
            return
        self._queue = [
            self._by_id[evaluation.best_candidate_id],
            self._by_id[evaluation.challenger_candidate_id],
        ]
        self._queue_kind = "pair"

    def ask(
        self,
        problem: ClosedLoopProblemDescriptor,
        budget: PublicBudgetView,
    ) -> CandidateRequest | None:
        del problem
        if self._certified or budget.tokens_remaining <= 0:
            return None
        if not self._queue:
            self._evaluate_and_schedule()
        if self._certified or not self._queue:
            return None
        return self._request(self._queue.pop(0))

    def tell(self, observation: PublicBatchObservation) -> None:
        super().tell(observation)
        if not self._queue:
            if self._queue_kind == "pair":
                self._round_index += 1
            self._evaluate_and_schedule()

    def recommend(self) -> ControllerRecommendation:
        if self._pending is not None:
            raise RuntimeError("cannot recommend with a pending request")
        best = self._rank(self._candidates)[0]
        status = "certified" if self._certified else "budget_exhausted"
        detail = ""
        if self._last_evaluation is not None:
            detail = (
                "confidence_gap="
                f"{self._last_evaluation.confidence_gap:.12g};"
                f"epsilon={self._epsilon:.12g};"
                f"round={self._round_index}"
            )
        return ControllerRecommendation(
            candidate_id=best.candidate_id,
            canonical_values=self._canonical.get(
                best.candidate_id, tuple(best.values)
            ),
            decision_status=status,
            detail=detail,
        )
