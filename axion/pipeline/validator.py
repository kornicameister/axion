import abc
import dataclasses as dc
import typing as t

from returns import result as rr

from axion import oas
from axion import response


@dc.dataclass(frozen=True)
class ValidationError:
    message: str = dc.field(
        repr=False,
        metadata={'doc': 'Detailed message concerning an error.'},
    )
    oas_operation_id: oas.OASOperationId = dc.field(
        repr=True,
        metadata={
            'doc': 'OAS operation that triggered an error',
        },
    )
    occurred_at: str = dc.field(
        repr=True,
        metadata={
            'doc': (
                'Property path, i.e. "return.http_code" or '
                '"request.path_param[id]", that points at specific location '
                'where validation error occurred'
            ),
        },
    )


VT = t.TypeVar('VT')  # type of data validator...validates ;-)


class Validator(t.Generic[VT], abc.ABC):
    __slots__ = '_oas_operation'

    def __init__(self, oas_operation: oas.OASOperation) -> None:
        self._oas_operation = oas_operation

    @abc.abstractmethod
    def __call__(self, r: response.Response) -> rr.Result[VT, ValidationError]:
        raise NotImplementedError()


class HttpCodeValidator(Validator[int]):
    __slots__ = (
        '_allowed_codes',
        '_has_default',
    )

    def __init__(
            self,
            oas_operation: oas.OASOperation,
    ) -> None:
        super().__init__(oas_operation)
        self._allowed_codes = set(
            filter(lambda code: code != 'default', oas_operation.responses.keys()),
        )
        self._has_default = 'default' in oas_operation.responses.keys()

    def __call__(self, r: response.Response) -> rr.Result[int, ValidationError]:
        http_code = r['http_code']
        if http_code in self._allowed_codes:
            return rr.Success(http_code)
        elif self._has_default:
            return rr.Success(http_code)
        else:
            return rr.Failure(
                ValidationError(
                    message=(
                        f'HTTP code {http_code} does not match {self._oas_operation.id} '
                        f'response codes {{{", ".join(map(str, self._allowed_codes))}}}.'
                    ),
                    oas_operation_id=self._oas_operation.id,
                    occurred_at='return.http_code',
                ),
            )
