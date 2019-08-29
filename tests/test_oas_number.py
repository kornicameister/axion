import typing as t

import pytest

from axion.specification import exceptions
from axion.specification import parser


@pytest.mark.parametrize('number_cls', (int, float))
def test_python_type(number_cls: t.Type[t.Union[int, float]]) -> None:
    assert issubclass(
        parser._build_oas_number(
            number_cls=number_cls,
            work_item={},
        ).python_type,
        number_cls,
    )


@pytest.mark.parametrize('key', ('default', 'example', 'minimum', 'maximum'))
@pytest.mark.parametrize('value', ['1', bool, {}, []])
def test_wrong_value_type(key: str, value: t.Any) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parser._build_oas_number(int, {key: value})


@pytest.mark.parametrize(
    ('example', 'default'),
    (
        (0, 1.0),
        (1.0, 0),
    ),
)
def test_mismatch_example_default(
        example: t.Any,
        default: t.Any,
) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parser._build_oas_number(
            int,
            {
                'example': example,
                'default': default,
            },
        )
