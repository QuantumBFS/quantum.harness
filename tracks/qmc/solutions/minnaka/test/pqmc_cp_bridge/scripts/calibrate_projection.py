#!/usr/bin/env python3
"""Recoverable TI projection scan followed by an independent II check."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from alf_statistics import (
    EnergyEstimate,
    choose_additional_nbin,
    estimate_energy,
    parse_replica,
    write_diagnostics,
)
from bridge_config import (
    approved_config,
    energy_ok,
    ltrot,
    theta_candidates,
)
from prepare_alf_chain import (
    DEFAULT_TRIAL_ASSETS,
    atomic_json,
    prepare_batch,
    sha256_file,
)
from run_alf_batch import run_batch


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
DEFAULT_RUN_ROOT = ROOT / "runs" / "alf_projection"
DEFAULT_RESULTS_ROOT = ROOT / "results"
DEFAULT_EXECUTABLE = (
    REPO / "test" / "alf_hirsch_binary" / "run" / "binary"
    / "bin" / "ALF.binary.out"
)


class BatchBudgetExhausted(RuntimeError):
    """Raised after the requested number of new Slurm-sized batches."""


def _estimate_dict(value: EnergyEstimate) -> dict[str, Any]:
    return asdict(value)


def _attempt_dict(value: EnergyEstimate) -> dict[str, Any]:
    data = {
        "sigma_bin": value.sigma_bin,
        "sigma_replica": value.sigma_replica,
        "sigma": value.sigma,
        "retained_bins": value.retained_bins,
        "replicas": value.replicas,
        "mean_sign": value.mean_sign,
        "negative_sign_bins": value.negative_sign_bins,
        "precision_ready": value.precision_ready,
        "hard_failure": value.hard_failure,
        "loo_stable": value.loo_stable,
        "max_green_precision": value.max_green_precision,
        "statistical_precision_pass": value.statistical_precision_pass,
        "green_stability_pass": value.green_stability_pass,
        "aggregated_bins": value.aggregated_bins,
    }
    if value.precision_ready:
        data["mean"] = value.mean
    return data


def _write_csv(results_root: Path, state: dict[str, Any]) -> None:
    path = results_root / "theta_scan.csv"
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "ensemble", "theta", "ltrot", "mean", "sigma",
                "sigma_bin", "sigma_replica", "retained_bins",
                "mean_sign", "energy_ok",
                "statistical_precision_pass", "green_stability_pass",
                "green_max", "green_median", "green_p95",
            ),
        )
        writer.writeheader()
        for ensemble in ("TI", "II"):
            for theta, point in sorted(
                state.get(ensemble, {}).items(), key=lambda item: int(item[0])
            ):
                estimate = point.get("estimate")
                if not estimate:
                    continue
                writer.writerow({
                    "ensemble": ensemble,
                    "theta": theta,
                    "ltrot": ltrot(int(theta), approved_config()),
                    "mean": format(estimate["mean"], ".17g"),
                    "sigma": format(estimate["sigma"], ".17g"),
                    "sigma_bin": format(estimate["sigma_bin"], ".17g"),
                    "sigma_replica": format(
                        estimate["sigma_replica"], ".17g"
                    ),
                    "retained_bins": estimate["retained_bins"],
                    "mean_sign": format(estimate["mean_sign"], ".17g"),
                    "energy_ok": point.get("energy_ok"),
                    "statistical_precision_pass": estimate[
                        "statistical_precision_pass"
                    ],
                    "green_stability_pass": estimate[
                        "green_stability_pass"
                    ],
                    "green_max": estimate["max_green_precision"],
                    "green_median": point.get("green_median", ""),
                    "green_p95": point.get("green_p95", ""),
                })
    temporary.replace(path)


class RealBackend:
    def __init__(
        self,
        *,
        run_root: Path,
        executable: Path,
        trial_assets: Path,
        master_seed: int,
        chains: int = 6,
        launcher: tuple[str, ...] = ("mpirun", "-np", "1"),
        initial_nbin: int = 25,
        max_nbin: int | None = None,
        max_new_batches: int | None = None,
        nwrap: int = 5,
        sweeps_per_bin: int = 250,
    ):
        self.run_root = run_root
        self.executable = executable
        self.trial_assets = trial_assets
        self.master_seed = master_seed
        self.chains = chains
        self.launcher = launcher
        self.initial_nbin = initial_nbin
        self.max_nbin = max_nbin
        self.max_new_batches = max_new_batches
        self.nwrap = nwrap
        self.sweeps_per_bin = sweeps_per_bin
        self.new_batches_completed = 0
        self.last_replicas: dict[tuple[str, int], list] = {}

    def _batch_dir(self, ensemble: str, theta: int, batch: int) -> Path:
        return (
            self.run_root / ensemble / f"theta_{theta:03d}"
            / f"batch_{batch:03d}"
        )

    def ensure_batch(
        self, ensemble: str, theta: int, batch: int, nbin: int, nsweep: int
    ) -> None:
        batch_dir = self._batch_dir(ensemble, theta, batch)
        state_path = batch_dir / "batch_state.json"
        already_complete = False
        if state_path.is_file():
            previous = json.loads(state_path.read_text(encoding="utf-8"))
            already_complete = previous.get("status") == "complete"
        if (
            not already_complete
            and self.max_new_batches is not None
            and self.new_batches_completed >= self.max_new_batches
        ):
            raise BatchBudgetExhausted(
                f"completed {self.new_batches_completed} new batch(es); "
                "submit the next bounded calibration job"
            )
        if not (batch_dir / "batch_manifest.json").is_file():
            prepare_batch(
                self.run_root,
                ensemble=ensemble,
                theta=theta,
                batch=batch,
                nbin=nbin,
                nsweep=nsweep,
                master_seed=self.master_seed,
                executable=self.executable,
                trial_assets=self.trial_assets,
                chains=self.chains,
                nwrap=self.nwrap,
            )
        state = run_batch(
            batch_dir,
            launcher=self.launcher,
            bind_cpus=True,
        )
        if state["status"] != "complete":
            raise RuntimeError(f"ALF batch failed: {batch_dir}")
        if not already_complete:
            self.new_batches_completed += 1

    def analyze(self, ensemble: str, theta: int) -> EnergyEstimate:
        root = self.run_root / ensemble / f"theta_{theta:03d}"
        replicas = []
        for batch_dir in sorted(root.glob("batch_*")):
            state = json.loads(
                (batch_dir / "batch_state.json").read_text(encoding="utf-8")
            )
            if state.get("status") != "complete":
                continue
            manifest = json.loads(
                (batch_dir / "batch_manifest.json").read_text(encoding="utf-8")
            )
            if manifest["ensemble"] != ensemble or manifest["theta"] != theta:
                raise RuntimeError(f"batch identity mismatch: {batch_dir}")
            for chain in manifest["chains"]:
                replicas.append(parse_replica(
                    batch_dir / f"chain_{chain['chain']}",
                    {
                        "chain": chain["chain"],
                        "batch": manifest["batch"],
                        "seed": chain["seed"],
                        "theta": theta,
                        "ltrot": manifest["ltrot"],
                        "nbin": manifest["nbin"],
                    },
                ))
        self.last_replicas[(ensemble, theta)] = replicas
        return estimate_energy(replicas)

    def write_diagnostics(
        self, results_root: Path, ensemble: str, theta: int
    ) -> dict[str, object]:
        return write_diagnostics(
            self.last_replicas[(ensemble, theta)],
            results_root / "diagnostics" / ensemble / f"theta_{theta:03d}",
            ensemble=ensemble,
            theta=theta,
        )


def _load_state(path: Path) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"schema_version": 1, "TI": {}, "II": {}}


def _precision_loop(
    backend: Any,
    *,
    ensemble: str,
    theta: int,
    state: dict[str, Any],
    state_path: Path,
) -> EnergyEstimate | None:
    point = state[ensemble].setdefault(
        str(theta),
        {"status": "running", "batches": [], "attempts": []},
    )
    if point.get("status") == "energy_checked":
        values = point["estimate"]
        return EnergyEstimate(**values)
    if not point["batches"]:
        initial_nbin = int(getattr(backend, "initial_nbin", 25))
        backend.ensure_batch(
            ensemble, theta, 0, initial_nbin,
            int(getattr(backend, "sweeps_per_bin", 250)),
        )
        point["batches"].append({
            "batch": 0,
            "nbin": initial_nbin,
            "nsweep": int(getattr(backend, "sweeps_per_bin", 250)),
        })
        atomic_json(state_path, state)
    while True:
        current = backend.analyze(ensemble, theta)
        diagnostic = None
        if hasattr(backend, "write_diagnostics"):
            diagnostic = backend.write_diagnostics(
                state_path.parent, ensemble, theta
            )
            point["green_median"] = diagnostic["green_median"]
            point["green_p95"] = diagnostic["green_p95"]
        attempt = _attempt_dict(current)
        if not point["attempts"] or point["attempts"][-1] != attempt:
            point["attempts"].append(attempt)
            atomic_json(state_path, state)
        if current.hard_failure:
            point["status"] = "hard_failure"
            point["hard_failure"] = current.hard_failure
            atomic_json(state_path, state)
            return None
        if not current.green_stability_pass:
            point["status"] = "green_stability_failed"
            point["hard_failure"] = (
                "Green stability exceeds 1e-8; shorten Nwrap and rerun"
            )
            atomic_json(state_path, state)
            return None
        if current.precision_ready:
            point["estimate"] = _estimate_dict(current)
            point["energy_ok"] = energy_ok(current.mean, approved_config())
            point["status"] = "energy_checked"
            atomic_json(state_path, state)
            print(
                f"{ensemble} theta={theta} E={current.mean:.8f} "
                f"sigma={current.sigma:.6f} "
                f"energy_ok={point['energy_ok']}",
                flush=True,
            )
            return current
        next_batch = len(point["batches"])
        nbin = choose_additional_nbin(
            current,
            chains=int(getattr(backend, "chains", 6)),
        )
        max_nbin = getattr(backend, "max_nbin", None)
        if max_nbin is not None:
            nbin = min(nbin, int(max_nbin))
        print(
            f"{ensemble} theta={theta} sigma={current.sigma:.6f}; "
            f"adding batch={next_batch} NBin={nbin}",
            flush=True,
        )
        backend.ensure_batch(
            ensemble, theta, next_batch, nbin,
            int(getattr(backend, "sweeps_per_bin", 250)),
        )
        point["batches"].append({
            "batch": next_batch, "nbin": nbin,
            "nsweep": int(getattr(backend, "sweeps_per_bin", 250)),
        })
        atomic_json(state_path, state)


def calibrate(
    backend: Any,
    *,
    results_root: Path,
    trial_manifest_sha256: str,
    alf_binary_sha256: str,
    include_ii: bool = True,
) -> dict[str, Any] | None:
    results_root.mkdir(parents=True, exist_ok=True)
    selected_path = results_root / "selected_projection.json"
    if selected_path.is_file():
        return json.loads(selected_path.read_text(encoding="utf-8"))
    state_path = results_root / "theta_scan.json"
    state = _load_state(state_path)
    cfg = approved_config()
    selected_theta: int | None = None
    ti_status = "target_reached"
    for theta in theta_candidates():
        current = _precision_loop(
            backend,
            ensemble="TI",
            theta=theta,
            state=state,
            state_path=state_path,
        )
        if current is None:
            _write_csv(results_root, state)
            return None
        if state["TI"][str(theta)]["energy_ok"]:
            selected_theta = theta
            break
    if selected_theta is None:
        selected_theta = 20
        ti_status = "max_theta_fallback"
    ti_estimate = state["TI"][str(selected_theta)]["estimate"]
    selected: dict[str, Any] = {
        "schema_version": 1,
        "ensemble_used_for_selection": "TI",
        "theta_star": selected_theta,
        "ltrot_star": ltrot(selected_theta, cfg),
        "nfield_star": ltrot(selected_theta, cfg) * cfg.lx * cfg.ly,
        "dt": cfg.dt,
        "beta": cfg.beta,
        "sigma_target": 0.005,
        "nwrap": int(getattr(backend, "nwrap", 5)),
        "energy_target": cfg.exact_energy,
        "energy_tolerance": 0.005,
        "status": ti_status,
        "ti_estimate": ti_estimate,
        "ii_confirmation": None,
        "trial_manifest_sha256": trial_manifest_sha256,
        "alf_binary_sha256": alf_binary_sha256,
        "completed_at": "",
    }
    if include_ii:
        ii = _precision_loop(
            backend,
            ensemble="II",
            theta=selected_theta,
            state=state,
            state_path=state_path,
        )
        if ii is None:
            _write_csv(results_root, state)
            return None
        selected["ii_confirmation"] = _estimate_dict(ii)
        if not state["II"][str(selected_theta)]["energy_ok"]:
            selected["status"] = "reference_confirmation_failed"
    selected["completed_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json(selected_path, selected)
    _write_csv(results_root, state)
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXECUTABLE)
    parser.add_argument("--trial-assets", type=Path, default=DEFAULT_TRIAL_ASSETS)
    parser.add_argument("--master-seed", type=int, default=900090)
    parser.add_argument("--chains", type=int, default=6)
    parser.add_argument("--initial-nbin", type=int, default=25)
    parser.add_argument("--max-nbin", type=int)
    parser.add_argument("--max-new-batches", type=int)
    parser.add_argument("--nwrap", type=int, default=5)
    parser.add_argument("--sweeps-per-bin", type=int, default=250)
    parser.add_argument(
        "--direct",
        action="store_true",
        help="run a serial/noMPI ALF executable without mpirun",
    )
    parser.add_argument("--ti-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    trial_manifest = args.trial_assets / "trial_manifest.json"
    backend = RealBackend(
        run_root=args.run_root,
        executable=args.executable.resolve(),
        trial_assets=args.trial_assets,
        master_seed=args.master_seed,
        chains=args.chains,
        launcher=() if args.direct else ("mpirun", "-np", "1"),
        initial_nbin=args.initial_nbin,
        max_nbin=args.max_nbin,
        max_new_batches=args.max_new_batches,
        nwrap=args.nwrap,
        sweeps_per_bin=args.sweeps_per_bin,
    )
    try:
        selected = calibrate(
            backend,
            results_root=args.results_root,
            trial_manifest_sha256=sha256_file(trial_manifest),
            alf_binary_sha256=sha256_file(args.executable),
            include_ii=not args.ti_only,
        )
    except BatchBudgetExhausted as exc:
        print(f"CALIBRATION_PENDING: {exc}", flush=True)
        return
    if selected is None:
        raise SystemExit("projection calibration stopped on a hard failure")
    print(json.dumps(selected, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
