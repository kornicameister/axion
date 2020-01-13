import typing as t

import pytest
import typing_extensions as te

from axion.utils import get_type_repr


@pytest.mark.parametrize(
    'the_type,str_repr',
    (
        (str, 'str'),
        (bool, 'bool'),
        (float, 'float'),
        (list, 'list'),
        (dict, 'dict'),
        (set, 'set'),
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
            'Cookies{debug: bool, csrftoken: str}',
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
            'Paging{page: typing.Optional[int], hasNext: bool, hasPrev: bool}',
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
                'page: typing.Optional[int], '
                'foo: typing.Union[typing.List[str], typing.Set[float]],'
                ' bar: Bar{little: bool}'
                '}'
            ),
        ),
    ),
)
def test_get_type_string_repr(the_type: t.Optional[t.Type[t.Any]], str_repr: str) -> None:
    if the_type is None:
        with pytest.raises(AssertionError):
            get_type_repr.get_repr(the_type)
    else:
        assert get_type_repr.get_repr(the_type) == str_repr
