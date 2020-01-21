from pathlib import Path
import typing as t

import pytest

from axion import response
from tests import utils


async def handle_200() -> response.Response:
    return {
        'http_code': 200,
    }


async def handle_204() -> response.Response:
    return {
        'http_code': 204,
    }


async def unmatched_http_code() -> response.Response:
    return {
        'http_code': 200,
    }


@pytest.mark.parametrize(
    'request_path,expected_status_code',
    (
        ('/200', 200),
        ('/204', 204),
    ),
)
async def test_ok(
        aiohttp_client: t.Any,
        request_path: str,
        expected_status_code: int,
) -> None:
    client = await aiohttp_client(
        utils.create_aiohttp_app(Path.cwd() / 'tests' / 'specifications' / 'get.yml'),
    )
    resp = await client.get(request_path)
    assert resp.status == expected_status_code


# TODO(kornicameister) how this can be verified
# Should there a unit test or perhaps it is time to extend
# pipeline to actually form a pipeline
async def test_expect_fail(aiohttp_client: t.Any) -> None:
    client = await aiohttp_client(
        utils.create_aiohttp_app(Path.cwd() / 'tests' / 'specifications' / 'get.yml'),
    )
    resp = await client.get('/unmatched')
    assert resp.status != 201
