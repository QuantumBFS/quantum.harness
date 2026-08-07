#!/usr/bin/env python3
"""Cycle-safe Linux entry point for the audited two-root SAT synthesiser.

The canonical implementation remains ``d_window_sat.py``.  This loader makes
only exact, count-checked source transformations:

1. use the sibling generic parser on Linux;
2. exclude descendants of either target root from the divisor boundary;
3. topologically sort a spliced candidate before canonical renumbering;
4. name the candidate from the input instance rather than hard-coding D.

Every expected source fragment is checked before compilation, so source drift
fails closed.
"""

from __future__ import annotations

from pathlib import Path


SOURCE_PATH = Path(__file__).with_name("d_window_sat.py")
source = SOURCE_PATH.read_text(encoding="utf-8")


def replace_exact(old: str, new: str, count: int = 1) -> None:
    global source
    actual = source.count(old)
    if actual != count:
        raise RuntimeError(
            f"audited source drift for {old[:60]!r}: "
            f"expected {count}, found {actual}"
        )
    source = source.replace(old, new)


replace_exact(
    "import hashlib\nimport importlib.util",
    "import hashlib\nimport heapq\nimport importlib.util",
)
replace_exact(
    'MODULE_PATH = Path(r"C:\\tmp\\occam71_d_window\\window_search.py")',
    'MODULE_PATH = Path(__file__).with_name("window_search.py")',
)
replace_exact(
    "            if token.name not in removed:\n"
    "                boundary.add(token.name)",
    "            if (\n"
    "                token.name not in removed\n"
    "                and token.name not in descendants\n"
    "            ):\n"
    "                boundary.add(token.name)",
    count=2,
)
replace_exact(
    "def reachable_examples(circuit, values, roots, removed):",
    "def reachable_examples(\n"
    "    circuit, values, roots, removed, descendants\n"
    "):",
)
replace_exact(
    "    boundary_names, examples = reachable_examples(\n"
    "        circuit, values, root_names, removed\n"
    "    )",
    "    boundary_names, examples = reachable_examples(\n"
    "        circuit, values, root_names, removed, descendants\n"
    "    )",
)
replace_exact(
    '        candidate_path = args.output_dir / "mystery-D.candidate.txt"',
    "        candidate_path = (\n"
    '            args.output_dir / f"{args.netlist.stem}.candidate.txt"\n'
    "        )",
)

old_live_order = """\
    live = [gate for gate in combined if gate.out in needed]

    rename = {}
"""
new_live_order = """\
    # Joint synthesis may use an independent signal that appeared later than
    # one old root. Recompute a deterministic topological order. Descendants
    # of either target were excluded from the divisor boundary above.
    original_position = {
        gate.out: index for index, gate in enumerate(combined)
    }
    live_by_out = {
        gate.out: gate for gate in combined if gate.out in needed
    }
    indegree = {name: 0 for name in live_by_out}
    children = {name: set() for name in live_by_out}
    for name, gate in live_by_out.items():
        dependencies = {
            token.name
            for token in (gate.left, gate.right)
            if token.name in live_by_out
        }
        indegree[name] = len(dependencies)
        for dependency in dependencies:
            children[dependency].add(name)
    ready = [
        (original_position[name], name)
        for name, degree in indegree.items()
        if degree == 0
    ]
    heapq.heapify(ready)
    live = []
    while ready:
        _, name = heapq.heappop(ready)
        live.append(live_by_out[name])
        for child in sorted(
            children[name], key=original_position.__getitem__
        ):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(
                    ready, (original_position[child], child)
                )
    if len(live) != len(live_by_out):
        cyclic = sorted(
            (name for name, degree in indegree.items() if degree),
            key=original_position.__getitem__,
        )
        raise ValueError(
            "replacement introduces a combinational cycle: "
            + ", ".join(cyclic[:12])
        )

    rename = {}
"""
replace_exact(old_live_order, new_live_order)

exec(compile(source, str(SOURCE_PATH), "exec"), globals(), globals())
