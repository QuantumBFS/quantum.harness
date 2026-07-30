# Oddcycle local-H first-batch portfolio

Date: 2026-07-30

Source commit:
`bebab46956baf3c672f68349a76e49879f6be483`

Frozen settings SHA-256:
`c2ba0297dc3c59e74db52cfbebc3858c8a04d57b0867e3bb088d5f2776dc30ae`

The preserved clean WSL worktree is detached at the exact source SHA. The CPU
source archive is
`/home/jzb/nnv-local-h-bebab46956baf3c672f68349a76e49879f6be483-source.tar`;
its SHA-256 is
`be546b877bcd86fac98705b1417183dd204647095746692a7c92ec7af59c1f25`.

## Result

The frozen length-one through length-four batch completed all 40 cells:

| route | cells | survivor | infeasible | inconclusive | claim |
|---|---:|---:|---:|---:|---|
| A: free local cone | 20 | 0 | 20 | 0 | numerical infeasibility only |
| B: named local targets | 16 | 0 | 16 | 0 | numerical infeasibility only |
| D: discrete transfers | 4 | 4 | 0 | 0 | exact positive transfers; numerical Hamiltonian profiles |

There was no numerical free-cell survivor and therefore no exact-promotion
candidate. The first batch established no certified exact local Hamiltonian
through maximum word length four. This is not a no-go theorem: the frozen runner
retained no exact dual separating functional, and longer or differently
prioritized word dictionaries remain open.

The Route-D cells produced a ranked batch of strictly positive transfers.
Their matrix logarithms are Hermitian, with numerical evidence for interaction
and non-Gaussianity, but none is established or certified exactly local. The
batch therefore reaches the design hierarchy's `L1`, not `L2`.

All 40 cell IDs were unique; there were no duplicates, missing payloads, or
payload-hash conflicts.

The earlier precompute regression reported `41 passed in 31.88s`. After the
run, the exact-SHA WSL code regression over the eleven Task 8 test files
reported `42 passed in 32.14s`, with all numerical-library threads and
`PYTHONHASHSEED` fixed as in the protocol. That final regression covered the
code at `bebab469...`; the newly tracked result JSON was parsed separately on
local Windows.

## Continuous-time macro-word construction

Let the certified alphabet be

```text
A = {B0, B0.T, B1, B1.T}
```

and let `Gamma(W)` be the number-conserving Fock lift of a word `W`. For each
transpose orbit define

```text
Phi_W = Gamma(W) + Gamma(W.T).
```

An exact Route-A or Route-B survivor would have

```text
H = E0 I - sum_W q_W Phi_W,       q_W > 0.
```

Expanding `exp(-beta H)` chooses `W` or `W.T` at each macro-event.
Concatenating the selected branches gives a word in the original four-letter
alphabet. Every Fock trace is therefore

```text
Tr Gamma(W_n ... W_1) = det(I + W_n ... W_1) > 0
```

by the frozen arbitrary-word oddcycle theorem. The scalar `E0` contributes
only the positive factor `exp(-beta E0)`. This is a continuous-time
interaction/Taylor expansion; it is separate from Route D below.

No such exact local combination was certified by the length-four free or
target screens.

## Discrete-transfer construction

Route D samples exact positive rational weights and constructs

```text
T = c I + sum_W q_W Phi_W,
H_D = -log(T / T_vac).
```

The integer shift `c` is chosen with exact arithmetic so every row has a
strict positive diagonal-dominance margin. Hence `T` is exactly real
symmetric positive definite. Word concatenation gives exact positive
discrete auxiliary-field histories.

The logarithm and its 252 normal-ordered coordinates are evaluated
numerically. Body-order norms, forbidden-support norms, interaction norm, and
Gaussian-grade distance are ranking diagnostics. A small forbidden norm
would not be an exact zero; the observed norms are in fact order one.

## Accepted reverse-construction seed

The compact accepted set contains one reverse-construction seed: the record
with the smallest `cluster-two-body` forbidden-support norm across all four
completed portfolio cells.

### Survivor A

```text
source cell:       portfolio-l2
sample index:      122
seed:              20260730
exact shift:       42
exact T_vac:       44
exact row margin:  12213/15625
```

With symbols `0=B0`, `1=B0.T`, `2=B1`, and `3=B1.T`, its word
representatives are:

```text
(0), (2), (0,0), (0,1), (0,2), (0,3),
(1,0), (1,2), (1,3), (2,2), (2,3), (3,2).
```

Their exact positive weights in the same order are:

```text
11/72, 1/36, 1/72, 11/72, 1/72, 1/24,
1/12, 1/24, 1/72, 1/72, 2/9, 2/9.
```

Thus the accepted Hamiltonian seed is exactly identified by

```text
T_A = 42 I + sum_W q_W Phi_W,
H_A = -log(T_A / 44).
```

The exact transfer certificate and numerical Hamiltonian diagnostics are:

| quantity | value | status |
|---|---:|---|
| minimum row margin | `12213/15625` | exact |
| minimum transfer eigenvalue | `43.08101089589473` | numerical |
| log reconstruction residual | `2.5863801869872575e-14` | numerical |
| coordinate reconstruction residual | `2.9716871307260523e-15` | numerical |
| interaction norm | `0.7721245374285716` | numerical |
| Gaussian-grade distance | `7.973697906947008` | numerical |
| cluster-two-body leakage | `0.5411019488203146` | numerical |
| path-arc3 leakage | `0.5977828806814701` | numerical |
| ring-arc3 leakage | `0.5691435089461904` | numerical |
| path-edge leakage | `0.6860196263057259` | numerical |
| ring-edge leakage | `0.6842674402775771` | numerical |

