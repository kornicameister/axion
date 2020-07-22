import dataclasses as dc
import functools
import re
import typing as t

import multidict as md
import typing_extensions as te

from axion import oas
from axion import pipeline
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
AXION_RESPONSE_ENTRIES: te.Final = pipeline.Response.__annotations__.copy()
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


UF = t.TypeVar('UF', bound=types.AnyCallable)
UF.__doc__ = 'User defined API handler'

RQP = t.TypeVar('RQP', bound=types.AnyCallable)
RQP.__doc__ = 'Request processor callable'

RPP = t.TypeVar('RPP', bound=types.AnyCallable)
RPP.__doc__ = 'Response processor callable'

RQ = t.TypeVar('RQ')  # request
RP = t.TypeVar('RP')  # response


@dc.dataclass(frozen=True, repr=True)
class BaseHandler(t.Generic[UF, RQP, RPP]):
    # init vars
    param_mapping: dc.InitVar[ParamMapping]

    # functions
    user_handler: UF
    request_processor: RQP
    response_processor: RPP

    # handler analysis results
    # TODO(kornicameister) create own object
    has_body: bool
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


SyncCallable = t.Callable[..., pipeline.Response]
SyncRequestProcessor = t.Callable[[RQ], pipeline.Request]
SyncResponseProcessor = t.Callable[[pipeline.Response], RP]

AsyncCallable = t.Callable[..., t.Coroutine[None, None, pipeline.Response]]
AsyncRequestProcessor = t.Callable[[RQ], t.Coroutine[None, None, pipeline.Request]]
AsyncResponseProcessor = t.Callable[[pipeline.Response], t.Coroutine[None, None, RP]]

RequestProcessor = t.Union[SyncRequestProcessor[RQ], AsyncRequestProcessor[RQ]]
ResponseProcessor = t.Union[SyncResponseProcessor[RP], AsyncResponseProcessor[RP]]


@te.final
class SyncHandler(BaseHandler[SyncCallable, SyncRequestProcessor[RQ],
                              SyncResponseProcessor[RP]]):
    ...


@te.final
class AsyncHandler(BaseHandler[AsyncCallable, AsyncRequestProcessor[RQ],
                               AsyncResponseProcessor[RP]]):
    ...


Handler = t.Union[SyncHandler, AsyncHandler]
