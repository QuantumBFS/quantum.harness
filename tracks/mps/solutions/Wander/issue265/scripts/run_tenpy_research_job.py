#!/usr/bin/env python3
"""Run one registered infinite-temperature XXZ job with purification TEBD.

TeNPy is an optional dependency; install ``requirements-tensor-network.txt``
in the execution environment.  The runner refuses to fabricate unsupported
observables and refuses to open production-B before the preregistered
unblinding record exists.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research_dataset import ResearchDataset, save_research_dataset
from src.tenpy_research_backend import (
    assemble_range2_cut_current,
    canonical_job_sha256,
    condition_initial_magnetization,
    grouped_counting_mask,
    interleave_grouped_values,
    load_manifest_job,
    local_gibbs_bias,
    normalized_initial_field,
    output_times,
    parse_fcs_gamma,
    parse_observables,
    require_job_authorized,
    resolve_numerics,
    site_coordinates,
    uses_grouped_backend,
    validate_physical_job,
)


def _source_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unavailable"


def _require_tenpy() -> dict[str, Any]:
    try:
        import tenpy
        from tenpy.algorithms.purification import PurificationTEBD
        from tenpy.linalg import np_conserved as npc
        from tenpy.models.spins_nnn import SpinChainNNN
        from tenpy.models.xxz_chain import XXZChain
        from tenpy.networks.purification_mps import PurificationMPS
        from tenpy.tools import hdf5_io
        import h5py
    except ImportError as error:
        raise SystemExit(
            "TeNPy is not installed in this Python environment. Install "
            "`requirements-tensor-network.txt` and rerun."
        ) from error
    return {
        "tenpy": tenpy,
        "PurificationTEBD": PurificationTEBD,
        "npc": npc,
        "SpinChainNNN": SpinChainNNN,
        "XXZChain": XXZChain,
        "PurificationMPS": PurificationMPS,
        "hdf5_io": hdf5_io,
        "h5py": h5py,
    }


def _two_site_current_operator(
    site: Any,
    coupling: float,
    npc: Any,
    *,
    left_component: str = "",
    right_component: str = "",
) -> Any:
    r"""Return ``j_i = i J/2 (S+_i S-_{i+1} - S-_i S+_{i+1})``."""

    def relabel(operator: Any, index: int) -> Any:
        operator = operator.copy()
        operator.ireplace_labels(
            ["p", "p*"],
            [f"p{index}", f"p{index}*"],
        )
        return operator

    def product(left: Any, right: Any) -> Any:
        return npc.outer(left, right).transpose(
            ["p0", "p1", "p0*", "p1*"]
        )

    sp_sm = product(
        relabel(site.get_op("Sp" + left_component), 0),
        relabel(site.get_op("Sm" + right_component), 1),
    )
    sm_sp = product(
        relabel(site.get_op("Sm" + left_component), 0),
        relabel(site.get_op("Sp" + right_component), 1),
    )
    return 0.5j * float(coupling) * (sp_sm - sm_sp)


def _one_group_current_operator(
    site: Any,
    coupling: float,
    *,
    left_component: str,
    right_component: str,
) -> Any:
    """Return one directed current between two spins in a grouped site."""

    return 0.5j * float(coupling) * (
        site.get_op(
            f"Sp{left_component} Sm{right_component}"
        )
        - site.get_op(
            f"Sm{left_component} Sp{right_component}"
        )
    )


def _grouped_current_operators(
    site: Any,
    *,
    nearest_coupling: float,
    next_nearest_coupling: float,
    npc: Any,
) -> dict[str, Any]:
    """Build all operator families needed for physical range-two cut current."""

    return {
        "intra_nn": _one_group_current_operator(
            site,
            nearest_coupling,
            left_component="0",
            right_component="1",
        ),
        "inter_nn": _two_site_current_operator(
            site,
            nearest_coupling,
            npc,
            left_component="1",
            right_component="0",
        ),
        "nnn_00": _two_site_current_operator(
            site,
            next_nearest_coupling,
            npc,
            left_component="0",
            right_component="0",
        ),
        "nnn_11": _two_site_current_operator(
            site,
            next_nearest_coupling,
            npc,
            left_component="1",
            right_component="1",
        ),
    }


def _real_observable(values: Any, name: str, tolerance: float = 1e-10) -> np.ndarray:
    values = np.asarray(values)
    maximum_imaginary = float(np.max(np.abs(np.imag(values))))
    if maximum_imaginary > tolerance:
        raise RuntimeError(
            f"{name} has an unexpected imaginary component "
            f"{maximum_imaginary:.3e}"
        )
    return np.asarray(np.real(values), dtype=float)


def _measure(
    psi: Any,
    *,
    observables: list[str],
    current_operator: Any | None,
    grouped: bool,
) -> dict[str, np.ndarray]:
    if grouped:
        magnetization = interleave_grouped_values(
            _real_observable(
                psi.expectation_value("Sz0"),
                "grouped magnetization component 0",
            ),
            _real_observable(
                psi.expectation_value("Sz1"),
                "grouped magnetization component 1",
            ),
        )
    else:
        magnetization = _real_observable(
            psi.expectation_value("Sz"),
            "magnetization",
        )
    measured: dict[str, np.ndarray] = {"magnetization": magnetization}
    if "local_spin_current" in observables:
        if grouped:
            if not isinstance(current_operator, dict):
                raise RuntimeError("Grouped current operators are missing")
            intra_nn = _real_observable(
                psi.expectation_value(current_operator["intra_nn"]),
                "grouped intra-site nearest current",
            )
            two_site_axes = (["p0", "p1"], ["p0*", "p1*"])
            inter_nn = _real_observable(
                psi.expectation_value(
                    current_operator["inter_nn"],
                    axes=two_site_axes,
                ),
                "grouped inter-site nearest current",
            )
            nnn_00 = _real_observable(
                psi.expectation_value(
                    current_operator["nnn_00"],
                    axes=two_site_axes,
                ),
                "grouped next-nearest current 00",
            )
            nnn_11 = _real_observable(
                psi.expectation_value(
                    current_operator["nnn_11"],
                    axes=two_site_axes,
                ),
                "grouped next-nearest current 11",
            )
            measured["local_spin_current"] = assemble_range2_cut_current(
                intra_nn=intra_nn,
                inter_nn=inter_nn,
                nnn_00=nnn_00,
                nnn_11=nnn_11,
            )
        else:
            measured["local_spin_current"] = _real_observable(
                psi.expectation_value(
                    current_operator,
                    axes=(["p0", "p1"], ["p0*", "p1*"]),
                ),
                "local spin current",
            )
    if "czz" in observables:
        center = len(measured["magnetization"]) // 2
        if grouped:
            center_group, center_component = divmod(center, 2)
            groups = len(psi.sites)
            correlation = interleave_grouped_values(
                psi.correlation_function(
                    f"Sz{center_component}",
                    "Sz0",
                    sites1=[center_group],
                    sites2=list(range(groups)),
                )[0],
                psi.correlation_function(
                    f"Sz{center_component}",
                    "Sz1",
                    sites1=[center_group],
                    sites2=list(range(groups)),
                )[0],
            )
        else:
            correlation = psi.correlation_function(
                "Sz",
                "Sz",
                sites1=[center],
                sites2=list(range(len(measured["magnetization"]))),
            )[0]
        correlation = _real_observable(correlation, "Czz")
        measured["czz"] = (
            correlation
            - measured["magnetization"][center]
            * measured["magnetization"]
        )
    return measured


def _build_initial_state(
    *,
    model: Any,
    target_m: np.ndarray,
    purification_mps: Any,
    npc: Any,
    grouped: bool,
) -> Any:
    sites = model.lat.mps_sites()
    psi = purification_mps.from_infiniteT(sites, bc="finite")
    biases = local_gibbs_bias(target_m)
    if grouped:
        if 2 * len(sites) != biases.size:
            raise RuntimeError(
                "Grouped model length does not match physical profile"
            )
        operators = [
            npc.expm(
                float(biases[2 * group]) * site.get_op("Sz0")
                + float(biases[2 * group + 1]) * site.get_op("Sz1")
            )
            for group, site in enumerate(sites)
        ]
    else:
        operators = [
            npc.expm(float(bias) * site.get_op("Sz"))
            for bias, site in zip(biases, sites, strict=True)
        ]
    psi.apply_product_op(operators, unitary=False, renormalize=True)
    if grouped:
        actual = interleave_grouped_values(
            _real_observable(
                psi.expectation_value("Sz0"),
                "initial grouped magnetization component 0",
            ),
            _real_observable(
                psi.expectation_value("Sz1"),
                "initial grouped magnetization component 1",
            ),
        )
    else:
        actual = _real_observable(
            psi.expectation_value("Sz"),
            "initial magnetization",
        )
    error = float(np.max(np.abs(actual - target_m)))
    if error > 5e-11:
        raise RuntimeError(
            f"Purification initial-state error {error:.3e} exceeds 5e-11"
        )
    return psi


def _counting_phase_operators(
    sites: list[Any],
    *,
    gamma: float,
    npc: Any,
    physical_length: int,
    grouped: bool,
) -> list[Any]:
    """Physical-leg operators for ``exp(i gamma Q_R)`` at the central cut."""

    if grouped:
        mask = grouped_counting_mask(physical_length)
        if mask.shape[0] != len(sites):
            raise RuntimeError(
                "Grouped FCS mask does not match the model length"
            )
        result = []
        for site, membership in zip(sites, mask, strict=True):
            generator = None
            if bool(membership[0]):
                generator = site.get_op("Sz0")
            if bool(membership[1]):
                second = site.get_op("Sz1")
                generator = (
                    second if generator is None else generator + second
                )
            result.append(
                site.get_op("Id")
                if generator is None
                else npc.expm(1j * float(gamma) * generator)
            )
        return result
    first_right_site = physical_length // 2
    if len(sites) != physical_length:
        raise RuntimeError("Ungrouped FCS site count does not match physical L")
    return [
        (
            site.get_op("Id")
            if index < first_right_site
            else npc.expm(1j * float(gamma) * site.get_op("Sz"))
        )
        for index, site in enumerate(sites)
    ]


def _tebd_options(numerics: dict[str, Any]) -> dict[str, Any]:
    return {
        "dt": numerics["dt"],
        "N_steps": numerics["steps_per_output"],
        "order": 2,
        "trunc_params": {
            "chi_max": numerics["chi_max"],
            "svd_min": numerics["truncation_cutoff"],
        },
        "disentangle": "backwards",
    }


def _save_checkpoint(
    path: Path,
    payload: dict[str, Any],
    *,
    h5py: Any,
    hdf5_io: Any,
) -> None:
    """Atomically replace one TeNPy HDF5 checkpoint."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with h5py.File(temporary, "w") as handle:
        hdf5_io.save_to_hdf5(handle, payload)
    os.replace(temporary, path)


