#!/usr/bin/env python3
"""Render the frozen cutoff data and competing extrapolations as standalone SVG."""

import csv
import math
import os
import re
import sys


root = sys.argv[1]
analysis = os.path.join(root, "results", "track_a_cutoff_analysis_20260730")
base_analysis = os.path.join(root, "results", "track_a_20260727", "analysis")
figure_dir = os.path.join(root, "reports", "figures")
os.makedirs(figure_dir, exist_ok=True)


def read_csv(name):
    with open(os.path.join(analysis, name), encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


critical = read_csv("combined_critical.csv")
fits = read_csv("model_fits.csv")
forecasts = read_csv("distinguishable_size.csv")
extension_fits = read_csv("extension_comparison_fits.csv")
with open(os.path.join(base_analysis, "aggregated.csv"), encoding="utf-8") as handle:
    base_rows = list(csv.DictReader(handle))
colors = {1.75: "#2563eb", 1.875: "#16a34a", 2.0: "#dc2626", 2.5: "#7c3aed"}


def match_figure_two_font_scale(content, width):
    """Compensate SVG text for downscaling to Figure 2's display width."""
    scale = width / 660.0

    def scaled(match):
        size = float(match.group(1)) * scale
        return f'font-size="{size:.1f}"'

    return re.sub(r'font-size="([0-9.]+)"', scaled, content)


def sx(log_l, x0, width, lo=6, hi=11):
    return x0 + (log_l - lo) / (hi - lo) * width


def sy(value, y0, height, lo, hi):
    return y0 + height - (value - lo) / (hi - lo) * height


def finite_size_figure():
    width, height = 1120, 430
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="560" y="27" text-anchor="middle" font-family="sans-serif" font-size="18">中心临界点的有限尺寸流</text>',
    ]
    panels = [("Rp", "Rₚ", -0.64, 0.08), ("Qm", "Qₘ", 0.68, 0.88)]
    for i, sigma in enumerate(colors):
        x = 185 + 170 * i
        svg.append(f'<line x1="{x}" y1="57" x2="{x+28}" y2="57" stroke="{colors[sigma]}" stroke-width="3"/>')
        svg.append(f'<text x="{x+36}" y="62" font-family="sans-serif" font-size="12">σ={sigma:g}</text>')
    for p, (obs, label, ymin, ymax) in enumerate(panels):
        x0, y0, pw, ph = 70 + 545 * p, 82, 450, 273
        svg.append(f'<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="none" stroke="#555"/>')
        for tick in range(6, 12):
            x = sx(tick, x0, pw)
            svg.append(f'<line x1="{x:.1f}" y1="{y0+ph}" x2="{x:.1f}" y2="{y0+ph+5}" stroke="#555"/>')
            svg.append(f'<text x="{x:.1f}" y="{y0+ph+22}" text-anchor="middle" font-family="sans-serif" font-size="12">{2**tick}</text>')
        for j in range(5):
            val = ymin + (ymax - ymin) * j / 4
            y = sy(val, y0, ph, ymin, ymax)
            svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+pw}" y2="{y:.1f}" stroke="#e5e7eb"/>')
            svg.append(f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{val:.2f}</text>')
        anchor = 0.0 if obs == "Rp" else 0.857
        y_anchor = sy(anchor, y0, ph, ymin, ymax)
        svg.append(f'<line x1="{x0}" y1="{y_anchor:.1f}" x2="{x0+pw}" y2="{y_anchor:.1f}" stroke="#111" stroke-dasharray="6,5"/>')
        svg.append(f'<text x="{x0+pw-12}" y="{y_anchor-11:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">短程锚点</text>')
        svg.append(f'<text x="{x0+pw/2}" y="{height-22}" text-anchor="middle" font-family="sans-serif" font-size="12">L</text>')
        svg.append(
            f'<text x="{x0-49}" y="{y0+ph/2}" text-anchor="middle" font-family="sans-serif" '
            f'font-size="12" transform="rotate(-90 {x0-49} {y0+ph/2})">{label}</text>'
        )
        for sigma in colors:
            rows = sorted(
                (r for r in critical if float(r["sigma"]) == sigma and r["observable"] == obs),
                key=lambda r: int(r["L"]),
            )
            points = []
            for row in rows:
                x = sx(math.log2(int(row["L"])), x0, pw)
                value = float(row["value"])
                y = sy(value, y0, ph, ymin, ymax)
                points.append((x, y))
                if row["se"] != "NaN":
                    err = float(row["se"])
                    y1 = sy(value - err, y0, ph, ymin, ymax)
                    y2 = sy(value + err, y0, ph, ymin, ymax)
                    svg.append(f'<line x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y2:.1f}" stroke="{colors[sigma]}"/>')
                svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{colors[sigma]}"/>')
            svg.append(
                f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in points)}" '
                f'fill="none" stroke="{colors[sigma]}" stroke-width="2"/>'
            )
    svg.append("</svg>")
    return "\n".join(svg)


