from fractions import Fraction
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.algebra import (  # noqa: E402
    GaussianRational,
    PauliWord,
)
from challenge233.sdp.kyfan import (  # noqa: E402
    ComplexLinearForm,
    MomentVariable,
    RationalLinearForm,
    build_global_kyfan_problem,
    build_clique_images,
    build_local_kyfan_problem,
    build_magnitude_witnesses,
    realify_hermitian_matrix,
)
from challenge233.sdp.hierarchy import (  # noqa: E402
    LOCAL_LEVELS,
    clique_orbit,
    local_pauli_basis,
)


def evaluate_form(form, values):
    return form.constant + sum(
        coefficient * values[variable]
        for variable, coefficient in form.terms
    )


def diagonal_word_element(word, state):
    value = Fraction(1)
    for site, label in word.factors:
        bit = (state >> site) & 1
        if label in {"X", "Y"}:
            return Fraction(0)
        if label == "Z":
            value *= 1 if bit else -1
    return value


def group_averaged_values(problem, states):
    values = {}
    for variable in problem.variables:
        orbit_average = sum(
            (
                sum(
                    diagonal_word_element(word, state)
                    for word in variable.orbit
                )
                / len(variable.orbit)
            )
            for state in states
        )
        values[variable.index] = orbit_average
    return values


def evaluate_complex_form(form, values):
    return GaussianRational(
        evaluate_form(form.real, values),
        evaluate_form(form.imag, values),
    )


def complex_quadratic_form(matrix, vector):
    value = GaussianRational()
    for row in range(len(vector)):
        for column in range(len(vector)):
            coefficient = GaussianRational(
                vector[row] * vector[column],
                Fraction(0),
            )
            value = (
                value
                + coefficient * matrix[row][column]
            )
    return value


