from __future__ import annotations

from challenge233.sdp.algebra import PauliWord
from challenge233.sdp.symmetry import (
    act_on_word,
    dihedral_elements,
    representation_permutation,
)


def close_word_basis(seed_words, size: int) -> tuple:
    """Close canonical Pauli words under the periodic-chain D_N action."""
    size = int(size)
    elements = dihedral_elements(size)
    seeds = tuple(seed_words)
    for word in seeds:
        if not isinstance(word, PauliWord):
            raise TypeError("every seed word must be a PauliWord")
        for site, _ in word.factors:
            if not 0 <= site < size:
                raise ValueError(
                    "word factor site must lie in range(size): "
                    f"site={site}, size={size}"
                )

    closed = {PauliWord()}
    for word in seeds:
        closed.update(
            act_on_word(element, word, size)
            for element in elements
        )
    basis = tuple(sorted(closed))

    for element in elements:
        representation_permutation(element, basis, size)
    return basis
