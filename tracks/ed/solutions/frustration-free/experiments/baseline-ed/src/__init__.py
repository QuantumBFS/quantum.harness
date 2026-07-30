"""Reusable Rice-Mele exact-diagonalization components."""

from .diagonalization import DiagonalizationResult, diagonalize_full
from .model import RiceMeleModel

__all__ = ["DiagonalizationResult", "RiceMeleModel", "diagonalize_full"]
