"""Static cost analysis for differentiated tensor contractions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import prod

import opt_einsum as oe

from vqetape.tn_program import ContractionStep
from vqetape.spatial_plan import SpatialTransferProgram


@dataclass(frozen=True)
class DifferentiatedContractionCost:
    """Forward, reverse, traffic, and residual cost for one program."""

    forward_flops: int
    backward_flops: int
    forward_read_elements: int
    forward_write_elements: int
    backward_read_elements: int
    backward_write_elements: int
    residual_elements: int
    peak_live_residual_elements: int
    largest_forward_intermediate_elements: int
    largest_backward_intermediate_elements: int
    forward_contractions: int
    backward_contractions: int

    @property
    def total_flops(self) -> int:
        return self.forward_flops + self.backward_flops

    @property
    def traffic_elements(self) -> int:
        return (
            self.forward_read_elements
            + self.forward_write_elements
            + self.backward_read_elements
            + self.backward_write_elements
        )

    def to_dict(self) -> dict[str, int]:
        payload = asdict(self)
        payload["total_flops"] = self.total_flops
        payload["traffic_elements"] = self.traffic_elements
        return payload


@dataclass(frozen=True)
class ReverseStep:
    """One einsum used to transpose a forward contraction input."""

    forward_step_index: int
    input_index: int
    equation: str
    input_shapes: tuple[tuple[int, ...], ...]
    output_shape: tuple[int, ...]
    flops: int
    largest_intermediate_elements: int


@dataclass(frozen=True)
class SpatialDifferentiatedCost:
    """Differentiated cost aggregated over a spatial recurrence."""

    first: DifferentiatedContractionCost
    bulk: DifferentiatedContractionCost | None
    tail: DifferentiatedContractionCost | None
    last: DifferentiatedContractionCost
    bulk_block_count: int
    dtype_bytes: int

    def _sum_metric(self, name: str) -> int:
        return (
            int(getattr(self.first, name))
            + self.bulk_block_count
            * (
                int(getattr(self.bulk, name))
                if self.bulk is not None
                else 0
            )
            + (
                int(getattr(self.tail, name))
                if self.tail is not None
                else 0
            )
            + int(getattr(self.last, name))
        )

    @property
    def peak_role_residual_elements(self) -> int:
        return max(
            item.peak_live_residual_elements
            for item in (
                self.first,
                self.bulk,
                self.tail,
                self.last,
            )
            if item is not None
        )

    @property
    def total_forward_flops(self) -> int:
        return self._sum_metric("forward_flops")

    @property
    def total_backward_flops(self) -> int:
        return self._sum_metric("backward_flops")

    @property
    def total_traffic_elements(self) -> int:
        return self._sum_metric("traffic_elements")

    @property
    def total_traffic_bytes(self) -> int:
        return self.total_traffic_elements * self.dtype_bytes

    @property
    def static_score(self) -> int:
        return (
            self.total_forward_flops
            + self.total_backward_flops
            + 4 * self.total_traffic_elements
            + 16 * self.peak_role_residual_elements
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "total_forward_flops": self.total_forward_flops,
            "total_backward_flops": self.total_backward_flops,
            "total_flops": (
                self.total_forward_flops
                + self.total_backward_flops
            ),
            "total_traffic_elements": self.total_traffic_elements,
            "total_traffic_bytes": self.total_traffic_bytes,
            "peak_role_residual_elements": (
                self.peak_role_residual_elements
            ),
            "static_score": self.static_score,
            "bulk_block_count": self.bulk_block_count,
            "dtype_bytes": self.dtype_bytes,
            "roles": {
                "first": self.first.to_dict(),
                "bulk": (
                    self.bulk.to_dict()
                    if self.bulk is not None
                    else None
                ),
                "tail": (
                    self.tail.to_dict()
                    if self.tail is not None
                    else None
                ),
                "last": self.last.to_dict(),
            },
        }


def _parse_equation(
    equation: str,
) -> tuple[tuple[str, ...], str]:
    try:
        left, output = equation.split("->", maxsplit=1)
    except ValueError as exc:
        raise ValueError(
            "einsum equation must contain an explicit output"
        ) from exc
    return tuple(left.split(",")), output


def reverse_einsum_equation(
    forward_equation: str,
    input_index: int,
) -> str:
    """Return the einsum that transposes one forward input."""

    inputs, output = _parse_equation(forward_equation)
    if input_index < 0 or input_index >= len(inputs):
        raise ValueError("reverse input index is out of range")
    parts = (output,) + tuple(
        subscript
        for index, subscript in enumerate(inputs)
        if index != input_index
    )
    return ",".join(parts) + "->" + inputs[input_index]


def _symbol_dimensions(
    subscripts: tuple[str, ...],
    shapes: tuple[tuple[int, ...], ...],
) -> dict[str, int]:
    if len(subscripts) != len(shapes):
        raise ValueError(
            "einsum operand count does not match shapes"
        )
    dimensions: dict[str, int] = {}
    for subscript, shape in zip(
        subscripts,
        shapes,
        strict=True,
    ):
        if len(subscript) != len(shape):
            raise ValueError(
                "einsum subscript rank does not match shape"
            )
        for symbol, extent in zip(
            subscript,
            shape,
            strict=True,
        ):
            previous = dimensions.setdefault(symbol, extent)
            if previous != extent:
                raise ValueError(
                    f"inconsistent extent for einsum symbol {symbol}"
                )
    return dimensions


def _output_shape(
    equation: str,
    shapes: tuple[tuple[int, ...], ...],
) -> tuple[int, ...]:
    inputs, output = _parse_equation(equation)
    dimensions = _symbol_dimensions(inputs, shapes)
    try:
        return tuple(dimensions[symbol] for symbol in output)
    except KeyError as exc:
        raise ValueError(
            "einsum output contains an unknown symbol"
        ) from exc


def _einsum_cost(
    equation: str,
    shapes: tuple[tuple[int, ...], ...],
) -> tuple[int, int]:
    try:
        _, info = oe.contract_path(
            equation,
            *shapes,
            shapes=True,
            optimize="greedy",
        )
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError(
            f"cannot analyze einsum equation {equation!r}"
        ) from exc
    return int(info.opt_cost), int(info.largest_intermediate)


def analyze_contraction_steps(
    input_shapes: tuple[tuple[int, ...], ...],
    steps: tuple[ContractionStep, ...],
) -> tuple[
    DifferentiatedContractionCost,
    tuple[tuple[ReverseStep, ...], ...],
]:
    """Analyze serialized forward steps and their generated VJPs."""

    if not input_shapes:
        raise ValueError("contraction requires at least one input")
    if not steps:
        raise ValueError("contraction requires at least one step")

    active_shapes = list(input_shapes)
    forward_flops = 0
    backward_flops = 0
    forward_read = 0
    forward_write = 0
    backward_read = 0
    backward_write = 0
    largest_forward = 0
    largest_backward = 0
    reverse_groups: list[tuple[ReverseStep, ...]] = []
    output_elements: list[int] = []

    for step_index, step in enumerate(steps):
        try:
            selected_shapes = tuple(
                active_shapes.pop(position)
                for position in step.positions
            )
        except IndexError as exc:
            raise ValueError(
                "contraction step position is out of range"
            ) from exc
        input_subscripts, _ = _parse_equation(step.einsum)
        if len(input_subscripts) != len(selected_shapes):
            raise ValueError(
                "contraction step equation does not match operands"
            )
        result_shape = _output_shape(
            step.einsum,
            selected_shapes,
        )
        result_elements = prod(result_shape)
        if result_elements != step.output_elements:
            raise ValueError(
                "contraction step output size is inconsistent"
            )
        step_flops, step_largest = _einsum_cost(
            step.einsum,
            selected_shapes,
        )
        forward_flops += step_flops
        forward_read += sum(
            prod(shape) for shape in selected_shapes
        )
        forward_write += result_elements
        largest_forward = max(
            largest_forward,
            step_largest,
            result_elements,
        )

        reverse_steps: list[ReverseStep] = []
        for input_index, input_shape in enumerate(
            selected_shapes
        ):
            equation = reverse_einsum_equation(
                step.einsum,
                input_index,
            )
            reverse_shapes = (
                result_shape,
                *(
                    shape
                    for index, shape in enumerate(
                        selected_shapes
                    )
                    if index != input_index
                ),
            )
            reverse_flops, reverse_largest = _einsum_cost(
                equation,
                reverse_shapes,
            )
            expected_shape = _output_shape(
                equation,
                reverse_shapes,
            )
            if expected_shape != input_shape:
                raise ValueError(
                    "reverse contraction output shape is inconsistent"
                )
            backward_flops += reverse_flops
            backward_read += sum(
                prod(shape) for shape in reverse_shapes
            )
            backward_write += prod(input_shape)
            largest_backward = max(
                largest_backward,
                reverse_largest,
                prod(input_shape),
            )
            reverse_steps.append(
                ReverseStep(
                    forward_step_index=step_index,
                    input_index=input_index,
                    equation=equation,
                    input_shapes=reverse_shapes,
                    output_shape=input_shape,
                    flops=reverse_flops,
                    largest_intermediate_elements=(
                        reverse_largest
                    ),
                )
            )
        reverse_groups.append(tuple(reverse_steps))
        output_elements.append(result_elements)
        active_shapes.append(result_shape)

    if len(active_shapes) != 1:
        raise ValueError(
            "contraction steps did not produce one output"
        )

    residual_elements = (
        sum(prod(shape) for shape in input_shapes)
        + sum(output_elements[:-1])
    )
    cost = DifferentiatedContractionCost(
        forward_flops=forward_flops,
        backward_flops=backward_flops,
        forward_read_elements=forward_read,
        forward_write_elements=forward_write,
        backward_read_elements=backward_read,
        backward_write_elements=backward_write,
        residual_elements=residual_elements,
        peak_live_residual_elements=residual_elements,
        largest_forward_intermediate_elements=largest_forward,
        largest_backward_intermediate_elements=largest_backward,
        forward_contractions=len(steps),
        backward_contractions=sum(
            len(group) for group in reverse_groups
        ),
    )
    return cost, tuple(reverse_groups)


def analyze_spatial_transfer(
    transfer: SpatialTransferProgram,
) -> SpatialDifferentiatedCost:
    """Aggregate differentiated costs for all spatial program roles."""

    def analyze(program):
        if program is None:
            return None
        cost, _ = analyze_contraction_steps(
            program.input_shapes,
            program.steps,
        )
        return cost

    return SpatialDifferentiatedCost(
        first=analyze(transfer.first),
        bulk=analyze(transfer.bulk),
        tail=analyze(transfer.tail),
        last=analyze(transfer.last),
        bulk_block_count=transfer.bulk_block_count,
        dtype_bytes=(
            8 if transfer.spec.dtype == "complex64" else 16
        ),
    )
