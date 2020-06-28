import typing as t

from loguru import logger

from axion import oas
from axion.handler import exceptions
from axion.handler import model
from axion.utils import types

RESERVED_HEADERS: t.Mapping[model.FunctionArgName, str] = {
    model.get_f_param(rh): rh.lower()
    for rh in oas.OASReservedHeaders
}


def analyze(
    parameters: t.Sequence[oas.OASParameter],
    headers_arg: t.Optional[t.Type[t.Any]],
) -> t.Tuple[t.Set[exceptions.Error], model.ParamMapping]:
    """Analyzes signature of the handler against the headers.

    axion supports defining headers in signature using:
    - typing_extensions.TypedDict
    - typing.Mapping
    - typing.Dict
    - Any other type is rejected with appropriate error.

    Also, when parsing the signature along with operation, following is taken
    into account:
    1. function does not have "headers" argument and there are no custom OAS headers
        - OK
    2. function does not have "headers" argument and there are custom OAS headers
        - Warning
        - If there are custom headers defined user ought to specify them
          in signature. There was a point to put them inside there after all.
          However they might be used by a middleware or something, not necessarily
          handler. The warning is the only reliable thing to say.
    3. function has "headers" argument and there no custom OAS headers ->
        - OK
        - User might want to get_repr a hold with headers like "Content-Type"
        - With Mapping all reserved headers go in
        - With TypedDict we must see if users wants one of reserved headers
          Only reserved headers are allowed to be requested for.
    4. function has "headers" argument and there are customer OAS headers
        - OK
        - With Mapping all reserved headers + OAS headers go in
        - With TypedDict allowed keys covers
            - one or more of reserved headers
            - all of OAS headers with appropriate types

    See link bellow for information on reserved header
    https://swagger.io/docs/specification/describing-parameters/#header-parameters
    """
    has_param_headers = len(parameters) > 0

    if headers_arg is not None:
        # pre-check type of headers param in signature
        # must be either TypedDict, Mapping or a subclass of those
        is_mapping, is_any = (
            types.is_dict_like(headers_arg),
            types.is_any_type(headers_arg),
        )
        if not (is_mapping or is_any):
            return {
                exceptions.Error(
                    param_name='headers',
                    reason=exceptions.IncorrectTypeReason(
                        actual=headers_arg,
                        expected=model.COOKIES_HEADERS_TYPE,
                    ),
                ),
            }, {}
        elif is_any:
            logger.warning(
                'Detected usage of "headers" declared as typing.Any. '
                'axion will allow such declaration but be warned that '
                'you will loose all the help linters (like mypy) offer.',
            )
        if has_param_headers:
            return _analyze_headers_signature_set_oas_set(
                parameters=parameters,
                headers_arg=headers_arg,
            )
        else:
            return _signature_set_oas_gone(headers_arg)
    elif has_param_headers:
        return _signature_gone_oas_set()
    else:
        return _signature_gone_oas_gone()


def _signature_gone_oas_gone() -> t.Tuple[t.Set[exceptions.Error], model.ParamMapping]:
    logger.debug('No "headers" in signature and operation parameters')
    return set(), {}


def _signature_gone_oas_set() -> t.Tuple[t.Set[exceptions.Error], model.ParamMapping]:
    logger.warning(
        '"headers" found in operation but not in signature. '
        'Please double check that. axion cannot infer a correctness of '
        'this situations. If you wish to access any "headers" defined in '
        'specification, they have to be present in your handler '
        'as either "typing.Dict[str, typing.Any]", "typing.Mapping[str, typing.Any]" '
        'or typing_extensions.TypedDict[str, typing.Any].',
    )
    return set(), {}


