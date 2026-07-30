"""Versioned certificate schemas."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import json

from pydantic import BaseModel, ConfigDict, Field

from . import MODEL_ID
from .intervals import DecimalInterval

SCHEMA_VERSION = "1.0"


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generator: str
    python_version: str
    numpy_version: str
    cvxpy_version: str
    solver: str
    git_commit: str


class RationalValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    numerator: int
    denominator: int = Field(gt=0)


class AndersonProof(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sites: int = Field(ge=2)
    eigenvalue_lower: RationalValue


class RationalBlockProof(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sites: int = Field(ge=2)
    vector: list[int] = Field(min_length=4)


class RationalSparseBlockProof(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sites: int = Field(ge=2)
    indices: list[int] = Field(min_length=1)
    values: list[int] = Field(min_length=1)


class RationalMPSBlockProof(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sites: int = Field(ge=2)
    bond_dimension: int = Field(ge=1)
    tensor_values: list[int]
    left_boundary: list[int]
    right_boundary: list[int]


class LTIDualProof(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sites: int = Field(ge=2)
    denominator: int = Field(gt=0)
    y_numerator: int
    matrix_numerators: list[int]


class RGDualProof(BaseModel):
    model_config = ConfigDict(extra="forbid")

    depth: int = Field(ge=4)
    bond_dimension: int = Field(ge=1)
    tensor_denominator: int = Field(gt=0)
    tensor_numerators: list[int]
    dual_denominator: int = Field(gt=0)
    y_numerator: int
    matrix_numerators: list[list[int]]


class U1LTIDualProof(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sites: int = Field(ge=2)
    denominator: int = Field(gt=0)
    y_numerator: int
    sector_matrix_numerators: list[list[int]]


class LevelCertificate(BaseModel):
    """A self-contained baseline two-sided certificate.

    Raw numerical candidates are informational. Certified endpoints identify
    analytic constructions that the verifier independently recomputes.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    model_id: str = MODEL_ID
    delta: Decimal
    level: int = Field(ge=2)
    block_size: int = Field(ge=2)
    raw_lti_lower: Decimal
    raw_block_upper: Decimal
    certified_lower: Decimal
    certified_upper: Decimal
    lower_method: str = "local-term-spectrum"
    upper_method: str = "polarized-or-neel-product"
    anderson_proof: AndersonProof | None = None
    rational_block_proof: RationalBlockProof | None = None
    rational_sparse_block_proof: RationalSparseBlockProof | None = None
    rational_mps_block_proof: RationalMPSBlockProof | None = None
    lti_dual_proof: LTIDualProof | None = None
    rg_dual_proof: RGDualProof | None = None
    u1_lti_dual_proof: U1LTIDualProof | None = None
    bethe: DecimalInterval
    provenance: Provenance

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def read(cls, path: Path) -> "LevelCertificate":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
