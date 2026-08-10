from pathlib import Path

import pytest

from challenge15.orchestrator import recover_before_act
from challenge15.production_schema import canonical_json


def test_recovery_adopts_one_independently_validated_candidate(tmp_path: Path):
    payload = {"identity": "seed=0"}
    document = {
        "schema": "synthetic.v1",
        "payload": payload,
        "payload_sha256": __import__("hashlib").sha256(canonical_json(payload)).hexdigest(),
    }
    path = tmp_path / f"{document['payload_sha256']}.json"
    path.write_bytes(canonical_json(document) + b"\n")
    recovered = recover_before_act(
        tmp_path,
        expected_schema="synthetic.v1",
        expected_identity={"identity": "seed=0"},
    )
    assert recovered.path == path


def test_recovery_rejects_multiple_or_tampered_candidates(tmp_path: Path):
    for nonce in ("a", "b"):
        payload = {"identity": "seed=0", "nonce": nonce}
        digest = __import__("hashlib").sha256(canonical_json(payload)).hexdigest()
        (tmp_path / f"{digest}.json").write_bytes(
            canonical_json(
                {"schema": "synthetic.v1", "payload": payload, "payload_sha256": digest}
            )
            + b"\n"
        )
    with pytest.raises(ValueError, match="multiple"):
        recover_before_act(
            tmp_path,
            expected_schema="synthetic.v1",
            expected_identity={"identity": "seed=0"},
        )
