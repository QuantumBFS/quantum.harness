from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from challenge15.artifacts import publish_production_envelope
from challenge15.finalization import (
    create_rank_extension_decision,
    finalize_reduction,
    select_terminal,
)
from challenge15.production_policy import policy_sha256
from challenge15.production_policy import production_policy
from challenge15.production_schema import (
    SCIENTIFIC_NESTED_CONTRACTS,
    canonical_json,
    contract_fixture,
    envelope_for,
    payload_sha256,
    validate_envelope,
)
from challenge15.artifacts import publish_create_only
from challenge15.reducer import expected_ranks_sha256
from challenge15.reducer import _validate_prerequisite


SHA = "a" * 64
RUNTIMES = {
    "training": {"qdeshell": "1" * 64},
    "coordinate": {"qdeshell": "2" * 64},
    "oracle": {"lasg02": "3" * 64},
    "exact": {"lasg02": "4" * 64},
    "reducer": {"lasg02": "5" * 64},
}


def _size_result(*, accepted: bool, basis: str = "fixture") -> dict:
    common = {
        "policy_sha256": policy_sha256(),
        "source_manifest_sha256": SHA,
        "runtime_attestations": RUNTIMES,
        "base_configuration_sha256": "b" * 64,
        "particles": 6,
    }
    nested = SCIENTIFIC_NESTED_CONTRACTS["challenge15.size-result.v1"]
    identities = {
        f"rank={rank},seed={seed}": "c" * 64
        for rank in (1, 2, 4)
        for seed in range(5)
    }
    policy = production_policy()
    payload = {
        **common,
        "expected_ranks": [1, 2, 4],
        "expected_seeds": [0, 1, 2, 3, 4],
        "oracle_sha256": "c" * 64,
        "generation_sha256_by_identity": identities,
        "exact_sha256_by_identity": identities,
        "coordinate_sha256_by_identity": identities,
        "coordinate_uncertainty_by_rank": [
            {
                "rank": rank,
                "paired_seed_ids": [0, 1, 2, 3, 4],
                "e0_seed_estimates": [0.0] * 5,
                "e2_seed_estimates": [1.0] * 5,
                "within_seed_inputs": [
                    {
                        "seed": seed,
                        "e0": 0.0,
                        "e2": 1.0,
                        "variance_mc_e0": 0.01,
                        "variance_mc_e2": 0.04,
                        "monte_carlo_covariance_e0_e2": 0.0,
                        "variance_mc_gap": 0.05,
                    }
                    for seed in range(5)
                ],
                "optimizer_variance_e0": 0.0,
                "optimizer_variance_e2": 0.0,
                "optimizer_covariance_e0_e2": 0.0,
                "paired_seed_count": 5,
                "variance_seed_mean_gap": 0.0,
                "uncertainty_status": "accepted",
            }
            for rank in (1, 2, 4)
        ],
        "prerequisite": contract_fixture(nested["prerequisite"]),
        "primitive_metrics": contract_fixture(nested["primitive_metrics"]),
        "rank_transitions": [
            {"previous_rank": 1, "new_rank": 2, "passed": True},
            {"previous_rank": 2, "new_rank": 4, "passed": True},
        ],
        "seed_gate": {
            "passing_seeds": [0, 1, 2, 3] if accepted else [0],
            "required_count": 4,
            "passed": accepted,
        },
        "missing_identities": [],
        "failed_gates": [] if accepted else [{"reason": "pending"}],
        "production_accepted": accepted,
        "claim": {
            "statement": (
                policy["claim_policy"]["accepted_claim"]
                if accepted
                else policy["claim_policy"]["pending_claim"]
            ),
            "basis": basis,
        },
    }
    if accepted:
        for sector in ("L0", "L2"):
            payload["primitive_metrics"]["per_state_gate_inputs_by_sector"][
                sector
            ] = {
                "finite": True,
                "normalized_amplitude_nonzero": True,
            }
    return payload


