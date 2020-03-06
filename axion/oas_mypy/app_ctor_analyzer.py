from mypy.plugin import FunctionContext
from mypy.types import (
    Instance,
    LiteralType,
    Type,
)

from axion import _plugins as axion_plugins
from axion.oas_mypy import errors


def hook(f_ctx: FunctionContext) -> Type:
    plugin_id_idx = f_ctx.callee_arg_names.index('plugin_id')
    plugin_id_type = f_ctx.arg_types[plugin_id_idx][0]

    assert isinstance(plugin_id_type, Instance)
    assert isinstance(plugin_id_type.last_known_value, LiteralType)

    plugin_id = plugin_id_type.last_known_value.value

    if plugin_id not in axion_plugins():
        err_ctx = f_ctx.context
        err_ctx.line = f_ctx.args[plugin_id_idx][0].line

        f_ctx.api.msg.fail(
            f'{plugin_id} is not axion plugin',
            context=err_ctx,
            code=errors.ERROR_UNKNOWN_PLUGIN,
        )

    return f_ctx.default_return_type
