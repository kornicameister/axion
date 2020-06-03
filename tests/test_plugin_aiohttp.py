from pathlib import Path
import typing as t

from _pytest import logging as _logging
from aiohttp import web
from aiohttp import web_urldispatcher
import mock
import pytest
import pytest_mock as ptm

from axion.oas import loader
from axion.oas import model
from axion.plugins import _aiohttp as app


@pytest.mark.parametrize('server_base_path', ('/', '/test'))
@pytest.mark.parametrize('add_api_base_path', ('/thor', '/iron_man', None))
def test_add_api_single_server(
    server_base_path: str,
    add_api_base_path: t.Optional[str],
    mocker: ptm.MockFixture,
    tmp_path: Path,
) -> None:
    loaded_spec = mocker.stub()
    loaded_spec.servers = [model.OASServer(
        url=server_base_path,
        variables={},
    )]

    apply_spec = mocker.patch('axion.plugins._aiohttp._apply_specification')
    get_base_path = mocker.patch(
        'axion.plugins._aiohttp._get_base_path',
        return_value=server_base_path,
    )

    the_app = app.AioHttpPlugin(configuration=mocker.ANY)
    the_app.add_api(loaded_spec, add_api_base_path)

    assert len(the_app.api_base_paths) == 1

    if add_api_base_path is not None:

        assert add_api_base_path in the_app.api_base_paths
        assert server_base_path not in the_app.api_base_paths

        get_base_path.assert_not_called()
        apply_spec.assert_called_once_with(
            for_app=the_app.api_base_paths[add_api_base_path],
            spec=loaded_spec,
        )
    else:

        assert server_base_path in the_app.api_base_paths
        assert add_api_base_path not in the_app.api_base_paths

        get_base_path.assert_called_once_with(loaded_spec.servers)
        apply_spec.assert_called_once_with(
            for_app=the_app.api_base_paths[server_base_path],
            spec=loaded_spec,
        )


def test_add_api_multiple_servers(
    mocker: ptm.MockFixture,
    caplog: _logging.LogCaptureFixture,
) -> None:
    loaded_spec = mocker.stub()
    loaded_spec.servers = [
        model.OASServer(url='/v1', variables={}),
        model.OASServer(url='/v2', variables={}),
        model.OASServer(url='/v3', variables={}),
    ]

    mocker.patch('axion.plugins._aiohttp._apply_specification')

    the_app = app.AioHttpPlugin(configuration=mocker.ANY)
    the_app.add_api(spec=loaded_spec)

    assert len(the_app.api_base_paths) == 1

    assert '/v1' in the_app.api_base_paths
    assert '/v2' not in the_app.api_base_paths
    assert '/v3' not in the_app.api_base_paths

    msg = (
        'There are 3 servers, axion will assume first one. '
        'This behavior might change in the future, once axion knows '
        'how to deal with multiple servers'
    )
    assert next(
        filter(
            lambda r: r.levelname.lower() == 'warning' and r.msg == msg,
            caplog.records,
        ),
        None,
    ) is not None


@pytest.mark.parametrize(
    'server_url',
    ('/', '/v1', '/api'),
)
def test_app_add_api_duplicated_base_path(
    server_url: str,
    mocker: ptm.MockFixture,
) -> None:
    spec_one = mocker.stub()
    spec_one.servers = [model.OASServer(url=server_url, variables={})]

    spec_two = mocker.stub()
    spec_two.servers = [model.OASServer(url=server_url, variables={})]

    apply_spec = mocker.patch('axion.plugins._aiohttp._apply_specification')

    the_app = app.AioHttpPlugin(configuration=mocker.ANY)
    the_app.add_api(spec_one)
    with pytest.raises(
            app.DuplicateBasePath,
            match=(f'You tried to add API with base_path={server_url}, '
                   f'but it is already added. '
                   f'If you want to add more than one API, you will need to '
                   f'specify unique base paths for each API. '
                   f'You can do this either via OAS\'s "servers" property or '
                   f'base_path argument of this function.'),
    ):
        the_app.add_api(spec_two)

    assert len(the_app.api_base_paths) == 1

    assert mock.call(
        for_app=the_app.api_base_paths[server_url],
        spec=spec_one,
    ) in apply_spec.call_args_list
    assert mock.call(
        for_app=the_app.api_base_paths[server_url],
        spec=spec_two,
    ) not in apply_spec.call_args_list

    if server_url == '/':
        apply_spec.assert_called_once_with(
            for_app=the_app.root_app,
            spec=spec_one,
        )
        assert not the_app.root_app._subapps
    else:
        assert the_app.root_app._subapps
        assert 1 == len(the_app.root_app._subapps)
        apply_spec.assert_called_once_with(
            for_app=the_app.root_app._subapps[-1],
            spec=spec_one,
        )


