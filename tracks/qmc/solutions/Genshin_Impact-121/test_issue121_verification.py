from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math
from pathlib import Path

import numpy as np
import pytest
from scipy.linalg import expm

import issue121_verification as verify


MANIFEST_PATH = Path(__file__).with_name("issue121_full_run.json")


@pytest.fixture
def manifest() -> dict:
    return verify.load_manifest(MANIFEST_PATH)


def test_manifest_and_exact_workload(manifest: dict) -> None:
    assert manifest["schema_version"] == 1
    assert manifest["seed"] == 1212026
    candidate = manifest["candidate"]
    assert candidate["dimensions"] == [3, 4, 6, 8, 12]
    assert candidate["depths"] == [1, 2, 4, 8, 16, 32, 64]
    assert candidate["samples_per_cell"] == 256
    assert candidate["time_distribution"] == {
        "kind": "log_uniform", "minimum": "1e-3", "maximum": "5"
    }
    regimes = {item["id"]: item for item in candidate["regimes"]}
    assert list(regimes) == [
        "center", "near_boundary", "kappa_to_zero", "dirichlet_open_triangle"
    ]
    assert (regimes["center"]["epsilon"], regimes["center"]["kappa"]) == (
        "1/100", "1/1000"
    )
    boundary = regimes["near_boundary"]
    assert (
        40 * verify.parse_fraction(boundary["epsilon"])
        + 59 * verify.parse_fraction(boundary["kappa"])
    ) == verify.parse_fraction("1999/1000")
    assert regimes["kappa_to_zero"]["kappa"] == "1/1000000"
    assert regimes["dirichlet_open_triangle"]["kind"] == "dirichlet_open_triangle"
    assert regimes["dirichlet_open_triangle"]["alpha"] == [1.0, 1.0, 1.0]

    split = manifest["positive_anchors"]["split_orthogonal"]
    semigroup = manifest["positive_anchors"]["semigroup_cone"]
    controls = manifest["component_controls"]
    assert split["n_values"] == semigroup["n_values"] == [1, 2, 3, 4]
    assert set(controls["components"]) == {"++", "--", "-+", "+-"}
    assert controls["n_values"] == [1]

    candidate_cells = len(candidate["dimensions"]) * len(candidate["depths"]) * 4
    split_cells = len(split["n_values"]) * len(split["depths"])
    semigroup_cells = len(semigroup["n_values"]) * len(semigroup["depths"])
    component_cells = 4 * len(controls["n_values"]) * len(controls["depths"])
    expected = manifest["expected_workload"]
    assert (candidate_cells, split_cells, semigroup_cells, component_cells) == (
        expected["candidate_cells"], expected["split_cells"],
        expected["semigroup_cells"], expected["component_cells"]
    ) == (140, 28, 28, 28)
    assert expected["candidate_words"] == candidate_cells * 256 == 35840
    assert expected["split_words"] == split_cells * 64 == 1792
    assert expected["semigroup_words"] == semigroup_cells * 64 == 1792
    assert expected["component_words"] == component_cells * 32 == 896
    assert expected["total_words"] == 40320
    assert expected["physical_poisson_words"] == 4 * 4096 == 16384
    assert expected["total_random_words_including_physical"] == 56704

    cells = verify.build_cells(manifest)
    assert len(cells) == expected["total_cells"] == 224
    assert Counter(cell.kind for cell in cells) == {
        "candidate": 140, "split_orthogonal": 28,
        "semigroup_cone": 28, "component_control": 28,
    }
    assert manifest["fock_oracle"]["maximum_dimension"] == 8
    assert manifest["fock_oracle"]["sample_indices"] == [0, 127, 255]
    assert expected["fock_oracle_checks"] == 4 * 7 * 4 * 3 == 336
    assert manifest["determinant_precision"]["mpmath_dps"] == 100
    assert manifest["determinant_precision"]["high_precision_zero_tolerance"] == "1e-60"
    execution = manifest["execution"]
    assert execution["cpus_per_task"] == 1
    assert execution["memory_mb"] <= 2048
    assert execution["time_limit_minutes"] <= 20
    assert execution["gpus"] == 0