def _publish_reduction(tmp_path, *, accepted: bool, basis: str = "fixture"):
    payload = _size_result(accepted=accepted, basis=basis)
    digest = payload_sha256(payload)
    path = tmp_path / "reductions" / expected_ranks_sha256((1, 2, 4)) / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    publish_production_envelope(path, "challenge15.size-result.v1", payload)
    return path


def _publish_payload(path: Path, schema: str, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    publish_create_only(
        path,
        canonical_json(envelope_for(schema, payload)) + b"\n",
    )
    return path


def _publish_transport_receipts(
    tmp_path: Path,
    reduction: Path,
    finalization: Path,
) -> tuple[Path, Path]:
    reduction_payload = validate_envelope(
        reduction, "challenge15.size-result.v1"
    )
    finalization_payload = validate_envelope(
        finalization, "challenge15.reduction-finalization.v1"
    )
    common = {
        field: reduction_payload[field]
        for field in (
            "policy_sha256",
            "source_manifest_sha256",
            "runtime_attestations",
            "base_configuration_sha256",
            "particles",
        )
    }
    members = {
        "reduction": payload_sha256(reduction_payload),
        "finalization": payload_sha256(finalization_payload),
    }
    imported = {
        **common,
        "bundle_sha256": "d" * 64,
        "destination_controller": "qdeshell",
        "destination_root": str(tmp_path / "imported"),
        "member_manifest": members,
        "imported_artifact_sha256": members["reduction"],
        "verified_at_utc": "2026-07-29T00:01:00Z",
    }
    import_digest = payload_sha256(imported)
    import_path = _publish_payload(
        tmp_path / "transport" / f"{import_digest}.json",
        "challenge15.import-bundle.v1",
        imported,
    )
    transfer = {
        **common,
        "direction": "lasg02->qdeshell",
        "export_bundle_sha256": "e" * 64,
        "import_bundle_sha256": import_digest,
        "source_controller": "lasg02",
        "destination_controller": "qdeshell",
        "source_identity": "/source/bundle",
        "destination_identity": "/destination/bundle",
        "partial_path": "/destination/.partial",
        "final_path": "/destination/final",
        "bytes": 1,
        "attempt_intent_sha256": "f" * 64,
        "correlation_id": "correlation",
        "remote_claim_sha256": "1" * 64,
        "started_at_utc": "2026-07-29T00:00:00Z",
        "verified_at_utc": "2026-07-29T00:01:00Z",
    }
    transfer_digest = payload_sha256(transfer)
    transfer_path = _publish_payload(
        tmp_path / "transport" / f"{transfer_digest}.json",
        "challenge15.transfer-receipt.v1",
        transfer,
    )
    return import_path, transfer_path


def test_multiple_provisional_finalizations_coexist_under_full_key(tmp_path):
    first_reduction = _publish_reduction(tmp_path, accepted=False, basis="first")
    second_reduction = _publish_reduction(tmp_path, accepted=False, basis="second")

    first = finalize_reduction(first_reduction, tmp_path / "finalizations")
    second = finalize_reduction(second_reduction, tmp_path / "finalizations")

    expected_parent = (
        tmp_path
        / "finalizations"
        / "N=6"
        / f"base={'b' * 64}"
        / f"expected={expected_ranks_sha256((1, 2, 4))}"
    )
    assert first.parent == expected_parent
    assert second.parent == expected_parent
    assert first != second
    assert len(tuple(expected_parent.glob("*.json"))) == 2


def test_terminal_selection_rejects_pending_and_is_create_only(tmp_path):
    pending = finalize_reduction(
        _publish_reduction(tmp_path, accepted=False),
        tmp_path / "pending-finalizations",
    )
    with pytest.raises(ValueError, match="accepted"):
        select_terminal(pending, tmp_path / "terminal-selections")
    assert not (tmp_path / "terminal-selections").exists()

    accepted = finalize_reduction(
        _publish_reduction(tmp_path, accepted=True),
        tmp_path / "accepted-finalizations",
    )
    selected = select_terminal(accepted, tmp_path / "terminal-selections")
    payload = validate_envelope(selected, "challenge15.terminal-selection.v1")
    finalization = validate_envelope(
        accepted, "challenge15.reduction-finalization.v1"
    )
    assert payload["selected_finalization_sha256"] == payload_sha256(finalization)
    assert payload["selected_reduction_sha256"] == finalization[
        "selected_reduction_sha256"
    ]
    with pytest.raises((FileExistsError, ValueError)):
        select_terminal(accepted, tmp_path / "terminal-selections")


def test_rank_extension_decision_binds_prior_reduction_and_finalization(tmp_path):
    reduction = _publish_reduction(tmp_path, accepted=False)
    finalization = finalize_reduction(reduction, tmp_path / "finalizations")
    import_receipt, transfer_receipt = _publish_transport_receipts(
        tmp_path, reduction, finalization
    )
    decision_path = create_rank_extension_decision(
        finalization,
        seed=3,
        new_rank=8,
        output_dir=tmp_path / "decisions",
        prior_import_receipt=import_receipt,
        prior_transfer_receipt=transfer_receipt,
    )
    decision = validate_envelope(
        decision_path, "challenge15.rank-extension-decision.v1"
    )
    finalization_payload = validate_envelope(
        finalization, "challenge15.reduction-finalization.v1"
    )
    assert decision["prior_reduction_sha256"] == finalization_payload[
        "selected_reduction_sha256"
    ]
    assert decision["prior_finalization_sha256"] == payload_sha256(
        finalization_payload
    )
    assert decision["current_rank"] == 4
    assert decision["new_rank"] == 8
    assert decision["prior_import_receipt_sha256"] == import_receipt.stem
    assert decision["prior_transfer_receipt_sha256"] == transfer_receipt.stem


def test_rank_extension_rejects_accepted_or_unbound_transport(tmp_path):
    accepted_reduction = _publish_reduction(tmp_path / "accepted", accepted=True)
    accepted_finalization = finalize_reduction(
        accepted_reduction, tmp_path / "accepted-finalizations"
    )
    import_receipt, transfer_receipt = _publish_transport_receipts(
        tmp_path / "accepted-transport",
        accepted_reduction,
        accepted_finalization,
    )
    with pytest.raises(ValueError, match="accepted"):
        create_rank_extension_decision(
            accepted_finalization,
            seed=0,
            new_rank=8,
            output_dir=tmp_path / "decisions",
            prior_import_receipt=import_receipt,
            prior_transfer_receipt=transfer_receipt,
        )

    pending_reduction = _publish_reduction(tmp_path / "pending", accepted=False)
    pending_finalization = finalize_reduction(
        pending_reduction, tmp_path / "pending-finalizations"
    )
    with pytest.raises(ValueError, match="transport"):
        create_rank_extension_decision(
            pending_finalization,
            seed=0,
            new_rank=8,
            output_dir=tmp_path / "decisions",
            prior_import_receipt=import_receipt,
            prior_transfer_receipt=transfer_receipt,
        )


def test_semantic_result_and_content_addressed_chain_are_required(tmp_path):
    forged_payload = _size_result(accepted=True)
    forged_payload["rank_transitions"][-1]["passed"] = False
    forged_digest = payload_sha256(forged_payload)
    forged_path = _publish_payload(
        tmp_path
        / "reductions"
        / expected_ranks_sha256((1, 2, 4))
        / f"{forged_digest}.json",
        "challenge15.size-result.v1",
        forged_payload,
    )
    with pytest.raises(ValueError, match="semantic"):
        finalize_reduction(forged_path, tmp_path / "finalizations")

    reduction = _publish_reduction(tmp_path / "valid", accepted=True)
    finalization = finalize_reduction(reduction, tmp_path / "valid-finalizations")
    copied = _publish_payload(
        tmp_path / "copied" / finalization.name,
        "challenge15.reduction-finalization.v1",
        validate_envelope(
            finalization, "challenge15.reduction-finalization.v1"
        ),
    )
    with pytest.raises(ValueError, match="content-addressed"):
        select_terminal(copied, tmp_path / "terminal-selections")


def test_terminal_selection_claim_is_atomic_for_size_and_base(tmp_path):
    first_reduction = _publish_reduction(
        tmp_path / "first", accepted=True, basis="first"
    )
    second_reduction = _publish_reduction(
        tmp_path / "second", accepted=True, basis="second"
    )
    first = finalize_reduction(first_reduction, tmp_path / "finalizations")
    second = finalize_reduction(second_reduction, tmp_path / "finalizations")

    def select(path: Path):
        try:
            return select_terminal(path, tmp_path / "terminal-selections")
        except (FileExistsError, ValueError):
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        selected = list(executor.map(select, (first, second)))

    assert sum(path is not None for path in selected) == 1
    key = tmp_path / "terminal-selections" / "N=6" / f"base={'b' * 64}"
    assert len(tuple(key.glob("*.json"))) == 1


def test_prerequisite_accepts_only_an_accepted_terminal_selection(tmp_path):
    accepted_finalization = finalize_reduction(
        _publish_reduction(tmp_path, accepted=True),
        tmp_path / "finalizations",
    )
    accepted = select_terminal(
        accepted_finalization, tmp_path / "terminal-selections"
    )
    target_common = {
        "policy_sha256": policy_sha256(),
        "source_manifest_sha256": SHA,
        "runtime_attestations": RUNTIMES,
        "base_configuration_sha256": "b" * 64,
        "particles": 7,
    }
    assert _validate_prerequisite(accepted, target_common)["accepted"] is True
    with pytest.raises(ValueError, match="requires"):
        _validate_prerequisite(None, target_common)
    with pytest.raises(ValueError, match="schema"):
        _validate_prerequisite(accepted_finalization, target_common)

    accepted_payload = validate_envelope(
        accepted, "challenge15.terminal-selection.v1"
    )
    pending_payload = {**accepted_payload, "production_accepted": False}
    pending_path = tmp_path / "pending-selection.json"
    publish_production_envelope(
        pending_path, "challenge15.terminal-selection.v1", pending_payload
    )
    with pytest.raises(ValueError, match="accepted"):
        _validate_prerequisite(pending_path, target_common)


@pytest.mark.parametrize(
    "mutation",
    (
        "missing-finalization",
        "corrupt-finalization",
        "missing-reduction",
        "corrupt-reduction",
        "mismatched-terminal",
    ),
)
def test_prerequisite_rejects_broken_trusted_lineage(tmp_path, mutation):
    root = tmp_path / mutation
    reduction = _publish_reduction(root, accepted=True)
    finalization = finalize_reduction(reduction, root / "finalizations")
    terminal = select_terminal(finalization, root / "terminal-selections")
    target_common = {
        "policy_sha256": policy_sha256(),
        "source_manifest_sha256": SHA,
        "runtime_attestations": RUNTIMES,
        "base_configuration_sha256": "b" * 64,
        "particles": 7,
    }

    if mutation == "missing-finalization":
        finalization.unlink()
    elif mutation == "corrupt-finalization":
        finalization.write_text("{", encoding="utf-8")
    elif mutation == "missing-reduction":
        reduction.unlink()
    elif mutation == "corrupt-reduction":
        reduction.write_text("{", encoding="utf-8")
    else:
        terminal_payload = validate_envelope(
            terminal, "challenge15.terminal-selection.v1"
        )
        terminal_payload["selected_reduction_sha256"] = "f" * 64
        terminal.unlink()
        terminal = _publish_payload(
            terminal.parent / f"{payload_sha256(terminal_payload)}.json",
            "challenge15.terminal-selection.v1",
            terminal_payload,
        )

    with pytest.raises((FileNotFoundError, ValueError)):
        _validate_prerequisite(terminal, target_common)
