# Challenge 194 Day-0 Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, independently validated finite-ring kernel,
union-find graph representation, exact small-system oracle, and accelerated
geometric-skipping sampler for the pinned `q=1` long-range percolation model.

**Architecture:** A small Python package separates model validation, kernel
evaluation, graph connectivity, independent quadratic sampling, exact graph
enumeration, and accelerated distance-class sampling. The accelerated sampler
is accepted only through deterministic identities and distribution-level
comparison with the independent oracle; no critical fitting or production
cluster run is included in this plan.

**Tech Stack:** CPython 3.12, NumPy 2.2.6, SciPy 1.15.3, h5py 3.14.0,
pytest, uv.

## Global constraints

- Work only under
  `tracks/qmc/solutions/frustration-free/challenge-194/`.
- The pinned model is
  `p_ij = 1 - exp[-kappa J_L,sigma(i-j)]` with the full periodic image sum.
- `L` is an even integer at least two, `sigma > 0`, and `kappa >= 0`.
- Every unordered edge appears once; the antipodal class has `L/2` edges.
- No cutoff, Kac normalization, independent nearest-neighbor parameter, or
  minimum-image substitution is allowed.
- The quadratic oracle and accelerated sampler must not share edge-selection
  logic beyond immutable model/kernel inputs.
- Use `numpy.random.Generator` only for Day-0 statistical validation. The
  counter-based production RNG belongs to the later production-sampler plan.
- All tests are written and observed failing before implementation.
- No generated data, virtual environment, cache, or external code is committed.
- Every commit names only files owned by its task; never use `git add .`.

---

## File map

- `pyproject.toml` — isolated Python 3.12 environment and pytest settings.
- `src/long_range_percolation/__init__.py` — public Day-0 API.
- `src/long_range_percolation/model.py` — immutable model specification,
  distance classes, and canonical edges.
- `src/long_range_percolation/kernel.py` — production and high-precision
  reference periodic kernels.
- `src/long_range_percolation/union_find.py` — deterministic disjoint-set
  implementation and component summaries.
- `src/long_range_percolation/oracle.py` — independent `O(L^2)` Bernoulli
  sampler.
- `src/long_range_percolation/enumeration.py` — exact graph probabilities for
  `L <= 6`.
- `src/long_range_percolation/geometric.py` — distance-class geometric-skipping
  sampler.
- `src/long_range_percolation/validation.py` — analytic and statistical
  validation report.
- `scripts/validate_day0.py` — one-command Day-0 acceptance CLI.
- `tests/test_model.py` — class cardinality and edge canonicalization.
- `tests/test_kernel.py` — image sums, analytic identities, and global sums.
- `tests/test_union_find.py` — deterministic partition behavior.
- `tests/test_oracle.py` — oracle limits and edge probabilities.
- `tests/test_enumeration.py` — exact product-measure distributions.
- `tests/test_geometric.py` — accelerated sampler limits and independence.
- `tests/test_validation.py` — acceptance report and fail-closed behavior.
- `README.md` — setup, validation command, scope, and non-claims.

---

### Task 1: Package boundary and pinned model

**Files:**
- Create: `pyproject.toml`
- Create: `src/long_range_percolation/__init__.py`
- Create: `src/long_range_percolation/model.py`
- Create: `tests/test_model.py`

**Interfaces:**
- Produces:
  - `ModelSpec(length: int, sigma: float, kappa: float)`
  - `distance_classes(length: int) -> tuple[DistanceClass, ...]`
  - `canonical_edge(length: int, distance: int, offset: int) -> tuple[int, int]`
  - `iter_unordered_edges(length: int) -> Iterator[tuple[int, int]]`
- `DistanceClass` fields are `distance: int` and `multiplicity: int`.

- [ ] **Step 1: Write the package metadata**

```toml
[project]
name = "challenge-194-long-range-percolation"
version = "0.1.0"
requires-python = "==3.12.*"
dependencies = [
  "h5py==3.14.0",
  "numpy==2.2.6",
  "scipy==1.15.3",
]

[dependency-groups]
dev = ["pytest>=8.3,<9"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/long_range_percolation"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

- [ ] **Step 2: Write failing model tests**

```python
import pytest

from long_range_percolation.model import (
    ModelSpec,
    canonical_edge,
    distance_classes,
    iter_unordered_edges,
)


def test_model_spec_rejects_non_even_or_nonphysical_parameters():
    for values in [
        {"length": 3, "sigma": 1.0, "kappa": 1.0},
        {"length": 2, "sigma": 0.0, "kappa": 1.0},
        {"length": 2, "sigma": 1.0, "kappa": -1.0},
        {"length": 2, "sigma": float("nan"), "kappa": 1.0},
        {"length": 2, "sigma": 1.0, "kappa": float("inf")},
    ]:
        with pytest.raises(ValueError):
            ModelSpec(**values)


def test_distance_classes_count_every_unordered_edge_once():
    for length in (2, 4, 6, 32):
        classes = distance_classes(length)
        assert sum(item.multiplicity for item in classes) == length * (length - 1) // 2
        assert classes[-1].distance == length // 2
        assert classes[-1].multiplicity == length // 2


