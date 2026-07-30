import json
from pathlib import Path
import re
import unittest


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = SOLUTION_ROOT / "knowledge"
ALLOWED_STATUSES = {
    "exact-constraint",
    "numerical-evidence",
    "working-hypothesis",
    "open-question",
}


def load_json_yaml(filename):
    path = KNOWLEDGE_ROOT / filename
    if not path.exists():
        raise AssertionError(f"{path.relative_to(SOLUTION_ROOT)} has not been implemented")
    return json.loads(path.read_text(encoding="utf-8"))


class KnowledgeBaseTests(unittest.TestCase):
    def test_claims_are_typed_and_traceable(self):
        payload = load_json_yaml("claims.yaml")
        self.assertGreaterEqual(len(payload["claims"]), 8)
        for claim in payload["claims"]:
            self.assertIn(claim["status"], ALLOWED_STATUSES)
            self.assertTrue(claim["claim_id"])
            self.assertTrue(claim["statement"])
            self.assertIsInstance(claim["source_ids"], list)
            self.assertTrue(claim["scope"])
            self.assertTrue(claim["limitations"])
            if claim["source_traceable"]:
                self.assertGreater(len(claim["source_ids"]), 0)

    def test_material_cases_cover_required_benchmarks(self):
        payload = load_json_yaml("material_cases.yaml")
        cases = {case["case_id"]: case for case in payload["cases"]}
        required = {
            "ueg-finite-q",
            "srvo3-jahn-teller",
            "srvo3-breathing",
            "cacu2o-half-breathing",
            "cacu2o-full-breathing",
            "cacu2o-dynamic",
            "coo-dfpt-u",
            "bkbio3-gwpt",
        }
        self.assertTrue(required.issubset(cases))
        for case in cases.values():
            for field in (
                "material",
                "mode",
                "q_point",
                "frequency_or_limit",
                "observable",
                "status",
                "source_ids",
                "normalization_note",
                "limitations",
                "verification_state",
            ):
                self.assertIn(field, case)
            self.assertIn(case["status"], ALLOWED_STATUSES)
            for value in case.get("reported_values", []):
                self.assertEqual(
                    set(value),
                    {"method", "value", "unit", "source_id", "source_location"},
                )

    def test_every_source_id_resolves_to_bibliography(self):
        claims = load_json_yaml("claims.yaml")["claims"]
        cases = load_json_yaml("material_cases.yaml")["cases"]
        bib_path = KNOWLEDGE_ROOT / "references.bib"
        if not bib_path.exists():
            self.fail("knowledge/references.bib has not been implemented")
        keys = set(re.findall(r"@[A-Za-z]+\{([^,]+),", bib_path.read_text(encoding="utf-8")))
        cited = {
            source_id
            for record in claims + cases
            for source_id in record["source_ids"]
        }
        self.assertTrue(cited.issubset(keys), f"missing bibliography keys: {sorted(cited - keys)}")

    def test_schema_declares_required_provenance_fields(self):
        schema = load_json_yaml("schema.yaml")
        claim_required = set(schema["definitions"]["claim"]["required"])
        case_required = set(schema["definitions"]["material_case"]["required"])
        self.assertTrue(
            {"claim_id", "status", "source_ids", "scope", "limitations", "source_traceable"}
            .issubset(claim_required)
        )
        self.assertTrue(
            {"case_id", "status", "source_ids", "normalization_note", "verification_state"}
            .issubset(case_required)
        )


if __name__ == "__main__":
    unittest.main()
