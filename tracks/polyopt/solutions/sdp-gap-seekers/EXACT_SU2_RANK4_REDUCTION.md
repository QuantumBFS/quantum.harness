# Exact continuous-spin reduction through degree four

## Scope

The complete `d=2` state-polynomial relaxation contains scalar moments with
at most four Pauli-vector factors. The existing exact V4 and S3 quotient is
the proper octahedral rotation group. Averaging any unrestricted feasible KMS
functional over global SU(2) rotations is therefore WLOG: it preserves the
Hamiltonian, stationarity, normalization, and every PSD condition. This is a
convex state average, not a restriction to a total-spin Hilbert-space sector.

## Missing rank-four identity

The octahedral and SO(3) invariant tensors agree through rank two. At rank
four, an SO(3)-invariant tensor on four fixed vector slots is

```text
T_abcd = alpha delta_ab delta_cd
       + beta  delta_ac delta_bd
       + gamma delta_ad delta_bc.
```

Consequently, for every fixed site and state-symbol skeleton,

```text
T_xxxx = T_xxyy + T_xyxy + T_xyyx.
```

Global axis permutations already identify the choices of distinct axes, so
this is the only additional continuous-spin relation needed at moment degree
at most four. If symbol commutativity or spatial reflection identifies some
of the three right-hand coordinates, their integer coefficients combine
exactly.

## Implementation and fail-closed status

`SHASTRY_SU2_RANK4_REDUCTION=1` substitutes the identity into every exact
coefficient polynomial before native Mosek constraints are created. The
default route and its established hashes are unchanged. The reduced route
uses a distinct fingerprint schema and records the number of eliminated
rank-four coordinates.

`SHASTRY_CERTIFICATE_BUILD_ONLY=1` stops after the complete native task and
coefficient fingerprint are assembled. It is intended only for independent
structural/hash reproduction and is recorded as `not_run_exact_build_only`;
it produces no numerical feasibility statement.

The native-dual route alone was inconclusive. L=1 job `118179614` reduced the
7,231 moment equations to 5,314 (1,917 eliminated; 26.5%) with coefficient SHA-256
`7308c57ba6b515501fd1c0c00f753868c0bb8cb32531429398fd902b4d63231a`.
Its native certificate task returned `OPTIMAL`, although the unreduced L=1
relaxation is known feasible. The fresh-task replay passes at `1e-7` with
maximum violation `2.3730706288915826e-8` but fails at `1e-9`. This numerical
contradiction is not a certificate. Unreduced control `118180537` reproduced
the established coefficient hash but also returned approximate `OPTIMAL`;
its `1.053194864653051e-9` violation fails the declared `1e-9` audit. Thus the
explicit bar system is weakly/numerically feasible even for the known-feasible
control, and status is not a valid discriminator.

The decisive native-primal comparison passed. SCNet job `118181379`, from
clean commit `4de8fc4`, reproduced the reduced hash and all 23 PSD blocks,
then returned a primal-and-dual feasible point classified
`feasible_residual_checked_float` at `1e-9`. Mosek's recomputed maximum
affine-cone and equality violations were both zero. The run used 5,314 moment
variables, 75,967 packed PSD rows, 241,903 scalar terms, and 24,548,328 KiB
Slurm MaxRSS. The exact rank-four quotient is therefore authorized for L=2.

Interpretation still requires the second gate:

1. completed: residual-checked L=1 reduced-primal feasibility with the exact
   reduced coefficient hash; and
2. pending: two independent L=2 constructions with the same exact coefficient
   hash before any numerical result is interpreted.
