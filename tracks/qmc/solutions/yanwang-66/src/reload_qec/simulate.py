"""Scalar reference simulator for frozen dynamic loss/reload semantics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import SimulationRequest
from .geometry import DataEdge, Geometry
from .graph import DecodeResult, GraphDecoder, MatchingGraph
from .policy import CarrierState, PolicyMachine
from .rng import EventType, bernoulli, data_pauli_kind


@dataclass(frozen=True)
class SimulationBatch:
    shot_id: np.ndarray
    detection_events: np.ndarray
    syndrome_valid_mask: np.ndarray
    missing_mask: np.ndarray
    erasure_mask: np.ndarray
    loss_mask: np.ndarray
    reload_request_mask: np.ndarray
    reload_mask: np.ndarray
    reload_failure_mask: np.ndarray
    reload_reset_fault_mask: np.ndarray
    logical_observable: np.ndarray
    decoder_prediction: np.ndarray
    logical_failure: np.ndarray
    catastrophic_loss: np.ndarray
    distinct_graphs: int


class Simulator:
    def __init__(self, request: SimulationRequest, geometry: Geometry):
        if (
            geometry.distance != request.distance
            or geometry.rounds != request.rounds
            or geometry.basis != request.basis
        ):
            raise ValueError("request and geometry identity do not match")
        self.request = request
        self.geometry = geometry
        self.data_edges = {edge.site_id: edge for edge in geometry.data_edges()}
        self.relevant_ancillas = {
            site_id: check_index
            for check_index, site_id in enumerate(geometry.relevant_ancilla_site_ids)
        }
        self.graph = MatchingGraph(
            geometry,
            p=request.p,
            p_m=request.p_m,
            p_reset=request.reload.reset_error_probability,
        )
        self.decoder = GraphDecoder(self.graph)

    def simulate(self, shot_ids: np.ndarray) -> SimulationBatch:
        shot_ids = np.asarray(shot_ids, dtype=np.uint64)
        if shot_ids.ndim != 1 or len(np.unique(shot_ids)) != len(shot_ids):
            raise ValueError("shot_ids must be a one-dimensional unique array")
        n_shots = len(shot_ids)
        rounds = self.request.rounds
        n_sites = self.geometry.n_sites
        n_checks = self.graph.n_checks
        detection = np.zeros((n_shots, rounds + 1, n_checks), dtype=np.uint8)
        validity = np.zeros((n_shots, rounds, n_checks), dtype=np.uint8)
        missing = np.zeros((n_shots, rounds + 1, n_sites), dtype=np.uint8)
        erasure = np.zeros((n_shots, rounds, n_sites), dtype=np.uint8)
        losses = np.zeros((n_shots, rounds, n_sites), dtype=np.uint8)
        requests = np.zeros((n_shots, rounds, n_sites), dtype=np.uint8)
        reloads = np.zeros((n_shots, rounds + 1, n_sites), dtype=np.uint8)
        failures = np.zeros((n_shots, rounds + 1, n_sites), dtype=np.uint8)
        reset_faults = np.zeros((n_shots, rounds + 1, n_sites), dtype=np.uint8)
        observables = np.zeros((n_shots, 1), dtype=np.uint8)

        for shot_index, shot_value in enumerate(shot_ids):
            shot_id = int(shot_value)
            machine = PolicyMachine(
                n_sites,
                self.request.policy,
                self.request.reload.delay_rounds,
            )
            logical = 0

            def apply_data_fault(edge: DataEdge, round_index: int) -> None:
                nonlocal logical
                for check_index in edge.endpoints:
                    detection[shot_index, round_index, check_index] ^= 1
                logical ^= edge.logical

            for boundary in range(rounds + 1):
                completion = machine.complete_due(
                    boundary,
                    lambda site_id, boundary=boundary: not bernoulli(
                        self.request.reload.failure_probability,
                        self.request.master_seed,
                        shot_id,
                        boundary,
                        site_id,
                        EventType.RELOAD_SUCCESS,
                    ),
                )
                reset_fault_sites: set[int] = set()
                for site_id in completion.succeeded:
                    reloads[shot_index, boundary, site_id] = 1
                    if bernoulli(
                        self.request.reload.reset_error_probability,
                        self.request.master_seed,
                        shot_id,
                        boundary,
                        site_id,
                        EventType.RELOAD_RESET,
                    ):
                        reset_faults[shot_index, boundary, site_id] = 1
                        reset_fault_sites.add(site_id)
                for site_id in completion.failed:
                    failures[shot_index, boundary, site_id] = 1

                missing[shot_index, boundary] = machine.missing_snapshot()
                if boundary == rounds:
                    break
                round_index = boundary
                active_start = tuple(
                    state == CarrierState.ACTIVE for state in machine.states
                )

                for site_id, edge in self.data_edges.items():
                    if not active_start[site_id]:
                        continue
                    if site_id in reset_fault_sites:
                        apply_data_fault(edge, round_index)
                    if bernoulli(
                        self.request.p,
                        self.request.master_seed,
                        shot_id,
                        round_index,
                        site_id,
                        EventType.DATA_PAULI,
                    ):
                        pauli_kind = data_pauli_kind(
                            self.request.master_seed,
                            shot_id,
                            round_index,
                            site_id,
                        )
                        relevant = (
                            pauli_kind != 0
                            if self.request.basis == "X"
                            else pauli_kind != 2
                        )
                        if relevant:
                            apply_data_fault(edge, round_index)

                new_losses: set[int] = set()
                for site_id, is_active in enumerate(active_start):
                    if not is_active:
                        continue
                    if bernoulli(
                        self.request.p_loss,
                        self.request.master_seed,
                        shot_id,
                        round_index,
                        site_id,
                        EventType.LOSS,
                    ):
                        machine.lose(site_id)
                        new_losses.add(site_id)
                        losses[shot_index, round_index, site_id] = 1

                erasure[shot_index, round_index] = missing[shot_index, boundary]
                for site_id in new_losses:
                    erasure[shot_index, round_index, site_id] = 1
                    edge = self.data_edges.get(site_id)
                    if edge is not None and bernoulli(
                        0.5,
                        self.request.master_seed,
                        shot_id,
                        round_index,
                        site_id,
                        EventType.LOSS_COMPONENT,
                    ):
                        apply_data_fault(edge, round_index)

                for ancilla_site_id, check_index in self.relevant_ancillas.items():
                    is_valid = (
                        active_start[ancilla_site_id]
                        and ancilla_site_id not in new_losses
                    )
                    validity[shot_index, round_index, check_index] = int(is_valid)
                    if not is_valid:
                        continue
                    flipped = ancilla_site_id in reset_fault_sites
                    flipped ^= bernoulli(
                        self.request.p_m,
                        self.request.master_seed,
                        shot_id,
                        round_index,
                        ancilla_site_id,
                        EventType.MEASUREMENT_FLIP,
                    )
                    if flipped:
                        detection[shot_index, round_index, check_index] ^= 1
                        detection[shot_index, round_index + 1, check_index] ^= 1

                machine.reveal_losses()
                requested = machine.decide_and_request(round_index)
                for site_id in requested:
                    requests[shot_index, round_index, site_id] = 1

            observables[shot_index, 0] = logical

        decoded: DecodeResult = self.decoder.decode(detection, erasure, reloads)
        logical_failure = np.bitwise_xor(
            decoded.prediction[:, 0], observables[:, 0]
        ).astype(np.uint8)
        return SimulationBatch(
            shot_id=shot_ids,
            detection_events=detection,
            syndrome_valid_mask=validity,
            missing_mask=missing,
            erasure_mask=erasure,
            loss_mask=losses,
            reload_request_mask=requests,
            reload_mask=reloads,
            reload_failure_mask=failures,
            reload_reset_fault_mask=reset_faults,
            logical_observable=observables,
            decoder_prediction=decoded.prediction,
            logical_failure=logical_failure,
            catastrophic_loss=decoded.catastrophic_loss,
            distinct_graphs=decoded.distinct_graphs,
        )
