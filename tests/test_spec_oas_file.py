import typing as t

import pytest

from axion.specification import model
from axion.specification import parser


@pytest.mark.parametrize(
    'str_format,expected_cls',
    (
        ('password', model.OASStringType),
        ('binary', model.OASFileType),
    ),
)
def test_oas_string_is_file(
        str_format: str,
        expected_cls: t.Type[t.Any],
) -> None:
    assert isinstance(
        parser._build_oas_string({'format': str_format}),
        expected_cls,
    )
