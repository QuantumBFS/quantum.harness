"""Protocol adapter for the frozen occupation-autoregressive candidate."""

from __future__ import annotations

from numbers import Integral
from types import MappingProxyType
from typing import Mapping

import numpy as np

from ...contracts import (
    CandidateAdapter,
    ConstructionCertificate,
    DiagnosticProvider,
    ResourceMetrics,
    SampleBatch,
)
from ...protocol import ProtocolConfig
from .constraints import occupation_m2
from .diagnostics import evaluate_tower_diagnostics
from .model import AutoregressiveNQS
from .operators import PreparedPairOperator, local_energy, local_l2
from .tower import FixedMMetropolisSampler, LadderComponent, LadderTower


CERTIFICATE_STATEMENT = (
    "Occupation-basis fermionic state: fixed LLL orbitals make strict LLL exact; "
    "bitset occupation makes particle-swap antisymmetry exact; sparse "
    "autoregressive and ladder operations avoid support enumeration."
)


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer")
    return int(value)


class OccupationState:
    """Batched ``StateHandle`` backed only by sparse occupation operations."""

    def __init__(
        self,
        *,
        label: str,
        l: int,
        m: int,
        model: AutoregressiveNQS,
        operator: PreparedPairOperator,
        burn_in_steps: int,
        direct_sector: str | None,
        tower: LadderTower | None = None,
        component: LadderComponent | None = None,
    ) -> None:
        if not isinstance(label, str) or not label:
            raise ValueError("label must be non-empty")
        self.label = label
        self.l = _integer("l", l)
        self.m = _integer("m", m)
        self._model = model
        self._operator = operator
        self._burn_in_steps = _integer("burn_in_steps", burn_in_steps)
        if self._burn_in_steps < 0:
            raise ValueError("burn_in_steps must be non-negative")
        if direct_sector not in {None, "ground", "excited"}:
            raise ValueError("direct_sector must be ground, excited, or None")
        if direct_sector is None and (tower is None or component is None):
            raise ValueError("derived states require a tower component")
        if direct_sector is not None and (tower is not None or component is not None):
            raise ValueError("direct states cannot carry a tower component")
        self._direct_sector = direct_sector
        self._tower = tower
        self._component = component
        self.n_electrons = model.n_electrons
        self.two_q = model.two_q

    def _validated_batch(self, config_batch: object) -> np.ndarray:
        configs = np.asarray(config_batch, dtype=object)
        if configs.ndim != 1 or configs.size == 0:
            raise ValueError("configuration input must be a one-dimensional non-empty batch")
        validated = np.empty(configs.size, dtype=object)
        for index, raw_state in enumerate(configs):
            state = _integer("state", raw_state)
            if state < 0 or state >= 1 << (self.two_q + 1):
                raise ValueError("state is outside the orbital range")
            if (
                state.bit_count() != self.n_electrons
                or occupation_m2(state, self.two_q) != 2 * self.m
            ):
                raise ValueError("state is not in the fixed-N fixed-M sector")
            validated[index] = state
        return validated

    def _logpsi_scalar(self, state: int) -> complex:
        if self._direct_sector is not None:
            return self._model.logpsi(state, self._direct_sector)
        if self._component is None:
            raise AssertionError("derived state is missing its component")
        return self._component.logpsi(state)

    @staticmethod
    def _finite(values: list[complex], name: str, *, allow_zero: bool = False) -> np.ndarray:
        array = np.asarray(values, dtype=np.complex128)
        real_ok = np.isfinite(array.real) | (allow_zero & np.isneginf(array.real))
        if not np.all(real_ok) or not np.all(np.isfinite(array.imag)):
            raise FloatingPointError(f"non-finite batched {name}")
        return array

    def sample(self, n_samples: int, seed: int) -> SampleBatch:
        sample_count = _integer("n_samples", n_samples)
        random_seed = _integer("seed", seed)
        if sample_count <= 0:
            raise ValueError("n_samples must be positive")
        if random_seed < 0:
            raise ValueError("seed must be non-negative")
        if self._direct_sector is not None:
            configs = np.asarray(
                self._model.sample(sample_count, self._direct_sector, seed=random_seed),
                dtype=object,
            )
            configs.setflags(write=False)
            return SampleBatch(
                configs=configs,
                n_samples=sample_count,
                burn_in_steps=self._burn_in_steps,
                seed=random_seed,
            )
        if self._tower is None:
            raise AssertionError("derived state is missing its tower")
        sampled = FixedMMetropolisSampler(self._tower, target_m=self.m).sample(
            n_samples=sample_count,
            burn_in_steps=self._burn_in_steps,
            seed=random_seed,
        )
        return SampleBatch(
            configs=sampled.configs,
            n_samples=sampled.n_samples,
            burn_in_steps=sampled.burn_in_steps,
            seed=sampled.seed,
        )

    def logpsi(self, config_batch: object) -> np.ndarray:
        configs = self._validated_batch(config_batch)
        return self._finite(
            [self._logpsi_scalar(int(state)) for state in configs],
            "logpsi",
            allow_zero=True,
        )

    def local_energy(self, config_batch: object) -> np.ndarray:
        configs = self._validated_batch(config_batch)
        return self._finite(
            [
                local_energy(
                    int(state),
                    operator=self._operator,
                    logpsi=self._logpsi_scalar,
                )
                for state in configs
            ],
            "local energy",
        )

    def local_l2(self, config_batch: object) -> np.ndarray:
        configs = self._validated_batch(config_batch)
        return self._finite(
            [
                local_l2(
                    int(state),
                    two_q=self.two_q,
                    target_m=float(self.m),
                    logpsi=self._logpsi_scalar,
                )
                for state in configs
            ],
            "local L2",
        )


