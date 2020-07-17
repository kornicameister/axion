import asyncio
import typing as t

from aiohttp import web
from aiohttp import web_app
from loguru import logger
import typing_extensions as te
import yarl

from axion import conf
from axion import handler
from axion import oas
from axion import plugin
from axion import response
from axion.pipeline import validator

APIs = t.Dict[str, web.Application]


@te.final
class AioHttpPlugin(
        plugin.Plugin,
        id='aiohttp',
        version='0.0.1',
):
    """aiohttp plugin.

    Usage:
        https://github.com/kornicameister/axion/issues/202

    """
    __slots__ = (
        'root_app',
        'api_base_paths',
    )

    def __init__(
            self,
            configuration: conf.Configuration,
            loop: t.Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        super().__init__(configuration)
        self.root_app = web.Application(loop=loop)
        self.api_base_paths = {}  # type: t.Dict[str, web.Application]

    def add_api(
        self,
        spec: oas.OASSpecification,
        base_path: t.Optional[str] = None,
        *_: None,
        middlewares: t.Optional[t.Sequence[web_app._Middleware]] = None,
        **kwargs: t.Any,
    ) -> None:
        base_path = base_path or _get_base_path(spec.servers)

        target_app, target_base_path = _get_target_app(
            root_app=self.root_app,
            base_path=base_path,
            known_base_paths=self.api_base_paths.keys(),
            middlewares=middlewares,
        )

        _apply_specification(
            for_app=target_app,
            spec=spec,
        )

        if target_app != self.root_app:
            logger.info(
                'Registering application for server_base_path={server_base_path} '
                'as a sub application',
                server_base_path=target_base_path,
            )
            self.root_app.add_subapp(
                prefix=target_base_path,
                subapp=target_app,
            )

        self.api_base_paths[target_base_path] = target_app


class DuplicateBasePath(ValueError):
    ...


class OverlappingBasePath(ValueError):
    ...


def _apply_specification(
    for_app: web.Application,
    spec: oas.OASSpecification,
) -> None:

    for op in spec.operations:
        the_route = for_app.router.add_route(
            method=op.http_method.value,
            path=op.path.human_repr(),
            name=op.id,
            handler=_make_handler(op),
        )
        logger.opt(lazy=True).debug(
            'Registered route={route} for {op_id}',
            route=lambda: the_route,
            op_id=lambda: op.id,
        )


def _make_handler(operation: oas.OASOperation) -> web_app._Handler:
    user_handler = handler.resolve(operation, asynchronous=True)
    validators = {
        validator.HttpCodeValidator(operation),
    }

    def _validate(
            r: response.Response,
            v: validator.Validator[t.Any],
    ) -> bool:
        try:
            v(r)
            return True
        except validator.ValidationError as e:
            logger.exception('Response validation failure', e)
            return False

    async def wrapper(request: web.Request) -> web.StreamResponse:
        d = await user_handler.fn()  # pragma: no cover

        is_valid = all(_validate(d, v) for v in validators)
        assert is_valid

        return web.Response(status=d['http_code'])  # pragma: no cover

    return wrapper


def _get_base_path(servers: t.List[oas.OASServer]) -> str:
    server_count = len(servers)

    if server_count > 1:
        logger.warning(
            (
                'There are {count} servers, axion will assume first one. '
                'This behavior might change in the future, once axion knows '
                'how to deal with multiple servers'
            ),
            count=len(servers),
        )
    first_server = servers[0]

    logger.debug(
        'Computing base path using server definition = {server}',
        server=first_server,
    )

    the_base_path: str = yarl.URL(first_server.url.format(**first_server.variables)).path

    logger.info(
        'API base path will be {base_path}',
        base_path=the_base_path,
    )

    return the_base_path


def _get_target_app(
    root_app: web.Application,
    base_path: str,
    known_base_paths: t.Iterable[str],
    middlewares: t.Optional[t.Sequence[web_app._Middleware]] = None,
) -> t.Tuple[web.Application, str]:
    def check_overlapping() -> bool:
        for known_base_path in known_base_paths:
            if known_base_path.startswith(base_path):
                return True
            elif base_path.startswith(known_base_path):
                return True
        return False

    if base_path in known_base_paths:
        raise DuplicateBasePath((
            f'You tried to add API with base_path={base_path}, '
            f'but it is already added. '
            f'If you want to add more than one API, you will need to '
            f'specify unique base paths for each API. '
            f'You can do this either via OAS\'s "servers" property or '
            f'base_path argument of this function.'
        ))
    elif check_overlapping():
        raise OverlappingBasePath((
            f'You tried to add API with base_path={base_path}, '
            f'but it is overlapping one of the APIs that has been already added. '
            f'You need to make sure that base paths for all APIs do '
            f'not overlap each other.'
        ))
    elif base_path == '/':
        logger.debug('Having base_path == / means returning root application')
        return root_app, base_path
    else:
        logger.debug(
            'Detected base_path == {base_path}, making a sub application',
            base_path=base_path,
        )
        nested_app = web.Application(middlewares=middlewares or ())
        return nested_app, base_path
