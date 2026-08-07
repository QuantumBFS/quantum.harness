#!/usr/bin/env python3
"""Stream CPMC path-audit binaries into compact diagnostic tables."""

from __future__ import annotations

import argparse
import csv
import heapq
import math
import pathlib
import struct
from typing import Dict, Iterable, Iterator, List, Optional, Tuple


HEADER = struct.Struct("<8s12I3d2Q32x")
RECORD_V1 = struct.Struct("<Q5d2IbB6x")
RECORD_V2 = struct.Struct("<Q5d2IbBfBB")
RECORD = RECORD_V2
MAGIC = b"CPAUDIT\x00"
TRIAL_NAMES = {1: "rhf_x", 2: "rhf_y", 3: "uhf"}
PROPOSAL_NAMES = {1: "site", 2: "joint"}
ORDER_NAMES = {1: "row", 2: "reverse", 3: "sublattice", 4: "na"}
LN10 = math.log(10.0)


class LogAccumulator:
    def __init__(self) -> None:
        self.maximum = -math.inf
        self.scaled_sum = 0.0

    def add(self, log_value: float) -> None:
        if not math.isfinite(log_value):
            return
        if log_value > self.maximum:
            if math.isfinite(self.maximum):
                self.scaled_sum *= math.exp(self.maximum - log_value)
            self.maximum = log_value
        self.scaled_sum += math.exp(log_value - self.maximum)

    def log_value(self) -> float:
        if self.scaled_sum == 0.0:
            return -math.inf
        return self.maximum + math.log(self.scaled_sum)

    def value(self) -> float:
        log_value = self.log_value()
        return 0.0 if not math.isfinite(log_value) else math.exp(log_value)


def read_header(path: pathlib.Path) -> Dict[str, object]:
    with path.open("rb") as stream:
        raw = stream.read(HEADER.size)
    if len(raw) != HEADER.size:
        raise ValueError(f"truncated header: {path}")
    values = HEADER.unpack(raw)
    (
        magic,
        version,
        header_bytes,
        record_bytes,
        endian_marker,
        lx,
        ly,
        n_up,
        n_down,
        slices,
        trial,
        proposal,
        order,
        hopping,
        interaction,
        dt,
        expected_records,
        actual_records,
    ) = values
    if (
        magic != MAGIC
        or version not in (1, 2)
        or header_bytes != HEADER.size
        or record_bytes != RECORD.size
        or endian_marker != 0x01020304
    ):
        raise ValueError(f"unsupported path format: {path}")
    return {
        "lx": lx,
        "format_version": version,
        "ly": ly,
        "n_up": n_up,
        "n_down": n_down,
        "slices": slices,
        "trial": TRIAL_NAMES[trial],
        "proposal": PROPOSAL_NAMES[proposal],
        "order": ORDER_NAMES[order],
        "hopping": hopping,
        "interaction": interaction,
        "dt": dt,
        "expected_records": expected_records,
        "actual_records": actual_records,
    }


def iter_records(path: pathlib.Path) -> Iterator[Dict[str, object]]:
    header = read_header(path)
    record_format = (
        RECORD_V2 if int(header["format_version"]) >= 2 else RECORD_V1
    )
    expected = int(header["actual_records"])
    with path.open("rb") as stream:
        stream.seek(HEADER.size)
        for _ in range(expected):
            raw = stream.read(record_format.size)
            if len(raw) != record_format.size:
                raise ValueError(f"truncated record data: {path}")
            values = record_format.unpack(raw)
            yield {
                "config_id": values[0],
                "log_abs_d": values[1],
                "log_q": values[2],
                "log_abs_weight": values[3],
                "min_log_abs_weight": values[4],
                "min_abs_overlap": values[5],
                "argmin_weight_step": values[6],
                "first_rejected_step": values[7],
                "sign_d": values[8],
                "alive": bool(values[9]),
                "linear_bottleneck": (
                    values[10]
                    if int(header["format_version"]) >= 2
                    else 0.0
                ),
                "argmin_linear_slice": (
                    values[11]
                    if int(header["format_version"]) >= 2
                    else 0
                ),
            }
        if stream.read(1):
            raise ValueError(f"unexpected trailing record data: {path}")


def record_scores(
    record: Dict[str, object], log_total_abs_d: float
) -> Dict[str, Optional[float]]:
    if not bool(record["alive"]):
        return {"under_sampling": None, "bottleneck": None}
    log_q = float(record["log_q"])
    log_weight = float(record["log_abs_weight"])
    min_log_weight = float(record["min_log_abs_weight"])
    if not (
        math.isfinite(log_q)
        and math.isfinite(log_weight)
        and math.isfinite(min_log_weight)
    ):
        return {"under_sampling": None, "bottleneck": None}
    under_sampling = (
        float(record["log_abs_d"]) - log_total_abs_d - log_q
    ) / LN10
    bottleneck = float(record["linear_bottleneck"]) / LN10
    return {
        "under_sampling": under_sampling,
        "bottleneck": bottleneck,
    }


def sample_quantile(values: List[float], probability: float) -> float:
    if not values:
        return math.nan
    if probability < 0.0 or probability > 1.0:
        raise ValueError("quantile probability must be in [0,1]")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def push_top(
    heap: List[Tuple[float, int, Dict[str, object]]],
    score: float,
    record: Dict[str, object],
    limit: int,
) -> None:
    item = (score, int(record["config_id"]), record)
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif item[:2] > heap[0][:2]:
        heapq.heapreplace(heap, item)


