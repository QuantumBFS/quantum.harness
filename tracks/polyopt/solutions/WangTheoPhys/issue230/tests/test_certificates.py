import json
from pathlib import Path

from fractions import Fraction

from xxzcert.certify import (
    attach_rg_dual_proof,
    attach_sparse_block_upper,
    attach_rational_mps_block_upper,
    attach_u1_lti_dual_proof,
    make_level_certificate,
)
from xxzcert.lti import solve_lti
from xxzcert.schema import LevelCertificate
from xxzcert.rg_rational import make_rg_dual_witness
from xxzcert.rg_relaxation import alternating_neel_mps
from xxzcert.lti_u1 import solve_u1_lti
from xxzcert.lti_u1_rational import make_u1_lti_dual_witness
from xxzcert.itebd import optimize_itebd
from xxzcert.upper import optimize_block_state
from xxzcert.verify import verify_level


def make_small_xxx_bundle() -> LevelCertificate:
    return make_level_certificate(
        "1", solve_lti(1.0, 2), optimize_block_state(1.0, 4)
    )


def test_verified_bundle_round_trip(tmp_path: Path):
    path = make_small_xxx_bundle().write(tmp_path / "level.json")
    report = verify_level(path)
    assert report.ok, report.errors


def test_tampered_lower_bound_is_rejected(tmp_path: Path):
    path = make_small_xxx_bundle().write(tmp_path / "level.json")
    payload = json.loads(path.read_text())
    payload["certified_lower"] = "-0.4"
    path.write_text(json.dumps(payload))
    report = verify_level(path)
    assert not report.ok
    assert any("lower" in error for error in report.errors)


def test_tampered_bethe_interval_is_rejected(tmp_path: Path):
    path = make_small_xxx_bundle().write(tmp_path / "level.json")
    payload = json.loads(path.read_text())
    payload["bethe"]["lower"] = "-0.44"
    path.write_text(json.dumps(payload))
    assert not verify_level(path).ok


def test_unknown_fields_fail_closed(tmp_path: Path):
    path = make_small_xxx_bundle().write(tmp_path / "level.json")
    payload = json.loads(path.read_text())
    payload["unchecked"] = True
    path.write_text(json.dumps(payload))
    assert not verify_level(path).ok


def test_rg_dual_bundle_round_trip_and_tamper_rejection(tmp_path: Path):
    base = make_small_xxx_bundle()
    witness, candidate = make_rg_dual_witness(
        Fraction(1), alternating_neel_mps(), depth=4, dual_scale=10**6
    )
    certificate = attach_rg_dual_proof(base, witness, candidate.raw_lower)
    path = certificate.write(tmp_path / "rg.json")
    report = verify_level(path)
    assert report.ok, report.errors
    payload = json.loads(path.read_text())
    payload["rg_dual_proof"]["y_numerator"] -= 100
    path.write_text(json.dumps(payload))
    assert not verify_level(path).ok


def test_u1_lti_bundle_round_trip_and_tamper_rejection(tmp_path: Path):
    base = make_small_xxx_bundle()
    candidate = solve_u1_lti(1.0, 4)
    witness = make_u1_lti_dual_witness(Fraction(1), candidate)
    certificate = attach_u1_lti_dual_proof(
        base, witness, candidate.raw_lower
    )
    path = certificate.write(tmp_path / "u1.json")
    report = verify_level(path)
    assert report.ok, report.errors
    payload = json.loads(path.read_text())
    payload["u1_lti_dual_proof"]["y_numerator"] -= 100
    path.write_text(json.dumps(payload))
    assert not verify_level(path).ok


def test_sparse_block_bundle_round_trip_and_tamper_rejection(tmp_path: Path):
    base = make_small_xxx_bundle()
    certificate = attach_sparse_block_upper(
        base, optimize_block_state(1.0, 6)
    )
    path = certificate.write(tmp_path / "sparse-upper.json")
    report = verify_level(path)
    assert report.ok, report.errors
    payload = json.loads(path.read_text())
    payload["rational_sparse_block_proof"]["values"][0] *= 100
    path.write_text(json.dumps(payload))
    assert not verify_level(path).ok


def test_compact_mps_bundle_round_trip_and_tamper_rejection(tmp_path: Path):
    base = make_small_xxx_bundle()
    tensor = optimize_itebd(
        1.0,
        4,
        seed=231,
        schedule=((0.1, 30), (0.02, 60), (0.005, 100)),
    ).tensor
    certificate = attach_rational_mps_block_upper(base, tensor, sites=20)
    path = certificate.write(tmp_path / "mps-upper.json")
    report = verify_level(path)
    assert report.ok, report.errors
    payload = json.loads(path.read_text())
    payload["rational_mps_block_proof"]["tensor_values"] = [
        0 for _ in payload["rational_mps_block_proof"]["tensor_values"]
    ]
    path.write_text(json.dumps(payload))
    assert not verify_level(path).ok
