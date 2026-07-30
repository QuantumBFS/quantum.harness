from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import os
import platform
import shutil
import socket
import time
import tomllib
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .fcidump_audit import audit_fcidump
from .orderings import (
    corrected_block2_ga_ordering,
    validate_ordering,
)
from .result_schema import validate_result_document


@dataclass(frozen=True)
class InstanceConfig:
    name: str
    filename: str
    sha256: str
    norb: int
    nelec: int
    ms2: int


@dataclass(frozen=True)
class DMRGConfig:
    symmetry: str
    spin: int
    seed: int
    threads: int
    stack_mem_gb: float
    bond_dimensions: tuple[int, ...]
    n_sweeps_per_m: int
    tolerance: float
    iprint: int
    stage_noise: float
    final_stage_noise: float
    stage_threshold: float
    final_stage_threshold: float
    tighten_final_stage: bool
    tighten_each_stage: bool


@dataclass(frozen=True)
class OrderingConfig:
    method: str
    ga_tasks: int
    ga_generations: int
    ga_configs: int | None
    ga_elite: int
    ga_clone_rate: float
    ga_mutate_rate: float


@dataclass(frozen=True)
class RunConfig:
    instance: InstanceConfig
    dmrg: DMRGConfig
    ordering: OrderingConfig
    references: dict[str, float]


@dataclass(frozen=True)
class SweepSchedule:
    noises: tuple[float, ...]
    thresholds: tuple[float, ...]


@dataclass(frozen=True)
class DMRGStage:
    bond_dimension: int
    energy_hartree: float
    discarded_weight: float | None
    wall_time_s: float
    rss_mb: float | None
    sweep_energy_hartree: float | None = None
    mps_norm: float | None = None


def limit_bond_dimensions(config: RunConfig, target_m: int) -> RunConfig:
    """Return a run configuration capped at one declared DMRG stage."""

    if target_m not in config.dmrg.bond_dimensions:
        raise ValueError(
            f"target M={target_m} is not in the declared bond-dimension ladder "
            f"{config.dmrg.bond_dimensions}"
        )
    dimensions = tuple(
        value for value in config.dmrg.bond_dimensions if value <= target_m
    )
    return replace(
        config,
        dmrg=replace(config.dmrg, bond_dimensions=dimensions),
    )


def load_resume_ordering(
    path: str | Path,
    *,
    n_orbitals: int,
    expected_method: str,
) -> tuple[tuple[int, ...], dict[str, Any]]:
    """Load the exact orbital permutation attached to an existing checkpoint."""

    ordering_path = Path(path)
    document = json.loads(ordering_path.read_text(encoding="utf-8"))
    recorded_method = str(document.get("method", "")).lower()
    if recorded_method != expected_method:
        raise ValueError(
            "ordering method changed across resume: "
            f"checkpoint={recorded_method!r}, config={expected_method!r}"
        )
    ordering = validate_ordering(document.get("permutation"), n_orbitals)
    return ordering, document


def validate_resume_stages(
    config: RunConfig,
    stages: list[DMRGStage],
) -> None:
    """Require completed checkpoints to be an exact prefix of the target ladder."""

    actual = tuple(stage.bond_dimension for stage in stages)
    expected = config.dmrg.bond_dimensions[: len(actual)]
    if actual != expected:
        raise ValueError(
            f"saved checkpoint stages {actual} are not a prefix of the "
            f"target bond-dimension ladder {config.dmrg.bond_dimensions}"
        )


def stage_schedule(
    *,
    n_sweeps: int,
    is_final: bool,
    final_tolerance: float,
    stage_noise: float = 1.0e-4,
    final_stage_noise: float = 1.0e-5,
    stage_threshold: float = 1.0e-6,
    final_stage_threshold: float = 1.0e-7,
) -> SweepSchedule:
    if n_sweeps < 2:
        raise ValueError("n_sweeps must leave at least two noise-free sweeps")
    noise = final_stage_noise if is_final else stage_noise
    noises = (noise,) * (n_sweeps - 2) + (0.0, 0.0)
    if is_final:
        thresholds = (final_stage_threshold,) * (n_sweeps - 2) + (
            final_tolerance,
            final_tolerance,
        )
    else:
        thresholds = (stage_threshold,) * n_sweeps
    return SweepSchedule(noises=noises, thresholds=thresholds)


def seed_block2_random(driver: Any, seed: int) -> None:
    driver.bw.b.Random.rand_seed(seed)