@pytest.mark.parametrize(
    "workload_key",
    [
        "candidate_cells",
        "split_cells",
        "semigroup_cells",
        "component_cells",
        "total_cells",
        "fock_oracle_checks",
    ],
)
def test_validate_manifest_rejects_incorrect_structural_workload(
    manifest: dict, workload_key: str
) -> None:
    broken = deepcopy(manifest)
    broken["expected_workload"][workload_key] += 1
    with pytest.raises(ValueError, match=rf"expected_workload\.{workload_key}="):
        verify.validate_manifest(broken)


def test_exact_fraction_certificates_and_components(manifest: dict) -> None:
    result = verify.exact_certificates(manifest)
    assert result["status"] == "pass"
    assert all(result["checks"].values())
    cert = result["certificates"]
    assert cert["mu_infinity"] == "-1/1000"
    assert cert["opposite_edge_product_A13_A31"] == "-1/50"
    assert cert["support_span_rank"] == 9
    assert verify.parse_fraction(cert["no_common_H_upper_bound"]) < 0
    assert verify.parse_fraction(cert["no_common_H_lower_bound"]) > 0
    assert cert["standard_polynomial_minimum"] == "37/27"
    assert cert["o11_component_det_I_plus"] == {
        "++": "16/3", "--": "-4/3", "-+": "0", "+-": "0"
    }
    assert verify.exact_component_weights() == cert["o11_component_det_I_plus"]


def test_ab_orbit_infinity_norm_certificate(manifest: dict) -> None:
    fixed = [r for r in manifest["candidate"]["regimes"] if r["kind"] == "fixed"]
    for regime in fixed:
        epsilon = float(verify.parse_fraction(regime["epsilon"]))
        kappa = float(verify.parse_fraction(regime["kappa"]))
        for _, _, generator in verify.ab_orbit(epsilon, kappa):
            assert verify.mu_infinity(generator) == pytest.approx(-kappa, abs=2e-15)
            for propagation_time in (1e-3, 0.1, 5.0):
                norm = np.linalg.norm(expm(propagation_time * generator), ord=np.inf)
                assert norm <= math.exp(-kappa * propagation_time) + 5e-12


def test_candidate_factor_order_equals_fock_trace(manifest: dict) -> None:
    cell = verify.Cell(
        "candidate__center__d04__m004", "candidate",
        {"regime": "center", "dimension": 4, "depth": 4},
    )
    rng = np.random.default_rng(verify.derive_seed(manifest["seed"], cell.cell_id))
    product, factor_specs, descriptor, total_kappa_time = verify.sample_candidate_word(
        manifest, cell, rng
    )
    rebuilt = np.eye(4)
    for factor in factor_specs:
        rebuilt = expm(factor["matrix"]) @ rebuilt
    assert len(factor_specs) == len(descriptor) == 4
    assert total_kappa_time > 0
    np.testing.assert_allclose(product, rebuilt, rtol=2e-13, atol=2e-13)

    determinant = float(np.linalg.det(np.eye(4) + product))
    fock_trace = verify.direct_fock_trace(factor_specs)
    tolerance = (
        float(manifest["fock_oracle"]["absolute_tolerance"])
        + float(manifest["fock_oracle"]["relative_tolerance"]) * abs(determinant)
    )
    assert determinant > 0
    assert abs(fock_trace.imag) <= tolerance
    assert abs(fock_trace.real - determinant) <= tolerance


def test_semigroup_sampler_records_actual_q_ranks(manifest: dict) -> None:
    config = deepcopy(manifest["positive_anchors"]["semigroup_cone"])
    config["time_distribution"] = {
        "kind": "log_uniform", "minimum": "0.1", "maximum": "0.1"
    }
    product, factor_specs, descriptor, generator_minimum, full, deficient, rank_failures = (
        verify.sample_semigroup_word(
            2, 2, 0, np.random.default_rng(1212026), config
        )
    )
    assert [item["q_kind"] for item in descriptor] == ["full", "rank_deficient"]
    assert [item["q_rank"] for item in descriptor] == [4, 2]
    assert (full, deficient) == (1, 1)
    assert rank_failures == 0
    assert generator_minimum >= -5e-12
    eta = verify.sph.split_metric(2)
    product_lmi = product.T @ eta @ product - eta
    product_lmi = 0.5 * (product_lmi + product_lmi.T)
    assert np.linalg.eigvalsh(product_lmi)[0] >= -5e-10
    determinant = verify.stable_determinant_i_plus(
        product, factor_specs, manifest["determinant_precision"]
    )
    assert determinant["classification"] == "positive"


