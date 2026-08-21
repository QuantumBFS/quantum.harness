import numpy as np
from core.lattice import SquareLattice


def test_neighbors_open_bc():
    L = SquareLattice(3, 3)
    assert sorted(L.neighbors(0)) == [1, 3]          # top-left corner
    assert sorted(L.neighbors(4)) == [1, 3, 5, 7]    # center
    assert sorted(L.neighbors(8)) == [5, 7]          # bottom-right corner
    assert L.N == 9


def test_snake_map_is_permutation_and_serpentine():
    L = SquareLattice(4, 3)  # width 4, height 3
    mp = L.snake_index_map()
    assert sorted(mp.tolist()) == list(range(L.N))   # a permutation
    # row 0 left->right: sites 0,1,2,3
    assert mp[0:4].tolist() == [0, 1, 2, 3]
    # row 1 right->left: sites 7,6,5,4  (y=1 row-major base = 4)
    assert mp[4:8].tolist() == [7, 6, 5, 4]
    # row 2 left->right: sites 8,9,10,11
    assert mp[8:12].tolist() == [8, 9, 10, 11]
