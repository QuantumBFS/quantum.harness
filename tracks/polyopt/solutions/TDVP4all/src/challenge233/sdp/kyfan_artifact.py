"""Deterministic export of exact Ky Fan moment problems."""

from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from pathlib import Path

from challenge233.sdp.algebra import (
    GaussianRational,
    PauliWord,
    canonical_relation_table_json,
    canonicalize_word,
)
from challenge233.sdp.constrained_trace import constrained_pauli_trace
from challenge233.sdp.kyfan import (
    CliqueImage,
    ComplexLinearForm,
    ComplexPSDBlock,
    KyFanProblem,
    LinearEquality,
    MagnitudeWitness,
    MomentVariable,
    RationalLinearForm,
    RealPSDBlock,
)


def _encode_fraction(value: Fraction) -> str:
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _encode_gaussian(value: GaussianRational) -> dict:
    return {
        "real": _encode_fraction(value.real),
        "imag": _encode_fraction(value.imag),
    }


def _encode_word(word: PauliWord) -> list:
    return [[site, label] for site, label in word.factors]


def _encode_form(form: RationalLinearForm) -> dict:
    return {
        "constant": _encode_fraction(form.constant),
        "terms": [
            [variable, _encode_fraction(coefficient)]
            for variable, coefficient in form.terms
        ],
    }


def _encode_complex_form(form: ComplexLinearForm) -> dict:
    return {
        "real": _encode_form(form.real),
        "imag": _encode_form(form.imag),
    }


def _encode_equality(row: LinearEquality) -> dict:
    return {
        "identifier": row.identifier,
        "form": _encode_form(row.form),
        "provenance": dict(row.provenance),
    }


def _encode_real_block(block: RealPSDBlock) -> dict:
    return {
        "identifier": block.identifier,
        "dimension": block.dimension,
        "entries": [
            [_encode_form(entry) for entry in row]
            for row in block.entries
        ],
        "provenance": dict(block.provenance),
    }


def _encode_complex_block(block: ComplexPSDBlock) -> dict:
    return {
        "identifier": block.identifier,
        "dimension": block.dimension,
        "entries": [
            [_encode_complex_form(entry) for entry in row]
            for row in block.entries
        ],
        "provenance": dict(block.provenance),
    }


def _encode_variable(variable: MomentVariable) -> dict:
    return {
        "index": variable.index,
        "representative": _encode_word(variable.representative),
        "orbit": [_encode_word(word) for word in variable.orbit],
    }


def _encode_witness(witness: MagnitudeWitness) -> dict:
    return {
        "variable": witness.variable,
        "block": witness.block,
        "row": witness.row,
        "column": witness.column,
        "phase": _encode_gaussian(witness.phase),
        "bound": _encode_fraction(witness.bound),
    }


def _encode_clique_image(image: CliqueImage) -> dict:
    return {
        "shift": image.shift,
        "reflected": image.reflected,
        "sites": list(image.sites),
        "representative_blocks": list(image.representative_blocks),
        "row_permutation": list(image.row_permutation),
        "localizer_sites": list(image.localizer_sites),
    }


def _constrained_trace_table(problem: KyFanProblem) -> list:
    words = {
        canonicalize_word(left.factors + right.factors).word
        for left in problem.moment_basis
        for right in problem.moment_basis
    }
    return [
        {
            "word": _encode_word(word),
            "value": constrained_pauli_trace(problem.size, word),
        }
        for word in sorted(words)
    ]


def _json_bytes(value) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _problem_payload(problem: KyFanProblem) -> dict:
    return {
        "schema_version": 1,
        "purpose": "finite-N-ky-fan-effect-moment-problem",
        "size": problem.size,
        "detuning": _encode_fraction(problem.detuning),
        "hierarchy": problem.hierarchy,
        "localizer_mode": problem.localizer_mode,
        "moment_basis": [
            _encode_word(word) for word in problem.moment_basis
        ],
        "safe_basis": [
            [[site, label] for site, label in word.factors]
            for word in problem.safe_basis
        ],
        "variables": [
            _encode_variable(variable)
            for variable in problem.variables
        ],
        "objective": _encode_form(problem.objective),
        "equalities": [
            _encode_equality(row) for row in problem.equalities
        ],
        "psd_blocks": [
            _encode_real_block(block) for block in problem.psd_blocks
        ],
        "unrealified_psd_blocks": [
            _encode_complex_block(block)
            for block in problem.unrealified_psd_blocks
        ],
        "magnitude_witnesses": [
            _encode_witness(witness)
            for witness in problem.magnitude_witnesses
        ],
        "clique_orbits": [
            [list(image) for image in orbit]
            for orbit in problem.clique_orbits
        ],
        "clique_images": [
            _encode_clique_image(image)
            for image in problem.clique_images
        ],
        "localizer_sites": list(problem.localizer_sites),
        "constrained_trace_table": _constrained_trace_table(problem),
        "provenance": dict(problem.provenance),
        "statistics": dict(problem.statistics),
    }


def export_kyfan_problem(
    problem: KyFanProblem,
    output_directory,
) -> Path:
    """Write exact problem data plus a source-bound provenance manifest."""
    if not isinstance(problem, KyFanProblem):
        raise TypeError("problem must be a KyFanProblem")
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)

    problem_path = output_directory / "problem.json"
    problem_bytes = _json_bytes(_problem_payload(problem))
    problem_path.write_bytes(problem_bytes)

    project_root = Path(__file__).resolve().parents[3]
    source_paths = (
        "src/challenge233/sdp/algebra.py",
        "src/challenge233/sdp/constraints.py",
        "src/challenge233/sdp/localizers.py",
        "src/challenge233/sdp/constrained_trace.py",
        "src/challenge233/sdp/hierarchy.py",
        "src/challenge233/sdp/kyfan.py",
        "src/challenge233/sdp/kyfan_artifact.py",
        "src/challenge233/sdp/verify_kyfan_problem.py",
    )
    manifest = {
        "schema_version": 1,
        "purpose": "finite-N-ky-fan-effect-moment-problem",
        "boundary": "periodic",
        "local_state_convention": "0=down, 1=up",
        "symmetry": "D_N group-averaged effect, all physical sectors",
        "localizer_mode": problem.localizer_mode,
        "problem_file": problem_path.name,
        "problem_sha256": hashlib.sha256(problem_bytes).hexdigest(),
        "relation_table_sha256": hashlib.sha256(
            canonical_relation_table_json().encode("utf-8")
        ).hexdigest(),
        "source_file_sha256": {
            relative: hashlib.sha256(
                (project_root / relative).read_bytes()
            ).hexdigest()
            for relative in source_paths
        },
    }
    (output_directory / "manifest.json").write_bytes(
        _json_bytes(manifest)
    )
    return output_directory
