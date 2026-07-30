"""Strict configuration and result schemas for ceffflow cells."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChannelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["identity", "erasure", "confusion"]
    parameter: float = 0.0

    @model_validator(mode="after")
    def validate_domain(self) -> "ChannelSpec":
        parameter = float(self.parameter)
        if self.kind == "identity" and parameter != 0.0:
            raise ValueError("identity channel parameter must be zero")
        if self.kind == "erasure" and not 0.0 <= parameter <= 1.0:
            raise ValueError("erasure retain probability must lie in [0, 1]")
        if self.kind == "confusion" and not 0.0 <= parameter <= 0.5:
            raise ValueError("confusion error probability must lie in [0, 1/2]")
        return self


class CellConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: Literal["clean_ising", "nishimori", "self_dual"]
    lengths: list[int] = Field(min_length=3)
    channel: ChannelSpec
    steps: int = Field(gt=0)
    burn_in: int = Field(ge=0)
    block_size: int = Field(gt=0)
    seed: int = Field(ge=0)
    particles: int = Field(default=256, gt=0)

    @model_validator(mode="after")
    def validate_grid(self) -> "CellConfig":
        if len(set(self.lengths)) != len(self.lengths):
            raise ValueError("lengths must be unique")
        if any(length < 2 for length in self.lengths):
            raise ValueError("all lengths must be at least two")
        if self.steps % self.block_size:
            raise ValueError("steps must be a multiple of block_size")
        if self.model == "nishimori" and self.channel.kind != "identity":
            raise ValueError(
                "Nishimori is a calibration model and only supports identity"
            )
        return self


class CellManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    status: Literal["success", "failed"]
    cell_id: str = Field(min_length=1)
    settings: CellConfig
    provenance: dict[str, str]
    normalization_ok: bool
    finite_blocks: bool
    blocks_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    error: str | None = None
