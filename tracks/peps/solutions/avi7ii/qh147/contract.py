from __future__ import annotations

from dataclasses import dataclass, field
from string import ascii_letters

import autoray as ar
import quimb.tensor as qtn

from .model import obc_bonds
from .pepo import FinitePEPO
from .trotter import X, Z


@dataclass(frozen=True)
class ThermodynamicPoint:
    """Log-partition and internal-energy densities for a finite PEPO."""

    z: object
    u: object
    _partition: object | None = field(default=None, repr=False, compare=False)

    def as_floats(self) -> "ThermodynamicPoint":
        """Convert a completed diagnostic to Python floats after validation."""
        if self._partition is not None:
            partition = float(ar.do("real", self._partition))
            if partition <= 0:
                raise FloatingPointError("non-positive partition function")
        return ThermodynamicPoint(z=float(self.z), u=float(self.u))


class BoundaryContractor:
    """Boundary-MPS scalar contractions with backend-native scalar outputs."""

    def __init__(self, *, chi: int, cutoff: float) -> None:
        if chi < 1:
            raise ValueError("chi must be positive")
        if cutoff < 0:
            raise ValueError("cutoff must be non-negative")
        self.chi = chi
        self.cutoff = cutoff

    @staticmethod
    def _site_tensor(pepo: FinitePEPO, x: int, y: int):
        return pepo.tn[f"I{x},{y}"]

    @staticmethod
    def _physical_data(tensor):
        out_axis = next(
            axis for axis, ind in enumerate(tensor.inds) if ind.startswith("ko")
        )
        in_axis = next(
            axis for axis, ind in enumerate(tensor.inds) if ind.startswith("ki")
        )
        virtual_axes = tuple(
            axis
            for axis in range(tensor.ndim)
            if axis not in (out_axis, in_axis)
        )
        permutation = (out_axis, in_axis, *virtual_axes)
        data = tensor.data
        if permutation != tuple(range(tensor.ndim)):
            data = ar.do("transpose", data, axes=permutation)
        virtual_inds = tuple(tensor.inds[axis] for axis in virtual_axes)
        return data, virtual_inds

    @staticmethod
    def _einsum_labels(count: int) -> tuple[str, ...]:
        labels = tuple(label for label in ascii_letters if label not in {"o", "i"})
        if count > len(labels):
            raise ValueError("scalar tensor has too many virtual indices")
        return labels[:count]

    def _scalar_network(
        self,
        pepo: FinitePEPO,
        insertions: dict[tuple[int, int], object] | None = None,
    ) -> qtn.TensorNetwork2D:
        insertions = {} if insertions is None else insertions
        valid_sites = {
            (x, y) for x in range(pepo.lx) for y in range(pepo.ly)
        }
        if not set(insertions).issubset(valid_sites):
            raise ValueError("operator insertion lies outside the PEPO lattice")

        tensors = []
        for x in range(pepo.lx):
            for y in range(pepo.ly):
                data, virtual_inds = self._physical_data(
                    self._site_tensor(pepo, x, y)
                )
                operator = insertions.get((x, y))
                if operator is None:
                    scalar_data = ar.do("trace", data, axis1=0, axis2=1)
                else:
                    operator = ar.do("asarray", operator, like=data)
                    labels = "".join(self._einsum_labels(len(virtual_inds)))
                    scalar_data = ar.do(
                        "einsum",
                        f"oi{labels},io->{labels}",
                        data,
                        operator,
                    )
                tensors.append(
                    qtn.Tensor(
                        scalar_data,
                        inds=virtual_inds,
                        tags={f"I{x},{y}"},
                    )
                )

        network = qtn.TensorNetwork(tensors)
        return qtn.TensorNetwork2D.from_TN(
            network,
            site_tag_id="I{},{}",
            x_tag_id="X{}",
            y_tag_id="Y{}",
            Lx=pepo.lx,
            Ly=pepo.ly,
        )

    def _contract(self, network: qtn.TensorNetwork2D):
        return network.contract_boundary(
            max_bond=self.chi,
            cutoff=self.cutoff,
            canonize=True,
        )

    def trace(self, pepo: FinitePEPO):
        return self._contract(self._scalar_network(pepo))

    def expectation_numerator(
        self,
        pepo: FinitePEPO,
        insertions: dict[tuple[int, int], object],
    ):
        return self._contract(self._scalar_network(pepo, insertions))

    def _double_layer_network(
        self,
        bra: FinitePEPO,
        ket: FinitePEPO,
        *,
        conjugate_bra: bool,
        swap_ket_physical: bool,
    ) -> qtn.TensorNetwork2D:
        if (bra.lx, bra.ly) != (ket.lx, ket.ly):
            raise ValueError("bra and ket must have matching lattice extents")

        tensors = []
        for x in range(bra.lx):
            for y in range(bra.ly):
                bra_data, bra_virtual = self._physical_data(
                    self._site_tensor(bra, x, y)
                )
                ket_data, ket_virtual = self._physical_data(
                    self._site_tensor(ket, x, y)
                )
                if conjugate_bra:
                    bra_data = ar.do("conj", bra_data)
                bra_labels = self._einsum_labels(len(bra_virtual))
                ket_labels = self._einsum_labels(
                    len(bra_virtual) + len(ket_virtual)
                )[len(bra_virtual) :]
                left_virtual = "".join(bra_labels)
                right_virtual = "".join(ket_labels)
                right_physical = "io" if swap_ket_physical else "oi"
                data = ar.do(
                    "einsum",
                    (
                        f"oi{left_virtual},{right_physical}{right_virtual}"
                        f"->{left_virtual}{right_virtual}"
                    ),
                    bra_data,
                    ket_data,
                )
                inds = (
                    *(f"bra:{ind}" for ind in bra_virtual),
                    *(f"ket:{ind}" for ind in ket_virtual),
                )
                tensors.append(qtn.Tensor(data, inds=inds, tags={f"I{x},{y}"}))

        network = qtn.TensorNetwork(tensors)
        return qtn.TensorNetwork2D.from_TN(
            network,
            site_tag_id="I{},{}",
            x_tag_id="X{}",
            y_tag_id="Y{}",
            Lx=bra.lx,
            Ly=bra.ly,
        )

    def overlap(self, bra: FinitePEPO, ket: FinitePEPO):
        network = self._double_layer_network(
            bra,
            ket,
            conjugate_bra=True,
            swap_ket_physical=False,
        )
        return self._contract(network)

    def _trace_operator_product(self, left: FinitePEPO, right: FinitePEPO):
        network = self._double_layer_network(
            left,
            right,
            conjugate_bra=False,
            swap_ket_physical=True,
        )
        return self._contract(network)

    def relative_frobenius_loss(self, student: FinitePEPO, teacher: FinitePEPO):
        student_norm = ar.do("real", self.overlap(student, student))
        teacher_norm = ar.do("real", self.overlap(teacher, teacher))
        cross = ar.do("real", self.overlap(student, teacher))
        return (student_norm + teacher_norm - 2 * cross) / teacher_norm

    def thermodynamic_point(
        self,
        pepo: FinitePEPO,
        *,
        j: float,
        h: float,
        log_scale: object,
    ) -> ThermodynamicPoint:
        partition = self.trace(pepo)
        energy_numerator = 0
        for first, second in obc_bonds(pepo.lx, pepo.ly):
            first_xy = divmod(first, pepo.ly)
            second_xy = divmod(second, pepo.ly)
            energy_numerator = energy_numerator - j * self.expectation_numerator(
                pepo,
                {first_xy: Z, second_xy: Z},
            )
        for site in range(pepo.lx * pepo.ly):
            energy_numerator = energy_numerator - h * self.expectation_numerator(
                pepo,
                {divmod(site, pepo.ly): X},
            )

        nsites = pepo.lx * pepo.ly
        real_partition = ar.do("real", partition)
        z = (log_scale + ar.do("log", real_partition)) / nsites
        u = ar.do("real", energy_numerator / partition) / nsites
        return ThermodynamicPoint(z=z, u=u, _partition=partition)

    def hermiticity_residual(self, pepo: FinitePEPO):
        norm_squared = ar.do("real", self.overlap(pepo, pepo))
        trace_squared = ar.do(
            "real", self._trace_operator_product(pepo, pepo)
        )
        residual_squared = ar.do(
            "maximum",
            2 * (norm_squared - trace_squared),
            0.0,
        )
        return ar.do("sqrt", residual_squared) / ar.do("sqrt", norm_squared)
