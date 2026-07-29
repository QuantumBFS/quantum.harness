"""Exact structural triage of completed deep exterior survivors."""

from __future__ import annotations

import argparse
import itertools
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

import sympy as sp

from . import exterior_deep_survivor as stage3
from . import exterior_depth12_exact_fallback as depth12_exact
from . import exterior_depth12_hp_continuation as depth12_hp
from . import exterior_depth16_survivor as stage4
from .exterior_candidates import (
    candidate_structure_audit,
    candidate_card,
    candidate_id,
    exact_atoms_from_card,
)
from .exterior_thin_scan import mixed_words


SCHEMA_VERSION = "exterior-structural-rank-v1"
TRACE_DEPTHS = (2, 3, 4)
TRACE_WORDS = ((0,), (1,), *mixed_words(2, depths=TRACE_DEPTHS))


def _rational_payload(value: sp.Expr) -> dict[str, int]:
    rational = sp.Rational(value)
    return {
        "numerator": int(rational.p),
        "denominator": int(rational.q),
    }


def _sector_traces(matrix: sp.MatrixBase) -> tuple[sp.Rational, ...]:
    """Return all exact exterior-sector traces from one characteristic polynomial."""

    coefficients = matrix.charpoly().all_coeffs()
    return tuple(
        sp.Rational((-1) ** grade * coefficients[grade])
        for grade in range(matrix.rows + 1)
    )


def sector_trace_gate(
    card: Mapping[str, object],
    *,
    max_depth: int = 4,
) -> dict[str, object]:
    """Stop at the first exact negative trace, a basis-invariant cone obstruction."""

    if (
        not isinstance(max_depth, int)
        or isinstance(max_depth, bool)
        or not 1 <= max_depth <= 4
    ):
        raise ValueError("max_depth must be an integer in 1..4")
    atoms = exact_atoms_from_card(card)
    dimension = atoms[0].rows
    words = tuple(word for word in TRACE_WORDS if len(word) <= max_depth)
    tested_sectors = 0
    for word in words:
        product = sp.eye(dimension)
        for atom_index in word:
            product = product * atoms[atom_index]
        traces = _sector_traces(product)
        for grade in range(1, dimension):
            tested_sectors += 1
            trace = traces[grade]
            if trace < 0:
                return {
                    "status": "sector-trace-obstructed",
                    "max_depth": max_depth,
                    "tested_words": words.index(word) + 1,
                    "tested_sectors": tested_sectors,
                    "witness": {
                        "word_indices": list(word),
                        "depth": len(word),
                        "grade": grade,
                        **_rational_payload(trace),
                    },
                }
    return {
        "status": f"trace-clean-depth{max_depth}",
        "max_depth": max_depth,
        "tested_words": len(words),
        "tested_sectors": tested_sectors,
        "witness": None,
    }


def full_determinant_cancellation_gate(
    card: Mapping[str, object],
    *,
    max_depth: int = 12,
) -> dict[str, object]:
    """Find a cheap exact pure-power negative-sector/positive-total witness."""

    if (
        not isinstance(max_depth, int)
        or isinstance(max_depth, bool)
        or not 1 <= max_depth <= 12
    ):
        raise ValueError("max_depth must be an integer in 1..12")
    atoms = exact_atoms_from_card(card)
    tested_words = 0
    for depth in range(1, max_depth + 1):
        for atom_index, atom in enumerate(atoms):
            tested_words += 1
            traces = _sector_traces(atom**depth)
            negative = [
                {
                    "grade": grade,
                    **_rational_payload(traces[grade]),
                }
                for grade in range(1, atom.rows)
                if traces[grade] < 0
            ]
            determinant = sum(traces, start=sp.Integer(0))
            if negative and determinant > 0:
                return {
                    "status": "exact-positive-determinant-negative-sector",
                    "probe": "pure-powers-two-atoms-depth-ascending",
                    "max_depth": max_depth,
                    "tested_words": tested_words,
                    "witness": {
                        "word_indices": [atom_index] * depth,
                        "depth": depth,
                        "negative_sectors": negative,
                        "determinant": _rational_payload(determinant),
                    },
                }
    return {
        "status": "no-pure-power-cancellation-through-depth"
        f"{max_depth}",
        "probe": "pure-powers-two-atoms-depth-ascending",
        "max_depth": max_depth,
        "tested_words": tested_words,
        "witness": None,
    }


