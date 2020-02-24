import pytest


@pytest.fixture(
    scope='session',
    autouse=True,
)
def axion_plugins() -> None:
    from axion import _plugins

    _plugins()
