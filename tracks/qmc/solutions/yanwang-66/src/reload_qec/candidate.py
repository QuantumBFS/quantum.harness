"""Public candidate CLI for one immutable simulation request."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .artifacts import RunWriter
from .config import RequestError, SimulationRequest
from .geometry import Geometry, GeometryError
from .simulate import Simulator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--precheck", action="store_true")
    return parser.parse_args()


def run(request: SimulationRequest, out_dir: Path, *, precheck: bool) -> dict:
    geometry = Geometry.load(
        request.instance_file,
        distance=request.distance,
        rounds=request.rounds,
        basis=request.basis,
    )
    if precheck:
        return {
            "status": "precheck-passed",
            "run_id": request.run_id,
            "instance_id": geometry.instance_id,
        }
    writer = RunWriter(out_dir=out_dir, request=request, geometry=geometry)
    writer.initialize()
    simulator = Simulator(request, geometry)
    stop = request.shot_start + request.shots
    for shard_index, shard_start in enumerate(
        range(request.shot_start, stop, request.shard_size)
    ):
        shard_stop = min(stop, shard_start + request.shard_size)
        shot_ids = np.arange(shard_start, shard_stop, dtype=np.uint64)
        writer.write_batch(shard_index, simulator.simulate(shot_ids))
    return writer.finalize()


def main() -> None:
    args = parse_args()
    try:
        request = SimulationRequest.load(args.request)
        result = run(request, args.out, precheck=args.precheck)
    except (RequestError, GeometryError, FileExistsError, ValueError) as exc:
        print(
            json.dumps(
                {"status": "rejected", "error": type(exc).__name__, "detail": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    print(json.dumps(result, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
