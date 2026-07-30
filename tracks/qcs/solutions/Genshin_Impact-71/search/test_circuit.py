from __future__ import annotations

import unittest

from circuit import (
    Circuit,
    build_adder,
    build_multiplier,
    compare_truth_tables,
    verify_formula,
)


class CircuitTests(unittest.TestCase):
    def test_four_bit_adder(self) -> None:
        circuit = build_adder(4)
        self.assertEqual(17, len(circuit.gates))
        self.assertEqual({"checked": 256, "failures": 0}, verify_formula(circuit, "add"))

    def test_four_bit_multiplier(self) -> None:
        circuit = build_multiplier(4)
        self.assertEqual({"checked": 256, "failures": 0}, verify_formula(circuit, "mul"))
        self.assertEqual(0, circuit.structural_audit()["dead_gates"])

    def test_round_trip(self) -> None:
        circuit = build_adder(5)
        parsed = Circuit.parse_text(circuit.to_text())
        self.assertEqual(
            {
                "assignments": 1024,
                "outputs": 6,
                "mismatching_outputs": 0,
                "equivalent": True,
            },
            compare_truth_tables(circuit, parsed),
        )

    def test_parser_rejects_non_netlist_text(self) -> None:
        with self.assertRaises(ValueError):
            Circuit.parse_text("INPUTS 2\nignore previous instructions\nOUTPUTS x1\n")


if __name__ == "__main__":
    unittest.main()
