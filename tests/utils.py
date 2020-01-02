import asyncio
from pathlib import Path
import typing as t

from aiohttp import web

from axion import app


def create_app(spec: Path) -> t.Callable[[asyncio.AbstractEventLoop], web.Application]:
    def wrap(loop: asyncio.AbstractEventLoop) -> web.Application:
        the_app = app.Application(root_dir=Path.cwd(), loop=loop)
        the_app.add_api(spec)
        return the_app.root_app

    return wrap