def normalized_mps_expectation(
    driver: Any,
    *,
    mpo: Any,
    ket: Any,
) -> tuple[float, float]:
    raw_energy = float(driver.expectation(ket, mpo, ket, iprint=0))
    norm = float(
        driver.expectation(ket, driver.get_identity_mpo(), ket, iprint=0)
    )
    if norm <= 0:
        raise ValueError(f"saved MPS has non-positive norm {norm}")
    return raw_energy / norm, norm


def _table(document: dict[str, Any], key: str) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"missing [{key}] table")
    return value


def load_config(path: str | Path) -> RunConfig:
    with Path(path).open("rb") as stream:
        document = tomllib.load(stream)
    instance_raw = _table(document, "instance")
    dmrg_raw = _table(document, "dmrg")
    ordering_raw = _table(document, "ordering")
    instance = InstanceConfig(
        name=str(instance_raw["name"]),
        filename=str(instance_raw["filename"]),
        sha256=str(instance_raw["sha256"]),
        norb=int(instance_raw["norb"]),
        nelec=int(instance_raw["nelec"]),
        ms2=int(instance_raw["ms2"]),
    )
    dmrg = DMRGConfig(
        symmetry=str(dmrg_raw.get("symmetry", "SU2")).upper(),
        spin=int(dmrg_raw.get("spin", 0)),
        seed=int(dmrg_raw.get("seed", 1234)),
        threads=int(dmrg_raw.get("threads", 8)),
        stack_mem_gb=float(dmrg_raw.get("stack_mem_gb", 8.0)),
        bond_dimensions=tuple(int(value) for value in dmrg_raw["bond_dimensions"]),
        n_sweeps_per_m=int(dmrg_raw.get("n_sweeps_per_m", 8)),
        tolerance=float(dmrg_raw.get("tolerance", 1.0e-9)),
        iprint=int(dmrg_raw.get("iprint", 1)),
        stage_noise=float(dmrg_raw.get("stage_noise", 1.0e-4)),
        final_stage_noise=float(dmrg_raw.get("final_stage_noise", 1.0e-5)),
        stage_threshold=float(dmrg_raw.get("stage_threshold", 1.0e-6)),
        final_stage_threshold=float(
            dmrg_raw.get("final_stage_threshold", 1.0e-7)
        ),
        tighten_final_stage=bool(dmrg_raw.get("tighten_final_stage", True)),
        tighten_each_stage=bool(dmrg_raw.get("tighten_each_stage", False)),
    )
    ordering = OrderingConfig(
        method=str(ordering_raw.get("method", "fiedler")).lower(),
        ga_tasks=int(ordering_raw.get("ga_tasks", 64)),
        ga_generations=int(ordering_raw.get("ga_generations", 10_000)),
        ga_configs=(
            int(ordering_raw["ga_configs"])
            if "ga_configs" in ordering_raw
            else None
        ),
        ga_elite=int(ordering_raw.get("ga_elite", 8)),
        ga_clone_rate=float(ordering_raw.get("ga_clone_rate", 0.1)),
        ga_mutate_rate=float(ordering_raw.get("ga_mutate_rate", 0.1)),
    )
    references_raw = document.get("references", {})
    references = {str(key): float(value) for key, value in references_raw.items()}

    if dmrg.symmetry not in {"SU2", "SZ"}:
        raise ValueError("dmrg.symmetry must be SU2 or SZ")
    if instance.ms2 == 0 and dmrg.symmetry == "SU2" and dmrg.spin != 0:
        raise ValueError("the confirmed MS2=0 setup targets the singlet spin=0 sector")
    if dmrg.spin < abs(instance.ms2) or (dmrg.spin - instance.nelec) % 2:
        raise ValueError("spin, MS2, and electron parity are inconsistent")
    if (
        not dmrg.bond_dimensions
        or any(value <= 0 for value in dmrg.bond_dimensions)
        or tuple(sorted(set(dmrg.bond_dimensions))) != dmrg.bond_dimensions
    ):
        raise ValueError("bond_dimensions must be positive and strictly increasing")
    if dmrg.threads < 1 or dmrg.stack_mem_gb <= 0:
        raise ValueError("threads and stack_mem_gb must be positive")
    if dmrg.n_sweeps_per_m < 2:
        raise ValueError("n_sweeps_per_m must be at least 2")
    if ordering.method not in {"none", "fiedler", "ga"}:
        raise ValueError("ordering.method must be none, fiedler, or ga")
    return RunConfig(
        instance=instance,
        dmrg=dmrg,
        ordering=ordering,
        references=references,
    )


