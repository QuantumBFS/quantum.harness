from functools import lru_cache
import importlib.util
from pathlib import Path


@lru_cache(maxsize=1)
def _trusted_basis_module():
    source = (
        Path(__file__).resolve().parents[3]
        / "external"
        / "1d-basis"
        / "pxpbasis.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_challenge233_external_pxpbasis",
        source,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load trusted basis source: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=None)
def build_constrained_basis(size: int):
    """Return the trusted periodic spin-1/2 blockade basis."""
    return _trusted_basis_module().constrained_basis(
        sps=2,
        N=size,
        kblock=None,
        pblock=None,
    )
