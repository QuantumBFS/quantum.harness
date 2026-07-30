# Solver-free Square J1-J2 patch and basis counts

These counts come from
`scripts/count_basis.jl` using the deterministic prototype in
`src/SquareJ1J2Prototype.jl`. No SDP solver or external package is involved.

Setup:

```text
outer patch Λ_L = [-L,L]²
inner patch I_L = [-(L-1),L-1]²
J1 bonds = horizontal/vertical, counted once
J2 bonds = both diagonals, counted once
positive basis degree = d
gap basis degree = d-1
no symmetry quotient
```

## Exact counts

| L | d | outer / inner sites | J1 / J2 bonds | bare operator positive basis | one-symbol positive basis | full state-polynomial positive basis | bare / one-symbol / full gap basis | raw full-positive matrix storage |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 9 / 1 | 12 / 8 | 352 | 703 | 1,810 | 4 / 7 / 7 | 49.99 MiB |
| 1 | 3 | 9 / 1 | 12 / 8 | 2,620 | 5,239 | 46,450 | 4 / 7 / 22 | 32.15 GiB |
| 2 | 2 | 25 / 9 | 40 / 32 | 2,776 | 5,551 | 14,026 | 28 / 55 / 55 | 2.931 GiB |
| 2 | 3 | 25 / 9 | 40 / 32 | 64,876 | 129,751 | 1,032,626 | 352 / 703 / 1,810 | 15.52 TiB |
| 3 | 2 | 49 / 25 | 84 / 72 | 10,732 | 21,463 | 53,950 | 76 / 151 / 151 | 43.37 GiB |

Definitions:

- `bare operator basis` contains all canonical Pauli strings through the
  stated degree.
- `one-symbol basis` contains every selected bare word `w` plus one scalar row
  `ζ(w)` for each nonidentity word. It is a deterministic structured baseline,
  not the complete hierarchy.
- `full state-polynomial basis` contains every formal monomial
  `ζ(w1)...ζ(wk)v` through the stated total degree. Its count is obtained
  exactly from the truncated generating function
  `(1+3t)^n Π_(w≠I)(1-t^deg(w))^-1`.
- Storage is only `16m²` bytes for one dense `ComplexF64` matrix of dimension
  `m`. It excludes affine maps, other PSD blocks, factorization workspace, and
  the solver's KKT system, so it is a strict underestimate of solve memory.

## Consequences

1. The complete state-polynomial positive matrix, not the gap block, is the
   first memory wall for this square exhaustion.
2. Even the smallest degree-three complete instance shown here has dimension
   `46,450` and raw matrix storage above `32 GiB`; an interior-point solve
   would require much more memory.
3. `(L,d)=(2,3)` is already impossible as a dense complete relaxation
   (`m=1,032,626`) without major locality/symmetry/block reductions.
4. A practical implementation therefore needs a declared nested structured
   basis. Reporting only `(L,d)` is insufficient: the basis rule and hash are
   part of the mathematical relaxation.
5. The upstream Kagome/TFIM basis sizes cannot be compared directly with this
   table because they use hand-selected words and symmetry blocks rather than
   the complete state-polynomial basis.

## Reproduction

```bash
julia --startup-file=no \
  tracks/polyopt/solutions/sdp-gap-seekers/scripts/count_basis.jl

julia --startup-file=no \
  tracks/polyopt/solutions/sdp-gap-seekers/test/runtests.jl
```

The unit suite currently checks patch/bond counts, the one-layer interaction
buffer, exact Pauli multiplication, explicit enumeration against the
combinatorial bare-word count, state-polynomial count anchors, and storage
arithmetic.