def test_shifted_hbar_exact_deterministic_and_poisson_conventions(manifest: dict) -> None:
    config = manifest["physical_benchmark"]
    assert config["sites"] == 4 and config["boundary"] == "open"
    assert config["triangles"] == [[0, 1, 2], [1, 2, 3]]
    assert config["couplings"] == {"A": "1/4", "B": "1/4"}
    assert config["chemical_potential"] == "0"
    assert config["betas"] == ["1/4", "1/2", "1", "2"]

    catalog, interaction, _ = verify.physical_vertex_catalog(config)
    assert len(catalog) == 24
    total_activity = sum(float(vertex["weight"]) for vertex in catalog)
    assert total_activity == pytest.approx(1.0, abs=1e-15)
    hbar = total_activity * np.eye(interaction.shape[0]) - interaction
    assert hbar.shape == (16, 16)
    assert np.linalg.norm(hbar - hbar.T.conj(), ord="fro") <= 1e-10
    assert abs(hbar[0, 0]) <= 1e-12

    beta = 0.25
    exact_shifted = float(np.trace(expm(-beta * hbar)).real)
    exact_unshifted = float(np.trace(expm(beta * interaction)).real)
    assert exact_shifted == pytest.approx(
        math.exp(-beta * total_activity) * exact_unshifted,
        rel=2e-13, abs=2e-13,
    )
    deterministic = verify.deterministic_partition_expansion(
        interaction, beta, config["deterministic_truncation_order"], total_activity
    )
    shifted_series = deterministic["z_bar_estimate_real"]
    shifted_bound = (
        deterministic["remainder_bound"] + float(config["deterministic_roundoff_allowance"])
    )
    assert abs(shifted_series - exact_shifted) <= shifted_bound

    poisson = verify.poisson_partition_estimate(
        catalog, beta, 1024,
        np.random.default_rng(verify.derive_seed(config["seed"], "pytest_hbar")),
        manifest["determinant_precision"],
    )
    assert poisson["negative_or_unresolved_configurations"] == 0
    assert poisson["minimum_fock_configuration_weight"] >= -1e-10
    assert poisson["maximum_fock_determinant_abs_error"] <= 1e-7
    shifted_estimate = poisson["z_bar_estimate"]
    shifted_se = poisson["standard_error"]
    assert abs(shifted_estimate - exact_shifted) <= max(
        12.0 * shifted_se, 0.03 * exact_shifted
    )


def _fixture_row(cell: verify.Cell, sample: int) -> dict[str, object]:
    row = {field: "" for field in verify.CSV_FIELDS}
    row.update({
        "cell_id": cell.cell_id,
        "kind": cell.kind,
        "sample": sample,
        "dimension": cell.parameters.get("dimension", ""),
        "n": cell.parameters.get("n", ""),
        "depth": cell.parameters.get("depth", ""),
        "regime": cell.parameters.get("regime", ""),
        "component": cell.parameters.get("component", ""),
        "det_class": "positive",
        "det_method": "fixture",
        "det_sign": 1,
        "log_abs_det": "0",
        "determinant_decimal": "1",
        "sigma_min_i_plus_t": "1",
        "structural_diagnostic": "0",
        "fock_checked": 0,
        "word_sha256": f"fixture-{sample}",
    })
    return row


def test_resume_binds_protocol_and_rows_hash(tmp_path: Path) -> None:
    cell = verify.Cell(
        "candidate__center__d03__m001", "candidate",
        {"regime": "center", "dimension": 3, "depth": 1},
    )
    rows_path = tmp_path / "rows.csv"
    summary_path = tmp_path / "summary.json"
    rows = [_fixture_row(cell, sample) for sample in range(3)]
    verify.atomic_write_csv(rows_path, rows)
    summary = {
        "cell_id": cell.cell_id,
        "protocol_id": "protocol-a",
        "sample_count": 3,
        "row_count": 3,
        "rows_sha256": verify.sha256_file(rows_path),
    }
    verify.atomic_write_json(summary_path, summary)
    assert verify.load_reusable_cell(
        summary_path, rows_path, cell=cell, expected_samples=3,
        protocol_id="protocol-a",
    ) == summary
    assert verify.load_reusable_cell(
        summary_path, rows_path, cell=cell, expected_samples=3,
        protocol_id="protocol-b",
    ) is None
    rows[0]["word_sha256"] = "tampered"
    verify.atomic_write_csv(rows_path, rows)
    assert verify.load_reusable_cell(
        summary_path, rows_path, cell=cell, expected_samples=3,
        protocol_id="protocol-a",
    ) is None