class KyFanGlobalAssemblyTests(unittest.TestCase):
    def test_n4_global_blocks_have_exact_realified_sizes(self):
        expected = {2: 134, 3: 350, 4: 512}
        for degree, dimension in expected.items():
            with self.subTest(degree=degree):
                problem = build_global_kyfan_problem(
                    4,
                    Fraction(1, 2),
                    degree,
                )
                self.assertEqual(
                    [block.dimension for block in problem.psd_blocks],
                    [dimension, dimension],
                )
                self.assertEqual(
                    {
                        block.identifier
                        for block in problem.psd_blocks
                    },
                    {"gamma", "blockade-complement"},
                )
                self.assertEqual(
                    problem.statistics["bounded_variable_count"],
                    problem.statistics["moment_variable_count"],
                )

    def test_problem_contains_trace_and_every_localizer_kind(self):
        problem = build_global_kyfan_problem(
            4,
            Fraction(1, 2),
            2,
        )
        self.assertIn(
            "trace-gamma-equals-2",
            {row.identifier for row in problem.equalities},
        )
        kinds = {
            row.provenance["localizer_kind"]
            for row in problem.equalities
            if "localizer_kind" in row.provenance
        }
        self.assertEqual(
            kinds,
            {"left-support", "right-support", "safe-sandwich"},
        )

    def test_exact_realification_matches_literal_matrix(self):
        one = RationalLinearForm(Fraction(1))
        two = RationalLinearForm(Fraction(2))
        zero = RationalLinearForm()
        matrix = (
            (
                ComplexLinearForm(one, zero),
                ComplexLinearForm(zero, one),
            ),
            (
                ComplexLinearForm(zero, RationalLinearForm(Fraction(-1))),
                ComplexLinearForm(two, zero),
            ),
        )
        realified = realify_hermitian_matrix(matrix)
        self.assertEqual(
            [
                [entry.constant for entry in row]
                for row in realified
            ],
            [
                [1, 0, 0, -1],
                [0, 2, 1, 0],
                [0, 1, 1, 0],
                [-1, 0, 0, 2],
            ],
        )

    def test_every_variable_has_a_psd_magnitude_witness(self):
        problem = build_global_kyfan_problem(
            4,
            Fraction(1, 2),
            2,
        )
        gamma = next(
            block
            for block in problem.psd_blocks
            if block.identifier == "gamma"
        )
        extra = MomentVariable(
            index=max(variable.index for variable in problem.variables) + 1,
            representative=PauliWord(((0, "X"),)),
            orbit=(PauliWord(((0, "X"),)),),
        )
        with self.assertRaisesRegex(
            ValueError,
            "moment variable has no PSD magnitude witness",
        ):
            build_magnitude_witnesses(
                (*problem.variables, extra),
                gamma,
            )

    def test_physical_n4_effects_remain_feasible(self):
        problem = build_global_kyfan_problem(
            4,
            Fraction(1, 2),
            2,
        )
        legal_states = (0, 1, 2, 4, 5, 8, 10)
        effects = tuple(
            (state, legal_states[(index + 1) % len(legal_states)])
            for index, state in enumerate(legal_states)
        ) + (
            (legal_states[1], legal_states[4]),
        )
        for states in effects:
            values = group_averaged_values(problem, states)
            for equality in problem.equalities:
                with self.subTest(states=states, row=equality.identifier):
                    self.assertEqual(
                        evaluate_form(equality.form, values),
                        0,
                    )
            for block in problem.unrealified_psd_blocks:
                matrix = tuple(
                    tuple(
                        evaluate_complex_form(entry, values)
                        for entry in row
                    )
                    for row in block.entries
                )
                dimension = block.dimension
                vectors = (
                    (Fraction(1),)
                    + (Fraction(0),) * (dimension - 1),
                    tuple(
                        Fraction(1 if index % 2 == 0 else -1)
                        for index in range(dimension)
                    ),
                    tuple(Fraction(1) for _ in range(dimension)),
                )
                for vector in vectors:
                    with self.subTest(
                        states=states,
                        block=block.identifier,
                        vector=vector[:4],
                    ):
                        value = complex_quadratic_form(
                            matrix,
                            vector,
                        )
                        self.assertEqual(value.imag, 0)
                        self.assertGreaterEqual(
                            value.real,
                            0,
                        )

    def test_no_localizer_ablation_changes_only_localizer_rows(self):
        sound = build_global_kyfan_problem(
            4,
            Fraction(1, 2),
            2,
            localizer_mode="sound",
        )
        ablation = build_global_kyfan_problem(
            4,
            Fraction(1, 2),
            2,
            localizer_mode="none",
        )
        self.assertEqual(sound.variables, ablation.variables)
        self.assertEqual(sound.objective, ablation.objective)
        self.assertEqual(sound.psd_blocks, ablation.psd_blocks)
        self.assertEqual(
            sound.magnitude_witnesses,
            ablation.magnitude_witnesses,
        )
        self.assertFalse(
            any(
                "localizer_kind" in row.provenance
                for row in ablation.equalities
            )
        )
        with self.assertRaisesRegex(ValueError, "localizer_mode"):
            build_global_kyfan_problem(
                4,
                Fraction(1, 2),
                2,
                localizer_mode="arbitrary-pauli",
            )

    def test_legacy_constraint_map_cannot_enter_kyfan_builder(self):
        source = (
            ROOT / "src/challenge233/sdp/kyfan.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("ConstraintMap", source)
        with self.assertRaises(TypeError):
            build_global_kyfan_problem(
                4,
                Fraction(1, 2),
                2,
                constraint_map=object(),
            )

    def test_package_exports_kyfan_boundary(self):
        from challenge233.sdp import (
            build_global_kyfan_problem as exported_builder,
        )

        self.assertIs(exported_builder, build_global_kyfan_problem)


class KyFanLocalAssemblyTests(unittest.TestCase):
    def test_n20_local_blocks_do_not_expand_with_global_hilbert_space(self):
        expected = {
            "L0": 74,
            "L1": 134,
            "L2": 350,
            "L3": 752,
        }
        for level in LOCAL_LEVELS:
            with self.subTest(level=level.name):
                problem = build_local_kyfan_problem(
                    20,
                    Fraction(1, 2),
                    level,
                )
                self.assertEqual(
                    max(
                        block.dimension
                        for block in problem.psd_blocks
                    ),
                    expected[level.name],
                )
                self.assertLess(
                    problem.statistics[
                        "largest_real_psd_dimension"
                    ],
                    1000,
                )
                self.assertEqual(
                    problem.statistics["bounded_variable_count"],
                    problem.statistics["moment_variable_count"],
                )
                self.assertEqual(
                    problem.clique_images,
                    build_clique_images(20, 0, level),
                )

    def test_every_size_and_level_exports_complete_dihedral_images(self):
        for size in range(4, 21):
            for level in LOCAL_LEVELS:
                with self.subTest(size=size, level=level.name):
                    images = build_clique_images(size, 0, level)
                    basis_size = len(
                        local_pauli_basis(size, 0, level)
                    )
                    self.assertEqual(len(images), 2 * size)
                    self.assertEqual(
                        {
                            (image.shift, image.reflected)
                            for image in images
                        },
                        {
                            (shift, reflected)
                            for reflected in (False, True)
                            for shift in range(size)
                        },
                    )
                    self.assertEqual(
                        {image.sites for image in images},
                        set(
                            clique_orbit(
                                size,
                                0,
                                level.range_sites,
                            )
                        ),
                    )
                    for image in images:
                        self.assertEqual(
                            sorted(image.row_permutation),
                            list(range(basis_size)),
                        )
                    self.assertEqual(
                        {
                            site
                            for image in images
                            for site in image.localizer_sites
                        },
                        set(range(size)),
                    )


if __name__ == "__main__":
    unittest.main()
