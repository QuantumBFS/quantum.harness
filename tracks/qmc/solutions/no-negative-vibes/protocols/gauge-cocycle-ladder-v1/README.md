# Gauge-cocycle ladder v1

This protocol audits the first edge-electric `Z2` gauge ansatz for cancelling
fermion hopping signs.

## Definition

- geometry: open `2 x L` ladder with row-major Fock ordering;
- gauge variables: one GF(2) electric bit `a_e` per hopping link;
- Gauss law: `n_v=q_v+sum_(e incident v) a_e mod 2`;
- hop: toggle the two endpoint occupations and the traversed link bit;
- compensator: an affine GF(2) phase of the link bits.

The square (`L=2`) and two-overlapping-square (`L=3`) systems are exhausted.
All closed legal words through depth 8 are counted for `L=3`.  The exact
central-rung support is then constructed for `L=2..10`.

## Run

From the solution directory:

```bash
python3 -m pytest tests/test_gauge_cocycle.py -q
```

## Outcome

The affine gauge phase cancels every fermion matrix-element sign and preserves
Gauss' law.  However, on a `2 x L` ladder the central rung phase contains all
`L-1` other rung variables.  Its support and radius grow with `L`, so this
ansatz only relocates the Jordan--Wigner string and is not a scalable local
encoding.

This protocol does not rule out modified-Gauss-law exact bosonization or
non-affine/projected gauge cones.
