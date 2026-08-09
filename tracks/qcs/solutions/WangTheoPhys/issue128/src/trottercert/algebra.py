from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import reduce
from typing import Iterable, Mapping

import numpy as np


def _fraction(value: int | Fraction) -> Fraction:
    return value if isinstance(value, Fraction) else Fraction(value)


@dataclass(frozen=True, slots=True)
class QComplex:
    """A complex number with exact rational real and imaginary parts."""

    real: Fraction = Fraction(0)
    imag: Fraction = Fraction(0)

    def __init__(
        self, real: int | Fraction = 0, imag: int | Fraction = 0
    ) -> None:
        object.__setattr__(self, "real", _fraction(real))
        object.__setattr__(self, "imag", _fraction(imag))

    @classmethod
    def coerce(cls, value: QComplex | int | Fraction) -> QComplex:
        return value if isinstance(value, cls) else cls(value)

    def __add__(self, other: QComplex | int | Fraction) -> QComplex:
        rhs = self.coerce(other)
        return QComplex(self.real + rhs.real, self.imag + rhs.imag)

    __radd__ = __add__

    def __neg__(self) -> QComplex:
        return QComplex(-self.real, -self.imag)

    def __sub__(self, other: QComplex | int | Fraction) -> QComplex:
        return self + (-self.coerce(other))

    def __rsub__(self, other: QComplex | int | Fraction) -> QComplex:
        return self.coerce(other) - self

    def __mul__(self, other: QComplex | int | Fraction) -> QComplex:
        rhs = self.coerce(other)
        return QComplex(
            self.real * rhs.real - self.imag * rhs.imag,
            self.real * rhs.imag + self.imag * rhs.real,
        )

    __rmul__ = __mul__

    def __truediv__(self, other: int | Fraction) -> QComplex:
        divisor = _fraction(other)
        return QComplex(self.real / divisor, self.imag / divisor)

    def conjugate(self) -> QComplex:
        return QComplex(self.real, -self.imag)

    def abs_float(self) -> float:
        return float(self.real * self.real + self.imag * self.imag) ** 0.5

    def to_complex(self) -> complex:
        return complex(float(self.real), float(self.imag))

    def is_zero(self) -> bool:
        return self.real == 0 and self.imag == 0


_MUL: dict[tuple[str, str], tuple[QComplex, str]] = {
    ("I", "I"): (QComplex(1), "I"),
    ("I", "X"): (QComplex(1), "X"),
    ("I", "Y"): (QComplex(1), "Y"),
    ("I", "Z"): (QComplex(1), "Z"),
    ("X", "I"): (QComplex(1), "X"),
    ("Y", "I"): (QComplex(1), "Y"),
    ("Z", "I"): (QComplex(1), "Z"),
    ("X", "X"): (QComplex(1), "I"),
    ("Y", "Y"): (QComplex(1), "I"),
    ("Z", "Z"): (QComplex(1), "I"),
    ("X", "Y"): (QComplex(0, 1), "Z"),
    ("Y", "Z"): (QComplex(0, 1), "X"),
    ("Z", "X"): (QComplex(0, 1), "Y"),
    ("Y", "X"): (QComplex(0, -1), "Z"),
    ("Z", "Y"): (QComplex(0, -1), "X"),
    ("X", "Z"): (QComplex(0, -1), "Y"),
}


@dataclass(frozen=True, order=True, slots=True)
class PauliString:
    """A phase-free tensor-product Pauli string."""

    ops: tuple[tuple[int, str], ...] = ()

    def __init__(self, ops: Mapping[int, str] | Iterable[tuple[int, str]] = ()) -> None:
        items = ops.items() if isinstance(ops, Mapping) else ops
        canonical: dict[int, str] = {}
        for site, op in items:
            if site < 0:
                raise ValueError("site indices must be nonnegative")
            if op not in {"I", "X", "Y", "Z"}:
                raise ValueError(f"invalid Pauli operator {op!r}")
            if op != "I":
                canonical[int(site)] = op
        object.__setattr__(self, "ops", tuple(sorted(canonical.items())))

    def as_dict(self) -> dict[int, str]:
        return dict(self.ops)

    @property
    def support(self) -> frozenset[int]:
        return frozenset(site for site, _ in self.ops)

    def multiply(self, other: PauliString) -> tuple[QComplex, PauliString]:
        left_index = right_index = 0
        phase_exponent = 0
        result: list[tuple[int, str]] = []
        while left_index < len(self.ops) or right_index < len(other.ops):
            if right_index >= len(other.ops) or (
                left_index < len(self.ops)
                and self.ops[left_index][0] < other.ops[right_index][0]
            ):
                result.append(self.ops[left_index])
                left_index += 1
                continue
            if left_index >= len(self.ops) or (
                other.ops[right_index][0] < self.ops[left_index][0]
            ):
                result.append(other.ops[right_index])
                right_index += 1
                continue
            site = self.ops[left_index][0]
            left_op = self.ops[left_index][1]
            right_op = other.ops[right_index][1]
            local_phase, op = _MUL[(left_op, right_op)]
            if local_phase.imag == 1:
                phase_exponent += 1
            elif local_phase.imag == -1:
                phase_exponent += 3
            elif local_phase.real == -1:
                phase_exponent += 2
            if op != "I":
                result.append((site, op))
            left_index += 1
            right_index += 1
        phases = (QComplex(1), QComplex(0, 1), QComplex(-1), QComplex(0, -1))
        return phases[phase_exponent % 4], PauliString(result)


