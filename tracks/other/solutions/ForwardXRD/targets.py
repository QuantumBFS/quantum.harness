#!/usr/bin/env python
"""Benchmark structures, the target registry, and the match criteria.

Shared definitions, kept here rather than in whichever experiment happened to
introduce them. Previously the solver imported its target builders from
`crossover.py` (a prior-vs-enumeration study) and its StructureMatcher settings
from `refine_coords.py` (a superseded refinement experiment), which made the
production path depend on two throwaway scripts and blocked deleting either.

The seven targets span five crystal systems and 1-9 free internal coordinates --
the variable that actually governs difficulty, unrelated to atom count (20-atom
CaTiO3 has 7, 8-atom CuO has 1).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Lattice, Structure

CF = Path(os.environ.get("CRYSTALFORMER_DIR",
                         Path.home() / "code/CrystalFormer"))


# --------------------------------------------------------------------------
# match criteria
# --------------------------------------------------------------------------

# graded: loose enough to score near-misses rather than only accept/reject
SM_GRADED = StructureMatcher(ltol=0.3, stol=0.5, angle_tol=10, primitive_cell=True)
# pass/fail at pymatgen defaults. NOTE stol=0.3 is permissive -- a structure can
# "fit" at rms ~0.18, which is not solved by any crystallographic standard. Use
# ltol=stol=0.05 when a result is being reported.
SM_STRICT = StructureMatcher(primitive_cell=True, attempt_supercell=True)


def strict_matcher(stol: float = 0.05):
    return StructureMatcher(ltol=stol, stol=stol, angle_tol=5,
                            primitive_cell=True, attempt_supercell=True)


# --------------------------------------------------------------------------
# builders: params -> Structure, at the reference cell
# --------------------------------------------------------------------------


def pyrite(p):
    return Structure.from_spacegroup(
        "Pa-3", Lattice.cubic(5.4160), ["Fe", "S"], [[0, 0, 0], [p[0], p[0], p[0]]])


def rutile(p):
    return Structure.from_spacegroup(
        "P4_2/mnm", Lattice.tetragonal(4.5937, 2.9587),
        ["Ti", "O"], [[0, 0, 0], [p[0], p[0], 0]])


def marcasite(p):
    return Structure.from_spacegroup(
        "Pnnm", Lattice.orthorhombic(4.4430, 5.4240, 3.3870),
        ["Fe", "S"], [[0, 0, 0], [p[0], p[1], 0]])


def quartz(p):
    return Structure.from_spacegroup(
        "P3_121", Lattice.hexagonal(4.9137, 5.4047),
        ["Si", "O"], [[p[0], 0, 1 / 3], [p[1], p[2], p[3]]])


def perovskite(p):
    return Structure.from_spacegroup(
        "Pnma", Lattice.orthorhombic(5.4423, 7.6401, 5.3800),
        ["Ca", "Ti", "O", "O"],
        [[p[0], 0.25, p[1]], [0, 0, 0.5], [p[2], 0.25, p[3]], [p[4], p[5], p[6]]])


def baddeleyite(p):
    return Structure.from_spacegroup(
        "P2_1/c", Lattice.monoclinic(5.1505, 5.2116, 5.3173, 99.23),
        ["Zr", "O", "O"],
        [[p[0], p[1], p[2]], [p[3], p[4], p[5]], [p[6], p[7], p[8]]])


def tenorite(p):
    return Structure.from_spacegroup(
        "C2/c", Lattice.monoclinic(4.6837, 3.4226, 5.1288, 99.54),
        ["Cu", "O"], [[0.25, 0.25, 0], [0, p[0], 0.25]])


# builder, true params, space group, formula, atoms/cell, prior samples
REGISTRY = {
    "pyrite": (pyrite, np.array([0.3847]), 205, "FeS2", 12,
               CF / "samples_ladder/out_sg205_FeS2.csv"),
    "rutile": (rutile, np.array([0.3053]), 136, "TiO2", 6,
               CF / "samples_ladder/out_sg136_TiO2.csv"),
    "tenorite": (tenorite, np.array([0.4184]), 15, "CuO", 8,
                 CF / "samples_SG/output_CuO.csv"),
    "marcasite": (marcasite, np.array([0.2003, 0.3787]), 58, "FeS2", 6,
                  CF / "samples_ladder/out_sg58_FeS2.csv"),
    "quartz": (quartz, np.array([0.4697, 0.4135, 0.2669, 0.1191]), 152, "SiO2", 9,
               CF / "samples_ladder/out_sg152_SiO2.csv"),
    "perovskite": (perovskite,
                   np.array([0.0357, -0.0064, 0.4890, 0.0707, 0.2887, 0.0387, 0.7113]),
                   62, "CaTiO3", 20, CF / "samples_ladder/out_sg62_CaTiO3.csv"),
    "baddeleyite": (baddeleyite,
                    np.array([0.2758, 0.0411, 0.2082, 0.0703, 0.3359, 0.3406,
                              0.4423, 0.7549, 0.4789]),
                    14, "ZrO2", 12, CF / "samples_SG/output_ZrO2.csv"),
}

# backwards-compatible aliases for the underscore names the experiment scripts used
_pyrite, _rutile, _marcasite = pyrite, rutile, marcasite
_quartz, _perovskite, _baddeleyite, _tenorite = quartz, perovskite, baddeleyite, tenorite
