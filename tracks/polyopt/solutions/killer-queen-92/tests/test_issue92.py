from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import networkx as nx
import numpy as np

from issue92.atomic_sdp import bisect_atomic_gap, solve_atomic_gap
from issue92.ed import sector_basis, sector_hamiltonian, solve_finite_patch
from issue92.graphs import GEOMETRIES, graph_summary, hyperbolic_rooted_ball, rooted_radius_one
from issue92.local_algebra import cutoff_commutator_error, local_operators
from issue92.rooted_sdp import solve_rooted_gap


CAMPAIGN_SPEC = importlib.util.spec_from_file_location(
    "issue92_build_campaign", Path(__file__).parents[1] / "scripts" / "build_campaign.py"
)
assert CAMPAIGN_SPEC is not None and CAMPAIGN_SPEC.loader is not None
BUILD_CAMPAIGN = importlib.util.module_from_spec(CAMPAIGN_SPEC)
CAMPAIGN_SPEC.loader.exec_module(BUILD_CAMPAIGN)

PRESENTATION_SPEC = importlib.util.spec_from_file_location(
    "issue92_build_presentation",
    Path(__file__).parents[1] / "scripts" / "build_presentation_manifest.py",
)
assert PRESENTATION_SPEC is not None and PRESENTATION_SPEC.loader is not None
BUILD_PRESENTATION = importlib.util.module_from_spec(PRESENTATION_SPEC)
PRESENTATION_SPEC.loader.exec_module(BUILD_PRESENTATION)

DEADLINE_SPEC = importlib.util.spec_from_file_location(
    "issue92_build_deadline",
    Path(__file__).parents[1] / "scripts" / "build_deadline_manifest.py",
)
assert DEADLINE_SPEC is not None and DEADLINE_SPEC.loader is not None
BUILD_DEADLINE = importlib.util.module_from_spec(DEADLINE_SPEC)
DEADLINE_SPEC.loader.exec_module(BUILD_DEADLINE)

RUNNER_SPEC = importlib.util.spec_from_file_location(
    "issue92_run_campaign_cell", Path(__file__).parents[1] / "scripts" / "run_campaign_cell.py"
)
assert RUNNER_SPEC is not None and RUNNER_SPEC.loader is not None
RUN_CAMPAIGN_CELL = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUN_CAMPAIGN_CELL)

AGGREGATOR_SPEC = importlib.util.spec_from_file_location(
    "issue92_aggregate_campaign", Path(__file__).parents[1] / "scripts" / "aggregate_campaign.py"
)
assert AGGREGATOR_SPEC is not None and AGGREGATOR_SPEC.loader is not None
AGGREGATE_CAMPAIGN = importlib.util.module_from_spec(AGGREGATOR_SPEC)
AGGREGATOR_SPEC.loader.exec_module(AGGREGATE_CAMPAIGN)

DEADLINE_ANALYSIS_SPEC = importlib.util.spec_from_file_location(
    "issue92_analyze_deadline",
    Path(__file__).parents[1] / "scripts" / "analyze_deadline.py",
)
assert DEADLINE_ANALYSIS_SPEC is not None and DEADLINE_ANALYSIS_SPEC.loader is not None
ANALYZE_DEADLINE = importlib.util.module_from_spec(DEADLINE_ANALYSIS_SPEC)
DEADLINE_ANALYSIS_SPEC.loader.exec_module(ANALYZE_DEADLINE)

FINAL_SUBMISSION_SPEC = importlib.util.spec_from_file_location(
    "issue92_build_final_submission",
    Path(__file__).parents[1] / "scripts" / "build_final_submission.py",
)
assert FINAL_SUBMISSION_SPEC is not None and FINAL_SUBMISSION_SPEC.loader is not None
BUILD_FINAL_SUBMISSION = importlib.util.module_from_spec(FINAL_SUBMISSION_SPEC)
FINAL_SUBMISSION_SPEC.loader.exec_module(BUILD_FINAL_SUBMISSION)


