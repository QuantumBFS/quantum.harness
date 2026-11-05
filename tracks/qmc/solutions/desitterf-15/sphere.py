"""Small-system LLL Coulomb Hamiltonian and exact SO(3) intertwiners.

Orbitals are ordered by m=-Q,...,Q. Energies use e^2/(epsilon l_B).
Only N=2,...,6 is supported because the construction enumerates Fock states.
"""

from functools import cache
from itertools import combinations
from math import comb, factorial, sqrt

import numpy as np
from scipy.linalg import null_space
from scipy.special import beta
from sympy import Rational
from sympy.physics.wigner import clebsch_gordan


@cache
def coupling(flux, first, second, total):
    q = Rational(flux, 2)
    return float(clebsch_gordan(q, q, total, first - q, second - q, first + second - flux))


def coulomb_pseudopotentials(flux):
    """Return V_J, indexed by pair total J, for the finite sphere.

    Fix particle 1 at the north pole and trace the pair projector over M.
    With t=sin(gamma/2)^2 the Coulomb factor is 1/(2 sqrt(Q t)).
    The remaining beta integrals are analytic, with no planar approximation.
    """
    radius = sqrt(flux / 2)
    values = []
    for total in range(flux + 1):
        integral = sum(
            coupling(flux, flux, k, total) ** 2
            * comb(flux, k) * beta(flux - k + 0.5, k + 1)
            for k in range(flux + 1)
        )
        values.append((flux + 1) ** 2 * integral / ((2 * total + 1) * 2 * radius))
    return np.array(values)


def angular_momentum(total):
    magnetic = np.arange(-total, total + 1, dtype=float)
    raising = np.diag(np.sqrt((total - magnetic[:-1]) * (total + magnetic[:-1] + 1)), -1)
    return (raising + raising.T) / 2, (raising - raising.T) / (2j), np.diag(magnetic)


def fermion_action(state, annihilate, create):
    """Apply operators in their action order, retaining the Fock signs."""
    sign = 1
    for orbital in annihilate:
        if not state & (1 << orbital):
            return None
        sign *= (-1) ** (state & ((1 << orbital) - 1)).bit_count()
        state ^= 1 << orbital
    for orbital in create:
        if state & (1 << orbital):
            return None
        sign *= (-1) ** (state & ((1 << orbital) - 1)).bit_count()
        state ^= 1 << orbital
    return state, sign


class Sphere:
    def __init__(self, electrons):
        if not isinstance(electrons, int) or not 2 <= electrons <= 6:
            raise ValueError('Supported electron counts are integers from 2 through 6')
        self.electrons = electrons
        self.flux = 3 * (electrons - 1)
        self.pseudopotentials = coulomb_pseudopotentials(self.flux)
        self.pairs = list(combinations(range(self.flux + 1), 2))
        self.sectors = {}
        for occupied in combinations(range(self.flux + 1), electrons):
            magnetic = (2 * sum(occupied) - electrons * self.flux) // 2
            self.sectors.setdefault(magnetic, []).append(sum(1 << k for k in occupied))

    def basis(self, magnetic):
        return self.sectors.get(magnetic, [])

    @cache
    def raising(self, magnetic):
        source = self.basis(magnetic)
        target = {state: row for row, state in enumerate(self.basis(magnetic + 1))}
        operator = np.zeros((len(target), len(source)))
        for column, state in enumerate(source):
            for k in range(self.flux):
                action = fermion_action(state, [k], [k + 1])
                if action is not None:
                    moved, sign = action
                    operator[target[moved], column] += sign * sqrt((self.flux - k) * (k + 1))
        return operator

    def pair_matrix(self, pseudopotentials):
        matrix = np.zeros((len(self.pairs), len(self.pairs)))
        for row, (a, b) in enumerate(self.pairs):
            for column, (c, d) in enumerate(self.pairs):
                if a + b == c + d:
                    matrix[row, column] = 2 * sum(
                        coupling(self.flux, a, b, total)
                        * coupling(self.flux, c, d, total) * pseudopotentials[total]
                        for total in range(self.flux - 1, -1, -2)
                    )
        return matrix

    def hamiltonian(self, magnetic, pseudopotentials=None):
        if pseudopotentials is None:
            pseudopotentials = self.pseudopotentials
        interaction = self.pair_matrix(pseudopotentials)
        basis = self.basis(magnetic)
        indices = {state: row for row, state in enumerate(basis)}
        matrix = np.zeros((len(basis), len(basis)))
        for column, state in enumerate(basis):
            for incoming, (c, d) in enumerate(self.pairs):
                if state & (1 << c) and state & (1 << d):
                    for outgoing in np.flatnonzero(np.abs(interaction[:, incoming]) > 1e-15):
                        a, b = self.pairs[outgoing]
                        action = fermion_action(state, [c, d], [b, a])
                        if action is not None:
                            moved, sign = action
                            matrix[indices[moved], column] += sign * interaction[outgoing, incoming]
        return matrix

    def tower(self, total):
        """Highest-weight nullspace and its normalized lowering descendants."""
        columns = {total: null_space(self.raising(total), rcond=1e-12)}
        if columns[total].shape[1] == 0:
            raise ValueError(f'No L={total} states at N={self.electrons}')
        for magnetic in range(total, -total, -1):
            normalization = sqrt((total + magnetic) * (total - magnetic + 1))
            raising = self.raising(magnetic - 1)
            lowered = raising.T @ columns[magnetic] / normalization
            casimir = raising.T @ raising + magnetic * (magnetic - 1) * np.eye(len(lowered))
            eigenvalues, vectors = np.linalg.eigh(casimir)
            subspace = vectors[:, np.abs(eigenvalues - total * (total + 1)) < 1e-9]
            # Remove high-L roundoff before its larger ladder factors amplify it.
            # Project the existing columns to preserve their common irrep-copy gauge.
            columns[magnetic - 1] = subspace @ (subspace.T @ lowered)
        return {m: self.basis(m) for m in columns}, columns

    def wavefunction(self, spinors, bases, tower, coefficients):
        """Evaluate the complete L multiplet on one N-particle spinor sample."""
        orbitals = np.array([
            sqrt((self.flux + 1) * comb(self.flux, k) / (4 * np.pi))
            * spinors[:, 0] ** k * spinors[:, 1] ** (self.flux - k)
            for k in range(self.flux + 1)
        ]).T
        amplitudes = []
        for magnetic in sorted(tower):
            determinants = np.array([
                np.linalg.det(orbitals[:, [k for k in range(self.flux + 1) if state & (1 << k)]])
                / sqrt(factorial(self.electrons))
                for state in bases[magnetic]
            ])
            amplitudes.append(determinants @ tower[magnetic] @ coefficients)
        return np.array(amplitudes)
