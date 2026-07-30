from chiral_graviton.basis import SphereSystem
from chiral_graviton.nqs_chirality import train_nqs_chirality


def test_v1_nqs_has_parent_channel_dark_state():
    result = train_nqs_chirality(
        SphereSystem.from_electron_count(4),
        "v1",
        hidden_width=10,
        seed=17,
        max_iterations=300,
    )
    assert result.training.success
    assert result.response.integrated.bright_minus > 0.0
    assert result.response.integrated.dark_plus < 1e-20
    assert result.response.bright_graviton_fraction > 0.98


def test_coulomb_nqs_has_suppressed_dark_parent_channel():
    result = train_nqs_chirality(
        SphereSystem.from_electron_count(4),
        "coulomb",
        hidden_width=10,
        seed=23,
        max_iterations=300,
    )
    assert result.response.integrated.bright_to_dark > 100.0
    assert result.response.graviton_bright_to_dark > 100.0


def test_nqs_chirality_fails_closed_on_unconverged_training():
    try:
        train_nqs_chirality(
            SphereSystem.from_electron_count(4),
            "coulomb",
            hidden_width=4,
            seed=5,
            max_iterations=0,
        )
    except RuntimeError as error:
        assert "optimizer failed" in str(error)
    else:
        raise AssertionError("unconverged NQS chirality must fail")
