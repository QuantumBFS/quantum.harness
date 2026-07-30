#!/usr/bin/env python3
"""Authenticate Challenge 194 evidence and draw deterministic report SVGs."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

EXPECTED_FILE_HASHES = {
    "approval": "29dc5d04fd18728ee46fffe90c70d98caa61032005974f354e2b4e0e6018a7ab",
    "p0_analysis": "44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b",
    "extension_protocol": "e363a60f842b11b32972c7a68ec1c5f237741bc45bc79ab8bf93f51f6760d84d",
    "extension_analysis": "d8fdd60a6de83cf3818349d4440f49f4a38bb5acd7fff1dab9b56ded4da913e5",
    "combined_analysis": "6c38e3e18a4577da41bc70c5610b5449e0316b1588291cb178e437099fb78929",
    "brackets": "7a84d545b4526d94aa6f93ca4f0d264dcf01e518f2f9b04383921634786c9962",
}

EXPECTED_EMBEDDED_HASHES = {
    "p0_analysis": "e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8",
    "extension_protocol": "a37ab41f3224594e61f4eebbe292975aeec449b9ecb7893e3e54f18d82d53321",
    "extension_analysis": "79232574d314348c29a40cd2fbb7690e96f3cae5f26843bd4f1cf07cb6a1f45b",
    "combined_analysis": "36f85c40e9159ef2e69742672c261769fb28d2f3c947780ba63e4ef5fe5975c3",
    "brackets": "098f19d8883097d5f1f274ce759416328c086958fa5301c034a0b46dcbd562df",
}

SOURCE_FILENAMES = {
    "approval": "pilot_correctness_approval.json",
    "p0_analysis": "p0_analysis.json",
    "extension_protocol": "p0_extension_v1_protocol.json",
    "extension_analysis": "p0_extension_v1_analysis.json",
    "combined_analysis": "p0_combined_analysis_v2.json",
    "brackets": "p0_combined_brackets_v2.json",
}

SCHEMAS = {
    "approval": "challenge-194-pilot-correctness-approval-v1",
    "p0_analysis": "challenge-194-p0-analysis-v1",
    "extension_protocol": "challenge-194-p0-extension-protocol-v1",
    "extension_analysis": "challenge-194-p0-extension-analysis-v1",
    "combined_analysis": "challenge-194-p0-combined-analysis-v2",
    "brackets": "challenge-194-p1-brackets-v2",
}

EMBEDDED_FIELDS = {
    "p0_analysis": "analysis_document_sha256",
    "extension_protocol": "protocol_sha256",
    "extension_analysis": "analysis_document_sha256",
    "combined_analysis": "analysis_document_sha256",
    "brackets": "bracket_document_sha256",
}

PANEL_SIGMAS = ((0.9).hex(), (1.0).hex())
PANEL_LENGTHS = (16384, 262144)
UNRESOLVED_REASON = "no_nonzero_interval_marked_by_both_estimators"
OBSERVABLES = ("q_g", "four_sector_crossing")


class SelectorPanel:
    def __init__(
        self,
        sigma_hex: str,
        kappas: tuple[str, ...],
        rows: dict[tuple[int, str], dict],
        q_marks: tuple[bool, ...],
        crossing_marks: tuple[bool, ...],
        status: str,
        reason: str,
    ) -> None:
        self.sigma_hex = sigma_hex
        self.kappas = kappas
        self.lengths = PANEL_LENGTHS
        self.rows = rows
        self.q_marks = q_marks
        self.crossing_marks = crossing_marks
        self.status = status
        self.reason = reason


class ReportEvidence:
    def __init__(
        self,
        documents: dict[str, dict],
        file_hashes: dict[str, str],
        embedded_hashes: dict[str, str],
        panels: dict[str, SelectorPanel],
    ) -> None:
        self.documents = documents
        self.file_hashes = file_hashes
        self.embedded_hashes = embedded_hashes
        self.panels = panels


def _canonical_float(hex_value: object, label: str) -> float:
    if not isinstance(hex_value, str):
        raise TypeError(f"{label} must be a binary64 hex string")
    try:
        value = float.fromhex(hex_value)
    except ValueError as error:
        raise ValueError(f"{label} is not valid float.hex()") from error
    if not math.isfinite(value) or value.hex() != hex_value:
        raise ValueError(f"{label} is not canonical finite float.hex()")
    return value


def _finite_number(value: object, label: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (nonnegative and result < 0.0):
        raise ValueError(f"{label} is not an allowed finite value")
    return result


def _selector_marks(
    rows: Mapping[tuple[int, str], dict],
    kappas: Sequence[str],
) -> tuple[tuple[bool, ...], tuple[bool, ...]]:
    q_marks: list[bool] = []
    crossing_marks: list[bool] = []
    for index in range(len(kappas) - 1):
        q_differences = []
        for endpoint in (index, index + 1):
            kappa = kappas[endpoint]
            q_differences.append(
                rows[(PANEL_LENGTHS[0], kappa)]["means"]["q_g"]
                - rows[(PANEL_LENGTHS[1], kappa)]["means"]["q_g"]
            )
        q_marks.append(min(q_differences) <= 0.0 <= max(q_differences))
        crossing_marks.append(
            any(
                min(
                    rows[(length, kappas[index])]["means"]["four_sector_crossing"],
                    rows[(length, kappas[index + 1])]["means"]["four_sector_crossing"],
                )
                <= 0.25
                and max(
                    rows[(length, kappas[index])]["means"]["four_sector_crossing"],
                    rows[(length, kappas[index + 1])]["means"]["four_sector_crossing"],
                )
                >= 0.75
                for length in PANEL_LENGTHS
            )
        )
    return tuple(q_marks), tuple(crossing_marks)


def load_evidence(paths: Mapping[str, Path]) -> ReportEvidence:
    """Load only the six exact authenticated inputs and reconstruct selectors."""
    if set(paths) != set(EXPECTED_FILE_HASHES):
        missing = sorted(set(EXPECTED_FILE_HASHES) - set(paths))
        extra = sorted(set(paths) - set(EXPECTED_FILE_HASHES))
        raise ValueError(f"required sources differ: missing={missing}, extra={extra}")

    documents: dict[str, dict] = {}
    file_hashes: dict[str, str] = {}
    for key, expected_digest in EXPECTED_FILE_HASHES.items():
        path = Path(paths[key])
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected_digest:
            raise ValueError(f"{SOURCE_FILENAMES[key]} SHA256 mismatch: {digest}")
        try:
            document = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"{SOURCE_FILENAMES[key]} is not valid JSON") from error
        if not isinstance(document, dict):
            raise TypeError(f"{SOURCE_FILENAMES[key]} must contain an object")
        if document.get("schema_version") != SCHEMAS[key]:
            raise ValueError(f"{SOURCE_FILENAMES[key]} schema mismatch")
        documents[key] = document
        file_hashes[key] = digest

    for key, field in EMBEDDED_FIELDS.items():
        if documents[key].get(field) != EXPECTED_EMBEDDED_HASHES[key]:
            raise ValueError(f"{SOURCE_FILENAMES[key]} embedded identity mismatch")

    extension_protocol = documents["extension_protocol"]
    extension = documents["extension_analysis"]
    combined = documents["combined_analysis"]
    brackets = documents["brackets"]
    approval = documents["approval"]

    if approval.get("report_sha256") != (
        "036b4b8a06164716aff5f40cc38ac4855a212026a556e1c5fe33ce32ce0babb8"
    ):
        raise ValueError("approval report identity mismatch")
    if (
        extension_protocol.get("source_p0_analysis_document_sha256")
        != (EXPECTED_EMBEDDED_HASHES["p0_analysis"])
    ):
        raise ValueError("extension protocol source link mismatch")
    if (
        extension.get("source_extension_protocol_sha256")
        != (EXPECTED_EMBEDDED_HASHES["extension_protocol"])
    ):
        raise ValueError("extension analysis protocol link mismatch")
    if (
        combined.get("source_p0_analysis_document_sha256")
        != (EXPECTED_EMBEDDED_HASHES["p0_analysis"])
    ):
        raise ValueError("combined P0 source link mismatch")
    if (
        combined.get("source_extension_analysis_document_sha256")
        != (EXPECTED_EMBEDDED_HASHES["extension_analysis"])
    ):
        raise ValueError("combined extension source link mismatch")
    if (
        brackets.get("source_analysis_document_sha256")
        != (EXPECTED_EMBEDDED_HASHES["combined_analysis"])
    ):
        raise ValueError("bracket source link mismatch")
    if brackets.get("requires_p0_extension") is not True:
        raise ValueError("unexpected selector completion state")
    if any("p1" in key.lower() and value for key, value in combined.items()):
        raise ValueError("combined evidence unexpectedly claims P1")

    sigma_entries = combined.get("sigma_entries")
    if not isinstance(sigma_entries, list):
        raise TypeError("combined analysis sigma_entries missing")
    by_sigma = {entry.get("sigma_hex"): entry for entry in sigma_entries}
    if set(PANEL_SIGMAS) - set(by_sigma):
        raise ValueError("required sigma panels missing")
    bracket_entries = brackets.get("brackets")
    if not isinstance(bracket_entries, list):
        raise TypeError("bracket entries missing")
    bracket_by_sigma = {entry.get("sigma_hex"): entry for entry in bracket_entries}

    panels: dict[str, SelectorPanel] = {}
    for sigma_hex in PANEL_SIGMAS:
        _canonical_float(sigma_hex, "sigma")
        entry = by_sigma[sigma_hex]
        raw_kappas = entry.get("kappas")
        if not isinstance(raw_kappas, list) or len(raw_kappas) < 2:
            raise ValueError("panel kappa axis missing")
        all_numeric_kappas = [
            _canonical_float(value, f"{sigma_hex} kappa") for value in raw_kappas
        ]
        if all_numeric_kappas != sorted(all_numeric_kappas):
            raise ValueError("panel kappas must be ordered")
        kappas = tuple(
            value
            for value, numeric in zip(raw_kappas, all_numeric_kappas)
            if numeric != 0.0
        )
        if len(kappas) < 2:
            raise ValueError("panel requires at least two nonzero kappas")
        if tuple(entry.get("lengths", ())) != (1024, 16384, 262144):
            raise ValueError("combined panel length axis mismatch")

        rows: dict[tuple[int, str], dict] = {}
        estimates = entry.get("estimates")
        if not isinstance(estimates, list):
            raise TypeError("panel estimates missing")
        for row in estimates:
            if (
                row.get("sigma_hex") != sigma_hex
                or row.get("length") not in PANEL_LENGTHS
                or row.get("kappa_hex") not in kappas
            ):
                continue
            means = row.get("means")
            standard_errors = row.get("standard_errors")
            if not isinstance(means, dict) or not isinstance(standard_errors, dict):
                raise TypeError("means or standard_errors missing")
            for observable in OBSERVABLES:
                _finite_number(means.get(observable), f"{observable} mean")
                _finite_number(
                    standard_errors.get(observable),
                    f"{observable} standard error",
                    nonnegative=True,
                )
            key = (row["length"], row["kappa_hex"])
            if key in rows:
                raise ValueError("duplicate plotted estimate")
            rows[key] = row
        expected_rows = {
            (length, kappa) for length in PANEL_LENGTHS for kappa in kappas
        }
        if set(rows) != expected_rows:
            raise ValueError("plotted estimate grid is incomplete")

        q_marks, crossing_marks = _selector_marks(rows, kappas)
        if any(q and crossing for q, crossing in zip(q_marks, crossing_marks)):
            raise ValueError("authenticated panel unexpectedly has a common interval")
        bracket = bracket_by_sigma.get(sigma_hex, {})
        if (
            bracket.get("status") != "requires_p0_extension"
            or bracket.get("reason") != UNRESOLVED_REASON
            or tuple(bracket.get("lengths", ())) != PANEL_LENGTHS
        ):
            raise ValueError("required unresolved bracket state mismatch")
        panels[sigma_hex] = SelectorPanel(
            sigma_hex,
            kappas,
            rows,
            q_marks,
            crossing_marks,
            bracket["status"],
            bracket["reason"],
        )

    return ReportEvidence(
        documents,
        file_hashes,
        dict(EXPECTED_EMBEDDED_HASHES),
        panels,
    )


def _svg_text(x: float, y: float, text: str, css_class: str = "") -> str:
    class_attribute = f' class="{css_class}"' if css_class else ""
    return f'<text x="{x:.1f}" y="{y:.1f}"{class_attribute}>{html.escape(text)}</text>'


def _polyline(points: Sequence[tuple[float, float]], color: str) -> str:
    coordinates = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return (
        f'<polyline points="{coordinates}" fill="none" stroke="{color}" '
        'stroke-width="2.4" stroke-linejoin="round"/>'
    )


def _plot_panel(
    panel: SelectorPanel,
    observable: str,
    x0: float,
    y0: float,
    width: float,
    height: float,
) -> list[str]:
    values = []
    for row in panel.rows.values():
        mean = row["means"][observable]
        error = row["standard_errors"][observable]
        values.extend((mean - error, mean + error))
    y_min = min(0.0, min(values))
    y_max = max(1.0 if observable == "four_sector_crossing" else 0.0, max(values))
    padding = max((y_max - y_min) * 0.08, 0.02)
    y_min -= padding
    y_max += padding
    x_values = [float.fromhex(value) for value in panel.kappas]
    x_min, x_max = min(x_values), max(x_values)

    def sx(value: float) -> float:
        return x0 + (value - x_min) * width / (x_max - x_min)

    def sy(value: float) -> float:
        return y0 + height - (value - y_min) * height / (y_max - y_min)

    sigma = float.fromhex(panel.sigma_hex)
    label = "Q_G" if observable == "q_g" else "four-sector crossing"
    output = [
        (
            f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{width:.1f}" '
            f'height="{height:.1f}" class="plot"/>'
        ),
        _svg_text(x0, y0 - 14, f"sigma = {sigma:.1f} · {label}", "panel-title"),
        _svg_text(x0 - 54, y0 + 12, f"{y_max:.2f}", "tick"),
        _svg_text(x0 - 54, y0 + height, f"{y_min:.2f}", "tick"),
        _svg_text(x0, y0 + height + 22, f"{x_min:.4g}", "tick"),
        _svg_text(x0 + width - 48, y0 + height + 22, f"{x_max:.4g}", "tick"),
        _svg_text(x0 + width / 2 - 18, y0 + height + 42, "kappa", "axis-label"),
    ]
    if observable == "four_sector_crossing":
        for guide in (0.25, 0.75):
            output.append(
                f'<line x1="{x0:.1f}" y1="{sy(guide):.2f}" '
                f'x2="{x0 + width:.1f}" y2="{sy(guide):.2f}" class="guide"/>'
            )
            output.append(
                _svg_text(x0 + width + 8, sy(guide) + 4, f"{guide:.2f}", "tick")
            )

    colors = {16384: "#1769aa", 262144: "#d1495b"}
    for length in PANEL_LENGTHS:
        points = []
        for kappa_hex, x_value in zip(panel.kappas, x_values):
            row = panel.rows[(length, kappa_hex)]
            mean = row["means"][observable]
            error = row["standard_errors"][observable]
            x_coordinate = sx(x_value)
            low, high = sy(mean - error), sy(mean + error)
            output.extend(
                (
                    (
                        f'<line x1="{x_coordinate:.2f}" y1="{low:.2f}" '
                        f'x2="{x_coordinate:.2f}" y2="{high:.2f}" '
                        f'stroke="{colors[length]}" class="error"/>'
                    ),
                    (
                        f'<line x1="{x_coordinate - 4:.2f}" y1="{low:.2f}" '
                        f'x2="{x_coordinate + 4:.2f}" y2="{low:.2f}" '
                        f'stroke="{colors[length]}" class="error"/>'
                    ),
                    (
                        f'<line x1="{x_coordinate - 4:.2f}" y1="{high:.2f}" '
                        f'x2="{x_coordinate + 4:.2f}" y2="{high:.2f}" '
                        f'stroke="{colors[length]}" class="error"/>'
                    ),
                    (
                        f'<circle cx="{x_coordinate:.2f}" cy="{sy(mean):.2f}" r="3.5" '
                        f'fill="{colors[length]}"/>'
                    ),
                )
            )
            points.append((x_coordinate, sy(mean)))
        output.append(_polyline(points, colors[length]))

    ribbon_y = y0 + height + 56
    for name, marks, color in (
        ("Q_G marks", panel.q_marks, "#7a5195"),
        ("four-sector marks", panel.crossing_marks, "#2a9d8f"),
    ):
        output.append(_svg_text(x0, ribbon_y + 10, name, "ribbon-label"))
        for index, marked in enumerate(marks):
            if marked:
                left = sx(x_values[index])
                right = sx(x_values[index + 1])
                output.append(
                    f'<rect x="{left:.2f}" y="{ribbon_y + 14:.1f}" '
                    f'width="{max(right - left, 1):.2f}" height="8" fill="{color}"/>'
                )
        ribbon_y += 28
    output.append(_svg_text(x0, ribbon_y + 12, "共同标记区间：无", "unresolved"))
    return output


def render_selector_svg(evidence: ReportEvidence) -> bytes:
    """Render authenticated means, ±1-SE bars, and unchanged selector marks."""
    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 1780">',
        "<title>Challenge 194 selector evidence for sigma 0.9 and 1.0</title>",
        (
            "<desc>Authenticated P0 plus extension v1 Q_G and four-sector means, "
            "standard errors, and unchanged interval marks; both sigma values remain "
            "unresolved.</desc>"
        ),
        (
            "<style>"
            "text{font-family:'DejaVu Sans','Noto Sans CJK SC',sans-serif;fill:#17202a}"
            ".title{font-size:30px;font-weight:700}.subtitle{font-size:18px}"
            ".panel-title{font-size:18px;font-weight:700}.tick{font-size:12px}"
            ".axis-label,.ribbon-label{font-size:13px}.unresolved{font-size:15px;font-weight:700;fill:#9b2226}"
            ".plot{fill:#fff;stroke:#59636e;stroke-width:1}.guide{stroke:#8d99ae;stroke-dasharray:5 4}"
            ".error{stroke-width:1.2}.caption{font-size:13px}.small{font-size:12px}"
            "</style>"
        ),
        _svg_text(70, 55, "挑战194：sigma 0.9 / 1.0 的 selector 实证", "title"),
        _svg_text(
            70,
            88,
            "误差条：均值 ± 1 standard error；选择器只使用均值，不使用误差条救援。",
            "subtitle",
        ),
    ]
    positions = (
        (PANEL_SIGMAS[0], "q_g", 100, 150),
        (PANEL_SIGMAS[0], "four_sector_crossing", 760, 150),
        (PANEL_SIGMAS[1], "q_g", 100, 770),
        (PANEL_SIGMAS[1], "four_sector_crossing", 760, 770),
    )
    for sigma_hex, observable, x, y in positions:
        body.extend(_plot_panel(evidence.panels[sigma_hex], observable, x, y, 540, 410))

    body.extend(
        (
            '<line x1="90" y1="1440" x2="1350" y2="1440" stroke="#b0b8c1"/>',
            '<circle cx="110" cy="1480" r="5" fill="#1769aa"/>',
            _svg_text(125, 1485, "L=16384", "caption"),
            '<circle cx="230" cy="1480" r="5" fill="#d1495b"/>',
            _svg_text(245, 1485, "L=262144", "caption"),
            '<rect x="370" y="1473" width="22" height="8" fill="#7a5195"/>',
            _svg_text(402, 1485, "Q_G interval mark", "caption"),
            '<rect x="575" y="1473" width="22" height="8" fill="#2a9d8f"/>',
            _svg_text(607, 1485, "four-sector interval mark", "caption"),
            _svg_text(
                90,
                1525,
                "状态：sigma = 0.9 与 sigma = 1.0 均为 requires_p0_extension；",
                "caption",
            ),
            _svg_text(
                90,
                1550,
                f"原因：{UNRESOLVED_REASON}。",
                "caption",
            ),
            _svg_text(
                90,
                1595,
                "来源 p0_combined_analysis_v2.json · SHA256 "
                + evidence.file_hashes["combined_analysis"],
                "small",
            ),
            _svg_text(
                90,
                1620,
                "来源 p0_combined_brackets_v2.json · SHA256 "
                + evidence.file_hashes["brackets"],
                "small",
            ),
            _svg_text(
                90,
                1645,
                "P0 source p0_analysis.json · SHA256 "
                + evidence.file_hashes["p0_analysis"],
                "small",
            ),
            _svg_text(
                90,
                1670,
                "extension-v1 source p0_extension_v1_analysis.json · SHA256 "
                + evidence.file_hashes["extension_analysis"],
                "small",
            ),
            _svg_text(
                90,
                1720,
                "Boundary: exploratory selector evidence only; not transition, scaling, exponent, or universality evidence.",
                "caption",
            ),
            "</svg>",
        )
    )
    return ("\n".join(body) + "\n").encode("utf-8")


def render_workflow_svg(evidence: ReportEvidence, dirty_paths: Sequence[str]) -> bytes:
    """Render the evidence chain and keep dirty v2 work outside that chain."""
    steps = (
        ("Issue #194", "model contract"),
        ("correctness approval", "authenticated"),
        ("P0 complete", "exploratory · 96 cells"),
        ("extension v1 complete", "96 cells / 96 trajectories"),
        ("combined selector", "mean-based rules"),
        ("sigma=0.9,1.0", "unresolved"),
        ("P1", "未发布 / 未运行"),
    )
    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1700 760">',
        "<title>Challenge 194 evidence workflow and unresolved status</title>",
        (
            "<desc>Authenticated workflow ends at unresolved sigma 0.9 and 1.0 and "
            "P1 not published or run. Partial extension-v2 workspace files are outside "
            "the evidence chain.</desc>"
        ),
        (
            "<style>"
            "text{font-family:'DejaVu Sans','Noto Sans CJK SC',sans-serif;fill:#17202a}"
            ".title{font-size:30px;font-weight:700}.box{fill:#f8fafc;stroke:#335c67;stroke-width:2}"
            ".blocked{fill:#fff1f2;stroke:#9b2226;stroke-width:2}.main{font-size:17px;font-weight:700}"
            ".sub{font-size:13px}.arrow{stroke:#335c67;stroke-width:3;fill:none}"
            ".dirty{fill:#fff8e7;stroke:#bb7b00;stroke-width:2;stroke-dasharray:8 6}"
            ".caption{font-size:12px}.boundary{font-size:15px;font-weight:700;fill:#9b2226}"
            "</style>"
        ),
        (
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            '<path d="M 0 0 L 10 5 L 0 10 z" fill="#335c67"/></marker></defs>'
        ),
        _svg_text(60, 55, "挑战194：证据工作流与停止边界", "title"),
    ]
    x_positions = (55, 285, 515, 745, 975, 1205, 1435)
    for index, ((main, sub), x) in enumerate(zip(steps, x_positions)):
        css = "blocked" if index >= 5 else "box"
        body.append(
            f'<rect x="{x}" y="130" width="200" height="115" rx="12" class="{css}"/>'
        )
        body.append(_svg_text(x + 15, 174, main, "main"))
        body.append(_svg_text(x + 15, 208, sub, "sub"))
        if index < len(steps) - 1:
            body.append(
                f'<line x1="{x + 200}" y1="187" x2="{x_positions[index + 1] - 12}" '
                'y2="187" class="arrow" marker-end="url(#arrow)"/>'
            )
    body.extend(
        (
            _svg_text(
                1205,
                280,
                f"reason: {UNRESOLVED_REASON}",
                "boundary",
            ),
            '<rect x="535" y="340" width="630" height="145" rx="12" class="dirty"/>',
            _svg_text(
                570,
                385,
                "当前工作区：extension-v2 局部未提交工作",
                "main",
            ),
            _svg_text(
                570,
                420,
                "不属于本报告证据链；未声称运行",
                "boundary",
            ),
            _svg_text(
                570,
                452,
                f"受保护 dirty 路径数：{len(tuple(dirty_paths))}",
                "sub",
            ),
            _svg_text(
                60,
                545,
                "来源 pilot_correctness_approval.json · SHA256 "
                + evidence.file_hashes["approval"],
                "caption",
            ),
            _svg_text(
                60,
                570,
                "来源 p0_analysis.json · SHA256 " + evidence.file_hashes["p0_analysis"],
                "caption",
            ),
            _svg_text(
                60,
                595,
                "来源 p0_extension_v1_protocol.json · SHA256 "
                + evidence.file_hashes["extension_protocol"],
                "caption",
            ),
            _svg_text(
                60,
                620,
                "来源 p0_extension_v1_analysis.json · SHA256 "
                + evidence.file_hashes["extension_analysis"],
                "caption",
            ),
            _svg_text(
                60,
                645,
                "来源 p0_combined_analysis_v2.json · SHA256 "
                + evidence.file_hashes["combined_analysis"],
                "caption",
            ),
            _svg_text(
                60,
                670,
                "来源 p0_combined_brackets_v2.json · SHA256 "
                + evidence.file_hashes["brackets"],
                "caption",
            ),
            _svg_text(
                60,
                715,
                "P0 / extension v1 are exploratory only; no P1, confirmatory, scaling, eta, or nu result follows.",
                "boundary",
            ),
            "</svg>",
        )
    )
    return ("\n".join(body) + "\n").encode("utf-8")


def write_outputs(output_dir: Path, outputs: Mapping[str, bytes]) -> None:
    """Atomically publish new files, accepting identical existing bytes only."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        target = output_dir / name
        if target.exists():
            if target.is_file() and target.read_bytes() == content:
                print(f"verified-existing {target}")
                continue
            raise FileExistsError(f"refusing to replace different output: {target}")
        temporary = None
        try:
            for attempt in range(100):
                candidate = output_dir / f".{name}.{os.getpid()}.{attempt}.partial"
                try:
                    descriptor = os.open(
                        candidate,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                    )
                    temporary = candidate
                    break
                except FileExistsError:
                    continue
            else:
                raise FileExistsError("unable to reserve private temporary output")
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                if target.is_file() and target.read_bytes() == content:
                    print(f"verified-existing {target}")
                    continue
                raise FileExistsError(f"refusing to replace different output: {target}")
            directory_descriptor = os.open(output_dir, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
            print(f"created {target}")
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--p0-analysis", type=Path, required=True)
    parser.add_argument("--extension-protocol", type=Path, required=True)
    parser.add_argument("--extension-analysis", type=Path, required=True)
    parser.add_argument("--combined-analysis", type=Path, required=True)
    parser.add_argument("--brackets", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    paths = {
        "approval": arguments.approval,
        "p0_analysis": arguments.p0_analysis,
        "extension_protocol": arguments.extension_protocol,
        "extension_analysis": arguments.extension_analysis,
        "combined_analysis": arguments.combined_analysis,
        "brackets": arguments.brackets,
    }
    evidence = load_evidence(paths)
    dirty_paths = (
        ".superpowers/sdd/task-1-report.md",
        "scripts/analyze_pilot.py",
        "src/long_range_percolation/pilot_extension.py",
        "tests/test_analyze_pilot_cli.py",
        "tests/test_pilot_extension.py",
    )
    outputs = {
        "challenge-194-selector-evidence.svg": render_selector_svg(evidence),
        "challenge-194-workflow-status.svg": render_workflow_svg(evidence, dirty_paths),
    }
    for name, content in outputs.items():
        print(f"{name} SHA256 {hashlib.sha256(content).hexdigest()}")
    if not arguments.verify_only:
        write_outputs(arguments.output_dir, outputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