def summarize_file(
    path: pathlib.Path, top_count: int, sample_limit: int
) -> Tuple[Dict[str, object], List[Dict[str, object]], List[Dict[str, object]]]:
    header = read_header(path)
    total = LogAccumulator()
    rejected = LogAccumulator()
    alive_count = 0
    negative_count = 0
    signed_sum = 0.0
    for record in iter_records(path):
        log_d = float(record["log_abs_d"])
        total.add(log_d)
        sign = int(record["sign_d"])
        if sign != 0 and math.isfinite(log_d):
            signed_sum += sign * math.exp(log_d)
        if bool(record["alive"]):
            alive_count += 1
        else:
            rejected.add(log_d)
        if sign < 0:
            negative_count += 1

    log_total = total.log_value()
    records = int(header["actual_records"])
    sample_stride = max(1, records // max(1, sample_limit))
    under_sample: List[float] = []
    bottleneck_sample: List[float] = []
    top_under: List[Tuple[float, int, Dict[str, object]]] = []
    top_bottleneck: List[Tuple[float, int, Dict[str, object]]] = []
    for ordinal, record in enumerate(iter_records(path)):
        scores = record_scores(record, log_total)
        under = scores["under_sampling"]
        bottleneck = scores["bottleneck"]
        if under is not None:
            push_top(top_under, under, record, top_count)
            if ordinal % sample_stride == 0:
                under_sample.append(under)
        if bottleneck is not None:
            push_top(top_bottleneck, bottleneck, record, top_count)
            if ordinal % sample_stride == 0:
                bottleneck_sample.append(bottleneck)

    total_value = total.value()
    rejected_fraction = (
        0.0 if total_value == 0.0 else rejected.value() / total_value
    )
    exact_under_max = max((item[0] for item in top_under), default=math.nan)
    exact_bottleneck_max = max(
        (item[0] for item in top_bottleneck), default=math.nan
    )
    summary = {
        "file": path.name,
        **header,
        "alive_records": alive_count,
        "survival_fraction": alive_count / records if records else math.nan,
        "negative_records": negative_count,
        "signed_sum_d": signed_sum,
        "absolute_sum_d": total_value,
        "rejected_absolute_mass_fraction": rejected_fraction,
        "under_sampling_p50": sample_quantile(under_sample, 0.50),
        "under_sampling_p90": sample_quantile(under_sample, 0.90),
        "under_sampling_p99": sample_quantile(under_sample, 0.99),
        "under_sampling_max": exact_under_max,
        "bottleneck_p50": sample_quantile(bottleneck_sample, 0.50),
        "bottleneck_p90": sample_quantile(bottleneck_sample, 0.90),
        "bottleneck_p99": sample_quantile(bottleneck_sample, 0.99),
        "bottleneck_max": exact_bottleneck_max,
        "quantile_sample_size": min(
            len(under_sample), len(bottleneck_sample)
        ),
    }

    def format_top(
        heap: List[Tuple[float, int, Dict[str, object]]], score_name: str
    ) -> List[Dict[str, object]]:
        rows = []
        for score, config_id, record in sorted(heap, reverse=True):
            rows.append(
                {
                    "file": path.name,
                    "trial": header["trial"],
                    "proposal": header["proposal"],
                    "order": header["order"],
                    "config_id": config_id,
                    score_name: score,
                    "log_abs_d": record["log_abs_d"],
                    "log_q": record["log_q"],
                    "log_abs_weight": record["log_abs_weight"],
                    "min_log_abs_weight": record[
                        "min_log_abs_weight"
                    ],
                    "argmin_weight_step": record["argmin_weight_step"],
                    "argmin_linear_slice": record[
                        "argmin_linear_slice"
                    ],
                    "min_abs_overlap": record["min_abs_overlap"],
                }
            )
        return rows

    return (
        summary,
        format_top(top_under, "under_sampling"),
        format_top(top_bottleneck, "bottleneck"),
    )


def write_csv(path: pathlib.Path, rows: Iterable[Dict[str, object]]) -> None:
    materialized = list(rows)
    if not materialized:
        return
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(materialized[0]))
        writer.writeheader()
        writer.writerows(materialized)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True, type=pathlib.Path)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--sample-limit", type=int, default=200_000)
    args = parser.parse_args()

    files = sorted(args.results.glob("paths_*.bin"))
    if not files:
        raise SystemExit("no paths_*.bin files found")
    summaries: List[Dict[str, object]] = []
    top_under: List[Dict[str, object]] = []
    top_bottleneck: List[Dict[str, object]] = []
    for path in files:
        print(f"summarizing {path.name}", flush=True)
        summary, under, bottleneck = summarize_file(
            path, args.top, args.sample_limit
        )
        summaries.append(summary)
        top_under.extend(under)
        top_bottleneck.extend(bottleneck)
    write_csv(args.results / "summary.csv", summaries)
    write_csv(args.results / "top_under_sampled.csv", top_under)
    write_csv(args.results / "top_bottlenecks.csv", top_bottleneck)
    print(
        f"wrote {args.results / 'summary.csv'} for {len(files)} files",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
