from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BasicObservables:
    open_edges: int
    component_count: int
    largest_size: int
    second_largest_size: int
    s1_fraction: float
    s2_fraction: float
    sum_size_sq: float
    sum_size_fourth: float
    q_g: float
    four_sector_crossing: bool
