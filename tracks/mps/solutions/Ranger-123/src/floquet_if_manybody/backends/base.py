"""Common, provenance-rich open-system result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class OpenSystemResult:
    method: str
    density_matrices: NDArray[np.complex128]
    times: NDArray[np.float64]
    converged: bool
    diagnostics: dict[str, float]
    metadata: dict[str, Any]
    step_maps: NDArray[np.complex128] | None = None
