import typing as t

from loguru import logger
import typing_inspect as ti

from axion import oas
from axion.handler import exceptions
from axion.handler import model


def analyze(
    request_body: t.Optional[oas.OASRequestBody],
    body_arg: t.Optional[t.Type[t.Any]],
) -> t.Tuple[t.Set[exceptions.Error], bool]:
    if body_arg is None:
        if request_body is None:
            return _analyze_signature_gone_oas_gone()
        else:
            return _analyze_signature_gone_oas_set()
    else:
        if request_body is None:
            return _analyze_signature_set_oas_gone()
        else:
            return _analyze_signature_set_oas_set(
                request_body=request_body,
                body_arg=body_arg,
            )


def _analyze_signature_set_oas_set(
    request_body: oas.OASRequestBody,
    body_arg: t.Type[t.Any],
) -> t.Tuple[t.Set[exceptions.Error], bool]:
    logger.opt(
        lazy=True,
        record=True,
    ).trace(
        'Operation defines both request body and argument handler',
    )
    is_required = request_body.required
    is_arg_required = not ti.is_optional_type(body_arg)

    if is_required and not is_arg_required:
        return {
            exceptions.Error(
                param_name='body',
                reason=exceptions.IncorrectTypeReason(
                    actual=body_arg,
                    expected=model.BODY_TYPES,
                ),
            ),
        }, True
    return set(), True


def _analyze_signature_set_oas_gone() -> t.Tuple[t.Set[exceptions.Error], bool]:
    logger.opt(
        lazy=True,
        record=True,
    ).error(
        'Operation does not define a request body, but it is '
        'specified in handler signature.',
    )
    return {
        exceptions.Error(
            param_name='body',
            reason='unexpected',
        ),
    }, False


def _analyze_signature_gone_oas_gone() -> t.Tuple[t.Set[exceptions.Error], bool]:
    logger.opt(
        lazy=True,
        record=True,
    ).trace(
        'Operation does not define a request body',
    )
    return set(), False


def _analyze_signature_gone_oas_set() -> t.Tuple[t.Set[exceptions.Error], bool]:
    logger.opt(
        lazy=True,
        record=True,
    ).error(
        'Operation defines a request body, but it is not specified in '
        'handler signature',
    )
    return {
        exceptions.Error(
            param_name='body',
            reason='missing',
        ),
    }, True
