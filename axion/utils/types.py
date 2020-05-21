import collections
import functools
import typing as t

import more_itertools
import typing_extensions as te
import typing_inspect as ti

DICT_LIKE_TYPES: te.Final = (dict, collections.abc.Mapping)

P_TYPES: te.Final = (
    int,
    float,
    complex,
    bool,
    str,
    bytes,
    frozenset,
    set,
    list,
    dict,
)
PP = t.Type[t.Union[None,
                    int,
                    float,
                    complex,
                    bool,
                    str,
                    bytes,
                    frozenset,
                    set,
                    list,
                    dict,
                    ]]

AnyCallable = t.Callable[..., t.Any]


@functools.lru_cache(maxsize=30, typed=True)
def is_none_type(tt: t.Type[t.Any]) -> bool:
    return tt is type(None)


@functools.lru_cache(maxsize=30, typed=True)
def is_any_type(tt: t.Any) -> bool:
    if ti.is_new_type(tt):
        return is_any_type(tt.__supertype__)
    return tt is t.Any


@functools.lru_cache(maxsize=30, typed=True)
def is_dict_like(tt: t.Any) -> bool:
    try:
        assert any((
            ti.is_generic_type(tt),
            getattr(tt, '__annotations__', None) is not None,
        ))
    except AssertionError:
        return False
    else:
        maybe_mro = getattr(tt, '__mro__', None)
        maybe_origin = ti.get_origin(tt)

    if ti.is_new_type(tt):
        return is_dict_like(tt.__supertype__)
    elif maybe_origin:
        return issubclass(maybe_origin, DICT_LIKE_TYPES)
    elif maybe_mro:
        return any(issubclass(mro, DICT_LIKE_TYPES) for mro in maybe_mro)
    return False  # pragma: no cover


def literal_types(tt: t.Any) -> t.Iterable[PP]:
    assert ti.is_literal_type(tt)
    pps = [_literal_types(x) for x in ti.get_args(tt, ti.NEW_TYPING)]
    return frozenset(more_itertools.flatten(pps))


def _literal_types(tt: t.Any) -> t.Iterable[PP]:
    if ti.is_literal_type(tt):
        return literal_types(tt)
    elif ti.is_new_type(tt):
        return literal_types(tt.__supertype__)
    elif isinstance(tt, P_TYPES):
        return (type(tt), )

    try:
        assert isinstance(tt, type(None))
        return (type(None), )
    except (TypeError, AssertionError):
        ...

    raise TypeError(f'Fail to resolve Literal mro for {type(tt)}')
