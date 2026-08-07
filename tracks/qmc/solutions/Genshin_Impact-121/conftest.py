def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "slow: marks stochastic end-to-end tests excluded from the default suite",
    )
