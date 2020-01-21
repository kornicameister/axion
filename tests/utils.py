import asyncio
from pathlib import Path
import typing as t

from aiohttp import web

import axion
from axion import conf
from axion.plugins import _aiohttp


def create_aiohttp_app(
        spec: Path,
) -> t.Callable[[asyncio.AbstractEventLoop], web.Application]:
    def wrap(loop: asyncio.AbstractEventLoop) -> web.Application:
        the_app = axion.Axion(
            root_dir=Path.cwd(),
            plugin_id='aiohttp',
            configuration=conf.Configuration(),
            loop=loop,
        )
        the_app.add_api(spec)

        plugged_app = the_app.plugged
        assert isinstance(plugged_app, _aiohttp.AioHttpPlugin)

        native_app = plugged_app.root_app
        assert isinstance(native_app, web.Application)

        return native_app

    return wrap
