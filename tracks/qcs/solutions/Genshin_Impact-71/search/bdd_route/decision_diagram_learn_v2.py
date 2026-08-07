#!/usr/bin/env python3
"""Reviewed entry point for decision_diagram_learn with constant materialization.

Kept separate so the original experiment snapshot remains immutable.
"""

from decision_diagram_learn import *  # noqa: F401,F403
from decision_diagram_learn import GateBuilder, Signal, main


def _materialize_constant(self: GateBuilder, value: int) -> Signal:
    zero = getattr(self, "_constant_zero_signal", None)
    if zero is None:
        wire = self._new_wire()
        self.lines.append((wire, "XOR", "x1", "x1"))
        zero = Signal(wire)
        self._constant_zero_signal = zero
    return zero if value == 0 else zero.negate()


GateBuilder.materialize_constant = _materialize_constant


if __name__ == "__main__":
    raise SystemExit(main())
