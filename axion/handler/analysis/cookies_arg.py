import typing as t

from loguru import logger
import typing_extensions as te

from axion import oas
from axion.handler import exceptions
from axion.handler import model
from axion.utils import get_type_repr
from axion.utils import types


def analyze(
    parameters: t.Sequence[oas.OASParameter],
    cookies_arg: t.Optional[t.Type[t.Any]],
) -> t.Tuple[t.Set[exceptions.Error], model.ParamMapping]:
    """Analyzes signature of the handler against the cookies.

    axion supports defining cookies in signature using:
    - typing_extensions.TypedDict
    - typing.Mapping
    - typing.Dict
    - Any other type is rejected with appropriate error.

    Also, when parsing the signature along with operation, following is taken
    into account:
    1. function does not have "cookies" argument and there are no custom OAS cookies
        - OK
    2. function has "cookies" argument and there no custom OAS cookies ->
        - Error
    3. function does not have "cookies" argument and there are custom OAS cookies
        - Warning
        - If there are custom cookies defined user ought to specify them
          in signature. There was a point to put them inside there after all.
          However they might be used by a middleware or something, not necessarily
          handler. The warning is the only reliable thing to say.
    4. function has "cookies" argument and there are customer OAS cookies
        - OK
        - With Mapping/Dict all parameters go as they are defined in operation
        - With TypedDict allowed keys are only those defined in operation
    """
    has_param_cookies = len(parameters) > 0

    if cookies_arg is not None:
        # pre-check type of headers param in signature
        # must be either TypedDict, Mapping, Dict or a subclass of those
        is_mapping, is_any = (
            types.is_dict_like(cookies_arg),
            types.is_any_type(cookies_arg),
        )
        if not (is_mapping or is_any):
            return {
                exceptions.Error(
                    param_name='cookies',
                    reason=exceptions.IncorrectTypeReason(
                        actual=cookies_arg,
                        expected=model.COOKIES_HEADERS_TYPE,
                    ),
                ),
            }, {}
        elif is_any:
            logger.warning(
                'Detected usage of "cookies" declared as typing.Any. '
                'axion will allow such declaration but be warned that '
                'you will loose all the help linters (like mypy) offer.',
            )
        if has_param_cookies:
            return _signature_set_oas_set(
                parameters=parameters,
                cookies_arg=cookies_arg,
            )
        else:
            return _signature_set_oas_gone(cookies_arg)
    elif has_param_cookies:
        return _signature_gone_oas_set()
    else:
        return _signature_gone_oas_gone()


def _signature_gone_oas_gone() -> t.Tuple[t.Set[exceptions.Error], model.ParamMapping]:
    logger.debug('No "cookies" in signature and operation parameters')
    return set(), {}


def _signature_gone_oas_set() -> t.Tuple[t.Set[exceptions.Error], model.ParamMapping]:
    logger.opt(lazy=True).warning(
        '"cookies" found in operation but not in signature. '
        'Please double check that. axion cannot infer a correctness of '
        'this situations. If you wish to access any "cookies" defined in '
        'specification, they have to be present in your handler '
        'as {types}.',
        types=lambda: [
            get_type_repr.get_repr(x)
            for x in (t.Dict[str, t.Any], t.Mapping[str, t.Any], te.TypedDict)
        ],
    )
    return set(), {}


def _signature_set_oas_gone(
    cookies_arg: t.Any,
) -> t.Tuple[t.Set[exceptions.Error], model.ParamMapping]:
    logger.error('"cookies" found in signature but not in operation')
    return {
        exceptions.Error(
            param_name='cookies',
            reason='unexpected',
        ),
    }, {}


def _signature_set_oas_set(
    parameters: t.Sequence[oas.OASParameter],
    cookies_arg: t.Any,
) -> t.Tuple[t.Set[exceptions.Error], model.ParamMapping]:
    logger.debug('"cookies" found both in signature and operation')

    errors: t.Set[exceptions.Error] = set()

    param_mapping: t.Dict[model.OASParam, model.FunctionArgName] = {}
    param_cookies = {model.get_f_param(rh.name): rh.name for rh in parameters}

    try:
        entries = t.get_type_hints(cookies_arg).items()
        if entries:
            for cookie_param_name, cookie_param_type in entries:
                if cookie_param_name in param_cookies:

                    oas_param = next(
                        filter(
                            lambda p: p.name == param_cookies[
                                model.get_f_param(cookie_param_name)],
                            parameters,
                        ),
                    )
                    oas_param_type = model.convert_oas_param_to_ptype(oas_param)
                    if oas_param_type != cookie_param_type:
                        errors.add(
                            exceptions.Error(
                                param_name=f'cookies.{cookie_param_name}',
                                reason=exceptions.IncorrectTypeReason(
                                    actual=cookie_param_type,
                                    expected=[oas_param_type],
                                ),
                            ),
                        )
                    else:
                        param_mapping[model.OASParam(
                            param_in='cookie',
                            param_name=param_cookies[model.get_f_param(
                                cookie_param_name,
                            )],
                        )] = model.get_f_param(cookie_param_name)

                else:
                    errors.add(
                        exceptions.Error(
                            param_name=f'cookies.{cookie_param_name}',
                            reason='unknown',
                        ),
                    )
        else:
            raise TypeError(
                'Not TypedDict to jump into exception below. '
                'This is 3.6 compatibility action.',
            )
    except TypeError:
        for hdr_param_name, hdr_param_type in param_cookies.items():
            param_mapping[model.OASParam(
                param_in='cookie',
                param_name=hdr_param_type,
            )] = hdr_param_name

    return errors, param_mapping
