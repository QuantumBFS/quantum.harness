import jax


def test_jax_x64_can_be_enabled() -> None:
    jax.config.update("jax_enable_x64", True)
    assert jax.config.x64_enabled
    assert jax.devices()
