#!/usr/bin/env python3
"""Generate the v12 manuscript macros, table, and figure from audited JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "v12"
SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parents[2]
OUTPUT_ROOT = SCRIPT_ROOT / "output"
MANUSCRIPT_ROOT = REPO_ROOT / "overleaf_sync" / "cross_mechanism_geometric_eth"
INFERENCE_JSON = OUTPUT_ROOT / f"cross_mechanism_geometric_eth_{VERSION}.json"
COMPLETE_JSON = OUTPUT_ROOT / f"cross_complete_covariance_{VERSION}.json"
ASSET_JSON = OUTPUT_ROOT / f"cross_mechanism_assets_{VERSION}.json"
RESOURCE_JSON = OUTPUT_ROOT / "moore_read_resource_estimate_v9.json"
RESULTS_TEX = MANUSCRIPT_ROOT / "generated" / f"results_{VERSION}.tex"
TABLE_TEX = MANUSCRIPT_ROOT / "generated" / f"mechanism_table_{VERSION}.tex"
FIGURE_TARGET = MANUSCRIPT_ROOT / "figures" / f"cross_mechanism_{VERSION}.pdf"
MANIFEST_JSON = OUTPUT_ROOT / f"cross_mechanism_manuscript_assets_{VERSION}.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def _atomic_text(path: Path, value: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(target)


def _atomic_copy(source: Path, target: Path) -> None:
    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copyfile(source, temporary)
    temporary.replace(destination)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _macro(name: str, value: object) -> str:
    return rf"\newcommand{{\{name}}}{{{value}}}"


def _scientific_tex(value: float, digits: int = 2) -> str:
    coefficient, exponent = f"{float(value):.{digits}e}".split("e")
    return rf"{coefficient}\times 10^{{{int(exponent)}}}"


def _comma(value: int) -> str:
    return f"{int(value):,}"


def _resource_case(resource: dict[str, Any], particles: int) -> dict[str, Any]:
    for case in resource.get("cases", []):
        if int(case.get("N", -1)) == int(particles):
            return case
    raise ValueError(f"missing Moore--Read resource case N={particles}")


def build_manuscript_assets(
    *,
    inference_json: Path = INFERENCE_JSON,
    complete_json: Path = COMPLETE_JSON,
    asset_json: Path = ASSET_JSON,
    resource_json: Path = RESOURCE_JSON,
    results_tex: Path = RESULTS_TEX,
    table_tex: Path = TABLE_TEX,
    figure_target: Path = FIGURE_TARGET,
    manifest_json: Path = MANIFEST_JSON,
) -> dict[str, Any]:
    """Build manuscript inputs only from passed, branch-matched artifacts."""

    inference = _load(inference_json)
    complete = _load(complete_json)
    assets = _load(asset_json)
    resource = _load(resource_json)
    if not (
        inference.get("version") == VERSION
        and inference.get("all_checks_pass") is True
        and inference.get("claim_status")
        == "provisional_opened_cross_mechanism_result"
        and complete.get("version") == VERSION
        and complete.get("all_checks_pass") is True
        and assets.get("version") == VERSION
        and all(assets.get("checks", {}).values())
        and resource.get("version") == "v9"
        and all(resource.get("checks", {}).values())
    ):
        raise ValueError("a manuscript source has not passed its scientific audit")
    if assets.get("selected_branch") != inference.get("selected_branch"):
        raise ValueError("figure branch does not match the inference branch")
    figure_source = OUTPUT_ROOT / str(assets["figure_pdf"])
    if sha256(figure_source) != str(assets["figure_pdf_sha256"]):
        raise ValueError("figure hash does not match the asset manifest")

    models = inference["models"]
    moore = models["moore_read"]
    lattice = models["lattice_susy"]
    xcube = models["xcube"]
    mr_cases = {int(case["size"]): case for case in moore["cases"]}
    ls_cases = {int(case["size"]): case for case in lattice["cases"]}
    covariance = complete["cases"]
    n8 = _resource_case(resource, 8)
    n10 = _resource_case(resource, 10)

    lines = [
        "% Generated from audited v12 JSON; do not edit numerical values.",
        _macro("CrossMechanismBranch", str(inference["selected_branch"]).replace("_", r"\_")),
        _macro("MRParticleSizes", r"4,6"),
        _macro("MRNFourRank", int(mr_cases[4]["fiber_rank"])),
        _macro("MRNSixRank", int(mr_cases[6]["fiber_rank"])),
        _macro("MRNFourBasis", int(covariance["moore_read_N4"]["ambient_dimension"])),
        _macro("MRNSixBasis", int(covariance["moore_read_N6"]["ambient_dimension"])),
        _macro("MRNFourGap", f"{float(mr_cases[4]['external_gap']):.6f}"),
        _macro("MRNSixGap", f"{float(mr_cases[6]['external_gap']):.6f}"),
        _macro("MRNFourRFour", f"{float(mr_cases[4]['local_R4_median']):.4f}"),
        _macro("MRNSixRFour", f"{float(mr_cases[6]['local_R4_median']):.4f}"),
        _macro("MRNFourCumulant", f"{float(covariance['moore_read_N4']['directional_estimate']):.4f}"),
        _macro("MRNFourCumulantSE", f"{float(covariance['moore_read_N4']['standard_error']):.4f}"),
        _macro("MRNFourZ", f"{float(covariance['moore_read_N4']['z_score']):.2f}"),
        _macro("MRNFourP", _scientific_tex(float(covariance["moore_read_N4"]["one_sided_p_value"]))),
        _macro("MRNSixCumulant", f"{float(covariance['moore_read_N6']['directional_estimate']):.4f}"),
        _macro("MRNSixCumulantSE", f"{float(covariance['moore_read_N6']['standard_error']):.4f}"),
        _macro("MRNSixZ", f"{float(covariance['moore_read_N6']['z_score']):.2f}"),
        _macro("MRNSixP", _scientific_tex(float(covariance["moore_read_N6"]["one_sided_p_value"]))),
        _macro("PanelCount", int(complete["protocol"]["realization_count"])),
        _macro("PanelPairCount", int(covariance["moore_read_N4"]["unordered_pair_count"])),
        _macro("WickPairingCount", int(complete["protocol"]["wick_pairings"])),
        _macro("LatticeCycleSizes", r"1,2,3"),
        _macro("LatticeRanks", ",".join(str(int(ls_cases[size]["fiber_rank"])) for size in (1, 2, 3))),
        _macro("LatticeBasisDims", ",".join(str(int(covariance[f"lattice_susy_m{size}"]["ambient_dimension"])) for size in (1, 2, 3))),
        _macro("LatticeCumulants", r",\,".join(f"{float(covariance[f'lattice_susy_m{size}']['directional_estimate']):.4f}" for size in (1, 2, 3))),
        _macro("LatticePValues", r",\,".join(f"{float(covariance[f'lattice_susy_m{size}']['one_sided_p_value']):.4f}" for size in (1, 2, 3))),
        _macro("LatticeCumulantNorms", r",\,".join(f"{float(covariance[f'lattice_susy_m{size}']['normalized_cumulant_norm']):.3f}" for size in (1, 2, 3))),
        _macro("XCubeLengths", r"2,3,4,5"),
        _macro("XCubeCurvature", f"{float(xcube['transport_curvature_eigenvalue']):.1f}"),
        _macro("XCubeConnectedVariance", f"{float(xcube['transport_connected_variance']):.1f}"),
        _macro("MRNEightBasis", _comma(int(n8["basis_dimension"]))),
        _macro("MRNEightRank", _comma(int(n8["zero_mode_rank"]))),
        _macro("MRNEightConstraintNNZ", _comma(int(n8["constraint_nnz"]))),
        _macro("MRNEightActionProducts", _comma(int(n8["parent_action_nonzero_products"]))),
        _macro("MRNTenBasis", _comma(int(n10["basis_dimension"]))),
        _macro("MRNTenRank", _comma(int(n10["zero_mode_rank"]))),
        _macro("MRNTenConstraintNNZ", _comma(int(n10["constraint_nnz"]))),
        _macro("MRNTenActionProducts", _comma(int(n10["parent_action_nonzero_products"]))),
    ]
    _atomic_text(results_tex, "\n".join(lines) + "\n")

    mr_sizes = ",".join(str(size) for size in sorted(mr_cases))
    mr_ranks = ",".join(
        str(int(mr_cases[size]["fiber_rank"])) for size in sorted(mr_cases)
    )
    ls_sizes = ",".join(str(size) for size in sorted(ls_cases))
    ls_ranks = ",".join(
        str(int(ls_cases[size]["fiber_rank"])) for size in sorted(ls_cases)
    )
    xcube_sizes = ",".join(str(size) for size in (2, 3, 4, 5))
    table = rf"""% Generated from audited v12 JSON; do not edit.
