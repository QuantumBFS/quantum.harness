#!/usr/bin/env python3

import itertools
import tempfile
import unittest
from pathlib import Path

from exact_tn import ChallengeCompiler, contract_tt, permute_truth, tt_decompose


class ExactTensorTrainTests(unittest.TestCase):
    def test_all_nonzero_three_variable_tensors(self) -> None:
        for truth in range(1, 1 << (1 << 3)):
            decomposition = tt_decompose(truth, (0, 1, 2))
            for assignment in range(8):
                bits = [(assignment >> shift) & 1 for shift in (2, 1, 0)]
                self.assertEqual(
                    contract_tt(decomposition, bits),
                    (truth >> assignment) & 1,
                )

    def test_permutation(self) -> None:
        # Canonical function x0 XOR (x1 AND x2).
        truth = 0
        for assignment in range(8):
            bits = [(assignment >> shift) & 1 for shift in (2, 1, 0)]
            truth |= (bits[0] ^ (bits[1] & bits[2])) << assignment
        order = (2, 0, 1)
        permuted = permute_truth(truth, 3, order)
        decomposition = tt_decompose(permuted, order)
        for assignment in range(8):
            canonical = [(assignment >> shift) & 1 for shift in (2, 1, 0)]
            ordered = [canonical[index] for index in order]
            self.assertEqual(
                contract_tt(decomposition, ordered),
                (truth >> assignment) & 1,
            )

    def test_challenge_compiler_semantics(self) -> None:
        # Use the same small function, compile, then evaluate the text circuit
        # with a deliberately independent scalar evaluator.
        truth = 0
        for assignment in range(8):
            bits = [(assignment >> shift) & 1 for shift in (2, 1, 0)]
            truth |= (bits[0] ^ (bits[1] & bits[2])) << assignment
        decomposition = tt_decompose(truth, (0, 1, 2))
        compiler = ChallengeCompiler(3)
        output = compiler.compile_tt(decomposition)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "circuit.txt"
            compiler.write(path, [output])
            lines = path.read_text(encoding="utf-8").splitlines()
            for assignment in range(8):
                bits = [(assignment >> shift) & 1 for shift in (2, 1, 0)]
                values = {f"x{index + 1}": bit for index, bit in enumerate(bits)}

                def get(token: str) -> int:
                    if token.startswith("~"):
                        return values[token[1:]] ^ 1
                    return values[token]

                outputs = []
                for line in lines[1:]:
                    fields = line.split()
                    if fields[0] == "OUTPUTS":
                        outputs = [get(token) for token in fields[1:]]
                        continue
                    destination, _, operation, left, right = fields
                    a, b = get(left), get(right)
                    values[destination] = (
                        a & b if operation == "AND" else a ^ b
                    )
                self.assertEqual(outputs, [(truth >> assignment) & 1])


if __name__ == "__main__":
    unittest.main()