def fit_value(model, limit, p1, p2, length):
    if model == "power":
        return limit + p1 * length ** (-p2)
    return limit + p1 / math.log(length / p2)


def extrapolation_figure():
    width, height = 1120, 760
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="560" y="27" text-anchor="middle" font-family="sans-serif" font-size="18">幂律与对数修正的竞争外推（Lₘᵢₙ=64）</text>',
    ]
    panels = [
        (1.875, "Rp", "σ=1.875，Rₚ", -0.50, 0.68),
        (2.0, "Rp", "σ=2.0，Rₚ", -0.36, 0.80),
        (1.875, "Qm", "σ=1.875，Qₘ", 0.70, 1.08),
        (2.0, "Qm", "σ=2.0，Qₘ", 0.74, 1.12),
    ]
    for p, (sigma, obs, title, ymin, ymax) in enumerate(panels):
        col, row = p % 2, p // 2
        x0, y0, pw, ph = 70 + 545 * col, 55 + 350 * row, 450, 265
        svg.append(f'<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="none" stroke="#555"/>')
        for tick in (6, 8, 10, 12, 14, 16):
            x = x0 + (tick - 6) / 10 * pw
            svg.append(f'<line x1="{x:.1f}" y1="{y0+ph}" x2="{x:.1f}" y2="{y0+ph+5}" stroke="#555"/>')
            svg.append(f'<text x="{x:.1f}" y="{y0+ph+20}" text-anchor="middle" font-family="sans-serif" font-size="12">{2**tick}</text>')
        for j in range(5):
            value = ymin + (ymax - ymin) * j / 4
            y = sy(value, y0, ph, ymin, ymax)
            svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+pw}" y2="{y:.1f}" stroke="#e5e7eb"/>')
            svg.append(f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{value:.2f}</text>')
        svg.append(f'<text x="{x0+8}" y="{y0+18}" font-family="sans-serif" font-size="13">{title.split("，")[0]}</text>')
        svg.append(f'<text x="{x0+pw/2}" y="{y0+ph+40}" text-anchor="middle" font-family="sans-serif" font-size="12">L</text>')
        ylabel = "Rₚ" if obs == "Rp" else "Qₘ"
        svg.append(
            f'<text x="{x0-49}" y="{y0+ph/2}" text-anchor="middle" font-family="sans-serif" '
            f'font-size="12" transform="rotate(-90 {x0-49} {y0+ph/2})">{ylabel}</text>'
        )
        svg.append(f'<line x1="{x0+20}" y1="{y0+36}" x2="{x0+44}" y2="{y0+36}" stroke="#0f766e" stroke-width="2"/>')
        svg.append(f'<text x="{x0+49}" y="{y0+40}" font-family="sans-serif" font-size="12">power</text>')
        svg.append(f'<line x1="{x0+180}" y1="{y0+36}" x2="{x0+204}" y2="{y0+36}" stroke="#c2410c" stroke-width="2"/>')
        svg.append(f'<text x="{x0+209}" y="{y0+40}" font-family="sans-serif" font-size="12">log</text>')
        for model, color in (("power", "#0f766e"), ("marginal", "#c2410c")):
            fit = next(
                r
                for r in fits
                if float(r["sigma"]) == sigma
                and r["observable"] == obs
                and int(r["Lmin"]) == 64
                and r["model"] == model
            )
            limit, p1, p2 = float(fit["limit"]), float(fit["p1"]), float(fit["p2"])
            points = []
            for step in range(121):
                log_l = 6 + 10 * step / 120
                length = 2**log_l
                value = fit_value(model, limit, p1, p2, length)
                x = x0 + (log_l - 6) / 10 * pw
                y = sy(value, y0, ph, ymin, ymax)
                points.append((x, max(y0, min(y0 + ph, y))))
            svg.append(
                f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in points)}" '
                f'fill="none" stroke="{color}" stroke-width="2"/>'
            )
        rows = sorted(
            (r for r in critical if float(r["sigma"]) == sigma and r["observable"] == obs),
            key=lambda r: int(r["L"]),
        )
        for datum in rows:
            log_l = math.log2(int(datum["L"]))
            x = x0 + (log_l - 6) / 10 * pw
            value = float(datum["value"])
            y = sy(value, y0, ph, ymin, ymax)
            if datum["se"] != "NaN":
                err = float(datum["se"])
                svg.append(
                    f'<line x1="{x:.1f}" y1="{sy(value-err, y0, ph, ymin, ymax):.1f}" '
                    f'x2="{x:.1f}" y2="{sy(value+err, y0, ph, ymin, ymax):.1f}" stroke="#111"/>'
                )
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#111"/>')
        measured_edge = x0 + (11 - 6) / 10 * pw
        svg.append(f'<line x1="{measured_edge:.1f}" y1="{y0}" x2="{measured_edge:.1f}" y2="{y0+ph}" stroke="#777" stroke-dasharray="4,4"/>')
        svg.append(f'<text x="{measured_edge+5:.1f}" y="{y0+ph-7}" font-family="sans-serif" font-size="9">预测区</text>')
    svg.append("</svg>")
    return "\n".join(svg)