def _signature_set_oas_gone(
    headers_arg: t.Any,
) -> t.Tuple[t.Set[exceptions.Error], model.ParamMapping]:
    logger.debug('"headers" found in signature but not in operation')

    errors: t.Set[exceptions.Error] = set()
    param_mapping: t.Dict[model.OASParam, model.FunctionArgName] = {}

    try:
        # deal with typed dict, only reserved headers are allowed as dict
        entries = t.get_type_hints(headers_arg).items()
        if entries:
            for hdr_param_name, hdr_param_type in entries:
                if hdr_param_name not in RESERVED_HEADERS:
                    logger.error(
                        '{sig_key} is not one of {reserved_headers} headers',
                        sig_key=hdr_param_name,
                        reserved_headers=oas.OASReservedHeaders,
                    )
                    errors.add(
                        exceptions.Error(
                            param_name=f'headers.{hdr_param_name}',
                            reason='unknown',
                        ),
                    )
                elif hdr_param_type != str:
                    errors.add(
                        exceptions.Error(
                            param_name=f'headers.{hdr_param_name}',
                            reason=exceptions.IncorrectTypeReason(
                                actual=hdr_param_type,
                                expected=[str],
                            ),
                        ),
                    )
                else:
                    param_key = model.get_f_param(hdr_param_name)
                    param_mapping[model.OASParam(
                        param_in='header',
                        param_name=RESERVED_HEADERS[param_key],
                    )] = param_key
        else:
            raise TypeError(
                'Not TypedDict to jump into exception below. '
                'This is 3.6 compatibility action.',
            )
    except TypeError:
        # deal with mapping: in that case user will receive all
        # reserved headers inside of the handler
        for hdr_f_name, hdr_name in RESERVED_HEADERS.items():
            param_mapping[model.OASParam(
                param_in='header',
                param_name=hdr_name.lower(),
            )] = hdr_f_name

    return errors, param_mapping


def _analyze_headers_signature_set_oas_set(
    parameters: t.Sequence[oas.OASParameter],
    headers_arg: t.Any,
) -> t.Tuple[t.Set[exceptions.Error], model.ParamMapping]:
    logger.debug('"headers" found both in signature and operation')

    errors: t.Set[exceptions.Error] = set()
    param_mapping: t.Dict[model.OASParam, model.FunctionArgName] = {}

    param_headers = {model.get_f_param(rh.name): str(rh.name) for rh in parameters}
    all_headers_names = {
        **param_headers,
        **RESERVED_HEADERS,
    }

    try:
        entries = t.get_type_hints(headers_arg).items()
        if entries:
            for hdr_param_name, hdr_param_type in entries:
                if hdr_param_name in all_headers_names:
                    # now tricky part, for reserved headers we enforce str
                    # for oas headers we do type check
                    if hdr_param_name in RESERVED_HEADERS and hdr_param_type != str:
                        errors.add(
                            exceptions.Error(
                                param_name=f'headers.{hdr_param_name}',
                                reason=exceptions.IncorrectTypeReason(
                                    actual=hdr_param_type,
                                    expected=[str],
                                ),
                            ),
                        )
                        continue
                    elif hdr_param_name in param_headers:
                        oas_param = next(
                            filter(
                                lambda p: p.name == param_headers[
                                    model.get_f_param(hdr_param_name)],
                                parameters,
                            ),
                        )
                        oas_param_type = model.convert_oas_param_to_ptype(oas_param)
                        if oas_param_type != hdr_param_type:
                            errors.add(
                                exceptions.Error(
                                    param_name=f'headers.{hdr_param_name}',
                                    reason=exceptions.IncorrectTypeReason(
                                        actual=hdr_param_type,
                                        expected=[str],
                                    ),
                                ),
                            )
                            continue

                    param_mapping[model.OASParam(
                        param_in='header',
                        param_name=all_headers_names[model.get_f_param(
                            hdr_param_name,
                        )].lower(),
                    )] = model.get_f_param(hdr_param_name)

                else:
                    errors.add(
                        exceptions.Error(
                            param_name=f'headers.{hdr_param_name}',
                            reason='unknown',
                        ),
                    )
        else:
            raise TypeError(
                'Not TypedDict to jump into exception below. '
                'This is 3.6 compatibility action.',
            )
    except TypeError:
        for hdr_param_name, hdr_param_type in all_headers_names.items():
            param_mapping[model.OASParam(
                param_in='header',
                param_name=hdr_param_type.lower(),
            )] = hdr_param_name

    return errors, param_mapping
