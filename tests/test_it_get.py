from pathlib import Path
import typing as t

import pytest
import typing_extensions as te

from tests import utils


async def handle_200() -> te.TypedDict('R200', http_code=int):
    return {
        'http_code': 200,
    }


async def handle_204() -> te.TypedDict('R1', http_code=te.Literal[204]):
    return {
        'http_code': 204,
    }


@pytest.mark.parametrize(
    'request_path,expected_status_code',
    (
        ('/200', 200),
        ('/204', 204),
    ),
)
async def test_200(
        aiohttp_client: t.Any,
        request_path: str,
        expected_status_code: int,
) -> None:
    client = await aiohttp_client(
        utils.create_app(Path.cwd() / 'tests' / 'specifications' / 'get.yml'),
    )
    resp = await client.get(request_path)
    assert resp.status == expected_status_code
