from pathlib import Path
import typing as t

from aiohttp import web_urldispatcher
import pytest
import pytest_mock as ptm

from axion import app
from axion.specification import loader
from axion.specification import model


def test_app_add_api_single_server(
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
        'axion.specification.load',
        return_value=loaded_spec,
    )
    apply_spec = mocker.patch('axion.app._apply_specification')

    spec_location = tmp_path / 'openapi.yaml'

    the_app = app.Application(root_dir=Path.cwd())
    the_app.add_api(spec_location)

    spec_load.assert_called_once_with(spec_location)
    apply_spec.assert_called_once_with(
        for_app=the_app.root_app,
        spec=loaded_spec,
    )

    assert the_app.root_dir == Path.cwd()
    assert len(the_app.api_base_paths) == 1


def test_app_add_more_than_single_server_gives_warning(
        mocker: ptm.MockFixture,
        tmp_path: Path,
) -> None:
    loaded_spec = mocker.stub()

    loaded_spec.servers = [
        model.OASServer(url='/', variables={}),
        model.OASServer(url='/v2', variables={}),
    ]

    mocker.patch('axion.specification.load', return_value=loaded_spec)
    mocker.patch('axion.app._apply_specification')
    loguru_warning = mocker.patch('loguru.logger.warning')

    the_app = app.Application(root_dir=Path.cwd())
    the_app.add_api(tmp_path / 'openapi.yaml')

    assert len(the_app.api_base_paths) == 1
    loguru_warning.assert_called_once()


@pytest.mark.parametrize(
    'server_url',
    ('/', '/v1', '/api'),
)
def test_app_add_api_duplicated_base_path(
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

    def spec_load_side_effect(path: Path) -> t.Any:
        return spec_one if path == spec_one_path else spec_two

    spec_load = mocker.patch(
        'axion.specification.load',
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
            spec=spec_one,
        )
    else:
        # if we are adding onto the different base path
        # and there's a duplicate assume that last added
        # app got the proper load_spec
        apply_spec.assert_called_once_with(
            for_app=the_app.root_app._subapps[-1],
            spec=spec_one,
        )


def test_app_add_api_overlapping_base_paths(
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
        'axion.specification.load',
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
        spec=spec_one,
    )


def test_app_add_with_custom_base_path(
        mocker: ptm.MockFixture,
        tmp_path: Path,
) -> None:
    spec_one = mocker.Mock()
    spec_one.servers = [model.OASServer(url='/api/v1', variables={})]
    spec_one_path = tmp_path / 'openapi_1.yml'

    spec_load = mocker.patch(
        'axion.specification.load',
        return_value=spec_one,
    )
    apply_spec = mocker.patch('axion.app._apply_specification')

    the_app = app.Application(root_dir=Path.cwd())
    the_app.add_api(spec_one_path, base_path='/')
    spec_load.assert_called_once_with(spec_one_path)

    router_resources = [r for r in the_app.root_app.router.resources()]

    assert len(router_resources) == 0
    apply_spec.assert_any_call(
        for_app=the_app.root_app,
        spec=spec_one,
    )


def test_app_add_with_relative_base_path(mocker: ptm.MockFixture) -> None:
    spec_one = mocker.Mock()
    spec_one.servers = [model.OASServer(url='/api/v1', variables={})]
    spec_one_path = Path('../tests/specifications/simple.yml')

    spec_load = mocker.patch(
        'axion.specification.load',
        return_value=spec_one,
    )
    apply_spec = mocker.patch('axion.app._apply_specification')

    the_app = app.Application(root_dir=Path.cwd())
    the_app.add_api(spec_one_path, base_path='/')
    spec_load.assert_called_once_with((Path.cwd() / spec_one_path).resolve())

    router_resources = [r for r in the_app.root_app.router.resources()]

    assert len(router_resources) == 0
    apply_spec.assert_any_call(
        for_app=the_app.root_app,
        spec=spec_one,
    )


def test_app_add_api_different_base_path(
        mocker: ptm.MockFixture,
        tmp_path: Path,
) -> None:
    spec_one = mocker.Mock()
    spec_one.servers = [model.OASServer(url='/v1', variables={})]
    spec_one_path = tmp_path / 'openapi_1.yml'

    spec_two = mocker.Mock()
    spec_two.servers = [model.OASServer(url='/v2', variables={})]
    spec_two_path = tmp_path / 'openapi_2.yml'

    spec_admin = mocker.Mock()
    spec_admin.servers = [model.OASServer(url='/admin', variables={})]
    spec_admin_path = tmp_path / 'openapi_admin.yml'

    def spec_load_side_effect(path: Path) -> t.Any:
        if path == spec_one_path:
            return spec_one
        elif path == spec_two_path:
            return spec_two
        else:
            return spec_admin

    spec_load = mocker.patch(
        'axion.specification.load',
        side_effect=spec_load_side_effect,
    )
    apply_spec = mocker.patch('axion.app._apply_specification')

    the_app = app.Application(root_dir=Path.cwd())
    the_app.add_api(spec_one_path)
    the_app.add_api(spec_two_path)
    the_app.add_api(spec_admin_path)

    spec_load.assert_any_call(spec_one_path)
    spec_load.assert_any_call(spec_two_path)
    spec_load.assert_any_call(spec_two_path)

    router_resources = [r for r in the_app.root_app.router.resources()]

    assert len(router_resources) == 3

    for prefix, the_spec in (
        ('/v1', spec_one),
        ('/v2', spec_two),
        ('/admin', spec_admin),
    ):
        sub_app = next((r for r in router_resources if r.canonical == prefix), None)
        assert sub_app is not None
        assert isinstance(
            sub_app,
            web_urldispatcher.PrefixedSubAppResource,
        )
        apply_spec.assert_any_call(
            for_app=sub_app._app,
            spec=the_spec,
        )


def test_apply_specification_no_subapp(
        spec_path: Path,
        mocker: ptm.MockFixture,
) -> None:

    the_spec = loader.load_spec(spec_path)
    the_app = app.Application(root_dir=Path.cwd())

    add_route_spy = mocker.spy(the_app.root_app.router, 'add_route')
    resolve_handler = mocker.patch('axion.app._resolve_handler')

    the_app.add_api(
        spec_location=spec_path,
        base_path='/',
    )

    assert resolve_handler.call_count == len(the_spec.operations)

    assert add_route_spy.call_count == len(the_spec.operations)
    assert len(the_app.root_app.router.resources()) == len(the_spec.operations)


def test_apply_specification_subapp(
        spec_path: Path,
        mocker: ptm.MockFixture,
) -> None:
    the_spec = loader.load_spec(spec_path)
    the_app = app.Application(root_dir=Path.cwd())

    add_route_spy = mocker.spy(the_app.root_app.router, 'add_route')
    add_subapp_spy = mocker.spy(the_app.root_app, 'add_subapp')
    resolve_handler = mocker.patch('axion.app._resolve_handler')

    the_app.add_api(
        spec_location=spec_path,
        base_path='/api',
    )

    assert resolve_handler.call_count == len(the_spec.operations)

    assert add_route_spy.call_count == 0
    assert add_subapp_spy.call_count == 1
    assert len(the_app.root_app.router.resources()) == 1

    subapp = the_app.root_app._subapps[0]
    assert len(subapp.router.resources()) == len(the_spec.operations)


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
