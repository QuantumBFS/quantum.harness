from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .dmrg_runner import load_config
from .fcidump_audit import audit_fcidump
from .orderings import validate_ordering
from .result_schema import validate_result_document


def _write_json(path: Path, document: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def adopt_checkpoint_energy(
    result: dict[str, Any],
    checkpoint_energy: float,
) -> dict[str, Any]:
    """Replace the headline with a saved-MPS expectation, preserving sweep output."""

    updated = copy.deepcopy(result)
    final_stage = updated["stages"][-1]
    final_stage.setdefault(
        "sweep_energy_hartree",
        final_stage["energy_hartree"],
    )
    final_stage["energy_hartree"] = float(checkpoint_energy)
    updated["headline"]["energy_hartree"] = float(checkpoint_energy)
    updated["headline"]["kind"] = "finite_m_mps_expectation"
    return validate_result_document(updated)


def verify_checkpoint(
    run_dir: str | Path,
    *,
    tolerance: float = 1.0e-9,
    update_headline: bool = False,
) -> dict[str, Any]:
    """Reload a saved MPS in a fresh driver and recompute its energy."""

    run_path = Path(run_dir)
    config = load_config(run_path / "config.toml")
    input_path = run_path / "inputs" / config.instance.filename
    audit = audit_fcidump(
        input_path,
        expected_norb=config.instance.norb,
        expected_nelec=config.instance.nelec,
        expected_ms2=config.instance.ms2,
        expected_sha256=config.instance.sha256,
    )
    result = json.loads((run_path / "result.json").read_text(encoding="utf-8"))
    ordering_document = json.loads(
        (run_path / "ordering.json").read_text(encoding="utf-8")
    )
    ordering = validate_ordering(
        ordering_document["permutation"],
        config.instance.norb,
    )

    os.environ["OMP_NUM_THREADS"] = str(config.dmrg.threads)
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"

    import numpy as np
    from pyblock2.driver.core import DMRGDriver, SymmetryTypes

    symmetry_type = (
        SymmetryTypes.SU2 if config.dmrg.symmetry == "SU2" else SymmetryTypes.SZ
    )
    scratch = run_path / "checkpoints" / "block2"
    driver = DMRGDriver(
        scratch=str(scratch),
        symm_type=symmetry_type,
        n_threads=config.dmrg.threads,
        stack_mem=int(config.dmrg.stack_mem_gb * 1.0e9),
    )
    driver.read_fcidump(filename=str(input_path), pg="c1", iprint=0)
    h1e = np.asarray(driver.h1e)
    g2e = driver.unpack_g2e(driver.g2e, n_sites=driver.n_sites)
    orbital_symmetries = (
        list(driver.orb_sym) if driver.orb_sym is not None else None
    )
    index = np.asarray(ordering, dtype=int)
    h1e = h1e[np.ix_(index, index)]
    g2e = g2e[np.ix_(index, index, index, index)]
    if orbital_symmetries is not None:
        orbital_symmetries = [orbital_symmetries[value] for value in ordering]
    driver.initialize_system(
        n_sites=config.instance.norb,
        n_elec=config.instance.nelec,
        spin=config.dmrg.spin,
        orb_sym=orbital_symmetries,
    )
    mpo = driver.get_qc_mpo(
        h1e=h1e,
        g2e=g2e,
        ecore=driver.ecore,
        unpack_g2e=False,
        iprint=0,
    )
    ket = driver.load_mps(tag="KET", nroots=1)
    raw_energy = float(driver.expectation(ket, mpo, ket, iprint=0))
    norm = float(
        driver.expectation(ket, driver.get_identity_mpo(), ket, iprint=0)
    )
    normalized_energy = raw_energy / norm
    headline_energy = float(result["headline"]["energy_hartree"])
    difference_before_update = normalized_energy - headline_energy
    headline_updated = False
    if abs(difference_before_update) > tolerance and update_headline:
        result = adopt_checkpoint_energy(result, normalized_energy)
        _write_json(run_path / "result.json", result)
        run_json_path = run_path / "run.json"
        if run_json_path.exists():
            run_document = json.loads(run_json_path.read_text(encoding="utf-8"))
            final_stage = run_document["stages"][-1]
            final_stage.setdefault(
                "sweep_energy_hartree",
                final_stage["energy_hartree"],
            )
            final_stage["energy_hartree"] = normalized_energy
            run_document["headline"] = result["headline"]
            run_document["checkpoint_headline_adopted_at_utc"] = (
                datetime.now(UTC).isoformat()
            )
            _write_json(run_json_path, run_document)
        headline_energy = normalized_energy
        headline_updated = True
    difference = normalized_energy - headline_energy
    verification = {
        "schema_version": 1,
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "input_sha256": audit.sha256,
        "checkpoint": str((scratch / "KET-mps_info.bin").resolve()),
        "ordering": ordering_document["method"],
        "raw_energy_hartree": raw_energy,
        "norm": norm,
        "normalized_energy_hartree": normalized_energy,
        "recorded_headline_before_update_hartree": (
            headline_energy - difference_before_update
            if headline_updated
            else headline_energy
        ),
        "headline_energy_hartree": headline_energy,
        "difference_before_update_hartree": difference_before_update,
        "difference_hartree": difference,
        "tolerance_hartree": tolerance,
        "headline_updated": headline_updated,
        "verified": abs(difference) <= tolerance and abs(norm - 1.0) <= tolerance,
    }
    _write_json(run_path / "checkpoint-verification.json", verification)
    if not verification["verified"]:
        raise RuntimeError(
            "checkpoint expectation differs from the recorded finite-M headline: "
            f"ΔE={difference:+.3e}, norm={norm:.16g}"
        )
    return verification


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reload a block2 MPS and independently recompute its energy"
    )
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--tolerance", type=float, default=1.0e-9)
    parser.add_argument(
        "--update-headline",
        action="store_true",
        help="replace a sweep-derived headline with the verified saved-MPS expectation",
    )
    args = parser.parse_args()
    verification = verify_checkpoint(
        args.run_dir,
        tolerance=args.tolerance,
        update_headline=args.update_headline,
    )
    print(json.dumps(verification, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
