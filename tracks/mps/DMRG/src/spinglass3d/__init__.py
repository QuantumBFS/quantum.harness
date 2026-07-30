"""Validated contracts for the three-dimensional spin-glass workflow."""

from .config import EvidenceSpec, HardGoalDesign, ModelSpec, RGSpec, load_design

__all__ = [
    "EvidenceSpec",
    "HardGoalDesign",
    "ModelSpec",
    "RGSpec",
    "load_design",
]

__version__ = "0.1.0"
