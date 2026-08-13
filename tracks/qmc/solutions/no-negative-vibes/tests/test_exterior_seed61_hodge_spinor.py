from __future__ import annotations

from oracle.exterior_seed61_hodge_spinor import (
    seed61_hodge_spinor_obstruction,
)


def test_seed61_mukai_form_is_split_and_both_natural_orthants_fail() -> None:
    result = seed61_hodge_spinor_obstruction()

    assert result["mukai"]["identity_replay"] is True
    assert result["mukai"]["hodge_is_signed_permutation"] is True
    assert result["mukai"]["inertia"] == [16, 16]
    assert result["self_anti_hodge"]["transpose_partner_replay"] is True
    assert result["self_anti_hodge"]["negative_entries"] == 122
    assert result["self_anti_hodge"]["reciprocal_sign_conflict"] == {
        "left": "+:01",
        "right": "+:02",
        "forward": "-62717/589824",
        "reverse": "1/8",
    }
    assert result["particle_hole_signed_basis"]["reciprocal_sign_conflict"] == {
        "left": "k2:13",
        "right": "k2:24",
        "forward": "-11/384",
        "reverse": "1001/3072",
    }


def test_seed61_particle_hole_pair_trace_is_negative_at_power_seven() -> None:
    result = seed61_hodge_spinor_obstruction()
    witness = result["paired_trace_witness"]

    assert witness["power"] == 7
    assert witness["pair_1_4"] == (
        "-2637203457670395078041392722514295103565195"
        "/3178828148885691643853424575651009708163072"
    )
    assert witness["pair_2_3"] == (
        "140780460557849141078414587008569"
        "/2284347543117575620391199571968"
    )
    assert witness["full_fock"] == (
        "199626234419917700768513242993680430182814325"
        "/3178828148885691643853424575651009708163072"
    )
