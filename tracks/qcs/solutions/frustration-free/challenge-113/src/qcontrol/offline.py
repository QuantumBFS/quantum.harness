from __future__ import annotations

from collections.abc import Callable
import math

import numpy as np

from qcontrol.objectives import normalized_infidelity
from qcontrol.pulses import PulseSpace
from qcontrol.systems import ControlSystem


def make_offline_evaluator(
    truth: ControlSystem,
    space: PulseSpace,
) -> Callable[[object], float]:
    """Build an exact evaluator for analysis code outside the device API."""
    if not isinstance(truth, ControlSystem):
        raise ValueError("truth must be a ControlSystem")
    if not isinstance(space, PulseSpace):
        raise ValueError("space must be a PulseSpace")
    if len(truth.controls) != space.control_count:
        raise ValueError("pulse space control count does not match the truth system")
    if tuple(truth.amplitude_scales) != tuple(space.amplitude_scales):
        raise ValueError("pulse space amplitude scales do not match the truth system")

    def evaluate(normalized_pulse: object) -> float:
        loss = float(normalized_infidelity(normalized_pulse, truth, space))
        fidelity = float(np.clip(1.0 - loss, 0.0, 1.0))
        if not math.isfinite(fidelity):
            raise ValueError("truth evaluation did not produce a finite fidelity")
        return fidelity

    return evaluate
