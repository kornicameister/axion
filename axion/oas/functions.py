import functools
import typing as t

from loguru import logger

from axion.oas import model

_PARAM_IN_TO_CLS_MAP = {
    'path': model.OASPathParameter,
    'query': model.OASQueryParameter,
    'cookie': model.OASCookieParameter,
    'header': model.OASHeaderParameter,
}  # type: t.Dict[model.OASParameterLocation, t.Type[model.OASParameter]]
_PARAM_CLS_TO_IN_MAP = {v: k for k, v in _PARAM_IN_TO_CLS_MAP.items()}
DV = t.Union[int,
             float,
             complex,
             str,
             bool,
             t.Mapping[t.Any, t.Any],
             t.Collection[t.Any],
             ]


@functools.lru_cache()
def operation_filter_parameters(
    operation: model.OASOperation,
    *types: model.OASParameterLocation,
) -> t.Sequence[model.OASParameter]:
    expected_types = tuple(
        param_type for param_in, param_type in _PARAM_IN_TO_CLS_MAP.items()
        if (param_in in types)
    )
    logger.opt(lazy=True).debug(
        'Filtering operation parameters by {expected_types}',
        expected_types=lambda: expected_types,
    )

    return list(filter(lambda p: isinstance(p, expected_types), operation.parameters))


def parameter_in(param: model.OASParameter) -> model.OASParameterLocation:
    return _PARAM_CLS_TO_IN_MAP[type(param)]


def parameter_default_values(param: model.OASParameter) -> t.Sequence[DV]:
    def _filter(v: t.Any) -> bool:
        return v is not None and isinstance(
            v,
            (
                int,
                float,
                complex,
                str,
                bool,
                dict,
                list,
                set,
            ),
        )

    if isinstance(param.schema, tuple):
        oas_type, _ = param.schema
        dvs = [oas_type.default]
    else:
        dvs = [v.schema.default for v in param.schema.values()]
    return t.cast(t.Sequence[DV], tuple(filter(_filter, dvs)))