def _is_entrywise_nonnegative(matrix: sp.MatrixBase) -> bool:
    return all(entry >= 0 for entry in matrix)


def _is_totally_nonnegative(matrix: sp.MatrixBase) -> bool:
    dimension = matrix.rows
    for grade in range(2, dimension + 1):
        subsets = tuple(itertools.combinations(range(dimension), grade))
        for rows in subsets:
            for columns in subsets:
                if matrix.extract(rows, columns).det() < 0:
                    return False
    return True


def induced_tn_signed_gauge(
    card: Mapping[str, object],
) -> dict[str, object] | None:
    """Find an exact shared signed gauge whose one-body atoms are totally nonnegative."""

    atoms = exact_atoms_from_card(card)
    dimension = atoms[0].rows
    for tail in itertools.product((-1, 1), repeat=dimension - 1):
        diagonal = (1, *tail)
        gauge = sp.diag(*diagonal)
        transformed = tuple(gauge * atom * gauge for atom in atoms)
        if not all(_is_entrywise_nonnegative(atom) for atom in transformed):
            continue
        if not _is_totally_nonnegative(transformed[0]):
            continue
        if transformed[1] != transformed[0].T:
            raise RuntimeError("validated transpose orbit was not preserved by gauge")
        return {
            "kind": "known-induced-tn-signed-gauge",
            "one_body_diagonal": list(diagonal),
            "shared_across_atoms": True,
            "all_exterior_grades": True,
            "verification": "exact-all-minors-nonnegative",
        }
    return None


def _control_reduction(card: Mapping[str, object]) -> dict[str, object]:
    audit = candidate_structure_audit(card)
    known = audit["known_reduction"]
    if known is not None:
        return {
            "kind": known,
            "shared_across_atoms": True,
            "all_exterior_grades": False,
            "verification": "canonical-card-structure-audit",
        }
    induced = induced_tn_signed_gauge(card)
    if induced is not None:
        return induced
    return {
        "kind": None,
        "shared_across_atoms": False,
        "all_exterior_grades": False,
        "verification": "no-exact-reduction-in-fast-library",
    }


def _rank_card(
    card: Mapping[str, object],
    *,
    identity: str,
    stage_statuses: Mapping[str, object] | None = None,
    probe_deep_cancellation: bool = False,
) -> dict[str, object]:
    trace = sector_trace_gate(card)
    control = _control_reduction(card)
    cancellation = (
        full_determinant_cancellation_gate(card)
        if probe_deep_cancellation
        else None
    )
    trace_clean = trace["status"] == "trace-clean-depth4"
    non_control = control["kind"] is None
    template = str(card["template"])
    if template == "exact5-oddcycle-block-pair" and trace_clean and non_control:
        priority = 0
        priority_class = "exact5-trace-clean-non-control"
    elif (
        cancellation is not None
        and cancellation["status"]
        == "exact-positive-determinant-negative-sector"
        and non_control
    ):
        priority = 1
        priority_class = "full-determinant-cancellation-non-control"
    elif trace_clean and non_control:
        priority = 2 if probe_deep_cancellation else 1
        priority_class = "trace-clean-non-control"
    elif control["kind"] is not None:
        priority = 3 if probe_deep_cancellation else 2
        priority_class = "known-control-reduction"
    else:
        priority = 4 if probe_deep_cancellation else 3
        priority_class = "sector-trace-obstructed"
    result = {
        "candidate_id": identity,
        "template": template,
        "seed": card["seed"],
        "dimension": card["dimension"],
        "stage_statuses": dict(stage_statuses)
        if stage_statuses is not None
        else {
            "stage2": stage3.PARENT_SURVIVOR_STATUS,
            "stage3": stage3.SURVIVOR_STATUS,
            "stage4": stage4.SURVIVOR_STATUS,
        },
        "sector_trace": trace,
        "control_reduction": control,
        "non_control": non_control,
        "priority": priority,
        "priority_class": priority_class,
    }
    if cancellation is not None:
        result["full_determinant_cancellation"] = cancellation
    return result


