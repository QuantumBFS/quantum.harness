from dataclasses import dataclass
from math import comb, sqrt


@dataclass(frozen=True, slots=True)
class SphereSpec:
    particles: int

    def __post_init__(self) -> None:
        if isinstance(self.particles, bool) or self.particles < 2:
            raise ValueError("particles must be at least 2")

    @property
    def two_q(self) -> int:
        return 3 * (self.particles - 1)

    @property
    def q(self) -> float:
        return self.two_q / 2

    @property
    def orbital_count(self) -> int:
        return self.two_q + 1

    @property
    def two_m_values(self) -> tuple[int, ...]:
        return tuple(range(-self.two_q, self.two_q + 1, 2))

    @property
    def radius_in_magnetic_lengths(self) -> float:
        return sqrt(self.q)

    @property
    def l_max(self) -> int:
        return self.particles * self.two_q // 2

    @property
    def full_dimension(self) -> int:
        return comb(self.orbital_count, self.particles)
