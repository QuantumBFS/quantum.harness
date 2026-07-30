"""Dual-unitary monitored-circuit primitives and a compact MPS backend."""

import time
from dataclasses import dataclass

import numpy as np
import scipy.linalg


X = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
Y = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=np.complex128)
Z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)
SWAP = np.array(
    [[1.0, 0.0, 0.0, 0.0],
     [0.0, 0.0, 1.0, 0.0],
     [0.0, 1.0, 0.0, 0.0],
     [0.0, 0.0, 0.0, 1.0]],
    dtype=np.complex128,
)


@dataclass(frozen=True)
class LayerEvent:
    pairs: tuple
    gates: tuple
    measured_sites: tuple
    measurement_uniforms: np.ndarray


def haar_su2(rng):
    """Draw a Haar-distributed matrix from SU(2)."""
    z = (rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2))) / np.sqrt(2)
    q, r = np.linalg.qr(z)
    diagonal = np.diag(r)
    phases = np.where(np.abs(diagonal) > 0.0,
                      diagonal / np.abs(diagonal), 1.0)
    q = q * phases[np.newaxis, :]
    q /= np.sqrt(np.linalg.det(q))
    return np.asarray(q, dtype=np.complex128)


def dual_unitary_gate(rng):
    """Draw one two-qubit gate from the dual-Haar ensemble."""
    phase, coupling = rng.uniform(0.0, np.pi, size=2)
    u_plus, u_minus, v_minus, v_plus = (haar_su2(rng) for _ in range(4))
    generator = (
        np.kron(X, X) + np.kron(Y, Y) + coupling * np.kron(Z, Z)
    )
    core = scipy.linalg.expm(-0.25j * np.pi * generator)
    gate = (
        np.exp(1j * phase)
        * np.kron(u_plus, u_minus)
        @ core
        @ np.kron(v_minus, v_plus)
    )
    return np.asarray(gate, dtype=np.complex128)


def dual_reshuffle(gate):
    """Reshuffle U[a,b,c,d] into its space-direction matrix U[a,c,b,d]."""
    gate = np.asarray(gate, dtype=np.complex128)
    if gate.shape != (4, 4):
        raise ValueError("gate must have shape (4, 4)")
    return gate.reshape(2, 2, 2, 2).transpose(0, 2, 1, 3).reshape(4, 4)