def test_protocol_id_depends_on_all_code_and_manifest_hashes(manifest: dict) -> None:
    manifest_hash = verify.sha256_bytes(verify.canonical_json(manifest).encode("utf-8"))
    verifier_hash = verify.sha256_file(Path(verify.__file__))
    support_hash = verify.sha256_file(Path(verify.sph.__file__).resolve())
    environment_signature = {
        "python_major": int(verify.sys.version_info.major),
        "python_full": verify.sys.version,
        "numpy": verify.np.__version__,
        "scipy": verify.scipy.__version__,
        "mpmath": verify.mp.__version__,
    }

    def protocol_id(
        manifest_digest: str, verifier_digest: str,
        support_digest: str, environment: dict,
    ) -> str:
        return verify.sha256_bytes(verify.canonical_json({
            "manifest_sha256": manifest_digest,
            "verifier_sha256": verifier_digest,
            "sign_problem_hunter_sha256": support_digest,
            "environment_signature": environment,
        }).encode("utf-8"))

    protocol = protocol_id(
        manifest_hash, verifier_hash, support_hash, environment_signature
    )
    changed = deepcopy(manifest)
    changed["seed"] += 1
    changed_hash = verify.sha256_bytes(verify.canonical_json(changed).encode("utf-8"))
    changed_environment = dict(environment_signature)
    changed_environment["numpy"] = "changed"
    assert len(protocol) == 64
    assert protocol != protocol_id(changed_hash, verifier_hash, support_hash, environment_signature)
    assert protocol != protocol_id(manifest_hash, "0" * 64, support_hash, environment_signature)
    assert protocol != protocol_id(manifest_hash, verifier_hash, "0" * 64, environment_signature)
    assert protocol != protocol_id(manifest_hash, verifier_hash, support_hash, changed_environment)


