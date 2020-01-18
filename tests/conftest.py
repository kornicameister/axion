import logging
from pathlib import Path
import secrets
import typing as t

from _pytest import logging as _logging
from loguru import logger
import pytest

SPECS = list((Path.cwd() / 'tests' / 'specifications').glob('*yml'))


@pytest.fixture
def random_spec() -> Path:
    return secrets.SystemRandom().choice(SPECS)


@pytest.fixture
def spec_path(random_spec: Path) -> Path:
    return random_spec


@pytest.fixture(autouse=True)
def clean_plugins() -> t.Generator[None, None, None]:
    from axion.plugin import PluginMeta
    yield
    PluginMeta.all_known_plugins = {}


@pytest.fixture
def caplog(caplog: _logging.LogCaptureFixture) -> _logging.LogCaptureFixture:
    class LoguruHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logging.getLogger(record.name).handle(record)

    logger.add(
        LoguruHandler(),
        format='{message}',
    )
    yield caplog
