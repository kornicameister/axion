from pathlib import Path
import typing as t

import pytest

from tests import utils


async def handle_200() -> int:
    return 200


async def handle_204() -> None:
    return None


@pytest.mark.parametrize(
    'request_path,expected_status_code',
    (
        ('/200', 200),
        ('/204', 204),
    ),
)
async def test_200(
        test_client: t.Any,
        request_path: str,
        expected_status_code: int,
) -> None:
    client = await test_client(
        utils.create_app(Path.cwd() / 'tests' / 'specifications' / 'get.yml'),
    )
    resp = await client.get(request_path)
    assert resp.status == expected_status_code
