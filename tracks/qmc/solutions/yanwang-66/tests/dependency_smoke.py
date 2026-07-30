"""SCNet-only smoke test for the pinned Stim/PyMatching reference path."""

from __future__ import annotations

import json

import numpy as np
import pymatching
import stim


def main() -> None:
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_x",
        distance=3,
        rounds=3,
        after_clifford_depolarization=1e-3,
        before_measure_flip_probability=1e-3,
        after_reset_flip_probability=1e-3,
    )
    detector_model = circuit.detector_error_model(decompose_errors=True)
    matching = pymatching.Matching.from_detector_error_model(detector_model)
    sampler = circuit.compile_detector_sampler(seed=13)
    detectors, observables = sampler.sample(
        shots=1_000,
        separate_observables=True,
    )
    predictions = matching.decode_batch(detectors)

    if predictions.shape != observables.shape:
        raise AssertionError(
            f"prediction shape {predictions.shape} != observable shape {observables.shape}"
        )
    failures = np.any(predictions != observables, axis=1)
    payload = {
        "stim_version": stim.__version__,
        "pymatching_version": pymatching.__version__,
        "shots": int(detectors.shape[0]),
        "detectors": int(detectors.shape[1]),
        "observables": int(observables.shape[1]),
        "logical_failures": int(np.count_nonzero(failures)),
        "dem_errors": detector_model.num_errors,
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