def build_result_document(
    *,
    instance: str,
    norb: int,
    nelec: int,
    ms2: int,
    spin: int,
    input_sha256: str,
    ordering_method: str,
    ordering: list[int] | tuple[int, ...],
    stages: list[DMRGStage],
    status: str,
    references: dict[str, float] | None = None,
) -> dict[str, Any]:
    if not stages:
        raise ValueError("at least one completed DMRG stage is required")
    final = stages[-1]
    document = {
        "schema_version": 1,
        "status": status,
        "instance": instance,
        "method": "block2-dmrg",
        "sector": {
            "norb": norb,
            "nelec": nelec,
            "ms2": ms2,
            "spin": spin,
        },
        "input": {"sha256": input_sha256},
        "ordering": {
            "method": ordering_method,
            "permutation": list(ordering),
        },
        "stages": [asdict(stage) for stage in stages],
        "headline": {
            "kind": "finite_m_mps_expectation",
            "bond_dimension": final.bond_dimension,
            "energy_hartree": final.energy_hartree,
        },
        "references": references or {},
    }
    return validate_result_document(document)


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _run_metadata(config: RunConfig, config_path: Path, run_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "running",
        "started_at_utc": datetime.now(UTC).isoformat(),
        "instance": asdict(config.instance),
        "dmrg": asdict(config.dmrg),
        "ordering": asdict(config.ordering),
        "references": config.references,
        "paths": {
            "run_dir": str(run_dir.resolve()),
            "config_source": str(config_path.resolve()),
            "scratch": str((run_dir / "checkpoints" / "block2").resolve()),
        },
        "software": {
            "python": platform.python_version(),
            "block2": _package_version("block2"),
            "numpy": _package_version("numpy"),
            "scipy": _package_version("scipy"),
            "pyscf": _package_version("pyscf"),
        },
        "hardware": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpus": os.cpu_count(),
        },
        "stages": [],
    }


def _rss_mb() -> float | None:
    try:
        import psutil

        return float(psutil.Process().memory_info().rss / 1.0e6)
    except (ImportError, OSError):
        return None


def _write_sweep_rows(
    path: Path,
    *,
    bond_dimension: int,
    bond_dimensions: Any,
    discarded_weights: Any,
    energies: Any,
) -> None:
    import numpy as np

    bdims = np.asarray(bond_dimensions).ravel()
    dws = np.asarray(discarded_weights, dtype=float).ravel()
    ens = np.asarray(energies, dtype=float)
    if ens.ndim > 1:
        ens = ens[:, 0]
    ens = ens.ravel()
    count = min(len(bdims), len(dws), len(ens))
    rows = zip(
        range(max(0, count - len(ens)), count),
        bdims[-count:],
        dws[-count:],
        ens[-count:],
    )
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        if write_header:
            writer.writerow(
                [
                    "stage_bond_dimension",
                    "sweep_index",
                    "reported_bond_dimension",
                    "discarded_weight",
                    "energy_hartree",
                ]
            )
        for sweep_index, reported_bond_dimension, discarded_weight, energy in rows:
            writer.writerow(
                [
                    bond_dimension,
                    sweep_index,
                    int(reported_bond_dimension),
                    f"{float(discarded_weight):.17g}",
                    f"{float(energy):.17g}",
                ]
            )
        stream.flush()


