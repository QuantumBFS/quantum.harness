import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_nonlinear_mori_nonidentifiability_is_constructive_and_fail_closed():
    payload = json.loads(
        (ROOT / "docs/nonlinear_mori_closure_no_go_certificate.json").read_text()
    )
    assert payload["exact_prefix"]["maximum_even_moment_order"] == 26
    assert payload["exact_prefix"]["recurrent_count"] == 13
    example = payload["constructive_counterexample"]
    assert example["both_spectral_measures_positive"] is True
    assert example["both_spectral_measures_unit_mass"] is True
    assert example["both_preserve_all_known_recurrents"] is True
    assert min(example["relative_separation"]) > 0.7
    gates = payload["gates"]
    assert gates["nonidentifiability_no_go_certified"] is True
    assert gates["finite_microscopic_prefix_uniquely_determines_nonlinear_kernel"] is False
    assert gates["tested_local_counterterms_renormalize_bare_one_loop"] is False
    assert gates["current_hydrodynamic_vertices_define_physical_F1_perp"] is False
    assert gates["unique_constant_burgers_pair_follows_analytically"] is False