def eta_scaling_figure():
    width, height = 900, 490
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="450" y="27" text-anchor="middle" font-family="sans-serif" font-size="18">χ(L)/L² 的临界幂律拟合</text>',
    ]
    x0, y0, pw, ph = 90, 55, 740, 345
    svg.append(f'<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="none" stroke="#555"/>')
    for tick in (64, 128, 256, 512):
        x = x0 + (math.log2(tick) - 6) / 3 * pw
        svg.append(f'<line x1="{x:.1f}" y1="{y0+ph}" x2="{x:.1f}" y2="{y0+ph+5}" stroke="#555"/>')
        svg.append(f'<text x="{x:.1f}" y="{y0+ph+22}" text-anchor="middle" font-family="sans-serif" font-size="12">{tick}</text>')
    logy_min, logy_max = math.log10(0.025), math.log10(0.35)
    for tick in (0.03, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3):
        y = sy(math.log10(tick), y0, ph, logy_min, logy_max)
        svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+pw}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        svg.append(f'<text x="{x0-9}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{tick:g}</text>')
    svg.append(f'<text x="{x0+pw/2}" y="{height-24}" text-anchor="middle" font-family="sans-serif" font-size="12">L</text>')
    svg.append(
        f'<text x="28" y="{y0+ph/2}" text-anchor="middle" font-family="sans-serif" font-size="12" '
        f'transform="rotate(-90 28 {y0+ph/2})">χ/L²</text>'
    )
    bcs = {1.75: 0.329136, 1.875: 0.336985, 2.0: 0.344439, 2.5: 0.369446}
    for idx, sigma in enumerate(colors):
        rows = sorted(
            (
                r
                for r in base_rows
                if abs(float(r["sigma"]) - sigma) < 1e-9
                and abs(float(r["beta"]) - bcs[sigma]) < 1e-9
            ),
            key=lambda r: int(r["L"]),
        )
        points = []
        for datum in rows:
            length = int(datum["L"])
            value = float(datum["chi"]) / length**2
            x = x0 + (math.log2(length) - 6) / 3 * pw
            y = sy(math.log10(value), y0, ph, logy_min, logy_max)
            points.append((x, y))
            err = float(datum["chi_seed_se"]) / length**2
            ylo = sy(math.log10(max(value - err, 1e-300)), y0, ph, logy_min, logy_max)
            yhi = sy(math.log10(value + err), y0, ph, logy_min, logy_max)
            svg.append(f'<line x1="{x:.1f}" y1="{ylo:.1f}" x2="{x:.1f}" y2="{yhi:.1f}" stroke="{colors[sigma]}"/>')
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{colors[sigma]}"/>')
        fit_rows = [r for r in rows if int(r["L"]) >= 128]
        xs = [math.log(float(r["L"])) for r in fit_rows]
        ys = [
            math.log(float(r["chi"]) / int(r["L"]) ** 2)
            for r in fit_rows
        ]
        xm, ym = sum(xs) / len(xs), sum(ys) / len(ys)
        slope = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / sum((x - xm) ** 2 for x in xs)
        intercept = ym - slope * xm
        eta = -slope
        line = []
        for length in (64, 512):
            value = math.exp(intercept) * length**slope
            x = x0 + (math.log2(length) - 6) / 3 * pw
            y = sy(math.log10(value), y0, ph, logy_min, logy_max)
            line.append((x, y))
        svg.append(
            f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in line)}" '
            f'fill="none" stroke="{colors[sigma]}" stroke-width="2" stroke-dasharray="6,4"/>'
        )
        ly = y0 + ph - 80 + idx * 20
        legend_x = x0 + pw - 225
        svg.append(f'<line x1="{legend_x}" y1="{ly}" x2="{legend_x+24}" y2="{ly}" stroke="{colors[sigma]}" stroke-width="3"/>')
        svg.append(
            f'<text x="{legend_x+31}" y="{ly+4}" font-family="sans-serif" '
            f'font-size="12">σ={sigma:g}, η={eta:.4f}</text>'
        )
    svg.append("</svg>")
    return "\n".join(svg)