\begin{{table*}}[t]
\caption{{\label{{tab:mechanisms}}Three independently implemented exact-degeneracy mechanisms. The last column states what the opened calculation establishes; a failed fixed-direction gate is not a proof that every fourth cumulant vanishes.}}
\begin{{tabular*}}{{\textwidth}}{{@{{\extracolsep{{\fill}}}}lllll}}
\toprule
Mechanism & Degeneracy source & Sizes & $D$ & Opened result \\
\midrule
Moore--Read & Three-body clustered parent & $N={mr_sizes}$ & ${mr_ranks}$ & Positive panel cumulant \\
Lattice SUSY & Graph cohomology & $m={ls_sizes}$ & ${ls_ranks}$ & Registered direction not positive \\
X-cube code & Stabilizer identities & $L={xcube_sizes}$ & $2^{{6L-3}}$ & Zero or scalar curvature \\
\bottomrule
\end{{tabular*}}
\end{{table*}}
"""
    _atomic_text(table_tex, table)
    _atomic_copy(figure_source, figure_target)

    checks = {
        "inference_passed": inference.get("all_checks_pass") is True,
        "complete_covariance_passed": complete.get("all_checks_pass") is True,
        "resource_audit_passed": all(resource.get("checks", {}).values()),
        "branch_is_domain_limited": inference.get("selected_branch")
        == "domain_limited_geometric_eth",
        "moore_read_positive_both_sizes": all(
            covariance[f"moore_read_N{size}"]["positive_directional_gate"]
            for size in (4, 6)
        ),
        "lattice_susy_no_registered_positive_case": not any(
            covariance[f"lattice_susy_m{size}"]["positive_directional_gate"]
            for size in (1, 2, 3)
        ),
        "xcube_exact_control": xcube["coefficient_curvature"] == 0.0
        and xcube["transport_connected_variance"] == 0.0,
        "figure_copy_exact": sha256(figure_source) == sha256(figure_target),
    }
    manifest = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "selected_branch": inference["selected_branch"],
        "inputs": {
            Path(path).name: sha256(path)
            for path in (inference_json, complete_json, asset_json, resource_json, figure_source)
        },
        "outputs": {
            Path(path).name: sha256(path)
            for path in (results_tex, table_tex, figure_target)
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    if not manifest["passed"]:
        raise RuntimeError(f"cross-mechanism manuscript assets failed: {checks}")
    _atomic_json(manifest_json, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=MANIFEST_JSON)
    arguments = parser.parse_args()
    payload = build_manuscript_assets(manifest_json=arguments.output)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
