import typing as t

import pytest

from axion.oas.parser import type as parse_type


@pytest.mark.parametrize(
    'unique_items,python_type',
    ((True, set), (False, list)),
)
def test_python_type(
        unique_items: bool,
        python_type: t.Type[t.Any],
) -> None:
    arr_python_type = parse_type.resolve(
        {},
        {
            'type': 'array',
            'uniqueItems': unique_items,
            'items': {
                'schema': {
                    'type': 'string',
                },
            },
        },
    ).python_type

    assert issubclass(
        arr_python_type,
        python_type,
    )


def test_oas_type() -> None:
    assert parse_type.resolve(
        {},
        {
            'type': 'array',
            'uniqueItems': False,
            'items': {
                'schema': {
                    'type': 'string',
                },
            },
        },
    ).oas_type == 'array'
