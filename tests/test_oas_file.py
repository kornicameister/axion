import typing as t

import pytest

from axion.specification import model
from axion.specification.parser import type as parse_type


@pytest.mark.parametrize(
    'str_format,expected_cls',
    (
        ('', model.OASStringType),
        ('binary', model.OASFileType),
    ),
)
def test_oas_file(
        str_format: str,
        expected_cls: t.Type[t.Any],
) -> None:
    assert isinstance(
        parse_type._build_oas_string({'format': str_format}),
        expected_cls,
    )


def test_oas_file_python_type() -> None:
    assert bytes == parse_type._build_oas_string({'format': 'binary'}).python_type
