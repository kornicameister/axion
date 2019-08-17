import asyncio
from pathlib import Path
import typing as t

from aiohttp import web
from aiohttp import web_app
from loguru import logger
import typing_extensions as te
import yarl

from axion import spec
from axion.spec import model

APIs = t.Dict[str, web.Application]


class DuplicateBasePath(ValueError):
    ...


class OverlappingBasePath(ValueError):
    ...


class AxionConfiguration(te.TypedDict):
    ...


@te.final
class Application:
    __slots__ = (
        'root_dir',
        'root_app',
        'api_base_paths',
    )

    @classmethod
    def __init_subclass__(cls: t.Type['Application']) -> None:
        raise TypeError(
            f'Inheritance class {cls.__name__} from axion.app.Application '
            f'is forbidden',
        )

    def __init__(
            self,
            root_dir: Path,
            axion_conf: AxionConfiguration = None,
            logging_conf: t.Dict[str, t.Any] = None,
    ) -> None:
        self.root_dir = root_dir.resolve()
        self.root_app = web.Application()
        # track down API base paths
        # if there is a try to add an API with the base path
        # that has been already added suggest adding all APIs
        # with unique base paths
        self.api_base_paths = set()  # type: t.Set[str]

    def add_api(
            self,
            spec_location: spec.SpecLocation,
            base_path: t.Optional[str] = None,
            middlewares: t.Optional[t.Sequence[web_app._Middleware]] = None,
    ) -> None:
        if not spec_location.is_absolute():
            spec_location = (self.root_dir / spec_location).resolve()

        loaded_spec = spec.load(spec_location)
        target_app, target_base_path = _get_target_app(
            root_app=self.root_app,
            known_base_paths=self.api_base_paths,
            servers=loaded_spec.servers,
            middlewares=middlewares,
            base_path=base_path,
        )
        self.api_base_paths.add(target_base_path)

        _apply_specification(
            for_app=target_app,
            specification=loaded_spec,
        )
        if target_app != self.root_app:
            logger.info(
                'Registering application for base_path={base_path} '
                'as a sub application',
                base_path=target_base_path,
            )
            self.root_app.add_subapp(
                prefix=target_base_path,
                subapp=target_app,
            )


def _apply_specification(
        for_app: web.Application,
        specification: model.OASSpecification,
) -> None:

    for op in specification.operations:
        the_route = for_app.router.add_route(
            method=op.http_method.value,
            path=op.path.human_repr(),
            name=op.operation_id,
            handler=_make_handler(op),
        )
        logger.opt(lazy=True).debug(
            'Registered route={route} for {op_id}',
            route=lambda: the_route,
            op_id=lambda: op.operation_id,
        )


def _make_handler(operation: model.Operation) -> web_app._Handler:
    @asyncio.coroutine
    def handler(request: web.Request) -> web.StreamResponse:
        ...

    return handler


def _get_target_app(
        root_app: web.Application,
        known_base_paths: t.Set[str],
        servers: t.List[model.OASServer],
        middlewares: t.Optional[t.Sequence[web_app._Middleware]] = None,
        base_path: t.Optional[str] = None,
) -> t.Tuple[web.Application, str]:
    the_base_path = _get_base_path(
        servers=servers,
        base_path=base_path,
    )

    def check_overlapping() -> bool:
        for known_base_path in known_base_paths:
            if known_base_path.startswith(the_base_path):
                return True
            elif the_base_path.startswith(known_base_path):
                return True
        return False

    if the_base_path in known_base_paths:
        raise DuplicateBasePath((
            f'You tried to add API with base_path={the_base_path}, '
            f'but it is already added. '
            f'If you want to add more than one API, you will need to '
            f'specify unique base paths for each API. '
            f'You can do this either via OAS\'s "servers" property or '
            f'base_path argument of this function.'
        ))
    elif check_overlapping():
        raise OverlappingBasePath((
            f'You tried to add API with base_path={the_base_path}, '
            f'but it is overlapping one of the APIs that has been already added. '
            f'You need to make sure that base paths for all APIs do '
            f'not overlap each other.'
        ))
    elif the_base_path == '/':
        logger.debug('Having base_path == / means returning root application')
        return root_app, the_base_path
    else:
        logger.opt(lazy=True).debug(
            'Detected base_path == {base_path}, making a sub application',
            base_path=lambda: the_base_path,
        )
        nested_app = web.Application(middlewares=middlewares or ())
        return nested_app, the_base_path


def _get_base_path(
        servers: t.List[model.OASServer],
        base_path: t.Optional[str] = None,
) -> str:
    the_base_path: str

    if base_path:
        logger.debug(
            'Using user provided base path = {base_path}',
            base_path=base_path,
        )
        the_base_path = base_path
    else:
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
        the_base_path = yarl.URL(first_server.url.format(**first_server.variables)).path

    logger.info(
        'API base path will be {base_path}',
        base_path=the_base_path,
    )

    return the_base_path
