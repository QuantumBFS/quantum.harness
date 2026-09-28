"""Pure helpers for the optional TeNPy high-temperature dynamics backend.

This module deliberately does not import TeNPy.  Manifest selection, initial
state construction, numerical-grid checks, provenance hashing, and the
pre-unblinding guard can therefore be unit tested in the lightweight analysis
environment.  The executable backend imports TeNPy only after these checks
pass.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .research_dataset import initial_profile, normalized_field


Array = np.ndarray
SUPPORTED_TEMPERATURES = {"infinite"}
SUPPORTED_BOUNDARY_CONDITIONS = {"open"}
SUPPORTED_OBSERVABLES = {
    "magnetization",
    "local_spin_current",
    "czz",
    "fcs_logZ",
}


def uses_grouped_backend(
    condition: Mapping[str, Any],
    *,
    force_grouped: bool = False,
) -> bool:
    """Return whether a physical condition needs the range-two layout."""

    j2 = float(condition.get("j2", 0.0))
    if not np.isfinite(j2):
        raise ValueError("J2 must be finite")
    return bool(force_grouped or abs(j2) > 1e-15)


def interleave_grouped_values(component0: Array, component1: Array) -> Array:
    """Map two grouped-site components back to physical-site order."""

    component0 = np.asarray(component0)
    component1 = np.asarray(component1)
    if component0.shape != component1.shape:
        raise ValueError("Grouped components must have identical shapes")
    result = np.empty(
        component0.shape[:-1] + (2 * component0.shape[-1],),
        dtype=np.result_type(component0, component1),
    )
    result[..., 0::2] = component0
    result[..., 1::2] = component1
    return result


def assemble_range2_cut_current(
    *,
    intra_nn: Array,
    inter_nn: Array,
    nnn_00: Array,
    nnn_11: Array,
) -> Array:
    """Return total current through each physical cut of a grouped chain.

    ``intra_nn`` lives on the physical cut inside each group.  The other
    arrays live between neighboring groups.  Each returned cut contains every
    range-one or range-two Hamiltonian bond crossing that cut.
    """

    intra_nn = np.asarray(intra_nn)
    inter_nn = np.asarray(inter_nn)
    nnn_00 = np.asarray(nnn_00)
    nnn_11 = np.asarray(nnn_11)
    if intra_nn.ndim < 1:
        raise ValueError("intra_nn must have a grouped-site axis")
    groups = intra_nn.shape[-1]
    expected_inter_shape = intra_nn.shape[:-1] + (max(groups - 1, 0),)
    if (
        inter_nn.shape != expected_inter_shape
        or nnn_00.shape != expected_inter_shape
        or nnn_11.shape != expected_inter_shape
    ):
        raise ValueError(
            "inter_nn, nnn_00, and nnn_11 must have G-1 values "
            "with the same leading shape as intra_nn"
        )
    result = np.zeros(
        intra_nn.shape[:-1] + (max(2 * groups - 1, 0),),
        dtype=np.result_type(intra_nn, inter_nn, nnn_00, nnn_11),
    )
    if groups == 0:
        return result
    result[..., 0::2] = intra_nn
    if groups > 1:
        result[..., 0] += nnn_00[..., 0]
        result[..., -1] += nnn_11[..., -1]
        result[..., 2:-1:2] += nnn_11[..., :-1] + nnn_00[..., 1:]
        result[..., 1::2] = inter_nn + nnn_00 + nnn_11
    return result


def grouped_counting_mask(length: int) -> Array:
    """Return right-half charge membership for both spins in each group."""

    length = int(length)
    if length < 2 or length % 2:
        raise ValueError("Grouped physical length must be positive and even")
    physical = np.arange(length, dtype=int).reshape(length // 2, 2)
    return physical >= length // 2


def load_manifest_job(
    manifest_path: str | Path,
    job_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the full manifest and one uniquely identified job."""

    path = Path(manifest_path)
    manifest = json.loads(path.read_text())
    matches = [
        dict(job)
        for job in manifest.get("jobs", [])
        if str(job.get("job_id")) == str(job_id)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one manifest job {job_id!r}; found {len(matches)}"
        )
    return manifest, matches[0]


