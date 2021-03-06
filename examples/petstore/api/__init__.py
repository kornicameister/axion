import typing as t

from axion import oas_endpoint
from axion import pipeline


@oas_endpoint
async def list_pets(
    tags: t.Optional[t.List[str]] = None,
    page: t.Optional[int] = 0,
    limit: t.Optional[int] = None,
) -> pipeline.Response:
    return {
        'http_code': 200,
    }


@oas_endpoint
async def find_pet(id: int) -> pipeline.Response:
    return {
        'http_code': 200,
    }


@oas_endpoint
async def delete_pet(id: int) -> pipeline.Response:
    return {
        'http_code': 204,
    }


@oas_endpoint
async def new_pet(body: t.Mapping[str, str]) -> pipeline.Response:
    return {
        'http_code': 200,
    }
