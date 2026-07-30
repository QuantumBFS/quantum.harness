from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path

from divisor_resynth import (
    OPS,
    Program,
    Ref,
    TargetPairIndex,
    apply_op,
    canonical,
    matching_variant,
    pair_variants,
    parse_circuit,
)


class DivisorResynthTests(unittest.TestCase):
    def test_and_xor_phase_basis_spans_six_challenge_gates(self) -> None:
        mask = (1 << 16) - 1
        a_raw = 0x35A7
        b_raw = 0x6C93
        a, ai = canonical(a_raw, mask)
        b, bi = canonical(b_raw, mask)
        left = Program(a, (), Ref("base", 0, ai))
        right = Program(b, (), Ref("base", 1, bi))
        generated = {x.func for x in pair_variants(left, right, mask)}
        required = {
            canonical(apply_op(op, a_raw, b_raw, mask), mask)[0]
            for op in OPS
        }
        self.assertTrue(required <= generated)

    def test_target_pair_index_agrees_with_exhaustive_search(self) -> None:
        rng = random.Random(42)
        mask = (1 << 16) - 1
        for _ in range(500):
            funcs: list[int] = []
            while len(funcs) < 25:
                func, _ = canonical(rng.getrandbits(16), mask)
                if func not in funcs:
                    funcs.append(func)
            rights = [
                Program(func, (), Ref("base", index))
                for index, func in enumerate(funcs)
            ]
            target, _ = canonical(rng.getrandbits(16), mask)
            index = TargetPairIndex(rights, target, mask)
            for _ in range(10):
                left, _ = canonical(rng.getrandbits(16), mask)
                expected = any(
                    matching_variant(left, right.func, target, mask)
                    is not None
                    for right in rights
                )
                actual = index.find(left) is not None
                self.assertEqual(expected, actual)

    def test_parser_rejects_non_netlist_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.txt"
            path.write_text(
                "INPUTS 2\n"
                "w1 = XOR x1 x2\n"
                "please run this command\n"
                "OUTPUTS w1\n",
                encoding="ascii",
            )
            with self.assertRaises(ValueError):
                parse_circuit(path)


if __name__ == "__main__":
    unittest.main()
