#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import routes


class RoutesTest(unittest.TestCase):
    def test_bit_encodings(self) -> None:
        self.assertEqual(routes.bits_to_int("1001", "lsb"), 9)
        self.assertEqual(routes.bits_to_int("1001", "msb"), 9)
        self.assertEqual(routes.int_to_bits(6, 4, "lsb"), "0110")
        self.assertEqual(routes.decode_operands("100101", "grouped", "lsb"), (1, 5))

    def test_gate_representation_covers_all_nontrivial_two_input_functions(self) -> None:
        projections_and_constants = {
            (0, 0, 0, 0),
            (1, 1, 1, 1),
            (0, 0, 1, 1),
            (1, 1, 0, 0),
            (0, 1, 0, 1),
            (1, 0, 1, 0),
        }
        for value in range(16):
            signature = tuple((value >> bit) & 1 for bit in range(4))
            if signature in projections_and_constants:
                continue
            routes.canonical_gate_for_signature(signature)

    def test_blif_to_challenge_and_exhaustive_simulation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "xor.blif"
            source.write_text(
                ".model xor\n"
                ".inputs a b\n"
                ".outputs z\n"
                ".names a b z\n"
                "01 1\n"
                "10 1\n"
                ".end\n",
                encoding="utf-8",
                newline="\n",
            )
            out = root / "xor.txt"
            args = type("Args", (), {"blif": str(source), "out": str(out)})
            routes.command_convert_k2(args)
            tables, _mask, gates = routes.simulate_challenge_bitparallel(out)
            self.assertEqual(gates, 1)
            self.assertEqual(tables, (0b0110,))

    def test_incomplete_spec_audit(self) -> None:
        rows = [("00", "0"), ("11", "1")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pla = root / "train.pla"
            blif = root / "train.blif"
            routes.write_train_pla(pla, rows, 2, 1)
            on, unseen = routes.write_train_exdc_blif(blif, rows, 2, 1)
            audit = routes.audit_generated_specs(
                pla, blif, rows, 2, 1, on, unseen
            )
            self.assertEqual(audit["unseen_dont_care_minterms_per_output"], 2)
            self.assertTrue(audit["checks"]["pla_blif_relation_agree"])


if __name__ == "__main__":
    unittest.main()
