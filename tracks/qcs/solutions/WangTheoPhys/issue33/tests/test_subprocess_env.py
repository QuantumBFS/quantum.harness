from vqetape.subprocess_env import worker_environment


def test_worker_environment_defaults_to_highest_matmul_precision(
    monkeypatch,
):
    monkeypatch.delenv(
        "JAX_DEFAULT_MATMUL_PRECISION",
        raising=False,
    )

    environment = worker_environment()

    assert (
        environment["JAX_DEFAULT_MATMUL_PRECISION"]
        == "highest"
    )


def test_worker_environment_preserves_explicit_precision(
    monkeypatch,
):
    monkeypatch.setenv(
        "JAX_DEFAULT_MATMUL_PRECISION",
        "default",
    )

    environment = worker_environment()

    assert (
        environment["JAX_DEFAULT_MATMUL_PRECISION"]
        == "default"
    )