def test_cli_cell_ids_are_stable_and_selectable(
    manifest: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    assert verify.main(["--manifest", str(MANIFEST_PATH), "--list-cells"]) == 0
    listed = capsys.readouterr().out.splitlines()
    expected = [cell.cell_id for cell in verify.build_cells(manifest)]
    assert listed == expected
    assert len(listed) == len(set(listed)) == 224
    assert listed[0] == "candidate__center__d03__m001"
    assert "semigroup_cone__n04__m064" in listed
    assert listed[-1] == "component__pm__n01__m064"

    chosen = [
        "candidate__center__d03__m001",
        "semigroup_cone__n02__m004",
    ]
    args = verify.parse_args([
        "--manifest", str(MANIFEST_PATH),
        "--cell-id", chosen[0],
        "--cell-id", chosen[1],
    ])
    assert args.cell_ids == chosen



@pytest.mark.parametrize(
    ("component", "expected_class"),
    [("++", "positive"), ("--", "negative"), ("-+", "inconclusive"), ("+-", "inconclusive")],
)
def test_o11_numeric_component_controls_and_exact_zero(
    manifest: dict, component: str, expected_class: str
) -> None:
    local_manifest = deepcopy(manifest)
    local_manifest["component_controls"]["samples_per_cell"] = 1
    label = component.replace("+", "p").replace("-", "m")
    cell = verify.Cell(
        f"component__{label}__n01__m001",
        "component_control",
        {"component": component, "n": 1, "dimension": 2, "depth": 1},
    )
    summary, rows = verify.run_component_cell(
        local_manifest,
        cell,
        np.random.default_rng(verify.derive_seed(manifest["seed"], cell.cell_id)),
    )
    assert summary["status"] == "pass"
    assert summary["sample_count"] == 1
    assert summary["determinant_class_counts"] == {expected_class: 1}
    expected_zero_count = int(component in {"-+", "+-"})
    raw_inconclusive_count = int(expected_class == "inconclusive")
    assert summary["inconclusive_determinants"] == raw_inconclusive_count
    assert summary["raw_inconclusive_determinants"] == raw_inconclusive_count
    assert summary["expected_exact_zero_controls"] == expected_zero_count
    assert summary["unexpected_inconclusive_determinants"] == 0

    assert len(rows) == 1
    assert rows[0]["det_class"] == expected_class
    if expected_class != "positive":
        assert rows[0]["det_method"] == "mpmath_100dps"
    if component in {"-+", "+-"}:
        assert rows[0]["det_method"] == "mpmath_100dps"
        assert float(rows[0]["sigma_min_i_plus_t"]) <= float(
            manifest["thresholds"]["component_zero_sigma"]
        )


def test_expected_exact_zero_aggregate_and_markdown_are_distinct(
    manifest: dict,
) -> None:
    mixed_cells = [
        cell
        for cell in verify.build_cells(manifest)
        if cell.kind == "component_control"
        and cell.parameters["component"] in {"-+", "+-"}
    ]
    assert len(mixed_cells) == 14
    summaries = {
        cell.cell_id: {
            "status": "pass",
            "high_precision_escalations": 32,
            "inconclusive_determinants": 32,
            "raw_inconclusive_determinants": 32,
            "expected_exact_zero_controls": 32,
            "unexpected_inconclusive_determinants": 0,
        }
        for cell in mixed_cells
    }
    aggregates = verify.aggregate_cell_results(mixed_cells, summaries)
    assert aggregates["inconclusive_determinants"] == 448
    assert aggregates["raw_inconclusive_determinants"] == 448
    assert aggregates["expected_exact_zero_controls"] == 448
    assert aggregates["unexpected_inconclusive_determinants"] == 0

    markdown = verify.report_markdown(
        {
            "status": "pass",
            "protocol_id": "fixture",
            "completed_cells": len(mixed_cells),
            "total_cells": len(mixed_cells),
            "sample_rows": 448,
            "stage_status": {
                "exact_certificates": "pass",
                "twirl_checks": "pass",
                "physical_benchmark": "pass",
            },
            "aggregates": aggregates,
            "failed_cells": [],
            "pending_cells": [],
        }
    )
    assert "Raw numeric inconclusive classifications: 448" in markdown
    assert "Expected exact-zero mixed O(1,1) controls: 448" in markdown
    assert "Unexpected inconclusive determinants: 0" in markdown


def test_twirl_stage_parses_fraction_tau_and_passes(manifest: dict) -> None:
    result = verify.run_twirl_checks(manifest)
    assert result["status"] == "pass"
    assert result["parameters"]["tau"] == pytest.approx(0.1)
    for family in ("A", "B"):
        assert result["checks"][family] == {"hermitian": True, "non_gaussian": True}


def test_complete_fast_path_verifies_report_hashes(
    manifest: dict, tmp_path: Path
) -> None:
    manifest_hash = verify.sha256_bytes(verify.canonical_json(manifest).encode("utf-8"))
    verifier_hash = verify.sha256_file(Path(verify.__file__))
    support_hash = verify.sha256_file(Path(verify.sph.__file__).resolve())
    environment_signature = {
        "python_major": int(verify.sys.version_info.major),
        "python_full": verify.sys.version,
        "numpy": verify.np.__version__,
        "scipy": verify.scipy.__version__,
        "mpmath": verify.mp.__version__,
    }
    protocol_id = verify.sha256_bytes(verify.canonical_json({
        "manifest_sha256": manifest_hash,
        "verifier_sha256": verifier_hash,
        "sign_problem_hunter_sha256": support_hash,
        "environment_signature": environment_signature,
    }).encode("utf-8"))

    report_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    complete_path = tmp_path / "COMPLETE"
    report = {"schema_version": 1, "status": "pass", "protocol_id": protocol_id}
    verify.atomic_write_json(report_path, report)
    verify.atomic_write_text(markdown_path, "# completed fixture\n")
    verify.atomic_write_json(complete_path, {
        "protocol_id": protocol_id,
        "report_json_sha256": verify.sha256_file(report_path),
        "report_markdown_sha256": verify.sha256_file(markdown_path),
        "completed_at": "fixture",
    })
    assert verify.run_verification(MANIFEST_PATH, tmp_path) == report

    verify.atomic_write_text(markdown_path, "# tampered fixture\n")
    with pytest.raises(RuntimeError, match="COMPLETE"):
        verify.run_verification(MANIFEST_PATH, tmp_path)
