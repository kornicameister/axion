import typing as t

import pytest
import typing_extensions as te

from axion.utils import types


@pytest.mark.parametrize(
    'the_type,expected_result',
    (
        (int, False),
        (str, False),
        (t.NewType('INT', int), True),
        (t.NewType('INT', str), True),
        (t.Mapping[str, str], False),
        (t.NewType('F', t.Mapping[str, str]), True),  # type: ignore
        (te.TypedDict('X', x=int), False),  # type: ignore
    ),
)
def test_is_new_type(the_type: t.Any, expected_result: bool) -> None:
    actual_result = types.is_new_type(the_type)
    assert expected_result == actual_result


@pytest.mark.parametrize(
    'the_type,expected_result',
    (
        (None, False),
        (type(None), True),
        (int, False),
        (te.Literal[None], False),
        (te.Literal[None, 204], False),
    ),
)
def test_is_none_type(the_type: t.Any, expected_result: bool) -> None:
    actual_result = types.is_none_type(the_type)
    assert expected_result == actual_result


@pytest.mark.parametrize(
    'the_type,expected_types',
    (
        (
            te.Literal[204],
            {int},
        ),
        (
            te.Literal[204, 300, 400],
            {int},
        ),
        (te.Literal['a', 'b', 'c'], {str}),
        (
            te.Literal[2, 'devils'],
            {str, int},
        ),
        (
            te.Literal[te.Literal[True], False],
            {bool},
        ),
        (
            te.Literal[te.Literal[2],
                       False,
                       t.NewType('R', te.Literal[.4]),
                       ],
            {bool, int, float},
        ),
    ),
)
def test_literal_types(
        the_type: t.Any,
        expected_types: t.Sequence[t.Any],
) -> None:
    actual_types = types.literal_types(the_type)
    assert expected_types == actual_types


def test_literal_types_not_literal_input() -> None:
    with pytest.raises(AssertionError):
        types.literal_types(t.Mapping[str, str])


@pytest.mark.parametrize(
    'the_type',
    (
        te.Literal[te.TypedDict('X', x=int)],  # type: ignore
        te.Literal[[1, 2]],
        te.Literal[{1, 2}],
    ),
)
def test_literal_types_not_resolvable_type(the_type: t.Any) -> None:
    with pytest.raises(TypeError):
        types.literal_types(the_type)
