from typing import Optional

from mypy.errorcodes import ErrorCode
from mypy.plugin import FunctionContext
from mypy.types import Type
from typing_extensions import Final

ERROR_UNKNOWN_PLUGIN: Final[ErrorCode] = ErrorCode(
    'axion-no-plugin',
    'Unknown axion plugin',
    'Plugin',
)
ERROR_NOT_OAS_OP: Final[ErrorCode] = ErrorCode(
    'axion-no-op',
    'Handler does not match any OAS operation',
    'OAS',
)
ERROR_INVALID_OAS_ARG: Final[ErrorCode] = ErrorCode(
    'axion-arg-type',
    'Handler argument type does not conform to OAS specification',
    'OAS',
)
ERROR_INVALID_OAS_VALUE: Final[ErrorCode] = ErrorCode(
    'axion-arg-value',
    'Handler argument (default) value does not conform to OAS specification',
    'OAS',
)


def not_oas_handler(
        msg: str,
        code: ErrorCode,
        ctx: FunctionContext,
        line_number: Optional[int] = None,
) -> Type:
    context = ctx.context
    context.line = line_number or context.line

    ctx.api.msg.fail(
        msg,
        context=context,
        code=code,
    )

    return ctx.default_return_type
