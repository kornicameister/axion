import typing as t

from axion import response


async def list_pets(
        tags: t.Optional[list] = None,
        limit: t.Optional[int] = None,
) -> response.Response:
    return {
        'http_code': 200,
    }


async def find_pet(id: int) -> response.Response:
    return {
        'http_code': 200,
    }


async def delete_pet(id: int) -> response.Response:
    return {
        'http_code': 204,
    }


async def new_pet(body: t.Mapping[str, str]) -> response.Response:
    return {
        'http_code': 200,
    }
