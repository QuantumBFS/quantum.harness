# Advisor review of Sihan's Feishu certificate update

Date: 2026-07-28  
Source: recent messages in the Feishu group `hackathon`  
Review mode: read-only and static

## Access status

Codex can access the `hackathon` group through the existing `lark-cli`
configuration and the installed `lark-im` skill. No additional skill
installation is needed.

The user identity is authorized for chat and message reads. The first
authorization check failed only because the sandbox could not reach the local
proxy; the same check succeeded with the permitted external command execution.

No message was sent, replied to, edited, bookmarked, downloaded, or otherwise
mutated during this review.

## Messages reviewed

The two most relevant updates were posted at approximately 18:27 and 18:42 on
2026-07-28 by Sihan's Feishu CLI.

### Boundary-scan update

Reported TFIM scan:

- configuration: `N=9`, `g=0.5`, `d=2`, `lso=6`;
- `γ=0.25025`, `0.2505`, and `0.25075`: `OPTIMAL`, primal/dual feasible;
- `γ=0.251`: `SLOW_PROGRESS/UNKNOWN`;
- `γ=0.25125`, `0.2515`, `0.25175`, and `0.252`: primal
  `INFEASIBILITY_CERTIFICATE`;
- proposed relaxation transition window: `(0.25075, 0.25125]`, with `0.251`
  retained as unknown.

Reported Kagome scan:

- configuration: `N=13`, `d=3`, `lso=5`;
- `γ=1.262` through `1.270`: `OPTIMAL`, primal/dual feasible;
- `γ=1.272` through `1.278`: `SLOW_PROGRESS` with
  `UNKNOWN_RESULT_STATUS`;
- proposed numerical transition window: `(1.270, 1.272]`;
- correctly **not** promoted to a strict upper bound because no validated
  high-side witness exists.

### Independent-audit update

Reported TFIM result:

- MOF model and ray read by a separate verifier;
- `23,949` variables;
- `2,705` affine equalities;
- four PSD blocks;
- normalized equality residual `2.28e-15`;
- PSD violation `1.68e-21`;
- normalized objective improvement `7.03e-6`;
- result described as a machine-replayable floating-point conic-ray
  certificate, explicitly not a rational/interval formal certificate.

Reported Kagome result:

- same verifier rejected the candidate;
- normalized equality residual `6.62e-11`;
- declared threshold `1e-12`;
- conclusion kept at numerical instability/unknown rather than a strict upper
  bound.

Referenced commits:

- solver/export source: `b1a1cad`;
- independent verifier: `8c6106f`;
- dense boundary scan: `59f4b09`;
- baseline: `c1ae6f7`.

Those commits are not present in the current local repository's refs, so their
code and artifacts could not be inspected during this review.

## Strong point: the Kagome rejection is scientifically responsible

The most reassuring part of the update is that the same audit machinery accepts
the TFIM candidate but rejects the badly scaled Kagome high-side result. This
shows that Sihan is not simply translating every solver
`INFEASIBILITY_CERTIFICATE` or `SLOW_PROGRESS` result into a certificate.

The current Kagome conclusion is appropriate:

> Feasible through `γ=1.270`; high-side results from `γ=1.272` are unknown and
> numerically unstable; no certified physical upper bound follows yet.

This is strictly better than the earlier legacy `flag=0` interpretation.

## Blocking inconsistency: the TFIM metadata does not match its dimensions

The 18:42 message labels the audited TFIM case as:

```text
N=7, g=1, d=3, lso=6, γ=0.25125
```

The immediately preceding scan identifies `γ=0.25125` as part of:

```text
N=9, g=0.5, d=2, lso=6
```

The reported block inventory settles which description matches the current
pinned SpectralGap basis builder.

For `N=9,d=2`, the code gives:

```text
get_basis blocks:      [211, 50]
get_bulkbasis blocks:  [11, 14]
```

These are exactly the block sizes previously reported for the `23,949`
variable, `2,705` equality model.

For `N=7,d=3`, the same static basis formulas give:

```text
get_basis blocks:      [194, 108]
get_bulkbasis blocks:  [66, 26]
```

Therefore the 18:42 model label and model dimensions cannot both describe the
same unmodified SpectralGap instance.

The most likely explanation is a summary typo: the independently audited case
was probably `N=9,g=0.5,d=2,γ=0.25125`. A more serious possibility is that
run metadata from one configuration was attached to another model/ray.

Do not cite or merge the TFIM result until Sihan confirms the exact
configuration from the machine-readable artifact and run metadata.

## Assessment of the TFIM numerical audit

Subject to correcting the metadata mismatch, the reported numerical checks are
promising:

- the equality residual is far below the stated `1e-12` threshold;
- the PSD violation is negligible at floating-point scale;
- the normalized objective direction is positive;
- the verifier reportedly consumes exported MOF model data rather than calling
  the original JuMP/SpectralGap assembly;
