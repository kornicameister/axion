from pathlib import Path
import secrets

import pytest

SPECS = list((Path.cwd() / 'tests' / 'specifications').glob('*yml'))


@pytest.fixture
def random_spec() -> Path:
    return secrets.SystemRandom().choice(SPECS)


@pytest.fixture
def spec_path(random_spec: Path) -> Path:
    return random_spec
