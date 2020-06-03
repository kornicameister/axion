import dataclasses as dc
import functools
import re
import typing as t

import multidict as md
import typing_extensions as te

from axion import oas
from axion import response
from axion.utils import types

HTTP_CODE_TYPE: te.Final = int
COOKIES_HEADERS_TYPE: te.Final = [
    t.Mapping[str, t.Any],
    t.Dict[str, t.Any],
    te.TypedDict,
]
BODY_TYPES: te.Final = [
    t.Mapping[str, t.Any],
    t.Dict[str, t.Any],
]
AXION_RESPONSE_ENTRIES: te.Final = response.Response.__annotations__.copy()
AXION_RESPONSE_KEYS: te.Final = frozenset(AXION_RESPONSE_ENTRIES.keys())

OASParam = t.NamedTuple(
    'OAS_Param',
    (
        ('param_in', oas.OASParameterLocation),
        ('param_name', str),
    ),
)
FunctionArgName = t.NewType('FunctionArgName', str)
ParamMapping = t.Mapping[OASParam, FunctionArgName]


class AnalysisResult(t.NamedTuple):
    param_mapping: ParamMapping
    has_body: bool


CamelCaseToSnakeCaseRegex = re.compile(r'(?!^)(?<!_)([A-Z])')


@functools.lru_cache()
def get_f_param(s: str) -> FunctionArgName:
    return FunctionArgName(
        CamelCaseToSnakeCaseRegex.sub(r'_\1', s.replace('-', '_')).lower(),
    )


def convert_oas_param_to_ptype(param: oas.OASParameter) -> t.Any:
    p_type = param.python_type
    p_required = param.required
    if not p_required:
        return t.Optional[p_type]
    else:
        return p_type


F = t.TypeVar('F', bound=types.AnyCallable)


@dc.dataclass(frozen=True, repr=True)
class Handler(t.Generic[F]):
    fn: F
    has_body: bool

    param_mapping: dc.InitVar[ParamMapping]
    path_params: t.Mapping[str, str] = dc.field(
        init=False,
        metadata={
            'oas_param_loc': 'path',
        },
        repr=False,
    )
    header_params: t.Mapping[str, str] = dc.field(
        init=False,
        metadata={
            'oas_param_loc': 'header',
        },
        repr=False,
    )
    query_params: t.Mapping[str, str] = dc.field(
        init=False,
        metadata={
            'oas_param_loc': 'query',
        },
        repr=False,
    )
    cookie_params: t.Mapping[str, str] = dc.field(
        init=False,
        metadata={
            'oas_param_loc': 'cookies',
        },
        repr=False,
    )

    def __post_init__(
        self,
        param_mapping: ParamMapping,
    ) -> None:
        def _params(param_in: oas.OASParameterLocation) -> t.Mapping[str, str]:
            v: t.Mapping[str, str] = md.CIMultiDict({
                oas_param.param_name: fn_param
                for oas_param, fn_param in param_mapping.items()
                if oas_param.param_in == param_in
            })
            return v

        derived_params = {
            ('header_params', 'header'),
            ('path_params', 'path'),
            ('query_params', 'query'),
            ('cookie_params', 'cookie'),
        }  # type: t.Collection[t.Tuple[str, oas.OASParameterLocation]]
        for attr_name, param_loc in derived_params:
            object.__setattr__(self, attr_name, _params(param_loc))


@te.final
class SyncHandler(Handler[t.Callable[..., response.Response]]):
    ...


@te.final
class AsyncHandler(Handler[t.Callable[..., t.Coroutine[t.Any, t.Any,
                                                       response.Response]]]):
    ...
