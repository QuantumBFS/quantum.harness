"""Exact-state primitives for Haar-random brickwork circuit layers."""

import time

import numpy as np


def haar_unitary_4(rng):
    """Sample a 4-by-4 unitary from the Haar measure."""
    z = (rng.normal(size=(4, 4)) + 1j * rng.normal(size=(4, 4))) / np.sqrt(2.0)
    q, r = np.linalg.qr(z)
    diagonal = np.diag(r)
    phases = np.where(np.abs(diagonal) > 0.0, diagonal / np.abs(diagonal), 1.0)
    return np.asarray(q * phases[np.newaxis, :], dtype=np.complex128)


def _haar_vector(dimension, rng):
    state = rng.normal(size=dimension) + 1j * rng.normal(size=dimension)
    state = np.asarray(state, dtype=np.complex128)
    state /= np.linalg.norm(state)
    return state


def global_haar_state(L, rng):
    """Return a normalized Haar-random state over all L qubits."""
    if int(L) < 2:
        raise ValueError("L must be at least two")
    return _haar_vector(1 << int(L), rng)


def product_haar_state(L, rng):
    """Return a tensor product of independent single-qubit Haar states."""
    if int(L) < 2:
        raise ValueError("L must be at least two")
    state = np.array([1.0 + 0.0j], dtype=np.complex128)
    for _ in range(int(L)):
        state = np.kron(state, _haar_vector(2, rng))
    return np.asarray(state, dtype=np.complex128)


def layer_pairs(L, parity):
    """Return the periodic nearest-neighbor pairs for one brickwork layer."""
    L, parity = int(L), int(parity)
    if L < 2 or L % 2 or parity not in (0, 1):
        raise ValueError("L must be even and parity must be zero or one")
    return tuple(
        ((parity + 2 * j) % L, (parity + 2 * j + 1) % L)
        for j in range(L // 2)
    )


def apply_two_qubit_gate_inplace(state, gate, sites, L):
    """Apply a gate in |00>, |01>, |10>, |11> order to the specified sites."""
    q0, q1 = map(int, sites)
    if state.dtype != np.complex128 or state.shape != (1 << int(L),):
        raise ValueError("state must be flat complex128 with length 2**L")
    if np.shape(gate) != (4, 4) or q0 == q1:
        raise ValueError("invalid gate or sites")
    tensor = state.reshape((2,) * int(L))
    moved = np.moveaxis(tensor, (q0, q1), (0, 1))
    acted = np.tensordot(
        np.asarray(gate).reshape(2, 2, 2, 2), moved, axes=((2, 3), (0, 1))
    )
    state[:] = np.moveaxis(acted, (0, 1), (q0, q1)).reshape(-1)


def apply_gate_layer(state, L, parity, rng):
    """Apply independent Haar gates over one periodic brickwork layer."""
    pairs = layer_pairs(L, parity)
    for pair in pairs:
        apply_two_qubit_gate_inplace(state, haar_unitary_4(rng), pair, L)
    return len(pairs)


def measure_z_inplace(state, site, L, rng):
    """Sample and apply a single-site computational-basis measurement."""
    tensor = state.reshape((2,) * int(L))
    norm2 = float(np.vdot(state, state).real)
    q0_raw = float(np.sum(np.abs(np.take(tensor, 0, axis=int(site))) ** 2))
    tolerance = 128.0 * np.finfo(np.float64).eps * max(1.0, norm2)
    if q0_raw < -tolerance or q0_raw > norm2 + tolerance:
        raise FloatingPointError("Born probability outside numerical tolerance")
    q0 = float(np.clip(q0_raw / norm2, 0.0, 1.0))
    outcome = int(rng.random() >= q0)
    probability = q0 if outcome == 0 else 1.0 - q0
    if probability <= np.finfo(np.float64).tiny:
        raise FloatingPointError("sampled outcome below positive threshold")
    index = [slice(None)] * int(L)
    index[int(site)] = 1 - outcome
    tensor[tuple(index)] = 0.0
    state /= np.sqrt(probability * norm2)
    return outcome, probability


def apply_measurement_layer(state, L, p, rng, accumulate_cost):
    """Apply independently selected single-site Z measurements."""
    selected = np.flatnonzero(rng.random(int(L)) < float(p))
    cost, outcomes = 0.0, [0, 0]
    for site in selected:
        outcome, probability = measure_z_inplace(state, int(site), L, rng)
        outcomes[outcome] += 1
        if accumulate_cost:
            cost -= float(np.log(probability))
    return {"cost": cost, "attempted": int(selected.size), "outcomes": outcomes}


def run_trajectory(L, p, seed, initial_family,
                   burn_in_steps=None, record_steps=None):
    """Evolve one seeded Haar-circuit trajectory with Z measurements."""
    L, p, seed = int(L), float(p), int(seed)
    if L < 2 or L % 2 or not 0.0 <= p <= 1.0:
        raise ValueError("invalid even width or measurement probability")
    burn = 4 * L if burn_in_steps is None else int(burn_in_steps)
    record = 24 * L if record_steps is None else int(record_steps)
    if burn < 0 or record <= 0:
        raise ValueError("invalid trajectory lengths")
    rng = np.random.default_rng(seed)
    factories = {"global_haar": global_haar_state, "product": product_haar_state}
    if initial_family not in factories:
        raise ValueError("unknown initial-state family")
    state = factories[initial_family](L, rng)
    cumulative, total_cost = [], 0.0
    attempted, outcomes, gates = 0, [0, 0], 0
    started = time.perf_counter()
    for step in range(burn + record):
        gates += apply_gate_layer(state, L, step % 2, rng)
        result = apply_measurement_layer(state, L, p, rng, step >= burn)
        attempted += result["attempted"]
        outcomes = [outcomes[j] + result["outcomes"][j] for j in (0, 1)]
        if step >= burn:
            total_cost += result["cost"]
            cumulative.append(total_cost)
    return {"schema_version": 1, "L": L, "p": p,
            "initial_family": initial_family, "seed": seed,
            "burn_in_steps": burn, "record_steps": record,
            "record_cost": total_cost, "cumulative_record_cost": cumulative,
            "runtime_seconds": time.perf_counter() - started,
            "gate_count": gates, "attempted_measurements": attempted,
            "outcome_counts": outcomes}
