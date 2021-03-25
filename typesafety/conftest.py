import logging

import pytest

logging.getLogger('openapi_spec_validator').setLevel(logging.ERROR)


@pytest.fixture(scope='session', autouse=True)
def axion_plugins() -> None:
    from axion import _plugins

    _plugins()