class LocalAlgebraTests(unittest.TestCase):
    def test_cutoff_commutator_and_nilpotency(self) -> None:
        for nmax in (1, 2, 3):
            with self.subTest(nmax=nmax):
                self.assertLess(cutoff_commutator_error(nmax), 1e-13)
                annihilation = local_operators(nmax)["b"]
                self.assertLess(np.linalg.norm(np.linalg.matrix_power(annihilation, nmax + 1)), 1e-13)
                self.assertGreater(np.linalg.norm(np.linalg.matrix_power(annihilation, nmax)), 0.5)


class GraphTests(unittest.TestCase):
    def test_exact_radius_one_combinatorics(self) -> None:
        expected = {
            "83": (3, 0, 3),
            "124": (4, 0, 4),
            "line83": (4, 2, 6),
        }
        for key, (degree, triangles, edges) in expected.items():
            with self.subTest(geometry=key):
                summary = graph_summary(rooted_radius_one(key))
                self.assertEqual(summary["root_degree"], degree)
                self.assertEqual(summary["triangles_at_root"], triangles)
                self.assertEqual(summary["edges"], edges)

    def test_hypertiling_matches_radius_one(self) -> None:
        for key in GEOMETRIES:
            with self.subTest(geometry=key):
                exact = rooted_radius_one(key)
                generated = hyperbolic_rooted_ball(key, 1)
                self.assertTrue(nx.is_isomorphic(exact, generated))

    def test_rooted_balls_are_stable_inside_larger_exports(self) -> None:
        node_match = nx.algorithms.isomorphism.categorical_node_match("root_marker", False)
        for key in GEOMETRIES:
            for radius in (1, 2):
                with self.subTest(geometry=key, radius=radius):
                    small = hyperbolic_rooted_ball(key, radius).copy()
                    larger = hyperbolic_rooted_ball(key, radius + 1)
                    selected = nx.single_source_shortest_path_length(larger, 0, cutoff=radius)
                    embedded = larger.subgraph(selected).copy()
                    nx.set_node_attributes(small, False, "root_marker")
                    nx.set_node_attributes(embedded, False, "root_marker")
                    small.nodes[0]["root_marker"] = True
                    embedded.nodes[0]["root_marker"] = True
                    self.assertTrue(nx.is_isomorphic(small, embedded, node_match=node_match))

    def test_degree_four_radius_two_windows_differ(self) -> None:
        g124 = hyperbolic_rooted_ball("124", 2)
        line83 = hyperbolic_rooted_ball("line83", 2)
        self.assertFalse(nx.is_isomorphic(g124, line83))
        self.assertNotEqual(g124.number_of_edges(), line83.number_of_edges())


class FiniteEDTests(unittest.TestCase):
    def test_one_particle_hopping_sign_and_hermiticity(self) -> None:
        graph = nx.Graph()
        graph.add_edge(0, 1)
        basis = sector_basis(2, 1, 1)
        hamiltonian = sector_hamiltonian(
            graph, basis, nmax=1, hopping=0.2, interaction=1.0, mu=0.0
        ).toarray()
        self.assertLess(np.linalg.norm(hamiltonian - hamiltonian.T), 1e-13)
        self.assertTrue(np.allclose(np.linalg.eigvalsh(hamiltonian), [-0.2, 0.2]))

    def test_atomic_patch_benchmark(self) -> None:
        for key in GEOMETRIES:
            for nmax in (1, 2, 3):
                with self.subTest(geometry=key, nmax=nmax):
                    result = solve_finite_patch(
                        rooted_radius_one(key), nmax=nmax, hopping=0.0, mu=0.5
                    )
                    self.assertAlmostEqual(result.finite_patch_gap, 0.5, places=10)
                    self.assertAlmostEqual(result.rho0, 1.0, places=10)
                    self.assertAlmostEqual(result.F0, 0.0, places=10)
                    self.assertAlmostEqual(result.K0, 0.0, places=10)


