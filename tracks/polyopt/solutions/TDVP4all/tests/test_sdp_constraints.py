from fractions import Fraction
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.algebra import (  # noqa: E402
    GaussianRational,
    PauliPolynomial,
    PauliWord,
    add_polynomials,
    expand_word,
    scale_polynomial,
)
from challenge233.sdp.basis import close_word_basis  # noqa: E402
from challenge233.sdp.artifact import export_constraint_map  # noqa: E402
from challenge233.sdp.constraints import (  # noqa: E402
    ConstraintMap,
    blockade_polynomial,
    build_constraint_map,
    expand_moment_entry_orbits,
    expand_zero_localizer_orbits,
    pxp_hamiltonian_polynomial,
)
from challenge233.sdp.symmetry import (  # noqa: E402
    DihedralElement,
    act_on_polynomial,
    dihedral_elements,
)


def periodic_blockade_states(size):
    return tuple(
        state
        for state in range(1 << size)
        if all(
            not (
                (state >> site) & 1
                and (state >> ((site + 1) % size)) & 1
            )
            for site in range(size)
        )
    )


def apply_word_to_state(word, state):
    target = state
    amplitude = 1 + 0j
    for site, label in word.factors:
        bit = (target >> site) & 1
        if label == "X":
            target ^= 1 << site
        elif label == "Y":
            amplitude *= 1j if bit else -1j
            target ^= 1 << site
        elif label == "Z":
            amplitude *= 1 if bit else -1
        else:
            raise AssertionError(
                f"unexpected canonical label: {label}"
            )
    return target, amplitude


def polynomial_matrix_elements(polynomial, legal_states):
    legal = set(legal_states)
    elements = {}
    for column_state in legal_states:
        for word, coefficient in polynomial.terms:
            row_state, amplitude = apply_word_to_state(
                word,
                column_state,
            )
            if row_state in legal:
                scalar = complex(
                    float(coefficient.real),
                    float(coefficient.imag),
                )
                key = (row_state, column_state)
                elements[key] = (
                    elements.get(key, 0j)
                    + scalar * amplitude
                )
    return {
        key: value
        for key, value in elements.items()
        if abs(value) > 1e-14
    }


