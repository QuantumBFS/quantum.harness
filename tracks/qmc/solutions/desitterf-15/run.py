"""Reproduce the finite-size symmetric-NQS benchmark for challenge #15."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np
import scipy
from scipy.linalg import expm
import sympy

from nqs import Sector, energy_gradient, measure, train
from sphere import Sphere, angular_momentum


def symmetry_check(model, towers, coefficients, seed):
    rng = np.random.default_rng(seed)
    rotation_errors, exchange_errors, absolute_rotation_errors = [], [], []
    pauli = np.array([[[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]])
    for _ in range(8):
        spinors = rng.normal(size=(model.electrons, 2)) + 1j * rng.normal(size=(model.electrons, 2))
        spinors /= np.linalg.norm(spinors, axis=1)[:, None]
        axis = rng.normal(size=3)
        axis /= np.linalg.norm(axis)
        angle = rng.uniform(-np.pi, np.pi)
        rotation = expm(-0.5j * angle * np.einsum('a,aij->ij', axis, pauli))
        swapped = spinors.copy()
        swapped[[0, 1]] = swapped[[1, 0]]
        for total, (bases, tower), state in zip((0, 2), towers, coefficients):
            original = model.wavefunction(spinors, bases, tower, state)
            rotated = model.wavefunction(spinors @ rotation.T, bases, tower, state)
            exchanged = model.wavefunction(swapped, bases, tower, state)
            generator = sum(a * j for a, j in zip(axis, angular_momentum(total)))
            expected = expm(-1j * angle * generator) @ original
            scale = max(np.linalg.norm(original), np.finfo(float).tiny)
            absolute_rotation_errors.append(float(np.linalg.norm(rotated - expected)))
            rotation_errors.append(float(np.linalg.norm(rotated - expected) / scale))
            exchange_errors.append(float(np.linalg.norm(exchanged + original) / scale))
    return {
        'rotation_relative_error': max(rotation_errors),
        'rotation_absolute_error': max(absolute_rotation_errors),
        'exchange_relative_error': max(exchange_errors),
        'coordinate_samples': 8,
        'seed': seed,
    }


def exact_l_energy(model, magnetic, hamiltonian, total):
    """Diagonalize the full M block, then label its eigenvectors by L²."""
    energies, vectors = np.linalg.eigh(hamiltonian)
    raising = model.raising(magnetic)
    labels = np.sum((raising @ vectors) ** 2, axis=0) + magnetic * (magnetic + 1)
    selected = energies[np.abs(labels - total * (total + 1)) < 1e-7]
    if not len(selected):
        raise RuntimeError(f'Could not identify L={total} in M={magnetic} ED spectrum')
    return float(selected.min())


def run_system(electrons, args):
    started = time.perf_counter()
    model = Sphere(electrons)
    towers = [model.tower(total) for total in (0, 2)]
    hamiltonians = {m: model.hamiltonian(m) for m in range(-2, 3)}
    sectors = [Sector(tower[total], hamiltonians[total] @ tower[total])
               for total, (_, tower) in zip((0, 2), towers)]
    dimensions = [sector.basis.shape[1] for sector in sectors]
    print(f'N={electrons} flux={model.flux} D(M=0)={len(model.basis(0))} multiplicities={dimensions}', flush=True)
    seed_results, networks = [], []
    for seed in args.seeds:
        network, trace = train(sectors, seed, args.steps, args.samples, args.width)
        energies, _ = energy_gradient(network, sectors)
        seed_results.append({'seed': seed, 'energies': energies, 'trace': trace})
        networks.append(network)
        np.savez(args.output / f'N{electrons}_seed{seed}.npz',
                 **{f'parameter_{i}': p for i, p in enumerate(network.parameters)},
                 dimensions=dimensions)
    selected = int(np.argmin([np.mean(run['energies']) for run in seed_results]))
    network = networks[selected]
    coefficients = network.states()
    # ED is used only after all stochastic optimization and checkpoint selection.
    references = [exact_l_energy(model, 0, hamiltonians[0], total) for total in (0, 2)]
    state_results = []
    for index, (total, sector, state, reference) in enumerate(zip((0, 2), sectors, coefficients, references)):
        wavefunction = sector.basis @ state
        action = sector.action @ state
        energy = float(wavefunction @ action)
        residual = float(np.linalg.norm(action - energy * wavefunction))
        measurement_seed = 100000 + 100 * electrons + index
        state_results.append({
            'L': total,
            'M': total,
            'multiplicity': len(state),
            'coefficients': state.tolist(),
            'energy': energy,
            'ed_energy': reference,
            'variational_excess': energy - reference,
            'eigenstate_residual': residual,
            'energy_variance': residual ** 2,
            'mc': measure(wavefunction, hamiltonians[total], args.measurements, measurement_seed),
        })
    multiplet = []
    _, excited_tower = towers[1]
    for magnetic in range(-2, 3):
        wavefunction = excited_tower[magnetic] @ coefficients[1]
        raising = model.raising(magnetic)
        l_squared_state = raising.T @ (raising @ wavefunction) + magnetic * (magnetic + 1) * wavefunction
        energy = float(wavefunction @ hamiltonians[magnetic] @ wavefunction)
        multiplet.append({
            'M': magnetic,
            'energy': energy,
            'ed_energy': exact_l_energy(model, magnetic, hamiltonians[magnetic], 2),
            'l_squared': float(wavefunction @ l_squared_state),
            'l_squared_residual': float(np.linalg.norm(l_squared_state - 6 * wavefunction)),
            'eigenstate_residual': float(np.linalg.norm(hamiltonians[magnetic] @ wavefunction - energy * wavefunction)),
        })
    symmetry = symmetry_check(model, towers, coefficients, seed=200000 + electrons)
    symmetry['multiplet_energy_spread'] = float(np.ptp([row['energy'] for row in multiplet]))
    symmetry['ed_multiplet_energy_spread'] = float(np.ptp([row['ed_energy'] for row in multiplet]))
    symmetry['rotation_commutator_norm'] = float(np.linalg.norm(
        hamiltonians[1] @ model.raising(0) - model.raising(0) @ hamiltonians[0]
    ))
    symmetry['ladder_residual'] = max(float(np.linalg.norm(
        model.raising(m - 1).T @ excited_tower[m]
        - np.sqrt((2 + m) * (3 - m)) * excited_tower[m - 1]
    )) for m in range(2, -2, -1))
    ground, excited = state_results
    gap = {
        'mc_mean': excited['mc']['mean'] - ground['mc']['mean'],
        'standard_error': float(np.hypot(excited['mc']['standard_error'], ground['mc']['standard_error'])),
        'exact_variational': excited['energy'] - ground['energy'],
        'ed': references[1] - references[0],
        'variational_bias_vs_ed': excited['variational_excess'] - ground['variational_excess'],
    }
    result = {
        'electrons': electrons, 'flux': model.flux, 'radius_lB': np.sqrt(model.flux / 2),
        'M0_dimension': len(model.basis(0)),
        'pseudopotentials_by_pair_J': model.pseudopotentials.tolist(),
        'network_parameters': sum(p.size for p in network.parameters),
        'selected_seed': args.seeds[selected],
        'training_runs': seed_results, 'states': state_results, 'gap': gap,
        'multiplet': multiplet, 'symmetry': symmetry,
        'runtime_seconds': time.perf_counter() - started,
    }
    print(f"N={electrons} gap={gap['mc_mean']:.10f} +/- {gap['standard_error']:.2g} ED={gap['ed']:.10f}", flush=True)
    return result


def plot_results(systems, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    with plt.rc_context({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False}):
        figure, axes = plt.subplots(1, 2, figsize=(9.6, 3.8), layout='constrained')
        sizes = [row['electrons'] for row in systems]
        axes[0].errorbar(sizes, [row['gap']['mc_mean'] for row in systems],
                         yerr=[row['gap']['standard_error'] for row in systems],
                         fmt='o', color='#0072B2', capsize=5, label='NQS, MC ±1 SE')
        axes[0].plot(sizes, [row['gap']['ed'] for row in systems],
                     '+', color='#D55E00', markersize=11, label='Exact diagonalization')
        axes[0].set(xlabel='Electron count N', ylabel=r'$\Delta\ [e^2/(\epsilon\ell_B)]$',
                    title='Finite-sphere neutral gap', xticks=sizes)
        axes[0].legend(frameon=False)
        for row, marker in zip(systems, ['o', 's', '^', 'd', 'v']):
            energies = np.array([entry['energy'] for entry in row['multiplet']])
            axes[1].plot(range(-2, 3), 1e12 * (energies - energies[4]),
                         marker=marker, label=f"N={row['electrons']}")
        axes[1].set(xlabel='Magnetic index M', ylabel=r'$10^{12}(E_{2,M}-E_{2,2})$',
                    title='Spin-2 multiplet numerical spread', xticks=range(-2, 3))
        axes[1].legend(frameon=False)
        figure.savefig(output / 'gap.png', dpi=180)
        figure.savefig(output / 'gap.pdf')
        plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--electrons', type=int, nargs='+', choices=range(2, 7), default=[4, 5, 6])
    parser.add_argument('--seeds', type=int, nargs='+', default=[11, 23, 37])
    parser.add_argument('--steps', type=int, default=4000)
    parser.add_argument('--samples', type=int, default=4096)
    parser.add_argument('--measurements', type=int, default=262144)
    parser.add_argument('--width', type=int, default=16)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'results')
    args = parser.parse_args()
    if args.steps < 1 or args.width < 1 or args.samples < 2 or args.measurements < 2 or min(args.seeds) < 0:
        parser.error('steps and width must be positive, sample counts at least 2, seeds nonnegative')
    args.output.mkdir(parents=True, exist_ok=True)
    source_hashes = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                     for name in ('sphere.py', 'nqs.py', 'run.py')}
    data = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'model': 'Spin-polarized LLL, flux 2Q=3(N-1), chord-distance Coulomb',
        'energy_units': 'e^2/(epsilon l_B)',
        'background': 'electron-electron energies, no uniform neutralizing background',
        'chirality': 'not evaluated, SO(3) quantum numbers alone do not determine helicity',
        'settings': {key: value for key, value in vars(args).items() if key != 'output'},
        'versions': {'python': platform.python_version(), 'numpy': np.__version__,
                     'scipy': scipy.__version__, 'sympy': sympy.__version__},
        'source_sha256': source_hashes,
        'systems': [],
    }
    for electrons in args.electrons:
        data['systems'].append(run_system(electrons, args))
        temporary = args.output / 'summary.tmp'
        temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
        temporary.replace(args.output / 'summary.json')
    plot_results(data['systems'], args.output)
    print(f'Results saved in {args.output.resolve()}', flush=True)


if __name__ == '__main__':
    main()
