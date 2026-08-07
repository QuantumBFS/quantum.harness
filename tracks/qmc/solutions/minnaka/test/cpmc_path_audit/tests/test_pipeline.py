import pathlib
import math
import hashlib
import struct
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pattern_analysis.counterfactual import compare_proposals  # noqa: E402
from pattern_analysis.plotting import save_publication_figure  # noqa: E402
from pattern_analysis.pipeline import (  # noqa: E402
    AnalysisConfig,
    mark_counterfactual_selection,
    maximum_scaled_ratio_residual,
    run_analysis,
    verify_analysis,
)
from pattern_analysis.path_records import HEADER_STRUCT, MAGIC  # noqa: E402


def synthetic_frame(config_ids, log_d, log_q):
    return pd.DataFrame(
        {
            "config_id": config_ids,
            "log_d": log_d,
            "log_q": log_q,
        }
    )


class CounterfactualTest(unittest.TestCase):
    def test_counterfactual_joins_same_config_and_physical_weight(self):
        table = compare_proposals(
            row=synthetic_frame(
                [0, 1], log_d=[2.0, 3.0], log_q=[-4.0, -5.0]
            ),
            reverse=synthetic_frame(
                [0, 1], log_d=[2.0, 3.0], log_q=[-3.0, -6.0]
            ),
            sublattice=synthetic_frame(
                [0, 1], log_d=[2.0, 3.0], log_q=[-3.5, -5.5]
            ),
            joint=synthetic_frame(
                [0, 1], log_d=[2.0, 3.0], log_q=[-2.0, -3.0]
            ),
        )

        self.assertLess(
            np.max(np.abs(table["log_d_row"] - table["log_d_joint"])),
            1e-12,
        )
        self.assertIn("score_improvement_joint", table)
        self.assertAlmostEqual(
            table.loc[0, "score_improvement_joint"], 2.0 / math.log(10.0)
        )

    def test_counterfactual_rejects_physical_weight_drift(self):
        with self.assertRaisesRegex(ValueError, "physical log D"):
            compare_proposals(
                row=synthetic_frame([0], log_d=[2.0], log_q=[-4.0]),
                reverse=synthetic_frame([0], log_d=[2.0], log_q=[-3.0]),
                sublattice=synthetic_frame(
                    [0], log_d=[2.0], log_q=[-3.5]
                ),
                joint=synthetic_frame([0], log_d=[2.1], log_q=[-2.0]),
            )


class RatioVerificationTest(unittest.TestCase):
    def test_large_ratio_uses_scaled_not_absolute_residual(self):
        steps = pd.DataFrame(
            {
                "predicted_r_plus": [1.0e9, 2.0],
                "predicted_r_minus": [1.0e9, 3.0],
                "direct_r_plus": [1.0e9, 2.0],
                "direct_r_minus": [1.0e9, 3.0],
                "ratio_residual": [6.0e-7, 2.0e-13],
            }
        )

        self.assertAlmostEqual(
            maximum_scaled_ratio_residual(steps), 1.0e-13
        )

    def test_counterfactual_selection_marks_exact_important_worst_tail(self):
        table = pd.DataFrame(
            {
                "trial": ["rhf_x"] * 4,
                "config_id": [0, 1, 2, 3],
                "log_d_row": np.log([4.0, 3.0, 0.5, 0.5]),
                "log_q_row": np.log([1.0e-4, 0.1, 0.1, 0.1]),
            }
        )

        marked = mark_counterfactual_selection(table, fraction=0.25)

        self.assertEqual(marked["worst_1pct"].sum(), 1)
        self.assertTrue(marked.loc[0, "important_worst_1pct"])
        self.assertEqual(marked.loc[0, "weight_bin"], "strongly_important")


