# Anticommuting D4 Certificate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Pauli-l1 bound on the local degree-four right-generator defect with an exact-rational pairwise-anticommuting partition certificate, certify 98 Trotter steps, and update PR #248 to a resource improvement above 4x.

**Architecture:** The existing interval Lie-series code will expose a canonical `2x2`-unit-cell D4 coefficient map. A deterministic optimizer will partition those Pauli terms into pairwise-anticommuting groups, while a separate proof function and verifier check coverage, symplectic anticommutation, and outward rational Euclidean bounds. A compact sidecar stores the large proof object; the main schema-v3 certificate binds it by SHA-256 and uses only the grouped D4 bound while retaining the existing D5-D7 and tail bounds.

**Tech Stack:** Python 3.12, `Fraction`, existing `RationalInterval`, exact binary symplectic Pauli arithmetic, JSON, SHA-256, pytest.

## Global Constraints

- Benchmark remains the periodic `12x12` isotropic spin-1/2 Heisenberg Hamiltonian with `h_ij=(XX+YY+ZZ)/4`, `T=1`, and operator-norm tolerance `1e-6`.
- Formula remains the 31-stage five-copy fourth-order Suzuki formula over the same four disjoint bond matchings.
- Cost remains `30*r+1` merged group exponentials, `N/2` bond propagators per group, and three CNOTs per bond propagator.
- The proof path uses exact integers, rational arithmetic, rational intervals, and outward rounding; floating point may choose a partition but may not establish an inequality.
- The previous 116-step certificate remains reproducible until the new 98-step certificate passes fast verification, deep regeneration, solution tests, repository tests, and the dense small-size cross-check.
- All committed files stay under `tracks/qcs/solutions/WangTheoPhys/`.

---

## File Structure

- Modify `src/trottercert/refined_error.py`: construct canonical interval D4 coefficients and accept a grouped D4 site bound.
- Create `src/trottercert/anticommuting.py`: deterministic partition discovery and exact partition certification.
- Modify `src/trottercert/verify.py`: verify the D4 sidecar in fast mode and regenerate it in deep mode.
- Modify `scripts/build_v3_certificate.py`: build the grouped proof, write the compact sidecar, bind its hash, and search the new integer boundary.
- Modify `src/trottercert/crosscheck.py`: update the outward summary and dense check to the certified step count.
- Create `certificates/issue128-d4-groups.json`: compact exact proof object.
- Modify `certificates/issue128-certificate.json`: schema-v3 candidate fields and 98-step resources.
- Modify `certificates/issue128-small-crosscheck.json`: dense check at 98 steps.
- Modify `certificates/issue128-verification.txt`: deep-verification transcript and resource ledger.
- Modify `README.md`: explain the D4 theorem and report the new count.
- Modify `tests/test_refined_error.py`, `tests/test_resources_verify.py`, and `tests/test_small_crosscheck.py`.
- Create `tests/test_anticommuting.py`.

---

### Task 1: Canonical exact D4 coefficient map

**Files:**
- Modify: `src/trottercert/refined_error.py`
- Test: `tests/test_refined_error.py`

**Interfaces:**
- Produces: `certified_d4_cell_coefficients(stages: Sequence[IntervalStage], *, quantization_digits: int = 18) -> dict[SymplecticPauli, RationalInterval]`.
- Preserves: `certified_leading_e5_cell_l1(stages: Sequence[IntervalStage], *, quantization_digits: int = 24) -> Fraction` and its current ungrouped bound for repeated-adjoint estimates.

- [ ] **Step 1: Write a failing canonicalization test**

Add a test that constructs two translated symplectic Pauli terms in one shared `CoordinateRegistry`, canonicalizes them with the colored unit cell, and requires identical output:

