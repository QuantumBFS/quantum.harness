"""Square lattice with open boundary conditions and a row-major serpentine
("snake") mapping used to turn the 2D lattice into a 1D chain for the v0
snake-MPS METTS engine.
"""
import numpy as np


class SquareLattice:
    def __init__(self, Lx, Ly):
        self.Lx = int(Lx)
        self.Ly = int(Ly)
        self.N = self.Lx * self.Ly

    def _xy(self, i):
        return i % self.Lx, i // self.Lx

    def neighbors(self, i):
        """Open-BC nearest neighbours of site i (row-major index)."""
        x, y = self._xy(i)
        nb = []
        if x + 1 < self.Lx:
            nb.append(i + 1)
        if x - 1 >= 0:
            nb.append(i - 1)
        if y + 1 < self.Ly:
            nb.append(i + self.Lx)
        if y - 1 >= 0:
            nb.append(i - self.Lx)
        return nb

    def snake_index_map(self):
        """Return a length-N int array ``mp`` with ``mp[snake_pos] = site_index``.

        Row-major serpentine: row y traversed left->right if y even,
        right->left if y odd. This keeps most 2D nearest-neighbour bonds
        adjacent in the 1D ordering.
        """
        mp = np.empty(self.N, dtype=int)
        pos = 0
        for y in range(self.Ly):
            xs = range(self.Lx) if y % 2 == 0 else range(self.Lx - 1, -1, -1)
            for x in xs:
                mp[pos] = y * self.Lx + x
                pos += 1
        return mp
