from fractions import Fraction
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.algebra import (  # noqa: E402
    GaussianRational,
    PauliPolynomial,
    PauliWord,
)
from challenge233.sdp.basis import close_word_basis  # noqa: E402
from challenge233.sdp.symmetry import (  # noqa: E402
    DihedralElement,
    act_on_polynomial,
    act_on_site,
    act_on_word,
    compose,
    dihedral_irrep_catalog,
    dihedral_elements,
    normalize,
    representation_permutation,
    sector_multiplicities,
    translation_orbits,
    word_orbit,
)


class DihedralActionTests(unittest.TestCase):
    def test_group_has_exactly_two_n_normalized_elements(self):
        for size in (5, 6):
            elements = dihedral_elements(size)
            self.assertEqual(len(elements), 2 * size)
            self.assertEqual(len(set(elements)), 2 * size)
            self.assertEqual(
                {element.shift for element in elements},
                set(range(size)),
            )

    def test_tn_r2_and_rtr_relations_hold(self):
        for size in (5, 6):
            with self.subTest(size=size):
                identity = DihedralElement(0, False)
                translation = DihedralElement(1, False)
                reflection = DihedralElement(0, True)

                power = identity
                for _ in range(size):
                    power = compose(translation, power, size)
                self.assertEqual(power, identity)
                self.assertEqual(
                    compose(reflection, reflection, size),
                    identity,
                )
                self.assertEqual(
                    compose(
                        reflection,
                        compose(
                            translation,
                            reflection,
                            size,
                        ),
                        size,
                    ),
                    DihedralElement(size - 1, False),
                )

    def test_composition_matches_successive_action_on_every_site(self):
        size = 5
        elements = (
            DihedralElement(1, False),
            DihedralElement(0, True),
            DihedralElement(2, True),
        )
        self.assertEqual(
            act_on_site(DihedralElement(1, False), 0, size),
            1,
        )
        self.assertEqual(
            act_on_site(DihedralElement(0, True), 1, size),
            4,
        )
        for left in elements:
            for right in elements:
                product = compose(left, right, size)
                for site in range(size):
                    with self.subTest(
                        left=left,
                        right=right,
                        site=site,
                    ):
                        self.assertEqual(
                            act_on_site(product, site, size),
                            act_on_site(
                                left,
                                act_on_site(right, site, size),
                                size,
                            ),
                        )

    def test_reflection_relabels_sites_without_identifying_them(self):
        word = PauliWord(((1, "X"), (3, "Z")))
        reflected = act_on_word(
            DihedralElement(0, True),
            word,
            size=5,
        )
        self.assertEqual(
            reflected,
            PauliWord(((2, "Z"), (4, "X"))),
        )
        self.assertNotEqual(reflected, word)

    def test_reflection_reverses_nearest_neighbor_orientation(self):
        nearest_neighbor = PauliWord(((0, "Z"), (1, "Z")))
        self.assertEqual(
            act_on_word(
                DihedralElement(0, True),
                nearest_neighbor,
                size=5,
            ),
            PauliWord(((0, "Z"), (4, "Z"))),
        )

    def test_polynomial_action_relabels_words_and_preserves_coefficients(self):
        half = GaussianRational(Fraction(1, 2), Fraction(0))
        neg_i = GaussianRational(Fraction(0), Fraction(-1))
        polynomial = PauliPolynomial(
            (
                (PauliWord(((0, "X"),)), half),
                (PauliWord(((1, "Z"),)), neg_i),
            )
        )
        self.assertEqual(
            act_on_polynomial(
                DihedralElement(2, True),
                polynomial,
                size=5,
            ),
            PauliPolynomial(
                (
                    (PauliWord(((2, "X"),)), half),
                    (PauliWord(((1, "Z"),)), neg_i),
                )
            ),
        )

    def test_single_site_word_orbit_contains_every_translate(self):
        orbit = word_orbit(PauliWord(((0, "X"),)), size=6)
        self.assertEqual(
            orbit,
            tuple(
                PauliWord(((site, "X"),))
                for site in range(6)
            ),
        )

    def test_representation_permutations_follow_group_composition(self):
        size = 5
        basis = (PauliWord(),) + tuple(
            PauliWord(((site, "X"),))
            for site in range(size)
        )
        translation = DihedralElement(1, False)
        reflection = DihedralElement(0, True)
        self.assertEqual(
            representation_permutation(translation, basis, size),
            (0, 2, 3, 4, 5, 1),
        )
        self.assertEqual(
            representation_permutation(reflection, basis, size),
            (0, 1, 5, 4, 3, 2),
        )
        elements = (
            DihedralElement(0, False),
            translation,
            reflection,
            DihedralElement(2, True),
        )
        for left in elements:
            left_permutation = representation_permutation(
                left,
                basis,
                size,
            )
            self.assertEqual(
                sorted(left_permutation),
                list(range(len(basis))),
            )
            for right in dihedral_elements(size):
                right_permutation = representation_permutation(
                    right,
                    basis,
                    size,
                )
                product_permutation = representation_permutation(
                    compose(left, right, size),
                    basis,
                    size,
                )
                self.assertEqual(
                    product_permutation,
                    tuple(
                        left_permutation[right_permutation[index]]
                        for index in range(len(basis))
                    ),
                )

    def test_nonclosed_basis_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not closed"):
            representation_permutation(
                DihedralElement(1, False),
                (PauliWord(), PauliWord(((0, "X"),))),
                size=4,
            )

    def test_size_and_normalization_are_validated(self):
        self.assertEqual(
            normalize(DihedralElement(-1, True), size=5),
            DihedralElement(4, True),
        )
        with self.assertRaisesRegex(ValueError, "size.*3"):
            dihedral_elements(2)
        with self.assertRaisesRegex(ValueError, "site.*range"):
            act_on_site(DihedralElement(0, False), 5, size=5)

    def test_package_exports_dihedral_boundary(self):
        from challenge233.sdp import (
            DihedralElement as ExportedElement,
            act_on_word as exported_act_on_word,
        )

        self.assertEqual(
            exported_act_on_word(
                ExportedElement(1, False),
                PauliWord(((0, "X"),)),
                size=4,
            ),
            PauliWord(((1, "X"),)),
        )


