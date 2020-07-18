from pathlib import Path
import typing as t

from _pytest import fixtures
import mock
import pytest
import pytest_mock as ptm

import axion
from axion.oas import model


@pytest.fixture(params=['aiohttp'])
def mocked_plugin(
    request: fixtures.SubRequest,
    mocker: ptm.MockFixture,
) -> t.Generator[t.Tuple[str, mock.Mock], None, None]:
    plugin = mocker.Mock()
    plugin_type = mocker.Mock(side_effect=lambda _: plugin)

    _plugins = mocker.patch(
        'axion._plugins',
        return_value={request.param: plugin_type},
    )

    yield request.param, plugin

    _plugins.assert_called_once()


def test_correct_init(
    mocked_plugin: t.Tuple[str, mock.Mock],
    mocker: ptm.MockFixture,
) -> None:
    plugin_id, plugin = mocked_plugin

    axion_app = axion.Axion(
        root_dir=Path.cwd(),
        configuration=mocker.ANY,
        plugin_id=plugin_id,
    )

    assert axion_app.plugin_id == plugin_id
    assert axion_app.plugged == plugin


@pytest.mark.parametrize(
    'base_path',
    (
        '/',
        '/test',
        '/a/b/c',
        None,
    ),
)
def test_add_api_single_server(
    mocked_plugin: t.Tuple[str, mock.Mock],
    base_path: t.Optional[str],
    mocker: ptm.MockFixture,
    tmp_path: Path,
) -> None:
    plugin_id, plugin = mocked_plugin

    spec_location = tmp_path / 'openapi.yaml'

    loaded_spec = mocker.stub()
    loaded_spec.servers = [model.OASServer(
        url=mocker.ANY,
        variables={},
    )]

    spec_load = mocker.patch(
        'axion.load_specification',
        return_value=loaded_spec,
    )

    the_app = axion.Axion(
        root_dir=Path.cwd(),
        configuration=mocker.ANY,
        plugin_id=plugin_id,
    )
    assert the_app.plugin_id == plugin_id
    assert the_app.plugged == plugin

    the_app.add_api(spec_location, server_base_path=base_path)

    spec_load.assert_called_once_with(spec_location, None)
    plugin.add_api.assert_called_once_with(
        spec=loaded_spec,
        base_path=base_path,
    )


@pytest.mark.parametrize(
    'base_path',
    (
        '/',
        '/test',
        '/a/b/c',
        None,
    ),
)
def test_add_api_relative_spec_path(
    base_path: t.Optional[str],
    mocked_plugin: t.Tuple[str, mock.Mock],
    mocker: ptm.MockFixture,
) -> None:
    plugin_id, plugin = mocked_plugin

    spec = mocker.Mock()
    spec.servers = [
        model.OASServer(url=mocker.ANY, variables={}),
    ]

    actual_spec_path = Path('../tests/specifications/simple.yml')
    expected_spec_path = (Path.cwd() / actual_spec_path).resolve()

    spec_load = mocker.patch(
        'axion.load_specification',
        return_value=spec,
    )

    the_app = axion.Axion(
        root_dir=Path.cwd(),
        configuration=mocker.ANY,
        plugin_id=plugin_id,
    )
    assert the_app.plugin_id == plugin_id
    assert the_app.plugged == plugin

    the_app.add_api(actual_spec_path, server_base_path=base_path)

    spec_load.assert_called_once_with(expected_spec_path, None)
    plugin.add_api.assert_called_once_with(
        spec=spec,
        base_path=base_path,
    )