def require_job_authorized(
    job: Mapping[str, Any],
    *,
    unblinding_record: str | Path,
) -> None:
    """Reject blinded production-B execution until the one-time record exists."""

    if str(job.get("stage")) != "production_b":
        return
    record = Path(unblinding_record)
    if not record.is_file():
        raise PermissionError(
            "Production-B remains blinded. Create the registered unblinding "
            f"record before running {job.get('job_id')}: {record}"
        )
    raw = json.loads(record.read_text())
    if int(raw.get("schema_version", -1)) != 1 or "analysis_sha256" not in raw:
        raise PermissionError(f"Invalid unblinding record: {record}")


def site_coordinates(length: int) -> Array:
    """Site-centred open-chain coordinates with the wall between centre sites."""

    length = int(length)
    if length < 6:
        raise ValueError("L must be at least 6")
    return np.arange(length, dtype=float) - 0.5 * (length - 1)


def condition_initial_magnetization(
    x: Array,
    condition: Mapping[str, Any],
) -> Array:
    """Construct the registered physical magnetization profile."""

    parameters = dict(condition.get("parameters", {}))
    allowed = {"center", "separation", "wavelength"}
    unknown = set(parameters) - allowed
    if unknown:
        raise ValueError(
            "Unsupported initial-profile parameters: " + ", ".join(sorted(unknown))
        )
    return initial_profile(
        np.asarray(x, dtype=float),
        profile=str(condition["profile"]),
        mu=float(condition["mu"]),
        orientation=int(condition["orientation"]),
        width=float(condition["width"]),
        background_m=float(condition["background_m"]),
        **parameters,
    )


def local_gibbs_bias(magnetization: Array) -> Array:
    r"""Return ``h_i`` for ``rho_i proportional exp(2 h_i S^z_i)``.

    For spin one half,

    .. math:: \langle S^z_i\rangle = \tfrac12\tanh h_i.

    Applying ``exp(h_i S^z_i)`` to the physical leg of an infinite-temperature
    purification produces precisely this reduced density matrix.
    """

    magnetization = np.asarray(magnetization, dtype=float)
    if np.any(~np.isfinite(magnetization)):
        raise ValueError("Initial magnetization contains non-finite values")
    if np.any(np.abs(magnetization) >= 0.5):
        raise ValueError("A finite Gibbs bias requires |m_i| < 1/2")
    return np.arctanh(2.0 * magnetization)


def magnetization_from_gibbs_bias(bias: Array) -> Array:
    """Inverse of :func:`local_gibbs_bias`, useful for validation."""

    return 0.5 * np.tanh(np.asarray(bias, dtype=float))


