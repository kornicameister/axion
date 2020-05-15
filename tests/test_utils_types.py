import sys
import types
import typing as t

import pytest
import typing_extensions as te

from axion.utils import types as axion_types


@pytest.mark.parametrize(
    'the_type,expected_result',
    (
        *[(pp, False) for pp in axion_types.P_TYPES],
        *[(t.NewType(repr(pp), pp), False) for pp in axion_types.P_TYPES],
        *[
            (t.Any, True),
            (t.NewType('X', t.Any), True),  # type: ignore
        ],
    ),
    ids=lambda x: repr(x),
)
def test_is_any_type(the_type: t.Any, expected_result: bool) -> None:
    actual_result = axion_types.is_any_type(the_type)
    assert expected_result == actual_result


@pytest.mark.parametrize('the_type', axion_types.P_TYPES)
def test_is_not_any_type(the_type: t.Any) -> None:
    assert not axion_types.is_any_type(the_type)


@pytest.mark.parametrize(
    'the_type,expected_result',
    (
        (t.Mapping[str, str], True),
        (t.Dict[str, str], True),
        (t.Mapping[int, float], True),
        (te.TypedDict('Z', z=int), True),  # type: ignore
        (t.List[int], False),
        (int, False),
        (bool, False),
        (complex, False),
        (t.Set[int], False),
        (t.Dict[str, complex], True),
        (
            types.new_class('C1', (t.Dict[str, str], )),
            True,
        ),
        (
            types.new_class('C2', (t.Dict[t.Any, complex], )),
            True,
        ),
        (
            types.new_class('C3', (t.Mapping[str, float], )),
            True,
        ),
        (
            types.new_class('C3', (t.NamedTuple, )),
            False,
        ),
        (
            t.NewType('C4', t.Dict[str, t.Set[complex]]),
            True,
        ),
        (
            t.NewType('C5', int),
            False,
        ),
    ),
    ids=lambda x: repr(x),
)
def test_is_dict_like(the_type: t.Any, expected_result: bool) -> None:
    actual_result = axion_types.is_dict_like(the_type)
    assert expected_result == actual_result


@pytest.mark.parametrize(
    'the_type,expected_result',
    (
        (None, False),
        (type(None), True),
        (int, False),
        (te.Literal[None], False),
        (te.Literal[None, 204], False),
        (t.Dict[str, str], False),
        (t.NamedTuple('NT', x=int), False),
    ),
    ids=lambda x: repr(x),
)
def test_is_none_type(the_type: t.Any, expected_result: bool) -> None:
    actual_result = axion_types.is_none_type(the_type)
    assert expected_result == actual_result


@pytest.mark.parametrize(
    'the_type,expected_types',
    (
        (
            te.Literal[1, 204],
            {int},
        ),
        (
            te.Literal[1],
            {int},
        ),
        (
            te.Literal[True],
            {bool},
        ),
        (
            te.Literal[False],
            {bool},
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
        (te.Literal[None], {type(None)}),
    ),
    ids=lambda x: repr(x),
)
@pytest.mark.xfail(
    sys.version_info >= (3, 8, 0),
    reason='https://bugs.python.org/issue39308',
)
def test_literal_types(
    the_type: t.Any,
    expected_types: t.Sequence[t.Any],
) -> None:
    actual_types = axion_types.literal_types(the_type)
    assert expected_types == actual_types


def test_literal_types_not_literal_input() -> None:
    with pytest.raises(AssertionError):
        axion_types.literal_types(t.Mapping[str, str])


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
        axion_types.literal_types(the_type)