class BlockadeConstraintTests(unittest.TestCase):
    def test_blockade_polynomial_is_exact_projector_product(self):
        quarter = GaussianRational(Fraction(1, 4), Fraction(0))
        expected = PauliPolynomial.from_terms(
            (
                (PauliWord(), quarter),
                (PauliWord(((0, "Z"),)), quarter),
                (PauliWord(((1, "Z"),)), quarter),
                (
                    PauliWord(((0, "Z"), (1, "Z"))),
                    quarter,
                ),
            )
        )
        self.assertEqual(blockade_polynomial(0, size=4), expected)

    def test_moment_entries_preserve_the_same_site_xz_phase(self):
        basis = close_word_basis(
            (
                PauliWord(((0, "X"),)),
                PauliWord(((0, "Z"),)),
            ),
            size=4,
        )
        constraint_map = build_constraint_map(
            size=4,
            moment_basis=basis,
            localizer_basis=(PauliWord(),),
        )
        row = basis.index(PauliWord(((0, "X"),)))
        column = basis.index(PauliWord(((0, "Z"),)))
        entry = constraint_map.moment_entries[
            row * len(basis) + column
        ]
        self.assertEqual(entry.row, row)
        self.assertEqual(entry.column, column)
        self.assertEqual(
            entry.polynomial,
            PauliPolynomial(
                (
                    (
                        PauliWord(((0, "Y"),)),
                        GaussianRational(
                            Fraction(0),
                            Fraction(-1),
                        ),
                    ),
                )
            ),
        )

    def test_every_site_and_localizer_entry_is_present(self):
        moment_basis = close_word_basis(
            (PauliWord(), PauliWord(((0, "X"),))),
            size=4,
        )
        localizer_basis = close_word_basis(
            (PauliWord(), PauliWord(((0, "Z"),))),
            size=4,
        )
        constraint_map = build_constraint_map(
            size=4,
            moment_basis=moment_basis,
            localizer_basis=localizer_basis,
        )
        self.assertEqual(
            len(constraint_map.moment_entries),
            len(moment_basis) ** 2,
        )
        self.assertEqual(
            {
                (entry.row, entry.column)
                for entry in constraint_map.moment_entries
            },
            {
                (row, column)
                for row in range(len(moment_basis))
                for column in range(len(moment_basis))
            },
        )
        self.assertEqual(
            len(constraint_map.zero_localizers),
            4 * len(localizer_basis) ** 2,
        )
        self.assertEqual(
            {
                (entry.site, entry.row, entry.column)
                for entry in constraint_map.zero_localizers
            },
            {
                (site, row, column)
                for site in range(4)
                for row in range(len(localizer_basis))
                for column in range(len(localizer_basis))
            },
        )
        identity_index = localizer_basis.index(PauliWord())
        identity_row = next(
            row
            for row in constraint_map.zero_localizers
            if (
                row.site,
                row.row,
                row.column,
            )
            == (3, identity_index, identity_index)
        )
        self.assertEqual(
            identity_row.polynomial,
            blockade_polynomial(3, size=4),
        )
        self.assertEqual(
            sum(
                item.irrep.dimension * item.multiplicity
                for item in constraint_map.moment_sector_multiplicities
            ),
            len(moment_basis),
        )
        self.assertEqual(
            sum(
                item.irrep.dimension * item.multiplicity
                for item in constraint_map.localizer_sector_multiplicities
            ),
            len(localizer_basis),
        )
        self.assertEqual(
            tuple(
                item.irrep
                for item in (
                    constraint_map.moment_sector_multiplicities
                )
            ),
            constraint_map.irrep_catalog,
        )
        self.assertEqual(
            tuple(
                item.irrep
                for item in (
                    constraint_map.localizer_sector_multiplicities
                )
            ),
            constraint_map.irrep_catalog,
        )

    def test_constraint_map_contains_all_dihedral_actions(self):
        moment_basis = close_word_basis(
            (PauliWord(), PauliWord(((0, "X"),))),
            size=5,
        )
        constraint_map = build_constraint_map(
            size=5,
            moment_basis=moment_basis,
            localizer_basis=(PauliWord(),),
        )
        self.assertEqual(len(constraint_map.group_elements), 10)
        self.assertEqual(
            len(constraint_map.moment_basis_permutations),
            10,
        )
        self.assertEqual(
            len(constraint_map.localizer_basis_permutations),
            10,
        )
        self.assertEqual(
            len(constraint_map.moment_entry_permutations),
            10,
        )
        self.assertEqual(
            len(constraint_map.zero_localizer_permutations),
            10,
        )
        for permutation in (
            *constraint_map.moment_basis_permutations,
            *constraint_map.localizer_basis_permutations,
            *constraint_map.moment_entry_permutations,
            *constraint_map.zero_localizer_permutations,
        ):
            self.assertEqual(
                sorted(permutation),
                list(range(len(permutation))),
            )

        reflection_index = constraint_map.group_elements.index(
            DihedralElement(0, True)
        )
        translation_index = constraint_map.group_elements.index(
            DihedralElement(1, False)
        )
        self.assertEqual(
            constraint_map.zero_localizer_permutations[
                reflection_index
            ][0],
            4,
        )
        self.assertEqual(
            constraint_map.zero_localizer_permutations[
                translation_index
            ][0],
            1,
        )
        destination = constraint_map.zero_localizer_permutations[
            reflection_index
        ][0]
        self.assertEqual(
            act_on_polynomial(
                DihedralElement(0, True),
                constraint_map.zero_localizers[0].polynomial,
                size=5,
            ),
            constraint_map.zero_localizers[destination].polynomial,
        )

    def test_builder_rejects_nonclosed_or_out_of_range_bases(self):
        identity = PauliWord()
        with self.assertRaisesRegex(ValueError, "moment basis.*D_N"):
            build_constraint_map(
                size=4,
                moment_basis=(
                    identity,
                    PauliWord(((0, "X"),)),
                ),
                localizer_basis=(identity,),
            )
        closed = close_word_basis(
            (identity, PauliWord(((0, "X"),))),
            size=4,
        )
        with self.assertRaisesRegex(ValueError, "localizer basis.*D_N"):
            build_constraint_map(
                size=4,
                moment_basis=closed,
                localizer_basis=(
                    identity,
                    PauliWord(((0, "X"),)),
                ),
            )
        with self.assertRaisesRegex(ValueError, "site.*range"):
            build_constraint_map(
                size=4,
                moment_basis=(
                    identity,
                    PauliWord(((4, "X"),)),
                ),
                localizer_basis=(identity,),
            )
        with self.assertRaisesRegex(ValueError, "site.*range"):
            build_constraint_map(
                size=4,
                moment_basis=(identity,),
                localizer_basis=(PauliWord(((4, "Z"),)),),
            )
        with self.assertRaisesRegex(ValueError, "size.*4"):
            build_constraint_map(
                size=3,
                moment_basis=(identity,),
                localizer_basis=(identity,),
            )

    def test_structural_map_does_not_impose_state_invariance(self):
        self.assertNotIn(
            "moment_invariance_equalities",
            ConstraintMap.__dataclass_fields__,
        )

    def test_legacy_artifact_is_explicitly_not_solver_input(self):
        constraint_map = build_constraint_map(
            size=4,
            moment_basis=(PauliWord(),),
            localizer_basis=(PauliWord(),),
        )
        with TemporaryDirectory() as directory:
            export_constraint_map(constraint_map, directory)
            manifest = json.loads(
                (Path(directory) / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            manifest["purpose"],
            "legacy-structural-arbitrary-sandwich-not-solver-input",
        )
        self.assertEqual(
            manifest["localizer_semantics"],
            "unsound-for-state-support",
        )

    def test_package_exports_constraint_boundary(self):
        from challenge233.sdp import (
            blockade_polynomial as exported_blockade,
            build_constraint_map as exported_build,
        )

        constraint_map = exported_build(
            size=4,
            moment_basis=(PauliWord(),),
            localizer_basis=(PauliWord(),),
        )
        self.assertEqual(
            constraint_map.zero_localizers[0].polynomial,
            exported_blockade(0, size=4),
        )


class EquivarianceRoundTripTests(unittest.TestCase):
    def test_equivariance_orbits_expand_to_dense_tables(self):
        for size in (4, 5):
            with self.subTest(size=size):
                basis = close_word_basis(
                    (
                        PauliWord(),
                        PauliWord(((0, "X"),)),
                        PauliWord(((0, "Z"),)),
                    ),
                    size=size,
                )
                constraint_map = build_constraint_map(
                    size=size,
                    moment_basis=basis,
                    localizer_basis=basis,
                )
                self.assertEqual(
                    expand_moment_entry_orbits(constraint_map),
                    constraint_map.moment_entries,
                )
                self.assertEqual(
                    expand_zero_localizer_orbits(constraint_map),
                    constraint_map.zero_localizers,
                )
                self.assertEqual(
                    constraint_map.assembly_statistics,
                    {
                        "moment_basis_size": len(basis),
                        "moment_entry_count": len(basis) ** 2,
                        "localizer_basis_size": len(basis),
                        "zero_localizer_count": (
                            size * len(basis) ** 2
                        ),
                        "group_order": 2 * size,
                        "dense_complex_matrix_bytes": (
                            16 * len(basis) ** 2
                            + 16 * size * len(basis) ** 2
                        ),
                    },
                )
                self._assert_orbit_partition(
                    constraint_map.moment_entry_orbits,
                    constraint_map.moment_entry_permutations,
                    len(constraint_map.moment_entries),
                )
                self._assert_orbit_partition(
                    constraint_map.zero_localizer_orbits,
                    constraint_map.zero_localizer_permutations,
                    len(constraint_map.zero_localizers),
                )

    def _assert_orbit_partition(
        self,
        orbits,
        permutations,
        table_size,
    ):
        flattened = []
        for orbit in orbits:
            self.assertEqual(
                orbit.representative,
                min(orbit.members),
            )
            self.assertEqual(
                tuple(sorted(orbit.members)),
                orbit.members,
            )
            self.assertEqual(
                set(orbit.members),
                {
                    permutation[orbit.representative]
                    for permutation in permutations
                },
            )
            flattened.extend(orbit.members)
        self.assertEqual(
            sorted(flattened),
            list(range(table_size)),
        )


class HamiltonianPolynomialTests(unittest.TestCase):
    def test_hamiltonian_uses_authoritative_projector_expansion(self):
        hamiltonian = pxp_hamiltonian_polynomial(
            size=4,
            detuning=Fraction(3, 10),
        )
        expected_terms = []
        for site in range(4):
            expected_terms.append(
                expand_word(
                    (
                        ((site - 1) % 4, "P"),
                        (site, "X"),
                        ((site + 1) % 4, "P"),
                    )
                )
            )
            expected_terms.append(
                scale_polynomial(
                    GaussianRational(
                        Fraction(-3, 10),
                        Fraction(0),
                    ),
                    expand_word(((site, "n"),)),
                )
            )
        self.assertEqual(
            hamiltonian,
            add_polynomials(*expected_terms),
        )

    def test_hamiltonian_requires_declared_size_and_exact_detuning(self):
        with self.assertRaisesRegex(ValueError, "size.*4"):
            pxp_hamiltonian_polynomial(
                size=3,
                detuning=Fraction(0),
            )
        with self.assertRaisesRegex(TypeError, "Fraction"):
            pxp_hamiltonian_polynomial(
                size=4,
                detuning=0.3,
            )

    def test_polynomial_matches_independent_blockaded_matrix(self):
        size = 4
        detuning = Fraction(3, 10)
        legal_states = periodic_blockade_states(size)
        actual = polynomial_matrix_elements(
            pxp_hamiltonian_polynomial(size, detuning),
            legal_states,
        )
        expected = {}
        legal = set(legal_states)
        for state in legal_states:
            diagonal = (
                -float(detuning)
                * bin(state).count("1")
            )
            if diagonal:
                expected[(state, state)] = complex(diagonal)
            for site in range(size):
                target = state ^ (1 << site)
                if target in legal:
                    key = (target, state)
                    expected[key] = expected.get(key, 0j) + 1.0

        self.assertEqual(set(actual), set(expected))
        for key, expected_value in expected.items():
            with self.subTest(matrix_element=key):
                self.assertAlmostEqual(
                    abs(actual[key] - expected_value),
                    0.0,
                    delta=1e-14,
                )

    def test_uniform_hamiltonian_is_dihedral_invariant(self):
        size = 5
        hamiltonian = pxp_hamiltonian_polynomial(
            size=size,
            detuning=Fraction(2, 5),
        )
        for element in dihedral_elements(size):
            self.assertEqual(
                act_on_polynomial(element, hamiltonian, size),
                hamiltonian,
            )

    def test_blockade_polynomials_form_a_dihedral_orbit(self):
        size = 5
        blockade_family = {
            blockade_polynomial(site, size)
            for site in range(size)
        }
        for element in dihedral_elements(size):
            self.assertEqual(
                {
                    act_on_polynomial(
                        element,
                        polynomial,
                        size,
                    )
                    for polynomial in blockade_family
                },
                blockade_family,
            )

    def test_package_exports_hamiltonian_boundary(self):
        from challenge233.sdp import (
            pxp_hamiltonian_polynomial as exported_hamiltonian,
        )

        self.assertEqual(
            exported_hamiltonian(4, Fraction(0)),
            pxp_hamiltonian_polynomial(4, Fraction(0)),
        )


if __name__ == "__main__":
    unittest.main()
