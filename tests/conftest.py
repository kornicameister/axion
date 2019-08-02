from pathlib import Path
import random
import typing as t

import pytest
import yaml

SPECS = list((Path.cwd() / 'tests' / 'specs').glob('*yml'))


@pytest.fixture
def random_spec() -> Path:
    return random.choice(SPECS)


@pytest.fixture
def spec_path(random_spec: Path) -> Path:
    return random_spec


@pytest.fixture
def spec_dict(random_spec: Path) -> t.Dict[str, t.Any]:
    with random_spec.open('r') as handler:
        spec: t.Dict[str, t.Any] = yaml.safe_load(handler)
    return spec