def linearized_extrapolation_figure():
    width, height = 1120, 1080
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="560" y="29" text-anchor="middle" font-family="sans-serif" font-size="18">修正变量线性化的热力学外推</text>',
    ]
    rows = [
        (1.875, "Rp", -0.45, 0.38),
        (2.0, "Rp", -0.32, 0.75),
        (1.875, "Qm", 0.72, 1.03),
        (2.0, "Qm", 0.75, 1.08),
    ]
    for row, (sigma, obs, ymin, ymax) in enumerate(rows):
        data = sorted(
            (r for r in critical if float(r["sigma"]) == sigma and r["observable"] == obs),
            key=lambda r: int(r["L"]),
        )
        for col, model in enumerate(("power", "marginal")):
            x0, y0, pw, ph = 105 + 525 * col, 55 + 255 * row, 430, 185
            fit = next(
                r for r in fits
                if float(r["sigma"]) == sigma
                and r["observable"] == obs
                and int(r["Lmin"]) == 64
                and r["model"] == model
            )
            limit, p1, q = float(fit["limit"]), float(fit["p1"]), float(fit["p2"])
            features = [
                (int(d["L"]) ** (-q) if model == "power"
                 else 1.0 / math.log(int(d["L"]) / q))
                for d in data
            ]
            xmax = max(features) * 1.08
            svg.append(f'<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="none" stroke="#555"/>')
            for j in range(5):
                value = ymin + (ymax - ymin) * j / 4
                y = sy(value, y0, ph, ymin, ymax)
                svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+pw}" y2="{y:.1f}" stroke="#e5e7eb"/>')
                svg.append(f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{value:.2f}</text>')
            for j in range(5):
                value = xmax * j / 4
                x = x0 + value / xmax * pw
                svg.append(f'<text x="{x:.1f}" y="{y0+ph+22}" text-anchor="middle" font-family="sans-serif" font-size="12">{value:.2f}</text>')
            color = "#0f766e" if model == "power" else "#c2410c"
            line_points = []
            for j in range(101):
                feature_value = xmax * j / 100
                value = limit + p1 * feature_value
                x = x0 + feature_value / xmax * pw
                y = sy(value, y0, ph, ymin, ymax)
                line_points.append((x, y))
            svg.append(
                f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in line_points)}" '
                f'fill="none" stroke="{color}" stroke-width="2"/>'
            )
            for datum, feature_value in zip(data, features):
                value = float(datum["value"])
                x = x0 + feature_value / xmax * pw
                y = sy(value, y0, ph, ymin, ymax)
                if datum["se"] != "NaN":
                    err = float(datum["se"])
                    svg.append(
                        f'<line x1="{x:.1f}" y1="{sy(value-err,y0,ph,ymin,ymax):.1f}" '
                        f'x2="{x:.1f}" y2="{sy(value+err,y0,ph,ymin,ymax):.1f}" stroke="#2563eb"/>'
                    )
                svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="white" stroke="#2563eb" stroke-width="1.5"/>')
            ylabel = "Rₚ" if obs == "Rp" else "Qₘ"
            svg.append(f'<text x="{x0+8}" y="{y0+20}" font-family="sans-serif" font-size="13">σ={sigma:g}, {ylabel}</text>')
            svg.append(f'<text x="{x0+pw-8}" y="{y0+20}" text-anchor="end" font-family="sans-serif" font-size="11">{ylabel},∞={limit:.3f}</text>')
            if model == "power":
                xlabel = '<tspan font-style="italic">L</tspan><tspan baseline-shift="super" font-size="8">−q</tspan>'
            else:
                xlabel = '1/log(<tspan font-style="italic">L</tspan>/<tspan font-style="italic">q</tspan>)'
            svg.append(f'<text x="{x0+pw/2}" y="{y0+ph+48}" text-anchor="middle" font-family="sans-serif" font-size="12">{xlabel}</text>')
            q_feature = 0.45 * xmax
            q_value = limit + p1 * q_feature
            qx = x0 + 0.45 * pw
            qy = max(y0 + 45, min(y0 + ph - 18, sy(q_value, y0, ph, ymin, ymax) - 18))
            svg.append(
                f'<text x="{qx:.1f}" y="{qy:.1f}" text-anchor="middle" font-family="sans-serif" '
                f'font-size="11" font-style="italic">q = {q:.3g}</text>'
            )
            svg.append(
                f'<text x="{x0-55}" y="{y0+ph/2}" text-anchor="middle" font-family="sans-serif" '
                f'font-size="12" transform="rotate(-90 {x0-55} {y0+ph/2})">{ylabel}(L)</text>'
            )
    svg.append("</svg>")
    return "\n".join(svg)


