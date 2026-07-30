import re


REQUIRED_KEYS = {
    "Onsager1944",
    "BloeteCardyNightingale1986",
    "Affleck1986",
    "Wolff1989",
    "Nishimori1981",
    "HoneckerJacobsenPiccoPujol2001",
    "EfronTibshirani1993",
    "Bravyi2005",
    "SkinnerRuhmanNahum2019",
    "LiChenFisher2018",
    "WangVasseurTrebstLudwigZhu2025",
    "BlackmanVigna2021",
}


def _entries(path):
    text = path.read_text(encoding="utf-8")
    starts = list(re.finditer(r"@\w+\{([^,]+),", text))
    entries = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        body = text[match.end() : end]
        fields = {
            field.group(1).lower(): field.group(2).strip()
            for field in re.finditer(
                r"(?m)^\s*([A-Za-z]+)\s*=\s*\{(.+)\},?\s*$", body
            )
        }
        entries[match.group(1)] = fields
    return entries


def test_references_have_prb_required_titles(paper_dir):
    entries = _entries(paper_dir / "references.bib")

    assert REQUIRED_KEYS <= set(entries)
    for key, entry in entries.items():
        assert entry["author"].strip(), key
        assert entry["title"].strip(), key
        assert entry["year"].isdigit(), key
        assert {"doi", "eprint", "isbn"} & set(entry), key


def test_dois_and_arxiv_identifiers_are_well_formed(paper_dir):
    entries = _entries(paper_dir / "references.bib")

    for key, entry in entries.items():
        if "doi" in entry:
            assert re.fullmatch(r"10\.\d{4,9}/\S+", entry["doi"]), key
        if "eprint" in entry:
            assert re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})", entry["eprint"]), key


def test_every_manuscript_citation_has_a_bibliography_entry(paper_dir):
    manuscript = (paper_dir / "paper.tex").read_text(encoding="utf-8")
    bibliography = (paper_dir / "references.bib").read_text(encoding="utf-8")
    available = set(re.findall(r"@\w+\{([^,]+),", bibliography))
    cited = {
        key.strip()
        for group in re.findall(r"\\cite\{([^}]+)\}", manuscript)
        for key in group.split(",")
    }

    assert cited <= available
    assert available <= cited
