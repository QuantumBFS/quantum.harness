"""Canonical schema-v2 artifacts for sparse Ky Fan structures."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import tempfile

from challenge233.sdp.algebra import (
    GaussianRational,
    PauliPolynomial,
    PauliWord,
    canonical_relation_table_json,
)
from challenge233.sdp.constrained_trace import periodic_blockade_dimension
from challenge233.sdp.kyfan import (
    CliqueImage,
    ComplexLinearForm,
    LinearEquality,
    MagnitudeWitness,
    MomentVariable,
    RationalLinearForm,
)
from challenge233.sdp.kyfan_sparse import (
    KyFanInstance,
    KyFanStructure,
    SparseComplexPSDBlock,
)
from challenge233.sdp.localizers import SafeWord


STRUCTURE_SOURCE_PATHS = (
    "src/challenge233/sdp/algebra.py",
    "src/challenge233/sdp/constraints.py",
    "src/challenge233/sdp/localizers.py",
    "src/challenge233/sdp/constrained_trace.py",
    "src/challenge233/sdp/hierarchy.py",
    "src/challenge233/sdp/kyfan.py",
    "src/challenge233/sdp/kyfan_sparse.py",
    "src/challenge233/sdp/kyfan_v2_artifact.py",
    "src/challenge233/sdp/verify_kyfan_problem.py",
    "src/challenge233/sdp/verify_kyfan_structure.py",
)


@dataclass(frozen=True)
class StructureBinding:
    directory: Path
    structure_path: Path
    structure_sha256: str
    structure_manifest_path: Path
    structure_manifest_sha256: str


@dataclass(frozen=True)
class ReductionBinding:
    directory: Path
    reduction_path: Path
    reduction_sha256: str
    reduction_manifest_path: Path
    reduction_manifest_sha256: str
    structure_sha256: str


def _fraction_text(value: Fraction) -> str:
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _encode_gaussian(value: GaussianRational) -> dict:
    return {
        "real": _fraction_text(value.real),
        "imag": _fraction_text(value.imag),
    }


def _encode_word(word: PauliWord) -> list:
    return [[site, label] for site, label in word.factors]


def _encode_safe_word(word: SafeWord) -> list:
    return [[site, label] for site, label in word.factors]


def _encode_polynomial(polynomial: PauliPolynomial) -> list:
    return [
        {
            "word": _encode_word(word),
            "coefficient": _encode_gaussian(coefficient),
        }
        for word, coefficient in polynomial.terms
    ]


def _encode_form(form: RationalLinearForm) -> dict:
    return {
        "constant": _fraction_text(form.constant),
        "terms": [
            [variable, _fraction_text(coefficient)]
            for variable, coefficient in form.terms
        ],
    }


def _encode_complex_form(form: ComplexLinearForm) -> dict:
    return {
        "real": _encode_form(form.real),
        "imag": _encode_form(form.imag),
    }


def _encode_variable(variable: MomentVariable) -> dict:
    return {
        "index": variable.index,
        "representative": _encode_word(variable.representative),
        "orbit": [_encode_word(word) for word in variable.orbit],
    }


def _encode_equality(row: LinearEquality) -> dict:
    return {
        "identifier": row.identifier,
        "form": _encode_form(row.form),
        "provenance": _json_value(row.provenance),
    }


def _encode_sparse_block(block: SparseComplexPSDBlock) -> dict:
    return {
        "identifier": block.identifier,
        "dimension": block.dimension,
        "upper_entries": [
            {
                "row": entry.row,
                "column": entry.column,
                "form": _encode_complex_form(entry.form),
            }
            for entry in block.upper_entries
        ],
        "provenance": _json_value(block.provenance),
    }


def _encode_witness(witness: MagnitudeWitness) -> dict:
    return {
        "variable": witness.variable,
        "block": witness.block,
        "row": witness.row,
        "column": witness.column,
        "phase": _encode_gaussian(witness.phase),
        "bound": _fraction_text(witness.bound),
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


def _json_value(value):
    if isinstance(value, Fraction):
        return _fraction_text(value)
    if isinstance(value, GaussianRational):
        return _encode_gaussian(value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {
            str(key): _json_value(item)
            for key, item in sorted(
                value.items(),
                key=lambda pair: str(pair[0]),
            )
        }
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(
        f"value is not canonically JSON encodable: {type(value).__name__}"
    )


def canonical_json_bytes(payload) -> bytes:
    """Return the unique human-readable JSON encoding used by schema v2."""
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _trace_table(structure: KyFanStructure) -> list:
    rows = [
        {
            "polynomial": _encode_polynomial(polynomial),
            "value": _encode_gaussian(value),
        }
        for polynomial, value in structure.constrained_trace_table
    ]
    return sorted(
        rows,
        key=lambda row: canonical_json_bytes(row),
    )


def _blockade_action_table(structure: KyFanStructure) -> dict:
    return {
        "state_encoding": "bit i is site i; 0=down, 1=up",
        "periodic_constraint": "n_i n_{i+1}=0 including wrap bond",
        "periodic_legal_state_count": (
            periodic_blockade_dimension(structure.size)
        ),
        "local_projectors": {
            "P": [
                {"input": 0, "value": "1/1"},
                {"input": 1, "value": "0/1"},
            ],
            "n": [
                {"input": 0, "value": "0/1"},
                {"input": 1, "value": "1/1"},
            ],
            "Z": [
                {"input": 0, "value": "-1/1"},
                {"input": 1, "value": "1/1"},
            ],
        },
        "local_pauli_action": [
            {
                "label": label,
                "input": bit,
                "output": output,
                "phase": {"real": real, "imag": imag},
            }
            for label, bit, output, real, imag in (
                ("X", 0, 1, "1/1", "0/1"),
                ("X", 1, 0, "1/1", "0/1"),
                ("Y", 0, 1, "0/1", "-1/1"),
                ("Y", 1, 0, "0/1", "1/1"),
                ("Z", 0, 0, "-1/1", "0/1"),
                ("Z", 1, 1, "1/1", "0/1"),
            )
        ],
    }


def structure_payload(structure: KyFanStructure) -> dict:
    """Encode detuning-independent logical data as schema-v2 JSON."""
    if not isinstance(structure, KyFanStructure):
        raise TypeError("structure must be a KyFanStructure")
    return {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-effect-moment-structure",
        "size": structure.size,
        "hierarchy": structure.hierarchy,
        "localizer_mode": structure.localizer_mode,
        "moment_basis": [
            _encode_word(word) for word in structure.moment_basis
        ],
        "safe_basis": [
            _encode_safe_word(word) for word in structure.safe_basis
        ],
        "variables": [
            _encode_variable(variable)
            for variable in structure.variables
        ],
        "objective_components": {
            identifier: _encode_form(form)
            for identifier, form in sorted(
                structure.objective_components.items()
            )
        },
        "equalities": [
            _encode_equality(row) for row in structure.equalities
        ],
        "psd_blocks": [
            _encode_sparse_block(block)
            for block in structure.psd_blocks
        ],
        "magnitude_witnesses": [
            _encode_witness(witness)
            for witness in structure.magnitude_witnesses
        ],
        "clique_orbits": [
            [list(image) for image in orbit]
            for orbit in structure.clique_orbits
        ],
        "clique_images": [
            _encode_clique_image(image)
            for image in structure.clique_images
        ],
        "localizer_sites": list(structure.localizer_sites),
        "constrained_trace_table": _trace_table(structure),
        "blockade_action_table": _blockade_action_table(structure),
        "provenance": _json_value(structure.provenance),
        "statistics": _json_value(structure.statistics),
    }


def _sha256_text(value, component: str) -> str:
    value = str(value)
    if len(value) != 64 or any(
        character not in "0123456789abcdef"
        for character in value
    ):
        raise ValueError(
            f"{component} must be a lowercase SHA-256"
        )
    return value


def _trial_manifest_sha256(value):
    if value is None:
        return None
    if isinstance(value, str):
        return _sha256_text(value, "trial manifest hash")
    if isinstance(value, dict):
        for key in ("sha256", "trial_manifest_sha256"):
            if key in value:
                return _sha256_text(
                    value[key],
                    "trial manifest hash",
                )
    for attribute in (
        "manifest_sha256",
        "trial_manifest_sha256",
    ):
        if hasattr(value, attribute):
            return _sha256_text(
                getattr(value, attribute),
                "trial manifest hash",
            )
    raise TypeError(
        "trial_manifest must provide an exact manifest SHA-256"
    )


def instance_payload(
    instance: KyFanInstance,
    structure_sha256: str,
) -> dict:
    """Encode one exact detuning overlay bound to shared structure bytes."""
    if not isinstance(instance, KyFanInstance):
        raise TypeError("instance must be a KyFanInstance")
    structure_sha256 = _sha256_text(
        structure_sha256,
        "structure_sha256",
    )
    return {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-effect-moment-instance",
        "structure_sha256": structure_sha256,
        "detuning": _fraction_text(instance.detuning),
        "objective": _encode_form(instance.objective),
        "physical_contract": _json_value(instance.physical_contract),
        "trial_manifest_sha256": _trial_manifest_sha256(
            instance.trial_manifest
        ),
    }


def logical_structure_sha256(structure: KyFanStructure) -> str:
    return hashlib.sha256(
        canonical_json_bytes(structure_payload(structure))
    ).hexdigest()


def _source_hashes() -> dict:
    project_root = Path(__file__).resolve().parents[3]
    return {
        relative: hashlib.sha256(
            (project_root / relative).read_bytes()
        ).hexdigest()
        for relative in STRUCTURE_SOURCE_PATHS
    }


def _install_exact_bytes(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(
                f"refusing to replace content-addressed artifact: {path}"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary_path), str(path))
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def export_shared_structure(
    structure: KyFanStructure,
    shared_root,
) -> StructureBinding:
    """Install one content-addressed shared logical structure."""
    payload = structure_payload(structure)
    structure_bytes = canonical_json_bytes(payload)
    structure_sha256 = hashlib.sha256(structure_bytes).hexdigest()
    directory = (
        Path(shared_root)
        / "kyfan-structures"
        / structure_sha256
    )
    structure_path = directory / "structure.json"
    _install_exact_bytes(structure_path, structure_bytes)

    manifest = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-shared-structure",
        "structure_file": "structure.json",
        "structure_sha256": structure_sha256,
        "structure_bytes": len(structure_bytes),
        "relation_table_sha256": hashlib.sha256(
            canonical_relation_table_json().encode("utf-8")
        ).hexdigest(),
        "source_file_sha256": _source_hashes(),
    }
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_path = directory / "manifest.json"
    _install_exact_bytes(manifest_path, manifest_bytes)
    return StructureBinding(
        directory=directory,
        structure_path=structure_path,
        structure_sha256=structure_sha256,
        structure_manifest_path=manifest_path,
        structure_manifest_sha256=hashlib.sha256(
            manifest_bytes
        ).hexdigest(),
    )


def export_solver_reduction(
    reduction,
    structure_binding: StructureBinding,
) -> ReductionBinding:
    """Install one content-addressed structure-only solver reduction."""
    from challenge233.sdp.kyfan_presolve import (
        KyFanSolverReduction,
        solver_reduction_payload,
    )

    if not isinstance(reduction, KyFanSolverReduction):
        raise TypeError(
            "reduction must be a KyFanSolverReduction"
        )
    if not isinstance(structure_binding, StructureBinding):
        raise TypeError(
            "structure_binding must be a StructureBinding"
        )
    if reduction.structure_sha256 != (
        structure_binding.structure_sha256
    ):
        raise ValueError(
            "reduction and structure binding SHA-256 differ"
        )
    reduction_bytes = canonical_json_bytes(
        solver_reduction_payload(reduction)
    )
    reduction_sha256 = hashlib.sha256(
        reduction_bytes
    ).hexdigest()
    shared_root = structure_binding.directory.parents[1]
    directory = (
        shared_root
        / "kyfan-reductions"
        / reduction_sha256
    )
    reduction_path = directory / "solver-reduction.json"
    _install_exact_bytes(reduction_path, reduction_bytes)
    manifest = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-shared-solver-reduction",
        "reduction_file": "solver-reduction.json",
        "reduction_sha256": reduction_sha256,
        "reduction_bytes": len(reduction_bytes),
        "structure_reference": _relative_reference(
            directory,
            structure_binding.structure_path,
        ),
        "structure_sha256": structure_binding.structure_sha256,
        "structure_manifest_reference": _relative_reference(
            directory,
            structure_binding.structure_manifest_path,
        ),
        "structure_manifest_sha256": (
            structure_binding.structure_manifest_sha256
        ),
    }
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_path = directory / "manifest.json"
    _install_exact_bytes(manifest_path, manifest_bytes)
    return ReductionBinding(
        directory=directory,
        reduction_path=reduction_path,
        reduction_sha256=reduction_sha256,
        reduction_manifest_path=manifest_path,
        reduction_manifest_sha256=hashlib.sha256(
            manifest_bytes
        ).hexdigest(),
        structure_sha256=structure_binding.structure_sha256,
    )


def _relative_reference(source_directory: Path, target: Path) -> str:
    relative = Path(
        os.path.relpath(
            str(target.resolve()),
            str(source_directory.resolve()),
        )
    )
    if relative.is_absolute():
        raise ValueError("artifact reference must be relative")
    normalized = relative.as_posix()
    if normalized != Path(normalized).as_posix():
        raise ValueError("artifact reference is not normalized")
    return normalized


def export_kyfan_instance(
    instance: KyFanInstance,
    structure_binding: StructureBinding,
    problem_directory,
    reduction_binding: ReductionBinding | None = None,
) -> Path:
    """Write one cell overlay plus relative bindings to shared structure."""
    if not isinstance(structure_binding, StructureBinding):
        raise TypeError("structure_binding must be a StructureBinding")
    if reduction_binding is not None:
        if not isinstance(reduction_binding, ReductionBinding):
            raise TypeError(
                "reduction_binding must be a ReductionBinding"
            )
        if reduction_binding.structure_sha256 != (
            structure_binding.structure_sha256
        ):
            raise ValueError(
                "reduction and structure bindings differ"
            )
    problem_directory = Path(problem_directory)
    run_root = structure_binding.directory.parents[2].resolve()
    resolved_problem = problem_directory.resolve()
    if (
        resolved_problem != run_root
        and run_root not in resolved_problem.parents
    ):
        raise ValueError("problem directory must be inside the run directory")
    problem_directory.mkdir(parents=True, exist_ok=True)

    payload = instance_payload(
        instance,
        structure_binding.structure_sha256,
    )
    instance_bytes = canonical_json_bytes(payload)
    instance_path = problem_directory / "instance.json"
    _install_exact_bytes(instance_path, instance_bytes)

    manifest = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-instance-binding",
        "instance_file": "instance.json",
        "instance_sha256": hashlib.sha256(instance_bytes).hexdigest(),
        "structure_reference": _relative_reference(
            problem_directory,
            structure_binding.structure_path,
        ),
        "structure_sha256": structure_binding.structure_sha256,
        "structure_manifest_reference": _relative_reference(
            problem_directory,
            structure_binding.structure_manifest_path,
        ),
        "structure_manifest_sha256": (
            structure_binding.structure_manifest_sha256
        ),
    }
    if reduction_binding is not None:
        manifest.update(
            {
                "reduction_reference": _relative_reference(
                    problem_directory,
                    reduction_binding.reduction_path,
                ),
                "reduction_sha256": (
                    reduction_binding.reduction_sha256
                ),
                "reduction_manifest_reference": (
                    _relative_reference(
                        problem_directory,
                        reduction_binding.reduction_manifest_path,
                    )
                ),
                "reduction_manifest_sha256": (
                    reduction_binding.reduction_manifest_sha256
                ),
            }
        )
    _install_exact_bytes(
        problem_directory / "manifest.json",
        canonical_json_bytes(manifest),
    )
    return problem_directory
