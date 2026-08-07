import cmath
import importlib
import unittest


def matmul(left, right):
    return [
        [sum(left[row][inner] * right[inner][column] for inner in range(len(right))) for column in range(len(right[0]))]
        for row in range(len(left))
    ]


def dagger(matrix):
    return [
        [complex(matrix[column][row]).conjugate() for column in range(len(matrix))]
        for row in range(len(matrix[0]))
    ]


class LocalUnitaryInvarianceTests(unittest.TestCase):
    def test_channel_weights_are_invariant_under_local_unitary_rotations(self):
        try:
            module = importlib.import_module("src.channel_decomposition")
        except ModuleNotFoundError:
            self.fail("src.channel_decomposition has not been implemented")

        operator = [
            [3.0, 0.4, 0.2, 0.1j],
            [0.4, 1.0, -0.3j, 0.0],
            [0.2, 0.3j, 2.0, -0.5],
            [-0.1j, 0.0, -0.5, 4.0],
        ]
        phase = cmath.exp(0.37j)
        root_two = 2.0**0.5
        local_u = [
            [1.0 / root_two, phase / root_two],
            [-phase.conjugate() / root_two, 1.0 / root_two],
        ]
        unitary = [
            [local_u[0][0], local_u[0][1], 0.0, 0.0],
            [local_u[1][0], local_u[1][1], 0.0, 0.0],
            [0.0, 0.0, local_u[0][0], local_u[0][1]],
            [0.0, 0.0, local_u[1][0], local_u[1][1]],
        ]
        rotated = matmul(dagger(unitary), matmul(operator, unitary))
        blocks = [[0, 1], [2, 3]]

        before = module.channel_weights(module.decompose_operator(operator, blocks))
        after = module.channel_weights(module.decompose_operator(rotated, blocks))

        for channel in ("global_charge", "site_charge", "internal", "nonlocal"):
            self.assertAlmostEqual(before[channel], after[channel], places=12)


if __name__ == "__main__":
    unittest.main()
