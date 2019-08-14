from pathlib import Path

import pytest
import pytest_mock as ptm

from axion import app


def test_app_init(mocker: ptm.MockFixture, tmp_path: Path) -> None:
    loaded_spec = mocker.stub()
    spec_load = mocker.patch('axion.spec.load', return_value=loaded_spec)
    spec_location = tmp_path / 'openapi.yaml'

    the_app = app.Application(spec_location=spec_location)

    spec_load.assert_called_once_with(spec_location)

    assert the_app.spec == loaded_spec
    assert the_app.spec_location == spec_location


def test_app_no_override() -> None:
    with pytest.raises(TypeError):

        class NoNo(app.Application):  # type: ignore
            ...
