# Reproducing the exact certificates

The finite certificates require only Python 3.10 or newer and use no
third-party packages.

Run from the root of the `quantum.harness` checkout:

```bash
python3 tracks/other/solutions/yanwang-251/submission_package/verify_interface_certificates.py
```

The script performs three independent checks:

1. It constructs the complete Bell-partition composition tensor on three
   terminals and compares every coefficient of the resulting symbolic
   biquadratic Rayleigh-determinant identity.
2. It constructs the complete 15-state four-terminal composition tensor,
   replays the two integer signatures from the research note, and checks all
   three disjoint perfect matchings before and after composition.
3. It directly enumerates every forest of `K3 join independent(r)` for
   `r=1,2,3,4` at integer core/spoke activities `2,3` and checks every pair of
   edges.  This is a regression for the closed-form proof in the note, not a
   replacement for that proof.

Expected final line:

```text
all exact interface certificates passed
```

All sign conventions are stated in `RESEARCH_NOTE.md`.  In particular,
`R = AD - BC > 0` is the counterexample sign requested by issue #251.
