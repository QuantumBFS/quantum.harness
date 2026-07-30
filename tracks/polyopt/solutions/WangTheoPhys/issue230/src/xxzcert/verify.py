"""Independent verification of frozen baseline certificates."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from . import MODEL_ID
from .bethe import bethe_interval
from .certify import analytic_local_lower, analytic_product_upper
from .rational import (
    AndersonWitness,
    LTIDualWitness,
    exact_block_product_energy,
    exact_sparse_block_product_energy,
    exact_mps_block_product_energy,
    verify_anderson_witness,
    verify_lti_dual_witness,
)
from .rg_rational import RGDualWitness, verify_rg_dual_witness
from .lti_u1_rational import (
    U1LTIDualWitness,
    verify_u1_lti_dual_witness,
)
from .schema import LevelCertificate, SCHEMA_VERSION


@dataclass(frozen=True)
class VerificationReport:
    ok: bool
    errors: tuple[str, ...] = field(default_factory=tuple)


def verify_level(path: Path) -> VerificationReport:
    errors: list[str] = []
    try:
        certificate = LevelCertificate.read(path)
    except Exception as exc:
        return VerificationReport(False, (f"schema: {exc}",))
    if certificate.schema_version != SCHEMA_VERSION:
        errors.append("unsupported schema version")
    if certificate.model_id != MODEL_ID:
        errors.append("model identifier mismatch")
    delta_fraction = Fraction(certificate.delta)
    if certificate.lower_method == "u1-lti-rational-dual":
        proof = certificate.u1_lti_dual_proof
        if proof is None:
            errors.append("missing U(1) LTI dual proof")
        else:
            witness = U1LTIDualWitness(
                sites=proof.sites,
                denominator=proof.denominator,
                y_numerator=proof.y_numerator,
                sector_matrix_numerators=tuple(
                    tuple(matrix) for matrix in proof.sector_matrix_numerators
                ),
            )
            try:
                feasible = verify_u1_lti_dual_witness(delta_fraction, witness)
            except Exception as exc:
                errors.append(f"U(1) LTI dual proof malformed: {exc}")
            else:
                if not feasible:
                    errors.append("U(1) LTI dual slack is not positive definite")
                if Fraction(certificate.certified_lower) > witness.energy_density_lower:
                    errors.append("certified lower rounds inside its exact U(1) witness")
    elif certificate.lower_method == "rg-lti-rational-dual":
        proof = certificate.rg_dual_proof
        if proof is None:
            errors.append("missing RG dual proof")
        else:
            witness = RGDualWitness(
                depth=proof.depth,
                bond_dimension=proof.bond_dimension,
                tensor_denominator=proof.tensor_denominator,
                tensor_numerators=tuple(proof.tensor_numerators),
                dual_denominator=proof.dual_denominator,
                y_numerator=proof.y_numerator,
                matrix_numerators=tuple(
                    tuple(matrix) for matrix in proof.matrix_numerators
                ),
            )
            try:
                feasible = verify_rg_dual_witness(delta_fraction, witness)
            except Exception as exc:
                errors.append(f"RG dual proof malformed: {exc}")
            else:
                if not feasible:
                    errors.append("RG dual slack is not positive definite")
                if Fraction(certificate.certified_lower) > witness.energy_density_lower:
                    errors.append("certified lower rounds inside its exact RG witness")
    elif certificate.lower_method == "lti-rational-dual":
        proof = certificate.lti_dual_proof
        if proof is None:
            errors.append("missing LTI dual proof")
        else:
            witness = LTIDualWitness(
                sites=proof.sites,
                denominator=proof.denominator,
                y_numerator=proof.y_numerator,
                matrix_numerators=tuple(proof.matrix_numerators),
            )
            try:
                feasible = verify_lti_dual_witness(delta_fraction, witness)
            except Exception as exc:
                errors.append(f"LTI dual proof malformed: {exc}")
            else:
                if not feasible:
                    errors.append("LTI dual slack is not positive definite")
                if Fraction(certificate.certified_lower) > witness.energy_density_lower:
                    errors.append("certified lower rounds inside its exact dual witness")
    elif certificate.lower_method == "anderson-rational-ldl":
        proof = certificate.anderson_proof
        if proof is None:
            errors.append("missing Anderson proof")
        else:
            eigenvalue = Fraction(
                proof.eigenvalue_lower.numerator,
                proof.eigenvalue_lower.denominator,
            )
            witness = AndersonWitness(proof.sites, eigenvalue)
            if not verify_anderson_witness(delta_fraction, witness):
                errors.append("Anderson LDL proof is not positive definite")
            exact_lower = witness.energy_density_lower
            if Fraction(certificate.certified_lower) > exact_lower:
                errors.append("certified lower rounds inside its exact witness")
    else:
        expected_lower = analytic_local_lower(certificate.delta)
        if certificate.certified_lower != expected_lower:
            errors.append("certified lower endpoint does not match its construction")
    if certificate.upper_method == "rational-mps-repeated-block":
        proof = certificate.rational_mps_block_proof
        if proof is None:
            errors.append("missing rational MPS block proof")
        else:
            try:
                exact_upper = exact_mps_block_product_energy(
                    delta_fraction,
                    proof.sites,
                    proof.bond_dimension,
                    tuple(proof.tensor_values),
                    tuple(proof.left_boundary),
                    tuple(proof.right_boundary),
                )
            except Exception as exc:
                errors.append(f"MPS block proof malformed: {exc}")
            else:
                if Fraction(certificate.certified_upper) < exact_upper:
                    errors.append("certified upper rounds inside MPS witness")
    elif certificate.upper_method == "rational-sparse-repeated-block":
        proof = certificate.rational_sparse_block_proof
        if proof is None:
            errors.append("missing rational sparse block proof")
        else:
            try:
                exact_upper = exact_sparse_block_product_energy(
                    delta_fraction,
                    proof.sites,
                    tuple(proof.indices),
                    tuple(proof.values),
                )
            except Exception as exc:
                errors.append(f"sparse block proof malformed: {exc}")
            else:
                if Fraction(certificate.certified_upper) < exact_upper:
                    errors.append("certified upper rounds inside sparse witness")
    elif certificate.upper_method == "rational-repeated-block":
        proof = certificate.rational_block_proof
        if proof is None:
            errors.append("missing rational block proof")
        elif len(proof.vector) != 1 << proof.sites:
            errors.append("rational block vector dimension mismatch")
        else:
            exact_upper = exact_block_product_energy(
                delta_fraction, tuple(proof.vector)
            )
            if Fraction(certificate.certified_upper) < exact_upper:
                errors.append("certified upper rounds inside its exact witness")
    else:
        expected_upper = analytic_product_upper(certificate.delta)
        if certificate.certified_upper != expected_upper:
            errors.append("certified upper endpoint does not match its construction")
    try:
        reference = bethe_interval(str(certificate.delta))
    except Exception as exc:
        errors.append(f"reference: {exc}")
    else:
        if certificate.bethe != reference:
            errors.append("stored Bethe interval does not match independent evaluation")
        if not (
            certificate.certified_lower
            <= reference.lower
            <= reference.upper
            <= certificate.certified_upper
        ):
            errors.append("certified interval does not contain Bethe interval")
    # Raw candidates are not proof endpoints, but impossible orientation is an
    # important corruption/alarm check.
    raw_tolerance = Decimal("1e-7")
    if certificate.raw_lti_lower > certificate.bethe.upper + raw_tolerance:
        errors.append("raw lower candidate excludes Bethe interval")
    if certificate.raw_block_upper < certificate.bethe.lower - raw_tolerance:
        errors.append("raw upper candidate excludes Bethe interval")
    return VerificationReport(not errors, tuple(errors))
