from functools import singledispatch
import typing as t

from aiohttp import web
import multidict as md

from axion import application

__all__ = 'handle'


class Arguments(t.NamedTuple):
    path: md.CIMultiDict[str]
    query: md.CIMultiDict[str]
    cookies: md.CIMultiDict[str]
    header: md.CIMultiDict[str]


@singledispatch
async def handle(
        request: t.Dict[t.Any, t.Any],
        handler: application.Handler,
) -> Arguments:
    raise TypeError('typing.Dict is not supported to collect arguments from')


@handle.register
async def _handle_aiohttp(
        request: web.Request,
        handler: application.Handler,
) -> Arguments:
    return Arguments(path={}, query={}, cookies={}, header={})
