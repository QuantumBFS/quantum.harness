#!/usr/bin/env python3
import csv
import math
import random
import sys
from collections import defaultdict
from pathlib import Path


def read_blocks(root):
    grouped = defaultdict(list)
    for path in sorted((root / "cells").glob("*/blocks.csv")):
        summary = path.with_name("summary.csv")
        if not summary.exists():
            continue
        with summary.open() as handle:
            meta = next(csv.DictReader(handle))
        L = int(meta["L"])
        with path.open() as handle:
            for row in csv.DictReader(handle):
                grouped[L].append(
                    tuple(float(row[k]) for k in ("m2", "m4", "R0", "R2"))
                )
    return grouped


def observables(rows, L):
    n = len(rows)
    m2 = sum(r[0] for r in rows) / n
    m4 = sum(r[1] for r in rows) / n
    r0 = sum(r[2] for r in rows) / n
    r2 = sum(r[3] for r in rows) / n
    return m2 * m2 / m4, r2 - 2 * r0, L * L * m2


def bootstrap(grouped, nboot=4000, seed=20260730):
    rng = random.Random(seed)
    point = {L: observables(rows, L) for L, rows in grouped.items()}
    samples = {L: [[], [], []] for L in grouped}
    etas = []
    sizes = sorted(grouped)
    for _ in range(nboot):
        current = {}
        for L, rows in grouped.items():
            draw = [rows[rng.randrange(len(rows))] for _ in rows]
            current[L] = observables(draw, L)
            for j, value in enumerate(current[L]):
                samples[L][j].append(value)
        xs = [math.log(L) for L in sizes]
        ys = [math.log(current[L][2]) for L in sizes]
        xm = sum(xs) / len(xs)
        ym = sum(ys) / len(ys)
        slope = sum((x-xm)*(y-ym) for x, y in zip(xs, ys)) / sum(
            (x-xm)**2 for x in xs
        )
        etas.append(2-slope)
    return point, samples, etas


def mean_sd(values):
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((x-mean)**2 for x in values) / (len(values)-1))
    return mean, sd


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "results/nn_v3_20260730")
    grouped = read_blocks(root)
    if sorted(grouped) != [64, 128, 256]:
        raise SystemExit(f"incomplete sizes: {sorted(grouped)}")
    point, samples, etas = bootstrap(grouped)
    out = root / "analysis"
    out.mkdir(exist_ok=True)
    with (out / "nn_observables.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("L", "observable", "value", "bootstrap_se", "blocks"))
        for L in sorted(grouped):
            for name, value, draws in zip(("Qm", "Rp", "chi"), point[L], samples[L]):
                _, se = mean_sd(draws)
                writer.writerow((L, name, value, se, len(grouped[L])))
    eta_mean, eta_se = mean_sd(etas)
    with (out / "eta_fit.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("Lmin", "Lmax", "eta", "bootstrap_se", "bootstrap_replicas"))
        writer.writerow((64, 256, eta_mean, eta_se, len(etas)))
    print(f"eta={eta_mean:.8f} +/- {eta_se:.8f}", flush=True)


if __name__ == "__main__":
    main()