The body-order norms from orders zero through five are:

```text
0,
0.19310387271049814,
0.5508039417815956,
0.4566425597169218,
0.22510540122185593,
0.18329334415921095.
```

Survivor A is an exact positive-transfer seed with a numerical
interacting/non-Gaussian Hamiltonian profile. It is not certified as an exact
local Hamiltonian.

## Length-four portfolio leader

Every portfolio cell retained 256 conclusive samples and zero inconclusive
samples:

| cell | best sample | payload SHA-256 | raw file SHA-256 |
|---|---:|---|---|
| `portfolio-l1` | 142 | `c52374feaf2e81a7c6e7aff69d4165594d4595cecc3b884ce4b5aa1f5fb270e8` | `3abcff81413d479801aa54e4d55e33464613813d5ee23d21249b3626f442b36f` |
| `portfolio-l2` | 122 | `b93465d16f4c9d796bac26104b035ae74f85c1e1e297cc94ff2cb8e4373e2c42` | `c16d32355448d9bd89e282323fbaa64852a408edc8439404feb82ff5bc21cae7` |
| `portfolio-l3` | 89 | `ce065bb507cc0c073f62b8f45a132b9aa0b5d420480368c4fecc184eb0359a81` | `f116c5e4bede6fb7f334d0ae193f3d7bc16de283934fd4a167a3ef04a7d9d4f0` |
| `portfolio-l4` | 206 | `d99c8c45bea6c90e75c1c00a9a591106d06c0844125b71a18e910c5e37ccac3c` | `4a48d182f44139ace3946a66bc1bc7b11828b540a938a1bf18779ce73aa2850b` |

The length-four cell compiled 180 columns and all 256 samples had conclusive
numerical logarithms. Its best record was sample 206:

| quantity | value |
|---|---:|
| exact shift | `14219` |
| exact row margin | `6660970905617/12179687500000` |
| minimum transfer eigenvalue | `14219.459608288844` |
| log reconstruction residual | `9.79082851200976e-15` |
| coordinate reconstruction residual | `2.483727966208917e-15` |
| interaction norm | `1.0788673738422012` |
| Gaussian-grade distance | `3.2399488165601835` |
| cluster-two-body leakage | `1.0782559100784923` |

It confirms that the longer dictionary supplies transfer-positive
interacting/non-Gaussian candidates, but its locality ranking is worse than
Survivor A.

## Reverse-construction handoff

The next Hamiltonian reverse-construction stage freezes Survivor A by its
cell ID, sample index, source payload digest, words, exact weights, shift, and
vacuum value. It then:

1. reconstructs `T_A` exactly and retains the exact positivity/history proof;
2. refines `H_A` at declared high precision;
3. promotes its dominant normal-ordered terms to a named target and uses its
   forbidden-support leakage to prioritize word extensions;
4. searches for a new positive continuous-time representation; and
5. requires exact forbidden-coordinate cancellation and full-Fock equality
   before any `L2` claim.

This is parallel to the protocol-required cache-reusing length-six amendment.
Survivor A does not stop the length extension because only an exact Route-A
or Route-B `L2` survivor can do that.

The controller records an explicit plan deviation at closure. The frozen
runner retained no exact dual or residual vectors with which to implement the
planned residual-prioritized length-six amendment; freezing a launch command
now would fabricate that prioritization. Under the delegated success-first
policy, the amendment is deferred while a separate Survivor-A
reverse-construction protocol is designed. Neither route may launch before its
protocol is frozen and committed. Task 8 execution/results are closed, while
the exact next-scientific-command interface is intentionally carried to that
next protocol task.

## Claim boundary

- Exact: source words and transpose pairing, positive rational weights,
  shifts, vacuum values, row margins, transfer positivity, Hermiticity of the
  matrix logarithm, and discrete-history positivity.
- Numerical: logarithm reconstruction, normal-ordered coefficients,
  interaction/non-Gaussian diagnostics, and all locality profiles.
- Not established: exact local `H`, exact non-stoquastic separation for a
  local `H`, or a scalable connected overlapping-cluster lattice.

A five-mode connected path or ring would be a finite `L2` cluster if exact
locality were proved. It would still not be a scalable lattice family.

The corrected WSL dispatch paths are:

```text
eligible free input:
  /home/zibojin/code/nnv-local-h-runs/bebab46956baf3c672f68349a76e49879f6be483/incoming-free
non-free preservation:
  /home/zibojin/code/nnv-local-h-runs/bebab46956baf3c672f68349a76e49879f6be483/incoming-other
exact promotion output:
  /home/zibojin/code/nnv-local-h-runs/bebab46956baf3c672f68349a76e49879f6be483/exact-promotions
```

Promotion was not invoked because there were zero eligible free candidates.
The legacy `incoming` directory preserves the initially rejected
`portfolio-l1` copy; it was never the corrected free-promotion input.

The complete compact summary is retained at the historical filename
`/home/zibojin/code/nnv-local-h-runs/bebab46956baf3c672f68349a76e49879f6be483/portfolio-partial-summary.json`;
despite its name it contains `portfolio-l1` through `portfolio-l4`. Its
SHA-256 is
`5279b37038d75a81a001f1583041612c9e272cd19007b5a9a048ee04e6b940ee`.
