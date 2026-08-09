#!/usr/bin/env python3
"""Build and validate the reviewer-facing Issue 128 delivery package."""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_CEILING, localcontext
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
CERTIFICATE = Path("certificates/issue128-certificate.json")
D4_SIDECAR = Path("certificates/issue128-d4-groups.json")
D5_SIDECAR = Path("certificates/issue128-d5-groups.json.gz")
SMALL_CROSSCHECK = Path("certificates/issue128-small-crosscheck.json")

EXPECTED: dict[str, object] = {
    "published_steps": 393,
    "candidate_steps": 97,
    "published_groups": 11_791,
    "candidate_groups": 2_911,
    "ratio": [11_791, 2_911],
    "d4_terms": 75_324,
    "d4_groups": 7_576,
    "d5_terms": 605_832,
    "d5_groups": 123_106,
    "certificate_sha256": "0a09623ce3b292a3637065c870fb3153bbdcddce30aef968565c4db3ddfc7201",
    "d4_sha256": "a397414bb0229fb1ebdb38798aa781fb89dbb9d5cdbed94c7cd2e9120da62718",
    "d5_sha256": "c5e8968a93b4497b41fe42c0e364324388272e183e1fcd20a536bc988f5361dd",
    "pr_head": "c550a6b0915ccf7a1db410ee765ff65d99f96b6f",
}

MANIFEST_PATHS = (
    Path("artifacts/issue128-summary.json"),
    Path("artifacts/issue128-summary.txt"),
    Path("artifacts/verification-transcript.txt"),
    CERTIFICATE,
    D4_SIDECAR,
    D5_SIDECAR,
    SMALL_CROSSCHECK,
    Path("docs/report/issue128-technical-report.tex"),
    Path("docs/report/references.bib"),
    Path("docs/report/output/issue128-technical-report.pdf"),
)