def resolve_numerics(
    job: Mapping[str, Any],
    *,
    length: int | None = None,
    dt: float | None = None,
    chi_max: int | None = None,
    truncation_cutoff: float | None = None,
    t_max: float | None = None,
    output_dt: float = 0.2,
    force_grouped: bool = False,
) -> dict[str, Any]:
    """Resolve CLI overrides and enforce an exactly aligned output grid."""

    base = dict(job["numerics"])
    resolved = {
        "L": int(base["L"] if length is None else length),
        "dt": float(base["dt"] if dt is None else dt),
        "chi_max": int(base["chi_max"] if chi_max is None else chi_max),
        "truncation_cutoff": float(
            base["truncation_cutoff"]
            if truncation_cutoff is None
            else truncation_cutoff
        ),
        "t_max": float(job["t_max"] if t_max is None else t_max),
        "output_dt": float(output_dt),
    }
    if resolved["L"] < 6:
        raise ValueError("L must be at least 6")
    if (
        resolved["dt"] <= 0.0
        or resolved["output_dt"] <= 0.0
        or resolved["t_max"] <= 0.0
    ):
        raise ValueError("dt, output_dt, and t_max must be positive")
    if resolved["chi_max"] < 2 or resolved["truncation_cutoff"] <= 0.0:
        raise ValueError("chi_max >= 2 and truncation_cutoff > 0 are required")
    grouped = uses_grouped_backend(
        job["condition"],
        force_grouped=force_grouped,
    )
    if grouped:
        if resolved["L"] % 2:
            raise ValueError(
                "The grouped range-two backend requires an even physical L"
            )
        resolved["backend_layout"] = "grouped_range2"

    steps_per_output = int(round(resolved["output_dt"] / resolved["dt"]))
    output_count = int(round(resolved["t_max"] / resolved["output_dt"]))
    if not np.isclose(
        steps_per_output * resolved["dt"],
        resolved["output_dt"],
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError("output_dt must be an integer multiple of dt")
    if not np.isclose(
        output_count * resolved["output_dt"],
        resolved["t_max"],
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError("t_max must be an integer multiple of output_dt")
    resolved["steps_per_output"] = steps_per_output
    resolved["output_count"] = output_count
    return resolved


def output_times(numerics: Mapping[str, Any]) -> Array:
    """Return the exactly represented measurement times including zero."""

    return np.arange(int(numerics["output_count"]) + 1, dtype=float) * float(
        numerics["output_dt"]
    )


def validate_physical_job(job: Mapping[str, Any]) -> None:
    """Fail early for unsupported thermodynamic or Hamiltonian parameters."""

    condition = dict(job["condition"])
    if str(condition["temperature"]) not in SUPPORTED_TEMPERATURES:
        raise NotImplementedError(
            "The current purification backend implements T=infinity only"
        )
    uses_grouped_backend(condition)


def parse_observables(
    job: Mapping[str, Any],
    override: str | None,
    *,
    allow_missing: bool,
) -> tuple[list[str], list[str]]:
    """Resolve requested observables and separate unsupported requests."""

    if override is None:
        requested = [str(value) for value in job.get("observables", [])]
    else:
        requested = [
            value.strip() for value in str(override).split(",") if value.strip()
        ]
    if "magnetization" not in requested:
        requested.insert(0, "magnetization")
    unsupported = sorted(set(requested) - SUPPORTED_OBSERVABLES)
    if unsupported and not allow_missing:
        raise NotImplementedError(
            "Unsupported observables in this backend: "
            + ", ".join(unsupported)
            + ". FCS needs a registered two-branch counting-field evolution; "
            "it must not be replaced by an equal-time proxy."
        )
    produced = [value for value in requested if value in SUPPORTED_OBSERVABLES]
    return produced, unsupported


def parse_fcs_gamma(raw: str | None) -> Array:
    """Return a symmetric real counting-field grid containing zero."""

    if raw is None:
        gamma = np.asarray(
            [-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6],
            dtype=float,
        )
    else:
        try:
            gamma = np.asarray(
                [float(value.strip()) for value in raw.split(",")],
                dtype=float,
            )
        except ValueError as error:
            raise ValueError("fcs-gamma must be a comma-separated float list") from error
    if gamma.ndim != 1 or gamma.size < 3 or np.any(~np.isfinite(gamma)):
        raise ValueError("fcs-gamma needs at least three finite values")
    gamma = np.unique(gamma)
    if not np.any(np.isclose(gamma, 0.0, rtol=0.0, atol=1e-13)):
        raise ValueError("fcs-gamma must contain zero")
    if not np.allclose(gamma, -gamma[::-1], rtol=0.0, atol=1e-13):
        raise ValueError("fcs-gamma must be symmetric about zero")
    return gamma


def canonical_job_sha256(
    job: Mapping[str, Any],
    numerics: Mapping[str, Any],
) -> str:
    """Hash the physical job and effective numerics for raw-data provenance."""

    payload = json.dumps(
        {"job": dict(job), "effective_numerics": dict(numerics)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def normalized_initial_field(
    magnetization: Array,
    condition: Mapping[str, Any],
) -> Array:
    """Return the article-normalized field for a manifest condition."""

    return normalized_field(
        magnetization,
        mu=float(condition["mu"]),
        background_m=float(condition["background_m"]),
    )
