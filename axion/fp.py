import dataclasses as dc
import typing as t

T = t.TypeVar('T')

RV = t.TypeVar('RV')
RE = t.TypeVar('RE')


@dc.dataclass(frozen=True)
class Result(t.Generic[RV, RE]):
    result: t.Optional[RV]
    error: t.Optional[RE]

    @classmethod
    def ok(cls, result: RV) -> 'Result[RV, RE]':
        return cls(result, None)

    @classmethod
    def fail(cls, error: RE) -> 'Result[RV, RE]':
        return cls(None, error)

    def map(self, fn: t.Callable[[RV], T]) -> t.Optional[T]:
        return fn(self.result) if self.result else None

    @staticmethod
    def is_ok(r: 'Result') -> bool:
        return r.result is not None

    @staticmethod
    def is_fail(r: 'Result') -> bool:
        return r.error is not None