class AtomicStatePolynomialTests(unittest.TestCase):
    def test_gap_feasibility_changes_at_half(self) -> None:
        for nmax in (1, 2, 3):
            with self.subTest(nmax=nmax):
                below = solve_atomic_gap(nmax, 0.49)
                above = solve_atomic_gap(nmax, 0.51)
                self.assertEqual(below.classification, "FEASIBLE")
                self.assertEqual(above.classification, "INFEASIBLE")
                self.assertIsNotNone(below.probabilities)
                self.assertTrue(np.allclose(below.probabilities, [0.0, 1.0] + [0.0] * (nmax - 1), atol=2e-6))

    def test_bisection_recovers_atomic_gap(self) -> None:
        lower, upper, _ = bisect_atomic_gap(2, tolerance=2e-5)
        self.assertLessEqual(lower, 0.50002)
        self.assertGreaterEqual(upper, 0.49998)
        self.assertLessEqual(upper - lower, 2e-5)


class RootedThermodynamicSDPTests(unittest.TestCase):
    def test_rooted_relaxation_recovers_atomic_threshold(self) -> None:
        graph = rooted_radius_one("83")
        below = solve_rooted_gap(graph, 1, 0.49, hopping=0.0, mu=0.5)
        above = solve_rooted_gap(graph, 1, 0.51, hopping=0.0, mu=0.5)
        self.assertEqual(below.classification, "FEASIBLE")
        self.assertEqual(above.classification, "INFEASIBLE")


