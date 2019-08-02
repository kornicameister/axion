from pathlib import Path
import typing as t

import openapi_spec_validator as osv
import pytest
import pytest_mock as ptm

from axion import spec


def test_spec_load_from_dict(
        spec_dict: t.Dict[str, t.Any],
        mocker: ptm.MockFixture,
) -> None:
    via_dict = mocker.spy(spec, '_via_dict')
    via_path = mocker.spy(spec, '_via_path')

    value = spec.load(spec_dict)

    assert value is not None
    via_dict.assert_called_once()
    assert not via_path.called


def test_spec_invalid_version() -> None:
    with pytest.raises(spec.UnsupportedSpecVersion):
        spec.load({
            'openapi': '2.9.9',
        })


def test_spec_is_just_invalid() -> None:
    with pytest.raises(osv.exceptions.OpenAPIValidationError):
        spec.load({
            'openapi': '3.0.0',
            'info': {},
        })


def test_spec_load_from_path(
        spec_path: Path,
        mocker: ptm.MockFixture,
) -> None:
    via_dict = mocker.spy(spec, '_via_dict')
    via_path = mocker.spy(spec, '_via_path')

    value = spec.load(spec_path)

    assert value is not None
    via_dict.assert_called_once()
    via_path.assert_called_once()


def test_spec_load_from_unsupported_type(mocker: ptm.MockFixture) -> None:
    via_dict = mocker.spy(spec, '_via_dict')
    via_path = mocker.spy(spec, '_via_path')

    with pytest.raises(ValueError):
        spec.load(1)  # type: ignore

    assert not via_dict.called
    assert not via_path.called
