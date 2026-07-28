from pathlib import Path

from .verify_dual_certificate import verify


def test_exported_exact_dual_certificate():
    certificate = (
        Path(__file__).parent
        / "certificates"
        / "dual_certificate_exact.json"
    )
    result = verify(certificate)
    assert result["valid"] is True
    assert result["upper_bound_fraction"] == "20003/10000"
    assert result["matrix_size"] == 45
    assert result["positive_ldl_pivots"] == 45
