import functools
import typing as t

from loguru import logger

from axion.specification import model

_PARAM_IN_TO_CLS_MAP = {
    'path': model.OASPathParameter,
    'query': model.OASQueryParameter,
    'cookie': model.OASCookieParameter,
    'header': model.OASHeaderParameter,
}  # type: t.Dict[model.OASParameterLocation, t.Type[model.OASParameter]]
_PARAM_CLS_TO_IN_MAP = {v: k for k, v in _PARAM_IN_TO_CLS_MAP.items()}


@functools.lru_cache(maxsize=100)
def operation_filter_parameters(
        operation: model.OASOperation,
        *types: model.OASParameterLocation,
) -> t.Sequence[model.OASParameter]:
    expected_types = tuple(
        param_type for param_in, param_type in _PARAM_IN_TO_CLS_MAP.items()
        if (param_in in types)
    )
    logger.opt(
        record=True,
        lazy=True,
    ).debug(
        'Filtering operation parameters by {expected_types}',
        expected_types=lambda: expected_types,
    )

    return list(filter(lambda p: isinstance(p, expected_types), operation.parameters))


@functools.lru_cache(maxsize=100)
def parameter_in(param: model.OASParameter) -> model.OASParameterLocation:
    return _PARAM_CLS_TO_IN_MAP[type(param)]
