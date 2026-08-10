"""Construct conservative baseline certificates from raw candidates."""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, localcontext
from fractions import Fraction
import platform
import subprocess

import cvxpy
import numpy
import numpy as np

from .bethe import bethe_interval
from .lti import LTICandidate
from .model import finite_xxz
from .rational import (
    exact_block_product_energy,
    exact_sparse_block_product_energy,
    exact_mps_block_product_energy,
    make_anderson_witness,
    make_lti_dual_witness,
    rationalize_state,
    rationalize_sparse_state,
)
from .schema import (
    AndersonProof,
    LTIDualProof,
    LevelCertificate,
    Provenance,
    RGDualProof,
    RationalBlockProof,
    RationalSparseBlockProof,
    RationalMPSBlockProof,
    RationalValue,
    U1LTIDualProof,
)
from .rg_rational import RGDualWitness
from .lti_u1_rational import U1LTIDualWitness
from .upper import UpperCandidate


def analytic_local_lower(delta: Decimal) -> Decimal:
    """Minimum eigenvalue of one XXZ bond, a thermodynamic lower bound."""
    return min(delta / 4, -delta / 4 - Decimal("0.5"))


def analytic_product_upper(delta: Decimal) -> Decimal:
    """Energy of an explicit polarized or Néel product state."""
    if delta <= -1:
        return delta / 4
    return -delta / 4


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _fraction_decimal(value: Fraction, lower: bool, digits: int = 40) -> Decimal:
    with localcontext() as context:
        context.prec = digits
        context.rounding = ROUND_FLOOR if lower else ROUND_CEILING
        return Decimal(value.numerator) / Decimal(value.denominator)


def make_level_certificate(
    delta_text: str,
    lower: LTICandidate,
    upper: UpperCandidate,
    proof_level: int | None = None,
) -> LevelCertificate:
    delta = Decimal(delta_text)
    if Decimal(str(lower.delta)) != delta or Decimal(str(upper.delta)) != delta:
        raise ValueError("candidate delta does not match requested delta")
    delta_fraction = Fraction(delta)
    # Candidate selection is heuristic and untrusted; only the selected
    # witness is subsequently proved by exact rational LDL.
    if proof_level is None:
        proof_level = lower.level
    if proof_level < 2:
        raise ValueError("proof_level must be at least 2")
    selected_sites = max(
        range(2, proof_level + 1),
        key=lambda sites: float(
            np.linalg.eigvalsh(
                finite_xxz(float(delta), sites, periodic=False).real
            )[0]
        )
        / (sites - 1),
    )
    anderson = make_anderson_witness(delta_fraction, selected_sites)
    dual = make_lti_dual_witness(
        delta_fraction,
        lower.level,
        lower.dual_trace,
        lower.dual_lti,
    )
    vector = rationalize_state(upper.state)
    exact_upper = exact_block_product_energy(delta_fraction, vector)
    analytic_lower_fraction = Fraction(analytic_local_lower(delta))
    analytic_upper_fraction = Fraction(analytic_product_upper(delta))
    lower_options = {
        "local-term-spectrum": analytic_lower_fraction,
        "anderson-rational-ldl": anderson.energy_density_lower,
        "lti-rational-dual": dual.energy_density_lower,
    }
    lower_method = max(lower_options, key=lower_options.get)
    certified_lower_fraction = lower_options[lower_method]
    use_block = exact_upper < analytic_upper_fraction
    fields = dict(
        delta=delta,
        level=proof_level,
        block_size=upper.sites,
        raw_lti_lower=Decimal(str(lower.raw_lower)),
        raw_block_upper=Decimal(str(upper.raw_upper)),
        certified_lower=_fraction_decimal(certified_lower_fraction, lower=True),
        certified_upper=(
            _fraction_decimal(exact_upper, lower=False)
            if use_block
            else analytic_product_upper(delta)
        ),
        lower_method=lower_method,
        upper_method=(
            "rational-repeated-block"
            if use_block
            else "polarized-or-neel-product"
        ),
        anderson_proof=(
            AndersonProof(
                sites=anderson.sites,
                eigenvalue_lower=RationalValue(
                    numerator=anderson.eigenvalue_lower.numerator,
                    denominator=anderson.eigenvalue_lower.denominator,
                ),
            )
            if lower_method == "anderson-rational-ldl"
            else None
        ),
        lti_dual_proof=(
            LTIDualProof(
                sites=dual.sites,
                denominator=dual.denominator,
                y_numerator=dual.y_numerator,
                matrix_numerators=list(dual.matrix_numerators),
            )
            if lower_method == "lti-rational-dual"
            else None
        ),
        rational_block_proof=(
            RationalBlockProof(sites=upper.sites, vector=list(vector))
            if use_block
            else None
        ),
        bethe=bethe_interval(delta_text),
        provenance=Provenance(
            generator="xxzcert",
            python_version=platform.python_version(),
            numpy_version=numpy.__version__,
            cvxpy_version=cvxpy.__version__,
            solver=lower.solver,
            git_commit=_git_commit(),
        ),
    )
    return LevelCertificate(**fields)