```python
def test_colored_unit_cell_canonicalization_merges_translates() -> None:
    registry = CoordinateRegistry()
    left = symplectic_pauli_from_coordinates(
        registry, ((0, 0, "X"), (1, 0, "X"))
    )
    right = symplectic_pauli_from_coordinates(
        registry, ((2, 0, "X"), (3, 0, "X"))
    )
    assert canonicalize_symplectic_unit_cell(registry, left) == (
        canonicalize_symplectic_unit_cell(registry, right)
    )
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```bash
pytest -q tests/test_refined_error.py::test_colored_unit_cell_canonicalization_merges_translates
```

Expected: import failure because `canonicalize_symplectic_unit_cell` and `symplectic_pauli_from_coordinates` do not exist.

- [ ] **Step 3: Implement exact symplectic translation canonicalization**

Add these signatures to `refined_error.py`:

```python
def symplectic_pauli_from_coordinates(
    registry: CoordinateRegistry,
    coordinates: Sequence[tuple[int, int, str]],
) -> SymplecticPauli:
    x_mask = z_mask = 0
    for x, y, op in coordinates:
        bit = 1 << registry.site((x, y))
        if op in {"X", "Y"}:
            x_mask |= bit
        if op in {"Z", "Y"}:
            z_mask |= bit
    return x_mask, z_mask


def canonicalize_symplectic_unit_cell(
    registry: CoordinateRegistry,
    pauli: SymplecticPauli,
    unit_cell: tuple[int, int] = (2, 2),
) -> SymplecticPauli:
    x_mask, z_mask = pauli
    sites = x_mask | z_mask
    coordinates = []
    while sites:
        bit = sites & -sites
        site = bit.bit_length() - 1
        x = bool(x_mask & bit)
        z = bool(z_mask & bit)
        op = "Y" if x and z else ("X" if x else "Z")
        cx, cy = registry.coordinate(site)
        coordinates.append((cx, cy, op))
        sites ^= bit
    if not coordinates:
        return 0, 0
    step_x, step_y = unit_cell
    min_x = min(x for x, _, _ in coordinates)
    min_y = min(y for _, y, _ in coordinates)
    shift_x = -(min_x - min_x % step_x)
    shift_y = -(min_y - min_y % step_y)
    return symplectic_pauli_from_coordinates(
        registry,
        tuple(
            (x + shift_x, y + shift_y, op)
            for x, y, op in coordinates
        ),
    )
```

Decode all occupied bit positions through `registry.coordinate(site)`, shift
the minimum coordinates to their residues modulo `(2,2)`, and rebuild the
masks through `registry.site(...)`. Empty Paulis remain `(0, 0)`.

- [ ] **Step 4: Refactor the E5 interval accumulator into a reusable map**

Add:

```python
def _leading_e5_cell_interval_coefficients(
    stages: Sequence[IntervalStage],
    *,
    quantization_digits: int,
    canonicalize: bool,
) -> dict[SymplecticPauli, RationalInterval]:
    logarithm = interval_formula_log_series(stages, 5)
    grid = 10**quantization_digits
    evaluator = SymplecticDyadicLocalDensityEvaluator(
        shared_coordinates=True
    )
    registry = evaluator.registries[0]
    integer_coefficients: dict[SymplecticPauli, tuple[int, int]] = {}
    for word, coefficient in logarithm[5].items():
        rounded = outward_quantize(coefficient, grid)
        word_lower = rounded.lower.numerator * (
            grid // rounded.lower.denominator
        )
        word_upper = rounded.upper.numerator * (
            grid // rounded.upper.denominator
        )
        for raw_pauli, numerator in evaluator.evaluate(word).items():
            pauli = (
                canonicalize_symplectic_unit_cell(registry, raw_pauli)
                if canonicalize
                else raw_pauli
            )
            lower, upper = integer_coefficients.get(pauli, (0, 0))
            if numerator >= 0:
                lower += numerator * word_lower
                upper += numerator * word_upper
            else:
                lower += numerator * word_upper
                upper += numerator * word_lower
            if lower or upper:
                integer_coefficients[pauli] = lower, upper
            else:
                integer_coefficients.pop(pauli, None)
    denominator = grid * 5 * (1 << 6)
    return {
        pauli: RationalInterval(
            Fraction(lower, denominator),
            Fraction(upper, denominator),
        )
        for pauli, (lower, upper) in integer_coefficients.items()
    }
