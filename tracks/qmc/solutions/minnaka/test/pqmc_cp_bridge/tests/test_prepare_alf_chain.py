#!/usr/bin/env python3
"""Contracts for immutable, resumable six-chain ALF batches."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prepare_alf_chain import (  # noqa: E402
    ALF_START_PARAMETERS,
    deterministic_seed,
    make_parameters,
    prepare_batch,
)
from run_alf_batch import run_batch  # noqa: E402


def assignment(text: str, name: str) -> str:
    import re

    match = re.search(
        rf"(?mi)^\s*{name}\s*=\s*([^!\n]+)", text
    )
    if match is None:
        raise AssertionError(f"missing assignment {name}")
    return match.group(1).strip()


class PrepareAlfChainTest(unittest.TestCase):
    def test_bundled_parameter_template_is_available_without_alf_checkout(
        self,
    ) -> None:
        self.assertTrue(ALF_START_PARAMETERS.is_file())
        self.assertIn(
            "&VAR_Hubbard_Plain_Vanilla",
            ALF_START_PARAMETERS.read_text(encoding="utf-8"),
        )

    def test_projection_grid_and_boundary_modes(self) -> None:
        expected = {10: 420, 12: 500, 14: 580, 16: 660, 18: 740, 20: 820}
        for theta, ltrot in expected.items():
            ti = make_parameters(
                theta=theta, nbin=7, nsweep=2000, boundary="TI"
            )
            ii = make_parameters(
                theta=theta, nbin=7, nsweep=2000, boundary="II"
            )
            ti_group = ti[ti.index("&VAR_Hubbard_Plain_Vanilla"):]
            ii_group = ii[ii.index("&VAR_Hubbard_Plain_Vanilla"):]
            self.assertEqual(assignment(ti_group, "Theta"), f"{theta}.d0")
            self.assertEqual(assignment(ti_group, "Trial_boundary_mode"), "1")
            self.assertEqual(assignment(ii_group, "Trial_boundary_mode"), "0")
            self.assertEqual(assignment(ti, "NBin"), "7")
            self.assertEqual(assignment(ti, "NSweep"), "2000")
            self.assertEqual(assignment(ti, "Nwrap"), "5")
            self.assertEqual(assignment(ti_group, "Beta"), "1.d0")
            self.assertEqual(assignment(ti_group, "Dtau"), "0.05d0")
            self.assertEqual(
                int(round(
                    (2 * theta + float(
                        assignment(ti_group, "Beta").replace("d0", "")
                    ))
                    / float(
                        assignment(ti_group, "Dtau").replace("d0", "")
                    )
                )),
                ltrot,
            )

    def test_seeds_are_positive_unique_and_reproducible(self) -> None:
        values = {
            deterministic_seed(900090, theta, batch, chain)
            for theta in (10, 12, 14, 16, 18, 20)
            for batch in range(3)
            for chain in range(6)
        }
        self.assertEqual(len(values), 6 * 3 * 6)
        self.assertGreater(min(values), 0)
        self.assertEqual(
            deterministic_seed(900090, 14, 2, 5),
            deterministic_seed(900090, 14, 2, 5),
        )

    def test_prepare_ti_copies_verified_trial_and_refuses_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / "assets"
            assets.mkdir()
            hashes = {}
            for name in ("trial_T_up.dat", "trial_T_down.dat"):
                content = f"asset {name}\n"
                (assets / name).write_text(content, encoding="utf-8")
                hashes[name] = hashlib.sha256(content.encode()).hexdigest()
            (assets / "trial_manifest.json").write_text(
                json.dumps({"sha256": hashes}), encoding="utf-8"
            )
            manifest = prepare_batch(
                root / "runs",
                ensemble="TI",
                theta=10,
                batch=0,
                nbin=7,
                nsweep=2000,
                master_seed=900090,
                executable=Path("/bin/true"),
                trial_assets=assets,
            )
            self.assertEqual(manifest["ltrot"], 420)
            self.assertEqual(manifest["nwrap"], 5)
            self.assertEqual(len(manifest["chains"]), 6)
            self.assertEqual(
                len({chain["seed"] for chain in manifest["chains"]}), 6
            )
            for chain in range(6):
                chain_dir = (
                    root / "runs" / "TI" / "theta_010" / "batch_000"
                    / f"chain_{chain}"
                )
                for name in ("trial_T_up.dat", "trial_T_down.dat"):
                    self.assertEqual(
                        hashlib.sha256((chain_dir / name).read_bytes()).hexdigest(),
                        hashes[name],
                    )
            (chain_dir / "Ener_scal").write_text("raw\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "raw output"):
                prepare_batch(
                    root / "runs",
                    ensemble="TI",
                    theta=10,
                    batch=0,
                    nbin=7,
                    nsweep=2000,
                    master_seed=900090,
                    executable=Path("/bin/true"),
                    trial_assets=assets,
                )

    def test_prepare_supports_sixty_four_independent_cluster_chains(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / "assets"
            assets.mkdir()
            hashes = {}
            for name in ("trial_T_up.dat", "trial_T_down.dat"):
                content = f"asset {name}\n"
                (assets / name).write_text(content, encoding="utf-8")
                hashes[name] = hashlib.sha256(content.encode()).hexdigest()
            (assets / "trial_manifest.json").write_text(
                json.dumps({"sha256": hashes}), encoding="utf-8"
            )
            manifest = prepare_batch(
                root / "runs",
                ensemble="TI",
                theta=10,
                batch=0,
                nbin=4,
                nsweep=2000,
                master_seed=900090,
                executable=Path("/bin/true"),
                trial_assets=assets,
                chains=64,
            )
            self.assertEqual(len(manifest["chains"]), 64)
            self.assertEqual(
                len({chain["seed"] for chain in manifest["chains"]}),
                64,
            )
            self.assertTrue(
                (root / "runs" / "TI" / "theta_010" / "batch_000"
                 / "chain_63" / "parameters").is_file()
            )

    def test_prepare_batch_records_global_and_local_chain_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / "assets"
            assets.mkdir()
            hashes = {}
            for name in ("trial_T_up.dat", "trial_T_down.dat"):
                content = f"asset {name}\n"
                (assets / name).write_text(content, encoding="utf-8")
                hashes[name] = hashlib.sha256(content.encode()).hexdigest()
            (assets / "trial_manifest.json").write_text(
                json.dumps({"sha256": hashes}), encoding="utf-8"
            )
            manifest = prepare_batch(
                root / "runs",
                ensemble="TI",
                theta=10,
                batch=1,
                nbin=1,
                nsweep=13950,
                master_seed=3_700_090,
                executable=Path("/bin/true"),
                trial_assets=assets,
                chains=6,
                chain_offset=192,
            )
            self.assertEqual(manifest["chain_offset"], 192)
            self.assertEqual(
                [item["chain"] for item in manifest["chains"]],
                list(range(192, 198)),
            )
            self.assertEqual(
                [item["local_chain"] for item in manifest["chains"]],
                list(range(6)),
            )
            self.assertTrue(
                (root / "runs/TI/theta_010/batch_001/chain_197/parameters")
                .is_file()
            )

    def test_runner_propagates_failure_and_reuses_complete_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mock = root / "mock_alf.py"
            mock.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                "import sys\n"
                "seed=int(Path('seeds').read_text())\n"
                "if seed % 13 == 0: sys.exit(7)\n"
                "Path('Ener_scal').write_text('1 1\\n2 1\\n')\n"
                "Path('info').write_text('mock\\n')\n",
                encoding="utf-8",
            )
            mock.chmod(0o755)
            assets = root / "assets"
            assets.mkdir()
            hashes = {}
            for name in ("trial_T_up.dat", "trial_T_down.dat"):
                (assets / name).write_text(name, encoding="utf-8")
                hashes[name] = hashlib.sha256(name.encode()).hexdigest()
            (assets / "trial_manifest.json").write_text(
                json.dumps({"sha256": hashes}), encoding="utf-8"
            )
            batch_dir = root / "runs" / "TI" / "theta_010" / "batch_000"
            manifest = prepare_batch(
                root / "runs",
                ensemble="TI",
                theta=10,
                batch=0,
                nbin=2,
                nsweep=1,
                master_seed=1,
                executable=mock,
                trial_assets=assets,
            )
            # Force one deterministic mock failure without changing preparation.
            manifest["chains"][2]["seed"] = 26
            (batch_dir / "chain_2" / "seeds").write_text("26\n")
            (batch_dir / "batch_manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            state = run_batch(batch_dir, launcher=[])
            self.assertEqual(state["status"], "failed")
            self.assertEqual(state["chains"]["2"]["returncode"], 7)
            self.assertFalse(state["statistics_eligible"])

            for chain in manifest["chains"]:
                chain["seed"] += 1 if chain["seed"] % 13 == 0 else 0
                (batch_dir / f"chain_{chain['chain']}" / "seeds").write_text(
                    f"{chain['seed']}\n"
                )
            (batch_dir / "batch_manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            state = run_batch(batch_dir, launcher=[], resume=True)
            self.assertEqual(state["status"], "complete")
            reused = run_batch(batch_dir, launcher=[], resume=True)
            self.assertEqual(reused, state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
