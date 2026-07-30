"""Pre-registered Stage 4 dense grid and replica bookkeeping."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import hmac
import json
import math
from typing import Iterable

from .dqmc import DQMCConfig
from .scan import run_fingerprint


EXPERIMENT_ID = "stage4-dense-20260729-v1"


@dataclass(frozen=True)
class DenseCell:
    index: int
    cell_id: str
    cohort: str
    config: DQMCConfig
    pair_id: str | None = None
    worker_id: int = -1


@dataclass(frozen=True)
class Stage4Policy:
    pilot_replicas: int = 2
    production_replicas: int = 4
    pilot_warmup_sweeps: int = 160
    pilot_measurement_sweeps: int = 320
    measure_every: int = 2
    target_ess_per_replica: float = 40.0
    warmup_tau_multiples: float = 20.0
    min_warmup_sweeps: int = 240
    max_warmup_sweeps: int = 1600
    min_measurement_sweeps: int = 640
    max_measurement_sweeps: int = 3200
    min_acceptance: float = 0.05
    max_acceptance: float = 0.995
    max_weight_log_error: float = 1.0e-6
    density_tolerance: float = 1.0e-7


@dataclass(frozen=True)
class ReplicaSpec:
    cell: DenseCell
    phase: str
    replica: int
    seed: int
    warmup_sweeps: int
    measurement_sweeps: int
    measure_every: int


MONITORED_TAU_KEYS = (
    "q_combined_tau_int",
    "q_a_sq_tau_int",
    "q_b_sq_tau_int",
    "hs_q_a_tau_int",
    "hs_q_b_tau_int",
    "staggered_structure_tau_int",
)
BLAS_THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def validate_blas_environment(environment: dict[str, str]) -> None:
    for name in BLAS_THREAD_VARIABLES:
        if environment.get(name) != "1":
            raise ValueError(f"{name} must be exactly 1 for production scans")


def _summary_audit_failure(
    summary: dict[str, object],
    *,
    policy: Stage4Policy,
    phase: str,
) -> str | None:
    acceptance = float(summary.get("acceptance", float("nan")))
    if (
        not math.isfinite(acceptance)
        or acceptance < policy.min_acceptance
        or acceptance > policy.max_acceptance
    ):
        return f"{phase} acceptance outside audit window"
    stability = (
        float(summary.get("direct_sign_min", float("nan"))),
        float(summary.get("weight_log_error_max", float("nan"))),
        float(summary.get("density_min", float("nan"))),
        float(summary.get("density_max", float("nan"))),
    )
    if (
        not all(math.isfinite(value) for value in stability)
        or stability[0] < 1.0 - 1.0e-8
        or stability[1] > policy.max_weight_log_error
        or stability[2] < -policy.density_tolerance
        or stability[3] > 1.0 + policy.density_tolerance
    ):
        return f"{phase} determinant or stability audit failed"
    return None


def production_audit(
    summary: dict[str, object],
    *,
    current_measurement_sweeps: int,
    policy: Stage4Policy,
) -> dict[str, object]:
    failure = _summary_audit_failure(
        summary, policy=policy, phase="production"
    )
    if failure is not None:
        return {"status": "STOP", "reason": failure}
    tau_values = [
        float(summary.get(key, float("nan"))) for key in MONITORED_TAU_KEYS
    ]
    if any(
        not math.isfinite(value) or value < 0.5 for value in tau_values
    ):
        return {
            "status": "STOP",
            "reason": "production autocorrelation estimate unavailable",
        }
    measurements = int(summary.get("measurements", 0))
    worst_tau = max(tau_values)
    achieved_ess = measurements / (2.0 * worst_tau)
    audit = {
        "worst_tau_int": worst_tau,
        "achieved_ess": achieved_ess,
        "measurement_sweeps": current_measurement_sweeps,
    }
    if achieved_ess >= policy.target_ess_per_replica:
        return {
            "status": "PASS",
            "reason": "production ESS and numerical audits passed",
            **audit,
        }
    required = (
        math.ceil(2.0 * worst_tau * policy.target_ess_per_replica)
        * policy.measure_every
    )
    next_measurement = max(
        required, current_measurement_sweeps + policy.measure_every
    )
    if next_measurement > policy.max_measurement_sweeps:
        return {
            "status": "STOP",
            "reason": "production autocorrelation cap exceeded",
            "required_measurement_sweeps": next_measurement,
            **audit,
        }
    return {
        "status": "EXTEND",
        "reason": "production ESS below target",
        "next_measurement_sweeps": next_measurement,
        **audit,
    }


def _scaled_label(value: float) -> str:
    return f"{int(round(100.0 * value)):03d}"


def _mu_label(value: float) -> str:
    if value < 0.0:
        return f"n{int(round(10.0 * abs(value))):02d}"
    if value > 0.0:
        return f"p{int(round(10.0 * value)):02d}"
    return "000"


def _make_cell(
    cells: list[DenseCell],
    *,
    cohort: str,
    g_ratio: float,
    t: float,
    mu: float,
    m: int,
    beta: float,
    pair_id: str | None = None,
) -> None:
    cell_id = (
        f"{cohort}_m{m:02d}_b{int(beta):02d}"
        f"_g{_scaled_label(g_ratio)}"
        f"_t{_scaled_label(t)}"
        f"_mu{_mu_label(mu)}"
    )
    cells.append(
        DenseCell(
            index=len(cells),
            cell_id=cell_id,
            cohort=cohort,
            pair_id=pair_id,
            config=DQMCConfig(
                m=m,
                beta=beta,
                dt=0.2,
                t=t,
                g_b_over_g_a=g_ratio,
                mu=mu,
                proposal_scale=0.5 if beta == 4.0 else 0.25,
                stabilize=True,
            ),
        )
    )


def dense_grid() -> list[DenseCell]:
    """Return the frozen 90-cell Stage 4 pilot grid."""
    cells: list[DenseCell] = []
    for g_ratio in (0.25, 0.5, 1.0):
        for t in (0.25, 0.5, 1.0):
            for m in (4, 6, 8):
                for beta in (4.0, 8.0):
                    _make_cell(
                        cells,
                        cohort="half_filled_core",
                        g_ratio=g_ratio,
                        t=t,
                        mu=0.0,
                        m=m,
                        beta=beta,
                    )
    for g_ratio in (0.75, 1.0, 1.25):
        for t in (0.5, 1.0):
            for m in (4, 6, 8):
                pair_id = (
                    f"g{_scaled_label(g_ratio)}"
                    f"_t{_scaled_label(t)}_m{m:02d}_b08"
                )
                for mu in (-1.5, 1.5):
                    _make_cell(
                        cells,
                        cohort="paired_competition",
                        g_ratio=g_ratio,
                        t=t,
                        mu=mu,
                        m=m,
                        beta=8.0,
                        pair_id=pair_id,
                    )
    return cells


def select_shard(
    cells: Iterable[DenseCell], machine: str
) -> list[DenseCell]:
    if machine not in {"wsl", "cpu"}:
        raise ValueError("machine must be 'wsl' or 'cpu'")
    selected = [
        cell
        for cell in cells
        if (cell.index % 5 == 0) == (machine == "wsl")
    ]
    first_worker = 0 if machine == "wsl" else 14
    worker_count = 14 if machine == "wsl" else 62
    return [
        replace(
            cell,
            worker_id=first_worker + ordinal % worker_count,
        )
        for ordinal, cell in enumerate(selected)
    ]


def assigned_grid() -> list[DenseCell]:
    return sorted(
        select_shard(dense_grid(), "wsl")
        + select_shard(dense_grid(), "cpu"),
        key=lambda cell: cell.index,
    )


def replica_seed(
    cell_id: str,
    phase: str,
    replica: int,
    worker_id: int,
) -> int:
    material = (
        f"{EXPERIMENT_ID}|{cell_id}|{phase}|{replica}|{worker_id}"
    ).encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:4], byteorder="big", signed=False)


def adaptive_budget(
    pilot_summaries: Iterable[dict[str, object]],
    *,
    policy: Stage4Policy,
) -> dict[str, object]:
    summaries = list(pilot_summaries)
    if len(summaries) != policy.pilot_replicas:
        return {
            "status": "STOP",
            "reason": "incomplete pilot replica set",
        }
    acceptances = [float(row.get("acceptance", float("nan"))) for row in summaries]
    if any(
        not math.isfinite(value)
        or value < policy.min_acceptance
        or value > policy.max_acceptance
        for value in acceptances
    ):
        return {
            "status": "STOP",
            "reason": "pilot acceptance outside audit window",
        }
    stability_values = [
        (
            float(row.get("direct_sign_min", float("nan"))),
            float(row.get("weight_log_error_max", float("nan"))),
            float(row.get("density_min", float("nan"))),
            float(row.get("density_max", float("nan"))),
        )
        for row in summaries
    ]
    if any(
        not all(math.isfinite(value) for value in values)
        or values[0] < 1.0 - 1.0e-8
        or values[1] > policy.max_weight_log_error
        or values[2] < -policy.density_tolerance
        or values[3] > 1.0 + policy.density_tolerance
        for values in stability_values
    ):
        return {
            "status": "STOP",
            "reason": "pilot determinant or stability audit failed",
        }
    tau_values = [
        float(row.get(key, float("nan")))
        for row in summaries
        for key in MONITORED_TAU_KEYS
    ]
    if not tau_values or any(
        not math.isfinite(value) or value < 0.5 for value in tau_values
    ):
        return {
            "status": "STOP",
            "reason": "pilot autocorrelation estimate unavailable",
        }
    worst_tau = max(tau_values)
    required_measurement = math.ceil(
        2.0 * worst_tau * policy.target_ess_per_replica
    ) * policy.measure_every
    measurement_sweeps = max(
        policy.min_measurement_sweeps, required_measurement
    )
    warmup_sweeps = max(
        policy.min_warmup_sweeps,
        math.ceil(policy.warmup_tau_multiples * worst_tau)
        * policy.measure_every,
    )
    if (
        measurement_sweeps > policy.max_measurement_sweeps
        or warmup_sweeps > policy.max_warmup_sweeps
    ):
        return {
            "status": "STOP",
            "reason": "autocorrelation budget cap exceeded",
            "worst_tau_int": worst_tau,
            "required_warmup_sweeps": warmup_sweeps,
            "required_measurement_sweeps": measurement_sweeps,
        }
    measurements = measurement_sweeps / policy.measure_every
    return {
        "status": "RUN",
        "reason": "pilot audit passed",
        "worst_tau_int": worst_tau,
        "warmup_sweeps": warmup_sweeps,
        "measurement_sweeps": measurement_sweeps,
        "measure_every": policy.measure_every,
        "production_replicas": policy.production_replicas,
        "projected_ess_per_replica": measurements / (2.0 * worst_tau),
    }


def synchronize_pair_budgets(
    cells: Iterable[DenseCell],
    decisions: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    synchronized = {
        cell_id: dict(decision) for cell_id, decision in decisions.items()
    }
    pairs: dict[str, list[DenseCell]] = {}
    for cell in cells:
        if cell.pair_id is not None:
            pairs.setdefault(cell.pair_id, []).append(cell)
    for pair in pairs.values():
        present = [
            cell for cell in pair if cell.cell_id in synchronized
        ]
        if len(present) != 2:
            continue
        pair_decisions = [
            synchronized[cell.cell_id] for cell in present
        ]
        if any(decision.get("status") != "RUN" for decision in pair_decisions):
            for cell in present:
                synchronized[cell.cell_id].update(
                    {
                        "status": "STOP",
                        "reason": "paired member failed pilot audit",
                        "paired_budget": True,
                    }
                )
            continue
        warmup = max(
            int(decision["warmup_sweeps"])
            for decision in pair_decisions
        )
        measurement = max(
            int(decision["measurement_sweeps"])
            for decision in pair_decisions
        )
        for cell in present:
            synchronized[cell.cell_id].update(
                {
                    "warmup_sweeps": warmup,
                    "measurement_sweeps": measurement,
                    "paired_budget": True,
                }
            )
    return synchronized


def replica_specs(
    cells: Iterable[DenseCell],
    *,
    phase: str,
    policy: Stage4Policy,
    decisions: dict[str, dict[str, object]] | None = None,
) -> list[ReplicaSpec]:
    if phase not in {"pilot", "production"}:
        raise ValueError("phase must be 'pilot' or 'production'")
    specs: list[ReplicaSpec] = []
    for cell in cells:
        if phase == "pilot":
            replicas = policy.pilot_replicas
            warmup = policy.pilot_warmup_sweeps
            measurement = policy.pilot_measurement_sweeps
        else:
            if decisions is None:
                raise ValueError("production phase requires budget decisions")
            decision = decisions.get(cell.cell_id)
            if decision is None or decision.get("status") != "RUN":
                continue
            replicas = policy.production_replicas
            warmup = int(decision["warmup_sweeps"])
            measurement = int(decision["measurement_sweeps"])
        for replica in range(replicas):
            specs.append(
                ReplicaSpec(
                    cell=cell,
                    phase=phase,
                    replica=replica,
                    seed=replica_seed(
                        cell.cell_id,
                        phase,
                        replica,
                        cell.worker_id,
                    ),
                    warmup_sweeps=warmup,
                    measurement_sweeps=measurement,
                    measure_every=policy.measure_every,
                )
            )
    return specs


def validate_pilot_replicas(
    cell: DenseCell,
    summaries: Iterable[dict[str, object]],
    *,
    policy: Stage4Policy,
) -> str:
    rows = list(summaries)
    expected_specs = {
        spec.replica: spec
        for spec in replica_specs([cell], phase="pilot", policy=policy)
    }
    replicas = [int(row.get("replica", -1)) for row in rows]
    if len(rows) != policy.pilot_replicas or set(replicas) != set(
        expected_specs
    ):
        raise ValueError("pilot replica set is incomplete or duplicated")
    source_revisions: set[str] = set()
    for row in rows:
        replica = int(row["replica"])
        spec = expected_specs[replica]
        run_spec = row.get("run_spec")
        if not isinstance(run_spec, dict):
            raise ValueError("pilot run_spec is missing")
        stored_fingerprint = str(row.get("run_fingerprint", ""))
        expected_fingerprint = run_fingerprint(run_spec)
        if not hmac.compare_digest(stored_fingerprint, expected_fingerprint):
            raise ValueError("pilot run fingerprint mismatch")
        expected_fields = {
            "experiment_id": EXPERIMENT_ID,
            "cell_id": cell.cell_id,
            "cell_index": cell.index,
            "cohort": cell.cohort,
            "pair_id": cell.pair_id,
            "machine": "wsl" if cell.worker_id < 14 else "cpu",
            "worker_id": cell.worker_id,
            "phase": "pilot",
            "replica": replica,
            "seed": spec.seed,
            "config": cell.config.as_dict(),
            "warmup_sweeps": spec.warmup_sweeps,
            "measurement_sweeps": spec.measurement_sweeps,
            "measure_every": spec.measure_every,
        }
        if any(run_spec.get(key) != value for key, value in expected_fields.items()):
            raise ValueError("pilot run_spec does not match frozen replica")
        if (
            row.get("status") != "COMPLETE"
            or row.get("experiment_id") != EXPERIMENT_ID
            or row.get("cell_id") != cell.cell_id
            or row.get("phase") != "pilot"
        ):
            raise ValueError("pilot summary identity mismatch")
        source_revision = str(run_spec.get("source_revision", ""))
        if not source_revision or source_revision == "unknown":
            raise ValueError("pilot source revision is unavailable")
        source_revisions.add(source_revision)
    if len(source_revisions) != 1:
        raise ValueError("pilot replicas use different source revisions")
    return source_revisions.pop()


def pilot_release_digest(
    summaries: Iterable[dict[str, object]],
) -> str:
    records = sorted(
        summaries,
        key=lambda row: (str(row["cell_id"]), int(row["replica"])),
    )
    encoded = json.dumps(
        records, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_budget_plan(
    plan: dict[str, object],
    *,
    source_revision: str,
    policy: Stage4Policy,
    pilot_summaries: Iterable[dict[str, object]],
) -> None:
    if plan.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("budget plan experiment_id mismatch")
    if plan.get("released") is not True:
        raise ValueError("budget plan is not released")
    if plan.get("source_revision") != source_revision:
        raise ValueError("budget plan source revision mismatch")
    if plan.get("policy") != asdict(policy):
        raise ValueError("budget plan policy mismatch")
    digest = str(plan.get("pilot_digest", ""))
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ValueError("budget plan pilot digest is invalid")
    decisions = plan.get("decisions")
    if not isinstance(decisions, dict):
        raise ValueError("budget plan decisions are missing")
    cells = assigned_grid()
    expected_cells = {cell.cell_id for cell in cells}
    if set(decisions) != expected_cells:
        raise ValueError("budget plan does not cover the frozen grid")
    if any(
        not isinstance(decision, dict)
        or decision.get("status") not in {"RUN", "STOP"}
        for decision in decisions.values()
    ):
        raise ValueError("budget plan contains an invalid decision")
    rows = list(pilot_summaries)
    summaries_by_cell: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        cell_id = str(row.get("cell_id", ""))
        if cell_id not in expected_cells:
            raise ValueError("pilot evidence contains an unknown cell")
        summaries_by_cell.setdefault(cell_id, []).append(row)
    source_revisions = {
        validate_pilot_replicas(
            cell,
            summaries_by_cell.get(cell.cell_id, []),
            policy=policy,
        )
        for cell in cells
    }
    if source_revisions != {source_revision}:
        raise ValueError("pilot evidence source revision mismatch")
    expected_digest = pilot_release_digest(rows)
    if not hmac.compare_digest(digest, expected_digest):
        raise ValueError("budget plan pilot digest mismatch")
    raw_decisions = {
        cell.cell_id: adaptive_budget(
            summaries_by_cell[cell.cell_id],
            policy=policy,
        )
        for cell in cells
    }
    expected_decisions = synchronize_pair_budgets(cells, raw_decisions)
    if decisions != expected_decisions:
        raise ValueError("budget plan decisions do not match pilot evidence")


def shard_exit_code(results: Iterable[dict[str, object]]) -> int:
    return int(any(result.get("status") == "ERROR" for result in results))