def layer_pairs(L, parity):
    """Return periodic brickwork pairs for an even-width chain."""
    L, parity = int(L), int(parity)
    if L < 2 or L % 2 or parity not in (0, 1):
        raise ValueError("L must be even and parity must be zero or one")
    return tuple(
        ((parity + 2 * index) % L, (parity + 2 * index + 1) % L)
        for index in range(L // 2)
    )


def layer_event(L, p, seed, step):
    """Generate one random-access gate and measurement layer."""
    L, p, seed, step = int(L), float(p), int(seed), int(step)
    if L < 2 or L % 2:
        raise ValueError("L must be a positive even width")
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be a probability")
    if step < 0:
        raise ValueError("step must be nonnegative")
    rng = np.random.default_rng(
        np.random.SeedSequence([seed, L, step, 0xD0A1])
    )
    pairs = layer_pairs(L, step % 2)
    gates = tuple(dual_unitary_gate(rng) for _ in pairs)
    measured_sites = tuple(map(int, np.flatnonzero(rng.random(L) < p)))
    measurement_uniforms = np.asarray(
        rng.random(len(measured_sites)), dtype=np.float64
    )
    return LayerEvent(
        pairs=pairs,
        gates=gates,
        measured_sites=measured_sites,
        measurement_uniforms=measurement_uniforms,
    )


def product_state_vectors(L, seed):
    """Return deterministic single-qubit Haar vectors for one trajectory."""
    L, seed = int(L), int(seed)
    if L < 2:
        raise ValueError("L must be at least two")
    rng = np.random.default_rng(np.random.SeedSequence([seed, L, 0x1A17]))
    vectors = []
    for _ in range(L):
        vector = rng.normal(size=2) + 1j * rng.normal(size=2)
        vector = np.asarray(vector / np.linalg.norm(vector), dtype=np.complex128)
        vectors.append(vector)
    return tuple(vectors)


def product_state_dense(vectors):
    """Form a flat dense state from ordered one-site vectors."""
    state = np.array([1.0 + 0.0j], dtype=np.complex128)
    for vector in vectors:
        state = np.kron(state, np.asarray(vector, dtype=np.complex128))
    return np.asarray(state, dtype=np.complex128)


class CanonicalMPS:
    """Minimal normalized OBC MPS with a tracked orthogonality center."""

    def __init__(self, tensors, center=0):
        self.tensors = [np.asarray(tensor, dtype=np.complex128)
                        for tensor in tensors]
        self.center = int(center)
        self.discarded_weight_sum = 0.0
        self.split_count = 0
        self.peak_bond = self.max_bond

    @classmethod
    def product_state(cls, vectors):
        tensors = [np.asarray(vector, dtype=np.complex128).reshape(1, 2, 1)
                   for vector in vectors]
        if len(tensors) < 2:
            raise ValueError("an MPS needs at least two sites")
        return cls(tensors, center=0)

    @property
    def L(self):
        return len(self.tensors)

    @property
    def max_bond(self):
        if len(self.tensors) < 2:
            return 1
        return max(tensor.shape[2] for tensor in self.tensors[:-1])

    def _move_center_right(self):
        site = self.center
        left = self.tensors[site]
        right = self.tensors[site + 1]
        dl, physical, bond = left.shape
        q, r = np.linalg.qr(left.reshape(dl * physical, bond), mode="reduced")
        new_bond = q.shape[1]
        self.tensors[site] = q.reshape(dl, physical, new_bond)
        self.tensors[site + 1] = np.tensordot(r, right, axes=(1, 0))
        self.center += 1

    def _move_center_left(self):
        site = self.center
        left = self.tensors[site - 1]
        right = self.tensors[site]
        bond, physical, dr = right.shape
        q, r = np.linalg.qr(
            right.reshape(bond, physical * dr).T, mode="reduced"
        )
        new_bond = q.shape[1]
        self.tensors[site] = q.T.reshape(new_bond, physical, dr)
        self.tensors[site - 1] = np.tensordot(left, r.T, axes=(2, 0))
        self.center -= 1

    def move_center(self, target):
        target = int(target)
        if not 0 <= target < self.L:
            raise ValueError("orthogonality center is outside the MPS")
        while self.center < target:
            self._move_center_right()
        while self.center > target:
            self._move_center_left()

    def apply_adjacent_gate(self, left_site, gate, chi, cutoff):
        """Apply and optimally split a gate on ``left_site,left_site+1``."""
        left_site, chi, cutoff = int(left_site), int(chi), float(cutoff)
        if not 0 <= left_site < self.L - 1:
            raise ValueError("adjacent gate starts outside the MPS")
        if chi <= 0 or cutoff < 0.0:
            raise ValueError("chi must be positive and cutoff nonnegative")
        gate = np.asarray(gate, dtype=np.complex128)
        if gate.shape != (4, 4):
            raise ValueError("gate must have shape (4, 4)")

        self.move_center(left_site)
        left = self.tensors[left_site]
        right = self.tensors[left_site + 1]
        dl, _, shared = left.shape
        if right.shape[0] != shared:
            raise ValueError("neighboring MPS tensors have mismatched bonds")
        dr = right.shape[2]
        theta = np.einsum("asb,btc->astc", left, right, optimize=True)
        theta = np.einsum(
            "uvst,astc->auvc", gate.reshape(2, 2, 2, 2), theta,
            optimize=True,
        )
        matrix = theta.reshape(dl * 2, 2 * dr)
        try:
            u, singular, vh = np.linalg.svd(matrix, full_matrices=False)
        except np.linalg.LinAlgError:
            print(
                "warning: gesdd SVD did not converge; retrying with gesvd",
                flush=True,
            )
            u, singular, vh = scipy.linalg.svd(
                matrix,
                full_matrices=False,
                check_finite=True,
                lapack_driver="gesvd",
            )
        norm2 = float(np.sum(singular**2))
        if not np.isfinite(norm2) or norm2 <= 0.0:
            raise FloatingPointError("two-site state has invalid norm")
        if cutoff == 0.0:
            numerical_rank = singular.size
        else:
            numerical_rank = int(np.count_nonzero(singular > cutoff * singular[0]))
        rank = max(1, min(chi, numerical_rank))
        discarded = float(np.sum(singular[rank:] ** 2) / norm2)
        kept = singular[:rank]
        kept_norm = float(np.linalg.norm(kept))
        if kept_norm <= 0.0:
            raise FloatingPointError("truncation removed the full state")
        kept = kept / kept_norm
        self.tensors[left_site] = u[:, :rank].reshape(dl, 2, rank)
        self.tensors[left_site + 1] = (
            kept[:, np.newaxis] * vh[:rank, :]
        ).reshape(rank, 2, dr)
        self.center = left_site + 1
        self.discarded_weight_sum += discarded
        self.split_count += 1
        self.peak_bond = max(self.peak_bond, self.max_bond)
        return discarded

    def apply_periodic_gate(self, sites, gate, chi, cutoff):
        """Apply a nearest-neighbor gate on the physical ring."""
        first, second = map(int, sites)
        before = self.discarded_weight_sum
        if second == first + 1:
            self.apply_adjacent_gate(first, gate, chi, cutoff)
        elif (first, second) == (self.L - 1, 0):
            for position in range(self.L - 2):
                self.apply_adjacent_gate(position, SWAP, chi, cutoff)
            reversed_gate = SWAP @ np.asarray(gate) @ SWAP
            self.apply_adjacent_gate(self.L - 2, reversed_gate, chi, cutoff)
            for position in reversed(range(self.L - 2)):
                self.apply_adjacent_gate(position, SWAP, chi, cutoff)
        else:
            raise ValueError("sites are not nearest neighbors on the ring")
        return self.discarded_weight_sum - before

    def measure_z(self, site, uniform):
        """Born-sample and project one site in the computational basis."""
        site, uniform = int(site), float(uniform)
        if not 0 <= site < self.L or not 0.0 <= uniform < 1.0:
            raise ValueError("invalid measurement site or uniform variate")
        self.move_center(site)
        tensor = self.tensors[site]
        norm2 = float(np.vdot(tensor, tensor).real)
        q0_raw = float(np.vdot(tensor[:, 0, :], tensor[:, 0, :]).real)
        tolerance = 256.0 * np.finfo(float).eps * max(1.0, norm2)
        if q0_raw < -tolerance or q0_raw > norm2 + tolerance:
            raise FloatingPointError("Born probability outside tolerance")
        q0 = float(np.clip(q0_raw / norm2, 0.0, 1.0))
        outcome = int(uniform >= q0)
        probability = q0 if outcome == 0 else 1.0 - q0
        if probability <= np.finfo(float).tiny:
            raise FloatingPointError("sampled a numerically zero-probability outcome")
        tensor[:, 1 - outcome, :] = 0.0
        tensor /= np.sqrt(probability * norm2)
        return outcome, probability

    def to_dense(self):
        """Contract the OBC MPS into a flat state vector."""
        state = self.tensors[0][0, :, :]
        for tensor in self.tensors[1:]:
            state = np.tensordot(state, tensor, axes=(-1, 0))
        return np.asarray(state[..., 0].reshape(-1), dtype=np.complex128)


def apply_dense_gate_inplace(state, gate, sites, L):
    """Apply a two-qubit gate to a dense state in ordered-site convention."""
    first, second = map(int, sites)
    tensor = state.reshape((2,) * int(L))
    moved = np.moveaxis(tensor, (first, second), (0, 1))
    acted = np.tensordot(
        np.asarray(gate).reshape(2, 2, 2, 2),
        moved,
        axes=((2, 3), (0, 1)),
    )
    state[:] = np.moveaxis(acted, (0, 1), (first, second)).reshape(-1)


def measure_dense_z_inplace(state, site, L, uniform):
    """Born-sample and project a dense state using a supplied uniform variate."""
    site, L, uniform = int(site), int(L), float(uniform)
    tensor = state.reshape((2,) * L)
    norm2 = float(np.vdot(state, state).real)
    q0 = float(np.sum(np.abs(np.take(tensor, 0, axis=site)) ** 2) / norm2)
    outcome = int(uniform >= q0)
    probability = q0 if outcome == 0 else 1.0 - q0
    if probability <= np.finfo(float).tiny:
        raise FloatingPointError("sampled a numerically zero-probability outcome")
    index = [slice(None)] * L
    index[site] = 1 - outcome
    tensor[tuple(index)] = 0.0
    state /= np.sqrt(probability * norm2)
    return outcome, probability


def _validate_trajectory_inputs(L, p, burn_in_steps, record_steps):
    L, p = int(L), float(p)
    burn_in_steps, record_steps = int(burn_in_steps), int(record_steps)
    if L < 2 or L % 2 or not 0.0 <= p <= 1.0:
        raise ValueError("invalid trajectory width or measurement probability")
    if burn_in_steps < 0 or record_steps <= 0:
        raise ValueError("invalid trajectory lengths")
    return L, p, burn_in_steps, record_steps


def run_dense_oracle(L, p, seed, burn_in_steps, record_steps):
    """Run a small exact trajectory using the same stateless random events."""
    L, p, burn_in_steps, record_steps = _validate_trajectory_inputs(
        L, p, burn_in_steps, record_steps
    )
    if L > 16:
        raise ValueError("dense oracle is restricted to L <= 16")
    state = product_state_dense(product_state_vectors(L, seed))
    cumulative, total_cost = [], 0.0
    outcomes, attempted = [0, 0], 0
    for step in range(burn_in_steps + record_steps):
        event = layer_event(L, p, seed, step)
        for sites, gate in zip(event.pairs, event.gates):
            apply_dense_gate_inplace(state, gate, sites, L)
        layer_cost = 0.0
        for site, uniform in zip(
            event.measured_sites, event.measurement_uniforms
        ):
            outcome, probability = measure_dense_z_inplace(
                state, site, L, uniform
            )
            outcomes[outcome] += 1
            attempted += 1
            if step >= burn_in_steps:
                layer_cost -= float(np.log(probability))
        if step >= burn_in_steps:
            total_cost += layer_cost
            cumulative.append(total_cost)
    return {
        "L": L,
        "p": p,
        "seed": int(seed),
        "burn_in_steps": burn_in_steps,
        "record_steps": record_steps,
        "record_cost": total_cost,
        "cumulative_record_cost": cumulative,
        "attempted_measurements": attempted,
        "outcome_counts": outcomes,
    }


def run_mps_trajectory(L, p, chi, seed, burn_in_steps, record_steps,
                       cutoff=1e-12, progress_every=0):
    """Run one periodic dual-unitary Born trajectory with a capped MPS."""
    L, p, burn_in_steps, record_steps = _validate_trajectory_inputs(
        L, p, burn_in_steps, record_steps
    )
    chi, cutoff = int(chi), float(cutoff)
    if chi <= 0 or cutoff < 0.0:
        raise ValueError("chi must be positive and cutoff nonnegative")
    mps = CanonicalMPS.product_state(product_state_vectors(L, seed))
    cumulative, total_cost = [], 0.0
    outcomes, attempted = [0, 0], 0
    progress_every = int(progress_every)
    if progress_every < 0:
        raise ValueError("progress_every must be nonnegative")
    started = time.perf_counter()
    total_steps = burn_in_steps + record_steps
    for step in range(total_steps):
        event = layer_event(L, p, seed, step)
        for sites, gate in zip(event.pairs, event.gates):
            mps.apply_periodic_gate(sites, gate, chi, cutoff)
        layer_cost = 0.0
        for site, uniform in zip(
            event.measured_sites, event.measurement_uniforms
        ):
            outcome, probability = mps.measure_z(site, uniform)
            outcomes[outcome] += 1
            attempted += 1
            if step >= burn_in_steps:
                layer_cost -= float(np.log(probability))
        if step >= burn_in_steps:
            total_cost += layer_cost
            cumulative.append(total_cost)
        completed = step + 1
        if progress_every and (
            completed % progress_every == 0 or completed == total_steps
        ):
            elapsed = time.perf_counter() - started
            remaining = elapsed * (total_steps / completed - 1.0)
            print(
                f"step={completed}/{total_steps} elapsed={elapsed:.1f}s "
                f"remaining={remaining:.1f}s record_cost={total_cost:.9f} "
                f"discarded={mps.discarded_weight_sum:.6e}",
                flush=True,
            )
    return {
        "schema_version": 1,
        "L": L,
        "p": p,
        "chi": chi,
        "cutoff": cutoff,
        "seed": int(seed),
        "burn_in_steps": burn_in_steps,
        "record_steps": record_steps,
        "record_cost": total_cost,
        "cumulative_record_cost": cumulative,
        "discarded_weight_sum": mps.discarded_weight_sum,
        "split_count": mps.split_count,
        "max_bond_used": mps.peak_bond,
        "runtime_seconds": time.perf_counter() - started,
        "attempted_measurements": attempted,
        "outcome_counts": outcomes,
    }
