#!/usr/bin/env python3
"""Analyze charge gap minima across (L, U) and assess gapless point splitting.

Detects local minima in Δc(δ, Δ), computes split distance d(U), direction,
and finite-size trends. Generates CSV tables and a markdown report.

Usage:
    python scripts/analyze_results.py --results-dir ../../results/gapless-point-split
    python scripts/analyze_results.py --results-dir ... --eps 0.01 --output report.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
_RMH_GAP = _PROJECT.parent / "rmh_gap_landscape"
sys.path.insert(0, str(_RMH_GAP))
sys.path.insert(0, str(_HERE))  # for run_scan import

# Reuse minima detection from run_scan
from run_scan import detect_local_minima  # noqa: E402


# ---------------------------------------------------------------------------
# Load results
# ---------------------------------------------------------------------------

def load_coarse_results(results_dir: Path, L: int, U: float) -> dict | None:
    """Load a coarse scan NPZ. Returns dict with keys or None."""
    tag = f"U{U:.3f}".replace(".", "p")
    path = results_dir / f"L{L}" / "coarse" / f"gaps_{tag}.npz"
    if not path.exists():
        return None
    data = np.load(path, allow_pickle=False)
    return {
        "path": path,
        "delta": data["delta_values"],
        "Delta": data["Delta_values"],
        "Delta_c": data["Delta_c"],
        "Delta_s": data["Delta_s"],
        "Delta_MB": data["Delta_MB"],
        "L": int(data["L"][0]),
        "U": float(data["U"][0]),
    }


def load_refined_minima(results_dir: Path, L: int, U: float) -> list[dict]:
    """Load refined minima CSV if it exists."""
    tag = f"U{U:.3f}".replace(".", "p")
    path = results_dir / f"L{L}" / "refine" / f"minima_{tag}.csv"
    if not path.exists():
        return []
    import csv
    minima = []
    with open(path) as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            minima.append({
                "delta": float(row["delta"]),
                "Delta": float(row["Delta"]),
                "gap": float(row["gap"]),
                "hessian_eigvals": [float(row["hessian_eigval_0"]),
                                    float(row["hessian_eigval_1"])],
            })
    return minima


# ---------------------------------------------------------------------------
# Split metrics
# ---------------------------------------------------------------------------

def compute_split_metrics(all_minima: dict[tuple, list[dict]],
                          L_list: list[int], U_list: list[float]) -> list[dict]:
    """Compute split distance, direction, and count for each (L, U).

    Returns list of dicts (one per (L, U)) with split metrics.
    """
    rows = []
    for L in L_list:
        for U in U_list:
            key = (L, U)
            minima = all_minima.get(key, [])

            N = len(minima)
            row = {
                "L": L, "U": U, "N_minima": N,
                "delta_0": minima[0]["delta"] if N >= 1 else None,
                "Delta_0": minima[0]["Delta"] if N >= 1 else None,
                "gap_0": minima[0]["gap"] if N >= 1 else None,
                "delta_1": minima[1]["delta"] if N >= 2 else None,
                "Delta_1": minima[1]["Delta"] if N >= 2 else None,
                "gap_1": minima[1]["gap"] if N >= 2 else None,
            }

            if N >= 2:
                d_delta = minima[1]["delta"] - minima[0]["delta"]
                d_Delta = minima[1]["Delta"] - minima[0]["Delta"]
                d_split = np.sqrt(d_delta**2 + d_Delta**2)
                direction = np.arctan2(d_Delta, d_delta)
                row["d_split"] = d_split
                row["direction_rad"] = direction
                row["direction_deg"] = np.degrees(direction)
                row["d_delta"] = d_delta
                row["d_Delta"] = d_Delta
                row["mid_delta"] = (minima[0]["delta"] + minima[1]["delta"]) / 2
                row["mid_Delta"] = (minima[0]["Delta"] + minima[1]["Delta"]) / 2
            else:
                row["d_split"] = 0.0 if N == 1 else None
                row["direction_rad"] = None
                row["direction_deg"] = None
                row["d_delta"] = None
                row["d_Delta"] = None
                row["mid_delta"] = None
                row["mid_Delta"] = None

            # Curvature info from first minimum
            if N >= 1 and minima[0].get("hessian_eigvals"):
                row["hessian_min"] = min(minima[0]["hessian_eigvals"])
                row["hessian_max"] = max(minima[0]["hessian_eigvals"])
            else:
                row["hessian_min"] = None
                row["hessian_max"] = None

            rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze(results_dir: Path, eps: float = 0.01,
            merge_distance: float = 2.0) -> dict:
    """Run full analysis on all available results.

    Returns dict with all_minima, split_rows, and summary stats.
    """
    # Discover available (L, U) from results directory
    available = []
    for L_dir in sorted(results_dir.glob("L*")):
        if not L_dir.is_dir():
            continue
        L = int(L_dir.name[1:])
        coarse_dir = L_dir / "coarse"
        if not coarse_dir.exists():
            continue
        for npz_path in sorted(coarse_dir.glob("gaps_U*.npz")):
            # Extract U from filename
            stem = npz_path.stem  # e.g. gaps_U0p000
            U_str = stem.replace("gaps_U", "").replace("p", ".")
            try:
                U = float(U_str)
            except ValueError:
                continue
            available.append((L, U))

    if not available:
        print("No results found.")
        return {}

    L_list = sorted(set(a[0] for a in available))
    U_list = sorted(set(a[1] for a in available))

    print(f"Found results for L ∈ {L_list}, U ∈ {U_list}")
    print(f"Scanning with eps={eps}, merge_distance={merge_distance}\n")

    # Detect minima for each (L, U)
    all_minima: dict[tuple, list[dict]] = {}

    for L in L_list:
        print(f"{'='*48}")
        print(f"L = {L}")
        print(f"{'='*48}")
        for U in U_list:
            key = (L, U)
            # Prefer refined minima if available
            refined = load_refined_minima(results_dir, L, U)
            if refined:
                all_minima[key] = refined
                print(f"  U={U:.3f}: {len(refined)} minima (from refinement)")
                for k, m in enumerate(refined):
                    print(f"    min {k}: δ={m['delta']:+.6f}  Δ={m['Delta']:+.6f}  "
                          f"Δc={m['gap']:.6f}")
                continue

            # Otherwise detect from coarse
            data = load_coarse_results(results_dir, L, U)
            if data is None:
                print(f"  U={U:.3f}: no results")
                all_minima[key] = []
                continue

            minima = detect_local_minima(
                data["delta"], data["Delta"], data["Delta_c"],
                eps=eps, merge_distance=merge_distance,
            )
            all_minima[key] = minima
            print(f"  U={U:.3f}: {len(minima)} minima (from coarse)")
            for k, m in enumerate(minima):
                print(f"    min {k}: δ={m['delta']:+.6f}  Δ={m['Delta']:+.6f}  "
                      f"Δc={m['gap']:.6f}")

    # Compute split metrics
    split_rows = compute_split_metrics(all_minima, L_list, U_list)

    return {
        "all_minima": all_minima,
        "split_rows": split_rows,
        "L_list": L_list,
        "U_list": U_list,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(analysis: dict, output_path: Path) -> None:
    """Write a markdown report with split analysis."""
    split_rows = analysis["split_rows"]
    L_list = analysis["L_list"]
    U_list = analysis["U_list"]

    lines = []
    lines.append("# Charge Gapless Point Split Analysis")
    lines.append("")
    lines.append("## Summary Table")
    lines.append("")
    lines.append("| L | U | N_min | δ₀ | Δ₀ | Δc₀ | δ₁ | Δ₁ | Δc₁ | d_split | direction(°) |")
    lines.append("|---|----|----|----|----|----|----|----|----|----|----|")

    for row in split_rows:
        def fmt(v, prec=4):
            return f"{v:+.{prec}f}" if v is not None else "—"

        lines.append(
            f"| {row['L']} | {row['U']:.3f} | {row['N_minima']} | "
            f"{fmt(row['delta_0'], 6)} | {fmt(row['Delta_0'], 4)} | "
            f"{fmt(row['gap_0'], 6)} | "
            f"{fmt(row['delta_1'], 6)} | {fmt(row['Delta_1'], 4)} | "
            f"{fmt(row['gap_1'], 6)} | "
            f"{fmt(row['d_split'], 6)} | {fmt(row['direction_deg'], 1)} |"
        )

    lines.append("")
    lines.append("## Split Distance vs U")
    lines.append("")
    lines.append("| U | " + " | ".join(f"d(L={L})" for L in L_list) + " |")
    lines.append("|---|" + "|".join("----|" for _ in L_list) + "|")

    for U in U_list:
        vals = []
        for L in L_list:
            row = next((r for r in split_rows
                        if r["L"] == L and abs(r["U"] - U) < 1e-10), None)
            if row and row["d_split"] is not None:
                vals.append(f"{row['d_split']:.6f}")
            else:
                vals.append("—")
        lines.append(f"| {U:.3f} | " + " | ".join(vals) + " |")

    lines.append("")
    lines.append("## Finite-Size Analysis")
    lines.append("")

    # Check if split exists for each (L, U)
    for U in U_list:
        lines.append(f"### U = {U:.3f}")
        lines.append("")
        for L in L_list:
            row = next((r for r in split_rows
                        if r["L"] == L and abs(r["U"] - U) < 1e-10), None)
            if row is None:
                lines.append(f"- L={L}: no data")
            elif row["N_minima"] == 0:
                lines.append(f"- L={L}: no minima found below threshold")
            elif row["N_minima"] == 1:
                lines.append(f"- L={L}: **single minimum** at "
                             f"δ={row['delta_0']:+.6f}, "
                             f"Δ={row['Delta_0']:+.4f}, "
                             f"Δc={row['gap_0']:.6f}")
            else:
                lines.append(f"- L={L}: **{row['N_minima']} minima**, "
                             f"d_split = {row['d_split']:.6f}, "
                             f"direction = {row['direction_deg']:.1f}°")
                lines.append(f"  - min 0: δ={row['delta_0']:+.6f}, "
                             f"Δ={row['Delta_0']:+.4f}, "
                             f"Δc={row['gap_0']:.6f}")
                lines.append(f"  - min 1: δ={row['delta_1']:+.6f}, "
                             f"Δ={row['Delta_1']:+.4f}, "
                             f"Δc={row['gap_1']:.6f}")
        lines.append("")

    # Overall assessment
    lines.append("## Assessment")
    lines.append("")

    # Find cases with 2+ minima
    split_cases = [r for r in split_rows if r["N_minima"] >= 2]
    if not split_cases:
        lines.append("**No splitting detected.** ")
        lines.append("All (L, U) combinations show at most one charge gap minimum "
                      "in the scanned region. The gapless point at U=0 does NOT "
                      "split into two distinct minima at small U within the "
                      "resolution of this scan.")
        lines.append("")
        lines.append("This may be because:")
        lines.append("1. The splitting, if it exists, is below the scan resolution")
        lines.append("2. The splitting occurs at larger U than those scanned")
        lines.append("3. The charge gap truly has a single minimum for all U")
    else:
        # Check finite-size stability
        lines.append(f"**Splitting detected in {len(split_cases)} cases.**")
        lines.append("")
        for case in split_cases:
            lines.append(f"- L={case['L']}, U={case['U']:.3f}: "
                         f"d_split = {case['d_split']:.6f}")

        # Check if splitting is consistent across L
        U_with_split = set(r["U"] for r in split_cases)
        for U in U_with_split:
            cases_at_U = [r for r in split_cases if abs(r["U"] - U) < 1e-10]
            Ls = [r["L"] for r in cases_at_U]
            ds = [r["d_split"] for r in cases_at_U]
            if len(Ls) >= 2:
                # Check if d_split increases or decreases with L
                if all(d > 0 for d in ds):
                    trend = "increasing" if ds[-1] > ds[0] else "decreasing"
                    lines.append(f"  - U={U:.3f}: d_split {trend} with L "
                                 f"({dict(zip(Ls, ds))})")

        lines.append("")
        lines.append("### Finite-size stability")
        lines.append("")
        stable_cases = []
        for U in U_with_split:
            cases_at_U = [r for r in split_cases if abs(r["U"] - U) < 1e-10]
            if len(cases_at_U) >= 2:
                ds = np.array([r["d_split"] for r in cases_at_U])
                if ds[-1] > 0.8 * ds[0]:  # within 20% of smallest-L value
                    stable_cases.append(U)
                    lines.append(f"- U={U:.3f}: split appears **stable** across L")
                else:
                    lines.append(f"- U={U:.3f}: split **shrinks** with L "
                                 f"(possible finite-size artifact)")

        if stable_cases:
            lines.append("")
            lines.append("**The split appears to be a genuine thermodynamic "
                         "effect, not a finite-size artifact.**")
        else:
            lines.append("")
            lines.append("**The split may be a finite-size artifact** — it "
                         "shrinks with increasing L.")

    # Write
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to {output_path}")


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def write_csvs(analysis: dict, output_dir: Path) -> None:
    """Write minima_summary.csv and split_metrics.csv."""
    import csv

    output_dir.mkdir(parents=True, exist_ok=True)

    # Minima summary
    minima_path = output_dir / "minima_summary.csv"
    all_minima = analysis["all_minima"]
    with open(minima_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["L", "U", "min_index", "delta", "Delta", "gap",
                          "hessian_eigval_0", "hessian_eigval_1", "source"])
        for (L, U), minima in sorted(all_minima.items()):
            # Check if from refinement
            refined = load_refined_minima(
                Path(args.results_dir) if 'args' in dir() else
                output_dir.parent, L, U)
            source = "refined" if refined else "coarse"
            for k, m in enumerate(minima):
                hess = m.get("hessian_eigvals", [None, None])
                writer.writerow([L, f"{U:.3f}", k,
                                 f"{m['delta']:.8f}", f"{m['Delta']:.8f}",
                                 f"{m['gap']:.8f}",
                                 f"{hess[0]:.6f}" if hess[0] is not None else "",
                                 f"{hess[1]:.6f}" if hess[1] is not None else "",
                                 source])
    print(f"Minima summary: {minima_path}")

    # Split metrics
    split_path = output_dir / "split_metrics.csv"
    split_rows = analysis["split_rows"]
    if split_rows:
        fieldnames = list(split_rows[0].keys())
        with open(split_path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(split_rows)
        print(f"Split metrics: {split_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global args  # hack for write_csvs
    parser = argparse.ArgumentParser(
        description="Analyze charge gap minima and assess gapless point splitting")
    parser.add_argument("--results-dir", required=True,
                        help="Path to results/gapless-point-split/")
    parser.add_argument("--eps", type=float, default=0.01,
                        help="Gap threshold for candidate gapless points")
    parser.add_argument("--merge-distance", type=float, default=2.0,
                        help="Grid spacings for clustering minima")
    parser.add_argument("--output", default=None,
                        help="Report output path (default: results-dir/analysis/report.md)")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        sys.exit(1)

    analysis = analyze(results_dir, eps=args.eps,
                       merge_distance=args.merge_distance)

    if not analysis:
        print("No data to analyze.")
        sys.exit(1)

    # Write outputs
    output_dir = results_dir / "analysis"
    write_csvs(analysis, output_dir)

    report_path = Path(args.output) if args.output else output_dir / "report.md"
    generate_report(analysis, report_path)

    print("\nDone.")


if __name__ == "__main__":
    main()
