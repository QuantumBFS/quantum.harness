"""Shared real MLP coefficients and IID Born-sampled variational optimization."""

from dataclasses import dataclass

import numpy as np


@dataclass
class Sector:
    basis: np.ndarray
    action: np.ndarray  # H @ basis, computed without diagonalizing H


class Network:
    """One-hot sector -> shared tanh layer -> multiplicity coefficients.

    Coefficients depend on L and the irrep copy, never on its magnetic index M.
    The fixed intertwiners supply the complete antisymmetric LLL wavefunction.
    Real coefficients suffice for the real Coulomb matrices in this convention.
    """

    def __init__(self, dimensions, width=16, seed=0):
        self.dimensions = dimensions
        rng = np.random.default_rng(seed)
        self.parameters = [
            rng.normal(scale=0.3, size=(len(dimensions), width)),
            np.zeros(width),
            rng.normal(scale=0.3, size=(width, max(dimensions))),
            np.zeros(max(dimensions)),
        ]

    def forward(self):
        first, bias, second, output_bias = self.parameters
        hidden = np.tanh(first + bias)
        raw = hidden @ second + output_bias
        states = [raw[i, :d] / np.linalg.norm(raw[i, :d]) for i, d in enumerate(self.dimensions)]
        return states, (hidden, raw)

    def states(self):
        return self.forward()[0]

    def backward(self, state_gradients, intermediates):
        hidden, raw = intermediates
        first_grad, bias_grad, second_grad, output_bias_grad = [
            np.zeros_like(parameter) for parameter in self.parameters
        ]
        for i, (dimension, gradient) in enumerate(zip(self.dimensions, state_gradients)):
            norm = np.linalg.norm(raw[i, :dimension])
            state = raw[i, :dimension] / norm
            output_grad = (gradient - state * (state @ gradient)) / norm
            second_grad[:, :dimension] += np.outer(hidden[i], output_grad)
            output_bias_grad[:dimension] += output_grad
            hidden_grad = (self.parameters[2][:, :dimension] @ output_grad) * (1 - hidden[i] ** 2)
            first_grad[i] += hidden_grad
            bias_grad += hidden_grad
        return [first_grad, bias_grad, second_grad, output_bias_grad]


def energy_gradient(network, sectors, rng=None, samples=4096):
    """Exact Rayleigh gradient, or its unbiased IID VMC covariance estimate."""
    states, intermediates = network.forward()
    energies, gradients = [], []
    for state, sector in zip(states, sectors):
        wavefunction = sector.basis @ state
        action = sector.action @ state
        energy = wavefunction @ action
        if rng is None:
            gradient = 2 * sector.basis.T @ (action - energy * wavefunction)
        else:
            probability = wavefunction ** 2
            probability /= probability.sum()
            counts = rng.multinomial(samples, probability)
            sampled = counts > 0
            local = action[sampled] / wavefunction[sampled]
            weights = counts[sampled] / samples
            mean = weights @ local
            # n/(n-1) removes the finite-n bias of the sample covariance.
            force = weights * (local - mean) / wavefunction[sampled]
            gradient = 2 * samples / (samples - 1) * sector.basis[sampled].T @ force
            # Born sampling cannot visit exact nodes with nonzero derivatives.
            # The enumerated finite basis permits their analytic contribution.
            nodes = wavefunction == 0
            gradient += 2 * sector.basis[nodes].T @ action[nodes]
        energies.append(float(energy))
        gradients.append(gradient / len(sectors))
    return energies, network.backward(gradients, intermediates)


def train(sectors, seed, steps=2000, samples=4096, width=16, progress=True):
    network = Network([sector.basis.shape[1] for sector in sectors], width, seed)
    rng = np.random.default_rng(seed + 10000)
    first_moment = [np.zeros_like(p) for p in network.parameters]
    second_moment = [np.zeros_like(p) for p in network.parameters]
    trace = []
    best_energy = np.inf
    best_parameters = None
    for step in range(1, steps + 1):
        energies, gradients = energy_gradient(network, sectors, rng, samples)
        if np.mean(energies) < best_energy:
            best_energy = np.mean(energies)
            best_parameters = [p.copy() for p in network.parameters]
        learning_rate = 0.02 * (0.02 + 0.98 * (1 - step / steps) ** 2)
        for parameter, gradient, first, second in zip(
            network.parameters, gradients, first_moment, second_moment
        ):
            first *= 0.9
            first += 0.1 * gradient
            second *= 0.999
            second += 0.001 * gradient ** 2
            corrected_first = first / (1 - 0.9 ** step)
            corrected_second = second / (1 - 0.999 ** step)
            parameter -= learning_rate * corrected_first / (np.sqrt(corrected_second) + 1e-8)
        if step == 1 or step % max(1, steps // 10) == 0:
            current, _ = energy_gradient(network, sectors)
            trace.append({'step': step, 'energies': current})
            if progress:
                print(f'  seed={seed} step={step}/{steps} E0={current[0]:.10f} E2={current[1]:.10f}', flush=True)
    final_energies, _ = energy_gradient(network, sectors)
    if best_energy < np.mean(final_energies):
        network.parameters = best_parameters
    return network, trace


def measure(wavefunction, hamiltonian, samples, seed):
    """Independent categorical draws, with a one-standard-error energy bar."""
    probability = np.abs(wavefunction) ** 2
    probability /= probability.sum()
    selected = np.random.default_rng(seed).choice(len(probability), size=samples, p=probability)
    local = (hamiltonian @ wavefunction)[selected] / wavefunction[selected]
    variance = float(np.var(local.real, ddof=1))
    return {
        'mean': float(np.mean(local.real)),
        'standard_error': float(np.sqrt(variance / samples)),
        'local_energy_variance': variance,
        'samples': samples,
        'seed': seed,
        'sampling': 'independent categorical Born draws',
    }
