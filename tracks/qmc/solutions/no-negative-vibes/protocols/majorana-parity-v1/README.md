# Majorana reflection-positive parity survey v1

The ordinary Majorana reflection-positivity theorem controls the full Fock
trace.  This first survey resolves it into even and odd fermion-parity sectors
in the canonical `J1/J2` and Jordan--Wigner Majorana orientation, and tests
the convention-dependent conjecture

```text
pi_* = (-1)^[m(m+1)/2],
```

where `m` is the number of complex fermion modes.

## Fixed survey

- modes `m=2,3,4,5,6`;
- depth `4`;
- normalized generator scale `3`;
- seed `20260728`;
- 128 histories per mode, 640 histories total.

Run from the solution directory:

```bash
PYTHONPATH=. python3 -m oracle.majorana_parity \
  --modes 2 3 4 5 6 \
  --depth 4 \
  --scale 3 \
  --seed 20260728 \
  --samples 128
```

An orientation-reversing Majorana relabeling can exchange the even and odd
labels.  The zero-failure sector is a numerical conjecture requiring an
analytic proof.  The complementary sector has float64 negative samples at
every tested mode count, but those samples have not yet received an
arbitrary-precision replay.

The committed machine-readable output is
`fixtures/majorana_parity_survey.json`; interpretation is summarized in
`docs/SPECULATIVE_STRUCTURE_RESULTS.md`.
