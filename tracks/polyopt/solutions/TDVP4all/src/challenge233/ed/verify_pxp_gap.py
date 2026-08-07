import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


class VerificationError(RuntimeError):
    pass


def _lucas_number(size: int) -> int:
    previous, current = 2, 1
    for _ in range(size):
        previous, current = current, previous + current
    return previous


def verify_run(
    output_directory,
    residual_tolerance: float = 1e-9,
    hermiticity_tolerance: float = 1e-14,
):
    output_directory = Path(output_directory)
    manifest = json.loads(
        (output_directory / "manifest.json").read_text(encoding="utf-8")
    )
    data_path = output_directory / manifest["data_file"]
    actual_data_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
    if actual_data_hash != manifest["data_sha256"]:
        raise VerificationError("data SHA-256 does not match manifest")

    project_root = Path(__file__).resolve().parents[3]
    for relative_path, expected_hash in manifest["source_file_sha256"].items():
        actual_hash = hashlib.sha256(
            (project_root / relative_path).read_bytes()
        ).hexdigest()
        if actual_hash != expected_hash:
            raise VerificationError(
                f"source SHA-256 does not match manifest: {relative_path}"
            )

    for raw_size in manifest["sizes"]:
        size = int(raw_size)
        metadata = manifest["basis_state_files"].get(str(size))
        if metadata is None:
            raise VerificationError(f"missing basis-state metadata for N={size}")
        if int(metadata["count"]) != _lucas_number(size):
            raise VerificationError(
                f"basis-state count is not the periodic Lucas count at N={size}"
            )
        states_path = output_directory / metadata["path"]
        actual_states_hash = hashlib.sha256(states_path.read_bytes()).hexdigest()
        if actual_states_hash != metadata["sha256"]:
            raise VerificationError(
                f"basis-state SHA-256 does not match manifest at N={size}"
            )

    with data_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    if len(rows) != manifest["point_count"]:
        raise VerificationError("point count does not match manifest")
    expected_grid = [
        (int(size), float(detuning))
        for size in manifest["sizes"]
        for detuning in manifest["detunings"]
    ]
    actual_grid = [
        (int(row["size"]), float(row["detuning"])) for row in rows
    ]
    if actual_grid != expected_grid:
        raise VerificationError("CSV does not contain the manifest grid")
    for row in rows:
        size = int(row["size"])
        if int(row["basis_dimension"]) != _lucas_number(size):
            raise VerificationError(
                f"basis dimension is not the periodic Lucas count at N={size}"
            )
        residual_columns = sorted(
            (
                column
                for column in row
                if column.startswith("residual_")
                and column.removeprefix("residual_").isdigit()
            ),
            key=lambda column: int(column.removeprefix("residual_")),
        )
        computed_max_residual = max(
            float(row[column]) for column in residual_columns
        )
        reported_max_residual = float(row["max_residual"])
        if not math.isclose(
            reported_max_residual,
            computed_max_residual,
            rel_tol=1e-12,
            abs_tol=1e-15,
        ):
            raise VerificationError(
                f"reported maximum residual is inconsistent at N={size}, "
                f"delta={row['detuning']}"
            )
        if computed_max_residual > residual_tolerance:
            raise VerificationError(
                f"eigenpair residual exceeds tolerance at N={size}, "
                f"delta={row['detuning']}"
            )
        if float(row["hermiticity_max_abs"]) > hermiticity_tolerance:
            raise VerificationError(
                f"Hermiticity error exceeds tolerance at N={size}, "
                f"delta={row['detuning']}"
            )
        energy_columns = sorted(
            (
                column
                for column in row
                if column.startswith("e") and column[1:].isdigit()
            ),
            key=lambda column: int(column[1:]),
        )
        energies = [float(row[column]) for column in energy_columns]
        if not all(math.isfinite(energy) for energy in energies):
            raise VerificationError(
                f"non-finite eigenvalue at N={size}, delta={row['detuning']}"
            )
        if any(
            left > right for left, right in zip(energies, energies[1:])
        ):
            raise VerificationError(
                f"eigenvalue order is invalid at N={size}, "
                f"delta={row['detuning']}"
            )
        gap = float(row["gap"])
        expected_gap = float(row["e1"]) - float(row["e0"])
        if not math.isclose(gap, expected_gap, rel_tol=1e-12, abs_tol=1e-12):
            raise VerificationError(
                f"gap does not equal E_1-E_0 at N={row['size']}, "
                f"delta={row['detuning']}"
            )

    return {
        "point_count": len(rows),
        "minimum_gap": min(float(row["gap"]) for row in rows),
        "maximum_residual": max(float(row["max_residual"]) for row in rows),
        "maximum_hermiticity_error": max(
            float(row["hermiticity_max_abs"]) for row in rows
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Independently verify a PXP ED run artifact"
    )
    parser.add_argument("run_directory")
    parser.add_argument("--residual-tolerance", type=float, default=1e-9)
    parser.add_argument("--hermiticity-tolerance", type=float, default=1e-14)
    arguments = parser.parse_args(argv)
    summary = verify_run(
        arguments.run_directory,
        residual_tolerance=arguments.residual_tolerance,
        hermiticity_tolerance=arguments.hermiticity_tolerance,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
