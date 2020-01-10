import collections
import functools
import typing as t

import more_itertools
import typing_inspect as ti

P_TYPES = (
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


def is_new_type(tt: t.Type[t.Any]) -> bool:
    return getattr(tt, '__supertype__', None) is not None


def is_none_type(tt: t.Type[t.Any]) -> bool:
    try:
        return issubclass(type(None), tt)
    except TypeError:
        return False


def is_any_type(tt: t.Any) -> bool:
    return tt is t.Any


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

    if is_new_type(tt):
        return is_dict_like(tt.__supertype__)
    elif maybe_mro:
        return any(issubclass(mro, (dict, collections.abc.Mapping)) for mro in maybe_mro)
    else:
        return False


@functools.lru_cache(maxsize=100, typed=True)
def literal_types(tt: t.Any) -> t.Iterable[PP]:
    assert ti.is_literal_type(tt)
    pps = [_literal_types(x) for x in ti.get_args(tt, ti.NEW_TYPING)]
    return frozenset(more_itertools.flatten(pps))


def _literal_types(tt: t.Any) -> t.Iterable[PP]:
    try:
        val = None

        if isinstance(tt, P_TYPES):
            val = (type(tt), )
        assert val is not None

        return val
    except (AssertionError, TypeError):
        if ti.is_literal_type(tt):
            return literal_types(tt)
        elif is_new_type(tt):
            return literal_types(tt.__supertype__)
    raise TypeError(f'Fail to resolve Literal mro for {type(tt)}')
