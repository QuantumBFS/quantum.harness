import json
from pathlib import Path
import unittest


class ReferencePinTests(unittest.TestCase):
    def test_rbim_reference_is_pinned_to_full_commit(self) -> None:
        metadata = json.loads(
            (
                Path(__file__).parents[1]
                / "references"
                / "rbim-baseline.json"
            ).read_text()
        )
        self.assertTrue(metadata["url"].startswith("https://github.com/"))
        self.assertEqual(len(metadata["commit"]), 40)
        int(metadata["commit"], 16)


if __name__ == "__main__":
    unittest.main()