def attach_rg_dual_proof(
    certificate: LevelCertificate,
    witness: RGDualWitness,
    raw_lower: float,
) -> LevelCertificate:
    """Return a certificate upgraded by a stronger exact RG dual witness."""
    if certificate.delta != Decimal("1"):
        raise ValueError("the initial RG witness implementation supports XXX")
    rg_lower = _fraction_decimal(witness.energy_density_lower, lower=True)
    if rg_lower <= certificate.certified_lower:
        raise ValueError("RG witness does not improve the certified lower endpoint")
    proof = RGDualProof(
        depth=witness.depth,
        bond_dimension=witness.bond_dimension,
        tensor_denominator=witness.tensor_denominator,
        tensor_numerators=list(witness.tensor_numerators),
        dual_denominator=witness.dual_denominator,
        y_numerator=witness.y_numerator,
        matrix_numerators=[
            list(matrix) for matrix in witness.matrix_numerators
        ],
    )
    return certificate.model_copy(
        update={
            "level": witness.depth,
            "raw_lti_lower": Decimal(str(raw_lower)),
            "certified_lower": rg_lower,
            "lower_method": "rg-lti-rational-dual",
            "anderson_proof": None,
            "lti_dual_proof": None,
            "rg_dual_proof": proof,
            "provenance": certificate.provenance.model_copy(
                update={"solver": "CVXOPT"}
            ),
        }
    )


def attach_u1_lti_dual_proof(
    certificate: LevelCertificate,
    witness: U1LTIDualWitness,
    raw_lower: float,
) -> LevelCertificate:
    """Return a certificate upgraded by a U(1)-blocked exact LTI dual."""
    lower = _fraction_decimal(witness.energy_density_lower, lower=True)
    if lower <= certificate.certified_lower:
        raise ValueError("U(1) LTI witness does not improve the lower endpoint")
    proof = U1LTIDualProof(
        sites=witness.sites,
        denominator=witness.denominator,
        y_numerator=witness.y_numerator,
        sector_matrix_numerators=[
            list(matrix) for matrix in witness.sector_matrix_numerators
        ],
    )
    return certificate.model_copy(
        update={
            "level": witness.sites,
            "raw_lti_lower": Decimal(str(raw_lower)),
            "certified_lower": lower,
            "lower_method": "u1-lti-rational-dual",
            "anderson_proof": None,
            "lti_dual_proof": None,
            "rg_dual_proof": None,
            "u1_lti_dual_proof": proof,
            "provenance": certificate.provenance.model_copy(
                update={"solver": "SCS"}
            ),
        }
    )


def attach_sparse_block_upper(
    certificate: LevelCertificate,
    upper: UpperCandidate,
) -> LevelCertificate:
    """Upgrade a certificate with an exact sparse repeated-block state."""
    if Decimal(str(upper.delta)) != certificate.delta:
        raise ValueError("upper candidate delta mismatch")
    indices, values = rationalize_sparse_state(upper.state)
    exact = exact_sparse_block_product_energy(
        Fraction(certificate.delta),
        upper.sites,
        indices,
        values,
    )
    endpoint = _fraction_decimal(exact, lower=False)
    if endpoint >= certificate.certified_upper:
        raise ValueError("sparse block does not improve the upper endpoint")
    return certificate.model_copy(
        update={
            "block_size": upper.sites,
            "raw_block_upper": Decimal(str(upper.raw_upper)),
            "certified_upper": endpoint,
            "upper_method": "rational-sparse-repeated-block",
            "rational_block_proof": None,
            "rational_sparse_block_proof": RationalSparseBlockProof(
                sites=upper.sites,
                indices=list(indices),
                values=list(values),
            ),
        }
    )


def attach_rational_mps_block_upper(
    certificate: LevelCertificate,
    tensor: np.ndarray,
    sites: int,
    *,
    scale: int = 10**6,
    left_index: int = 0,
    right_index: int = 0,
) -> LevelCertificate:
    """Upgrade a certificate with a compact exact OBC-MPS block."""
    array = np.asarray(tensor)
    if array.ndim != 3 or array.shape[0] != array.shape[2] or array.shape[1] != 2:
        raise ValueError("MPS tensor must have shape (D,2,D)")
    if np.max(np.abs(array.imag)) > 1e-9:
        raise ValueError("compact rational MPS currently supports real tensors")
    bond = array.shape[0]
    if not (0 <= left_index < bond and 0 <= right_index < bond):
        raise ValueError("MPS boundary index out of range")
    values = tuple(
        int(round(float(value) * scale)) for value in array.real.reshape(-1)
    )
    left = tuple(1 if index == left_index else 0 for index in range(bond))
    right = tuple(1 if index == right_index else 0 for index in range(bond))
    exact = exact_mps_block_product_energy(
        Fraction(certificate.delta), sites, bond, values, left, right
    )
    endpoint = _fraction_decimal(exact, lower=False)
    if endpoint >= certificate.certified_upper:
        raise ValueError("rational MPS block does not improve the upper endpoint")
    return certificate.model_copy(
        update={
            "block_size": sites,
            "raw_block_upper": endpoint,
            "certified_upper": endpoint,
            "upper_method": "rational-mps-repeated-block",
            "rational_block_proof": None,
            "rational_sparse_block_proof": None,
            "rational_mps_block_proof": RationalMPSBlockProof(
                sites=sites,
                bond_dimension=bond,
                tensor_values=list(values),
                left_boundary=list(left),
                right_boundary=list(right),
            ),
        }
    )