@pytest.mark.parametrize(
    'server_url,overlapping_server_url',
    (
        ('/', '/v1'),
        ('/v1', '/v1/app'),
        ('/', '/api'),
    ),
)
def test_app_add_api_overlapping_base_paths(
    server_url: str,
    overlapping_server_url: str,
    mocker: ptm.MockFixture,
) -> None:
    spec_one = mocker.stub()
    spec_one.servers = [model.OASServer(url=server_url, variables={})]

    spec_two = mocker.stub()
    spec_two.servers = [model.OASServer(url=overlapping_server_url, variables={})]

    apply_spec = mocker.patch('axion.plugins._aiohttp._apply_specification')

    the_app = app.AioHttpPlugin(configuration=mocker.ANY)

    the_app.add_api(spec_one)
    with pytest.raises(
            app.OverlappingBasePath,
            match=(f'You tried to add API with base_path={overlapping_server_url}, '
                   f'but it is overlapping one of the APIs that has been already added. '
                   f'You need to make sure that base paths for all APIs do '
                   f'not overlap each other.'),
    ):
        the_app.add_api(spec_two)

    assert len(the_app.api_base_paths) == 1
    apply_spec.assert_called_once_with(
        for_app=the_app.api_base_paths[server_url],
        spec=spec_one,
    )

    if server_url == '/':
        apply_spec.assert_called_once_with(
            for_app=the_app.root_app,
            spec=spec_one,
        )
        assert not the_app.root_app._subapps
    else:
        assert the_app.root_app._subapps
        assert 1 == len(the_app.root_app._subapps)
        apply_spec.assert_called_once_with(
            for_app=the_app.root_app._subapps[-1],
            spec=spec_one,
        )


def test_app_add_with_custom_base_path(mocker: ptm.MockFixture) -> None:
    server_url = '/api/v1/'
    arg_base_path = '/'

    spec_one = mocker.stub()
    spec_one.servers = [
        model.OASServer(url=server_url, variables={}),
    ]

    apply_spec = mocker.patch('axion.plugins._aiohttp._apply_specification')
    get_base_path = mocker.patch('axion.plugins._aiohttp._get_base_path')

    the_app = app.AioHttpPlugin(configuration=mocker.ANY)
    the_app.add_api(spec_one, base_path=arg_base_path)

    assert 1 == len(the_app.api_base_paths)
    assert arg_base_path in the_app.api_base_paths
    assert server_url not in the_app.api_base_paths

    apply_spec.assert_any_call(
        for_app=the_app.root_app,
        spec=spec_one,
    )
    get_base_path.assert_not_called()


def test_app_add_api_different_base_path(
    mocker: ptm.MockFixture,
    tmp_path: Path,
) -> None:
    spec_one = mocker.stub()
    spec_one.servers = [model.OASServer(url='/v1', variables={})]

    spec_two = mocker.stub()
    spec_two.servers = [model.OASServer(url='/v2', variables={})]

    spec_admin = mocker.stub()
    spec_admin.servers = [model.OASServer(url='/admin', variables={})]

    apply_spec = mocker.patch('axion.plugins._aiohttp._apply_specification')

    the_app = app.AioHttpPlugin(configuration=mocker.ANY)

    the_app.add_api(spec_one)
    the_app.add_api(spec_two)
    the_app.add_api(spec_admin)

    router_resources = list(the_app.root_app.router.resources())
    assert len(router_resources) == 3
    assert len(the_app.api_base_paths) == 3

    for prefix, the_spec in (
        ('/v1', spec_one),
        ('/v2', spec_two),
        ('/admin', spec_admin),
    ):
        sub_app_a = the_app.api_base_paths.get(prefix, None)
        sub_app_b = next((r for r in router_resources if r.canonical == prefix), None)

        assert sub_app_a is not None
        assert isinstance(
            sub_app_a,
            web.Application,
        )

        assert sub_app_b is not None
        assert isinstance(
            sub_app_b,
            web_urldispatcher.PrefixedSubAppResource,
        )

        assert sub_app_a == sub_app_b._app
        apply_spec.assert_any_call(
            for_app=sub_app_b._app,
            spec=the_spec,
        )
        apply_spec.assert_any_call(
            for_app=sub_app_a,
            spec=the_spec,
        )


def test_apply_specification_no_subapp(
    spec_path: Path,
    mocker: ptm.MockFixture,
) -> None:
    the_spec = loader.load_spec(spec_path)
    the_app = app.AioHttpPlugin(configuration=mocker.ANY)

    add_route_spy = mocker.spy(the_app.root_app.router, 'add_route')
    resolve_handler = mocker.patch('axion.handler.resolve')

    the_app.add_api(
        spec=the_spec,
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
    the_app = app.AioHttpPlugin(configuration=mocker.ANY)

    add_route_spy = mocker.spy(the_app.root_app.router, 'add_route')
    add_subapp_spy = mocker.spy(the_app.root_app, 'add_subapp')
    resolve_handler = mocker.patch('axion.handler.resolve')

    the_app.add_api(
        spec=the_spec,
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
    ) == expected_base_path
