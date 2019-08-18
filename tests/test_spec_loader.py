from pathlib import Path

import openapi_spec_validator as osv
import pytest
import pytest_mock as ptm

from axion.specification import loader
from axion.specification import parser


def test_spec_is_just_invalid(tmp_path: Path) -> None:
    spec_path = tmp_path / 'openapi.yml'
    with spec_path.open('w') as h:
        h.write("""
---
openapi: '3.0.0'
info: {}
        """)
    with pytest.raises(osv.exceptions.OpenAPIValidationError):
        loader.load_spec(spec_path)


def test_spec_load_from_path(
        spec_path: Path,
        mocker: ptm.MockFixture,
) -> None:
    parse_spec = mocker.spy(parser, 'parse_spec')
    assert loader.load_spec(spec_path) is not None
    parse_spec.assert_called_once()


def test_spec_load_from_unsupported_type(mocker: ptm.MockFixture) -> None:
    parse_spec = mocker.spy(parser, 'parse_spec')
    with pytest.raises(ValueError):
        loader.load_spec(1)  # type: ignore
    assert not parse_spec.called
