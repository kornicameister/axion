import typing as t

from loguru import logger
import typing_inspect as ti

from axion.utils import types


def get_repr(val: t.Any) -> str:
    logger.opt(lazy=True).trace(
        'Getting string representation for val={val}',
        val=lambda: val,
    )
    return _repr(val)


def _repr(val: t.Any) -> str:

    assert val is not None

    if types.is_none_type(val):
        return 'NoneType'
    elif ti.is_literal_type(val):
        return str(val)
    elif ti.is_new_type(val):
        nested_type = val.__supertype__
        return f'{_qualified_name(val)}[{get_repr(nested_type)}]'
    elif ti.is_typevar(val):
        tv_constraints = ti.get_constraints(val)
        tv_bound = ti.get_bound(val)
        if tv_constraints:
            constraints_repr = (get_repr(tt) for tt in tv_constraints)
            return f'typing.TypeVar(?, {", ".join(constraints_repr)})'
        elif tv_bound:
            return get_repr(tv_bound)
        else:
            return 'typing.Any'
    elif ti.is_optional_type(val):
        optional_args = ti.get_args(val, True)[:-1]
        nested_union = len(optional_args) > 1
        optional_reprs = (get_repr(tt) for tt in optional_args)
        if nested_union:
            return f'typing.Optional[typing.Union[{", ".join(optional_reprs)}]]'
        else:
            return f'typing.Optional[{", ".join(optional_reprs)}]'
    elif ti.is_union_type(val):
        union_reprs = (get_repr(tt) for tt in ti.get_args(val, True))
        return f'typing.Union[{", ".join(union_reprs)}]'
    elif ti.is_generic_type(val):
        attr_name = val._name
        generic_reprs = (get_repr(tt) for tt in ti.get_args(val, evaluate=True))
        return f'typing.{attr_name}[{", ".join(generic_reprs)}]'
    else:
        val_name = _qualified_name(val)
        maybe_td_entries = getattr(val, '__annotations__', {}).copy()
        if maybe_td_entries:
            # we are dealing with typed dict
            # that's quite lovely
            td_keys = sorted(maybe_td_entries.keys())
            internal_members_repr = ', '.join(
                '{key}: {type}'.format(key=k, type=get_repr(maybe_td_entries.get(k)))
                for k in td_keys
            )
            return f'{val_name}{{{internal_members_repr}}}'
        elif 'TypedDict' == getattr(val, '__name__', ''):
            return 'typing_extensions.TypedDict'
        else:
            return val_name


def _qualified_name(tt: t.Type[t.Any]) -> str:
    the_name = str(tt)

    if 'typing' not in the_name:
        the_name = tt.__name__ or tt.__qualname__

    return the_name
