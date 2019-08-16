from pathlib import Path
import typing as t

import pytest
import pytest_mock as ptm

from axion import app
from axion.spec import model


def test_app_init(
        mocker: ptm.MockFixture,
        tmp_path: Path,
) -> None:
    single_server = model.OASServer(
        url='/',
        variables={},
    )
    loaded_spec = mocker.stub()
    loaded_spec.servers = [single_server]

    spec_load = mocker.patch(
        'axion.spec.load',
        return_value=loaded_spec,
    )
    apply_spec = mocker.patch('axion.app._apply_specification')

    spec_location = tmp_path / 'openapi.yaml'

    the_app = app.Application(root_dir=Path.cwd())
    the_app.add_api(spec_location)

    spec_load.assert_called_once_with(spec_location)
    apply_spec.assert_called_once_with(
        for_app=the_app.root_app,
        specification=loaded_spec,
    )

    assert the_app.root_dir == Path.cwd()
    assert len(the_app.root_app._subapps) == 0
    assert len(the_app.api_base_paths) == 1


@pytest.mark.parametrize(
    'server_url',
    ('/', '/v1', '/api'),
)
def test_app_multiple_add_apis(
        server_url: str,
        mocker: ptm.MockFixture,
        tmp_path: Path,
) -> None:
    spec_one = mocker.Mock()
    spec_one.servers = [model.OASServer(url=server_url, variables={})]
    spec_one_path = tmp_path / 'openapi_1.yml'

    spec_two = mocker.Mock()
    spec_two.servers = [model.OASServer(url=server_url, variables={})]
    spec_two_path = tmp_path / 'openapi_2.yml'

    def spec_load_side_effect(path: Path) -> ptm.Mock:
        return spec_one if path == spec_one_path else spec_two

    spec_load = mocker.patch(
        'axion.spec.load',
        side_effect=spec_load_side_effect,
    )
    apply_spec = mocker.patch('axion.app._apply_specification')

    the_app = app.Application(root_dir=Path.cwd())
    the_app.add_api(spec_one_path)
    with pytest.raises(app.DuplicateBasePath):
        the_app.add_api(spec_two_path)

    spec_load.assert_any_call(spec_one_path)
    spec_load.assert_any_call(spec_two_path)

    if server_url == '/':
        apply_spec.assert_called_once_with(
            for_app=the_app.root_app,
            specification=spec_one,
        )
    else:
        # if we are adding onto the different base path
        # and there's a duplicate assume that last added
        # app got the proper load
        apply_spec.assert_called_once_with(
            for_app=the_app.root_app._subapps[-1],
            specification=spec_one,
        )


def test_app_overlapping_base_paths(
        mocker: ptm.MockFixture,
        tmp_path: Path,
) -> None:
    spec_one = mocker.Mock()
    spec_one.servers = [model.OASServer(url='/', variables={})]
    spec_one_path = tmp_path / 'openapi_1.yml'

    spec_two = mocker.Mock()
    spec_two.servers = [model.OASServer(url='/v1', variables={})]
    spec_two_path = tmp_path / 'openapi_2.yml'

    def spec_load_side_effect(path: Path) -> t.Any:
        return spec_one if path == spec_one_path else spec_two

    spec_load = mocker.patch(
        'axion.spec.load',
        side_effect=spec_load_side_effect,
    )
    apply_spec = mocker.patch('axion.app._apply_specification')

    the_app = app.Application(root_dir=Path.cwd())
    the_app.add_api(spec_one_path)
    with pytest.raises(app.OverlappingBasePath):
        the_app.add_api(spec_two_path)

    spec_load.assert_any_call(spec_one_path)
    spec_load.assert_any_call(spec_two_path)

    apply_spec.assert_called_once_with(
        for_app=the_app.root_app,
        specification=spec_one,
    )


def _test_app_build_routes() -> None:
    spec_location = Path('tests/specifications/complex.yml')
    the_app = app.Application(root_dir=Path.cwd())
    the_app.add_api(spec_location)


@pytest.mark.parametrize(('url', 'variables', 'expected_base_path'), (
    (
        '/',
        {},
        '/',
    ),
    (
        'https://example.org/',
        {},
        '/',
    ),
    (
        '/v{api_version}',
        {
            'api_version': '1',
        },
        '/v1',
    ),
    (
        'https://example.org/v{api_version}',
        {
            'api_version': '1',
        },
        '/v1',
    ),
    (
        '{protocol}://example.org:{port}/v{api_version}',
        {
            'api_version': '1',
            'port': '443',
            'protocol': 'https',
        },
        '/v1',
    ),
))
def test_app_get_base_path(
        url: str,
        variables: t.Dict[str, str],
        expected_base_path: str,
) -> None:
    assert expected_base_path == app._get_base_path(
        servers=[model.OASServer(url=url, variables=variables)],
        base_path=None,
    ) == expected_base_path


def test_app_no_override() -> None:
    with pytest.raises(TypeError):

        class NoNo(app.Application):  # type: ignore
            ...
