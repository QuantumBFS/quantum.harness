"""Small interpretable classifiers without a scikit-learn dependency."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Sequence

import numpy as np
from scipy.special import expit
from scipy.stats import rankdata


def roc_auc(labels: np.ndarray, scores: np.ndarray) -> float:
    y = np.asarray(labels, dtype=np.float64)
    prediction = np.asarray(scores, dtype=np.float64)
    if y.shape != prediction.shape or y.ndim != 1:
        raise ValueError("labels and scores must be equal one-dimensional arrays")
    positive = y == 1.0
    negative = y == 0.0
    if not np.all(positive | negative):
        raise ValueError("labels must be binary")
    positive_count = int(positive.sum())
    negative_count = int(negative.sum())
    if positive_count == 0 or negative_count == 0:
        return math.nan
    ranks = rankdata(prediction, method="average")
    rank_sum = float(ranks[positive].sum())
    return (
        rank_sum - positive_count * (positive_count + 1) / 2.0
    ) / (positive_count * negative_count)


def precision_recall_auc(labels: np.ndarray, scores: np.ndarray) -> float:
    """Return average precision, the step-integrated precision-recall area."""

    y = np.asarray(labels, dtype=np.float64)
    prediction = np.asarray(scores, dtype=np.float64)
    if y.shape != prediction.shape or y.ndim != 1:
        raise ValueError("labels and scores must be equal one-dimensional arrays")
    if not np.all((y == 0.0) | (y == 1.0)):
        raise ValueError("labels must be binary")
    positive_count = int(y.sum())
    if positive_count == 0:
        return math.nan
    order = np.argsort(-prediction, kind="stable")
    ordered = y[order]
    true_positive = np.cumsum(ordered)
    precision = true_positive / np.arange(1, len(y) + 1)
    return float(precision[ordered == 1.0].sum() / positive_count)


@dataclass(frozen=True)
class SparseLogisticModel:
    coefficients: np.ndarray
    intercept: float
    means: np.ndarray
    scales: np.ndarray
    binary_columns: np.ndarray
    iterations: int
    converged: bool

    def transform(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != len(self.coefficients):
            raise ValueError("feature shape does not match logistic model")
        return (values - self.means) / self.scales

    def predict_probability(self, features: np.ndarray) -> np.ndarray:
        transformed = self.transform(features)
        return expit(transformed @ self.coefficients + self.intercept)


def _standardize_features(
    features: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(features, dtype=np.float64)
    if values.ndim != 2 or len(values) == 0:
        raise ValueError("features must be a nonempty matrix")
    if not np.all(np.isfinite(values)):
        raise ValueError("features must be finite")
    binary = np.array(
        [
            np.all((values[:, column] == 0.0) | (values[:, column] == 1.0))
            for column in range(values.shape[1])
        ],
        dtype=bool,
    )
    means = values.mean(axis=0)
    scales = values.std(axis=0)
    means[binary] = 0.0
    scales[binary] = 1.0
    scales[scales == 0.0] = 1.0
    return (values - means) / scales, means, scales, binary


def fit_sparse_logistic(
    features: np.ndarray,
    labels: np.ndarray,
    l1: float,
    max_iter: int = 2000,
    tolerance: float = 1.0e-8,
) -> SparseLogisticModel:
    """Fit L1 logistic regression by FISTA with an unpenalized intercept."""

    if l1 < 0.0 or max_iter <= 0 or tolerance <= 0.0:
        raise ValueError("invalid logistic optimization parameter")
    x, means, scales, binary = _standardize_features(features)
    y = np.asarray(labels, dtype=np.float64)
    if y.ndim != 1 or len(y) != len(x):
        raise ValueError("label shape does not match features")
    if not np.all((y == 0.0) | (y == 1.0)) or len(np.unique(y)) != 2:
        raise ValueError("logistic labels must contain both binary classes")

    rows, columns = x.shape
    beta = np.zeros(columns, dtype=np.float64)
    accelerated_beta = beta.copy()
    prevalence = float(np.clip(y.mean(), 1.0e-8, 1.0 - 1.0e-8))
    intercept = math.log(prevalence / (1.0 - prevalence))
    accelerated_intercept = intercept
    momentum = 1.0
    augmented = np.column_stack([x, np.ones(rows)])
    spectral_norm = float(np.linalg.norm(augmented, ord=2))
    lipschitz = 0.25 * spectral_norm * spectral_norm / rows
    step = 1.0 / max(lipschitz, 1.0e-12)
    converged = False

    for iteration in range(1, max_iter + 1):
        probability = expit(
            x @ accelerated_beta + accelerated_intercept
        )
        residual = probability - y
        gradient = x.T @ residual / rows
        intercept_gradient = float(residual.mean())
        candidate = accelerated_beta - step * gradient
        beta_next = np.sign(candidate) * np.maximum(
            np.abs(candidate) - step * l1, 0.0
        )
        intercept_next = (
            accelerated_intercept - step * intercept_gradient
        )
        maximum_change = max(
            float(np.max(np.abs(beta_next - beta), initial=0.0)),
            abs(intercept_next - intercept),
        )
        momentum_next = (
            1.0 + math.sqrt(1.0 + 4.0 * momentum * momentum)
        ) / 2.0
        factor = (momentum - 1.0) / momentum_next
        accelerated_beta = beta_next + factor * (beta_next - beta)
        accelerated_intercept = (
            intercept_next + factor * (intercept_next - intercept)
        )
        beta = beta_next
        intercept = intercept_next
        momentum = momentum_next
        if maximum_change < tolerance:
            converged = True
            break
    if not converged:
        raise RuntimeError("sparse logistic optimization did not converge")
    return SparseLogisticModel(
        coefficients=beta,
        intercept=intercept,
        means=means,
        scales=scales,
        binary_columns=binary,
        iterations=iteration,
        converged=converged,
    )


@dataclass
class TreeNode:
    probability: float
    samples: int
    feature_index: Optional[int] = None
    feature_name: Optional[str] = None
    threshold: Optional[float] = None
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None

    @property
    def is_leaf(self) -> bool:
        return self.feature_index is None

    def used_features(self) -> list[str]:
        result = []
        if self.feature_name is not None:
            result.append(self.feature_name)
        for child in (self.left, self.right):
            if child is not None:
                result.extend(child.used_features())
        return list(dict.fromkeys(result))

    def predict_probability(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=np.float64)
        if values.ndim != 2:
            raise ValueError("tree features must be a matrix")
        result = np.empty(len(values), dtype=np.float64)
        for row_index, row in enumerate(values):
            node = self
            while not node.is_leaf:
                assert node.feature_index is not None
                assert node.threshold is not None
                child = (
                    node.left
                    if row[node.feature_index] <= node.threshold
                    else node.right
                )
                if child is None:
                    raise RuntimeError("tree node is missing a child")
                node = child
            result[row_index] = node.probability
        return result

    def to_rules(self, indent: str = "") -> str:
        if self.is_leaf:
            return (
                f"{indent}predict p={self.probability:.6g} "
                f"(n={self.samples})"
            )
        assert self.feature_name is not None
        assert self.threshold is not None
        assert self.left is not None and self.right is not None
        return (
            f"{indent}if {self.feature_name} <= {self.threshold:.6g}:\n"
            f"{self.left.to_rules(indent + '  ')}\n"
            f"{indent}else:\n"
            f"{self.right.to_rules(indent + '  ')}"
        )


def _gini(labels: np.ndarray) -> float:
    if len(labels) == 0:
        return 0.0
    probability = float(labels.mean())
    return 2.0 * probability * (1.0 - probability)


def fit_shallow_tree(
    features: np.ndarray,
    labels: np.ndarray,
    feature_names: Sequence[str],
    max_depth: int = 3,
    min_leaf: int = 50,
) -> TreeNode:
    """Fit a deterministic small CART tree with readable thresholds."""

    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    if (
        x.ndim != 2
        or y.ndim != 1
        or len(x) != len(y)
        or x.shape[1] != len(feature_names)
    ):
        raise ValueError("tree feature, label, or name shape mismatch")
    if not np.all((y == 0.0) | (y == 1.0)):
        raise ValueError("tree labels must be binary")
    if max_depth < 0 or min_leaf <= 0:
        raise ValueError("invalid tree depth or leaf size")

    def build(indices: np.ndarray, depth: int) -> TreeNode:
        node_labels = y[indices]
        leaf = TreeNode(
            probability=float(node_labels.mean()),
            samples=len(indices),
        )
        if (
            depth >= max_depth
            or len(indices) < 2 * min_leaf
            or np.all(node_labels == node_labels[0])
        ):
            return leaf
        parent_impurity = _gini(node_labels)
        best = None
        for feature_index in range(x.shape[1]):
            values = x[indices, feature_index]
            unique = np.unique(values)
            if len(unique) <= 1:
                continue
            if len(unique) == 2 and np.array_equal(unique, [0.0, 1.0]):
                thresholds = np.array([0.5])
            else:
                thresholds = np.unique(
                    np.quantile(values, np.linspace(0.0, 1.0, 17)[1:-1])
                )
            for threshold in thresholds:
                left_mask = values <= threshold
                left_count = int(left_mask.sum())
                right_count = len(indices) - left_count
                if left_count < min_leaf or right_count < min_leaf:
                    continue
                weighted = (
                    left_count * _gini(node_labels[left_mask])
                    + right_count * _gini(node_labels[~left_mask])
                ) / len(indices)
                gain = parent_impurity - weighted
                candidate = (
                    -gain,
                    feature_index,
                    float(threshold),
                    left_mask,
                )
                if best is None or candidate[:3] < best[:3]:
                    best = candidate
        if best is None or -best[0] <= 0.0:
            return leaf
        _, feature_index, threshold, left_mask = best
        return TreeNode(
            probability=leaf.probability,
            samples=leaf.samples,
            feature_index=feature_index,
            feature_name=str(feature_names[feature_index]),
            threshold=threshold,
            left=build(indices[left_mask], depth + 1),
            right=build(indices[~left_mask], depth + 1),
        )

    return build(np.arange(len(x), dtype=np.int64), 0)


def _splitmix64(value: int) -> int:
    mask = (1 << 64) - 1
    value = (value + 0x9E3779B97F4A7C15) & mask
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
    return value ^ (value >> 31)


def grouped_fold(
    config_ids: np.ndarray,
    orbit_ids: np.ndarray,
    folds: int = 5,
) -> np.ndarray:
    """Assign complete symmetry orbits to stable held-out folds."""

    configs = np.asarray(config_ids, dtype=np.uint64)
    orbits = np.asarray(orbit_ids, dtype=np.uint64)
    if configs.shape != orbits.shape or configs.ndim != 1:
        raise ValueError("config and orbit ids must be equal vectors")
    if folds < 2:
        raise ValueError("at least two folds are required")
    return np.array(
        [_splitmix64(int(orbit)) % folds for orbit in orbits],
        dtype=np.int16,
    )