def window_stability_figure():
    width, height = 1120, 750
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="560" y="27" text-anchor="middle" font-family="sans-serif" font-size="18">热力学外推极限的拟合窗口稳定性</text>',
    ]
    panels = [
        (1.875, "Rp", "σ=1.875", -0.25, 2.9),
        (2.0, "Rp", "σ=2.0", -0.25, 2.3),
        (1.875, "Qm", "σ=1.875", 0.75, 1.45),
        (2.0, "Qm", "σ=2.0", 0.75, 1.65),
    ]
    model_style = {"power": ("#0f766e", "circle"), "marginal": ("#c2410c", "square")}
    lmins = [64, 128, 256, 512]
    for p, (sigma, obs, title, ymin, ymax) in enumerate(panels):
        col, row = p % 2, p // 2
        x0, y0, pw, ph = 105 + 525 * col, 55 + 345 * row, 430, 255
        svg.append(f'<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="none" stroke="#555"/>')
        for i, lmin in enumerate(lmins):
            x = x0 + 35 + i * (pw - 70) / 3
            svg.append(f'<line x1="{x:.1f}" y1="{y0+ph}" x2="{x:.1f}" y2="{y0+ph+5}" stroke="#555"/>')
            svg.append(f'<text x="{x:.1f}" y="{y0+ph+21}" text-anchor="middle" font-family="sans-serif" font-size="12">{lmin}</text>')
        for j in range(5):
            value = ymin + (ymax - ymin) * j / 4
            y = sy(value, y0, ph, ymin, ymax)
            svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+pw}" y2="{y:.1f}" stroke="#e5e7eb"/>')
            svg.append(f'<text x="{x0-7}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{value:.2f}</text>')
        svg.append(f'<text x="{x0+8}" y="{y0+18}" font-family="sans-serif" font-size="12">{title}</text>')
        svg.append(f'<text x="{x0+pw/2}" y="{y0+ph+39}" text-anchor="middle" font-family="sans-serif" font-size="16">Lₘᵢₙ</text>')
        ylabel = "Rₚ,∞" if obs == "Rp" else "Qₘ,∞"
        svg.append(
            f'<text x="{x0-52}" y="{y0+ph/2}" text-anchor="middle" font-family="sans-serif" '
            f'font-size="12" transform="rotate(-90 {x0-52} {y0+ph/2})">{ylabel}</text>'
        )
        for model, (color, marker) in model_style.items():
            rows = sorted(
                (
                    r
                    for r in fits
                    if float(r["sigma"]) == sigma
                    and r["observable"] == obs
                    and r["model"] == model
                ),
                key=lambda r: int(r["Lmin"]),
            )
            points = []
            for datum in rows:
                i = lmins.index(int(datum["Lmin"]))
                x = x0 + 35 + i * (pw - 70) / 3
                value = float(datum["limit"])
                y = sy(value, y0, ph, ymin, ymax)
                points.append((x, max(y0, min(y0 + ph, y))))
                lo, hi = float(datum["limit_boot_p16"]), float(datum["limit_boot_p84"])
                ylo = max(y0, min(y0 + ph, sy(lo, y0, ph, ymin, ymax)))
                yhi = max(y0, min(y0 + ph, sy(hi, y0, ph, ymin, ymax)))
                svg.append(f'<line x1="{x:.1f}" y1="{ylo:.1f}" x2="{x:.1f}" y2="{yhi:.1f}" stroke="{color}"/>')
                if marker == "circle":
                    svg.append(f'<circle cx="{x:.1f}" cy="{max(y0,min(y0+ph,y)):.1f}" r="4" fill="{color}"/>')
                else:
                    svg.append(f'<rect x="{x-4:.1f}" y="{max(y0,min(y0+ph,y))-4:.1f}" width="8" height="8" fill="{color}"/>')
            svg.append(
                f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in points)}" '
                f'fill="none" stroke="{color}" stroke-width="2"/>'
            )
        svg.append(f'<circle cx="{x0+245}" cy="{y0+17}" r="4" fill="#0f766e"/>')
        svg.append(f'<text x="{x0+254}" y="{y0+21}" font-family="sans-serif" font-size="12">power</text>')
        svg.append(f'<rect x="{x0+355}" y="{y0+13}" width="8" height="8" fill="#c2410c"/>')
        svg.append(f'<text x="{x0+369}" y="{y0+21}" font-family="sans-serif" font-size="12">log</text>')
    svg.append("</svg>")
    return "\n".join(svg)


