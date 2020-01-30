from asyncio import iscoroutinefunction
from functools import wraps
from typing import Any, NamedTuple

from axion.oas.model import OASOperationId
from axion.utils.types import AnyCallable

__all__ = ('oas_endpoint', )


def oas_endpoint(f: AnyCallable) -> AnyCallable:
    """Decorates the OAS handler for static analysis.

    This decorator has no <b>runtime</b> applications.
    It's purpose is to mark OAS handlers so that they can
    be found by mypy plugin.

    Decorator will also put some metadata onto returned wrapper.
    Metadata, accessible via "__axion_meta__" key, can be examined but
    must not be relied on. This is internal implementation detail that
    can change without any notice.

    """

    if iscoroutinefunction(f):

        @wraps(f)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await f(*args, **kwargs)  # pragma: no cover
    else:

        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return f(*args, **kwargs)  # pragma: no cover

    operation_id = OASOperationId(f'{f.__module__}.{f.__name__}')
    setattr(  # noqa
        wrapper,
        '__axion_meta__',
        EndpointMeta(
            operation_id=operation_id,
            asynchronous=iscoroutinefunction(f),
        ),
    )

    return wrapper


class EndpointMeta(NamedTuple):
    operation_id: OASOperationId
    asynchronous: bool