class OccupationCandidate:
    """Frozen candidate plus its exact-construction diagnostics provider."""

    name = "BOTS-848 occupation autoregressive"
    family = "occupation_autoregressive"

    def __init__(
        self,
        *,
        model: AutoregressiveNQS,
        operator: PreparedPairOperator,
        protocol: ProtocolConfig,
        resources: ResourceMetrics,
        training_seed: int,
        manifest_sha256: str,
        checkpoint_sha256: str,
    ) -> None:
        if not isinstance(model, AutoregressiveNQS):
            raise TypeError("model must be an AutoregressiveNQS")
        if not isinstance(operator, PreparedPairOperator):
            raise TypeError("operator must be a PreparedPairOperator")
        if operator.two_q != model.two_q:
            raise ValueError("operator and model flux do not match")
        self._model = model
        self._operator = operator
        self._protocol = protocol
        self._resources = resources
        self.training_seed = _integer("training_seed", training_seed)
        self.protocol_sha256 = protocol.sha256
        self.manifest_sha256 = manifest_sha256
        self.checkpoint_sha256 = checkpoint_sha256
        self.parameter_count = model.parameter_count
        burn_in = int(protocol.sampling["burn_in_steps"])
        tower = LadderTower.from_m0(
            logpsi=lambda state: model.logpsi(state, "excited"),
            log_score=lambda state: model.log_derivative(state, "excited"),
            n_electrons=model.n_electrons,
            two_q=model.two_q,
            l=2,
        )
        self._tower = tower
        self._ground = OccupationState(
            label="ground_l0_m0",
            l=0,
            m=0,
            model=model,
            operator=operator,
            burn_in_steps=burn_in,
            direct_sector="ground",
        )
        components: dict[int, OccupationState] = {}
        for m in tower:
            if m == 0:
                components[m] = OccupationState(
                    label="tower_l2_m0",
                    l=2,
                    m=0,
                    model=model,
                    operator=operator,
                    burn_in_steps=burn_in,
                    direct_sector="excited",
                )
            else:
                components[m] = OccupationState(
                    label=f"tower_l2_m{m:+d}",
                    l=2,
                    m=m,
                    model=model,
                    operator=operator,
                    burn_in_steps=burn_in,
                    direct_sector=None,
                    tower=tower,
                    component=tower[m],
                )
        self._multiplet: Mapping[int, OccupationState] = MappingProxyType(
            {m: components[m] for m in (-2, -1, 0, 1, 2)}
        )

    def ground_state(self) -> OccupationState:
        return self._ground

    def generate_multiplet(self) -> Mapping[int, OccupationState]:
        return self._multiplet

    def construction_certificate(self) -> ConstructionCertificate:
        return ConstructionCertificate(
            strict_lll=True,
            antisymmetric=True,
            scalable=True,
            trainable_parameters=self.parameter_count,
            statement=CERTIFICATE_STATEMENT,
        )

    def resource_metrics(self) -> ResourceMetrics:
        return self._resources

    def evaluate(
        self,
        candidate: CandidateAdapter,
        *,
        seed: int,
        swap_probes: int,
        rotation_probes: int,
    ) -> Mapping[str, float]:
        if candidate is not self:
            raise ValueError("diagnostics provider is bound to this candidate")
        swaps = _integer("swap_probes", swap_probes)
        rotations = _integer("rotation_probes", rotation_probes)
        random_seed = _integer("seed", seed)
        if swaps <= 0 or rotations <= 0:
            raise ValueError("diagnostic probe counts must be positive")
        if random_seed < 0:
            raise ValueError("seed must be non-negative")
        return evaluate_tower_diagnostics(
            self._tower,
            seed=random_seed,
            burn_in_steps=int(self._protocol.sampling["burn_in_steps"]),
            sample_count=swaps,
            rotation_probes=rotations,
        )
