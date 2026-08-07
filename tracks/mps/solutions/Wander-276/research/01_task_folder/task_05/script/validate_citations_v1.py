#!/usr/bin/env python3
"""Validate the large-scale companion bibliography against primary metadata.

The audit is intentionally explicit: every bibliography key is registered,
assigned to an intended manuscript section, and checked against a primary
identifier.  No task_03 files or bibliography are imported.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_BIB = (
    REPO_ROOT
    / "overleaf_sync"
    / "geometric_eth_large_scale"
    / "references.bib"
)
DEFAULT_JSON = SCRIPT_DIR / "output" / "citation_audit_v1.json"
DEFAULT_MARKDOWN = (
    REPO_ROOT
    / "docs"
    / "literature"
    / "2026-07-28-geometric-eth-large-scale-citation-audit.md"
)
USER_AGENT = (
    "Chaos-of-Quantum-Geometry citation audit/1.0 "
    "(mailto:thomasjwang@users.noreply.github.com)"
)


def _record(
    key: str,
    title: str,
    year: int,
    authors: tuple[str, ...],
    section: str,
    *,
    doi: str | None = None,
    arxiv: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "year": year,
        "authors": list(authors),
        "section": section,
        "doi": doi,
        "arxiv": arxiv,
    }


REGISTRY = (
    _record(
        "berry1984",
        "Quantal phase factors accompanying adiabatic changes",
        1984,
        ("Berry",),
        "geometric foundations",
        doi="10.1098/rspa.1984.0023",
    ),
    _record(
        "wilczekzee1984",
        "Appearance of gauge structure in simple dynamical systems",
        1984,
        ("Wilczek", "Zee"),
        "geometric foundations",
        doi="10.1103/PhysRevLett.52.2111",
    ),
    _record(
        "provostvallee1980",
        "Riemannian structure on manifolds of quantum states",
        1980,
        ("Provost", "Vallee"),
        "geometric foundations",
        doi="10.1007/BF02193559",
    ),
    _record(
        "kato1950",
        "On the adiabatic theorem of quantum mechanics",
        1950,
        ("Kato",),
        "isolated-projector formalism",
        doi="10.1143/JPSJ.5.435",
    ),
    _record(
        "chen2026",
        "Chaos of Berry curvature for BPS microstates",
        2026,
        ("Chen", "Colin-Ellerin", "Mamroud", "Papadodimas"),
        "geometric chaos motivation",
        arxiv="2604.23287",
    ),
    _record(
        "laughlin1983",
        (
            "Anomalous quantum Hall effect: An incompressible quantum "
            "fluid with fractionally charged excitations"
        ),
        1983,
        ("Laughlin",),
        "Laughlin zero modes",
        doi="10.1103/PhysRevLett.50.1395",
    ),
    _record(
        "haldane1983",
        (
            "Fractional quantization of the Hall effect: A hierarchy of "
            "incompressible quantum fluid states"
        ),
        1983,
        ("Haldane",),
        "fractional quantum Hall hierarchy",
        doi="10.1103/PhysRevLett.51.605",
    ),
    _record(
        "bernevighaldane2008",
        "Model fractional quantum Hall states and Jack polynomials",
        2008,
        ("Bernevig", "Haldane"),
        "generalized exclusion rules",
        doi="10.1103/PhysRevLett.100.246802",
    ),
    _record(
        "chenseidel2015",
        (
            "Algebraic approach to the study of zero modes of Haldane "
            "pseudopotentials"
        ),
        2015,
        ("Chen", "Seidel"),
        "zero-mode algebra",
        doi="10.1103/PhysRevB.91.085103",
    ),
    _record(
        "mooreread1991",
        "Nonabelions in the fractional quantum Hall effect",
        1991,
        ("Moore", "Read"),
        "higher clustering",
        doi="10.1016/0550-3213(91)90407-O",
    ),
    _record(
        "readrezayi1999",
        (
            "Beyond paired quantum Hall states: Parafermions and "
            "incompressible states in the first excited Landau level"
        ),
        1999,
        ("Read", "Rezayi"),
        "higher clustering",
        doi="10.1103/PhysRevB.59.8084",
    ),
    _record(
        "zhang2023",
        (
            "From frustration-free parent Hamiltonians to off-diagonal "
            "long-range order: Moore-Read and related states in second "
            "quantization"
        ),
        2023,
        ("Fanmao Zhang", "Matheus Schossler", "Seidel", "Chen"),
        "clustered root spaces",
        doi="10.1103/PhysRevB.108.075142",
    ),
    _record(
        "mazaheri2015",
        (
            "Zero modes, bosonization, and topological quantum order: "
            "The Laughlin state in second quantization"
        ),
        2015,
        ("Mazaheri", "Ortiz", "Nussinov", "Seidel"),
        "zero-mode algebra",
        doi="10.1103/PhysRevB.91.085115",
    ),
    _record(
        "kapitmueller2010",
        "Exact parent Hamiltonian for the quantum Hall states in a lattice",
        2010,
        ("Kapit", "Mueller"),
        "lattice validation",
        doi="10.1103/PhysRevLett.105.215303",
    ),
    _record(
        "leeqi2014",
        (
            "Lattice construction of pseudopotential Hamiltonians for "
            "fractional Chern insulators"
        ),
        2014,
        ("Lee", "Qi"),
        "lattice pseudopotentials",
        doi="10.1103/PhysRevB.90.085103",
    ),
    _record(
        "neupert2011",
        "Fractional quantum Hall states at zero magnetic field",
        2011,
        ("Neupert", "Santos", "Chamon", "Mudry"),
        "fractional Chern insulators",
        doi="10.1103/PhysRevLett.106.236804",
    ),
    _record(
        "bravyi2010",
        "Topological quantum order: Stability under local perturbations",
        2010,
        ("Bravyi", "Hastings", "Michalakis"),
        "gapped-phase stability",
        doi="10.1063/1.3490195",
    ),
    _record(
        "bachmann2011",
        (
            "Automorphic equivalence within gapped phases of quantum "
            "lattice systems"
        ),
        2011,
        ("Bachmann", "Michalakis", "Nachtergaele", "Sims"),
        "gapped-phase transport",
        doi="10.1007/s00220-011-1380-0",
    ),
    _record(
        "schuch2011",
        (
            "Classifying quantum phases using matrix product states and "
            "projected entangled pair states"
        ),
        2011,
        ("Schuch", "David Perez", "Cirac"),
        "phase classification",
        doi="10.1103/PhysRevB.84.165139",
    ),
    _record(
        "hastingswen2005",
        (
            "Quasiadiabatic continuation of quantum states: The stability "
            "of topological ground-state degeneracy and emergent gauge "
            "invariance"
        ),
        2005,
        ("Hastings", "Wen"),
        "gapped-projector transport",
        doi="10.1103/PhysRevB.72.045141",
    ),
    _record(
        "collins2005",
        (
            "Product of random projections, Jacobi ensembles and "
            "universality problems arising from free probability"
        ),
        2005,
        ("Collins",),
        "Jacobi null model",
        doi="10.1007/s00440-005-0428-5",
    ),
    _record(
        "zyczkowski2000",
        "Truncations of random unitary matrices",
        2000,
        ("Zyczkowski", "Sommers"),
        "Haar compressions",
        doi="10.1088/0305-4470/33/10/307",
    ),
    _record(
        "atas2013",
        (
            "Distribution of the ratio of consecutive level spacings in "
            "random matrix ensembles"
        ),
        2013,
        ("Atas", "Bogomolny", "Giraud", "Roux"),
        "local spectral statistics",
        doi="10.1103/PhysRevLett.110.084101",
    ),
    _record(
        "niuthoulesswu1985",
        "Quantized Hall conductance as a topological invariant",
        1985,
        ("Niu", "Thouless", "Wu"),
        "many-body topology",
        doi="10.1103/PhysRevB.31.3372",
    ),
    _record(
        "kolodrubetz2017",
        "Geometry and non-adiabatic response in quantum and classical systems",
        2017,
        ("Kolodrubetz", "Sels", "Mehta", "Polkovnikov"),
        "quantum geometric response",
        doi="10.1016/j.physrep.2017.07.001",
    ),
    _record(
        "bohigas1984",
        (
            "Characterization of chaotic quantum spectra and universality "
            "of level fluctuation laws"
        ),
        1984,
        ("Bohigas", "Giannoni", "Schmit"),
        "random-matrix quantum chaos",
        doi="10.1103/PhysRevLett.52.1",
    ),
    _record(
        "deutsch1991",
        "Quantum statistical mechanics in a closed system",
        1991,
        ("Deutsch",),
        "eigenstate thermalization",
        doi="10.1103/PhysRevA.43.2046",
    ),
    _record(
        "srednicki1994",
        "Chaos and quantum thermalization",
        1994,
        ("Srednicki",),
        "eigenstate thermalization",
        doi="10.1103/PhysRevE.50.888",
    ),
    _record(
        "dalessio2016",
        (
            "From quantum chaos and eigenstate thermalization to "
            "statistical mechanics and thermodynamics"
        ),
        2016,
        ("D'Alessio", "Kafri", "Polkovnikov", "Rigol"),
        "ETH review",
        doi="10.1080/00018732.2016.1198134",
    ),
    _record(
        "foinikurchan2019",
        (
            "Eigenstate thermalization hypothesis and out of time order "
            "correlators"
        ),
        2019,
        ("Foini", "Kurchan"),
        "higher matrix-element correlations",
        doi="10.1103/PhysRevE.99.042139",
    ),
    _record(
        "pappalardi2022",
        "Eigenstate Thermalization Hypothesis and Free Probability",
        2022,
        ("Pappalardi", "Foini", "Kurchan"),
        "full ETH and free cumulants",
        doi="10.1103/PhysRevLett.129.170603",
    ),
    _record(
        "fukui2005",
        (
            "Chern Numbers in Discretized Brillouin Zone: Efficient Method "
            "of Computing (Spin) Hall Conductances"
        ),
        2005,
        ("Fukui", "Hatsugai", "Suzuki"),
        "discrete Chern links",
        doi="10.1143/JPSJ.74.1674",
    ),
    _record(
        "chenludwig2018",
        (
            "Universal spectral correlations in the chaotic wave function, "
            "and the development of quantum chaos"
        ),
        2018,
        ("Chen", "Ludwig"),
        "non-energy spectral correlations",
        doi="10.1103/PhysRevB.98.064309",
    ),
    _record(
        "pandey2020",
        "Adiabatic eigenstate deformations as a sensitive probe for quantum chaos",
        2020,
        ("Pandey", "Claeys", "Campbell", "Polkovnikov", "Sels"),
        "adiabatic deformation chaos diagnostic",
        doi="10.1103/PhysRevX.10.041017",
    ),
    _record(
        "sharipov2024",
        "Hilbert space geometry and quantum chaos",
        2024,
        ("Sharipov", "Tiutiakina", "Gorsky", "Gritsev", "Polkovnikov"),
        "Hilbert-space geometry",
        arxiv="2411.11968",
    ),
)


def normalize(value: str) -> str:
    """Return an accent-, punctuation-, and case-insensitive comparison key."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    return "".join(character for character in ascii_text.lower() if character.isalnum())


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def parse_bibtex(path: Path) -> dict[str, str]:
    """Parse entry blocks sufficiently strictly for a controlled local BibTeX."""
    text = path.read_text(encoding="utf-8")
    matches = list(
        re.finditer(
            r"@\w+\s*\{\s*([^,\s]+)\s*,(.*?)(?=^@\w+\s*\{|\Z)",
            text,
            flags=re.DOTALL | re.MULTILINE,
        )
    )
    keys = [match.group(1) for match in matches]
    if len(keys) != len(set(keys)):
        duplicates = sorted(
            key for key in set(keys) if keys.count(key) > 1
        )
        raise ValueError(f"duplicate BibTeX keys: {duplicates}")
    return {match.group(1): match.group(0) for match in matches}