```

Reuse the existing word-endpoint loop. Accumulate integer lower and upper
numerators, optionally canonicalizing each evaluated Pauli before merging,
then divide by the common denominator
`grid * 5 * (1 << 6)`.

Implement:

```python
def certified_d4_cell_coefficients(
    stages: Sequence[IntervalStage],
    *,
    quantization_digits: int = 18,
) -> dict[SymplecticPauli, RationalInterval]:
    return {
        pauli: coefficient * 5
        for pauli, coefficient in _leading_e5_cell_interval_coefficients(
            stages,
            quantization_digits=quantization_digits,
            canonicalize=True,
        ).items()
    }
```

Keep `certified_leading_e5_cell_l1` defined as the sum of absolute upper
endpoints from the noncanonical map so D5-D7 retain the prior proof.

- [ ] **Step 5: Add exact regression assertions**

Extend the slow refined-error test:

```python
coefficients = certified_d4_cell_coefficients(stages)
assert coefficients
assert all(interval.lower <= interval.upper for interval in coefficients.values())
assert sum(
    interval.abs_upper() for interval in coefficients.values()
) <= 5 * certified_leading_e5_cell_l1(stages)
```

- [ ] **Step 6: Run the refined-error tests**

Run:

```bash
pytest -q tests/test_refined_error.py
```

Expected: all unmarked tests pass; slow regeneration remains deselected by the project configuration.

- [ ] **Step 7: Commit Task 1**

```bash
git add tracks/qcs/solutions/WangTheoPhys/issue128/src/trottercert/refined_error.py \
        tracks/qcs/solutions/WangTheoPhys/issue128/tests/test_refined_error.py
git commit -m "expose canonical interval D4 coefficients"
```

---

### Task 2: Deterministic anticommuting partition and exact proof

**Files:**
- Create: `src/trottercert/anticommuting.py`
- Create: `tests/test_anticommuting.py`

**Interfaces:**
- Consumes: the `dict[SymplecticPauli, RationalInterval]` from Task 1.
- Produces: `AnticommutingPartitionCertificate`, `discover_anticommuting_partition(...)`, and `certify_anticommuting_partition(...)`.

- [ ] **Step 1: Write failing proof tests**

Create `tests/test_anticommuting.py` with:

```python
from fractions import Fraction

import pytest

from trottercert.anticommuting import (
    certify_anticommuting_partition,
    discover_anticommuting_partition,
    symplectic_anticommutes,
)
from trottercert.intervals import RationalInterval


def test_symplectic_anticommutation() -> None:
    x = (1, 0)
    y = (1, 1)
    z = (0, 1)
    assert symplectic_anticommutes(x, y)
    assert symplectic_anticommutes(y, z)
    assert symplectic_anticommutes(z, x)


def test_exact_group_bound_uses_euclidean_norm() -> None:
    coefficients = {
        (1, 0): RationalInterval.point(1),
        (1, 1): RationalInterval.point(2),
        (0, 1): RationalInterval.point(2),
    }
    certificate = certify_anticommuting_partition(
        coefficients, (((1, 0), (1, 1), (0, 1)),)
    )
    assert certificate.bound == 3


def test_corrupt_commuting_group_is_rejected() -> None:
    coefficients = {
        (1, 0): RationalInterval.point(1),
        (2, 0): RationalInterval.point(1),
    }
    with pytest.raises(ValueError, match="does not anticommute"):
        certify_anticommuting_partition(
            coefficients, (((1, 0), (2, 0)),)
        )
```

- [ ] **Step 2: Run the tests and verify import failure**

Run:

```bash
pytest -q tests/test_anticommuting.py
```

Expected: collection fails because `trottercert.anticommuting` does not exist.

- [ ] **Step 3: Implement proof dataclasses and exact helpers**

Create:

```python
@dataclass(frozen=True)
class AnticommutingGroupCertificate:
    term_indices: tuple[int, ...]
    bound: Fraction