def test_canonical_edges_match_direct_unordered_enumeration():
    length = 8
    from_classes = {
        canonical_edge(length, item.distance, offset)
        for item in distance_classes(length)
        for offset in range(item.multiplicity)
    }
    assert from_classes == set(iter_unordered_edges(length))
    assert len(from_classes) == length * (length - 1) // 2
```

- [ ] **Step 3: Run tests and observe the missing-module failure**

Run:

```bash
uv sync --project . --python 3.12
uv run --project . pytest tests/test_model.py -q
```

Expected: collection fails because `long_range_percolation.model` does not
exist.

- [ ] **Step 4: Implement the immutable model and canonical edge map**

```python
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterator


def _strict_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


@dataclass(frozen=True)
class ModelSpec:
    length: int
    sigma: float
    kappa: float

    def __post_init__(self) -> None:
        length = _strict_int(self.length, "length")
        if length < 2 or length % 2:
            raise ValueError("length must be even and at least two")
        if (
            isinstance(self.sigma, bool)
            or not isinstance(self.sigma, (int, float))
            or not math.isfinite(float(self.sigma))
            or float(self.sigma) <= 0.0
        ):
            raise ValueError("sigma must be finite and positive")
        if (
            isinstance(self.kappa, bool)
            or not isinstance(self.kappa, (int, float))
            or not math.isfinite(float(self.kappa))
            or float(self.kappa) < 0.0
        ):
            raise ValueError("kappa must be finite and nonnegative")


@dataclass(frozen=True)
class DistanceClass:
    distance: int
    multiplicity: int