def distinguishability_figure():
    width, height = 900, 470
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="450" y="27" text-anchor="middle" font-family="sans-serif" font-size="18">注册预测区间内的最大模型分离度</text>',
    ]
    x0, y0, pw, ph = 85, 55, 750, 325
    svg.append(f'<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="none" stroke="#555"/>')
    lmins = [64, 128, 256, 512]
    for i, lmin in enumerate(lmins):
        x = x0 + 55 + i * (pw - 110) / 3
        svg.append(f'<line x1="{x:.1f}" y1="{y0+ph}" x2="{x:.1f}" y2="{y0+ph+5}" stroke="#555"/>')
        svg.append(f'<text x="{x:.1f}" y="{y0+ph+21}" text-anchor="middle" font-family="sans-serif" font-size="12">{lmin}</text>')
    for j in range(7):
        value = 0.5 * j
        y = sy(value, y0, ph, 0, 3.25)
        svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+pw}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        svg.append(f'<text x="{x0-9}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{value:.1f}</text>')
    threshold = sy(3.0, y0, ph, 0, 3.25)
    svg.append(f'<line x1="{x0}" y1="{threshold:.1f}" x2="{x0+pw}" y2="{threshold:.1f}" stroke="#111" stroke-dasharray="6,5"/>')
    svg.append(f'<text x="{x0+pw-5}" y="{threshold-7:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">3σ 判别门槛</text>')
    svg.append(f'<text x="{x0+pw/2}" y="{height-24}" text-anchor="middle" font-family="sans-serif" font-size="16">Lₘᵢₙ</text>')
    svg.append(
        f'<text x="27" y="{y0+ph/2}" text-anchor="middle" font-family="sans-serif" font-size="12" '
        f'transform="rotate(-90 27 {y0+ph/2})">max z（L≤65536）</text>'
    )
    series = [
        (1.875, "Rp", "#16a34a", "σ=1.875, Rₚ"),
        (1.875, "Qm", "#15803d", "σ=1.875, Qₘ"),
        (2.0, "Rp", "#dc2626", "σ=2.0, Rₚ"),
        (2.0, "Qm", "#991b1b", "σ=2.0, Qₘ"),
    ]
    for idx, (sigma, obs, color, label) in enumerate(series):
        rows = sorted(
            (
                r
                for r in forecasts
                if float(r["sigma"]) == sigma and r["observable"] == obs
            ),
            key=lambda r: int(r["Lmin"]),
        )
        points = []
        for datum in rows:
            i = lmins.index(int(datum["Lmin"]))
            x = x0 + 55 + i * (pw - 110) / 3
            y = sy(float(datum["max_separation_z"]), y0, ph, 0, 3.25)
            points.append((x, y))
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')
        svg.append(
            f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in points)}" '
            f'fill="none" stroke="{color}" stroke-width="2"/>'
        )
        ly = y0 + 55 + idx * 20
        svg.append(f'<line x1="{x0+18}" y1="{ly}" x2="{x0+40}" y2="{ly}" stroke="{color}" stroke-width="3"/>')
        svg.append(f'<text x="{x0+46}" y="{ly+4}" font-family="sans-serif" font-size="12">{label}</text>')
    svg.append("</svg>")
    return "\n".join(svg)


