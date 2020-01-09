from pathlib import Path
import typing as t

import multidict as md
import pydantic as pd
import typing_extensions as te

__all__ = (
    'Headers',
    'Cookies',
    'HTTPCode',
    'HTTPBody',
    'Response',
)

Headers = t.NewType('Headers', t.Mapping[str, str])
Cookies = t.NewType('Cookies', t.Mapping[str, str])

Body = t.Any
Collection = t.Sequence[Body]
Stream = t.NewType('Stream', t.IO[bytes])
File = t.NewType('File', Path)

HTTPCode = t.NewType('HTTPCode', int)
HTTPBody = t.Optional[t.Union[Stream, Body, Collection, pd.BaseModel]]


class Response(te.TypedDict, total=False):
    """Axion framework response.

    This class represents **one** way to end axion's handler.
    Reason is simple: no ambiguity!.

    It is typed way to ensure that all handlers end in a same way while
    being flexible in what they respond with.

    """
    body: t.Any
    http_code: int
    headers: t.Mapping[str, str]
    cookies: t.Mapping[str, str]


@te.final
class AxionResponse(t.NamedTuple):
    """Internal representation of response.

    Class is built from an instance of `Response` and thus should not be
    used directly.

    """
    body: HTTPBody
    http_code: HTTPCode
    headers: Headers
    cookies: Cookies
