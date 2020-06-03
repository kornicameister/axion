import typing as t

import multidict as md
import typing_extensions as te

from axion.utils import get_type_repr


class IncorrectTypeReason:
    expected: t.Sequence[t.Any]
    actual: t.Any

    def __init__(self, expected: t.Sequence[t.Any], actual: t.Any) -> None:
        self.expected = expected
        self.actual = actual

    def __repr__(self) -> str:
        expected_str = ','.join(get_type_repr.get_repr(rt) for rt in self.expected)
        actual_str = get_type_repr.get_repr(self.actual)
        return f'expected [{expected_str}], but got {actual_str}'


CustomReason = t.NewType('CustomReason', str)
CommonReasons = te.Literal['missing', 'unexpected', 'unknown']
Reason = t.Union[CommonReasons, IncorrectTypeReason, CustomReason]


class Error(t.NamedTuple):
    reason: Reason
    param_name: str


@te.final
class InvalidHandlerError(
        ValueError,
        t.Mapping[str, str],
):
    __slots__ = (
        '_operation_id',
        '_errors',
    )

    def __init__(
        self,
        operation_id: str,
        errors: t.Optional[t.AbstractSet[Error]] = None,
        message: t.Optional[str] = None,
    ) -> None:
        header_msg = f'\n{operation_id} handler mismatch signature:'

        if errors and not message:
            error_str = '\n'.join(
                f'argument {m.param_name} :: {m.reason}' for m in errors
            )
            super().__init__('\n'.join([
                header_msg,
                error_str,
            ]))
        else:
            super().__init__(message)

        self._errors = frozenset(errors or [])
        self._operation_id = operation_id

    @property
    def operation_id(self) -> str:
        return self._operation_id

    @property
    def reasons(self) -> t.Mapping[str, str]:
        v: t.Mapping[str, str]
        v = md.CIMultiDict({e.param_name: str(e.reason) for e in self._errors or []})
        return v

    def __iter__(self) -> t.Iterator[Error]:  # type: ignore
        return iter(e for e in self._errors or [])

    def __len__(self) -> int:
        return len(self._errors or [])

    def __getitem__(self, key: str) -> str:
        assert isinstance(
            key,
            str,
        ), f'{key} must be {type(str)}, but it was {type(object)}'
        return self.reasons[key]

    def __repr__(self) -> str:
        repr_reasons = (f'{k}: {v}' for k, v in self.reasons.items())
        return f'InvalidHandlerError :: {", ".join(repr_reasons)}'