def distance_classes(length: int) -> tuple[DistanceClass, ...]:
    length = _strict_int(length, "length")
    if length < 2 or length % 2:
        raise ValueError("length must be even and at least two")
    return tuple(
        DistanceClass(
            distance=distance,
            multiplicity=length if distance < length // 2 else length // 2,
        )
        for distance in range(1, length // 2 + 1)
    )


def canonical_edge(length: int, distance: int, offset: int) -> tuple[int, int]:
    matching = {item.distance: item for item in distance_classes(length)}
    if distance not in matching:
        raise ValueError("distance is outside the canonical range")
    if isinstance(offset, bool) or not isinstance(offset, int):
        raise ValueError("offset must be an integer")
    if not 0 <= offset < matching[distance].multiplicity:
        raise ValueError("offset is outside the distance class")
    left = offset
    right = (offset + distance) % length
    return (left, right) if left < right else (right, left)


def iter_unordered_edges(length: int) -> Iterator[tuple[int, int]]:
    distance_classes(length)
    for left in range(length):
        for right in range(left + 1, length):
            yield left, right
```

Export these symbols from `src/long_range_percolation/__init__.py`.

- [ ] **Step 5: Run the model tests**

Run:

```bash
uv run --project . pytest tests/test_model.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/pyproject.toml \
  tracks/qmc/solutions/frustration-free/challenge-194/uv.lock \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/__init__.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/model.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_model.py
GIT_AUTHOR_NAME=Codex GIT_AUTHOR_EMAIL=codex@local \
GIT_COMMITTER_NAME=Codex GIT_COMMITTER_EMAIL=codex@local \
git commit -m "Add pinned Challenge 194 model"
```

---

### Task 2: Periodic image-summed kernel

**Files:**
- Create: `src/long_range_percolation/kernel.py`
- Create: `tests/test_kernel.py`
- Modify: `src/long_range_percolation/__init__.py`

**Interfaces:**
- Consumes: `ModelSpec`, `distance_classes`.
- Produces:
  - `periodic_kernel(length: int, sigma: float) -> np.ndarray`
  - `periodic_kernel_reference(length: int, sigma: float, images: int) -> tuple[np.ndarray, np.ndarray]`
  - `kernel_weight_sum(length: int, sigma: float) -> float`
  - `edge_probabilities(spec: ModelSpec, kernel: np.ndarray) -> np.ndarray`
- The reference function returns `(partial_sum, rigorous_tail_bound)` entrywise.

- [ ] **Step 1: Write failing analytic and reference tests**

```python
import numpy as np
import pytest
from scipy.special import zeta

from long_range_percolation.kernel import (
    edge_probabilities,
    kernel_weight_sum,
    periodic_kernel,
    periodic_kernel_reference,
)
from long_range_percolation.model import ModelSpec, distance_classes


def test_sigma_one_kernel_matches_cosecant_identity():
    for length in (4, 6, 32, 256):
        distances = np.arange(1, length // 2 + 1, dtype=np.float64)
        expected = (np.pi / length) ** 2 / np.sin(np.pi * distances / length) ** 2
        np.testing.assert_allclose(
            periodic_kernel(length, 1.0),
            expected,
            rtol=2e-14,
            atol=2e-14,
        )


def test_hurwitz_kernel_is_enclosed_by_direct_image_sum():
    values = periodic_kernel(12, 0.8)
    partial, bound = periodic_kernel_reference(12, 0.8, images=100_000)
    assert np.all(np.abs(values - partial) <= bound)


def test_reference_error_and_bound_shrink_with_more_images():
    values = periodic_kernel(12, 0.8)
    coarse, coarse_bound = periodic_kernel_reference(12, 0.8, images=100)
    fine, fine_bound = periodic_kernel_reference(12, 0.8, images=200)
    assert np.all(np.abs(values - fine) < np.abs(values - coarse))
    assert np.all(fine_bound < coarse_bound)


def test_global_kernel_sum_identity():
    for length, sigma in [(4, 0.8), (12, 1.0), (32, 1.1)]:
        values = periodic_kernel(length, sigma)
        measured = sum(
            item.multiplicity * values[item.distance - 1]
            for item in distance_classes(length)
        )
        expected = length * zeta(1.0 + sigma, 1.0) * (
            1.0 - length ** (-(1.0 + sigma))
        )
        assert measured == pytest.approx(expected, rel=2e-13)


def test_edge_probabilities_use_stable_exponential_form():
    spec = ModelSpec(length=4, sigma=1.0, kappa=1e-16)
    probability = edge_probabilities(spec, periodic_kernel(4, 1.0))[0]
    assert probability > 0.0
    assert probability == pytest.approx(
        spec.kappa * periodic_kernel(4, 1.0)[0],
        rel=1e-15,
    )
```

- [ ] **Step 2: Run tests and observe missing functions**

Run:

```bash
uv run --project . pytest tests/test_kernel.py -q
```

Expected: collection fails because `kernel.py` does not exist.

- [ ] **Step 3: Implement production and reference kernels**

```python
from __future__ import annotations

import math

import numpy as np
from scipy.special import zeta

from .model import ModelSpec


def periodic_kernel(length: int, sigma: float) -> np.ndarray:
    ModelSpec(length=length, sigma=sigma, kappa=0.0)
    distances = np.arange(1, length // 2 + 1, dtype=np.float64)
    if float(sigma) == 1.0:
        angles = np.pi * distances / length
        return (np.pi / length) ** 2 / np.sin(angles) ** 2
    exponent = 1.0 + float(sigma)
    fraction = distances / length
    return length ** (-exponent) * (
        zeta(exponent, fraction) + zeta(exponent, 1.0 - fraction)
    )


def periodic_kernel_reference(
    length: int,
    sigma: float,
    images: int,
) -> tuple[np.ndarray, np.ndarray]:
    ModelSpec(length=length, sigma=sigma, kappa=0.0)
    if isinstance(images, bool) or not isinstance(images, int) or images < 1:
        raise ValueError("images must be a positive integer")
    exponent = 1.0 + float(sigma)
    distances = np.arange(1, length // 2 + 1, dtype=np.float64)
    partial = np.zeros_like(distances)
    for image in range(-images, images + 1):
        displacement = np.abs(distances + image * length)
        partial += displacement ** (-exponent)
    half_index = images + 0.5
    tail = np.full_like(
        distances,
        2.0 * length ** (-exponent) * (
            half_index ** (-exponent)
            + half_index ** (1.0 - exponent) / (exponent - 1.0)
        ),
    )
    return partial, tail


def kernel_weight_sum(length: int, sigma: float) -> float:
    ModelSpec(length=length, sigma=sigma, kappa=0.0)
    exponent = 1.0 + float(sigma)
    return float(
        length * zeta(exponent, 1.0) * (1.0 - length ** (-exponent))
    )


def edge_probabilities(spec: ModelSpec, kernel: np.ndarray) -> np.ndarray:
    values = np.asarray(kernel, dtype=np.float64)
    if values.shape != (spec.length // 2,):
        raise ValueError("kernel shape does not match model length")
    if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError("kernel must contain finite positive values")
    return -np.expm1(-spec.kappa * values)
```

The tail bound uses both omitted half-lines and the monotone-series
sum-versus-integral bound. Add a test that doubles `images` and requires both
the partial-sum error and the stated bound to decrease.

- [ ] **Step 4: Run kernel tests**

Run:

```bash
uv run --project . pytest tests/test_kernel.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/__init__.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/kernel.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_kernel.py
GIT_AUTHOR_NAME=Codex GIT_AUTHOR_EMAIL=codex@local \
GIT_COMMITTER_NAME=Codex GIT_COMMITTER_EMAIL=codex@local \
git commit -m "Implement periodic long-range kernel"
```

---

### Task 3: Deterministic union-find and graph sample type

**Files:**
- Create: `src/long_range_percolation/union_find.py`
- Create: `src/long_range_percolation/sample.py`
- Create: `tests/test_union_find.py`
- Modify: `src/long_range_percolation/__init__.py`

**Interfaces:**
- Produces:
  - `UnionFind(length: int)`
  - `UnionFind.union(left: int, right: int) -> bool`
  - `UnionFind.labels() -> np.ndarray`
  - `UnionFind.component_sizes() -> np.ndarray`
  - `GraphSample(length: int, edges: np.ndarray, labels: np.ndarray)`
- `GraphSample.edges` has shape `(n_edges, 2)`, dtype `int64`, and canonical
  sorted endpoints.

- [ ] **Step 1: Write failing partition and validation tests**

```python
import numpy as np
import pytest

from long_range_percolation.sample import GraphSample
from long_range_percolation.union_find import UnionFind


def test_union_find_returns_deterministic_labels_and_sizes():
    union_find = UnionFind(6)
    for left, right in [(4, 5), (1, 2), (0, 2), (3, 5)]:
        union_find.union(left, right)
    np.testing.assert_array_equal(union_find.labels(), [0, 0, 0, 3, 3, 3])
    np.testing.assert_array_equal(union_find.component_sizes(), [3, 3])


def test_graph_sample_rejects_duplicate_or_noncanonical_edges():
    labels = np.arange(4)
    with pytest.raises(ValueError, match="canonical"):
        GraphSample(4, np.array([[2, 1]]), labels)
    with pytest.raises(ValueError, match="duplicate"):
        GraphSample(4, np.array([[0, 1], [0, 1]]), labels)
```

- [ ] **Step 2: Run tests and observe missing modules**

Run:

```bash
uv run --project . pytest tests/test_union_find.py -q
```

Expected: collection fails because `union_find.py` and `sample.py` do not
exist.

- [ ] **Step 3: Implement union-by-size with deterministic tie-breaking**

```python
from __future__ import annotations

import numpy as np


class UnionFind:
    def __init__(self, length: int):
        if isinstance(length, bool) or not isinstance(length, int) or length < 1:
            raise ValueError("length must be a positive integer")
        self.parent = np.arange(length, dtype=np.int64)
        self.size = np.ones(length, dtype=np.int64)

    def find(self, node: int) -> int:
        if isinstance(node, bool) or not isinstance(node, int):
            raise ValueError("node must be an integer")
        if not 0 <= node < self.parent.size:
            raise ValueError("node is out of range")
        root = node
        while self.parent[root] != root:
            root = int(self.parent[root])
        while self.parent[node] != node:
            parent = int(self.parent[node])
            self.parent[node] = root
            node = parent
        return root

    def union(self, left: int, right: int) -> bool:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return False
        if (
            self.size[root_left] < self.size[root_right]
            or (
                self.size[root_left] == self.size[root_right]
                and root_left > root_right
            )
        ):
            root_left, root_right = root_right, root_left
        self.parent[root_right] = root_left
        self.size[root_left] += self.size[root_right]
        return True

    def labels(self) -> np.ndarray:
        roots = np.array([self.find(i) for i in range(self.parent.size)])
        minimum = {}
        for node, root in enumerate(roots.tolist()):
            minimum[root] = min(node, minimum.get(root, node))
        return np.array([minimum[int(root)] for root in roots], dtype=np.int64)

    def component_sizes(self) -> np.ndarray:
        _, counts = np.unique(self.labels(), return_counts=True)
        return np.sort(counts.astype(np.int64))[::-1]
```

Implement `GraphSample` as a frozen dataclass:

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .union_find import UnionFind


@dataclass(frozen=True)
class GraphSample:
    length: int
    edges: np.ndarray
    labels: np.ndarray

    def __post_init__(self) -> None:
        if (
            isinstance(self.length, bool)
            or not isinstance(self.length, int)
            or self.length < 1
        ):
            raise ValueError("length must be a positive integer")
        edges = np.array(self.edges, dtype=np.int64, copy=True)
        labels = np.array(self.labels, dtype=np.int64, copy=True)
        if edges.ndim != 2 or edges.shape[1:] != (2,):
            raise ValueError("edges must have shape (n_edges, 2)")
        if labels.shape != (self.length,):
            raise ValueError("labels must have shape (length,)")
        if edges.size and (
            np.any(edges < 0) or np.any(edges >= self.length)
        ):
            raise ValueError("edge endpoint is out of range")
        if edges.size and np.any(edges[:, 0] >= edges[:, 1]):
            raise ValueError("edges must have canonical increasing endpoints")
        edge_tuples = [tuple(edge) for edge in edges.tolist()]
        if edge_tuples != sorted(edge_tuples):
            raise ValueError("edges must be sorted")
        if len(edge_tuples) != len(set(edge_tuples)):
            raise ValueError("duplicate edges are forbidden")
        union_find = UnionFind(self.length)
        for left, right in edge_tuples:
            union_find.union(left, right)
        if not np.array_equal(labels, union_find.labels()):
            raise ValueError("labels do not match the edge-induced partition")
        edges.setflags(write=False)
        labels.setflags(write=False)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "labels", labels)
```

- [ ] **Step 4: Run union-find tests**

Run:

```bash
uv run --project . pytest tests/test_union_find.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/__init__.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/sample.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/union_find.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_union_find.py
GIT_AUTHOR_NAME=Codex GIT_AUTHOR_EMAIL=codex@local \
GIT_COMMITTER_NAME=Codex GIT_COMMITTER_EMAIL=codex@local \
git commit -m "Add deterministic percolation components"
```

---

### Task 4: Independent quadratic Bernoulli oracle

**Files:**
- Create: `src/long_range_percolation/oracle.py`
- Create: `tests/test_oracle.py`
- Modify: `src/long_range_percolation/__init__.py`

**Interfaces:**
- Consumes: `ModelSpec`, `periodic_kernel`, `UnionFind`, `GraphSample`.
- Produces:
  - `sample_quadratic(spec: ModelSpec, rng: np.random.Generator) -> GraphSample`
  - `expected_open_edges(spec: ModelSpec) -> float`
  - `variance_open_edges(spec: ModelSpec) -> float`
  - `no_edge_probability(spec: ModelSpec) -> float`

- [ ] **Step 1: Write failing deterministic-limit and moment tests**

```python
import numpy as np
import pytest

from long_range_percolation.model import ModelSpec
from long_range_percolation.oracle import (
    expected_open_edges,
    no_edge_probability,
    sample_quadratic,
    variance_open_edges,
)


def test_quadratic_oracle_exact_limits():
    empty = sample_quadratic(
        ModelSpec(8, 1.0, 0.0),
        np.random.default_rng(1),
    )
    assert empty.edges.shape == (0, 2)
    np.testing.assert_array_equal(empty.labels, np.arange(8))

    full = sample_quadratic(
        ModelSpec(8, 1.0, 1e6),
        np.random.default_rng(1),
    )
    assert full.edges.shape == (28, 2)
    np.testing.assert_array_equal(full.labels, np.zeros(8, dtype=np.int64))


def test_oracle_edge_count_matches_analytic_moments():
    spec = ModelSpec(8, 0.9, 0.7)
    counts = np.array(
        [
            sample_quadratic(spec, np.random.default_rng(seed)).edges.shape[0]
            for seed in range(30_000)
        ]
    )
    assert counts.mean() == pytest.approx(
        expected_open_edges(spec),
        abs=5.0 * np.sqrt(variance_open_edges(spec) / counts.size),
    )
    assert counts.var(ddof=1) == pytest.approx(
        variance_open_edges(spec),
        rel=0.05,
    )


def test_no_edge_probability_uses_total_kernel_weight():
    spec = ModelSpec(6, 1.0, 0.4)
    observed = np.mean(
        [
            sample_quadratic(spec, np.random.default_rng(seed)).edges.size == 0
            for seed in range(40_000)
        ]
    )
    assert observed == pytest.approx(no_edge_probability(spec), abs=0.01)
```

- [ ] **Step 2: Run tests and observe missing functions**

Run:

```bash
uv run --project . pytest tests/test_oracle.py -q
```

Expected: collection fails because `oracle.py` does not exist.

- [ ] **Step 3: Implement the independently structured oracle**

```python
from __future__ import annotations

import math

import numpy as np

from .kernel import edge_probabilities, kernel_weight_sum, periodic_kernel
from .model import ModelSpec
from .sample import GraphSample
from .union_find import UnionFind


def _distance(left: int, right: int, length: int) -> int:
    separation = right - left
    return min(separation, length - separation)


def sample_quadratic(
    spec: ModelSpec,
    rng: np.random.Generator,
) -> GraphSample:
    if not isinstance(rng, np.random.Generator):
        raise ValueError("rng must be numpy.random.Generator")
    probabilities = edge_probabilities(
        spec,
        periodic_kernel(spec.length, spec.sigma),
    )
    union_find = UnionFind(spec.length)
    edges = []
    for left in range(spec.length):
        for right in range(left + 1, spec.length):
            probability = probabilities[_distance(left, right, spec.length) - 1]
            if rng.random() < probability:
                edges.append((left, right))
                union_find.union(left, right)
    edge_array = np.asarray(edges, dtype=np.int64).reshape(-1, 2)
    return GraphSample(spec.length, edge_array, union_find.labels())


def _class_probabilities(spec: ModelSpec) -> tuple[np.ndarray, np.ndarray]:
    from .model import distance_classes

    multiplicity = np.array(
        [item.multiplicity for item in distance_classes(spec.length)],
        dtype=np.float64,
    )
    probability = edge_probabilities(
        spec,
        periodic_kernel(spec.length, spec.sigma),
    )
    return multiplicity, probability


def expected_open_edges(spec: ModelSpec) -> float:
    multiplicity, probability = _class_probabilities(spec)
    return float(multiplicity @ probability)


def variance_open_edges(spec: ModelSpec) -> float:
    multiplicity, probability = _class_probabilities(spec)
    return float(multiplicity @ (probability * (1.0 - probability)))


def no_edge_probability(spec: ModelSpec) -> float:
    return math.exp(-spec.kappa * kernel_weight_sum(spec.length, spec.sigma))
```

- [ ] **Step 4: Run oracle tests**

Run:

```bash
uv run --project . pytest tests/test_oracle.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/__init__.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/oracle.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_oracle.py
GIT_AUTHOR_NAME=Codex GIT_AUTHOR_EMAIL=codex@local \
GIT_COMMITTER_NAME=Codex GIT_COMMITTER_EMAIL=codex@local \
git commit -m "Add independent quadratic graph oracle"
```

---

### Task 5: Exact graph enumeration through `L = 6`

**Files:**
- Create: `src/long_range_percolation/enumeration.py`
- Create: `tests/test_enumeration.py`
- Modify: `src/long_range_percolation/__init__.py`

**Interfaces:**
- Produces:
  - `GraphOutcome(mask: int, probability: float, open_edges: int, component_sizes: tuple[int, ...])`
  - `enumerate_graphs(spec: ModelSpec) -> Iterator[GraphOutcome]`
  - `exact_partition_distribution(spec: ModelSpec) -> dict[tuple[int, ...], float]`
- Enumeration rejects `L > 6`.

- [ ] **Step 1: Write failing normalization and known-case tests**

```python
import math

import pytest

from long_range_percolation.enumeration import (
    enumerate_graphs,
    exact_partition_distribution,
)
from long_range_percolation.model import ModelSpec
from long_range_percolation.oracle import (
    expected_open_edges,
    no_edge_probability,
)


def test_all_graph_probabilities_normalize_and_reproduce_analytic_moments():
    for length in (2, 4, 6):
        spec = ModelSpec(length, 0.9, 0.6)
        outcomes = list(enumerate_graphs(spec))
        assert len(outcomes) == 2 ** (length * (length - 1) // 2)
        assert math.fsum(item.probability for item in outcomes) == pytest.approx(1.0)
        assert math.fsum(
            item.probability * item.open_edges for item in outcomes
        ) == pytest.approx(expected_open_edges(spec))
        assert outcomes[0].probability == pytest.approx(no_edge_probability(spec))


def test_two_site_partition_probabilities_are_exact():
    spec = ModelSpec(2, 1.0, 0.3)
    distribution = exact_partition_distribution(spec)
    closed = no_edge_probability(spec)
    assert distribution[(1, 1)] == pytest.approx(closed)
    assert distribution[(2,)] == pytest.approx(1.0 - closed)


def test_enumeration_rejects_lengths_above_six():
    with pytest.raises(ValueError, match="at most six"):
        list(enumerate_graphs(ModelSpec(8, 1.0, 1.0)))


def test_zero_coupling_assigns_unit_mass_to_empty_graph():
    outcomes = list(enumerate_graphs(ModelSpec(4, 1.0, 0.0)))
    assert outcomes[0].probability == 1.0
    assert all(item.probability == 0.0 for item in outcomes[1:])
```

- [ ] **Step 2: Run tests and observe missing module**

Run:

```bash
uv run --project . pytest tests/test_enumeration.py -q
```

Expected: collection fails because `enumeration.py` does not exist.

- [ ] **Step 3: Implement mask enumeration using independent edge probabilities**

```python
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterator

from .kernel import edge_probabilities, periodic_kernel
from .model import ModelSpec, iter_unordered_edges
from .union_find import UnionFind


@dataclass(frozen=True)
class GraphOutcome:
    mask: int
    probability: float
    open_edges: int
    component_sizes: tuple[int, ...]


def enumerate_graphs(spec: ModelSpec) -> Iterator[GraphOutcome]:
    if spec.length > 6:
        raise ValueError("exact enumeration supports length at most six")
    probabilities = edge_probabilities(
        spec,
        periodic_kernel(spec.length, spec.sigma),
    )
    edges = list(iter_unordered_edges(spec.length))
    if spec.kappa == 0.0:
        for mask in range(1 << len(edges)):
            yield GraphOutcome(
                mask=mask,
                probability=1.0 if mask == 0 else 0.0,
                open_edges=0 if mask == 0 else mask.bit_count(),
                component_sizes=(
                    tuple([1] * spec.length)
                    if mask == 0
                    else _component_sizes_for_mask(spec.length, edges, mask)
                ),
            )
        return
    for mask in range(1 << len(edges)):
        union_find = UnionFind(spec.length)
        log_probability = 0.0
        open_count = 0
        for index, (left, right) in enumerate(edges):
            separation = right - left
            distance = min(separation, spec.length - separation)
            probability = float(probabilities[distance - 1])
            if mask & (1 << index):
                log_probability += math.log(probability)
                open_count += 1
                union_find.union(left, right)
            else:
                log_probability += math.log1p(-probability)
        yield GraphOutcome(
            mask=mask,
            probability=math.exp(log_probability),
            open_edges=open_count,
            component_sizes=tuple(union_find.component_sizes().tolist()),
        )


def exact_partition_distribution(
    spec: ModelSpec,
) -> dict[tuple[int, ...], float]:
    result: dict[tuple[int, ...], float] = {}
    for outcome in enumerate_graphs(spec):
        result[outcome.component_sizes] = (
            result.get(outcome.component_sizes, 0.0) + outcome.probability
        )
    return result
```

Add this helper above `enumerate_graphs`:

```python
def _component_sizes_for_mask(
    length: int,
    edges: list[tuple[int, int]],
    mask: int,
) -> tuple[int, ...]:
    union_find = UnionFind(length)
    for index, (left, right) in enumerate(edges):
        if mask & (1 << index):
            union_find.union(left, right)
    return tuple(union_find.component_sizes().tolist())
```

- [ ] **Step 4: Run enumeration tests**

Run:

```bash
uv run --project . pytest tests/test_enumeration.py -q
```

Expected: `4 passed`, including the added `kappa = 0` test.

- [ ] **Step 5: Commit**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/__init__.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/enumeration.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_enumeration.py
GIT_AUTHOR_NAME=Codex GIT_AUTHOR_EMAIL=codex@local \
GIT_COMMITTER_NAME=Codex GIT_COMMITTER_EMAIL=codex@local \
git commit -m "Add exact small-graph product oracle"
```

---

### Task 6: Geometric-skipping accelerated sampler

**Files:**
- Create: `src/long_range_percolation/geometric.py`
- Create: `tests/test_geometric.py`
- Modify: `src/long_range_percolation/__init__.py`

**Interfaces:**
- Consumes: `ModelSpec`, `distance_classes`, `canonical_edge`,
  `periodic_kernel`, `UnionFind`, `GraphSample`.
- Produces:
  - `sample_geometric(spec: ModelSpec, rng: np.random.Generator) -> GraphSample`
- The implementation does not call `sample_quadratic` or iterate all
  unordered pairs.

- [ ] **Step 1: Write failing structure and limit tests**

```python
import inspect

import numpy as np
import pytest

import long_range_percolation.geometric as geometric_module
from long_range_percolation.geometric import sample_geometric
from long_range_percolation.model import ModelSpec


def test_geometric_sampler_does_not_call_quadratic_oracle():
    source = inspect.getsource(geometric_module)
    assert "sample_quadratic" not in source
    assert "iter_unordered_edges" not in source


def test_geometric_sampler_exact_limits_and_antipodal_uniqueness():
    empty = sample_geometric(
        ModelSpec(8, 1.0, 0.0),
        np.random.default_rng(4),
    )
    assert empty.edges.shape == (0, 2)

    full = sample_geometric(
        ModelSpec(8, 1.0, 1e6),
        np.random.default_rng(4),
    )
    assert full.edges.shape == (28, 2)
    antipodal = [
        edge for edge in full.edges.tolist()
        if min((edge[1] - edge[0]) % 8, (edge[0] - edge[1]) % 8) == 4
    ]
    assert len(antipodal) == 4


def test_geometric_sampler_is_seed_reproducible():
    spec = ModelSpec(32, 0.8, 0.7)
    first = sample_geometric(spec, np.random.default_rng(20260729))
    second = sample_geometric(spec, np.random.default_rng(20260729))
    np.testing.assert_array_equal(first.edges, second.edges)
    np.testing.assert_array_equal(first.labels, second.labels)


def test_geometric_sampler_rejects_unregistered_rng_objects():
    with pytest.raises(ValueError, match="numpy.random.Generator"):
        sample_geometric(ModelSpec(8, 1.0, 0.7), object())
```

- [ ] **Step 2: Run tests and observe missing module**

Run:

```bash
uv run --project . pytest tests/test_geometric.py -q
```

Expected: collection fails because `geometric.py` does not exist.

- [ ] **Step 3: Implement independent distance-class skipping**

```python
from __future__ import annotations

import math

import numpy as np

from .kernel import periodic_kernel
from .model import ModelSpec, canonical_edge, distance_classes
from .sample import GraphSample
from .union_find import UnionFind


def sample_geometric(
    spec: ModelSpec,
    rng: np.random.Generator,
) -> GraphSample:
    if not isinstance(rng, np.random.Generator):
        raise ValueError("rng must be numpy.random.Generator")
    if spec.kappa == 0.0:
        return GraphSample(
            spec.length,
            np.empty((0, 2), dtype=np.int64),
            np.arange(spec.length, dtype=np.int64),
        )
    rates = spec.kappa * periodic_kernel(spec.length, spec.sigma)
    union_find = UnionFind(spec.length)
    edges: list[tuple[int, int]] = []
    for item in distance_classes(spec.length):
        rate = float(rates[item.distance - 1])
        offset = 0
        while offset < item.multiplicity:
            uniform = 1.0 - rng.random()
            skipped = int(math.floor(-math.log(uniform) / rate))
            offset += skipped
            if offset >= item.multiplicity:
                break
            edge = canonical_edge(spec.length, item.distance, offset)
            edges.append(edge)
            union_find.union(*edge)
            offset += 1
    edge_array = np.asarray(sorted(edges), dtype=np.int64).reshape(-1, 2)
    return GraphSample(spec.length, edge_array, union_find.labels())
```

- [ ] **Step 4: Run geometric tests**

Run:

```bash
uv run --project . pytest tests/test_geometric.py -q
```

Expected: `4 passed`, including rejection of unregistered RNG objects.

- [ ] **Step 5: Commit**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/__init__.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/geometric.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_geometric.py
GIT_AUTHOR_NAME=Codex GIT_AUTHOR_EMAIL=codex@local \
GIT_COMMITTER_NAME=Codex GIT_COMMITTER_EMAIL=codex@local \
git commit -m "Add accelerated distance-class sampler"
```

---

### Task 7: Independent sampler acceptance and Day-0 documentation

**Files:**
- Create: `tests/test_day0_acceptance.py`
- Create: `README.md`

**Interfaces:**
- Consumes all prior Day-0 interfaces.
- Produces no reusable production API. This task is an acceptance gate.

- [ ] **Step 1: Write the independent statistical acceptance tests**

```python
from collections import Counter

import numpy as np
import pytest
from scipy.stats import binomtest

from long_range_percolation.enumeration import exact_partition_distribution
from long_range_percolation.geometric import sample_geometric
from long_range_percolation.kernel import (
    edge_probabilities,
    periodic_kernel,
)
from long_range_percolation.model import ModelSpec, distance_classes
from long_range_percolation.oracle import sample_quadratic


def _edge_distance(edge: tuple[int, int], length: int) -> int:
    separation = edge[1] - edge[0]
    return min(separation, length - separation)


def _distance_open_counts(samples, length: int) -> Counter[int]:
    counts: Counter[int] = Counter()
    for sample in samples:
        counts.update(
            _edge_distance(tuple(edge), length)
            for edge in sample.edges.tolist()
        )
    return counts


@pytest.mark.parametrize("length", [4, 8, 32])
def test_geometric_distance_frequencies_match_exact_probabilities(length):
    spec = ModelSpec(length, 1.0, 0.7)
    n_samples = 20_000
    samples = [
        sample_geometric(spec, np.random.default_rng(100_000 + index))
        for index in range(n_samples)
    ]
    counts = _distance_open_counts(samples, length)
    probabilities = edge_probabilities(
        spec,
        periodic_kernel(length, spec.sigma),
    )
    classes = distance_classes(length)
    alpha = 0.001 / len(classes)
    for item in classes:
        trials = n_samples * item.multiplicity
        result = binomtest(
            counts[item.distance],
            trials,
            probabilities[item.distance - 1],
        )
        assert result.pvalue > alpha


@pytest.mark.parametrize("length", [4, 6])
def test_oracle_and_geometric_partition_histograms_match_exact_distribution(
    length,
):
    spec = ModelSpec(length, 0.9, 0.6)
    exact = exact_partition_distribution(spec)
    n_samples = 40_000
    for sampler, seed_offset in [
        (sample_quadratic, 0),
        (sample_geometric, 1_000_000),
    ]:
        observed: Counter[tuple[int, ...]] = Counter()
        for index in range(n_samples):
            sample = sampler(
                spec,
                np.random.default_rng(seed_offset + index),
            )
            _, counts = np.unique(sample.labels, return_counts=True)
            observed[tuple(sorted(counts.tolist(), reverse=True))] += 1
        for partition, probability in exact.items():
            standard_error = np.sqrt(
                max(probability * (1.0 - probability), 1e-12) / n_samples
            )
            assert observed[partition] / n_samples == pytest.approx(
                probability,
                abs=6.0 * standard_error + 1.0 / n_samples,
            )


def test_accelerated_and_quadratic_samples_use_independent_seed_streams():
    spec = ModelSpec(32, 1.0, 0.7)
    quadratic = sample_quadratic(spec, np.random.default_rng(11))
    geometric = sample_geometric(spec, np.random.default_rng(12))
    assert not np.array_equal(quadratic.edges, geometric.edges)
```

- [ ] **Step 2: Run the acceptance tests**

Run:

```bash
uv run --project . pytest tests/test_day0_acceptance.py -q
```

Expected: all six parameterized acceptance cases pass.

- [ ] **Step 3: Write the challenge README**

Create `README.md` with the following complete sections:

```markdown
# Challenge 194: long-range q=1 random-cluster model

This directory implements the pinned independent-edge finite-ring model from
QuantumBFS/quantum.harness issue #194. It does not use Gori et al.'s
minimum-image `C/r^(1+sigma)` convention.

## Scope

The current Day-0 milestone validates the periodic kernel, canonical edge
classes, deterministic union-find, exact graph enumeration through `L=6`,
an independent quadratic Bernoulli oracle, and a geometric-skipping sampler.
It makes no transition or critical-exponent claim.

## Setup

```bash
uv sync \
  --project tracks/qmc/solutions/frustration-free/challenge-194 \
  --python 3.12
```

## Verify

```bash
uv run \
  --project tracks/qmc/solutions/frustration-free/challenge-194 \
  pytest -q
```

The accelerated sampler is accepted only when it agrees with analytic edge
probabilities and exact small-system partition distributions. Generated
production data do not exist at this milestone.

## Design and references

- `DESIGN.md` pins the scientific and statistical protocol.
- `PLAN.md` records the test-driven implementation sequence.
- `references/README.md` records source URLs and SHA256 hashes.
```

- [ ] **Step 4: Run the complete Day-0 suite**

Run from the challenge directory:

```bash
uv run --project . pytest -q
```

Expected: all tests pass with no failures.

- [ ] **Step 5: Verify repository hygiene**

Run:

```bash
git status --short
git diff --check
git check-ignore \
  tracks/qmc/results/frustration-free/challenge-194/
```

Expected: only owned source/test/documentation changes are visible; the
challenge result directory is ignored; `git diff --check` exits zero.

- [ ] **Step 6: Commit**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/README.md \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_day0_acceptance.py
GIT_AUTHOR_NAME=Codex GIT_AUTHOR_EMAIL=codex@local \
GIT_COMMITTER_NAME=Codex GIT_COMMITTER_EMAIL=codex@local \
git commit -m "Validate Challenge 194 graph generation"
```

---

## Day-0 completion gate

The subproject is complete only when:

1. the full local test suite passes from a fresh `uv sync`;
2. analytic kernel, edge-count, and exact-enumeration gates pass;
3. independent distance-frequency and partition-distribution acceptance tests
   pass for both samplers;
4. the challenge result directory is ignored by Git;
5. the working tree is clean after the final commit;
6. an independent reviewer confirms that oracle and accelerated samplers do
   not share edge-selection logic.

After this gate, write and review a separate production-sampler plan covering
the Poisson/Newman-Ziff sweep, counter-based RNG, compiled performance path,
incremental observables, immutable raw batches, and local-versus-cluster
resource calibration.
