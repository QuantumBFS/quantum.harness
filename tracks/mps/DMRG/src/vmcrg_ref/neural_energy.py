"""具有平移、D4 和 Z2 对称性的局域神经能量。

实现声明
--------
``D4EvenLocalMLP`` 在周期性块自旋晶格的每个 3x3 patch 上计算同一个
局域 MLP，并对 8 个 D4 变换以及 ``mu -> -mu`` 显式平均：

    V_theta(mu) = sum_x [f_theta(q_x) + f_theta(-q_x)] / 2.

对所有 patch 中心求和保证平移不变和能量广延性。模型没有输出常数项，
因为哈密顿量的加性常数无法由 VMCRG 确定。``LocalEnergyCache`` 将有限
局域状态编译成精确查找表，使一次自旋翻转只更新受影响的局域项。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


__all__ = [
    "D4EvenLocalMLP",
    "LocalEnergyCache",
    "LocalEnergyProposal",
    "MLPGradient",
]


@dataclass
class MLPGradient:
    """Gradient of the local neural energy with no unidentifiable output bias."""

    weight_in: np.ndarray
    bias_hidden: np.ndarray
    weight_out: np.ndarray

    def copy(self) -> "MLPGradient":
        return MLPGradient(
            self.weight_in.copy(),
            self.bias_hidden.copy(),
            self.weight_out.copy(),
        )

    def norm(self) -> float:
        return float(
            np.sqrt(
                np.sum(self.weight_in**2)
                + np.sum(self.bias_hidden**2)
                + np.sum(self.weight_out**2)
            )
        )


class D4EvenLocalMLP:
    """Extensive local neural energy for a periodic square Ising lattice.

    A radius-r patch is reduced to sums over the D4 coordinate orbits
    ``(|dx|, |dy|)``.  These shell features are exactly D4 invariant and change
    sign under a global spin flip.  Averaging the raw MLP at ``q`` and ``-q``
    therefore imposes exact Z2 invariance:

        V(s) = sum_x 0.5 * (f(q_x) + f(-q_x)).

    The sum over patch centres makes the energy translation invariant and
    extensive.  There is deliberately no output bias because an additive
    constant in a Hamiltonian is not identifiable by VMCRG.
    """

    def __init__(
        self,
        radius: int,
        hidden: int,
        weight_in: np.ndarray,
        bias_hidden: np.ndarray,
        weight_out: np.ndarray,
        feature_mode: str = "shell",
    ) -> None:
        if radius < 1:
            raise ValueError("radius must be positive")
        if hidden < 1:
            raise ValueError("hidden must be positive")
        self.radius = int(radius)
        self.hidden = int(hidden)
        if feature_mode not in ("shell", "patch", "multiscale"):
            raise ValueError(
                "feature_mode must be 'shell', 'patch', or 'multiscale'"
            )
        if feature_mode == "multiscale" and radius < 2:
            raise ValueError("multiscale features require radius >= 2")
        self.feature_mode = feature_mode
        if feature_mode == "shell":
            self.shell_keys, self.offset_feature, self.shell_counts = self._shell_data(
                self.radius
            )
            self.feature_permutations = np.arange(
                len(self.shell_keys), dtype=np.int32
            ).reshape(1, -1)
        elif feature_mode == "patch":
            (
                self.shell_keys,
                self.offset_feature,
                self.shell_counts,
                self.feature_permutations,
            ) = self._patch_data(self.radius)
        else:
            (
                self.shell_keys,
                self.offset_feature,
                self.shell_counts,
                self.feature_permutations,
            ) = self._multiscale_data(self.radius)
        self.lookup_strides = np.empty(len(self.shell_keys), dtype=np.int64)
        stride = 1
        for feature, count in enumerate(self.shell_counts):
            self.lookup_strides[feature] = stride
            stride *= int(count) + 1
        self.lookup_size = int(stride)
        n_features = len(self.shell_keys)
        self.weight_in = np.asarray(weight_in, dtype=np.float64).copy()
        self.bias_hidden = np.asarray(bias_hidden, dtype=np.float64).copy()
        self.weight_out = np.asarray(weight_out, dtype=np.float64).copy()
        if self.weight_in.shape != (self.hidden, n_features):
            raise ValueError("weight_in has the wrong shape")
        if self.bias_hidden.shape != (self.hidden,):
            raise ValueError("bias_hidden has the wrong shape")
        if self.weight_out.shape != (self.hidden,):
            raise ValueError("weight_out has the wrong shape")
        if not all(
            np.all(np.isfinite(values))
            for values in (self.weight_in, self.bias_hidden, self.weight_out)
        ):
            raise ValueError("neural parameters must all be finite")

    @classmethod
    def random(
        cls,
        radius: int = 2,
        hidden: int = 32,
        seed: int = 20260715,
        feature_mode: str = "shell",
    ) -> "D4EvenLocalMLP":
        rng = np.random.default_rng(seed)
        if feature_mode == "shell":
            n_features = (radius + 1) * (radius + 2) // 2
        elif feature_mode == "patch":
            n_features = (2 * radius + 1) ** 2
        elif feature_mode == "multiscale":
            n_features = 9 + sum(major + 1 for major in range(2, radius + 1))
        else:
            raise ValueError(
                "feature_mode must be 'shell', 'patch', or 'multiscale'"
            )
        weight_in = rng.normal(0.0, 1.0 / np.sqrt(n_features), (hidden, n_features))
        # A nonzero hidden bias is essential: with tanh and exact Z2 averaging,
        # zero hidden biases would make every hidden feature cancel identically.
        bias_hidden = rng.normal(0.0, 0.2, hidden)
        # Zero output weights give an exactly zero initial bias while preserving
        # a nonzero first gradient with respect to the output layer.
        weight_out = np.zeros(hidden, dtype=np.float64)
        return cls(
            radius,
            hidden,
            weight_in,
            bias_hidden,
            weight_out,
            feature_mode=feature_mode,
        )

    @staticmethod
    def _shell_data(
        radius: int,
    ) -> tuple[tuple[tuple[int, int], ...], np.ndarray, np.ndarray]:
        keys = tuple(
            (major, minor)
            for major in range(radius + 1)
            for minor in range(major + 1)
        )
        key_to_index = {key: index for index, key in enumerate(keys)}
        width = 2 * radius + 1
        offset_feature = np.empty((width, width), dtype=np.int32)
        counts = np.zeros(len(keys), dtype=np.int32)
        for ix, dx in enumerate(range(-radius, radius + 1)):
            for iy, dy in enumerate(range(-radius, radius + 1)):
                key = (max(abs(dx), abs(dy)), min(abs(dx), abs(dy)))
                feature = key_to_index[key]
                offset_feature[ix, iy] = feature
                counts[feature] += 1
        return keys, offset_feature, counts

    @staticmethod
    def _patch_data(
        radius: int,
    ) -> tuple[
        tuple[tuple[int, int], ...], np.ndarray, np.ndarray, np.ndarray
    ]:
        offsets = tuple(
            (dx, dy)
            for dx in range(-radius, radius + 1)
            for dy in range(-radius, radius + 1)
        )
        index = {offset: feature for feature, offset in enumerate(offsets)}
        width = 2 * radius + 1
        offset_feature = np.arange(width * width, dtype=np.int32).reshape(width, width)
        counts = np.ones(width * width, dtype=np.int32)

        def transforms(x: int, y: int) -> tuple[tuple[int, int], ...]:
            return (
                (x, y),
                (-y, x),
                (-x, -y),
                (y, -x),
                (-x, y),
                (x, -y),
                (y, x),
                (-y, -x),
            )

        permutations = np.empty((8, len(offsets)), dtype=np.int32)
        for transform_index in range(8):
            for output_feature, (dx, dy) in enumerate(offsets):
                permutations[transform_index, output_feature] = index[
                    transforms(dx, dy)[transform_index]
                ]
        return offsets, offset_feature, counts, permutations

    @staticmethod
    def _multiscale_data(
        radius: int,
    ) -> tuple[
        tuple[tuple[int, int], ...], np.ndarray, np.ndarray, np.ndarray
    ]:
        """Keep the inner 3x3 patch exact and pool only the outer D4 shells.

        The exact inner sites retain all published four-spin geometries.  The
        outer shell averages retain the complete radius-three two-spin range
        without feeding any hand-written operator value into the network.
        """
        inner = tuple(
            (dx, dy) for dx in range(-1, 2) for dy in range(-1, 2)
        )
        outer = tuple(
            (major, minor)
            for major in range(2, radius + 1)
            for minor in range(major + 1)
        )
        keys = (*inner, *outer)
        inner_index = {offset: index for index, offset in enumerate(inner)}
        outer_index = {
            shell: len(inner) + index for index, shell in enumerate(outer)
        }
        width = 2 * radius + 1
        offset_feature = np.empty((width, width), dtype=np.int32)
        counts = np.zeros(len(keys), dtype=np.int32)
        for ix, dx in enumerate(range(-radius, radius + 1)):
            for iy, dy in enumerate(range(-radius, radius + 1)):
                if max(abs(dx), abs(dy)) <= 1:
                    feature = inner_index[(dx, dy)]
                else:
                    feature = outer_index[
                        (max(abs(dx), abs(dy)), min(abs(dx), abs(dy)))
                    ]
                offset_feature[ix, iy] = feature
                counts[feature] += 1

        def transforms(x: int, y: int) -> tuple[tuple[int, int], ...]:
            return (
                (x, y),
                (-y, x),
                (-x, -y),
                (y, -x),
                (-x, y),
                (x, -y),
                (y, x),
                (-y, -x),
            )

        permutations = np.empty((8, len(keys)), dtype=np.int32)
        for transform_index in range(8):
            for feature, offset in enumerate(inner):
                permutations[transform_index, feature] = inner_index[
                    transforms(*offset)[transform_index]
                ]
            for shell, feature in outer_index.items():
                permutations[transform_index, feature] = feature
        return keys, offset_feature, counts, permutations

    @property
    def n_features(self) -> int:
        return len(self.shell_keys)

    def copy(self) -> "D4EvenLocalMLP":
        return D4EvenLocalMLP(
            self.radius,
            self.hidden,
            self.weight_in,
            self.bias_hidden,
            self.weight_out,
            feature_mode=self.feature_mode,
        )

    def parameter_payload(self) -> dict[str, np.ndarray]:
        """Return a detached, deterministic checkpoint payload."""
        return {
            "radius": np.asarray(self.radius, dtype=np.int64),
            "hidden": np.asarray(self.hidden, dtype=np.int64),
            "feature_mode": np.asarray(self.feature_mode),
            "weight_in": self.weight_in.copy(),
            "bias_hidden": self.bias_hidden.copy(),
            "weight_out": self.weight_out.copy(),
        }

    def feature_grid(self, spins: np.ndarray) -> np.ndarray:
        spins = np.asarray(spins, dtype=np.int8)
        if spins.ndim != 2 or spins.shape[0] != spins.shape[1]:
            raise ValueError("spins must be a square 2D array")
        length = spins.shape[0]
        if length < 2 * self.radius + 1:
            raise ValueError("lattice is smaller than the local receptive field")
        features = np.zeros((length, length, self.n_features), dtype=np.float64)
        for ix, dx in enumerate(range(-self.radius, self.radius + 1)):
            for iy, dy in enumerate(range(-self.radius, self.radius + 1)):
                feature = int(self.offset_feature[ix, iy])
                shifted = np.roll(spins, shift=(-dx, -dy), axis=(0, 1))
                features[:, :, feature] += shifted
        features /= self.shell_counts.reshape(1, 1, -1)
        return features

    def density_from_features(self, features: np.ndarray) -> np.ndarray:
        features = np.asarray(features, dtype=np.float64)
        if features.shape[-1] != self.n_features:
            raise ValueError("feature array has the wrong final dimension")
        flat = features.reshape(-1, self.n_features)
        density = np.zeros(flat.shape[0], dtype=np.float64)
        symmetry_count = self.feature_permutations.shape[0]
        for permutation in self.feature_permutations:
            transformed = flat[:, permutation]
            plus = np.tanh(transformed @ self.weight_in.T + self.bias_hidden)
            minus = np.tanh(-transformed @ self.weight_in.T + self.bias_hidden)
            density += 0.5 * (plus + minus) @ self.weight_out
        density /= symmetry_count
        return density.reshape(features.shape[:-1])

    def energy(self, spins: np.ndarray) -> float:
        return float(self.density_from_features(self.feature_grid(spins)).sum())

    def state_indices_from_features(self, features: np.ndarray) -> np.ndarray:
        """Encode the finite shell-sum state at every patch centre."""
        features = np.asarray(features, dtype=np.float64)
        shell_sums = np.rint(features * self.shell_counts).astype(np.int64)
        digits = (shell_sums + self.shell_counts) // 2
        if np.any(digits < 0) or np.any(digits > self.shell_counts):
            raise ValueError("features are not valid Ising shell averages")
        return np.sum(digits * self.lookup_strides, axis=-1, dtype=np.int64)

    def density_lookup_table(self) -> np.ndarray:
        """Compile the discrete local MLP into an exact finite lookup table."""
        indices = np.arange(self.lookup_size, dtype=np.int64)
        features = np.empty((self.lookup_size, self.n_features), dtype=np.float64)
        for feature, count in enumerate(self.shell_counts):
            levels = int(count) + 1
            digit = (indices // self.lookup_strides[feature]) % levels
            shell_sum = 2 * digit - int(count)
            features[:, feature] = shell_sum / float(count)
        return self.density_from_features(features)

    def gradient_from_features(self, features: np.ndarray) -> MLPGradient:
        """Return the gradient of the sum of all supplied local densities."""
        features = np.asarray(features, dtype=np.float64)
        if features.shape[-1] != self.n_features:
            raise ValueError("feature array has the wrong final dimension")
        q = features.reshape(-1, self.n_features)
        grad_out = np.zeros_like(self.weight_out)
        grad_bias = np.zeros_like(self.bias_hidden)
        grad_in = np.zeros_like(self.weight_in)
        for permutation in self.feature_permutations:
            transformed = q[:, permutation]
            z_plus = transformed @ self.weight_in.T + self.bias_hidden
            z_minus = -transformed @ self.weight_in.T + self.bias_hidden
            h_plus = np.tanh(z_plus)
            h_minus = np.tanh(z_minus)
            grad_out += 0.5 * (h_plus + h_minus).sum(axis=0)
            delta_plus = (1.0 - h_plus**2) * self.weight_out
            delta_minus = (1.0 - h_minus**2) * self.weight_out
            grad_bias += 0.5 * (delta_plus + delta_minus).sum(axis=0)
            local_grad = 0.5 * (
                delta_plus.T @ transformed - delta_minus.T @ transformed
            )
            grad_in += local_grad
        symmetry_count = self.feature_permutations.shape[0]
        grad_out /= symmetry_count
        grad_bias /= symmetry_count
        grad_in /= symmetry_count
        return MLPGradient(grad_in, grad_bias, grad_out)

    def gradient(self, spins: np.ndarray) -> MLPGradient:
        return self.gradient_from_features(self.feature_grid(spins))

    def save(self, path: str) -> None:
        np.savez_compressed(
            path,
            radius=np.asarray(self.radius, dtype=np.int64),
            hidden=np.asarray(self.hidden, dtype=np.int64),
            feature_mode=np.asarray(self.feature_mode),
            weight_in=self.weight_in,
            bias_hidden=self.bias_hidden,
            weight_out=self.weight_out,
        )

    @classmethod
    def load(cls, path: str) -> "D4EvenLocalMLP":
        with np.load(path, allow_pickle=False) as data:
            required = {"radius", "hidden", "weight_in", "bias_hidden", "weight_out"}
            missing = required.difference(data.files)
            if missing:
                raise ValueError(f"model archive is missing fields: {sorted(missing)}")
            feature_mode = (
                str(data["feature_mode"])
                if "feature_mode" in data.files
                else "shell"
            )
            return cls(
                int(data["radius"]),
                int(data["hidden"]),
                data["weight_in"],
                data["bias_hidden"],
                data["weight_out"],
                feature_mode=feature_mode,
            )


@dataclass(frozen=True)
class LocalEnergyProposal:
    x: int
    y: int
    old_spin: int
    centers_x: np.ndarray
    centers_y: np.ndarray
    feature_indices: np.ndarray
    feature_delta: np.ndarray
    new_state_index: np.ndarray | None
    new_density: np.ndarray
    delta_energy: float


class LocalEnergyCache:
    """Exact local-update cache for ``D4EvenLocalMLP``."""

    MAX_LOOKUP_STATES = 1_000_000

    def __init__(self, model: D4EvenLocalMLP, spins: np.ndarray) -> None:
        self.model = model
        self.spins = spins
        if spins.shape[0] < 2 * model.radius + 1:
            raise ValueError("lattice is smaller than the local receptive field")
        self.features = model.feature_grid(spins)
        self.refresh_model()
        radius = model.radius
        patch_offsets: list[tuple[int, int, int]] = []
        for ix, dx in enumerate(range(-radius, radius + 1)):
            for iy, dy in enumerate(range(-radius, radius + 1)):
                patch_offsets.append((dx, dy, int(model.offset_feature[ix, iy])))
        self.patch_offsets = tuple(patch_offsets)

    @property
    def energy(self) -> float:
        return float(self.density.sum())

    def refresh_model(self) -> None:
        flat = self.features.reshape(-1, self.model.n_features)
        self.z_plus = (
            flat @ self.model.weight_in.T + self.model.bias_hidden
        ).reshape(*self.features.shape[:-1], self.model.hidden)
        self.z_minus = (
            -flat @ self.model.weight_in.T + self.model.bias_hidden
        ).reshape(*self.features.shape[:-1], self.model.hidden)
        if self.model.lookup_size <= self.MAX_LOOKUP_STATES:
            self.state_index: np.ndarray | None = (
                self.model.state_indices_from_features(self.features)
            )
            self.lookup_table: np.ndarray | None = self.model.density_lookup_table()
            self.density = self.lookup_table[self.state_index]
        else:
            # Large receptive fields have an exponentially large discrete state
            # space.  Their exact local energy is evaluated directly from the
            # affected feature vectors instead of allocating an unsafe lookup.
            self.state_index = None
            self.lookup_table = None
            self.density = self.model.density_from_features(self.features)

    def force_direct_evaluation(self) -> None:
        """Disable the lookup path while retaining the exact cached features."""
        self.state_index = None
        self.lookup_table = None
        self.density = self.model.density_from_features(self.features)

    def proposal(self, x: int, y: int) -> LocalEnergyProposal:
        length = self.spins.shape[0]
        x %= length
        y %= length
        old_spin = int(self.spins[x, y])
        n_affected = len(self.patch_offsets)
        centers_x = np.empty(n_affected, dtype=np.int32)
        centers_y = np.empty(n_affected, dtype=np.int32)
        feature_indices = np.empty(n_affected, dtype=np.int32)
        feature_delta = np.empty(n_affected, dtype=np.float64)
        new_state_index = (
            np.empty(n_affected, dtype=np.int64)
            if self.state_index is not None
            else None
        )
        old_density = np.empty(n_affected, dtype=np.float64)
        for index, (dx, dy, feature) in enumerate(self.patch_offsets):
            cx = (x - dx) % length
            cy = (y - dy) % length
            delta = -2.0 * old_spin / float(self.model.shell_counts[feature])
            centers_x[index] = cx
            centers_y[index] = cy
            feature_indices[index] = feature
            feature_delta[index] = delta
            if new_state_index is not None:
                if self.state_index is None:
                    raise AssertionError("lookup state unexpectedly missing")
                new_state_index[index] = (
                    self.state_index[cx, cy]
                    - old_spin * self.model.lookup_strides[feature]
                )
            old_density[index] = self.density[cx, cy]
        if new_state_index is not None:
            if self.lookup_table is None:
                raise AssertionError("lookup table unexpectedly missing")
            new_density = self.lookup_table[new_state_index]
        else:
            proposed_features = self.features[centers_x, centers_y].copy()
            proposed_features[
                np.arange(n_affected), feature_indices
            ] += feature_delta
            new_density = self.model.density_from_features(proposed_features)
        return LocalEnergyProposal(
            x=x,
            y=y,
            old_spin=old_spin,
            centers_x=centers_x,
            centers_y=centers_y,
            feature_indices=feature_indices,
            feature_delta=feature_delta,
            new_state_index=new_state_index,
            new_density=new_density,
            delta_energy=float((new_density - old_density).sum()),
        )

    def commit(self, proposal: LocalEnergyProposal) -> None:
        if int(self.spins[proposal.x, proposal.y]) != proposal.old_spin:
            raise AssertionError("spin changed before the local cache was committed")
        for index in range(proposal.centers_x.size):
            cx = int(proposal.centers_x[index])
            cy = int(proposal.centers_y[index])
            feature = int(proposal.feature_indices[index])
            delta = float(proposal.feature_delta[index])
            self.features[cx, cy, feature] += delta
            if proposal.new_state_index is not None:
                if self.state_index is None:
                    raise AssertionError("lookup state unexpectedly missing")
                self.state_index[cx, cy] = proposal.new_state_index[index]
            self.z_plus[cx, cy] += self.model.weight_in[:, feature] * delta
            self.z_minus[cx, cy] -= self.model.weight_in[:, feature] * delta
            self.density[cx, cy] = proposal.new_density[index]

    def assert_consistent(self) -> None:
        expected_features = self.model.feature_grid(self.spins)
        np.testing.assert_allclose(self.features, expected_features, atol=1e-12, rtol=0.0)
        expected_density = self.model.density_from_features(expected_features)
        np.testing.assert_allclose(self.density, expected_density, atol=1e-12, rtol=0.0)
        if self.state_index is not None:
            np.testing.assert_array_equal(
                self.state_index,
                self.model.state_indices_from_features(expected_features),
            )
