from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import sys
import time

import jax
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qcontrol.closed_loop import make_search_space
from qcontrol.config import DeviceConfig, SearchConfig, SystemConfig
from qcontrol.device import make_query_device
from qcontrol.landscape import analyze_landscape
from qcontrol.offline import (
    compute_geometry_diagnostics,
    cumulative_best_exact_infidelity,
    make_offline_evaluator,
    optimize_restricted_noiseless_upper_bound,
)
from qcontrol.open_loop import optimize_open_loop
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system, perturb_system


def timed(callable_):
    started = time.perf_counter()
    result = callable_()
    return result, time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=int, default=32)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not 20 <= args.queries <= 100:
        parser.error("--queries must be between 20 and 100")

    system_config = SystemConfig("two_qubit", 20, 4.0)
    model = make_system(system_config)
    pulse_space = PulseSpace.from_system(model, system_config.segments)
    open_loop, open_loop_seconds = timed(
        lambda: optimize_open_loop(model, pulse_space, seed=5)
    )
    landscape, landscape_seconds = timed(
        lambda: analyze_landscape(
            model,
            pulse_space,
            open_loop,
            leading_count=15,
            dense_validation=True,
        )
    )
    origin = np.asarray(
        landscape.polishing.normalized_pulse
        if landscape.polishing is not None
        else open_loop.normalized_pulse,
        dtype=np.float64,
    )
    truth = perturb_system(model, 0.05, 5)
    search_space = make_search_space(
        SearchConfig("model_hessian", 4, 2_000),
        origin,
        model_basis=landscape.model_basis,
        seed=5,
    )
    rng = np.random.default_rng(5)
    pulses = [
        search_space.to_pulse(rng.uniform(-0.2, 0.2, search_space.dimension))
        for _ in range(args.queries)
    ]
    device = make_query_device(
        truth,
        pulse_space,
        DeviceConfig(gap=0.05, shots=None, perturbation_seed=5),
        seed=5,
    )
    first, compilation_seconds = timed(lambda: device.query(pulses[0]))
    observations, warm_seconds = timed(
        lambda: [device.query(pulse) for pulse in pulses[1:]]
    )
    audited = list(zip(pulses, [first, *observations], strict=True))
    _, exact_seconds = timed(
        lambda: cumulative_best_exact_infidelity(
            make_offline_evaluator(truth, pulse_space),
            initial_pulse=origin,
            audited_queries=audited,
        )
    )
    _, geometry_seconds = timed(
        lambda: compute_geometry_diagnostics(model, truth, pulse_space, origin)
    )
    restricted, restricted_seconds = timed(
        lambda: optimize_restricted_noiseless_upper_bound(
            truth,
            pulse_space,
            search_space,
        )
    )
    warm_queries = args.queries - 1
    payload = {
        "cpu_count": os.cpu_count(),
        "exact_trajectory_seconds": exact_seconds,
        "first_query_compilation_inclusive_seconds": compilation_seconds,
        "geometry_seconds": geometry_seconds,
        "jax_platform": jax.devices()[0].platform,
        "landscape_seconds": landscape_seconds,
        "open_loop_seconds": open_loop_seconds,
        "parameter_count": pulse_space.parameter_count,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "queries": args.queries,
        "restricted_nfev": restricted.nfev,
        "restricted_optimization_seconds": restricted_seconds,
        "schema_version": 1,
        "search_dimension": search_space.dimension,
        "warm_queries_per_second": warm_queries / warm_seconds,
        "warm_query_seconds": warm_seconds,
        "x64_enabled": bool(jax.config.x64_enabled),
    }
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(payload, allow_nan=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
