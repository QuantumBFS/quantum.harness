#!/usr/bin/env python3
"""Chain-aware ratio statistics for independent ALF projector replicas."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import json
import math
from pathlib import Path
import re
from typing import Iterable, Sequence


FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
SCALAR_LINE = re.compile(
    rf"^\s*(\d+)\s+\(\s*({FLOAT})\s*,\s*({FLOAT})\s*\)\s+({FLOAT})\s*$"
)


@dataclass(frozen=True)
class ReplicaData:
    chain: int
    batch: int
    seed: int
    theta: int
    ltrot: int
    energy: tuple[float, ...]
    kinetic: tuple[float, ...]
    potential: tuple[float, ...]
    particles: tuple[float, ...]
    signs: tuple[float, ...]
    max_green_precision: float
    green_location: tuple[int, int, int, int, int, int, int] = (
        0, 0, 0, 0, 0, 0, 0
    )


@dataclass(frozen=True)
class EnergyEstimate:
    mean: float
    sigma_bin: float
    sigma_replica: float
    sigma: float
    retained_bins: int
    replicas: int
    loo_min: float
    loo_max: float
    mean_sign: float
    negative_sign_bins: int
    precision_ready: bool
    hard_failure: str | None
    loo_stable: bool
    max_green_precision: float
    statistical_precision_pass: bool
    green_stability_pass: bool
    aggregated_bins: int


def _float(value: str) -> float:
    return float(value.replace("D", "E").replace("d", "e"))


def _parse_scalar(path: Path) -> tuple[tuple[float, ...], tuple[float, ...]]:
    values: list[float] = []
    signs: list[float] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        match = SCALAR_LINE.match(line)
        if match is None or int(match.group(1)) != 2:
            raise RuntimeError(f"cannot parse scalar {path}:{line_number}")
        value = _float(match.group(2))
        imaginary = _float(match.group(3))
        sign = _float(match.group(4))
        if abs(imaginary) > 1.0e-12:
            raise RuntimeError(f"non-real scalar in {path}:{line_number}")
        if not all(math.isfinite(item) for item in (value, sign)):
            raise RuntimeError(f"non-finite scalar in {path}:{line_number}")
        values.append(value)
        signs.append(sign)
    return tuple(values), tuple(signs)


def _info_value(info: str, label: str) -> float:
    match = re.search(
        rf"(?mi)^\s*{re.escape(label)}\s*:\s*({FLOAT})", info
    )
    if match is None:
        raise RuntimeError(f"missing info value: {label}")
    return _float(match.group(1))


def parse_replica(run_dir: Path, expected: dict) -> ReplicaData:
    parsed = {
        name: _parse_scalar(run_dir / filename)
        for name, filename in (
            ("energy", "Ener_scal"),
            ("kinetic", "Kin_scal"),
            ("potential", "Pot_scal"),
            ("particles", "Part_scal"),
        )
    }
    lengths = {len(item[0]) for item in parsed.values()}
    if lengths != {int(expected["nbin"])}:
        raise RuntimeError(
            f"expected {expected['nbin']} complete bins, found {sorted(lengths)}"
        )
    reference_signs = parsed["energy"][1]
    if any(item[1] != reference_signs for item in parsed.values()):
        raise RuntimeError("observable sign columns differ")
    for index, (energy, kinetic, potential, particle, sign) in enumerate(
        zip(
            parsed["energy"][0],
            parsed["kinetic"][0],
            parsed["potential"][0],
            parsed["particles"][0],
            reference_signs,
        )
    ):
        if abs(energy - kinetic - potential) > 1.0e-10:
            raise RuntimeError(f"E != K + V in bin {index}")
        if abs(sign) < 1.0e-15 or abs(particle / sign - 16.0) > 1.0e-10:
            raise RuntimeError(f"particle number != 16 in bin {index}")
    info = (run_dir / "info").read_text(encoding="utf-8")
    theta = int(round(_info_value(info, "Theta")))
    if theta != int(expected["theta"]):
        raise RuntimeError(f"Theta={theta}, expected {expected['theta']}")
    match = re.search(
        rf"(?mi)^\s*dtau,Ltrot_eff\s*:\s*({FLOAT})\s+(\d+)", info
    )
    if match is None:
        raise RuntimeError("missing dtau,Ltrot_eff")
    actual_ltrot = int(match.group(2))
    if actual_ltrot != int(expected["ltrot"]):
        raise RuntimeError(
            f"Ltrot={actual_ltrot}, expected {expected['ltrot']}"
        )
    seed_match = re.search(
        r"(?mi)^\s*No initial configuration,\s*Seed_in\s+(\d+)\s*$",
        info,
    )
    if seed_match is None or int(seed_match.group(1)) != int(expected["seed"]):
        actual_seed = seed_match.group(1) if seed_match else "missing"
        raise RuntimeError(
            f"seed={actual_seed}, expected {expected['seed']}"
        )
    precision_match = re.search(
        rf"(?mi)^\s*Precision Green\s+Mean,\s*Max\s*:\s*"
        rf"{FLOAT}\s+({FLOAT})",
        info,
    )
    if precision_match is None:
        raise RuntimeError("missing maximum Green precision")
    location_match = re.search(
        r"(?mi)^\s*Precision Green Max Location "
        r"\(bin,sweep,direction,slice,i,j,flavor\)\s*:\s*"
        r"(\d+)\s+(\d+)\s+(-?\d+)\s+(\d+)\s+"
        r"(\d+)\s+(\d+)\s+(\d+)",
        info,
    )
    location = (
        tuple(int(location_match.group(index)) for index in range(1, 8))
        if location_match is not None else (0, 0, 0, 0, 0, 0, 0)
    )
    return ReplicaData(
        chain=int(expected["chain"]),
        batch=int(expected["batch"]),
        seed=int(expected["seed"]),
        theta=theta,
        ltrot=actual_ltrot,
        energy=parsed["energy"][0],
        kinetic=parsed["kinetic"][0],
        potential=parsed["potential"][0],
        particles=parsed["particles"][0],
        signs=reference_signs,
        max_green_precision=_float(precision_match.group(1)),
        green_location=location,
    )


def _ratio(numerators: Iterable[float], denominators: Iterable[float]) -> float:
    numerator = math.fsum(numerators)
    denominator = math.fsum(denominators)
    if abs(denominator) < 1.0e-15:
        raise RuntimeError("ratio denominator vanishes")
    return numerator / denominator


def _jackknife_error(values: Sequence[float]) -> float:
    if len(values) < 2:
        return math.inf
    center = math.fsum(values) / len(values)
    return math.sqrt(
        (len(values) - 1) / len(values)
        * math.fsum((value - center) ** 2 for value in values)
    )


def _failure(
    message: str,
    retained_bins: int,
    replica_count: int,
    negative: int,
    mean_sign: float,
) -> EnergyEstimate:
    return EnergyEstimate(
        mean=math.nan,
        sigma_bin=math.inf,
        sigma_replica=math.inf,
        sigma=math.inf,
        retained_bins=retained_bins,
        replicas=replica_count,
        loo_min=math.nan,
        loo_max=math.nan,
        mean_sign=mean_sign,
        negative_sign_bins=negative,
        precision_ready=False,
        hard_failure=message,
        loo_stable=False,
        max_green_precision=math.nan,
        statistical_precision_pass=False,
        green_stability_pass=False,
        aggregated_bins=retained_bins,
    )


def aggregate_bins(
    replicas: Sequence[ReplicaData],
) -> list[dict[str, float | int]]:
    """Combine equal-numbered bins across chains before taking ratios."""
    grouped: dict[int, dict[int, ReplicaData]] = {}
    for item in replicas:
        batch = grouped.setdefault(item.batch, {})
        if item.chain in batch:
            raise RuntimeError(
                f"duplicate chain {item.chain} in batch {item.batch}"
            )
        batch[item.chain] = item
    rows: list[dict[str, float | int]] = []
    for batch_id, by_chain in sorted(grouped.items()):
        chains = sorted(by_chain)
        if chains != list(range(len(chains))):
            raise RuntimeError(
                f"batch {batch_id} chain slots are not contiguous"
            )
        lengths = {len(item.energy) for item in by_chain.values()}
        if len(lengths) != 1:
            raise RuntimeError(
                f"batch {batch_id} chains have different bin counts"
            )
        number_bins = lengths.pop()
        for bin_index in range(1, number_bins):
            energy = math.fsum(
                by_chain[chain].energy[bin_index] for chain in chains
            )
            kinetic = math.fsum(
                by_chain[chain].kinetic[bin_index] for chain in chains
            )
            potential = math.fsum(
                by_chain[chain].potential[bin_index] for chain in chains
            )
            particles = math.fsum(
                by_chain[chain].particles[bin_index] for chain in chains
            )
            sign = math.fsum(
                by_chain[chain].signs[bin_index] for chain in chains
            )
            if abs(sign) < 1.0e-15:
                raise RuntimeError("cross-chain bin denominator vanishes")
            rows.append({
                "batch": batch_id,
                "bin": bin_index,
                "chains": len(chains),
                "energy_numerator": energy,
                "kinetic_numerator": kinetic,
                "potential_numerator": potential,
                "particle_numerator": particles,
                "sign_denominator": sign,
                "energy": energy / sign,
                "kinetic": kinetic / sign,
                "potential": potential / sign,
                "particles": particles / sign,
            })
    return rows


def leave_one_chain_values(
    replicas: Sequence[ReplicaData],
) -> list[tuple[int, float]]:
    chains = sorted({item.chain for item in replicas})
    chain_sums = {
        chain: (
            math.fsum(
                item.energy[index]
                for item in replicas if item.chain == chain
                for index in range(1, len(item.energy))
            ),
            math.fsum(
                item.signs[index]
                for item in replicas if item.chain == chain
                for index in range(1, len(item.signs))
            ),
        )
        for chain in chains
    }
    total_energy = math.fsum(value[0] for value in chain_sums.values())
    total_sign = math.fsum(value[1] for value in chain_sums.values())
    return [
        (
            chain,
            (total_energy - chain_sums[chain][0])
            / (total_sign - chain_sums[chain][1]),
        )
        for chain in chains
    ]


def estimate_energy(replicas: Sequence[ReplicaData]) -> EnergyEstimate:
    ordered = sorted(replicas, key=lambda item: (item.chain, item.batch))
    chains = sorted({item.chain for item in ordered})
    all_signs = [sign for item in ordered for sign in item.signs]
    negative = sum(sign < 0.0 for sign in all_signs)
    mean_sign = (
        math.fsum(all_signs) / len(all_signs) if all_signs else math.nan
    )
    seeds = [item.seed for item in ordered]
    if len(seeds) != len(set(seeds)):
        return _failure(
            "duplicate seed across independent chain segments",
            0, len(chains), negative, mean_sign,
        )
    if negative:
        return _failure(
            "negative sign bin encountered",
            0, len(chains), negative, mean_sign,
        )
    if not ordered or len(chains) < 6 or chains != list(range(len(chains))):
        return _failure(
            "at least six contiguous chain slots are required",
            0, len(chains), negative, mean_sign,
        )
    for item in ordered:
        lengths = {
            len(item.energy), len(item.kinetic), len(item.potential),
            len(item.particles), len(item.signs),
        }
        scalars = (
            *item.energy, *item.kinetic, *item.potential, *item.particles,
            *item.signs, item.max_green_precision,
        )
        if len(lengths) != 1 or len(item.energy) < 2:
            return _failure(
                "incomplete replica segment",
                0, len(chains), negative, mean_sign,
            )
        if not all(math.isfinite(value) for value in scalars):
            return _failure(
                "non-finite replica data",
                0, len(chains), negative, mean_sign,
            )
        for energy, kinetic, potential, particle, sign in zip(
            item.energy, item.kinetic, item.potential,
            item.particles, item.signs,
        ):
            if abs(energy - kinetic - potential) > 1.0e-10:
                return _failure(
                    "E != K + V",
                    0, len(chains), negative, mean_sign,
                )
            if abs(sign) < 1.0e-15 \
                    or abs(particle / sign - 16.0) > 1.0e-10:
                return _failure(
                    "particle number != 16",
                    0, len(chains), negative, mean_sign,
                )
    try:
        bins = aggregate_bins(ordered)
    except RuntimeError as exc:
        return _failure(str(exc), 0, len(chains), negative, mean_sign)
    retained_bins = len(bins)
    if retained_bins < 2:
        return _failure(
            "at least two cross-chain measurement bins are required",
            retained_bins, len(chains), negative, mean_sign,
        )
    total_energy = math.fsum(
        float(row["energy_numerator"]) for row in bins
    )
    total_sign = math.fsum(
        float(row["sign_denominator"]) for row in bins
    )
    mean = total_energy / total_sign
    leave_bin = [
        (
            total_energy - float(row["energy_numerator"])
        ) / (
            total_sign - float(row["sign_denominator"])
        )
        for row in bins
    ]
    sigma_bin = _jackknife_error(leave_bin)

    leave_replica = [
        value for _chain, value in leave_one_chain_values(ordered)
    ]
    sigma_replica = _jackknife_error(leave_replica)
    sigma = sigma_bin
    loo_min = min(leave_replica)
    loo_max = max(leave_replica)
    loo_stable = (
        max(abs(value - mean) for value in leave_replica)
        <= 3.0 * sigma + 1.0e-15
    )
    maximum_precision = max(item.max_green_precision for item in ordered)
    statistical_pass = (
        retained_bins >= 20 and sigma <= 0.005
        and mean_sign >= 0.999999
    )
    green_pass = maximum_precision <= 1.0e-8
    ready = statistical_pass and green_pass
    return EnergyEstimate(
        mean=mean,
        sigma_bin=sigma_bin,
        sigma_replica=sigma_replica,
        sigma=sigma,
        retained_bins=retained_bins,
        replicas=len(chains),
        loo_min=loo_min,
        loo_max=loo_max,
        mean_sign=mean_sign,
        negative_sign_bins=negative,
        precision_ready=ready,
        hard_failure=None,
        loo_stable=loo_stable,
        max_green_precision=maximum_precision,
        statistical_precision_pass=statistical_pass,
        green_stability_pass=green_pass,
        aggregated_bins=retained_bins,
    )


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def write_diagnostics(
    replicas: Sequence[ReplicaData],
    output_dir: Path,
    *,
    ensemble: str,
    theta: int,
) -> dict[str, object]:
    """Write identical raw/bin/jackknife/Green products for TI and II."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ordered = sorted(replicas, key=lambda item: (item.batch, item.chain))
    estimate = estimate_energy(ordered)
    aggregate = aggregate_bins(ordered)
    leave_chain = leave_one_chain_values(ordered)

    raw_path = output_dir / "raw_chain_bins.csv"
    with raw_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow((
            "ensemble", "theta", "batch", "chain", "bin",
            "thermalization_bin", "energy_numerator",
            "kinetic_numerator", "potential_numerator",
            "particle_numerator", "sign_denominator", "energy_ratio",
        ))
        for item in ordered:
            for bin_index in range(len(item.energy)):
                writer.writerow((
                    ensemble, theta, item.batch, item.chain, bin_index,
                    int(bin_index == 0),
                    format(item.energy[bin_index], ".17g"),
                    format(item.kinetic[bin_index], ".17g"),
                    format(item.potential[bin_index], ".17g"),
                    format(item.particles[bin_index], ".17g"),
                    format(item.signs[bin_index], ".17g"),
                    format(
                        item.energy[bin_index] / item.signs[bin_index],
                        ".17g",
                    ),
                ))

    aggregate_path = output_dir / "cross_chain_bins.csv"
    with aggregate_path.open("w", newline="", encoding="utf-8") as handle:
        fields = list(aggregate[0])
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(aggregate)

    leave_path = output_dir / "leave_one_chain.csv"
    with leave_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("omitted_chain", "energy", "deviation_from_total"))
        for chain, value in leave_chain:
            writer.writerow((
                chain, format(value, ".17g"),
                format(value - estimate.mean, ".17g"),
            ))

    green_path = output_dir / "green_stability.csv"
    green_rows = []
    by_chain = {
        chain: max(
            (item for item in ordered if item.chain == chain),
            key=lambda item: item.max_green_precision,
        )
        for chain in sorted({item.chain for item in ordered})
    }
    for chain, item in by_chain.items():
        (
            bin_index, sweep, direction, slice_index,
            row, column, flavor,
        ) = item.green_location
        green_rows.append({
            "batch": item.batch,
            "chain": chain,
            "max_delta_g": item.max_green_precision,
            "pass_1e-8": item.max_green_precision <= 1.0e-8,
            "bin": bin_index,
            "sweep": sweep,
            "direction": direction,
            "slice": slice_index,
            "i": row,
            "j": column,
            "flavor": flavor,
        })
    with green_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(green_rows[0]))
        writer.writeheader()
        writer.writerows(green_rows)

    green_values = [
        item.max_green_precision for item in by_chain.values()
    ]
    failing = [
        row for row in green_rows if not bool(row["pass_1e-8"])
    ]
    summary: dict[str, object] = {
        "schema_version": 1,
        "ensemble": ensemble,
        "theta": theta,
        "chains": len({item.chain for item in ordered}),
        "measurement_bins_after_thermalization": estimate.aggregated_bins,
        "thermalization_bins_per_chain_segment": 1,
        "mean_energy": estimate.mean,
        "energy_error_cross_chain_bins": estimate.sigma,
        "statistical_precision_pass": estimate.statistical_precision_pass,
        "green_stability_pass": estimate.green_stability_pass,
        "mean_sign": estimate.mean_sign,
        "leave_one_chain_jackknife_error": estimate.sigma_replica,
        "leave_one_chain_min": estimate.loo_min,
        "leave_one_chain_max": estimate.loo_max,
        "leave_one_chain_stable_3sigma": estimate.loo_stable,
        "green_max": max(green_values),
        "green_median": _percentile(green_values, 0.5),
        "green_p95": _percentile(green_values, 0.95),
        "green_failed_chain_locations": failing,
        "files": {
            "raw_chain_bins": str(raw_path.resolve()),
            "cross_chain_bins": str(aggregate_path.resolve()),
            "leave_one_chain": str(leave_path.resolve()),
            "green_stability": str(green_path.resolve()),
        },
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def choose_additional_nbin(
    estimate: EnergyEstimate,
    chains: int = 6,
    target: float = 0.005,
) -> int:
    if chains <= 0 or target <= 0.0:
        raise ValueError("chains and target must be positive")
    if estimate.retained_bins <= 0 or not math.isfinite(estimate.sigma):
        additional = 20
    else:
        growth = max(1.5, (estimate.sigma / target) ** 2)
        additional = max(
            20,
            math.ceil(estimate.retained_bins * (growth - 1.0)),
        )
    return 1 + additional