class FigureExportTest(unittest.TestCase):
    def test_publication_export_writes_vector_and_300_dpi_raster(self):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        with tempfile.TemporaryDirectory() as directory:
            stem = pathlib.Path(directory) / "figure"
            figure, axis = plt.subplots(figsize=(3.5, 2.5))
            axis.plot([0.0, 1.0], [0.0, 1.0])

            paths = save_publication_figure(figure, stem)

            self.assertEqual({path.suffix for path in paths}, {".pdf", ".png"})
            self.assertTrue(all(path.stat().st_size > 0 for path in paths))
            plt.close(figure)


def write_synthetic_paths(
    path,
    *,
    proposal_code,
    order_code,
    slices=3,
):
    count = 1 << (4 * slices)
    record_struct = struct.Struct("<Q5d2IbBfBB")
    records = []
    for config_id in range(count):
        if config_id < 40:
            d_value = 20.0
        else:
            d_value = 0.1
        if config_id < 20:
            log_q = -10.0
        elif 40 <= config_id < 61:
            log_q = -20.0
        else:
            log_q = 0.0
        if proposal_code == 2:
            log_q += 1.0
        elif order_code == 2:
            log_q += 0.3
        elif order_code == 3:
            log_q += 0.1
        records.append(
            record_struct.pack(
                config_id,
                math.log(d_value),
                log_q,
                0.0,
                0.0,
                1.0,
                0,
                0,
                1,
                1,
                0.0,
                0,
                0,
            )
        )
    header = HEADER_STRUCT.pack(
        MAGIC,
        2,
        128,
        64,
        0x01020304,
        2,
        2,
        2,
        2,
        slices,
        1,
        proposal_code,
        order_code,
        1.0,
        8.0,
        0.1,
        count,
        count,
    )
    path.write_bytes(header + b"".join(records))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


class PipelineSmokeTest(unittest.TestCase):
    @unittest.skipUnless(
        (ROOT / "build" / "cpmc_audit").exists(),
        "build/cpmc_audit is required for integration smoke",
    )
    def test_pipeline_writes_all_artifacts_without_mutating_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            m6 = root / "m6"
            m4 = root / "m4"
            output = root / "analysis"
            m6.mkdir()
            m4.mkdir()
            primary = m6 / "paths_rhf_x_site_row.bin"
            write_synthetic_paths(primary, proposal_code=1, order_code=1)
            variants = {
                "paths_rhf_x_site_row.bin": (1, 1),
                "paths_rhf_x_site_reverse.bin": (1, 2),
                "paths_rhf_x_site_sublattice.bin": (1, 3),
                "paths_rhf_x_joint_na.bin": (2, 4),
            }
            for name, (proposal, order) in variants.items():
                write_synthetic_paths(
                    m4 / name,
                    proposal_code=proposal,
                    order_code=order,
                )
            before = {
                path: sha256(path)
                for path in [primary, *(m4 / name for name in variants)]
            }

            config = AnalysisConfig(
                m6_results=m6,
                m4_results=m4,
                output=output,
                executable=ROOT / "build" / "cpmc_audit",
                trials=("rhf_x",),
                fraction=0.01,
                progress_updates=2,
            )
            run_analysis(config)
            verification = verify_analysis(config)

            required = {
                "selection_summary.csv",
                "worst1_all.csv",
                "cases_controls.csv",
                "step_attribution.csv",
                "orthogonality_diagnostics.csv",
                "predicted_orthogonal_masks.csv",
                "slice_motif_enrichment.csv",
                "transition_motif_enrichment.csv",
                "bit_interaction_enrichment.csv",
                "counterfactual_m4.csv",
                "model_metrics.csv",
                "model_rules.txt",
                "PATTERN_REPORT.md",
            }
            self.assertLessEqual(required, {path.name for path in output.iterdir()})
            figure_files = list((output / "figures").glob("*"))
            self.assertEqual(len(figure_files), 12)
            self.assertTrue(list((output / "traces").glob("*_steps.csv")))
            self.assertTrue(list((output / "traces").glob("*_masks.csv")))
            self.assertTrue(verification["valid"])
            self.assertEqual(
                before,
                {
                    path: sha256(path)
                    for path in [primary, *(m4 / name for name in variants)]
                },
            )


if __name__ == "__main__":
    unittest.main()
