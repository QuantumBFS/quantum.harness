"""Replay a saved generator or direct-factor example at high precision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mpmath as mp


def _decode_matrix(payload: object) -> mp.matrix:
    if isinstance(payload, dict):
        real = payload["real"]
        imag = payload["imag"]
        return mp.matrix(
            [
                [
                    mp.mpc(str(real[row][column]), str(imag[row][column]))
                    for column in range(len(real[row]))
                ]
                for row in range(len(real))
            ]
        )
    return mp.matrix([[mp.mpf(str(value)) for value in row] for row in payload])


def replay_weight(example: dict[str, object], *, dps: int = 80) -> mp.mpf | mp.mpc:
    """Re-evaluate a recorded determinant weight."""

    if dps < 30:
        raise ValueError("dps must be at least 30")
    with mp.workdps(dps):
        if "generators" in example:
            matrices = [
                _decode_matrix(payload) for payload in example["generators"]
            ]
            exponentiate = True
        elif "factors" in example:
            matrices = [
                _decode_matrix(payload) for payload in example["factors"]
            ]
            exponentiate = False
        else:
            raise ValueError("example must contain generators or factors")

        size = matrices[0].rows
        product = mp.eye(size)
        for matrix in matrices:
            if matrix.rows != size or matrix.cols != size:
                raise ValueError("all matrices must have the same square shape")
            product = product * (mp.expm(matrix) if exponentiate else matrix)
        return mp.det(mp.eye(size) + product)


def replay_manifest(
    path: str | Path,
    *,
    classification: str = "negative",
    dps: int = 80,
) -> dict[str, object]:
    """Replay one saved counterexample and return a JSON-serializable summary."""

    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        example = manifest["examples"][classification]
    except KeyError as error:
        raise ValueError(
            f"manifest has no saved {classification!r} example"
        ) from error

    weight = replay_weight(example, dps=dps)
    with mp.workdps(dps):
        real = mp.re(weight)
        imag = mp.im(weight)
        if abs(imag) <= mp.mpf(10) ** (-(dps // 2)):
            sign = "positive" if real > 0 else "negative" if real < 0 else "zero"
        else:
            sign = "complex"
        return {
            "manifest": str(manifest_path),
            "classification": classification,
            "dps": dps,
            "replayed_sign": sign,
            "weight_real": mp.nstr(real, n=dps),
            "weight_imag": mp.nstr(imag, n=dps),
            "float64_log_abs_weight": example["log_abs_weight"],
            "float64_sigma_min_I_plus_D": example["sigma_min_I_plus_D"],
            "float64_condition_number_I_plus_D": example[
                "condition_number_I_plus_D"
            ],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="path to a scan-cell manifest")
    parser.add_argument(
        "--classification",
        default="negative",
        choices=("negative", "complex", "uncertain"),
    )
    parser.add_argument("--dps", type=int, default=80)
    args = parser.parse_args()
    print(
        json.dumps(
            replay_manifest(
                args.manifest,
                classification=args.classification,
                dps=args.dps,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
