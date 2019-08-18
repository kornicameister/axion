from axion.application import handler

resolve_handler = handler.resolve
InvalidHandlerError = handler.InvalidHandlerError

__all__ = [
    'resolve_handler',
    'InvalidHandlerError',
]
