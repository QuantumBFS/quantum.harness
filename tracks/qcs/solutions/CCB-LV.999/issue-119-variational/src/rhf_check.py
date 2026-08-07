from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path


def rhf_energy(path: str | Path, *, verbose: int = 0) -> float:
    from pyscf import gto, scf
    from pyscf.tools import fcidump

    input_path = str(path)
    integrals = fcidump.read(input_path)
    molecule = gto.M()
    molecule.nelectron = int(integrals["NELEC"])
    molecule.spin = int(integrals["MS2"])
    molecule.verbose = verbose
    molecule.atom = []
    molecule.build()
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Function mol\.dumps drops attribute .*",
            category=UserWarning,
        )
        mean_field = scf.RHF(molecule)
        mean_field.__dict__.update(fcidump.to_scf(input_path, molecule).__dict__)
        mean_field.verbose = verbose
        energy = mean_field.kernel()
    if not mean_field.converged:
        raise RuntimeError("RHF did not converge")
    return float(energy)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an RHF FCIDUMP sign check")
    parser.add_argument("--fcidump", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    energy = rhf_energy(args.fcidump, verbose=4)
    result = {
        "schema_version": 1,
        "method": "pyscf-rhf",
        "fcidump": str(args.fcidump.resolve()),
        "energy_hartree": energy,
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