def rank_continuation_survivors(
    *,
    run_dir: str | Path,
    continuation_kind: str,
) -> dict[str, object]:
    """Validate and structurally rank one completed depth-12 continuation."""

    if continuation_kind == "exact-fallback":
        module = depth12_exact
    elif continuation_kind == "stage3hp":
        module = depth12_hp
    else:
        raise ValueError(
            "continuation_kind must be 'exact-fallback' or 'stage3hp'"
        )
    root = Path(run_dir)
    plan = depth12_exact._load_json(root / "continuation-plan.json")
    entries = module._validate_plan(plan)
    terminal_counts: Counter[str] = Counter()
    survivors: list[tuple[Mapping[str, object], Mapping[str, object]]] = []
    for entry in entries:
        identity = str(entry["candidate_id"])
        path = root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            raise RuntimeError(f"continuation manifest missing: {identity}")
        manifest = depth12_exact._load_json(path)
        if not module._terminal_is_valid(
            manifest,
            entry=entry,
            plan=plan,
        ):
            raise RuntimeError(f"invalid continuation terminal: {identity}")
        status = str(manifest["status"])
        terminal_counts[status] += 1
        if status != module.SURVIVOR_STATUS:
            continue
        card = candidate_card(
            template=str(entry["template"]),
            seed=entry["seed"],  # type: ignore[arg-type]
        )
        if (
            candidate_id(card) != identity
            or entry.get("card_sha256") != identity
            or card["dimension"] != entry.get("dimension")
        ):
            raise RuntimeError(f"continuation candidate does not reconstruct: {identity}")
        survivors.append((entry, card))

    ranking = [
        _rank_card(
            card,
            identity=str(entry["candidate_id"]),
            stage_statuses={
                "continuation_kind": continuation_kind,
                "continuation": module.SURVIVOR_STATUS,
                "verified_depths": list(module.DEPTHS),
            },
            probe_deep_cancellation=True,
        )
        for entry, card in survivors
    ]
    ranking.sort(
        key=lambda item: (
            int(item["priority"]),
            str(item["template"]),
            int(item["seed"]),
            str(item["candidate_id"]),
        )
    )
    priority_counts = Counter(str(item["priority_class"]) for item in ranking)
    template_counts = Counter(str(item["template"]) for item in ranking)
    cancellation_count = sum(
        item["full_determinant_cancellation"]["status"]
        == "exact-positive-determinant-negative-sector"
        for item in ranking
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "continuation_kind": continuation_kind,
        "continuation_run_id": plan["run_id"],
        "continuation_plan_hash": plan["continuation_plan_hash"],
        "verified_depths": list(module.DEPTHS),
        "terminal": len(entries),
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "selected": len(ranking),
        "full_determinant_cancellation_count": cancellation_count,
        "exact5_trace_clean_non_control_count": sum(
            item["priority_class"] == "exact5-trace-clean-non-control"
            for item in ranking
        ),
        "priority_counts": dict(sorted(priority_counts.items())),
        "template_counts": dict(sorted(template_counts.items())),
        "ranking": ranking,
    }


