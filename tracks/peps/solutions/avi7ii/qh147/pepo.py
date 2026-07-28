from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import quimb.tensor as qtn

from .trotter import Gate


@dataclass
class FinitePEPO:
    lx: int
    ly: int
    tn: qtn.TensorNetwork

    @classmethod
    def identity(cls, lx: int, ly: int) -> "FinitePEPO":
        tensors = []
        for x in range(lx):
            for y in range(ly):
                virtual = []
                if x > 0:
                    virtual.append(f"hx{x - 1},{y}")
                if x + 1 < lx:
                    virtual.append(f"hx{x},{y}")
                if y > 0:
                    virtual.append(f"vy{x},{y - 1}")
                if y + 1 < ly:
                    virtual.append(f"vy{x},{y}")
                data = np.eye(2).reshape((2, 2) + (1,) * len(virtual))
                tensors.append(
                    qtn.Tensor(
                        data,
                        inds=(f"ko{x},{y}", f"ki{x},{y}", *virtual),
                        tags={f"I{x},{y}", "PEPO"},
                    )
                )
        return cls(lx=lx, ly=ly, tn=qtn.TensorNetwork(tensors))

    def copy(self) -> "FinitePEPO":
        return FinitePEPO(self.lx, self.ly, self.tn.copy())

    def adjoint(self) -> "FinitePEPO":
        result = self.copy()
        for tensor in result.tn.tensors:
            out_axis = next(
                axis
                for axis, ind in enumerate(tensor.inds)
                if ind.startswith("ko")
            )
            in_axis = next(
                axis
                for axis, ind in enumerate(tensor.inds)
                if ind.startswith("ki")
            )
            tensor.modify(
                data=np.swapaxes(
                    np.asarray(tensor.data).conj(),
                    out_axis,
                    in_axis,
                ),
                inds=tensor.inds,
            )
        return result

    def _coords(self, site: int) -> tuple[int, int]:
        return divmod(site, self.ly)

    def out_ind(self, site: int) -> str:
        x, y = self._coords(site)
        return f"ko{x},{y}"

    def in_ind(self, site: int) -> str:
        x, y = self._coords(site)
        return f"ki{x},{y}"

    def apply_gate(self, gate: Gate, *, max_bond: int) -> None:
        out_inds = tuple(self.out_ind(site) for site in gate.sites)
        contract = True if len(out_inds) == 1 else "split"
        self.tn.gate_inds_(
            gate.matrix,
            out_inds,
            contract=contract,
            max_bond=max_bond,
            cutoff=0.0,
        )

    def to_dense(self) -> np.ndarray:
        out_inds = tuple(
            self.out_ind(site) for site in range(self.lx * self.ly)
        )
        in_inds = tuple(
            self.in_ind(site) for site in range(self.lx * self.ly)
        )
        return np.asarray(self.tn.to_dense(out_inds, in_inds))

    def renormalize_tensors(self) -> float:
        removed_log_scale = 0.0
        for tensor in self.tn.tensors:
            scale = float(np.max(np.abs(tensor.data)))
            if not np.isfinite(scale) or scale <= 0:
                raise FloatingPointError("invalid PEPO tensor scale")
            tensor.modify(data=tensor.data / scale)
            removed_log_scale += np.log(scale)
        return removed_log_scale