def require_equal(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise ValueError(f"{label} drift: {actual!r} != {expected!r}")


def canonical_json(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise TypeError(f"expected an object in {path}")
    return payload


def _gzip_object(path: Path) -> dict[str, object]:
    with gzip.open(path, "rt") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise TypeError(f"expected an object in {path}")
    return payload


def _decimal(pair: list[int], digits: int = 16) -> str:
    with localcontext() as context:
        context.prec = 80
        value = Decimal(pair[0]) / Decimal(pair[1])
        return format(value, f".{digits}g").lower()


def _outward_upper(pair: list[int], digits: int = 16) -> str:
    """Format a positive rational upward, never below the certified bound."""

    with localcontext() as context:
        context.prec = 100
        value = Decimal(pair[0]) / Decimal(pair[1])
        exponent = value.adjusted()
        quantum = Decimal(1).scaleb(exponent - digits + 1)
        rounded = value.quantize(quantum, rounding=ROUND_CEILING)
        return format(rounded, f".{digits - 1}e").lower()


def _git_provenance(root: Path) -> tuple[str, str]:
    repository = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    relative = (root / CERTIFICATE).resolve().relative_to(Path(repository).resolve())
    output = subprocess.run(
        ["git", "log", "-1", "--format=%H%n%cI", "--", relative.as_posix()],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().splitlines()
    if len(output) != 2:
        raise ValueError("could not determine certificate provenance")
    return output[0], output[1]


def build_summary(root: Path = ROOT) -> dict[str, object]:
    root = root.resolve()
    certificate = _object(root / CERTIFICATE)
    crosscheck = _object(root / SMALL_CROSSCHECK)
    d5 = _gzip_object(root / D5_SIDECAR)
    benchmark = certificate["benchmark"]
    published = certificate["published_baseline"]
    candidate = certificate["candidate"]
    resources = certificate["claimed_resources"]
    claims = certificate["claims"]
    if not all(isinstance(item, dict) for item in (benchmark, published, candidate, resources, claims)):
        raise TypeError("main certificate schema is malformed")

    checks = (
        ("published steps", resources["published_steps"], EXPECTED["published_steps"]),
        ("candidate steps", resources["candidate_steps"], EXPECTED["candidate_steps"]),
        ("published groups", resources["published_group_exponentials"], EXPECTED["published_groups"]),
        ("candidate groups", resources["candidate_group_exponentials"], EXPECTED["candidate_groups"]),
        ("exact ratio", claims["exact_improvement_ratio"], EXPECTED["ratio"]),
    )
    for label, actual, expected in checks:
        require_equal(label, actual, expected)

    d4 = candidate["d4_certificate"]
    if not isinstance(d4, dict):
        raise TypeError("D4 metadata is malformed")
    require_equal("D4 terms", d4["term_count"], EXPECTED["d4_terms"])
    require_equal("D4 groups", d4["group_count"], EXPECTED["d4_groups"])
    require_equal("D5 terms", d5["term_count"], EXPECTED["d5_terms"])
    require_equal("D5 groups", d5["group_count"], EXPECTED["d5_groups"])

    hashes = {
        "main_certificate": sha256_file(root / CERTIFICATE),
        "d4_sidecar": sha256_file(root / D4_SIDECAR),
        "d5_sidecar": sha256_file(root / D5_SIDECAR),
    }
    require_equal("main certificate digest", hashes["main_certificate"], EXPECTED["certificate_sha256"])
    require_equal("D4 sidecar digest", hashes["d4_sidecar"], EXPECTED["d4_sha256"])
    require_equal("D5 sidecar digest", hashes["d5_sidecar"], EXPECTED["d5_sha256"])

    tolerance = benchmark["tolerance"]
    error = candidate["global_error_upper"]
    previous_error = candidate["previous_step_error_upper"]
    accepted = error[0] * tolerance[1] <= tolerance[0] * error[1]
    rejected = previous_error[0] * tolerance[1] > tolerance[0] * previous_error[1]
    require_equal("97-step acceptance", accepted, True)
    require_equal("96-step rejection", rejected, True)

    source_commit, source_timestamp = _git_provenance(root)
    exact_ratio = claims["exact_improvement_ratio"]
    conditional_ratio = [resources["published_group_exponentials"], 30 * 78 + 1]
    removed = [
        resources["published_group_exponentials"] - resources["candidate_group_exponentials"],
        resources["published_group_exponentials"],
    ]
    contributions = candidate["contributions"]
    if not isinstance(contributions, dict):
        raise TypeError("error contribution ledger is malformed")

    return {
        "schema_version": 1,
        "sources": {
            "anchored_pr_head": EXPECTED["pr_head"],
            "source_commit_for_main_certificate": source_commit,
            "source_commit_timestamp": source_timestamp,
            "main_certificate": {"path": CERTIFICATE.as_posix(), "sha256": hashes["main_certificate"]},
            "d4_sidecar": {"path": D4_SIDECAR.as_posix(), "sha256": hashes["d4_sidecar"]},
            "d5_sidecar": {"path": D5_SIDECAR.as_posix(), "sha256": hashes["d5_sidecar"]},
        },
        "benchmark": {
            "model": benchmark["model"],
            "normalization": benchmark["normalization"],
            "length": benchmark["length"],
            "sites": benchmark["length"] ** 2,
            "time": benchmark["time"],
            "tolerance": tolerance,
            "formula": candidate["formula"],
            "formula_order": published["formula_order"],
            "stage_count": published["stage_count"],
        },
        "published_baseline": {
            "source_theorem": published["source_theorem"],
            "theorem_center": published["theorem_center"],
            "site_density_upper": published["site_density_upper"],
            "site_density_upper_decimal": _outward_upper(published["site_density_upper"]),
            "steps": resources["published_steps"],
            "group_exponentials": resources["published_group_exponentials"],
            "bond_propagators": resources["published_bond_propagators"],
            "cnot_upper": resources["published_cnot_upper"],
        },
        "certified_result": {
            "status": "certified",
            "steps": resources["candidate_steps"],
            "group_exponentials": resources["candidate_group_exponentials"],
            "bond_propagators": resources["candidate_bond_propagators"],
            "cnot_upper": resources["candidate_cnot_upper"],
            "error_upper": error,
            "error_upper_decimal_outward": _outward_upper(error),
            "previous_step": 96,
            "previous_step_error_upper": previous_error,
            "previous_step_error_upper_decimal_outward": _outward_upper(previous_error),
            "accepted_at_97": accepted,
            "rejected_at_96": rejected,
        },
        "improvement": {
            "exact_ratio": exact_ratio,
            "decimal": _decimal(exact_ratio),
            "resource_fraction_removed": removed,
            "resource_percent_removed": _decimal([100 * removed[0], removed[1]]) + "%",
            "multiple_of_required_twofold_target": _decimal([exact_ratio[0], 2 * exact_ratio[1]]),
        },
        "error_ledger": {
            name: {"exact": pair, "decimal_outward": _outward_upper(pair)}
            for name, pair in contributions.items()
        },
        "method": {
            "proof_method": candidate["proof_method"],
            "innovations": [
                "full free-associative-word logarithm before norm inequalities",
                "Dynkin-Specht-Wever projection to degree-5 and degree-7 Lie elements",
                "translation-canonical Pauli combination before taking norms",
                "exact pairwise-anticommuting grouping for the leading D4 defect",
                "exact single-bond Heisenberg commutator growth constant 1",
                "finite-step right-generator ledger with a rational geometric tail",
                "independent exact-rational and symplectic verification",
            ],
        },
        "verification": {
            "d4_term_count": d4["term_count"],
            "d4_group_count": d4["group_count"],
            "d4_max_group_size": d4["max_group_size"],
            "d4_cell_norm_upper": d4["cell_norm_upper"],
            "d4_cell_norm_upper_decimal": _outward_upper(d4["cell_norm_upper"]),
            "small_crosscheck": crosscheck,
        },
        "fivefold_followup": {
            "status": "not_certified",
            "conditional_step_count": 78,
            "conditional_group_exponentials": conditional_ratio[1],
            "conditional_exact_ratio": conditional_ratio,
            "conditional_ratio_decimal": _decimal(conditional_ratio),
            "d5_term_count": d5["term_count"],
            "d5_group_count": d5["group_count"],
            "d5_site_density_upper": d5["site_bound"],
            "d5_site_density_upper_decimal": _outward_upper(d5["site_bound"]),
            "unresolved_proof_gates": [
                "translation-coupled D4 norm below the r=78 budget",
                "explicit D8 and delayed high-degree tail certificate",
                "complete exact global error ledger at r=78",
            ],
            "claim_boundary": "No 78-step global error certificate is claimed or supplied.",
        },
    }


def render_summary_text(summary: Mapping[str, object]) -> str:
    b = summary["benchmark"]
    p = summary["published_baseline"]
    r = summary["certified_result"]
    i = summary["improvement"]
    v = summary["verification"]
    f = summary["fivefold_followup"]
    s = summary["sources"]
    return "\n".join((
        "ISSUE 128 FINAL RESULT SUMMARY",
        "================================",
        "",
        f"BENCHMARK: {b['model']}",
        f"LATTICE: L={b['length']}, N={b['sites']}",
        f"NORMALIZATION: {b['normalization']}",
        "TIME: T=1; OPERATOR-NORM TOLERANCE: 1e-6",
        "",
        f"PUBLISHED BASELINE: {p['steps']} steps, {p['group_exponentials']} groups, {p['bond_propagators']} bond propagators, {p['cnot_upper']} CNOT upper",
        f"CERTIFIED RESULT: {i['decimal']}x",
        f"  {r['steps']} steps, {r['group_exponentials']} groups, {r['bond_propagators']} bond propagators, {r['cnot_upper']} CNOT upper",
        f"  exact ratio: {i['exact_ratio'][0]}/{i['exact_ratio'][1]}",
        f"  resource reduction: {i['resource_percent_removed']}",
        f"  97-step error upper (outward decimal): {r['error_upper_decimal_outward']}",
        f"  96-step error upper (outward decimal): {r['previous_step_error_upper_decimal_outward']}",
        "  integer boundary: 97 accepted; 96 rejected",
        "",
        f"EXACT D4: {v['d4_term_count']} terms, {v['d4_group_count']} groups, maximum size {v['d4_max_group_size']}, cell bound {v['d4_cell_norm_upper_decimal']}",
        "",
        "FIVEFOLD STATUS: NOT CERTIFIED",
        f"  conditional arithmetic only: r={f['conditional_step_count']}, groups={f['conditional_group_exponentials']}, ratio={f['conditional_ratio_decimal']}x",
        f"  verified D5 evidence: {f['d5_term_count']} terms, {f['d5_group_count']} groups, site bound {f['d5_site_density_upper_decimal']}",
        f"  {f['claim_boundary']}",
        "",
        "SOURCE BINDINGS",
        f"  main certificate SHA-256: {s['main_certificate']['sha256']}",
        f"  D4 sidecar SHA-256: {s['d4_sidecar']['sha256']}",
        f"  D5 sidecar SHA-256: {s['d5_sidecar']['sha256']}",
        "",
    ))


def _run(root: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src"
    return subprocess.run([sys.executable, *arguments], cwd=root, env=environment, capture_output=True, text=True)


def capture_verification(root: Path = ROOT) -> str:
    root = root.resolve()
    commit, timestamp = _git_provenance(root)
    lines = [
        "ISSUE 128 VERIFICATION TRANSCRIPT",
        "=================================",
        f"source_commit_for_main_certificate: {commit}",
        f"source_commit_timestamp: {timestamp}",
        f"python: {platform.python_version()}",
        f"platform: {platform.platform()}",
        "",
    ]
    for arguments in (
        ["scripts/verify.py", CERTIFICATE.as_posix()],
        ["scripts/build_d5_certificate.py", "--verify-only"],
    ):
        completed = _run(root, arguments)
        display = "PYTHONPATH=src python " + " ".join(arguments)
        lines.extend((
            f"$ {display}",
            f"exit_code: {completed.returncode}",
            "--- stdout ---",
            completed.stdout.rstrip(),
            "--- stderr ---",
            completed.stderr.rstrip() or "(empty)",
            "",
        ))
        if completed.returncode:
            raise RuntimeError(f"verification command failed: {display}")
    lines.extend(("OVERALL STATUS: PASS", ""))
    return "\n".join(lines)


def write_delivery_files(root: Path = ROOT, output_dir: Path | None = None, *, capture: bool = True) -> set[Path]:
    root = root.resolve()
    destination = output_dir or root / "artifacts"
    destination.mkdir(parents=True, exist_ok=True)
    summary = build_summary(root)
    json_path = destination / "issue128-summary.json"
    text_path = destination / "issue128-summary.txt"
    json_path.write_text(canonical_json(summary))
    text_path.write_text(render_summary_text(summary))
    written = {json_path, text_path}
    if capture:
        transcript = destination / "verification-transcript.txt"
        transcript.write_text(capture_verification(root))
        written.add(transcript)
    return written


def write_sha_manifest(root: Path = ROOT) -> Path:
    root = root.resolve()
    missing = [path.as_posix() for path in MANIFEST_PATHS if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError("manifest inputs missing: " + ", ".join(missing))
    manifest = root / "artifacts/SHA256SUMS"
    manifest.write_text("\n".join(f"{sha256_file(root / path)}  {path.as_posix()}" for path in MANIFEST_PATHS) + "\n")
    return manifest


def verify_sha_manifest(root: Path = ROOT) -> None:
    root = root.resolve()
    for line in (root / "artifacts/SHA256SUMS").read_text().splitlines():
        digest, relative = line.split("  ", 1)
        require_equal(f"manifest digest for {relative}", sha256_file(root / relative), digest)


def check_delivery(root: Path = ROOT) -> None:
    root = root.resolve()
    summary = build_summary(root)
    require_equal("summary JSON", (root / "artifacts/issue128-summary.json").read_text(), canonical_json(summary))
    require_equal("summary text", (root / "artifacts/issue128-summary.txt").read_text(), render_summary_text(summary))
    if "OVERALL STATUS: PASS" not in capture_verification(root):
        raise ValueError("current verifier run did not pass")
    if "OVERALL STATUS: PASS" not in (root / "artifacts/verification-transcript.txt").read_text():
        raise ValueError("committed verifier transcript did not pass")
    verify_sha_manifest(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--manifest", action="store_true")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    if arguments.check:
        check_delivery(ROOT)
        print("delivery_check=PASS")
        return
    written = write_delivery_files(ROOT, arguments.output_dir)
    if arguments.manifest:
        written.add(write_sha_manifest(ROOT))
    for path in sorted(written):
        print(f"wrote={path}")


if __name__ == "__main__":
    main()
