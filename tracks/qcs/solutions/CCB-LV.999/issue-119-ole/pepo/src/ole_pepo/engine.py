"""Product-observable evolution through the pinned quimb PEPO circuit."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
import time

import numpy as np
import quimb.tensor as qtn

from .gates import interaction_edges, quimb_gates
from .qasm import OLEProtocol


@dataclass(frozen=True, slots=True)
class ProgressRecord:
    processed_causal_gates: int
    total_causal_gates: int
    support_size: int
    max_realized_bond: int
    retained_tail_ratio: float | None
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class EvolutionDiagnostics:
    total_recorded_gates: int
    causal_gates: int
    final_support: tuple[int, ...]
    max_realized_bond: int
    max_retained_tail_ratio: float | None


@dataclass(frozen=True, slots=True)
class EvolutionResult:
    operator: qtn.TensorNetworkGenOperator
    diagnostics: EvolutionDiagnostics


def reverse_lightcone_indices(
    gates: Sequence[qtn.Gate],
    initial_support: Collection[int],
) -> tuple[int, ...]:
    support = set(initial_support)
    selected: list[int] = []
    for index in range(len(gates) - 1, -1, -1):
        where = tuple(gates[index].qubits)
        if support.isdisjoint(where):
            continue
        support.update(where)
        selected.append(index)
    return tuple(selected)


def _retained_tail_ratio(local_info: Mapping[object, np.ndarray]) -> float | None:
    for singular_values in local_info.values():
        values = np.asarray(singular_values).reshape(-1)
        if values.size == 0:
            continue
        leading = abs(values[0])
        if leading == 0:
            return float("inf")
        return float(abs(values[-1]) / leading)
    return None


class ProductObservablePEPO(qtn.CircuitPEPOSimpleUpdate):
    def evolve_product(
        self,
        operators: Mapping[int, np.ndarray],
        *,
        max_bond: int | None = None,
        cutoff: float | None = None,
        progress_every: int = 100,
        progress_callback: Callable[[ProgressRecord], None] | None = None,
    ) -> EvolutionResult:
        """Evolve a product observable through the recorded circuit."""
        if not operators:
            raise ValueError("operators must contain at least one local factor")
        if progress_every <= 0:
            raise ValueError("progress_every must be positive")

        factors = iter(operators.items())
        first_site, first_operator = next(factors)
        first_where = self._parse_where(first_site)
        operator = self._initial_operator(first_operator, first_where)
        support = {first_site}

        for site, local_operator in factors:
            self._parse_where(site)
            operator.gate_upper_(
                np.asarray(local_operator),
                site,
                contract=True,
            )
            support.add(site)

        gates = tuple(self.gates)
        selected = reverse_lightcone_indices(gates, support)
        total_causal_gates = len(selected)
        options = {**self.gate_opts}
        if max_bond is not None:
            options["max_bond"] = max_bond
        if cutoff is not None:
            options["cutoff"] = cutoff

        gauges: dict[object, np.ndarray] = {}
        max_realized_bond = int(operator.max_bond())
        max_retained_tail_ratio: float | None = None
        start = time.monotonic()

        for processed, gate_index in enumerate(selected, start=1):
            gate = gates[gate_index]
            support.update(gate.qubits)
            array = np.asarray(gate.array)
            dimension = int(round(array.size ** 0.5))
            gate_dagger = array.reshape(dimension, dimension).conj().T
            local_info: dict[object, np.ndarray] = {}
            operator.gate_simple_(
                gate_dagger,
                gate.qubits,
                gauges,
                info=local_info,
                **options,
            )

            max_realized_bond = max(
                max_realized_bond,
                int(operator.max_bond()),
            )
            retained_tail_ratio = _retained_tail_ratio(local_info)
            if retained_tail_ratio is not None:
                if max_retained_tail_ratio is None:
                    max_retained_tail_ratio = retained_tail_ratio
                else:
                    max_retained_tail_ratio = max(
                        max_retained_tail_ratio,
                        retained_tail_ratio,
                    )

            if progress_callback is not None and (
                processed == 1
                or processed % progress_every == 0
                or processed == total_causal_gates
            ):
                progress_callback(
                    ProgressRecord(
                        processed_causal_gates=processed,
                        total_causal_gates=total_causal_gates,
                        support_size=len(support),
                        max_realized_bond=max_realized_bond,
                        retained_tail_ratio=retained_tail_ratio,
                        elapsed_seconds=time.monotonic() - start,
                    )
                )

        operator.gauge_simple_insert(gauges)
        diagnostics = EvolutionDiagnostics(
            total_recorded_gates=len(gates),
            causal_gates=total_causal_gates,
            final_support=tuple(sorted(support)),
            max_realized_bond=max_realized_bond,
            max_retained_tail_ratio=max_retained_tail_ratio,
        )
        return EvolutionResult(operator=operator, diagnostics=diagnostics)


def build_pepo_circuit(
    protocol: OLEProtocol,
    max_bond: int | None,
    cutoff: float | None,
) -> ProductObservablePEPO:
    edges = interaction_edges(protocol)
    if not edges:
        raise ValueError("protocol has no CZ geometry")
    edge_set = {frozenset(edge) for edge in edges}
    for gate in protocol.gates:
        if len(gate.qubits) == 2 and frozenset(gate.qubits) not in edge_set:
            raise ValueError(
                f"two-site gate {gate.qubits} is not on a declared CZ edge"
            )

    circuit = ProductObservablePEPO(
        edges=interaction_edges(protocol),
        max_bond=max_bond,
        cutoff=cutoff,
        gate_opts={"renorm": False},
    )
    circuit.apply_gates(quimb_gates(protocol))
    return circuit