def run_dmrg(
    config_path: str | Path,
    run_dir: str | Path,
    *,
    resume: bool = False,
    max_bond_dimension: int | None = None,
) -> dict[str, Any]:
    config_file = Path(config_path)
    run_path = Path(run_dir)
    config = load_config(config_file)
    if max_bond_dimension is not None:
        config = limit_bond_dimensions(config, max_bond_dimension)
    run_path.mkdir(parents=True, exist_ok=True)
    input_path = run_path / "inputs" / config.instance.filename
    audit = audit_fcidump(
        input_path,
        expected_norb=config.instance.norb,
        expected_nelec=config.instance.nelec,
        expected_ms2=config.instance.ms2,
        expected_sha256=config.instance.sha256,
    )
    copied_config = run_path / "config.toml"
    if not copied_config.exists() or not resume:
        shutil.copy2(config_file, copied_config)

    os.environ["OMP_NUM_THREADS"] = str(config.dmrg.threads)
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"

    import numpy as np
    from pyblock2.driver.core import DMRGDriver, SymmetryTypes

    np.random.seed(config.dmrg.seed)
    scratch = run_path / "checkpoints" / "block2"
    scratch.mkdir(parents=True, exist_ok=True)
    run_json_path = run_path / "run.json"
    if resume and run_json_path.exists():
        run_document = json.loads(run_json_path.read_text(encoding="utf-8"))
        run_document.setdefault("resume_history", []).append(
            {
                "resumed_at_utc": datetime.now(UTC).isoformat(),
                "previous_status": run_document.get("status"),
                "previous_headline": run_document.get("headline"),
            }
        )
        run_document["status"] = "running"
        run_document["dmrg"] = asdict(config.dmrg)
        run_document.pop("completed_at_utc", None)
        run_document.pop("failed_at_utc", None)
        run_document.pop("error", None)
        _write_json(run_json_path, run_document)
    else:
        run_document = _run_metadata(config, config_file, run_path)
        _write_json(run_json_path, run_document)
        (run_path / "sweeps.csv").unlink(missing_ok=True)

    symmetry_type = (
        SymmetryTypes.SU2 if config.dmrg.symmetry == "SU2" else SymmetryTypes.SZ
    )
    driver = DMRGDriver(
        scratch=str(scratch),
        symm_type=symmetry_type,
        n_threads=config.dmrg.threads,
        stack_mem=int(config.dmrg.stack_mem_gb * 1.0e9),
    )
    seed_block2_random(driver, config.dmrg.seed)
    stages = [DMRGStage(**stage) for stage in run_document.get("stages", [])]
    validate_resume_stages(config, stages)
    try:
        driver.read_fcidump(
            filename=str(input_path),
            pg="c1",
            iprint=config.dmrg.iprint,
        )
        if (
            int(driver.n_sites) != config.instance.norb
            or int(driver.n_elec) != config.instance.nelec
            or int(driver.spin) != config.instance.ms2
        ):
            raise ValueError("block2 FCIDUMP sector differs from the audited header")
        h1e = np.asarray(driver.h1e)
        g2e = driver.unpack_g2e(driver.g2e, n_sites=driver.n_sites)
        orbital_symmetries = (
            list(driver.orb_sym) if driver.orb_sym is not None else None
        )

        ordering_path = run_path / "ordering.json"
        checkpoint = scratch / "KET-mps_info.bin"
        if resume and checkpoint.exists():
            ordering, ordering_document = load_resume_ordering(
                ordering_path,
                n_orbitals=config.instance.norb,
                expected_method=config.ordering.method,
            )
        else:
            ga_document: dict[str, Any] | None = None
            if config.ordering.method == "none":
                ordering = tuple(range(config.instance.norb))
            elif config.ordering.method == "fiedler":
                ordering = validate_ordering(
                    driver.orbital_reordering(h1e, g2e, method="fiedler"),
                    config.instance.norb,
                )
            else:
                selection = corrected_block2_ga_ordering(
                    driver,
                    h1e,
                    g2e,
                    n_tasks=config.ordering.ga_tasks,
                    base_seed=config.dmrg.seed,
                    n_generations=config.ordering.ga_generations,
                    n_configs=config.ordering.ga_configs,
                    n_elite=config.ordering.ga_elite,
                    clone_rate=config.ordering.ga_clone_rate,
                    mutate_rate=config.ordering.ga_mutate_rate,
                )
                ordering = selection.ordering
                ga_document = {
                    "selected_cost": selection.cost,
                    "candidates": [
                        asdict(candidate) for candidate in selection.candidates
                    ],
                }

            ordering_document = {
                "method": config.ordering.method,
                "permutation": list(ordering),
                "ga": ga_document,
            }
            _write_json(ordering_path, ordering_document)
        run_document["ordering_result"] = ordering_document
        _write_json(run_json_path, run_document)

        index = np.asarray(ordering, dtype=int)
        h1e = h1e[np.ix_(index, index)]
        g2e = g2e[np.ix_(index, index, index, index)]
        if orbital_symmetries is not None:
            orbital_symmetries = [orbital_symmetries[value] for value in ordering]
        driver.initialize_system(
            n_sites=config.instance.norb,
            n_elec=config.instance.nelec,
            spin=config.dmrg.spin,
            orb_sym=orbital_symmetries,
        )
        mpo = driver.get_qc_mpo(
            h1e=h1e,
            g2e=g2e,
            ecore=driver.ecore,
            unpack_g2e=False,
            iprint=config.dmrg.iprint,
        )
        if resume and checkpoint.exists():
            ket = driver.load_mps(tag="KET", nroots=1)
        else:
            seed_block2_random(driver, config.dmrg.seed)
            ket = driver.get_random_mps(
                tag="KET",
                bond_dim=config.dmrg.bond_dimensions[0],
                nroots=1,
            )

        completed_dimensions = {stage.bond_dimension for stage in stages}
        for stage_index, bond_dimension in enumerate(config.dmrg.bond_dimensions):
            if bond_dimension in completed_dimensions:
                continue
            is_final = (
                config.dmrg.tighten_each_stage
                or (
                    config.dmrg.tighten_final_stage
                    and stage_index == len(config.dmrg.bond_dimensions) - 1
                )
            )
            schedule = stage_schedule(
                n_sweeps=config.dmrg.n_sweeps_per_m,
                is_final=is_final,
                final_tolerance=config.dmrg.tolerance,
                stage_noise=config.dmrg.stage_noise,
                final_stage_noise=config.dmrg.final_stage_noise,
                stage_threshold=config.dmrg.stage_threshold,
                final_stage_threshold=config.dmrg.final_stage_threshold,
            )
            print(
                f"starting M={bond_dimension} "
                f"({config.dmrg.n_sweeps_per_m} sweeps)",
                flush=True,
            )
            started = time.monotonic()
            energy = driver.dmrg(
                mpo,
                ket,
                n_sweeps=config.dmrg.n_sweeps_per_m,
                bond_dims=[bond_dimension] * config.dmrg.n_sweeps_per_m,
                noises=list(schedule.noises),
                thrds=list(schedule.thresholds),
                iprint=config.dmrg.iprint,
                tol=config.dmrg.tolerance,
            )
            wall_time = time.monotonic() - started
            bond_dimensions, discarded_weights, energies = driver.get_dmrg_results()
            dws = np.asarray(discarded_weights, dtype=float).ravel()
            ens = np.asarray(energies, dtype=float)
            if ens.ndim > 1:
                ens = ens[:, 0]
            sweep_energy = float(ens.ravel()[-1]) if ens.size else float(energy)
            final_dw = float(dws[-1]) if dws.size else None
            _write_sweep_rows(
                run_path / "sweeps.csv",
                bond_dimension=bond_dimension,
                bond_dimensions=bond_dimensions,
                discarded_weights=discarded_weights,
                energies=energies,
            )
            mps_energy, mps_norm = normalized_mps_expectation(
                driver,
                mpo=mpo,
                ket=ket,
            )
            stage = DMRGStage(
                bond_dimension=bond_dimension,
                energy_hartree=mps_energy,
                discarded_weight=final_dw,
                wall_time_s=round(wall_time, 3),
                rss_mb=round(value, 3) if (value := _rss_mb()) is not None else None,
                sweep_energy_hartree=sweep_energy,
                mps_norm=mps_norm,
            )
            stages.append(stage)
            run_document["stages"] = [asdict(value) for value in stages]
            run_document["last_updated_at_utc"] = datetime.now(UTC).isoformat()
            _write_json(run_json_path, run_document)
            print(
                f"finished M={bond_dimension}: E_mps={mps_energy:.12f} "
                f"E_sweep={sweep_energy:.12f} "
                f"dw={final_dw!s} wall={wall_time:.1f}s",
                flush=True,
            )

        result = build_result_document(
            instance=config.instance.name,
            norb=config.instance.norb,
            nelec=config.instance.nelec,
            ms2=config.instance.ms2,
            spin=config.dmrg.spin,
            input_sha256=audit.sha256,
            ordering_method=config.ordering.method,
            ordering=ordering,
            stages=stages,
            status="completed",
            references=config.references,
        )
        _write_json(run_path / "result.json", result)
        run_document["status"] = "completed"
        run_document["completed_at_utc"] = datetime.now(UTC).isoformat()
        run_document["headline"] = result["headline"]
        _write_json(run_json_path, run_document)
        return result
    except BaseException as exc:
        run_document["status"] = "failed"
        run_document["failed_at_utc"] = datetime.now(UTC).isoformat()
        run_document["error"] = {"type": type(exc).__name__, "message": str(exc)}
        _write_json(run_json_path, run_document)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Run staged block2 DMRG")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--max-bond-dimension",
        type=int,
        help="stop after this exact value in the configured M ladder",
    )
    args = parser.parse_args()
    result = run_dmrg(
        args.config,
        args.run_dir,
        resume=args.resume,
        max_bond_dimension=args.max_bond_dimension,
    )
    print(json.dumps(result["headline"], sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