def extension_extrapolation_figure():
    width, height = 1120, 1080
    rendered_label_font = 10.0 * width / 660.0
    label_ascent = 0.82 * rendered_label_font
    label_descent = 0.24 * rendered_label_font
    label_line_gap = 5.0

    def place_q_label(
        text,
        target_fit,
        panel_fits,
        marker_points,
        occupied_boxes,
        preferred_fraction,
        prefer_above,
        x0,
        y0,
        pw,
        ph,
        xmax,
        ymin,
        ymax,
    ):
        """Place a direct label near its curve without touching either fit."""
        label_width = min(pw - 20.0, max(112.0, len(text) * rendered_label_font * 0.62))
        allowed_top = y0 + 32.0
        allowed_bottom = y0 + ph - 6.0
        candidates = []
        x_fractions = sorted(
            (0.20 + 0.04 * index for index in range(18)),
            key=lambda fraction: abs(fraction - preferred_fraction),
        )

        for fraction in x_fractions:
            qx = x0 + fraction * pw
            left = qx - label_width / 2.0
            right = qx + label_width / 2.0
            if left < x0 + 6.0 or right > x0 + pw - 6.0:
                continue

            left_feature = (left - x0) / pw * xmax
            right_feature = (right - x0) / pw * xmax
            line_ranges = []
            for limit, p1, _ in panel_fits:
                line_ranges.append(
                    sorted(
                        (
                            sy(limit + p1 * left_feature, y0, ph, ymin, ymax),
                            sy(limit + p1 * right_feature, y0, ph, ymin, ymax),
                        )
                    )
                )

            limit, p1, _ = target_fit
            target_y = sy(
                limit + p1 * fraction * xmax,
                y0,
                ph,
                ymin,
                ymax,
            )
            first_baseline = allowed_top + label_ascent
            last_baseline = allowed_bottom - label_descent
            steps = max(0, int((last_baseline - first_baseline) / 2.0))
            for step in range(steps + 1):
                baseline = first_baseline + 2.0 * step
                top = baseline - label_ascent
                bottom = baseline + label_descent

                if any(
                    line_bottom >= top - label_line_gap
                    and line_top <= bottom + label_line_gap
                    for line_top, line_bottom in line_ranges
                ):
                    continue
                if any(
                    left - 10.0 <= px <= right + 10.0
                    and top - 10.0 <= py <= bottom + 10.0
                    for px, py in marker_points
                ):
                    continue
                if any(
                    left - 8.0 <= other_right
                    and right + 8.0 >= other_left
                    and top - 6.0 <= other_bottom
                    and bottom + 6.0 >= other_top
                    for other_left, other_top, other_right, other_bottom in occupied_boxes
                ):
                    continue

                if bottom < target_y:
                    separation = target_y - bottom
                    is_above = True
                elif top > target_y:
                    separation = top - target_y
                    is_above = False
                else:
                    continue
                side_penalty = 0.0 if is_above == prefer_above else 9.0
                outside_penalty = (
                    max(y0 - target_y, target_y - (y0 + ph), 0.0) * 2.0
                )
                score = (
                    separation
                    + abs(fraction - preferred_fraction) * 70.0
                    + side_penalty
                    + outside_penalty
                )
                candidates.append(
                    (score, qx, baseline, (left, top, right, bottom))
                )

        if not candidates:
            raise RuntimeError(f"could not place curve label without overlap: {text}")
        _, qx, baseline, box = min(candidates, key=lambda item: item[0])
        return qx, baseline, box

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="560" y="29" text-anchor="middle" font-family="sans-serif" font-size="18">大尺寸数据与完整窗口的线性化外推</text>',
    ]
    rows = [
        (1.875, "Rp", -0.45, 0.75),
        (2.0, "Rp", -0.35, 3.25),
        (1.875, "Qm", 0.72, 1.10),
        (2.0, "Qm", 0.75, 1.85),
    ]
    for row, (sigma, obs, ymin, ymax) in enumerate(rows):
        all_data = sorted(
            (r for r in critical if float(r["sigma"]) == sigma and r["observable"] == obs),
            key=lambda r: int(r["L"]),
        )
        for col, model in enumerate(("power", "marginal")):
            x0, y0, pw, ph = 105 + 525 * col, 55 + 255 * row, 430, 185
            clip_id = f"extension-panel-{row}-{col}"
            svg.append(
                f'<defs><clipPath id="{clip_id}"><rect x="{x0}" y="{y0}" '
                f'width="{pw}" height="{ph}"/></clipPath></defs>'
            )
            window_data = {}
            window_fits = {}
            all_features = []
            for maxL in (2048,):
                fit = next(
                    r for r in extension_fits
                    if float(r["sigma"]) == sigma
                    and r["observable"] == obs
                    and int(r["Lmax"]) == maxL
                    and r["model"] == model
                )
                limit, p1, q = float(fit["limit"]), float(fit["p1"]), float(fit["p2"])
                data = [d for d in all_data if int(d["L"]) <= maxL]
                features = [
                    (int(d["L"]) ** (-q) if model == "power"
                     else 1.0 / math.log(int(d["L"]) / q))
                    for d in data
                ]
                window_data[maxL] = (data, features)
                window_fits[maxL] = (limit, p1, q)
                all_features.extend(features)
            xmax = max(all_features) * 1.08
            svg.append(f'<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="none" stroke="#555"/>')
            for j in range(5):
                value = ymin + (ymax - ymin) * j / 4
                y = sy(value, y0, ph, ymin, ymax)
                svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+pw}" y2="{y:.1f}" stroke="#e5e7eb"/>')
                svg.append(f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{value:.2f}</text>')
            for j in range(5):
                value = xmax * j / 4
                x = x0 + value / xmax * pw
                svg.append(f'<text x="{x:.1f}" y="{y0+ph+22}" text-anchor="middle" font-family="sans-serif" font-size="12">{value:.2f}</text>')
            marker_points = []
            label_specs = []
            for maxL, color, dash in ((2048, "#2563eb", ""),):
                limit, p1, q = window_fits[maxL]
                points = []
                for j in range(101):
                    feature_value = xmax * j / 100
                    value = limit + p1 * feature_value
                    x = x0 + feature_value / xmax * pw
                    y = sy(value, y0, ph, ymin, ymax)
                    points.append((x, y))
                dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
                svg.append(
                    f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in points)}" '
                    f'fill="none" stroke="{color}" stroke-width="2"{dash_attr} '
                    f'clip-path="url(#{clip_id})"/>'
                )
                data, features = window_data[maxL]
                for datum, feature_value in zip(data, features):
                    if int(datum["L"]) <= 512:
                        continue
                    value = float(datum["value"])
                    x = x0 + feature_value / xmax * pw
                    y = sy(value, y0, ph, ymin, ymax)
                    marker_points.append((x, y))
                    svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.8" fill="white" stroke="{color}" stroke-width="1.5"/>')
                label_specs.append(
                    (
                        maxL,
                        color,
                        f"L≤{maxL}: q={q:.3g}",
                        window_fits[maxL],
                    )
                )

            occupied_boxes = []
            for maxL, color, label, target_fit in label_specs:
                qx, qy, box = place_q_label(
                    label,
                    target_fit,
                    tuple(window_fits.values()),
                    marker_points,
                    occupied_boxes,
                    0.62,
                    False,
                    x0,
                    y0,
                    pw,
                    ph,
                    xmax,
                    ymin,
                    ymax,
                )
                occupied_boxes.append(box)
                svg.append(
                    f'<text x="{qx:.1f}" y="{qy:.1f}" text-anchor="middle" font-family="sans-serif" '
                    f'font-size="10" font-style="italic" fill="{color}">{label}</text>'
                )
            ylabel = "Rₚ" if obs == "Rp" else "Qₘ"
            svg.append(f'<text x="{x0+8}" y="{y0+20}" font-family="sans-serif" font-size="13">σ={sigma:g}, {ylabel}</text>')
            if model == "power":
                xlabel = '<tspan font-style="italic">L</tspan><tspan baseline-shift="super" font-size="8">−q</tspan>'
            else:
                xlabel = '1/log(<tspan font-style="italic">L</tspan>/<tspan font-style="italic">q</tspan>)'
            svg.append(f'<text x="{x0+pw/2}" y="{y0+ph+48}" text-anchor="middle" font-family="sans-serif" font-size="12">{xlabel}</text>')
            svg.append(
                f'<text x="{x0-55}" y="{y0+ph/2}" text-anchor="middle" font-family="sans-serif" '
                f'font-size="12" transform="rotate(-90 {x0-55} {y0+ph/2})">{ylabel}(L)</text>'
            )
    svg.append("</svg>")
    return "\n".join(svg)


