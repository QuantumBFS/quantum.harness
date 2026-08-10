"""Small serializable decimal interval type."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class DecimalInterval(BaseModel):
    """Closed finite interval with decimal endpoints."""

    model_config = ConfigDict(frozen=True)

    lower: Decimal
    upper: Decimal

    @field_validator("lower", "upper")
    @classmethod
    def finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("interval endpoints must be finite")
        return value

    def model_post_init(self, _context: object) -> None:
        if self.lower > self.upper:
            raise ValueError("lower endpoint exceeds upper endpoint")

    def as_strings(self) -> tuple[str, str]:
        return (str(self.lower), str(self.upper))

    @property
    def width(self) -> Decimal:
        return self.upper - self.lower

    def contains(self, value: Decimal) -> bool:
        return self.lower <= value <= self.upper