def _load_checkpoint(
    path: Path,
    *,
    h5py: Any,
    hdf5_io: Any,
) -> dict[str, Any]:
    with h5py.File(path, "r") as handle:
        payload = hdf5_io.load_from_hdf5(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid checkpoint payload: {path}")
    return payload


def _default_smoke_output(job_id: str) -> Path:
    return (
        ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / f"{job_id}__smoke.npz"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "results_research_program" / "manifest.json",
    )
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--unblinding-record",
        type=Path,
        default=ROOT / "results_research_program" / "unblinding.json",
    )
    parser.add_argument("--L", type=int)
    parser.add_argument("--dt", type=float)
    parser.add_argument("--chi-max", type=int)
    parser.add_argument("--truncation-cutoff", type=float)
    parser.add_argument("--t-max", type=float)
    parser.add_argument("--output-dt", type=float)
    parser.add_argument(
        "--observables",
        help="Comma-separated override, intended for backend smoke tests.",
    )
    parser.add_argument(
        "--fcs-gamma",
        help=(
            "Symmetric comma-separated counting fields. Defaults to "
            "-0.6,-0.4,-0.2,0,0.2,0.4,0.6."
        ),
    )
    parser.add_argument(
        "--fcs-explicit-negative",
        action="store_true",
        help=(
            "Evolve negative counting fields independently. By default they "
            "are reconstructed from the exact characteristic-function "
            "identity Z(-gamma)=conj(Z(gamma))."
        ),
    )
    parser.add_argument(
        "--allow-missing-observables",
        action="store_true",
        help=(
            "Record but do not fabricate unsupported observables. Never use "
            "this flag for confirmatory production."
        ),
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Use a tiny numerical grid while retaining the registered physics.",
    )
    parser.add_argument(
        "--force-grouped",
        action="store_true",
        help=(
            "Use the two-spin grouped representation even at J2=0. "
            "Restricted to --smoke representation-equivalence tests."
        ),
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="HDF5 checkpoint path; defaults to OUTPUT.checkpoint.h5.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=25,
        help="Checkpoint every N saved output intervals (default: 25).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the verified HDF5 checkpoint.",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    manifest, job = load_manifest_job(args.manifest, args.job_id)
    require_job_authorized(
        job,
        unblinding_record=args.unblinding_record,
    )
    validate_physical_job(job)
    if args.force_grouped and not args.smoke:
        raise SystemExit("--force-grouped is restricted to --smoke")

    if args.smoke:
        length = 16 if args.L is None else args.L
        dt = 0.01 if args.dt is None else args.dt
        chi_max = 32 if args.chi_max is None else args.chi_max
        truncation_cutoff = (
            1e-10
            if args.truncation_cutoff is None
            else args.truncation_cutoff
        )
        t_max = 0.2 if args.t_max is None else args.t_max
        output_dt_value = 0.05 if args.output_dt is None else args.output_dt
    else:
        length = args.L
        dt = args.dt
        chi_max = args.chi_max
        truncation_cutoff = args.truncation_cutoff
        t_max = args.t_max
        output_dt_value = 0.2 if args.output_dt is None else args.output_dt

    numerics = resolve_numerics(
        job,
        length=length,
        dt=dt,
        chi_max=chi_max,
        truncation_cutoff=truncation_cutoff,
        t_max=t_max,
        output_dt=output_dt_value,
        force_grouped=args.force_grouped,
    )
    observables, omitted_observables = parse_observables(
        job,
        args.observables,
        allow_missing=args.allow_missing_observables,
    )
    if omitted_observables and not args.smoke:
        raise SystemExit(
            "--allow-missing-observables is restricted to --smoke; "
            "confirmatory data must contain every registered observable."
        )
    fcs_gamma = (
        parse_fcs_gamma(args.fcs_gamma)
        if "fcs_logZ" in observables
        else None
    )
    if fcs_gamma is not None:
        numerics["fcs_gamma"] = [float(value) for value in fcs_gamma]

    output = (
        _default_smoke_output(str(job["job_id"]))
        if args.smoke and args.output is None
        else Path(job["output_path"])
        if args.output is None
        else args.output
    )
    output = output.resolve()
    if output.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite existing dataset: {output}")
    if args.checkpoint_every < 1:
        raise SystemExit("--checkpoint-every must be positive")
    checkpoint = (
        args.checkpoint.resolve()
        if args.checkpoint is not None
        else output.with_suffix(output.suffix + ".checkpoint.h5")
    )
    if args.resume and not checkpoint.exists():
        raise SystemExit(f"Resume checkpoint does not exist: {checkpoint}")
    if checkpoint.exists() and not args.resume and not args.overwrite:
        raise SystemExit(
            "A checkpoint already exists. Use --resume, or explicitly "
            f"--overwrite to start again: {checkpoint}"
        )

    packages = _require_tenpy()
    XXZChain = packages["XXZChain"]
    SpinChainNNN = packages["SpinChainNNN"]
    PurificationMPS = packages["PurificationMPS"]
    PurificationTEBD = packages["PurificationTEBD"]
    npc = packages["npc"]
    tenpy = packages["tenpy"]
    hdf5_io = packages["hdf5_io"]
    h5py = packages["h5py"]

    condition = dict(job["condition"])
    J = 1.0
    grouped = uses_grouped_backend(
        condition,
        force_grouped=args.force_grouped,
    )
    if grouped:
        model = SpinChainNNN(
            {
                "L": numerics["L"] // 2,
                "S": 0.5,
                "Jx": -J,
                "Jy": -J,
                "Jz": -J * float(condition["delta"]),
                "Jxp": -float(condition.get("j2", 0.0)),
                "Jyp": -float(condition.get("j2", 0.0)),
                "Jzp": -float(condition.get("j2", 0.0)),
                "hx": 0.0,
                "hy": 0.0,
                "hz": 0.0,
                "bc_MPS": "finite",
                "conserve": "Sz",
            }
        )
    else:
        model = XXZChain(
            {
                "L": numerics["L"],
                "Jxx": -J,
                "Jz": -J * float(condition["delta"]),
                "hz": 0.0,
                "bc_MPS": "finite",
                "conserve": "Sz",
            }
        )
    x = site_coordinates(numerics["L"])
    target_m = condition_initial_magnetization(x, condition)
    job_hash = canonical_job_sha256(job, numerics)
    checkpoint_payload: dict[str, Any] | None = None
    if args.resume:
        checkpoint_payload = _load_checkpoint(
            checkpoint,
            h5py=h5py,
            hdf5_io=hdf5_io,
        )
        if int(checkpoint_payload.get("schema_version", -1)) != 1:
            raise RuntimeError("Unsupported checkpoint schema")
        if str(checkpoint_payload.get("job_sha256")) != job_hash:
            raise RuntimeError(
                "Checkpoint job/numerics hash does not match this execution"
            )
        if str(checkpoint_payload.get("output_path")) != str(output):
            raise RuntimeError(
                "Checkpoint output path does not match this execution"
            )
        psi = checkpoint_payload["psi"]
    else:
        psi = _build_initial_state(
            model=model,
            target_m=target_m,
            purification_mps=PurificationMPS,
            npc=npc,
            grouped=grouped,
        )
    current_operator = (
        (
            _grouped_current_operators(
                model.lat.mps_sites()[0],
                nearest_coupling=-J,
                next_nearest_coupling=-float(
                    condition.get("j2", 0.0)
                ),
                npc=npc,
            )
            if grouped
            else _two_site_current_operator(
                model.lat.mps_sites()[0],
                -J,
                npc,
            )
        )
        if "local_spin_current" in observables
        else None
    )
    engine = PurificationTEBD(psi, model, _tebd_options(numerics))
    fcs_branches: list[dict[str, Any]] = []
    if fcs_gamma is not None:
        sites = model.lat.mps_sites()
        if checkpoint_payload is None:
            branch_states = {}
        else:
            branch_states = {
                float(record["gamma"]): record["psi"]
                for record in checkpoint_payload.get("fcs_branches", [])
            }
        active_gammas = [
            float(gamma)
            for gamma in fcs_gamma
            if not np.isclose(gamma, 0.0, rtol=0.0, atol=1e-13)
            and (gamma > 0.0 or args.fcs_explicit_negative)
        ]
        if checkpoint_payload is not None and set(branch_states) != set(
            active_gammas
        ):
            raise RuntimeError("Checkpoint FCS branches do not match this run")
        for gamma in active_gammas:
            if checkpoint_payload is None:
                branch = psi.copy()
                branch.apply_product_op(
                    _counting_phase_operators(
                        sites,
                        gamma=-float(gamma),
                        npc=npc,
                        physical_length=numerics["L"],
                        grouped=grouped,
                    ),
                    unitary=True,
                    renormalize=False,
                )
            else:
                branch = branch_states[gamma]
            fcs_branches.append(
                {
                    "gamma": float(gamma),
                    "psi": branch,
                    "engine": PurificationTEBD(
                        branch,
                        model,
                        _tebd_options(numerics),
                    ),
                    "plus_phase": _counting_phase_operators(
                        sites,
                        gamma=float(gamma),
                        npc=npc,
                        physical_length=numerics["L"],
                        grouped=grouped,
                    ),
                    "minus_phase": _counting_phase_operators(
                        sites,
                        gamma=-float(gamma),
                        npc=npc,
                        physical_length=numerics["L"],
                        grouped=grouped,
                    ),
                }
            )

    registered_times = output_times(numerics)
    all_engines = [engine] + [
        branch["engine"] for branch in fcs_branches
    ]
    if checkpoint_payload is None:
        magnetization: list[np.ndarray] = []
        currents: list[np.ndarray] = []
        correlations: list[np.ndarray] = []
        fcs_logz: list[np.ndarray] = []
        maximum_entropy = 0.0
        maximum_chi = 1
        maximum_discarded_increment = 0.0
        discarded_offsets = [0.0 for _ in all_engines]
        previous_discarded = [0.0 for _ in all_engines]
        elapsed_offset = 0.0
        initial_total_magnetization: float | None = None
        first_output_index = 0
    else:
        checkpoint_index = int(checkpoint_payload["output_index"])
        if checkpoint_index < 0 or checkpoint_index >= registered_times.size:
            raise RuntimeError("Checkpoint output index is out of range")
        checkpoint_time = float(registered_times[checkpoint_index])
        for active_engine in all_engines:
            active_engine.evolved_time = checkpoint_time
        magnetization = [
            np.asarray(row, dtype=float)
            for row in np.asarray(checkpoint_payload["magnetization"])
        ]
        currents = [
            np.asarray(row, dtype=float)
            for row in np.asarray(checkpoint_payload["current"])
        ]
        correlations = [
            np.asarray(row, dtype=float)
            for row in np.asarray(checkpoint_payload["czz"])
        ]
        fcs_logz = [
            np.asarray(row, dtype=complex)
            for row in np.asarray(checkpoint_payload["fcs_logZ"])
        ]
        expected_rows = checkpoint_index + 1
        for name, rows in (
            ("magnetization", magnetization),
            ("current", currents),
            ("czz", correlations),
            ("fcs_logZ", fcs_logz),
        ):
            if rows and len(rows) != expected_rows:
                raise RuntimeError(
                    f"Checkpoint {name} row count does not match its index"
                )
        maximum_entropy = float(checkpoint_payload["maximum_entropy"])
        maximum_chi = int(checkpoint_payload["maximum_chi"])
        maximum_discarded_increment = float(
            checkpoint_payload["maximum_discarded_increment"]
        )
        discarded_offsets = [
            float(value)
            for value in checkpoint_payload["discarded_cumulative"]
        ]
        if len(discarded_offsets) != len(all_engines):
            raise RuntimeError("Checkpoint engine count does not match")
        previous_discarded = list(discarded_offsets)
        elapsed_offset = float(checkpoint_payload["elapsed_seconds"])
        initial_total_magnetization = float(
            checkpoint_payload["initial_total_magnetization"]
        )
        first_output_index = checkpoint_index + 1
    discarded_values = list(discarded_offsets)
    started = time.monotonic()

    for output_index in range(first_output_index, registered_times.size):
        registered_time = registered_times[output_index]
        if output_index > 0:
            for active_engine in all_engines:
                active_engine.run()
        if not np.isclose(
            float(engine.evolved_time),
            float(registered_time),
            rtol=0.0,
            atol=5e-11,
        ):
            raise RuntimeError(
                "TEBD clock drift: "
                f"{engine.evolved_time} != {registered_time}"
            )
        for branch in fcs_branches:
            if not np.isclose(
                float(branch["engine"].evolved_time),
                float(registered_time),
                rtol=0.0,
                atol=5e-11,
            ):
                raise RuntimeError(
                    "FCS-branch TEBD clock drift at gamma="
                    f"{branch['gamma']}: "
                    f"{branch['engine'].evolved_time} != {registered_time}"
                )
        measured = _measure(
            psi,
            observables=observables,
            current_operator=current_operator,
            grouped=grouped,
        )
        magnetization.append(measured["magnetization"])
        if "local_spin_current" in measured:
            currents.append(measured["local_spin_current"])
        if "czz" in measured:
            correlations.append(measured["czz"])
        if fcs_gamma is not None:
            values: dict[float, complex] = {0.0: 1.0 + 0.0j}
            for branch in fcs_branches:
                branch["psi"].apply_product_op(
                    branch["plus_phase"],
                    unitary=True,
                    renormalize=False,
                )
                values[branch["gamma"]] = complex(
                    psi.overlap(branch["psi"])
                )
                branch["psi"].apply_product_op(
                    branch["minus_phase"],
                    unitary=True,
                    renormalize=False,
                )
            ordered = np.asarray(
                [
                    (
                        1.0 + 0.0j
                        if np.isclose(
                            gamma,
                            0.0,
                            rtol=0.0,
                            atol=1e-13,
                        )
                        else values[float(gamma)]
                        if float(gamma) in values
                        else np.conj(values[-float(gamma)])
                    )
                    for gamma in fcs_gamma
                ],
                dtype=complex,
            )
            if np.any(np.abs(ordered) < 1e-14):
                raise RuntimeError(
                    "FCS overlap fell below 1e-14; logarithm is unresolved"
                )
            fcs_logz.append(np.log(ordered))

        total_magnetization = float(np.sum(measured["magnetization"]))
        if initial_total_magnetization is None:
            initial_total_magnetization = total_magnetization
        entropy = np.asarray(psi.entanglement_entropy(), dtype=float)
        if entropy.size:
            maximum_entropy = max(maximum_entropy, float(np.max(entropy)))
        active_states = [psi] + [
            branch["psi"] for branch in fcs_branches
        ]
        maximum_chi = max(
            maximum_chi,
            max(
                (
                    int(max(state.chi))
                    for state in active_states
                    if state.chi
                ),
                default=1,
            ),
        )
        discarded_values = [
            float(offset) + float(active_engine.trunc_err.eps)
            for offset, active_engine in zip(
                discarded_offsets,
                all_engines,
                strict=True,
            )
        ]
        maximum_discarded_increment = max(
            maximum_discarded_increment,
            max(
                (
                    max(0.0, value - previous)
                    for value, previous in zip(
                        discarded_values,
                        previous_discarded,
                        strict=True,
                    )
                ),
                default=0.0,
            ),
        )
        previous_discarded = discarded_values
        discarded = float(sum(discarded_values))
        progress = {
            "job_id": job["job_id"],
            "smoke": bool(args.smoke),
            "t": float(registered_time),
            "t_max": float(numerics["t_max"]),
            "chi_max_observed": maximum_chi,
            "discarded_weight_cumulative": discarded,
            "fcs_branch_count": len(fcs_branches),
            "magnetization_drift": float(
                total_magnetization - initial_total_magnetization
            ),
            "elapsed_seconds": float(time.monotonic() - started),
        }
        progress["elapsed_seconds"] += elapsed_offset
        print(json.dumps(progress, ensure_ascii=False), flush=True)

        should_checkpoint = (
            output_index == registered_times.size - 1
            or output_index % args.checkpoint_every == 0
        )
        if should_checkpoint:
            # Applying the counting phases can permute the local MPS leg
            # labels even after the inverse phase.  Evolution tolerates that
            # ordering, but HDF5 reconstruction intentionally enforces the
            # canonical PurificationMPS label order.
            for branch in fcs_branches:
                branch["psi"].canonical_form()
            _save_checkpoint(
                checkpoint,
                {
                    "schema_version": 1,
                    "job_sha256": job_hash,
                    "output_path": str(output),
                    "output_index": output_index,
                    "psi": psi,
                    "fcs_branches": [
                        {
                            "gamma": branch["gamma"],
                            "psi": branch["psi"],
                        }
                        for branch in fcs_branches
                    ],
                    "magnetization": np.stack(magnetization),
                    "current": (
                        np.stack(currents)
                        if currents
                        else np.empty((0, numerics["L"] - 1))
                    ),
                    "czz": (
                        np.stack(correlations)
                        if correlations
                        else np.empty((0, numerics["L"]))
                    ),
                    "fcs_logZ": (
                        np.stack(fcs_logz)
                        if fcs_logz
                        else np.empty((0, 0), dtype=complex)
                    ),
                    "maximum_entropy": maximum_entropy,
                    "maximum_chi": maximum_chi,
                    "maximum_discarded_increment": (
                        maximum_discarded_increment
                    ),
                    "discarded_cumulative": discarded_values,
                    "initial_total_magnetization": (
                        initial_total_magnetization
                    ),
                    "elapsed_seconds": (
                        elapsed_offset + time.monotonic() - started
                    ),
                },
                h5py=h5py,
                hdf5_io=hdf5_io,
            )

    m = np.stack(magnetization)
    u = np.stack(
        [
            normalized_initial_field(profile, condition)
            for profile in magnetization
        ]
    )
    total_magnetization = np.sum(m, axis=1)
    maximum_magnetization_drift = float(
        np.max(np.abs(total_magnetization - total_magnetization[0]))
    )
    elapsed_total = float(elapsed_offset + time.monotonic() - started)
    metadata = {
        "schema_version": 1,
        "hamiltonian": (
            (
                "ferromagnetic J1-J2 XXZ: "
                "-J sum(SxSx+SySy+Delta SzSz) "
                "-J2 sum(Sx_i Sx_{i+2}+Sy_i Sy_{i+2}+"
                "Sz_i Sz_{i+2})"
            )
            if grouped
            else (
                "ferromagnetic nearest-neighbour XXZ: "
                "-J sum(SxSx+SySy+Delta SzSz)"
            )
        ),
        "delta": float(condition["delta"]),
        "J": J,
        "J2": float(condition.get("j2", 0.0)),
        "temperature": str(condition["temperature"]),
        "mu": float(condition["mu"]),
        "orientation": int(condition["orientation"]),
        "profile": str(condition["profile"]),
        "width": float(condition["width"]),
        "background_m": float(condition["background_m"]),
        "L": int(numerics["L"]),
        "boundary_condition": "open",
        "algorithm": (
            "TeNPy PurificationTEBD order=2, backwards disentangler, "
            "Sz-conserving purification"
            + (
                ", two-physical-spin GroupedSite range-two representation"
                if grouped
                else ""
            )
        ),
        "time_step": float(numerics["dt"]),
        "chi_max": int(numerics["chi_max"]),
        "truncation_cutoff": float(numerics["truncation_cutoff"]),
        "discarded_weight_max": maximum_discarded_increment,
        "source_commit": _source_commit(),
        "raw_sha256": job_hash,
        "preprocessing": "none; raw site-resolved expectation values",
        "manifest_path": str(args.manifest.resolve()),
        "manifest_sha256": str(manifest.get("matrix_sha256", "unavailable")),
        "job_id": str(job["job_id"]),
        "stage": str(job["stage"]),
        "smoke_test": bool(args.smoke),
        "requested_observables": [
            str(value) for value in job.get("observables", [])
        ],
        "produced_observables": observables,
        "omitted_observables": omitted_observables,
        "tenpy_version": str(getattr(tenpy, "__version__", "unknown")),
        "output_dt": float(numerics["output_dt"]),
        "maximum_chi_observed": maximum_chi,
        "maximum_entanglement_entropy": maximum_entropy,
        "discarded_weight_cumulative": float(
            sum(discarded_values)
        ),
        "maximum_total_magnetization_drift": maximum_magnetization_drift,
        "wall_time_seconds": elapsed_total,
        "checkpoint_path": str(checkpoint),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if grouped:
        metadata.update(
            {
                "backend_layout": "grouped_range2",
                "grouped_mps_length": len(model.lat.mps_sites()),
                "physical_output_layout": (
                    "site-resolved physical spins, interleaved from "
                    "GroupedSite components 0 and 1"
                ),
            }
        )
    if fcs_gamma is not None:
        metadata.update(
            {
                "fcs_definition": (
                    "two-projective-measurement transfer through the central "
                    "cut: Z(gamma,t)=Tr[rho0 U^dagger exp(i gamma Q_R) "
                    "U exp(-i gamma Q_R)]"
                ),
                "fcs_counted_charge": "Q_R=sum_{i>=L/2} Sz_i",
                "fcs_branch_count": len(fcs_branches),
                "fcs_negative_fields": (
                    "explicitly evolved"
                    if args.fcs_explicit_negative
                    else "reconstructed using Z(-gamma)=conj(Z(gamma))"
                ),
                "fcs_symmetry_note": (
                    "rho0 is diagonal in Sz and commutes with Q_R"
                ),
            }
        )
    dataset = ResearchDataset(
        condition_id=str(job["condition_id"]),
        x=x,
        t=registered_times,
        u=u,
        m=m,
        current=np.stack(currents) if currents else None,
        czz=np.stack(correlations) if correlations else None,
        fcs_gamma=fcs_gamma,
        fcs_logZ=np.stack(fcs_logz) if fcs_logz else None,
        metadata=metadata,
    )
    save_research_dataset(dataset, output)
    summary_path = output.with_suffix(".run.json")
    summary_path.write_text(
        json.dumps(
            {
                "status": "complete",
                "output": str(output),
                "job_id": job["job_id"],
                "smoke": bool(args.smoke),
                "effective_numerics": numerics,
                "produced_observables": observables,
                "omitted_observables": omitted_observables,
                "maximum_total_magnetization_drift": (
                    maximum_magnetization_drift
                ),
                "maximum_chi_observed": maximum_chi,
                "discarded_weight_cumulative": float(
                    sum(discarded_values)
                ),
                "fcs_branch_count": len(fcs_branches),
                "wall_time_seconds": elapsed_total,
                "checkpoint": str(checkpoint),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "output": str(output),
                "summary": str(summary_path),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