class CampaignManifestTests(unittest.TestCase):
    def test_scientific_classifications_are_closed(self) -> None:
        for value in ("FEASIBLE", "EXCLUDED", "UNKNOWN", "feasible", None):
            self.assertIn(
                AGGREGATE_CAMPAIGN.scientific_classification(value),
                AGGREGATE_CAMPAIGN.SCIENTIFIC_CLASSIFICATIONS,
            )
        for invalid in ("BRACKETED", "VERIFIED_EXCLUSION"):
            with self.assertRaises(ValueError):
                AGGREGATE_CAMPAIGN.scientific_classification(invalid)

    def test_slurm_memory_parser(self) -> None:
        self.assertEqual(RUN_CAMPAIGN_CELL.slurm_memory_mb("65536"), 65536)
        self.assertEqual(RUN_CAMPAIGN_CELL.slurm_memory_mb("64G"), 65536)
        self.assertEqual(RUN_CAMPAIGN_CELL.slurm_memory_mb("1.5T"), 1572864)

    def test_level_report_accepts_dry_level_manifest_schema(self) -> None:
        cell = {
            "id": "dry-toy", "geometry": "83", "nmax": 2, "L": 1, "d": 3,
            "encoding": "matrix", "basis_family": "ts2",
            "symmetry": "U1_INVARIANT_KMS_STATES", "requested_memory_gb": 192,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            results = root / "results"
            results.mkdir()
            manifest.write_text(json.dumps({"levels": [cell]}))
            (results / "dry-toy.json").write_text(
                json.dumps(
                    {
                        "level": {
                            "window_sites": 4, "interior_sites": 1, "induced_edges": 3,
                            "moment_basis_count": 10, "moment_block_sizes": [4, 6],
                            "gap_basis_count": 2, "gap_block_sizes": [2],
                            "equality_count": 3, "real_scalar_variable_count": 12,
                            "affine_term_count": 20, "estimated_memory_gb": 1.0,
                        },
                        "runner": {"allocated_memory_gb": 237, "max_rss_gb": 5.5},
                    }
                )
            )
            rows = ANALYZE_DEADLINE.level_size_rows([(manifest, results)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["basis_family"], "ts2")
        self.assertEqual(rows[0]["requested_memory_gb"], 237.0)
        self.assertEqual(rows[0]["max_rss_gb"], 5.5)

    def test_primary_workload_count(self) -> None:
        cells = list(BUILD_CAMPAIGN.primary_cells())
        self.assertEqual(sum(cell["kind"] == "gap" for cell in cells), 90)
        self.assertEqual(sum(cell["kind"] == "observable" for cell in cells) * 6, 1620)

    def test_presentation_subset_is_explicitly_diagnostic(self) -> None:
        cells = BUILD_PRESENTATION.presentation_cells()
        self.assertEqual(len(cells), 12)
        self.assertEqual({cell["point"] for cell in cells}, {"P2", "P4"})
        self.assertTrue(all(cell["diagnostic_only"] for cell in cells))
        self.assertEqual(
            {(cell["geometry"], cell["point"]) for cell in cells},
            {("83", "P2"), ("124", "P2"), ("line83", "P2"), ("83", "P4")},
        )

    def test_deadline_campaign_is_small_nested_and_nonadaptive(self) -> None:
        nested = BUILD_DEADLINE.nested_cells()
        scans = BUILD_DEADLINE.gap_scan_cells()
        refinements = BUILD_DEADLINE.gap_refinement_cells()
        retries = BUILD_DEADLINE.gap_retry_cells()
        micro = BUILD_DEADLINE.gap_micro_cells()
        geometry_refinements = BUILD_DEADLINE.geometry_refinement_cells()
        geometry_parallel = BUILD_DEADLINE.geometry_parallel_recovery_cells()
        geometry_micro = BUILD_DEADLINE.geometry_micro_recovery_cells()
        geometry_grid = BUILD_DEADLINE.geometry_target_grid_cells()
        final_geometry_refinements = BUILD_DEADLINE.final_geometry_refinement_cells()
        remaining_gaps = BUILD_DEADLINE.remaining_target_gap_cells()
        target_refinements = BUILD_DEADLINE.target_refinement_cells()
        p5_fine = BUILD_DEADLINE.p5_fine_refinement_cells()
        p3_micro = BUILD_DEADLINE.p3_micro_refinement_cells()
        remaining_observables = BUILD_DEADLINE.remaining_target_observable_cells()
        cutoff2_gaps = BUILD_DEADLINE.representative_cutoff2_gap_cells()
        exact_observables = BUILD_DEADLINE.exact_observable_cells()
        self.assertEqual({(item["L"], item["d"]) for item in nested}, {(1, 3), (2, 2)})
        self.assertTrue(all(item["geometry"] == "83" and item["gamma"] == 0 for item in nested))
        self.assertTrue(all(item["requested_memory_gb"] == 192 for item in nested))
        self.assertEqual(
            {(item["geometry"], item["point"]) for item in scans},
            {("83", "P2"), ("124", "P2"), ("line83", "P2"), ("83", "P4")},
        )
        self.assertTrue(all(item["kind"] == "gap_scan" for item in scans))
        self.assertTrue(all(item["diagnostic_only"] for item in [*nested, *scans]))
        self.assertTrue(all(item["gamma_trials"][0] == 0 for item in scans))
        self.assertTrue(all(item["feasible_anchor_path"].endswith("g0.00.json") for item in scans))
        self.assertEqual(sum(len(item["gamma_trials"]) for item in scans), 35)
        self.assertEqual({item["point"] for item in refinements}, {"P2", "P4"})
        self.assertEqual([len(item["gamma_trials"]) for item in refinements], [21, 11])
        self.assertTrue(
            all(
                abs(b - a - 0.005) < 1e-12
                for item in refinements
                for a, b in zip(item["gamma_trials"], item["gamma_trials"][1:])
            )
        )
        self.assertEqual(len(p5_fine), 1)
        self.assertEqual(p5_fine[0]["point"], "P5")
        self.assertEqual(p5_fine[0]["gamma_trials"], [0.765, 0.755, 0.775, 0.760, 0.770])
        self.assertEqual(len(p3_micro), 1)
        self.assertEqual(p3_micro[0]["point"], "P3")
        self.assertEqual(p3_micro[0]["gamma_trials"], [0.514, 0.516, 0.512, 0.518])
        self.assertEqual(len(retries), 1)
        self.assertEqual(retries[0]["gamma_trials"], [0.510, 0.515])
        self.assertEqual(retries[0]["requested_direct_solver"], "qdldl")
        self.assertEqual(len(micro), 1)
        self.assertEqual(micro[0]["gamma_trials"], [0.511, 0.509, 0.512, 0.508])
        self.assertNotIn(0.510, micro[0]["gamma_trials"])
        self.assertEqual(
            {item["geometry"] for item in geometry_refinements}, {"124", "line83"}
        )
        self.assertTrue(
            all(item["gamma_trials"] == [0.52, 0.51, 0.54, 0.56, 0.58]
                for item in geometry_refinements)
        )
        self.assertEqual(len(geometry_parallel), 1)
        self.assertEqual(geometry_parallel[0]["geometry"], "124")
        self.assertEqual(geometry_parallel[0]["gamma_trials"], [0.51, 0.54])
        self.assertEqual(
            [(item["geometry"],item["gamma_trials"]) for item in geometry_micro],
            [("124",[0.515]),("line83",[0.53])],
        )
        self.assertEqual(len(geometry_grid), 8)
        self.assertEqual(
            {(item["geometry"], item["point"]) for item in geometry_grid},
            {
                (geometry, point)
                for geometry in ("124", "line83")
                for point in ("P1", "P3", "P4", "P5")
            },
        )
        self.assertTrue(all(item["gamma_trials"][-1] == 0.0 for item in geometry_grid))
        self.assertEqual(sum(len(item["gamma_trials"]) for item in geometry_grid), 16)
        self.assertEqual(len(final_geometry_refinements), 4)
        self.assertEqual(
            [
                (item["geometry"], item["point"], item["gamma_trials"])
                for item in final_geometry_refinements
            ],
            [
                ("124", "P4", [0.170, 0.160]),
                ("line83", "P4", [0.170, 0.160]),
                ("124", "P5", [0.800, 0.750]),
                ("line83", "P4", [0.165]),
            ],
        )
        self.assertEqual({item["point"] for item in remaining_gaps}, {"P1", "P3", "P5"})
        self.assertEqual(sum(len(item["gamma_trials"]) for item in remaining_gaps), 30)
        self.assertEqual([item["point"] for item in target_refinements], ["P5", "P1", "P3"])
        self.assertEqual([len(item["gamma_trials"]) for item in target_refinements], [7, 19, 19])
        self.assertEqual(target_refinements[0]["gamma_trials"][0], 0.875)
        self.assertTrue(
            all(
                abs(b - a - 0.005) < 1e-12
                for item in target_refinements[1:]
                for a, b in zip(item["gamma_trials"], item["gamma_trials"][1:])
            )
        )
        self.assertEqual(len(remaining_observables), 9)
        self.assertEqual({item["point"] for item in remaining_observables}, {"P1", "P3", "P5"})
        self.assertEqual({item["gamma"] for item in remaining_observables}, {0.0, 0.05, 0.10})
        self.assertTrue(all(item["geometry"] == "83" for item in remaining_observables))
        self.assertEqual(len(cutoff2_gaps), 1)
        self.assertEqual(cutoff2_gaps[0]["nmax"], 2)
        self.assertEqual(cutoff2_gaps[0]["gamma_trials"], [0.75, 0.0, 0.60, 0.50])
        self.assertEqual(len(exact_observables), 1)
        self.assertEqual(
            (exact_observables[0]["geometry"], exact_observables[0]["point"], exact_observables[0]["gamma"]),
            ("83", "P4", 0.10),
        )
        self.assertTrue(exact_observables[0]["exact_observable_certificate"])

    def test_deadline_analysis_accepts_only_two_checked_endpoints(self) -> None:
        common = {
            "id": "toy", "geometry": "83", "point": "P2", "t": 0.05,
            "mu": 0.5, "gamma": 0.0, "nmax": 1, "L": 1, "d": 2,
            "observable": "rho0", "certificate_class": "PRIMAL_DUAL_CHECKED",
        }
        accepted = ANALYZE_DEADLINE.interval_rows(
            [
                {**common, "sense": "min", "classification": "FEASIBLE", "optimum": 0.9},
                {**common, "sense": "max", "classification": "FEASIBLE", "optimum": 1.0},
            ]
        )
        self.assertEqual(len(accepted), 1)
        self.assertTrue(accepted[0]["accepted"])
        rejected = ANALYZE_DEADLINE.interval_rows(
            [
                {**common, "sense": "min", "classification": "FEASIBLE", "optimum": 0.9},
                {**common, "sense": "max", "classification": "UNKNOWN", "optimum": 1.0},
            ]
        )
        self.assertFalse(rejected[0]["accepted"])

    def test_deadline_report_preserves_floating_endpoints(self) -> None:
        common = {
            "id": "toy", "geometry": "83", "point": "P2", "t": 0.05,
            "mu": 0.5, "gamma": 0.0, "nmax": 1, "L": 1, "d": 2,
            "observable": "rho0", "certificate_class": "NO_CERTIFICATE",
            "raw_status": "OPTIMAL", "cell_status": "COMPLETE",
        }
        records = [
            {**common, "sense": "min", "classification": "FEASIBLE", "optimum": 0.9},
            {**common, "sense": "max", "classification": "UNKNOWN", "optimum": 1.0},
        ]
        self.assertEqual(ANALYZE_DEADLINE.evidence_tier(records[0]), "ACCEPTED")
        self.assertEqual(ANALYZE_DEADLINE.evidence_tier(records[1]), "FLOATING")
        working = ANALYZE_DEADLINE.working_interval_rows(records)
        self.assertEqual(len(working), 1)
        self.assertEqual(working[0]["lower_tier"], "ACCEPTED")
        self.assertEqual(working[0]["upper_tier"], "FLOATING")
        self.assertFalse(ANALYZE_DEADLINE.interval_rows(records)[0]["accepted"])
        exact_upgrade = {
            **records[0],
            "id": "toy-exact",
            "optimum": 0.8999,
            "certificate_class": "VERIFIED_EXACT_PROJECTED_BOUND",
            "certificate_precision_bits": 256,
        }
        deduplicated = ANALYZE_DEADLINE.deduplicate_observable_rows(
            [records[0], records[1], exact_upgrade]
        )
        self.assertEqual(len(deduplicated), 2)
        self.assertEqual(
            next(row for row in deduplicated if row["sense"] == "min")["id"],
            "toy-exact",
        )
        # Exact upgrades are separate resumable campaign cells, but interval
        # construction must still pair them with the strongest opposite side
        # for the same physical model/observable.
        upgraded_working = ANALYZE_DEADLINE.working_interval_rows(deduplicated)
        self.assertEqual(len(upgraded_working), 1)
        self.assertEqual(upgraded_working[0]["lower"], 0.8999)
        self.assertEqual(upgraded_working[0]["upper"], 1.0)

    def test_gap_summary_uses_only_verified_exclusion_and_checked_feasibility(self) -> None:
        common = {
            "geometry": "83", "point": "P2", "t": 0.05, "mu": 0.5,
            "nmax": 1, "L": 1, "d": 2, "message": "",
        }
        summaries = ANALYZE_DEADLINE.gap_bracket_rows(
            [
                {**common, "gamma": 0.50, "classification": "FEASIBLE", "certificate_class": "PRIMAL_CHECKED"},
                {**common, "gamma": 0.55, "classification": "UNKNOWN", "certificate_class": "NO_CERTIFICATE"},
                {**common, "gamma": 0.60, "classification": "EXCLUDED", "certificate_class": "VERIFIED_EXACT_PROJECTED"},
            ]
        )
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["last_not_excluded"], 0.50)
        self.assertEqual(summaries[0]["upper_endpoint"], 0.60)
        self.assertAlmostEqual(summaries[0]["sample_width"], 0.10)
        self.assertAlmostEqual(summaries[0]["search_span"], 0.10)
        self.assertEqual(summaries[0]["unknown_between"], 1)
        comparison_seed = [
            {
                "geometry": "83", "point": "P2", "nmax": 1, "L": 1, "d": 2,
                "upper_endpoint": 0.51, "search_span": 0.01, "unknown_between": 0,
            },
            {
                "geometry": "124", "point": "P2", "nmax": 1, "L": 1, "d": 2,
                "upper_endpoint": 0.60, "search_span": 0.10, "unknown_between": 0,
            },
            {
                "geometry": "83", "point": "P4", "nmax": 1, "L": 1, "d": 2,
                "upper_endpoint": 0.165, "search_span": 0.005, "unknown_between": 0,
            },
            {
                "geometry": "83", "point": "P2", "nmax": 2, "L": 1, "d": 2,
                "upper_endpoint": 0.75, "search_span": None, "unknown_between": 0,
            },
        ]
        comparisons = ANALYZE_DEADLINE.gap_comparison_rows(comparison_seed)
        self.assertEqual(
            {item["dimension"] for item in comparisons},
            {"geometry", "parameter point", "cutoff"},
        )
        self.assertTrue(all("true" in item["claim_boundary"] or item["dimension"] != "geometry"
                            for item in comparisons))

    def test_final_submission_separates_upper_statements_from_search_spans(self) -> None:
        common = {
            "geometry": "83", "point": "P2", "t": "0.05", "mu": "0.5",
            "nmax": "1", "L": "1", "d": "2",
        }
        rows = BUILD_FINAL_SUBMISSION.transition_rows(
            [
                {**common, "gamma": "0.50", "classification": "FEASIBLE", "certificate_class": "PRIMAL_CHECKED"},
                {**common, "gamma": "0.55", "classification": "UNKNOWN", "certificate_class": "NO_CERTIFICATE"},
                # A solver-only exclusion is not allowed into the submission.
                {**common, "gamma": "0.575", "classification": "EXCLUDED", "certificate_class": "FLOATING_CANDIDATE"},
                {
                    **common, "gamma": "0.60", "classification": "EXCLUDED",
                    "certificate_class": "VERIFIED_EXACT_PROJECTED",
                },
                {
                    **common, "point": "P4", "t": "0.03", "mu": "0.15",
                    "gamma": "0.30", "classification": "EXCLUDED",
                    "certificate_class": "VERIFIED_EXACT_PROJECTED",
                },
            ]
        )
        p2 = next(row for row in rows if row["point"] == "P2")
        self.assertEqual(p2["last_feasible"], 0.50)
        self.assertEqual(p2["verified_excluded"], 0.60)
        self.assertEqual(p2["unresolved_inside"], 2)
        self.assertFalse(p2["clean_0p005"])
        p4 = next(row for row in rows if row["point"] == "P4")
        self.assertIsNone(p4["last_feasible"])
        self.assertIsNone(p4["search_span"])
        self.assertEqual(p4["verified_excluded"], 0.30)

    def test_unique_dry_levels_and_tiers(self) -> None:
        cells = [
            *BUILD_CAMPAIGN.primary_cells(),
            *BUILD_CAMPAIGN.comparison_cells(),
            *BUILD_CAMPAIGN.optional_cells(),
        ]
        levels = BUILD_CAMPAIGN.dry_levels(cells)
        self.assertEqual(len(levels), 38)
        self.assertEqual(len({level["id"] for level in levels}), 38)
        tiers = BUILD_CAMPAIGN.dry_tiers(levels)
        self.assertEqual(
            {memory: tier["count"] for memory, tier in tiers.items()},
            {"64": 17, "192": 16, "225": 5},
        )
        self.assertEqual(tiers["64"]["slurm_array_spec"], "0-11,13-17")
        self.assertEqual(tiers["192"]["slurm_array_spec"], "12,18-32")


if __name__ == "__main__":
    unittest.main()
