from axion.application import base_path
from axion.application import handler

resolve_handler = handler.make
InvalidHandlerError = handler.InvalidHandlerError

get_base_path = base_path.make

__all__ = [
    # handler operationss
    'resolve_handler',
    'InvalidHandlerError',
    # base path operations
    'get_base_path',
]
