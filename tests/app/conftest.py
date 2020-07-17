import asyncio
from pathlib import Path
import typing as t

from _pytest.fixtures import FixtureRequest
from aiohttp import web
from aiohttp.test_utils import TestClient
import pytest

import axion
from axion.plugins import _aiohttp


@pytest.fixture
async def app(
    aiohttp_client: t.Any,
    request: FixtureRequest,
) -> t.AsyncGenerator[TestClient, None]:
    test_file_path = Path(request.node.fspath)
    client = await aiohttp_client(_make_app(test_file_path.with_suffix('.yml')))
    yield client


def _make_app(
    spec_path: Path,
) -> t.Callable[[asyncio.AbstractEventLoop], web.Application]:
    def wrap(loop: asyncio.AbstractEventLoop) -> web.Application:
        the_app = axion.Axion(
            root_dir=spec_path.parent,
            plugin_id='aiohttp',
            configuration=axion.conf.Configuration(),
            loop=loop,
        )
        the_app.add_api(spec_path)

        plugged_app = the_app.plugged
        assert isinstance(plugged_app, _aiohttp.AioHttpPlugin)

        native_app = plugged_app.root_app
        assert isinstance(native_app, web.Application)

        return native_app

    return wrap
