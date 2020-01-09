import sys
import typing as t

import pytest
import typing_extensions as te

from axion.utils import get_type_repr

if sys.version_info > (3, 8):
    LITERAL_PKG = 'typing'
else:
    LITERAL_PKG = 'typing_extensions'


@pytest.mark.parametrize(
    ['the_type', 'expected_type_repr'],
    (
        (str, 'str'),
        (bool, 'bool'),
        (float, 'float'),
        (list, 'list'),
        (dict, 'dict'),
        (set, 'set'),
        (te.Literal[1], f'{LITERAL_PKG}.Literal[1]'),
        (te.Literal[1, 2], f'{LITERAL_PKG}.Literal[1, 2]'),
        (
            te.Literal[True],
            f'{LITERAL_PKG}.Literal[{1 if sys.version_info > (3, 8) else True}]',
        ),
        (te.Literal[False], f'{LITERAL_PKG}.Literal[False]'),
        (te.Literal[True, False], f'{LITERAL_PKG}.Literal[True, False]'),
        (te.Literal[False, True], f'{LITERAL_PKG}.Literal[False, True]'),
        (te.Literal[None], f'{LITERAL_PKG}.Literal[None]'),
        (te.Literal['test'], f"{LITERAL_PKG}.Literal['test']"),
        (
            te.Literal['a', 'x', 'i', 'o', 'n'],
            f"{LITERAL_PKG}.Literal['a', 'x', 'i', 'o', 'n']",
        ),
        (t.NewType('Cookies', int), 'Cookies[int]'),
        (t.NewType('Cookies', bool), 'Cookies[bool]'),
        (t.NewType('Cookies', str), 'Cookies[str]'),
        (t.NewType('Cookies', float), 'Cookies[float]'),
        (t.NewType('Cookies', t.List[str]), 'Cookies[typing.List[str]]'),
        (t.NewType('Cookies', t.Set[str]), 'Cookies[typing.Set[str]]'),
        (t.TypeVar('T'), 'typing.Any'),  # type: ignore
        (t.TypeVar('T', int, float), 'typing.TypeVar(?, int, float)'),  # type: ignore
        (t.TypeVar('T', int, float,  # type: ignore
                   bool), 'typing.TypeVar(?, int, float, bool)'),
        (t.TypeVar('T', bound=list), 'list'),  # type: ignore
        (t.TypeVar('T', bound=set), 'set'),  # type: ignore
        (t.AnyStr, 'typing.TypeVar(?, bytes, str)'),
        (t.Union[int, float], 'typing.Union[int, float]'),
        (t.Union[int], 'int'),
        (t.Optional[int], 'typing.Optional[int]'),
        (t.Optional[float], 'typing.Optional[float]'),
        (t.Optional[bool], 'typing.Optional[bool]'),
        (
            t.Optional[t.Union[float, int]],
            'typing.Optional[typing.Union[float, int]]',
        ),
        (
            t.Optional[t.Union[int, float]],
            'typing.Optional[typing.Union[float, int]]',
        ),
        (
            t.Optional[t.Union[dict, set, list]],
            'typing.Optional[typing.Union[dict, set, list]]',
        ),
        (
            t.Optional[t.Union[t.AnyStr, int, float]],
            'typing.Optional[typing.Union[typing.TypeVar(?, bytes, str), int, float]]',
        ),
        (t.Dict[str, str], 'typing.Dict[str, str]'),
        (t.Optional[t.Dict[str, str]], 'typing.Optional[typing.Dict[str, str]]'),
        (t.Optional[t.Dict[str, t.Any]], 'typing.Optional[typing.Dict[str, typing.Any]]'),
        (t.Dict, 'typing.Dict[typing.Any, typing.Any]'),
        (t.Dict[t.Any, t.Any], 'typing.Dict[typing.Any, typing.Any]'),
        (t.Set, 'typing.Set[typing.Any]'),
        (t.Set[str], 'typing.Set[str]'),
        (t.Set[bool], 'typing.Set[bool]'),
        (t.Set[float], 'typing.Set[float]'),
        (t.Set[t.Any], 'typing.Set[typing.Any]'),
        (t.Mapping, 'typing.Mapping[typing.Any, typing.Any]'),
        (t.Mapping[str, str], 'typing.Mapping[str, str]'),
        (t.Mapping[str, int], 'typing.Mapping[str, int]'),
        (t.Mapping[int, str], 'typing.Mapping[int, str]'),
        (t.AbstractSet, 'typing.AbstractSet[typing.Any]'),
        (t.AbstractSet[bool], 'typing.AbstractSet[bool]'),
        (t.Optional[t.AbstractSet[bool]], 'typing.Optional[typing.AbstractSet[bool]]'),
        (type(None), 'NoneType'),
        (None, None),
        (t.Any, 'typing.Any'),
        (te.TypedDict, 'typing_extensions.TypedDict'),
        (
            te.TypedDict(  # type: ignore
                'Cookies',
                {
                    'debug': bool,
                    'csrftoken': str,
                },
            ),
            'Cookies{csrftoken: str, debug: bool}',
        ),
        (
            te.TypedDict(  # type: ignore
                'Paging',
                {
                    'page': t.Optional[int],
                    'hasNext': bool,
                    'hasPrev': bool,
                },
            ),
            'Paging{hasNext: bool, hasPrev: bool, page: typing.Optional[int]}',
        ),
        (
            te.TypedDict(  # type: ignore
                'Complex',
                {
                    'page': t.Optional[int],
                    'foo': t.Union[t.List[str], t.Set[float]],
                    'bar': te.TypedDict('Bar', {'little': bool}),  # type: ignore
                },
            ),
            (
                'Complex{'
                'bar: Bar{little: bool}, '
                'foo: typing.Union[typing.List[str], typing.Set[float]], '
                'page: typing.Optional[int]'
                '}'
            ),
        ),
    ),
)
def test_get_type_repr(
        the_type: t.Optional[t.Type[t.Any]],
        expected_type_repr: str,
) -> None:
    if the_type is None:
        with pytest.raises(AssertionError):
            get_type_repr(the_type)  # type: ignore
    else:
        actual_type_repr = get_type_repr(the_type)
        assert actual_type_repr == expected_type_repr


def test_response_repr() -> None:
    from axion import response

    v1 = (
        'Response{'
        'body: typing.Any, '
        'cookies: typing.Mapping[str, str], '
        'headers: typing.Mapping[str, str], '
        'http_code: int'
        '}'
    )
    v2 = get_type_repr(response.Response)

    assert v1 == v2
