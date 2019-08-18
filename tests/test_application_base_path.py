import typing as t

import pytest

from axion import application
from axion import specification


@pytest.mark.parametrize(('url', 'variables', 'expected_base_path'), (
    (
        '/',
        {},
        '/',
    ),
    (
        'https://example.org/',
        {},
        '/',
    ),
    (
        '/v{api_version}',
        {
            'api_version': '1',
        },
        '/v1',
    ),
    (
        'https://example.org/v{api_version}',
        {
            'api_version': '1',
        },
        '/v1',
    ),
    (
        '{protocol}://example.org:{port}/v{api_version}',
        {
            'api_version': '1',
            'port': '443',
            'protocol': 'https',
        },
        '/v1',
    ),
))
def test_app_get_base_path(
        url: str,
        variables: t.Dict[str, str],
        expected_base_path: str,
) -> None:
    assert expected_base_path == application.get_base_path(
        servers=[specification.OASServer(url=url, variables=variables)],
    ) == expected_base_path