outputs = {
    "critical_finite_size_extended.svg": match_figure_two_font_scale(
        finite_size_figure(), 1120
    ),
    "eta_scaling.svg": match_figure_two_font_scale(eta_scaling_figure(), 900),
    "competing_extrapolations.svg": match_figure_two_font_scale(
        linearized_extrapolation_figure(), 1120
    ),
    "extrapolation_window_stability.svg": match_figure_two_font_scale(
        window_stability_figure(), 1120
    ),
    "distinguishability_forecast.svg": match_figure_two_font_scale(
        distinguishability_figure(), 900
    ),
    "extension_extrapolation.svg": match_figure_two_font_scale(
        extension_extrapolation_figure(), 1120
    ),
}


def english_version(content):
    replacements = {
        "中心临界点的有限尺寸流": "Finite-size flow at published critical points",
        "短程锚点": "short-range anchor",
        "χ(L)/L² 的临界幂律拟合": "Critical power-law fits of χ(L)/L²",
        "χ(L) 的临界幂律拟合": "Critical power-law fits of χ(L)",
        "幂律与对数修正的竞争外推": "Competing power and logarithmic extrapolations",
        "修正变量线性化的热力学外推": "Thermodynamic extrapolation in linearized correction coordinates",
        "热力学外推极限的拟合窗口稳定性": "Fit-window stability of thermodynamic limits",
        "注册预测区间内的最大模型分离度": "Maximum model separation in the registered forecast range",
        "大尺寸数据与完整窗口的线性化外推": "Linearized full-window extrapolation with large-size data",
        "预测区": "forecast",
        "3σ 判别门槛": "3σ threshold",
        "（": " (",
        "）": ")",
    }
    for source, target in replacements.items():
        content = content.replace(source, target)
    return content


outputs.update(
    {
        name.replace(".svg", "_en.svg"): english_version(content)
        for name, content in list(outputs.items())
    }
)

for name, content in outputs.items():
    path = os.path.join(figure_dir, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content + "\n")
    print(path)
