# External 1D Basis Sources

Place the original optimized basis-construction source files in this
directory without modifying them to fit the project.

When the files are present, record:

- language and required runtime;
- entry point and expected arguments;
- open or periodic boundary convention;
- blockade radius and state encoding;
- basis ordering and state ↔ index map;
- symmetry sectors;
- source or license information.

Generated tables and caches belong in `.cache/` and are ignored. The
project-facing adapter will be written later under
`src/challenge233/basis/`, after the Hamiltonian and basis contract receive
explicit confirmation.

## Trusted source drop (2026-07-29)

The user supplied the following original Python sources and declared them
trusted. Keep these files unchanged; project-specific checks and Hamiltonian
construction belong in `src/challenge233/basis/` and `src/challenge233/ed/`.

| File | Purpose | SHA-256 |
|---|---|---|
| `pxpbasis.py` | Spin-1/2 constrained `QuSpin.user_basis` using 32-bit bit states | `1dddefa1b616fad7eb57702deb30a192479507dbb617929c744b1d43d7b652fe` |
| `pxpbasisS.py` | General-`sps` constrained `QuSpin.user_basis` using 32-bit base-`sps` states | `2462c40153bddf1ac0a088971bc7d33564d1f8ad9b6e5cbe3f2a174350bc078e` |

Both files export:

```python
constrained_basis(sps, N, kblock, pblock)
```

Recorded source contract:

- Runtime: Python with QuSpin, Numba, and NumPy.
- Boundary: periodic. The blockade pre-check wraps site `N - 1` back to site
  `0`; these sources do not implement an open-boundary switch. This records
  the supplied source behavior only and does not choose the research
  Hamiltonian's finite-size boundary condition.
- Constraint: nearest-neighbor blockade. In `pxpbasis.py`, no adjacent bits
  may both equal one. In `pxpbasisS.py`, no adjacent occupations may both be
  nonzero.
- Encoding: `pxpbasis.py` uses bit-packed `uint32` states for spin-1/2;
  `pxpbasisS.py` uses base-`sps` `uint32` states. The practical size bound
  must therefore be checked before an adapter requests a system.
- Symmetries: optional one-site translation (`kblock`) and reflection
  (`pblock`). The supplied code combines reflection with translation only
  when `kblock == 0`; otherwise a requested `pblock` is not applied.
- Basis ordering and state-to-index mapping are owned by QuSpin's
  `user_basis`; the source does not declare a separate stable ordering.
  Adapters must treat the returned `basis.states` ordering as explicit run
  metadata rather than reimplementing it.
- Provenance/license: user-supplied trusted source; no external license was
  declared. Do not redistribute before the user declares the local research
  project complete.