def _request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_doi_record(doi: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(doi, safe="")
    data = _request_json(
        f"https://api.openalex.org/works/https://doi.org/{encoded}"
    )
    return {
        "title": data["title"],
        "year": int(data["publication_year"]),
        "authors": [
            authorship["author"]["display_name"]
            for authorship in data["authorships"]
        ],
        "identifier": data.get("doi", f"https://doi.org/{doi}"),
        "metadata_source": "OpenAlex DOI resolution",
    }


def fetch_arxiv_record(arxiv_id: str) -> dict[str, Any]:
    url = (
        "https://export.arxiv.org/api/query?id_list="
        + urllib.parse.quote(arxiv_id)
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", namespace)
    if entry is None:
        raise LookupError(f"arXiv did not return {arxiv_id}")
    title = " ".join(
        (entry.findtext("atom:title", default="", namespaces=namespace)).split()
    )
    published = entry.findtext(
        "atom:published",
        default="",
        namespaces=namespace,
    )
    authors = [
        author.findtext("atom:name", default="", namespaces=namespace)
        for author in entry.findall("atom:author", namespace)
    ]
    return {
        "title": title,
        "year": int(published[:4]),
        "authors": authors,
        "identifier": f"https://arxiv.org/abs/{arxiv_id}",
        "metadata_source": "arXiv Atom API",
    }


def validate_record(
    expected: dict[str, Any],
    observed: dict[str, Any],
) -> dict[str, Any]:
    expected_title = normalize(expected["title"])
    observed_title = normalize(observed["title"])
    title_similarity = SequenceMatcher(
        None,
        expected_title,
        observed_title,
    ).ratio()
    observed_authors = normalize(" ".join(observed["authors"]))
    author_matches = {
        author: normalize(author) in observed_authors
        for author in expected["authors"]
    }
    checks = {
        "title": title_similarity >= 0.90,
        "year": int(expected["year"]) == int(observed["year"]),
        "authors": all(author_matches.values()),
    }
    return {
        **expected,
        "observed": observed,
        "title_similarity": title_similarity,
        "author_matches": author_matches,
        "checks": checks,
        "verified": all(checks.values()),
    }


def _write_markdown(audit: dict[str, Any], path: Path) -> None:
    lines = [
        "# Citation audit: *From Local Repulsion to Global Geometry*",
        "",
        (
            "Generated on 2026-07-28 by the task-local citation validator. "
            "Each bibliography entry is assigned to an intended manuscript "
            "section and resolved through a DOI or arXiv identifier."
        ),
        "",
        f"Overall status: **{'PASS' if audit['all_checks_pass'] else 'FAIL'}**.",
        "",
        "| Key | Intended use | Verified metadata | Result |",
        "|---|---|---|---|",
    ]
    for record in audit["records"]:
        if record.get("doi"):
            link = f"https://doi.org/{record['doi']}"
            label = f"DOI {record['doi']}"
        else:
            link = f"https://arxiv.org/abs/{record['arxiv']}"
            label = f"arXiv:{record['arxiv']}"
        status = "PASS" if record["verified"] else "FAIL"
        lines.append(
            f"| `{record['key']}` | {record['section']} | "
            f"[{label}]({link}) | **{status}** |"
        )
    lines.extend(
        [
            "",
            "## Audit contract",
            "",
            (
                "The validator rejects an unresolved identifier, a title "
                "similarity below 0.90, an incorrect publication year, a "
                "missing registered author, a duplicate BibTeX key, an "
                "unregistered bibliography entry, or a registered source "
                "missing from the bibliography."
            ),
            "",
            (
                "The citation map is intentionally article-specific. Passing "
                "this audit establishes bibliographic identity; the final "
                "delivery audit separately verifies that every key is cited "
                "in the compiled manuscript or supplement."
            ),
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(
    bib_path: Path = DEFAULT_BIB,
    output_json: Path = DEFAULT_JSON,
    output_markdown: Path = DEFAULT_MARKDOWN,
    *,
    observed_override: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entries = parse_bibtex(bib_path)
    registry_by_key = {record["key"]: record for record in REGISTRY}
    entry_keys = set(entries)
    registry_keys = set(registry_by_key)
    missing_bib = sorted(registry_keys - entry_keys)
    unregistered_bib = sorted(entry_keys - registry_keys)

    results = []
    errors = []
    for expected in REGISTRY:
        key = expected["key"]
        try:
            if observed_override is not None:
                observed = observed_override[key]
            elif expected["doi"]:
                observed = fetch_doi_record(expected["doi"])
            else:
                observed = fetch_arxiv_record(expected["arxiv"])
            result = validate_record(expected, observed)
        except Exception as exc:  # network/metadata failures are audit failures
            result = {
                **expected,
                "verified": False,
                "checks": {
                    "title": False,
                    "year": False,
                    "authors": False,
                },
                "error": f"{type(exc).__name__}: {exc}",
            }
            errors.append({"key": key, "error": result["error"]})

        entry = entries.get(key, "")
        identifier_present = bool(
            (
                expected["doi"]
                and normalize(expected["doi"]) in normalize(entry)
            )
            or (
                expected["arxiv"]
                and expected["arxiv"] in entry
            )
        )
        result["checks"]["identifier_in_bib"] = identifier_present
        result["verified"] = bool(result["verified"] and identifier_present)
        results.append(result)

    all_checks_pass = bool(
        not missing_bib
        and not unregistered_bib
        and not errors
        and all(result["verified"] for result in results)
    )
    audit = {
        "schema_version": 1,
        "article": (
            "From Local Repulsion to Global Geometry: "
            "Large-Scale Tests of Geometric ETH"
        ),
        "bibliography": _display_path(bib_path),
        "registered_records": len(REGISTRY),
        "bibliography_records": len(entries),
        "missing_bibliography_keys": missing_bib,
        "unregistered_bibliography_keys": unregistered_bib,
        "errors": errors,
        "records": results,
        "all_checks_pass": all_checks_pass,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_markdown(audit, output_markdown)
    if not all_checks_pass:
        raise RuntimeError(
            "citation audit failed; inspect "
            f"{_display_path(output_json)}"
        )
    return audit


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bib", type=Path, default=DEFAULT_BIB)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    return parser.parse_args()


def main() -> None:
    arguments = _parse_args()
    audit = run(arguments.bib, arguments.json, arguments.markdown)
    print(
        "citation audit: PASS "
        f"({audit['registered_records']} verified records)"
    )


if __name__ == "__main__":
    main()
