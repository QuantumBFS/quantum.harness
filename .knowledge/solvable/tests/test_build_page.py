"""Parser tests for the catalog-page generator (scripts/build_solvable_page.py).

The generator lives outside this package, so it is imported by file path via
importlib — the same pattern test_oracles.py uses for the oracle scripts.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]          # .knowledge/solvable
REPO = ROOT.parents[1]                              # repo root
GENERATOR = REPO / "scripts" / "build_solvable_page.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("build_solvable_page", GENERATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gen():
    return _load_generator()


INDEX_FIXTURE = """\
# Exactly-Solvable Models Catalog — Index

Intro prose that the parser must skip, including a non-group table:

| Tier | Meaning |
|---|---|
| **A** | Full solution |

## T1 Quadratic / free-particle

| Model | Tier | Script | Status | Card |
|---|---|---|---|---|
| `tfim-chain` | A | S | ✓ wave 1 | [ORACLE](./tfim-chain/ORACLE.md) |
| `bogoliubov-bose-gas` | A/D | S | ✓ wave 1 | [ORACLE](./bogoliubov-bose-gas/ORACLE.md) |

## T3 Bethe ansatz / Yang–Baxter

| Model | Tier | Script | Status | Card |
|---|---|---|---|---|
| `xyz-chain` | B | P | wave 2 | — |

## Totals

3 models
"""


def test_parse_index_rows(gen):
    entries = gen.parse_index(INDEX_FIXTURE)
    assert len(entries) == 3

    e0, e1, e2 = entries
    assert e0["slug"] == "tfim-chain"
    assert e0["name"] == "tfim-chain"
    assert e0["technique"] == "T1"
    assert e0["tier"] == "A"
    assert e0["flag"] == "S"
    assert e0["status"] == "wave 1"
    assert e0["built"] is True

    # composite tier survives verbatim
    assert e1["slug"] == "bogoliubov-bose-gas"
    assert e1["tier"] == "A/D"
    assert e1["built"] is True

    # second group, unbuilt row
    assert e2["slug"] == "xyz-chain"
    assert e2["technique"] == "T3"
    assert e2["tier"] == "B"
    assert e2["flag"] == "P"
    assert e2["status"] == "wave 2"
    assert e2["built"] is False


def test_parse_index_group_titles(gen):
    titles = gen.parse_group_titles(INDEX_FIXTURE)
    assert titles["T1"] == "Quadratic / free-particle"
    assert titles["T3"] == "Bethe ansatz / Yang–Baxter"
    assert "Totals" not in titles.values()


def test_parse_card_on_real_tfim(gen):
    text = (ROOT / "tfim-chain" / "ORACLE.md").read_text(encoding="utf-8")
    card = gen.parse_card(text)

    # Hamiltonian: first $$…$$ block, LaTeX body without the delimiters
    assert "\\sum" in card["hamiltonian"]
    assert "$$" not in card["hamiltonian"]

    # Solvability: first paragraph of the section, markdown stripped
    solv = card["solvability"]
    assert solv.strip()
    assert "Jordan–Wigner" in solv
    assert "**" not in solv and "`" not in solv

    # Benchmarks: at least one parsed data row with the table's four cells
    rows = card["benchmarks"]
    assert len(rows) >= 1
    first = rows[0]
    assert set(first) == {"quantity", "params", "value", "source"}
    assert first["quantity"]  # non-empty, no header/separator leakage
    assert first["quantity"] != "Quantity"
    assert "---" not in first["quantity"]


def test_every_built_entry_has_a_hook(gen):
    """Every slug marked built (✓) in the real INDEX.md must have a HOOKS entry.

    This reads the live INDEX at test time (not a fixture) so it tracks
    whichever cards are actually built. It passes today because all wave-1
    slugs have hooks; it is expected to start failing once wave-2 cards are
    marked built without a matching HOOKS entry added yet, which is the
    point — a loud, test-level reminder to fill in the hook.
    """
    index_text = (ROOT / "INDEX.md").read_text(encoding="utf-8")
    entries = gen.parse_index(index_text)
    built = [e for e in entries if e["built"]]
    assert built, "expected at least one built entry in the real INDEX.md"
    missing = [e["slug"] for e in built if not gen.HOOKS.get(e["slug"], "").strip()]
    assert not missing, f"built slugs missing a HOOKS entry: {missing}"


def test_benchmark_citekeys_render_readable(gen):
    # single key: readable text, raw key preserved in title= for provenance
    out = gen._md_cell("[@Pfeuty1970]")
    assert ">Pfeuty 1970<" in out
    assert 'title="[@Pfeuty1970]"' in out
    assert not out.startswith("[@")

    # camel-cased multi-name key + multi-key cell
    multi = gen._md_cell("[@LiebSchultzMattis1961; @Kitaev2003]")
    assert "Lieb–Schultz–Mattis 1961" in multi
    assert "Kitaev 2003" in multi
    assert 'title="[@LiebSchultzMattis1961; @Kitaev2003]"' in multi

    # yearless key degrades gracefully
    assert ">Baxter<" in gen._md_cell("[@Baxter]")