- the same verifier rejects the Kagome candidate.

The appropriate terminology is:

> independently machine-replayed floating-point conic-ray witness for the
> exported MOF problem

or:

> numerically audited conic-ray candidate

It should not yet be called:

- a rational certificate;
- an interval certificate;
- a formal proof;
- a formulation-independent proof;
- an unqualified certified physical gap upper bound.

## Questions that must be answered before promotion

### 1. What is the exact TFIM configuration?

Sihan should confirm:

```text
N
g
d
lso
gamma
symmetry mode
Hamiltonian normalization
```

These values should come from the committed run metadata, not a manually
written chat summary.

### 2. What exactly is normalized?

The report uses:

- “normalized equality residual”;
- “PSD violation”;
- “normalized objective improvement.”

The verifier should document the formulas:

```text
row residual normalization
ray normalization
objective normalization
PSD/block scaling
```

An absolute `1e-12` threshold is meaningful only after the scale convention is
unambiguous.

### 3. Is one variable ordering used everywhere?

The verifier must bind:

```text
MOF variable ordering
ray coordinate ordering
affine matrix columns
objective coefficients
PSD-cone coordinate maps
```

It should reject missing blocks, extra blocks, truncated vectors, permuted
coordinates, and incompatible model/ray hashes.

This is particularly relevant because the local worker's first verifier
mistakenly checked three unbound representations. Sihan's MOF verifier should
demonstrate that it avoids the same failure mode.

### 4. Is the model itself bound to the intended physics?

Auditing the exported MOF conic problem proves a property of that exported
problem. It does not independently prove that the model was assembled from the
intended TFIM Hamiltonian, basis, stationarity relations, and symmetry mode.

The evidence bundle should include:

- Hamiltonian support/coefficient hash;
- ordered basis/support manifest hash;
- source and dependency hashes;
- MOF SHA-256;
- ray SHA-256;
- run-metadata SHA-256;
- exact verifier command and output;
- variable/block inventory;
- independent-assembly comparison if available.

### 5. How is the near-boundary PSD result made rigorous?

A violation of approximately `1.68e-21` is excellent numerically, but it still
places at least one block on or extremely near the PSD boundary. A small exact
affine correction could move the matrix outside the cone.

For a strict certificate, retain the stated requirement for rational/interval
post-processing or provide a rigorous correction/projection argument that
preserves:

```text
A*x = 0
x in all PSD cones
c'x > 0
```

## Strategic implication for the local worker

Sihan's MOF-based pipeline appears more mature than maintaining a second
Julia-`Serialization` certificate format locally. The team should avoid
diverging into two incompatible certificate systems.

Recommended coordination:

1. obtain Sihan's `b1a1cad` and `8c6106f` through a visible branch or PR;
2. resolve the TFIM configuration mismatch;
3. compare Sihan's MOF verifier contract with the local one-vector verifier
   requirements;
4. adopt one shared, versioned artifact schema;
5. use the TFIM case only as calibration;
6. after the certificate path is stable, return effort to the actual
   Square/Shastry-Sutherland challenge target.

The Kagome rejection should be preserved as a negative regression test.

## Suggested clarification message to Sihan

The following is a draft only; it has **not** been sent:

```text
收到，Kagome 在同一 verifier 下因 normalized equality residual
6.62e-11 > 1e-12 被明确拒绝，这个结论和 unknown 语义我赞同。

TFIM 这条在引用前请先澄清一个 metadata 冲突：上一条边界扫描是
N=9, g=0.5, d=2, lso=6, gamma=0.25125；最新消息写成
N=7, g=1, d=3。但你报告的 23,949 vars / 2,705 equalities 和
PSD blocks [211,50]/[11,14] 在当前 pinned SpectralGap basis builder
下正好对应 N=9,d=2；N=7,d=3 应是 [194,108]/[66,26]。
请从 machine-readable runmeta/MOF 确认实际 N,g,d,lso,gamma，
避免只是聊天摘要笔误之外还有 model/ray metadata 串线。

另外请把 b1a1cad、8c6106f 和对应 MOF/ray/runmeta 放到可见 branch/PR
或给出完整 artifact SHA。也请说明 normalized residual/objective/PSD
的具体公式与 tolerance，并确认 verifier 强制绑定 MOF variable order、
ray order、objective、affine columns 和全部 PSD cone maps。

在这些确认后，我认为可称：
“independently machine-replayed floating-point conic-ray witness for the
exported MOF problem”；仍保留你写的 caveat：不是 rational/interval
formal certificate。Kagome 暂不形成严格上界。
```

## Bottom line

The update is technically encouraging and much more careful than the earlier
solver-flag claims. The Kagome rejection is reliable in spirit, and the TFIM
audit may be a valuable independent floating-point witness.

The TFIM configuration mismatch is currently blocking. Resolve that mismatch
and inspect the referenced commits/artifacts before treating the message as
verified evidence.
