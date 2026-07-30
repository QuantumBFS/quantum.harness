"""Fixed COPY and pair-factor tensors for the N-queens partition function."""

from .tensor import SparseTensor


def _endpoint_label(row: int, other: int) -> str:
    low, high = sorted((row, other))
    endpoint = "lo" if row == low else "hi"
    return f"edge_{low}_{high}_{endpoint}"


def _leaf_tree(
    name: str, kind: str, labels: tuple[str, ...], nnz: int
) -> dict[str, object]:
    return {
        "type": "leaf",
        "name": name,
        "tensor_kind": kind,
        "indices": list(labels),
        "nnz": nnz,
    }


def copy_tensor(row: int, n: int) -> SparseTensor:
    labels = tuple(
        _endpoint_label(row, other) for other in range(n) if other != row
    )
    dimensions = (n,) * len(labels)
    if labels:
        data = {(column,) * len(labels): 1 for column in range(n)}
    else:
        data = {(): 1}
    name = f"COPY_{row}"
    return SparseTensor(
        name=name,
        labels=labels,
        dimensions=dimensions,
        data=data,
        tree=_leaf_tree(name, "COPY", labels, len(data)),
    )


def pair_factor(row_a: int, row_b: int, n: int) -> SparseTensor:
    if row_a >= row_b:
        raise ValueError("pair factors require row_a < row_b")
    labels = (
        _endpoint_label(row_a, row_b),
        _endpoint_label(row_b, row_a),
    )
    row_distance = row_b - row_a
    data = {
        (column_a, column_b): 1
        for column_a in range(n)
        for column_b in range(n)
        if column_a != column_b
        and abs(column_a - column_b) != row_distance
    }
    name = f"PAIR_{row_a}_{row_b}"
    return SparseTensor(
        name=name,
        labels=labels,
        dimensions=(n, n),
        data=data,
        tree=_leaf_tree(name, "PAIR", labels, len(data)),
    )


def build_pair_factor_network(n: int) -> list[SparseTensor]:
    if n < 1:
        raise ValueError("the algebraic network requires n >= 1")
    tensors = [copy_tensor(row, n) for row in range(n)]
    tensors.extend(
        pair_factor(row_a, row_b, n)
        for row_a in range(n)
        for row_b in range(row_a + 1, n)
    )
    appearances: dict[str, int] = {}
    for tensor in tensors:
        for label in tensor.labels:
            appearances[label] = appearances.get(label, 0) + 1
    if any(count != 2 for count in appearances.values()):
        raise AssertionError("every tensor-network index must appear exactly twice")
    return tensors


def build_copy_absorbed_network(n: int) -> list[SparseTensor]:
    """Return the exact factor hypergraph after applying the COPY identity."""
    if n < 1:
        raise ValueError("the algebraic network requires n >= 1")
    tensors: list[SparseTensor] = []
    for row in range(n):
        label = f"column_{row}"
        name = f"ONE_{row}"
        data = {(column,): 1 for column in range(n)}
        tensors.append(
            SparseTensor(
                name=name,
                labels=(label,),
                dimensions=(n,),
                data=data,
                tree=_leaf_tree(name, "ONE", (label,), len(data)),
            )
        )
    for row_a in range(n):
        for row_b in range(row_a + 1, n):
            labels = (f"column_{row_a}", f"column_{row_b}")
            distance = row_b - row_a
            data = {
                (column_a, column_b): 1
                for column_a in range(n)
                for column_b in range(n)
                if column_a != column_b
                and abs(column_a - column_b) != distance
            }
            name = f"PAIR_{row_a}_{row_b}"
            tensors.append(
                SparseTensor(
                    name=name,
                    labels=labels,
                    dimensions=(n, n),
                    data=data,
                    tree=_leaf_tree(name, "PAIR", labels, len(data)),
                )
            )
    scalar_name = "SCALAR_ONE"
    tensors.append(
        SparseTensor(
            name=scalar_name,
            labels=(),
            dimensions=(),
            data={(): 1},
            tree=_leaf_tree(scalar_name, "SCALAR", (), 1),
        )
    )
    return tensors