@dataclass(frozen=True)
class AnticommutingPartitionCertificate:
    paulis: tuple[SymplecticPauli, ...]
    coefficients: tuple[RationalInterval, ...]
    groups: tuple[AnticommutingGroupCertificate, ...]
    bound: Fraction
```

Implement `symplectic_anticommutes(left, right)` with the exact binary
symplectic parity expression. Implement an outward rational square-root
helper using `isqrt`, defaulting to 30 decimal digits and checking
`upper * upper >= value`.

- [ ] **Step 4: Implement the deterministic discovery heuristic**

Use:

```python
def discover_anticommuting_partition(
    coefficients: Mapping[SymplecticPauli, RationalInterval],
    *,
    max_group_size: int = 10,
) -> tuple[tuple[SymplecticPauli, ...], ...]:
    if max_group_size < 1:
        raise ValueError("maximum group size must be positive")
    ordered = tuple(
        sorted(
            coefficients,
            key=lambda pauli: (
                -float(coefficients[pauli].abs_upper()),
                pauli,
            ),
        )
    )
    used: set[SymplecticPauli] = set()
    groups: list[tuple[SymplecticPauli, ...]] = []
    for position, pauli in enumerate(ordered):
        if pauli in used:
            continue
        group = [pauli]
        used.add(pauli)
        for candidate in ordered[position + 1:]:
            if candidate in used:
                continue
            if all(
                symplectic_anticommutes(candidate, member)
                for member in group
            ):
                group.append(candidate)
                used.add(candidate)
                if len(group) == max_group_size:
                    break
        groups.append(tuple(group))
    return tuple(groups)
```

Sort by `(-float(interval.abs_upper()), pauli)`. For every largest unused
Pauli, scan the remaining order and add a candidate exactly when it
anticommutes with every group member. Stop at `max_group_size`; preserve
singletons.

- [ ] **Step 5: Implement independent exact certification**

Use:

```python
def certify_anticommuting_partition(
    coefficients: Mapping[SymplecticPauli, RationalInterval],
    groups: Sequence[Sequence[SymplecticPauli]],
    *,
    sqrt_decimal_places: int = 30,
) -> AnticommutingPartitionCertificate:
    paulis = tuple(sorted(coefficients))
    index = {pauli: offset for offset, pauli in enumerate(paulis)}
    flattened = tuple(pauli for group in groups for pauli in group)
    if len(flattened) != len(set(flattened)):
        raise ValueError("partition coverage contains duplicate terms")
    if set(flattened) != set(paulis):
        raise ValueError("partition coverage differs from coefficient map")
    certified_groups = []
    for group in groups:
        if not group:
            raise ValueError("anticommuting group must be nonempty")
        for left_position, left in enumerate(group):
            for right in group[left_position + 1:]:
                if not symplectic_anticommutes(left, right):
                    raise ValueError("group members do not anticommute")
        squared = sum(
            (
                coefficients[pauli].abs_upper() ** 2
                for pauli in group
            ),
            Fraction(),
        )
        bound = sqrt_fraction_upper(
            squared, decimal_places=sqrt_decimal_places
        )
        certified_groups.append(
            AnticommutingGroupCertificate(
                tuple(index[pauli] for pauli in group),
                bound,
            )
        )
    return AnticommutingPartitionCertificate(
        paulis,
        tuple(coefficients[pauli] for pauli in paulis),
        tuple(certified_groups),
        sum((group.bound for group in certified_groups), Fraction()),
    )