class DihedralSectorTests(unittest.TestCase):
    def test_single_site_seed_closes_to_identity_plus_all_translates(self):
        basis = close_word_basis(
            (PauliWord(), PauliWord(((0, "X"),))),
            size=4,
        )
        self.assertEqual(len(basis), 5)
        self.assertIn(PauliWord(), basis)
        for site in range(4):
            self.assertIn(PauliWord(((site, "X"),)), basis)
        for element in dihedral_elements(4):
            self.assertEqual(
                sorted(
                    act_on_word(element, word, 4)
                    for word in basis
                ),
                list(basis),
            )

    def test_translation_orbits_are_ordered_from_canonical_representative(self):
        basis = close_word_basis(
            (PauliWord(), PauliWord(((0, "X"),))),
            size=5,
        )
        orbits = translation_orbits(basis, size=5)
        self.assertEqual(len(orbits), 2)
        self.assertEqual(orbits[0].members, (PauliWord(),))
        self.assertEqual(
            orbits[1].members,
            tuple(
                PauliWord(((site, "X"),))
                for site in range(5)
            ),
        )
        self.assertEqual(
            orbits[1].representative,
            PauliWord(((0, "X"),)),
        )

    def test_irrep_catalog_has_full_group_dimension(self):
        for size in (5, 6):
            catalog = dihedral_irrep_catalog(size)
            self.assertEqual(
                sum(irrep.dimension**2 for irrep in catalog),
                2 * size,
            )
            for irrep in catalog:
                if irrep.dimension == 2:
                    self.assertEqual(len(irrep.momenta), 2)
                    self.assertEqual(
                        sum(irrep.momenta) % size,
                        0,
                    )
                    self.assertIsNone(irrep.reflection_parity)
                else:
                    self.assertIn(irrep.reflection_parity, (-1, 1))

    def test_sector_multiplicities_reconstruct_representation_dimension(self):
        basis = close_word_basis(
            (PauliWord(), PauliWord(((0, "X"),))),
            size=4,
        )
        sectors = sector_multiplicities(basis, size=4)
        self.assertEqual(
            sum(
                item.irrep.dimension * item.multiplicity
                for item in sectors
            ),
            len(basis),
        )
        by_label = {
            item.irrep.label: item.multiplicity
            for item in sectors
        }
        self.assertEqual(by_label["k=0,r=+1"], 2)
        self.assertEqual(by_label["k=0,r=-1"], 0)
        self.assertEqual(by_label["k=pi,r=+1"], 1)
        self.assertEqual(by_label["k=pi,r=-1"], 0)
        self.assertEqual(by_label["k=1<->3"], 1)

    def test_reflection_paired_translation_orbits_split_both_parities(self):
        basis = close_word_basis(
            (PauliWord(((0, "X"), (1, "Z"))),),
            size=6,
        )
        sectors = sector_multiplicities(basis, size=6)
        self.assertEqual(
            sum(
                item.irrep.dimension * item.multiplicity
                for item in sectors
            ),
            len(basis),
        )
        by_label = {
            item.irrep.label: item.multiplicity
            for item in sectors
        }
        # The oriented-word orbit contributes one copy of each parity;
        # close_word_basis also inserts the reflection-even identity.
        self.assertEqual(by_label["k=0,r=+1"], 2)
        self.assertEqual(by_label["k=0,r=-1"], 1)
        self.assertEqual(by_label["k=pi,r=+1"], 1)
        self.assertEqual(by_label["k=pi,r=-1"], 1)
        self.assertEqual(by_label["k=1<->5"], 2)
        self.assertEqual(by_label["k=2<->4"], 2)

    def test_odd_reflection_offset_gives_odd_pi_parity(self):
        basis = close_word_basis(
            (PauliWord(((0, "X"), (1, "X"))),),
            size=4,
        )
        sectors = sector_multiplicities(basis, size=4)
        by_label = {
            item.irrep.label: item.multiplicity
            for item in sectors
        }
        self.assertEqual(by_label["k=pi,r=+1"], 0)
        self.assertEqual(by_label["k=pi,r=-1"], 1)

    def test_basis_builder_rejects_out_of_range_or_nonword_seeds(self):
        with self.assertRaisesRegex(ValueError, "site.*range"):
            close_word_basis(
                (PauliWord(((4, "X"),)),),
                size=4,
            )
        with self.assertRaisesRegex(TypeError, "PauliWord"):
            close_word_basis(("X_0",), size=4)

    def test_package_exports_basis_and_sector_boundary(self):
        from challenge233.sdp import (
            close_word_basis as exported_close,
            sector_multiplicities as exported_sectors,
        )

        basis = exported_close(
            (PauliWord(((0, "Z"),)),),
            size=5,
        )
        self.assertEqual(
            sum(
                item.irrep.dimension * item.multiplicity
                for item in exported_sectors(basis, size=5)
            ),
            len(basis),
        )


if __name__ == "__main__":
    unittest.main()
