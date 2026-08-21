#!/usr/bin/env python3
"""Render deterministic LaTeX evidence assets for Paper I."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


MODEL_ORDER = ("laughlin", "susy_syk", "moore_read", "lattice_susy", "xcube")
MODEL_LABELS = {
    "laughlin": "Laughlin parents",
    "susy_syk": r"$\mathcal{N}=2$ SYK",
    "moore_read": "Moore--Read parent",
    "lattice_susy": r"Lattice $\mathcal{N}=2$ SUSY",
    "xcube": "X-cube control",
}
FORBIDDEN_POSITIVE_CLAIMS = (
    "asymptotic_geometric_eth",
    "universal_geometric_eth",
    "cross_mechanism_universal_scaling",
    "independent_model_operator_class_established",
    "thermalization",
    "lyapunov_behavior",
    "moore_read_N8_production_result",
    "centered_full_r4_moore_read_N4",
    "centered_full_r4_lattice_susy_m1_m2_m3",
)
FORBIDDEN_TEXT = ("nan", "unresolved-placeholder", "inferred universal")


def _walk(value: Any, path: str = "registry") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key in sorted(value):
            yield from _walk(value[key], f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    else:
        yield path, value


def _validate_payload(payload: dict[str, Any]) -> None:
    required = {"sources", "models", "observables", "gates", "claims", "source_hashes"}
    if set(payload) != required:
        missing = sorted(required - set(payload))
        extra = sorted(set(payload) - required)
        raise RuntimeError(f"invalid registry keys; missing={missing}, extra={extra}")
    if tuple(name for name in MODEL_ORDER if name in payload["models"]) != MODEL_ORDER:
        raise RuntimeError("registry is missing a required Paper I model")
    for claim in FORBIDDEN_POSITIVE_CLAIMS:
        if payload["claims"].get(claim) is not False:
            raise RuntimeError(f"forbidden positive claim in registry: {claim}")
    for path, value in _walk(payload):
        if isinstance(value, float) and not math.isfinite(value):
            raise RuntimeError(f"non-finite empirical value at {path}")
        if isinstance(value, str):
            lowered = value.lower()
            if any(token in lowered for token in FORBIDDEN_TEXT):
                raise RuntimeError(f"forbidden placeholder or claim text at {path}")
    hashes = payload["source_hashes"]
    if len(hashes) < 11 or any(
        not isinstance(value, str) or len(value) != 64 for value in hashes.values()
    ):
        raise RuntimeError("registry source hashes are incomplete")
    full = payload["observables"].get("centered_whitened_full_r4_v13", {})
    if (
        full.get("claim_eligible") is not True
        or full.get("inference_status")
        != "finite_rank_exact_population_mean_familywise"
        or full.get("claim_gate_by_case")
        != {
            "lattice_susy_m1": False,
            "lattice_susy_m2": False,
            "lattice_susy_m3": False,
            "moore_read_N4": False,
            "moore_read_N6": True,
        }
    ):
        raise RuntimeError("centered full-R4 finite-rank gate is contradictory")
    if (
        payload["claims"].get("centered_full_r4_positive_only_moore_read_N6")
        is not True
        or payload["claims"].get("centered_full_r4_positive_claim") is not True
        or payload["claims"].get(
            "centered_full_r4_population_mean_audit_complete"
        )
        is not True
        or payload["claims"].get("strongest_statistical_scope")
        != "finite_rank_domain_limited_moore_read_N6_only"
    ):
        raise RuntimeError("centered full-R4 claim scope is contradictory")
    response = full.get("response_sign_provenance", {})
    if (
        response.get("stored_channel_interpretation")
        != "stored_channels=-X_a_when_source_omits_Kato_minus"
        or response.get("even_contractions_invariant_under_global_channel_sign")
        is not True
    ):
        raise RuntimeError("centered response-sign provenance is contradictory")


def _canonical_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_header(payload: dict[str, Any], title: str) -> list[str]:
    lines = [
        "% AUTO-GENERATED FILE. DO NOT EDIT.",
        f"% {title}",
        f"% registry-payload-sha256: {_canonical_payload_hash(payload)}",
    ]
    for source_id in sorted(payload["source_hashes"]):
        lines.append(f"% source {source_id}: {payload['source_hashes'][source_id]}")
    lines.append(
        "% source protected_scaling_inference_v4: unavailable (not tracked in delivery branch)"
    )
    return lines


def _number(value: int | float) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"empirical macro received a non-numeric value: {value!r}")
    if isinstance(value, float) and not math.isfinite(value):
        raise RuntimeError("non-finite empirical value")
    if isinstance(value, int):
        return str(value)
    if value == 0.0:
        return "0"
    rendered = f"{value:.8g}"
    if "e" not in rendered.lower():
        return rendered
    mantissa, exponent = rendered.lower().split("e")
    return rf"{mantissa}\times 10^{{{int(exponent)}}}"


def _macro(name: str, value: int | float) -> str:
    return rf"\newcommand{{\{name}}}{{{_number(value)}}}"


def _text_macro(name: str, value: str) -> str:
    return rf"\newcommand{{\{name}}}{{\text{{{_latex_text(value)}}}}}"


def _latex_text(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in value)


def _words(value: str) -> str:
    words = value.replace("_", " ")
    words = words.replace("two body", "two-body").replace("three body", "three-body")
    words = words.replace("finite size", "finite-size")
    return _latex_text(words)


def _english_index(value: int) -> str:
    names = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
    try:
        return names[value]
    except KeyError as exc:
        raise RuntimeError(f"no stable macro-name mapping for index {value}") from exc


def render_results(payload: dict[str, Any]) -> str:
    """Render empirical values as LaTeX macros."""

    _validate_payload(payload)
    lines = _source_header(payload, "Paper I empirical result macros (v13)")
    lines.append("")

    spectral = payload["observables"]["spectral_silence"]
    lines.extend(
        [
            _macro("RegisteredSourceCount", len(payload["source_hashes"])),
            _macro("SpectralKernelBandwidth", spectral["kernel_bandwidth"]),
            _macro("SpectralExternalGap", spectral["external_gap"]),
            _macro("SpectralFiberRank", spectral["fiber_rank"]),
            r"\newcommand{\StoredResponseChannelConvention}{\(\widetilde X_a=-X_a\) when the source omits the Kato minus}",
            r"\newcommand{\EvenResponseContractionsSignInvariant}{\text{yes}}",
        ]
    )

    matrix = payload["observables"]["matrix_element_geometry"]
    lines.append(
        _macro(
            "LaughlinDescriptiveSlopePerParticle",
            matrix["descriptive_slope_per_particle"],
        )
    )
    for case in sorted(matrix["cases"], key=lambda item: item["N"]):
        suffix = f"N{_english_index(case['N'])}"
        lines.extend(
            [
                _macro(f"Laughlin{suffix}Rank", case["rank"]),
                _macro(f"Laughlin{suffix}BasisDimension", case["basis_dimension"]),
                _macro(f"Laughlin{suffix}ExternalGap", case["external_gap"]),
                _macro(
                    f"Laughlin{suffix}PhysicalTwoPairRFour",
                    case["physical_R4_median"],
                ),
                _macro(
                    f"Laughlin{suffix}GaussianTwoPairRFour",
                    case["gaussian_R4_interval"][1],
                ),
                _macro(f"Laughlin{suffix}FourthMomentExcess", case["physical_excess"]),
                _macro(
                    f"Laughlin{suffix}StructuredTwoPairRFour",
                    case["structured_R4"],
                ),
            ]
        )

    continuum = payload["models"]["laughlin"]["continuum_connected_excess_by_size"]
    for size in sorted(continuum, key=int):
        lines.append(
            _macro(
                f"ContinuumLaughlinN{_english_index(int(size))}ConnectedExcess",
                continuum[size],
            )
        )

    for case in sorted(payload["models"]["moore_read"]["cases"], key=lambda item: item["size"]):
        suffix = f"N{_english_index(case['size'])}"
        lines.extend(
            [
                _macro(f"MooreRead{suffix}Rank", case["fiber_rank"]),
                _macro(f"MooreRead{suffix}ExternalGap", case["external_gap"]),
                _macro(
                    f"MooreRead{suffix}LocalTwoPairRFour",
                    case["local_R4_median"],
                ),
                _macro(
                    f"MooreRead{suffix}StructuredTwoPairRFour",
                    case["structured_R4"],
                ),
            ]
        )

    raw_moment = payload["observables"][
        "raw_uncentered_moment_residual_v12"
    ]
    full_r4 = payload["observables"]["centered_whitened_full_r4_v13"]
    for case_id in ("moore_read_N4", "moore_read_N6"):
        raw_case = raw_moment["cases"][case_id]
        full_case = full_r4["cases"][case_id]
        suffix = "NFour" if case_id.endswith("N4") else "NSix"
        lines.extend(
            [
                _macro(
                    f"MooreRead{suffix}RawMomentResidualEstimate",
                    raw_case["directional_estimate"],
                ),
                _macro(
                    f"MooreRead{suffix}RawMomentResidualPValue",
                    raw_case["one_sided_p_value"],
                ),
                _macro(
                    f"MooreRead{suffix}RawMomentResidualNorm",
                    raw_case["normalized_cumulant_norm"],
                ),
                _macro(
                    f"MooreRead{suffix}FullRFourDirectionalEstimate",
                    full_case["primary"]["summary"]["directional_estimate"],
                ),
                _macro(
                    f"MooreRead{suffix}FullRFourLower",
                    full_case["primary"]["summary"]["one_sided_interval_low"],
                ),
                _macro(
                    f"MooreRead{suffix}FullRFourPValue",
                    full_case["primary"]["summary"]["one_sided_p_value"],
                ),
                _macro(
                    f"MooreRead{suffix}FullRFourZScore",
                    full_case["primary"]["summary"]["z_score"],
                ),
                _macro(
                    f"MooreRead{suffix}FullRFourCumulantNorm",
                    full_case["primary"]["summary"]["normalized_cumulant_norm"],
                ),
                _macro(
                    f"MooreRead{suffix}FullRFourFamilywiseLower",
                    full_case["primary"]["familywise_one_sided_interval_low"],
                ),
                _macro(
                    f"MooreRead{suffix}FullRFourReverseDirectionalEstimate",
                    full_case["reverse_descriptive"]["summary"][
                        "directional_estimate"
                    ],
                ),
                _text_macro(
                    f"MooreRead{suffix}FullRFourClaimStatus",
                    "passed"
                    if full_case["primary"]["gate_for_claim"]
                    else "not passed",
                ),
            ]
        )

    for case in sorted(payload["models"]["lattice_susy"]["cases"], key=lambda item: item["size"]):
        suffix = f"M{_english_index(case['size'])}"
        lines.extend(
            [
                _macro(f"LatticeSusy{suffix}Rank", case["fiber_rank"]),
                _macro(f"LatticeSusy{suffix}ExternalGap", case["external_gap"]),
                _macro(
                    f"LatticeSusy{suffix}LocalTwoPairRFour", case["local_R4"]
                ),
                _macro(
                    f"LatticeSusy{suffix}IsotropicTwoPairRFour",
                    case["isotropic_R4"],
                ),
                _macro(f"LatticeSusy{suffix}HodgeBalance", case["hodge_balance_local"]),
            ]
        )
        case_id = f"lattice_susy_m{case['size']}"
        raw_case = raw_moment["cases"][case_id]
        full_case = full_r4["cases"][case_id]
        lines.extend(
            [
                _macro(
                    f"LatticeSusy{suffix}RawMomentResidualEstimate",
                    raw_case["directional_estimate"],
                ),
                _macro(
                    f"LatticeSusy{suffix}RawMomentResidualPValue",
                    raw_case["one_sided_p_value"],
                ),
                _macro(
                    f"LatticeSusy{suffix}RawMomentResidualNorm",
                    raw_case["normalized_cumulant_norm"],
                ),
                _macro(
                    f"LatticeSusy{suffix}FullRFourDirectionalEstimate",
                    full_case["primary"]["summary"]["directional_estimate"],
                ),
                _macro(
                    f"LatticeSusy{suffix}FullRFourLower",
                    full_case["primary"]["summary"]["one_sided_interval_low"],
                ),
                _macro(
                    f"LatticeSusy{suffix}FullRFourPValue",
                    full_case["primary"]["summary"]["one_sided_p_value"],
                ),
                _macro(
                    f"LatticeSusy{suffix}FullRFourZScore",
                    full_case["primary"]["summary"]["z_score"],
                ),
                _macro(
                    f"LatticeSusy{suffix}FullRFourCumulantNorm",
                    full_case["primary"]["summary"]["normalized_cumulant_norm"],
                ),
                _macro(
                    f"LatticeSusy{suffix}FullRFourFamilywiseLower",
                    full_case["primary"]["familywise_one_sided_interval_low"],
                ),
                _macro(
                    f"LatticeSusy{suffix}FullRFourReverseDirectionalEstimate",
                    full_case["reverse_descriptive"]["summary"][
                        "directional_estimate"
                    ],
                ),
                _text_macro(
                    f"LatticeSusy{suffix}FullRFourClaimStatus",
                    "passed"
                    if full_case["primary"]["gate_for_claim"]
                    else "not passed",
                ),
            ]
        )

    syk = payload["models"]["susy_syk"]["N14_observed_medians"]
    lines.extend(
        [
            _macro("SusySykNFourteenMedianOne", syk[0]),
            _macro("SusySykNFourteenMedianTwo", syk[1]),
        ]
    )

    xcube = payload["models"]["xcube"]
    lines.extend(
        [
            _macro("XCubeCoefficientCurvature", xcube["coefficient_curvature"]),
            _macro("XCubeTransportCurvatureEigenvalue", xcube["transport_curvature_eigenvalue"]),
            _macro("XCubeTransportConnectedVariance", xcube["transport_connected_variance"]),
        ]
    )

    for case in sorted(
        payload["observables"]["topological_holonomy"]["sizes"],
        key=lambda item: item["N"],
    ):
        suffix = f"N{_english_index(case['N'])}"
        lines.extend(
            [
                _macro(f"Holonomy{suffix}Rank", case["rank"]),
                _macro(f"Holonomy{suffix}ChernNumber", case["base_chern_integer"]),
                _macro(f"Holonomy{suffix}MinimumGap", case["minimum_external_gap"]),
                _macro(f"Holonomy{suffix}BaseGapRatio", case["base_gap_ratio"]),
                _macro(
                    f"Holonomy{suffix}FinalGapRatioMedian",
                    case["final_gap_ratio_interval"][1],
                ),
                _macro(
                    f"Holonomy{suffix}MinimumOverlapSingularValue",
                    case["minimum_overlap_singular_value"],
                ),
            ]
        )

    raw_protocol = raw_moment["protocol"]
    full_protocol = full_r4["protocol"]
    lines.extend(
        [
            _macro(
                "RawMomentResidualRealizationCount",
                raw_protocol["realization_count"],
            ),
            _macro("RawMomentResidualLabelCount", raw_protocol["label_count"]),
            _macro(
                "FullRFourTrainingCount",
                len(full_protocol["primary_training_indices"]),
            ),
            _macro(
                "FullRFourInferenceCount",
                len(full_protocol["primary_inference_indices"]),
            ),
            _macro(
                "FullRFourPairingCount", full_protocol["complete_wick_pairings"]
            ),
            _macro("FullRFourFamilyAlpha", full_protocol["family_alpha"]),
            _macro("FullRFourPerCaseAlpha", full_protocol["per_case_alpha"]),
            _macro(
                "FullRFourPrimaryFamilySize",
                full_protocol["primary_case_family_size"],
            ),
            _macro(
                "FullRFourStudentTDegreesOfFreedom",
                full_protocol["student_t_degrees_of_freedom"],
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def _availability(value: Any) -> tuple[str, str]:
    if value is True:
        return r"\(\text{available}\)", "available"
    if value is False:
        return r"\(\text{not tested}\)", "not-tested"
    if value == "not_applicable_exact_control":
        return r"\(\substack{\text{not}\\\text{applicable}}\)", "not-applicable"
    raise RuntimeError(f"unregistered evidence availability state: {value!r}")


def _production(value: Any) -> tuple[str, str]:
    if value is True:
        return r"\(\text{complete}\)", "complete"
    if value is False:
        return r"\(\text{pilot only}\)", "pilot-only"
    raise RuntimeError(f"unregistered production state: {value!r}")


def _ranks(model_name: str, model: dict[str, Any]) -> str:
    if model_name == "laughlin":
        ranks = model["matrix_element_ranks"]
    elif model_name in {"moore_read", "lattice_susy"}:
        ranks = [case["fiber_rank"] for case in model["cases"]]
    else:
        return r"\(\text{not tested}\)"
    return ", ".join(str(rank) for rank in ranks)


def render_model_table(payload: dict[str, Any]) -> str:
    """Render the mechanism and evidence-status table."""

    _validate_payload(payload)
    row_end = " " + "\\" * 2
    lines = _source_header(payload, "Paper I model table (v13)")
    lines.extend(
        [
            "",
            r"\begin{table*}[t]",
            r"\caption{Mechanisms that protect exact degeneracy and the evidence currently available for geometric statistics. The centered three-pairing statistic is denoted \(R_4^{\mathrm{full}}\). Its primary gates use exact registered finite-ensemble means, a Student-\(t_{11}\) finite-sample reference, and Bonferroni control over five cases. A missing calculation is written as \(\text{not tested}\), not as a null result.}",
            r"\label{tab:model-evidence}",
            r"\begin{ruledtabular}",
            r"\begin{tabular}{@{}p{0.10\textwidth}p{0.18\textwidth}p{0.13\textwidth}p{0.09\textwidth}p{0.14\textwidth}p{0.10\textwidth}p{0.08\textwidth}@{}}",
            "Model & Degeneracy mechanism & Geometric role & "
            r"\(\substack{\text{Sampled}\\D}\) & "
            r"\(\substack{R_4^{\mathrm{full}}\\\text{primary split}}\) & "
            r"\(\substack{\text{Independent}\\\text{ensemble}}\) & Run state"
            + row_end,
            r"\hline",
            r"% canonical column: \(R_4^{\mathrm{full}}\), primary split",
            "% canonical Moore--Read status: N=4: not passed; N=6: passed (finite-rank)",
        ]
    )
    for name in MODEL_ORDER:
        model = payload["models"][name]
        full_r4, full_r4_meta = _availability(
            model["centered_complete_covariance_v13"]
        )
        ensemble, ensemble_meta = _availability(model["independent_ensemble_complete"])
        production, production_meta = _production(model["production_complete"])
        if model["centered_complete_covariance_v13"] is True:
            if name == "moore_read":
                full_r4 = (
                    r"\(\substack{N=4:\\ \text{not passed}\\"
                    r"N=6:\\ \text{passed}\\ \text{finite rank}}\)"
                )
                full_r4_meta = "N4-not-passed-N6-passed-finite-rank"
            else:
                full_r4 = r"\(\substack{m=1,2,3:\\\text{not passed}}\)"
                full_r4_meta = "m1-m2-m3-not-passed"
        row = (
            f"{MODEL_LABELS[name]} & {_words(model['mechanism'])} & "
            f"{_words(model['role'])} & {_ranks(name, model)} & {full_r4} & "
            f"{ensemble} & {production}{row_end} "
            f"% MODELROW:{name}; centered-full-r4={full_r4_meta}; "
            f"independent-ensemble={ensemble_meta}; production={production_meta}"
        )
        lines.append(row)
    lines.extend(
        [
            r"\end{tabular}",
            r"\end{ruledtabular}",
            r"\end{table*}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_evidence_matrix(payload: dict[str, Any]) -> str:
    """Render the claim-to-evidence boundary table."""

    _validate_payload(payload)
    row_end = " " + "\\" * 2
    lines = _source_header(payload, "Paper I evidence matrix (v13)")
    lines.extend(
        [
            "",
            r"\begin{table*}[t]",
            r"\caption{Claim boundary used in the main text. \(R_4^{2\mathrm{pair}}\), the raw uncentered moment residual, and centered \(R_4^{\mathrm{full}}\) are distinct observables. The centered primary gates use exact registered finite-ensemble population means, a Student-\(t_{11}\) reference, and a Bonferroni familywise threshold over five cases.}",
            r"\label{tab:claim-boundary}",
            r"\begin{ruledtabular}",
            r"\begin{tabular}{p{0.25\textwidth}p{0.19\textwidth}p{0.49\textwidth}}",
            "Question & Evidence state & Permitted statement" + row_end,
            r"\hline",
            r"Energy-spectrum diagnostic & \(\text{established}\) & The connected spectral form factor is silent inside the registered exactly degenerate manifold."
            + row_end,
            r"Projector geometry & \(\text{established}\) & The protected projector moves and its off-fiber response is nonzero in the opened stochastic families."
            + row_end,
            r"Two-pair Wick residual, \(R_4^{2\mathrm{pair}}\) & \(\text{finite-size observable}\) & The registered panel values subtract the two ordinary complex pairings; they are not the centered three-pairing statistic."
            + row_end,
            r"v12 three-pairing value & \(\text{claim-ineligible}\) & This is a raw, uncentered moment residual evaluated without channel whitening; it is retained for traceability and is not a complete-covariance gate."
            + row_end,
            r"Laughlin and SUSY-SYK \(R_4^{\mathrm{full}}\) & \(\text{not tested}\) & No centered three-pairing conclusion is assigned to the production data."
            + row_end,
            r"Moore--Read \(R_4^{\mathrm{full}}\) & \(\text{finite-rank N=6 only}\) & The N=4 gate does not pass and N=6 gate passes with familywise lower bound \(\MooreReadNSixFullRFourFamilywiseLower\); this is a finite-rank N=6-only result."
            + row_end,
            r"Lattice SUSY \(R_4^{\mathrm{full}}\) & \(\text{positive-direction gate not passed}\) & The familywise primary gate is not passed for \(D=2,4,8\); this is not a Gaussianity claim."
            + row_end,
            r"Reverse 12/12 split & \(\text{descriptive}\) & The reverse split is descriptive only; it is never pooled with the primary split and exposes no claim gate."
            + row_end,
            r"X-cube controls & \(\text{exact structured control}\) & Coefficient reweighting is flat; local isospectral transport has scalar curvature and zero connected variance."
            + row_end,
            r"Independent model/operator ensemble & \(\text{not tested}\) & No cross-mechanism independent-ensemble closure is claimed."
            + row_end,
            r"Large-rank or universal limit & \(\text{not established}\) & The N=6 gate does not provide asymptotic or universal evidence; claim eligibility is restricted to the registered finite-rank N=6 calculation."
            + row_end,
            r"\end{tabular}",
            r"\end{ruledtabular}",
            r"\end{table*}",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    registry_path = (
        repo_root
        / "01_task_folder/task_05/script/output/paper1_prb_v13/evidence_registry_v13.json"
    )
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    destination = repo_root / "overleaf_sync/exactly_degenerate_quantum_chaos_prb/generated"
    outputs = {
        "results_v13.tex": render_results(payload),
        "evidence_matrix_v13.tex": render_evidence_matrix(payload),
        "model_table_v13.tex": render_model_table(payload),
    }
    for filename, content in outputs.items():
        _write_atomic(destination / filename, content)
        print(destination / filename)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
