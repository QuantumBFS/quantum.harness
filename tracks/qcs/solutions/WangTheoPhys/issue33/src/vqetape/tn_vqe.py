"""Exact direct tensor-network VQE energy and gradient builders."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import jax
import jax.numpy as jnp
from jax import Array
from jax.ad_checkpoint import checkpoint_policies

from vqetape.spec import (
    GateRepresentation,
    HamiltonianRepresentation,
    TFIMVQESpec,
)
from vqetape.tn_program import (
    ContractionProgram,
    PathStrategy,
    execute_contraction,
    execute_tree_contraction,
    plan_contraction,
    subtree_nodes_at_depth,
)
from vqetape.tn_template import (
    ProductPauliTerm,
    bind_mpo_tensors,
    bind_term_tensors,
    build_expectation_template,
    build_mpo_expectation_template,
)

RematPolicy = Literal[
    "none",
    "all",
    "output-ge-threshold",
    "term",
    "objective",
    "subtree",
    "named",
]
TensorEnergyFunction = Callable[[Array], Array]
TensorValueAndGradFunction = Callable[[Array], tuple[Array, Array]]


def tfim_product_terms(spec: TFIMVQESpec) -> tuple[ProductPauliTerm, ...]:
    """Return product-Pauli terms for the open-boundary TFIM."""

    terms: list[ProductPauliTerm] = []
    for wire in range(spec.nqubits - 1):
        operators = ["I"] * spec.nqubits
        operators[wire] = "Z"
        operators[wire + 1] = "Z"
        terms.append(
            ProductPauliTerm(
                coefficient=-spec.coupling,
                operators=tuple(operators),
            )
        )
    for wire in range(spec.nqubits):
        operators = ["I"] * spec.nqubits
        operators[wire] = "X"
        terms.append(
            ProductPauliTerm(
                coefficient=-spec.field,
                operators=tuple(operators),
            )
        )
    return tuple(terms)


def remat_steps_for_policy(
    program: ContractionProgram,
    policy: RematPolicy,
    threshold_bytes: int | None,
) -> frozenset[int]:
    """Resolve a symbolic tape policy to explicit contraction-step indices."""

    if policy in ("none", "term", "objective", "subtree", "named"):
        if threshold_bytes is not None:
            raise ValueError("threshold_bytes is only valid for threshold policy")
        return frozenset()
    if policy == "all":
        if threshold_bytes is not None:
            raise ValueError("threshold_bytes is only valid for threshold policy")
        return frozenset(range(len(program.steps)))
    if policy != "output-ge-threshold":
        raise ValueError(f"unsupported remat policy: {policy}")
    if threshold_bytes is None or threshold_bytes < 1:
        raise ValueError("threshold policy requires positive threshold_bytes")
    return frozenset(
        index
        for index, output_bytes in enumerate(program.step_output_bytes)
        if output_bytes >= threshold_bytes
    )


def build_tn_energy(
    spec: TFIMVQESpec,
    *,
    path_strategy: PathStrategy,
    remat_policy: RematPolicy,
    threshold_bytes: int | None = None,
    explicit_path: tuple[tuple[int, ...], ...] | None = None,
    subtree_depth: int | None = None,
    name_residuals: bool = False,
    save_names: tuple[str, ...] | None = None,
    gate_representation: GateRepresentation = "dense",
    hamiltonian_representation: HamiltonianRepresentation = "pauli_sum",
) -> tuple[TensorEnergyFunction, ContractionProgram, frozenset[int]]:
    """Build an exact direct scalar-contraction TFIM energy function."""

    if hamiltonian_representation not in ("pauli_sum", "mpo"):
        raise ValueError(
            "unsupported hamiltonian_representation: "
            f"{hamiltonian_representation}"
        )
    template = (
        build_expectation_template(
            spec,
            gate_representation=gate_representation,
        )
        if hamiltonian_representation == "pauli_sum"
        else build_mpo_expectation_template(
            spec,
            gate_representation=gate_representation,
        )
    )
    program = plan_contraction(
        template,
        path_strategy,
        explicit_path=explicit_path,
    )
    remat_steps = remat_steps_for_policy(
        program,
        remat_policy,
        threshold_bytes,
    )
    if remat_policy == "subtree":
        if subtree_depth is None or subtree_depth < 0:
            raise ValueError(
                "subtree policy requires nonnegative subtree_depth"
            )
        checkpoint_node_ids = frozenset(
            node.node_id
            for node in subtree_nodes_at_depth(program, subtree_depth)
        )
        if not checkpoint_node_ids:
            raise ValueError(
                f"no internal subtree nodes exist at depth {subtree_depth}"
            )
    else:
        if subtree_depth is not None:
            raise ValueError(
                "subtree_depth is only valid for subtree policy"
            )
        checkpoint_node_ids = frozenset()
    if remat_policy == "named":
        if save_names is None:
            raise ValueError("named policy requires save_names")
        allowed_names = {
            f"contract:{step_index}:elements{step.output_elements}:{component}"
            for step_index, step in enumerate(program.steps)
            for component in ("real", "imag")
        }
        unknown_names = set(save_names) - allowed_names
        if unknown_names:
            raise ValueError(
                "named tape contains values from another "
                f"contraction program: {sorted(unknown_names)}"
            )
        name_residuals = True
    elif save_names is not None:
        raise ValueError("save_names is only valid for named policy")
    terms = (
        tfim_product_terms(spec)
        if hamiltonian_representation == "pauli_sum"
        else ()
    )
    real_dtype = jnp.float32 if spec.dtype == "complex64" else jnp.float64

    def contract_tensors(tensors: tuple[Array, ...]) -> Array:
        return (
            execute_tree_contraction(
                program,
                tensors,
                checkpoint_node_ids=checkpoint_node_ids,
            )
            if remat_policy == "subtree"
            else execute_contraction(
                program,
                tensors,
                remat_steps=remat_steps,
                name_residuals=name_residuals,
            )
        )

    def pauli_sum_energy(theta: Array) -> Array:
        total = jnp.asarray(0.0, dtype=real_dtype)
        for term in terms:
            def contract_term(
                local_theta: Array,
                fixed_term: ProductPauliTerm = term,
            ) -> Array:
                tensors = bind_term_tensors(
                    template,
                    local_theta,
                    fixed_term,
                    name_residuals=name_residuals,
                )
                return contract_tensors(tensors)

            expectation = (
                jax.checkpoint(contract_term)(theta)
                if remat_policy == "term"
                else contract_term(theta)
            )
            total = total + term.coefficient * jnp.real(expectation)
        return total

    def mpo_energy(theta: Array) -> Array:
        def contract_mpo(local_theta: Array) -> Array:
            tensors = bind_mpo_tensors(
                template,
                local_theta,
                name_residuals=name_residuals,
            )
            return contract_tensors(tensors)

        expectation = (
            jax.checkpoint(contract_mpo)(theta)
            if remat_policy == "term"
            else contract_mpo(theta)
        )
        return jnp.asarray(jnp.real(expectation), dtype=real_dtype)

    raw_energy = (
        pauli_sum_energy
        if hamiltonian_representation == "pauli_sum"
        else mpo_energy
    )

    if remat_policy == "objective":
        energy = jax.checkpoint(raw_energy)
    elif remat_policy == "named":
        assert save_names is not None
        policy = checkpoint_policies.save_only_these_names(*save_names)
        energy = jax.checkpoint(raw_energy, policy=policy)
    else:
        energy = raw_energy
    remat_units = (
        checkpoint_node_ids
        if remat_policy == "subtree"
        else frozenset(save_names)
        if remat_policy == "named" and save_names is not None
        else remat_steps
    )
    return energy, program, remat_units


def build_tn_value_and_grad(
    spec: TFIMVQESpec,
    *,
    path_strategy: PathStrategy,
    remat_policy: RematPolicy,
    threshold_bytes: int | None = None,
    explicit_path: tuple[tuple[int, ...], ...] | None = None,
    subtree_depth: int | None = None,
    save_names: tuple[str, ...] | None = None,
    gate_representation: GateRepresentation = "dense",
    hamiltonian_representation: HamiltonianRepresentation = "pauli_sum",
) -> TensorValueAndGradFunction:
    """Build a JIT-compiled direct-TN value-and-full-gradient executable."""

    energy, _, _ = build_tn_energy(
        spec,
        path_strategy=path_strategy,
        remat_policy=remat_policy,
        threshold_bytes=threshold_bytes,
        explicit_path=explicit_path,
        subtree_depth=subtree_depth,
        save_names=save_names,
        gate_representation=gate_representation,
        hamiltonian_representation=hamiltonian_representation,
    )
    return jax.jit(jax.value_and_grad(energy))
