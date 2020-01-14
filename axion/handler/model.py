from dataclasses import dataclass
import functools
import re
import sys
import typing as t

import multidict as md
import typing_extensions as te

from axion import oas
from axion import response
from axion.utils import types

if sys.version_info >= (3, 8):
    cached_property = functools.cached_property
else:
    from cached_property import cached_property

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


@dataclass(frozen=True, repr=True)
class Handler(t.Generic[F]):
    fn: F
    has_body: bool
    param_mapping: ParamMapping

    @cached_property
    def path_params(self) -> md.CIMultiDict[FunctionArgName]:
        return self._params('path')

    @cached_property
    def header_params(self) -> md.CIMultiDict[FunctionArgName]:
        return self._params('header')

    @cached_property
    def query_params(self) -> md.CIMultiDict[FunctionArgName]:
        return self._params('query')

    @cached_property
    def cookie_params(self) -> md.CIMultiDict[FunctionArgName]:
        return self._params('cookie')

    def _params(
            self,
            param_in: oas.OASParameterLocation,
    ) -> md.CIMultiDict[FunctionArgName]:
        return md.CIMultiDict({
            oas_param.param_name: fn_param
            for oas_param, fn_param in self.param_mapping.items()
            if oas_param.param_in == param_in
        })


@te.final
class SyncHandler(Handler[t.Callable[..., response.Response]]):
    ...


@te.final
class AsyncHandler(Handler[t.Callable[..., t.Coroutine[t.Any, t.Any,
                                                       response.Response]]]):
    ...