```

Require exact set equality between coefficient keys and flattened groups,
reject duplicates, check every within-group pair, compute each squared
absolute upper sum, round its square root upward, and sum group bounds.

- [ ] **Step 6: Add deterministic and coverage tests**

Add:

```python
def test_discovery_is_deterministic_and_covers_terms() -> None:
    coefficients = {
        (1, 0): RationalInterval.point(3),
        (1, 1): RationalInterval.point(2),
        (0, 1): RationalInterval.point(1),
    }
    first = discover_anticommuting_partition(coefficients, max_group_size=3)
    second = discover_anticommuting_partition(coefficients, max_group_size=3)
    assert first == second
    certificate = certify_anticommuting_partition(coefficients, first)
    assert set(certificate.paulis) == set(coefficients)
```

- [ ] **Step 7: Run and commit Task 2**

Run:

```bash
pytest -q tests/test_anticommuting.py
```

Then:

```bash
git add tracks/qcs/solutions/WangTheoPhys/issue128/src/trottercert/anticommuting.py \
        tracks/qcs/solutions/WangTheoPhys/issue128/tests/test_anticommuting.py
git commit -m "certify anticommuting Pauli partitions"
```

---

### Task 3: Integrate the grouped D4 bound into resource evaluation

**Files:**
- Modify: `src/trottercert/refined_error.py`
- Modify: `tests/test_refined_error.py`

**Interfaces:**
- Consumes: `AnticommutingPartitionCertificate.bound`, a per-cell bound.
- Produces: optional `d4_site_override` in `evaluate_refined_fourth_order_bound`.

- [ ] **Step 1: Write the failing override test**

Add:

```python
def test_d4_override_changes_only_degree_four() -> None:
    constants = build_refined_fourth_order_constants()
    original = evaluate_refined_fourth_order_bound(constants, 144, 116)
    grouped = evaluate_refined_fourth_order_bound(
        constants,
        144,
        116,
        d4_site_override=constants.d4_site / 2,
    )
    assert grouped.degree_four_contribution == (
        original.degree_four_contribution / 2
    )
    assert grouped.degree_five_contribution == original.degree_five_contribution
    assert grouped.degree_six_contribution == original.degree_six_contribution
    assert grouped.degree_seven_contribution == original.degree_seven_contribution
    assert grouped.tail_contribution == original.tail_contribution
```

- [ ] **Step 2: Verify failure**

Run:

```bash
pytest -q tests/test_refined_error.py::test_d4_override_changes_only_degree_four
```

Expected: `TypeError` for unexpected keyword `d4_site_override`.

- [ ] **Step 3: Implement the optional bound**

Change the signature to:

```python
def evaluate_refined_fourth_order_bound(
    constants: RefinedFourthOrderConstants,
    n_sites: int,
    steps: int,
    *,
    d4_site_override: Fraction | None = None,
) -> RefinedFourthOrderBound:
```

Use `constants.d4_site` when the override is `None`. Reject a negative
override and reject an override larger than the original Pauli-l1 bound so
the grouped path cannot accidentally weaken the certificate.

- [ ] **Step 4: Add the 98/97 discovery regression**

Mark the expensive test slow. It regenerates coefficients, discovers and
certifies groups of size ten, evaluates steps 98 and 97, and asserts:

```python
assert at_98.global_error_bound <= Fraction(1, 10**6)
assert at_97.global_error_bound > Fraction(1, 10**6)
assert certificate.bound < 4 * constants.d4_site
```

The last line compares the per-cell grouped D4 bound with the original
per-cell Pauli-l1 value.

- [ ] **Step 5: Run focused tests and commit Task 3**

Run:

```bash
pytest -q tests/test_refined_error.py
pytest -q -m slow tests/test_refined_error.py::test_grouped_d4_crosses_fourfold_target
```

Commit:

```bash
git add tracks/qcs/solutions/WangTheoPhys/issue128/src/trottercert/refined_error.py \
        tracks/qcs/solutions/WangTheoPhys/issue128/tests/test_refined_error.py
