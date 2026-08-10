"""Immutable provisional finalization and terminal selection."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import socket
from typing import Any, Mapping

from .artifacts import publish_production_envelope
from .production_schema import (
    RankExtensionDecision,
    payload_sha256,
    validate_envelope,
    validate_rank_extension_decision,
)
from .reducer import expected_ranks_sha256, validate_size_result_semantics


def finalize_reduction(reduction: Path, output_dir: Path) -> Path:
    """Publish one provisional finalization for an exact reduction path."""

    reduction_path = Path(reduction).absolute()
    result = validate_envelope(
        reduction_path, "challenge15.size-result.v1"
    )
    validate_size_result_semantics(result)
    ranks = tuple(int(rank) for rank in result["expected_ranks"])
    rank_digest = expected_ranks_sha256(ranks)
    reduction_digest = payload_sha256(result)
    _validate_reduction_path(
        reduction_path, result, reduction_digest, rank_digest
    )
    payload = {
        **_common(result),
        "expected_ranks": list(ranks),
        "expected_ranks_sha256": rank_digest,
        "selected_reduction_sha256": reduction_digest,
        "selected_reduction_path": str(reduction_path),
        "production_accepted": bool(result["production_accepted"]),
        "finalized_at_utc": _now(),
        "finalized_by": socket.gethostname(),
    }
    digest = payload_sha256(payload)
    parent = (
        Path(output_dir)
        / f"N={result['particles']}"
        / f"base={result['base_configuration_sha256']}"
        / f"expected={rank_digest}"
    )
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / f"{digest}.json"
    publish_production_envelope(
        destination,
        "challenge15.reduction-finalization.v1",
        payload,
    )
    return destination


def select_terminal(finalization: Path, output_dir: Path) -> Path:
    """Create the sole accepted terminal selection for one size/configuration."""

    finalization_path = Path(finalization).absolute()
    provisional = validate_envelope(
        finalization_path, "challenge15.reduction-finalization.v1"
    )
    finalization_digest = payload_sha256(provisional)
    _validate_finalization_path(
        finalization_path, provisional, finalization_digest
    )
    if not provisional["production_accepted"]:
        raise ValueError("terminal selection requires an accepted finalization")
    reduction_path = Path(str(provisional["selected_reduction_path"]))
    result = validate_envelope(
        reduction_path, "challenge15.size-result.v1"
    )
    validate_size_result_semantics(result)
    if (
        payload_sha256(result) != provisional["selected_reduction_sha256"]
        or not result["production_accepted"]
    ):
        raise ValueError("accepted finalization does not bind an accepted reduction")
    _validate_reduction_path(
        reduction_path,
        result,
        str(provisional["selected_reduction_sha256"]),
        str(provisional["expected_ranks_sha256"]),
    )
    for field, value in _common(provisional).items():
        if result[field] != value:
            raise ValueError(f"terminal reduction has stale {field}")
    if (
        result["expected_ranks"] != provisional["expected_ranks"]
        or expected_ranks_sha256(tuple(result["expected_ranks"]))
        != provisional["expected_ranks_sha256"]
    ):
        raise ValueError("terminal finalization expected-rank lineage mismatch")

    payload = {
        **_common(provisional),
        "selected_expected_ranks_sha256": provisional[
            "expected_ranks_sha256"
        ],
        "selected_finalization_sha256": finalization_digest,
        "selected_reduction_sha256": provisional[
            "selected_reduction_sha256"
        ],
        "production_accepted": True,
        "selected_at_utc": _now(),
        "selected_by": socket.gethostname(),
    }
    digest = payload_sha256(payload)
    parent = (
        Path(output_dir)
        / f"N={provisional['particles']}"
        / f"base={provisional['base_configuration_sha256']}"
    )
    parent.parent.mkdir(parents=True, exist_ok=True)
    try:
        parent.mkdir()
    except FileExistsError as exc:
        raise ValueError("a terminal selection already exists for this key") from exc
    destination = parent / f"{digest}.json"
    publish_production_envelope(
        destination,
        "challenge15.terminal-selection.v1",
        payload,
    )
    return destination


def create_rank_extension_decision(
    prior_finalization: Path,
    seed: int,
    new_rank: int,
    output_dir: Path,
    *,
    prior_import_receipt: Path,
    prior_transfer_receipt: Path,
) -> Path:
    """Publish a deterministic next-rank decision bound to its prior cycle."""

    finalization_path = Path(prior_finalization).absolute()
    provisional = validate_envelope(
        finalization_path, "challenge15.reduction-finalization.v1"
    )
    finalization_digest = payload_sha256(provisional)
    _validate_finalization_path(
        finalization_path, provisional, finalization_digest
    )
    if provisional["production_accepted"]:
        raise ValueError("accepted finalization cannot authorize rank extension")
    current_rank = int(provisional["expected_ranks"][-1])
    if new_rank != 2 * current_rank:
        raise ValueError("rank extension decision must consecutively double")
    reduction_path = Path(str(provisional["selected_reduction_path"]))
    result = validate_envelope(
        reduction_path, "challenge15.size-result.v1"
    )
    validate_size_result_semantics(result)
    reduction_digest = payload_sha256(result)
    if reduction_digest != provisional["selected_reduction_sha256"]:
        raise ValueError("prior finalization does not bind its reduction")
    _validate_reduction_path(
        reduction_path,
        result,
        reduction_digest,
        str(provisional["expected_ranks_sha256"]),
    )
    for field, expected in _common(provisional).items():
        if result[field] != expected:
            raise ValueError(f"prior reduction has stale {field}")

    import_path = Path(prior_import_receipt).absolute()
    imported = validate_envelope(
        import_path, "challenge15.import-bundle.v1"
    )
    import_digest = payload_sha256(imported)
    _require_content_addressed(import_path, import_digest, "import receipt")
    transfer_path = Path(prior_transfer_receipt).absolute()
    transfer = validate_envelope(
        transfer_path, "challenge15.transfer-receipt.v1"
    )
    transfer_digest = payload_sha256(transfer)
    _require_content_addressed(transfer_path, transfer_digest, "transfer receipt")
    for label, payload in (("import", imported), ("transfer", transfer)):
        for field, expected in _common(provisional).items():
            if payload[field] != expected:
                raise ValueError(f"{label} transport receipt has stale {field}")
    if transfer["import_bundle_sha256"] != import_digest:
        raise ValueError("transport receipt does not bind the import receipt")
    member_hashes = {
        str(value) for value in imported["member_manifest"].values()
    }
    if not {reduction_digest, finalization_digest} <= member_hashes:
        raise ValueError("transport import omits prior reduction/finalization")
    if imported["imported_artifact_sha256"] not in member_hashes:
        raise ValueError("transport import artifact is not a declared member")
    decision = RankExtensionDecision(
        **_common(provisional),
        seed=seed,
        current_rank=current_rank,
        new_rank=new_rank,
        prior_expected_ranks_sha256=provisional["expected_ranks_sha256"],
        prior_reduction_sha256=reduction_digest,
        prior_finalization_sha256=finalization_digest,
        prior_import_receipt_sha256=import_digest,
        prior_transfer_receipt_sha256=transfer_digest,
        decision="train",
        reason=(
            "scheduled_initial_ladder"
            if current_rank < 4
            else "rank_convergence_pending"
        ),
        decision_metrics={
            "prior_production_accepted": provisional[
                "production_accepted"
            ],
            "transport_binding": "validated-import-transfer",
        },
    )
    validate_rank_extension_decision(decision)
    digest = payload_sha256(decision.to_payload())
    parent = Path(output_dir)
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / f"{digest}.json"
    publish_production_envelope(
        destination,
        "challenge15.rank-extension-decision.v1",
        decision,
    )
    return destination


def _validate_reduction_path(
    path: Path,
    payload: Mapping[str, Any],
    digest: str,
    rank_digest: str,
) -> None:
    if (
        not path.is_absolute()
        or path.name != f"{digest}.json"
        or path.parent.name != rank_digest
        or expected_ranks_sha256(tuple(payload["expected_ranks"])) != rank_digest
    ):
        raise ValueError("reduction path is not content-addressed by expected ranks")


def _validate_finalization_path(
    path: Path,
    payload: Mapping[str, Any],
    digest: str,
) -> None:
    if (
        not path.is_absolute()
        or path.name != f"{digest}.json"
        or path.parent.name != f"expected={payload['expected_ranks_sha256']}"
        or path.parent.parent.name
        != f"base={payload['base_configuration_sha256']}"
        or path.parent.parent.parent.name != f"N={payload['particles']}"
    ):
        raise ValueError("provisional finalization path is not content-addressed")


def _require_content_addressed(path: Path, digest: str, label: str) -> None:
    if not path.is_absolute() or path.name != f"{digest}.json":
        raise ValueError(f"{label} path is not content-addressed")


def _common(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: payload[field]
        for field in (
            "policy_sha256",
            "source_manifest_sha256",
            "runtime_attestations",
            "base_configuration_sha256",
            "particles",
        )
    }


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
