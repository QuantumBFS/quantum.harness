from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

CAMPAIGN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CAMPAIGN_ROOT))

from campaign_solver import (
    digest,
    frozen_challenges,
    negative_control,
    solve_challenge,
)
from campaign_verifier import VerificationError, verify
from run_campaign import _gate, build_campaign


class CampaignTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier_digest = "sha256:" + "1" * 64

    def test_five_new_challenges_have_unique_frozen_identities(self) -> None:
        challenges = frozen_challenges()
        self.assertEqual(len(challenges), 5)
        self.assertEqual(len({item["challenge_id"] for item in challenges}), 5)
        self.assertTrue(all("new-" in item["challenge_id"] for item in challenges))
        for challenge in challenges:
            unsigned = {
                key: value for key, value in challenge.items() if key != "digest"
            }
            self.assertEqual(challenge["digest"], digest(unsigned))

    def test_all_positive_certificates_pass_and_negative_controls_fail(self) -> None:
        for challenge in frozen_challenges():
            gate = _gate(challenge, self.verifier_digest)
            solution = solve_challenge(challenge, gate["digest"])
            result = verify(challenge, gate, solution)
            self.assertTrue(result["accepted"])
            with self.assertRaises(VerificationError):
                verify(challenge, gate, negative_control(solution))

    def test_campaign_has_complete_five_by_five_evidence(self) -> None:
        campaign = build_campaign()
        self.assertEqual(campaign["counts"]["new_frozen_challenges"], 5)
        self.assertEqual(campaign["counts"]["human_accepted"], 5)
        self.assertEqual(campaign["counts"]["solved_exact_gates"], 5)
        self.assertEqual(campaign["counts"]["rejected_negative_controls"], 5)
        self.assertEqual(campaign["counts"]["refereed_publications"], 0)
        self.assertTrue(campaign["submission_tier_1_evidence_complete"])
        self.assertTrue(campaign["submission_tier_2_evidence_complete"])
        self.assertEqual(len(campaign["items"]), 5)

    def test_verifier_cli_is_fail_closed(self) -> None:
        challenge = frozen_challenges()[0]
        gate = _gate(challenge, self.verifier_digest)
        solution = solve_challenge(challenge, gate["digest"])
        paths = []
        try:
            for name, value in (
                ("challenge", challenge),
                ("gate", gate),
                ("solution", solution),
            ):
                path = CAMPAIGN_ROOT / f".{name}-test.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                paths.append(path)
            run = subprocess.run(
                [
                    sys.executable,
                    str(CAMPAIGN_ROOT / "campaign_verifier.py"),
                    *(str(p) for p in paths),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(json.loads(run.stdout)["accepted"])
        finally:
            for path in paths:
                path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