git commit -m "apply grouped D4 norm to refined bound"
```

---

### Task 4: Serialize and independently verify the large D4 proof

**Files:**
- Modify: `src/trottercert/verify.py`
- Modify: `tests/test_resources_verify.py`
- Modify: `scripts/build_v3_certificate.py`
- Create: `certificates/issue128-d4-groups.json`

**Interfaces:**
- Produces sidecar schema:

```json
{
  "schema_version": 1,
  "coefficient_denominator": 1,
  "terms": [[0, 0, 0, 0]],
  "sqrt_denominator": 1,
  "groups": [[[0], 0]],
  "cell_bound": [0, 1]
}
```

The real file uses a common exact coefficient denominator; each term is
`[x_mask, z_mask, lower_numerator, upper_numerator]`, and each group is
`[term_indices, bound_numerator]`.

- [ ] **Step 1: Add failing fast-verifier corruption tests**

Extend `test_resources_verify.py` to copy both certificate files to a
temporary directory and corrupt, one at a time:

1. a repeated term index;
2. a within-group Pauli mask so the pair commutes;
3. a group-bound numerator reduced by one;
4. the sidecar hash in the main certificate.

Each mutation must raise a `ValueError` containing a distinct stable phrase:
`coverage`, `anticommute`, `group bound`, or `sidecar digest`.

- [ ] **Step 2: Add sidecar serialization to the builder**

Add helper functions:

```python
def d4_sidecar_payload(
    certificate: AnticommutingPartitionCertificate,
) -> dict[str, object]:
    coefficient_denominator = lcm(
        *(
            denominator
            for interval in certificate.coefficients
            for denominator in (
                interval.lower.denominator,
                interval.upper.denominator,
            )
        )
    )
    sqrt_denominator = lcm(
        *(group.bound.denominator for group in certificate.groups)
    )
    return {
        "schema_version": 1,
        "coefficient_denominator": coefficient_denominator,
        "terms": [
            [
                pauli[0],
                pauli[1],
                interval.lower.numerator
                * (coefficient_denominator // interval.lower.denominator),
                interval.upper.numerator
                * (coefficient_denominator // interval.upper.denominator),
            ]
            for pauli, interval in zip(
                certificate.paulis, certificate.coefficients
            )
        ],
        "sqrt_denominator": sqrt_denominator,
        "groups": [
            [
                list(group.term_indices),
                group.bound.numerator
                * (sqrt_denominator // group.bound.denominator),
            ]
            for group in certificate.groups
        ],
        "cell_bound": pair(certificate.bound),
    }


def canonical_json_bytes(payload: dict[str, object]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
```

Write `issue128-d4-groups.json` from canonical bytes and store in the main
certificate:

```python
"d4_certificate": {
    "path": "issue128-d4-groups.json",
    "sha256": hashlib.sha256(sidecar_bytes).hexdigest(),
    "max_group_size": 10,
    "cell_norm_upper": pair(partition.bound),
}
```

Search the minimum step count with
`d4_site_override=partition.bound / 4`.

- [ ] **Step 3: Implement the fast sidecar verifier**

Add:

```python
def _verify_d4_sidecar(
    certificate_path: Path,
    candidate: dict[str, object],
) -> Fraction:
    metadata = candidate["d4_certificate"]
    root = certificate_path.resolve().parent
    sidecar_path = (root / str(metadata["path"])).resolve()
    if sidecar_path.parent != root:
        raise ValueError("D4 sidecar path escapes certificate directory")
    raw = sidecar_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
        raise ValueError("D4 sidecar digest mismatch")
    payload = json.loads(raw)
    coefficient_denominator = int(payload["coefficient_denominator"])
    rows = payload["terms"]
    paulis = tuple((int(row[0]), int(row[1])) for row in rows)
    if len(paulis) != len(set(paulis)):
        raise ValueError("D4 sidecar coefficient terms are duplicated")
    coefficients = {
        pauli: RationalInterval(
            Fraction(int(row[2]), coefficient_denominator),
            Fraction(int(row[3]), coefficient_denominator),
        )
        for pauli, row in zip(paulis, rows)
    }
    submitted_groups = payload["groups"]
    groups = tuple(
        tuple(paulis[int(index)] for index in row[0])
        for row in submitted_groups
    )
    regenerated = certify_anticommuting_partition(coefficients, groups)
    sqrt_denominator = int(payload["sqrt_denominator"])
    submitted_bounds = tuple(
        Fraction(int(row[1]), sqrt_denominator)
        for row in submitted_groups
    )
    regenerated_bounds = tuple(
        group.bound for group in regenerated.groups
    )
    if submitted_bounds != regenerated_bounds:
        raise ValueError("D4 group bound mismatch")
    cell_bound = _fraction(payload["cell_bound"])
    if cell_bound != regenerated.bound:
        raise ValueError("D4 cell bound mismatch")
    if cell_bound != _fraction(metadata["cell_norm_upper"]):
        raise ValueError("D4 main-certificate bound mismatch")
    return cell_bound / 4
```

Resolve the sidecar relative to the main certificate, reject path traversal,
verify SHA-256, parse integer masks and common denominators, check exact
coverage and every pair, verify every squared rational bound, and require the
sum to equal `cell_bound`. Return the per-site value `cell_bound / 4`.

- [ ] **Step 4: Wire fast and deep modes**

Fast mode passes the returned site bound into
`evaluate_refined_fourth_order_bound`. Deep mode regenerates
`certified_d4_cell_coefficients`, reconstructs the ordered term table,
requires exact equality with the sidecar, and then invokes the same fast
proof checks.

- [ ] **Step 5: Run corruption and fast-verification tests**

Run:

```bash
pytest -q tests/test_resources_verify.py
PYTHONPATH=src python scripts/build_v3_certificate.py
PYTHONPATH=src python scripts/verify.py \
  certificates/issue128-certificate.json
```

Expected certificate summary:

```text
candidate_steps: 98
candidate_group_exponentials: 2941
global_twofold_target_met: true
improvement: greater than 4
```

- [ ] **Step 6: Commit Task 4**

```bash
git add tracks/qcs/solutions/WangTheoPhys/issue128/src/trottercert/verify.py \
        tracks/qcs/solutions/WangTheoPhys/issue128/tests/test_resources_verify.py \
        tracks/qcs/solutions/WangTheoPhys/issue128/scripts/build_v3_certificate.py \
        tracks/qcs/solutions/WangTheoPhys/issue128/certificates/issue128-d4-groups.json \
        tracks/qcs/solutions/WangTheoPhys/issue128/certificates/issue128-certificate.json
git commit -m "add machine-checkable grouped D4 certificate"
```

---

### Task 5: Rebuild cross-checks, transcripts, and documentation

**Files:**
- Modify: `src/trottercert/crosscheck.py`
- Modify: `tests/test_small_crosscheck.py`
- Modify: `certificates/issue128-small-crosscheck.json`
- Modify: `certificates/issue128-verification.txt`
- Modify: `README.md`

**Interfaces:**
- Consumes: the verified candidate step, error ledger, and exact resources.
- Produces: reproducible human-readable and dense-check artifacts.

- [ ] **Step 1: Update the dense-check regression**

Change `REFINED_STEPS` to the certificate step count and replace the
outward-rounded N=144 summary with the smallest decimal rational above the
exact grouped certificate total. Keep the N=4 scaling and assertions:

```python
assert result["bound_dominates_empirical_error"]
assert result["bound_meets_tolerance"]
assert result["steps"] == 98
```

- [ ] **Step 2: Regenerate the dense artifact**

Run:

```bash
PYTHONPATH=src python scripts/crosscheck_small.py \
  --length 2 --tolerance 1000000
```

Copy the emitted values exactly into
`certificates/issue128-small-crosscheck.json`.

- [ ] **Step 3: Run deep verification and capture the exact ledger**

Run:

```bash
PYTHONPATH=src python scripts/verify.py \
  certificates/issue128-certificate.json --deep
```

Update `issue128-verification.txt` with the emitted candidate error,
previous-step error, D4 grouped bound, steps, group count, bond count, CNOT
count, and exact improvement ratio.

- [ ] **Step 4: Update README claims**

Document:

- the pairwise-anticommuting theorem;
- the fact that partition discovery is untrusted and proof checking is exact;
- the 98/97 integer boundary;
- `2941` candidate groups;
- `2941 * 72` bond propagators;
- three times that number for CNOTs;
- exact `11791/2941` improvement;
- updated test and deep-verification results.

- [ ] **Step 5: Commit Task 5**

```bash
git add tracks/qcs/solutions/WangTheoPhys/README.md \
        tracks/qcs/solutions/WangTheoPhys/issue128/src/trottercert/crosscheck.py \
        tracks/qcs/solutions/WangTheoPhys/issue128/tests/test_small_crosscheck.py \
        tracks/qcs/solutions/WangTheoPhys/issue128/certificates/issue128-small-crosscheck.json \
        tracks/qcs/solutions/WangTheoPhys/issue128/certificates/issue128-verification.txt
git commit -m "document fourfold certified resource reduction"
```

---

### Task 6: Full verification and PR update

**Files:**
- Modify only if verification exposes an in-scope defect in files listed above.

**Interfaces:**
- Produces: a clean pushed branch and updated PR #248.

- [ ] **Step 1: Run the solution test suite**

```bash
cd tracks/qcs/solutions/WangTheoPhys/issue128
pytest -q
```

Expected: all default tests pass.

- [ ] **Step 2: Run the deep proof regeneration**

```bash
PYTHONPATH=src python scripts/verify.py \
  certificates/issue128-certificate.json --deep
```

Expected: `"valid": true`, `"verification_level": "deep"`,
`"deep_proof_regenerated": true`, candidate steps 98, and improvement above
four.

- [ ] **Step 3: Run repository tests with the dependency-complete interpreter**

From the repository root:

```bash
python3.12 -m pytest scripts/tests/ -q \
  --cov=cluster_profile --cov=cluster_guardrail --cov=cluster_probe \
  --cov=parameter_scan --cov=scaling_fit \
  --cov-report=term-missing
```

Expected: 223 repository tests pass and measured coverage remains at least
95%.

- [ ] **Step 4: Audit scope and formatting**

```bash
git diff --check myfork/codex/issue-128-trotter-certificate...HEAD
git diff --name-only myfork/codex/issue-128-trotter-certificate...HEAD |
  awk '!/^tracks\\/qcs\\/solutions\\/WangTheoPhys\\// {print}'
git status --short
```

Expected: no whitespace errors, no out-of-scope paths, and no uncommitted
changes.

- [ ] **Step 5: Push the tested head to the PR branch**

```bash
git push myfork HEAD:codex/issue-128-trotter-certificate
```

- [ ] **Step 6: Update and inspect PR #248**

Set the title to the exact verified decimal rounded to three places:

```bash
gh pr edit 248 --repo QuantumBFS/quantum.harness \
  --title "[qcs] 🔭 WangTheoPhys: certify a 4.009× tighter Trotter resource bound" \
  --body-file /tmp/issue128-pr-body.md
gh pr view 248 --repo QuantumBFS/quantum.harness \
  --json url,title,state,isDraft,headRefName,statusCheckRollup
```

The body must report only values copied from the verified certificate and
must retain the team name and member information already present in the
submission.

---

## Self-Review

- Spec coverage: Tasks 1-3 establish the mathematical bound; Task 4 makes it
  independently machine-checkable; Task 5 updates every derived artifact;
  Task 6 verifies and submits it.
- Trusted-computing-base boundary: discovery floats select groups only;
  exact interval coefficients, anticommutation, square roots, coverage,
  arithmetic, and hashing are rechecked.
- Type consistency: the coefficient map uses
  `dict[SymplecticPauli, RationalInterval]`; discovery consumes that exact
  type; certification returns `AnticommutingPartitionCertificate`; resource
  evaluation consumes its `Fraction` cell bound divided by four.
- Scope consistency: all committed paths remain beneath the allowed
  `WangTheoPhys` solution directory.
