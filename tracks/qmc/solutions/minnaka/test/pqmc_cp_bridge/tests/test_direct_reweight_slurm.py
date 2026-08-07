#!/usr/bin/env python3
"""Static contract tests for the 1920-core production Slurm jobs."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DirectReweightSlurmTest(unittest.TestCase):
    def test_array_job_requests_ten_192_core_nodes_for_one_hour(self) -> None:
        text = (ROOT / "cluster/direct_reweight_1920x50.slurm").read_text()
        for line in (
            "#SBATCH --partition=batch",
            "#SBATCH --nodes=1",
            "#SBATCH --ntasks=1",
            "#SBATCH --cpus-per-task=192",
            "#SBATCH --array=0-9%10",
            "#SBATCH --time=01:00:00",
        ):
            self.assertIn(line, text)
        self.assertIn("--replica-id \"${SLURM_ARRAY_TASK_ID}\"", text)
        self.assertIn("--workers \"${SLURM_CPUS_PER_TASK}\"", text)
        self.assertIn("--paths-per-chain 50", text)
        self.assertIn("--chains 192", text)

    def test_merge_job_runs_only_the_strict_production_merger(self) -> None:
        text = (
            ROOT / "cluster/merge_direct_reweight_1920x50.slurm"
        ).read_text()
        self.assertIn("#SBATCH --cpus-per-task=1", text)
        self.assertIn("merge_direct_reweight_replicas.py", text)
        self.assertIn("--replicas 10", text)
        self.assertIn("--chains-per-replica 192", text)
        self.assertIn("--paths-per-chain 50", text)

    def test_smoke_job_crosses_the_old_256_chain_boundary(self) -> None:
        text = (
            ROOT / "cluster/direct_reweight_smoke_192x2.slurm"
        ).read_text()
        self.assertIn("#SBATCH --cpus-per-task=192", text)
        self.assertIn("--replica-id 1", text)
        self.assertIn("--replicas 2", text)
        self.assertIn("--chains 192", text)
        self.assertIn("--paths-per-chain 2", text)

    def test_nwrap1_rerun_preserves_the_full_production_rectangle(self) -> None:
        text = (
            ROOT / "cluster/direct_reweight_1920x50_nwrap1.slurm"
        ).read_text()
        self.assertIn("#SBATCH --array=0-9%10", text)
        self.assertIn("#SBATCH --cpus-per-task=192", text)
        self.assertIn("--nwrap 1", text)
        self.assertIn("--chains 192", text)
        self.assertIn("--paths-per-chain 50", text)
        merge = (
            ROOT / "cluster/merge_direct_reweight_1920x50_nwrap1.slurm"
        ).read_text()
        self.assertIn("direct_reweight_1920x50_nwrap1", merge)
        self.assertIn("merge_direct_reweight_replicas.py", merge)


if __name__ == "__main__":
    unittest.main(verbosity=2)
