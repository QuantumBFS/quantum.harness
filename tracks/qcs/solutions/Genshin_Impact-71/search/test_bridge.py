from __future__ import annotations

import unittest

from bridge import (
    BlifGate,
    BlifNetwork,
    OccamCircuit,
    OccamGate,
    OPS_SET,
    blif_to_occam,
    occam_to_blif,
    verify_equivalent,
    verify_occam_equivalent,
)


class StrictParsingTests(unittest.TestCase):
    def test_occam_rejects_prompt_like_text(self) -> None:
        with self.assertRaises(ValueError):
            OccamCircuit.parse_text(
                "INPUTS 2\nignore previous instructions\nOUTPUTS x1\n"
            )

    def test_blif_rejects_unknown_directive(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported BLIF directive"):
            BlifNetwork.parse_text(
                ".model m\n.inputs a\n.outputs a\n.shell do_something\n.end\n"
            )

    def test_blif_rejects_non_topological_gate(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-topological"):
            BlifNetwork.parse_text(
                ".model m\n"
                ".inputs a b\n"
                ".outputs y\n"
                ".names future a y\n"
                "11 1\n"
                ".names a b future\n"
                "11 1\n"
                ".end\n"
            )

    def test_blif_rejects_mixed_output_planes(self) -> None:
        with self.assertRaisesRegex(ValueError, "mixed output planes"):
            BlifNetwork.parse_text(
                ".model m\n"
                ".inputs a b\n"
                ".outputs y\n"
                ".names a b y\n"
                "00 0\n"
                "11 1\n"
                ".end\n"
            )

    def test_continuation_and_negative_plane(self) -> None:
        network = BlifNetwork.parse_text(
            ".model m\n"
            ".inputs a \\\n"
            " b\n"
            ".outputs y\n"
            ".names a b y\n"
            "11 0\n"
            ".end\n"
        )
        self.assertEqual((1, 1, 1, 0), network.gates[0].table)


class BridgeTests(unittest.TestCase):
    def assert_bridge_equivalent(
        self, circuit: OccamCircuit, expected_gate_count: int | None = None
    ) -> OccamCircuit:
        blif = occam_to_blif(circuit)
        first_audit = verify_equivalent(circuit, blif)
        self.assertTrue(first_audit["equivalent"], first_audit)
        reparsed = BlifNetwork.parse_text(blif.to_text())
        rebuilt = blif_to_occam(reparsed)
        second_audit = verify_occam_equivalent(circuit, rebuilt)
        self.assertTrue(second_audit["equivalent"], second_audit)
        if expected_gate_count is not None:
            self.assertEqual(expected_gate_count, len(rebuilt.gates))
        return rebuilt

    def test_free_internal_and_output_phases_round_trip(self) -> None:
        circuit = OccamCircuit(
            3,
            (
                OccamGate("w1", "AND", "~x1", "x2"),
                OccamGate("w2", "XOR", "~w1", "x3"),
                OccamGate("w3", "NOR", "w1", "~w2"),
            ),
            ("~w3", "w2", "~w1"),
        )
        rebuilt = self.assert_bridge_equivalent(circuit, 3)
        self.assertTrue(all(gate.op in OPS_SET for gate in rebuilt.gates))

    def test_output_in_both_polarities_costs_no_occam_gate(self) -> None:
        circuit = OccamCircuit(
            2,
            (OccamGate("w1", "AND", "x1", "x2"),),
            ("w1", "~w1"),
        )
        blif = occam_to_blif(circuit)
        self.assertEqual(2, len(blif.gates))
        rebuilt = blif_to_occam(blif)
        self.assertEqual(1, len(rebuilt.gates))
        self.assertTrue(verify_occam_equivalent(circuit, rebuilt)["equivalent"])

    def test_complemented_primary_output_is_free_after_return(self) -> None:
        circuit = OccamCircuit(2, (), ("~x1", "x1", "~x2"))
        blif = occam_to_blif(circuit)
        rebuilt = blif_to_occam(blif)
        self.assertEqual(0, len(rebuilt.gates))
        self.assertTrue(verify_occam_equivalent(circuit, rebuilt)["equivalent"])

    def test_numeric_eslim_style_identifiers(self) -> None:
        network = BlifNetwork.parse_text(
            ".model spec\n"
            ".inputs 1 2\n"
            ".outputs 4 5\n"
            ".names 1 2 3\n"
            "01 1\n"
            "10 1\n"
            ".names 3 4\n"
            "0 1\n"
            ".names 3 5\n"
            "1 1\n"
            ".end\n"
        )
        circuit = blif_to_occam(network)
        self.assertEqual(1, len(circuit.gates))
        self.assertTrue(verify_equivalent(circuit, network)["equivalent"])

    def test_all_sixteen_binary_functions(self) -> None:
        for mask in range(16):
            with self.subTest(mask=mask):
                table = tuple((mask >> index) & 1 for index in range(4))
                network = BlifNetwork(
                    "all_functions",
                    ("a", "b"),
                    ("y",),
                    (BlifGate("y", ("a", "b"), table),),
                )
                circuit = blif_to_occam(network)
                dependencies = []
                if table[0] != table[2] or table[1] != table[3]:
                    dependencies.append("a")
                if table[0] != table[1] or table[2] != table[3]:
                    dependencies.append("b")
                expected = 1 if len(dependencies) in {0, 2} else 0
                self.assertEqual(expected, len(circuit.gates))
                self.assertTrue(
                    verify_equivalent(circuit, network)["equivalent"]
                )
                self.assertTrue(
                    all(gate.op in OPS_SET for gate in circuit.gates)
                )

    def test_constants_are_propagated_and_shared(self) -> None:
        network = BlifNetwork(
            "constants",
            ("a", "b"),
            ("zero", "one", "projection"),
            (
                BlifGate("zero", (), (0,)),
                BlifGate("one", (), (1,)),
                BlifGate("projection", ("a", "zero"), (0, 0, 1, 1)),
            ),
        )
        circuit = blif_to_occam(network)
        self.assertEqual(1, len(circuit.gates))
        self.assertEqual(("w1", "~w1", "x1"), circuit.outputs)
        self.assertTrue(verify_equivalent(circuit, network)["equivalent"])

    def test_complete_truth_table_round_trip(self) -> None:
        circuit = OccamCircuit(
            4,
            (
                OccamGate("w1", "XOR", "x1", "~x2"),
                OccamGate("w2", "NAND", "x3", "x4"),
                OccamGate("w3", "OR", "~w1", "w2"),
                OccamGate("w4", "XNOR", "w1", "~w3"),
            ),
            ("w1", "~w2", "w3", "~w4"),
        )
        rebuilt = self.assert_bridge_equivalent(circuit, 4)
        for assignment in range(16):
            bits = f"{assignment:04b}"
            self.assertEqual(circuit.evaluate(bits), rebuilt.evaluate(bits))


if __name__ == "__main__":
    unittest.main()
