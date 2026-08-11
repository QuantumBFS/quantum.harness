"""Scientific claim contract for the sigma=2 infrared decision."""

from __future__ import annotations

QUESTION_ID = "sigma2_infrared_fate_v1"
TRACKS = {"massless", "finite_g_rg"}
CLAIM_STATUSES = {
    "proved",
    "ruled_out",
    "supported",
    "unresolved",
    "blocked",
}
EVIDENCE_CLASSES = {
    "rigorous_theorem",
    "controlled_local_rg",
    "fixed_scheme_finite_order",
    "sensitivity",
}
UPDATE_KEYS = {
    "ferromagnetic_lro",
    "ordinary_gapped_phase",
    "eventual_bkt",
    "non_bkt_massless",
}
UPDATE_VALUES = {
    "excluded",
    "unchanged",
    "proved",
    "supported",
    "unresolved",
}


def make_decision_record(
    *,
    track: str,
    claim_status: str,
    evidence_class: str,
    updates: dict[str, str],
    does_not_imply: list[str],
    blocking_obligations: list[str],
    source_hashes: dict[str, str],
) -> dict:
    """Construct and validate one track's scientific decision record."""

    record = {
        "question_id": QUESTION_ID,
        "track": track,
        "claim_status": claim_status,
        "evidence_class": evidence_class,
        "updates": dict(updates),
        "does_not_imply": list(does_not_imply),
        "blocking_obligations": list(blocking_obligations),
        "source_hashes": dict(source_hashes),
    }
    validate_decision_record(record)
    return record


def validate_decision_record(record: dict) -> None:
    """Reject malformed records and scientific claim escalation."""

    if record.get("question_id") != QUESTION_ID:
        raise ValueError("unknown scientific question")
    if record.get("track") not in TRACKS:
        raise ValueError("unknown decision track")
    if record.get("claim_status") not in CLAIM_STATUSES:
        raise ValueError("unknown claim status")
    if record.get("evidence_class") not in EVIDENCE_CLASSES:
        raise ValueError("unknown evidence class")

    updates = record.get("updates")
    if not isinstance(updates, dict) or set(updates) != UPDATE_KEYS:
        raise ValueError("decision updates must contain the registered keys")
    if any(value not in UPDATE_VALUES for value in updates.values()):
        raise ValueError("unknown scientific update value")

    for key in ("does_not_imply", "blocking_obligations"):
        values = record.get(key)
        if (
            not isinstance(values, list)
            or any(not isinstance(value, str) or not value for value in values)
        ):
            raise ValueError(f"{key} must be a list of nonempty strings")

    hashes = record.get("source_hashes")
    if (
        not isinstance(hashes, dict)
        or any(
            not isinstance(path, str)
            or not isinstance(digest, str)
            or len(digest) != 64
            for path, digest in hashes.items()
        )
    ):
        raise ValueError("source hashes must be path-to-SHA256 mappings")

    if record["track"] == "massless" and (
        updates["eventual_bkt"] != "unresolved"
        or updates["non_bkt_massless"] != "unresolved"
    ):
        raise ValueError("massless track cannot decide the infrared endpoint")

    local_only = record["evidence_class"] == "controlled_local_rg"
    global_claim = (
        updates["eventual_bkt"] == "proved"
        or updates["non_bkt_massless"] == "proved"
    )
    if local_only and global_claim:
        raise ValueError("controlled local RG is not a global basin proof")
    if (
        updates["eventual_bkt"] == "proved"
        and "physical_g1_global_basin" in record["blocking_obligations"]
    ):
        raise ValueError("eventual BKT requires a closed global basin")