class PauliSum:
    """A finite exact Gaussian-rational linear combination of Pauli strings."""

    def __init__(
        self,
        terms: Mapping[PauliString, QComplex | int | Fraction] | None = None,
    ) -> None:
        self.terms: dict[PauliString, QComplex] = {}
        for pauli, coefficient in (terms or {}).items():
            self._accumulate(pauli, QComplex.coerce(coefficient))

    @classmethod
    def term(
        cls,
        pauli: PauliString,
        coefficient: QComplex | int | Fraction = 1,
    ) -> PauliSum:
        return cls({pauli: coefficient})

    @classmethod
    def identity(cls, coefficient: QComplex | int | Fraction = 1) -> PauliSum:
        return cls.term(PauliString(), coefficient)

    @classmethod
    def zero(cls) -> PauliSum:
        return cls()

    def copy(self) -> PauliSum:
        return PauliSum(self.terms)

    def _accumulate(self, pauli: PauliString, coefficient: QComplex) -> None:
        updated = self.terms.get(pauli, QComplex()) + coefficient
        if updated.is_zero():
            self.terms.pop(pauli, None)
        else:
            self.terms[pauli] = updated

    def __add__(self, other: PauliSum) -> PauliSum:
        result = self.copy()
        for pauli, coefficient in other.terms.items():
            result._accumulate(pauli, coefficient)
        return result

    def __sub__(self, other: PauliSum) -> PauliSum:
        return self + (-other)

    def __neg__(self) -> PauliSum:
        return self.scale(-1)

    def scale(self, coefficient: QComplex | int | Fraction) -> PauliSum:
        scalar = QComplex.coerce(coefficient)
        return PauliSum({p: scalar * c for p, c in self.terms.items()})

    def __mul__(self, other: PauliSum | QComplex | int | Fraction) -> PauliSum:
        if not isinstance(other, PauliSum):
            return self.scale(other)
        result = PauliSum.zero()
        for left, left_coefficient in self.terms.items():
            for right, right_coefficient in other.terms.items():
                phase, pauli = left.multiply(right)
                result._accumulate(pauli, left_coefficient * right_coefficient * phase)
        return result

    def __rmul__(self, other: QComplex | int | Fraction) -> PauliSum:
        return self.scale(other)

    def dagger(self) -> PauliSum:
        return PauliSum({p: c.conjugate() for p, c in self.terms.items()})

    def is_hermitian(self) -> bool:
        return self.terms == self.dagger().terms

    def pauli_l1(self) -> float:
        return sum(coefficient.abs_float() for coefficient in self.terms.values())

    def exact_real_l1(self) -> Fraction:
        total = Fraction()
        for coefficient in self.terms.values():
            if coefficient.imag != 0:
                raise ValueError("exact_real_l1 requires real coefficients")
            total += abs(coefficient.real)
        return total

    def exact_axis_l1(self) -> Fraction:
        """Exact l1 norm when every coefficient is purely real or imaginary."""

        total = Fraction()
        for coefficient in self.terms.values():
            if coefficient.real and coefficient.imag:
                raise ValueError("coefficient modulus is irrational in general")
            total += abs(coefficient.real) + abs(coefficient.imag)
        return total

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PauliSum) and self.terms == other.terms

    def __bool__(self) -> bool:
        return bool(self.terms)


def commutator(left: PauliSum, right: PauliSum) -> PauliSum:
    result = PauliSum.zero()
    for left_pauli, left_coefficient in left.terms.items():
        for right_pauli, right_coefficient in right.terms.items():
            if pauli_strings_commute(left_pauli, right_pauli):
                continue
            phase, product = left_pauli.multiply(right_pauli)
            result._accumulate(
                product,
                QComplex(2) * left_coefficient * right_coefficient * phase,
            )
    return result


def pauli_strings_commute(left: PauliString, right: PauliString) -> bool:
    left_index = right_index = 0
    parity = 0
    while left_index < len(left.ops) and right_index < len(right.ops):
        left_site, left_op = left.ops[left_index]
        right_site, right_op = right.ops[right_index]
        if left_site < right_site:
            left_index += 1
        elif right_site < left_site:
            right_index += 1
        else:
            if left_op != right_op:
                parity ^= 1
            left_index += 1
            right_index += 1
        if parity and (
            left_index >= len(left.ops) or right_index >= len(right.ops)
        ):
            break
    return parity == 0


_DENSE = {
    "I": np.eye(2, dtype=complex),
    "X": np.array([[0, 1], [1, 0]], dtype=complex),
    "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
    "Z": np.array([[1, 0], [0, -1]], dtype=complex),
}


def to_dense(operator: PauliSum, n_qubits: int) -> np.ndarray:
    if n_qubits < 0:
        raise ValueError("n_qubits must be nonnegative")
    dimension = 1 << n_qubits
    result = np.zeros((dimension, dimension), dtype=complex)
    for pauli, coefficient in operator.terms.items():
        local = pauli.as_dict()
        factors = [_DENSE[local.get(site, "I")] for site in range(n_qubits)]
        matrix = reduce(np.kron, factors, np.array([[1]], dtype=complex))
        result += coefficient.to_complex() * matrix
    return result
