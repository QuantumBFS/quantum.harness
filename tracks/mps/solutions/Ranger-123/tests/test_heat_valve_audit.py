from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from heat_valve_fixtures import valid_heat_valve_manifest

from floquet_if_manybody.heat_valve_audit import audit_heat_valve_manifest


@pytest.mark.parametrize(
    ("mutation", "failure"),
    [
        (
            lambda manifest: manifest["points"][0]["model"].update(
                drive_frequency=2.9
            ),
            "fixed drive frequency",
        ),
        (
            lambda manifest: manifest["points"][1]["pole_fit"].update(
                reconstruction_residual=0.08
            ),
            "pole reconstruction",
        ),
        (
            lambda manifest: manifest["points"][1].update(
                integrated_absolute_heat=0.2
            ),
            "tenfold heat suppression",
        ),
        (
            lambda manifest: manifest["points"][1].update(
                visible_residue_weight=0.2
            ),
            "tenfold residue suppression",
        ),
        (
            lambda manifest: manifest["points"][1]["poles"][0].update(
                eigenpair_residual=1e-6
            ),
            "eigenpair residual",
        ),
        (
            lambda manifest: manifest["points"][1]["poles"][0][
                "eigenvalue"
            ].update(abs=1.01),
            "unit disk",
        ),
    ],
)
def test_audit_rejects_unsupported_dark_claim(
    mutation: Callable[[dict[str, Any]], None],
    failure: str,
) -> None:
    manifest = valid_heat_valve_manifest()
    mutation(manifest)
    audit = audit_heat_valve_manifest(manifest)
    assert not audit.dark_channel_passed
    assert any(failure in item for item in audit.failures)


def test_audit_accepts_fixed_frequency_many_body_valve() -> None:
    audit = audit_heat_valve_manifest(valid_heat_valve_manifest())
    assert audit.complete
    assert audit.dark_channel_passed
    assert audit.many_body_amplification_passed
    assert audit.markov_payoff_passed
    assert audit.failures == ()
    assert audit.metrics["heat_contrast_n3"] == 120.0
