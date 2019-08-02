from pathlib import Path
import typing as t

import openapi_spec_validator as osv
import pytest
import pytest_mock as ptm

from axion import spec


def test_spec_is_just_invalid(tmp_path: Path) -> None:
    spec_path = tmp_path / 'openapi.yml'
    with spec_path.open('w') as h:
        h.write("""
---
openapi: '3.0.0'
info: {}
        """)
    with pytest.raises(osv.exceptions.OpenAPIValidationError):
        spec.load(spec_path)


def test_spec_load_from_path(
        spec_path: Path,
        mocker: ptm.MockFixture,
) -> None:
    parse_spec = mocker.spy(spec, '_parse_spec')
    assert spec.load(spec_path) is not None
    parse_spec.assert_called_once()


def test_spec_load_from_unsupported_type(mocker: ptm.MockFixture) -> None:
    parse_spec = mocker.spy(spec, '_parse_spec')
    with pytest.raises(ValueError):
        spec.load(1)  # type: ignore
    assert not parse_spec.called


def test_spec_render_complex_schema() -> None:
    the_spec = spec.load(Path('tests/specs/complex.yml'))

    assert the_spec.raw_spec
    assert len(the_spec.operations) == 4