def rank_survivor_cards(
    *,
    stage2_run_dir: str | Path,
    stage3_run_dir: str | Path,
    stage4_run_dir: str | Path,
) -> dict[str, object]:
    """Validate the three-stage chain and rank exactly its depth-16 survivors."""

    plan, entries, stage3_protocol = stage4.load_stage3_survivors(
        stage2_run_dir, stage3_run_dir
    )
    stage4_protocol = stage4._protocol_hash(
        plan, stage3_protocol, stage4.RUN_ID
    )
    root = Path(stage4_run_dir)
    survivors: list[tuple[dict[str, object], Mapping[str, object]]] = []
    terminal_counts: Counter[str] = Counter()
    for entry in entries:
        identity = str(entry["candidate_id"])
        path = root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            raise RuntimeError(f"Stage-4 manifest missing: {identity}")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not stage4._manifest_is_valid(
            manifest,
            entry=entry,
            plan=plan,
            stage3_protocol=stage3_protocol,
            run_id=stage4.RUN_ID,
            protocol_hash=stage4_protocol,
        ):
            raise RuntimeError(f"invalid Stage-4 terminal manifest: {identity}")
        terminal_counts[str(manifest["status"])] += 1
        if manifest["status"] != stage4.SURVIVOR_STATUS:
            continue
        survivors.append((entry, stage3._entry_card(entry)))

    ranking = [
        _rank_card(card, identity=str(entry["candidate_id"]))
        for entry, card in survivors
    ]
    ranking.sort(
        key=lambda item: (
            int(item["priority"]),
            str(item["template"]),
            int(item["seed"]),
            str(item["candidate_id"]),
        )
    )
    priority_counts = Counter(str(item["priority_class"]) for item in ranking)
    template_counts = Counter(str(item["template"]) for item in ranking)
    return {
        "schema_version": SCHEMA_VERSION,
        "stage2_run_id": plan["run_id"],
        "stage2_protocol_hash": plan["protocol_hash"],
        "stage3_run_id": stage3.RUN_ID,
        "stage3_protocol_hash": stage3_protocol,
        "stage4_run_id": stage4.RUN_ID,
        "stage4_protocol_hash": stage4_protocol,
        "trace_word_order": "singletons-then-mixed-depth2-through4-lexicographic",
        "stage4_terminal": len(entries),
        "stage4_terminal_counts": dict(sorted(terminal_counts.items())),
        "selected": len(ranking),
        "priority_counts": dict(sorted(priority_counts.items())),
        "template_counts": dict(sorted(template_counts.items())),
        "ranking": ranking,
    }


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage2-run-dir")
    parser.add_argument("--stage3-run-dir")
    parser.add_argument("--stage4-run-dir")
    parser.add_argument("--continuation-run-dir")
    parser.add_argument(
        "--continuation-kind",
        choices=("exact-fallback", "stage3hp"),
    )
    parser.add_argument("--output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.continuation_run_dir is not None:
        if args.continuation_kind is None:
            parser.error("--continuation-kind is required with --continuation-run-dir")
        result = rank_continuation_survivors(
            run_dir=args.continuation_run_dir,
            continuation_kind=args.continuation_kind,
        )
    else:
        missing = [
            option
            for option, value in (
                ("--stage2-run-dir", args.stage2_run_dir),
                ("--stage3-run-dir", args.stage3_run_dir),
                ("--stage4-run-dir", args.stage4_run_dir),
            )
            if value is None
        ]
        if missing:
            parser.error(
                "depth-16 mode requires " + ", ".join(missing)
            )
        result = rank_survivor_cards(
            stage2_run_dir=args.stage2_run_dir,
            stage3_run_dir=args.stage3_run_dir,
            stage4_run_dir=args.stage4_run_dir,
        )
    if args.output is not None:
        _write_json_atomic(Path(args.output), result)
    print(stage3._canonical_json(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "TRACE_WORDS",
    "full_determinant_cancellation_gate",
    "induced_tn_signed_gauge",
    "rank_continuation_survivors",
    "rank_survivor_cards",
    "sector_trace_gate",
]
