import typing as t

from loguru import logger

from axion import oas
from axion.handler import exceptions
from axion.handler import model
from axion.handler.analysis import body_arg
from axion.handler.analysis import cookies_arg
from axion.handler.analysis import headers_arg
from axion.handler.analysis import path_query_arg
from axion.handler.analysis import return_type
from axion.utils import types


def analyze(
    handler: types.AnyCallable,
    operation: oas.OASOperation,
) -> model.AnalysisResult:
    logger.opt(
        record=True,
        lazy=True,
    ).debug(
        'Analyzing operation {id}',
        id=lambda: operation.id,
    )
    signature = t.get_type_hints(handler)

    errors, has_body = body_arg.analyze(
        operation.request_body,
        signature.pop('body', None),
    )
    rt_errors = return_type.analyze(
        operation,
        signature,
    )

    errors.update(rt_errors)
    param_mapping: t.Dict[model.OASParam, model.FunctionArgName] = {}

    if operation.parameters:
        h_errors, h_params = headers_arg.analyze(
            oas.operation_filter_parameters(operation, 'header'),
            signature.pop('headers', None),
        )
        c_errors, c_params = cookies_arg.analyze(
            oas.operation_filter_parameters(operation, 'cookie'),
            signature.pop('cookies', None),
        )
        pq_errors, pq_params = path_query_arg.analyze(
            oas.operation_filter_parameters(operation, 'path', 'query'),
            signature,
        )

        if signature:
            logger.opt(record=True).error(
                'Unconsumed arguments [{f_args}] detected in {op_id} handler signature',
                op_id=operation.id,
                f_args=', '.join(arg_key for arg_key in signature.keys()),
            )
            errors.update(
                exceptions.Error(
                    param_name=arg_key,
                    reason='unexpected',
                ) for arg_key in signature.keys()
            )

        errors.update(pq_errors, h_errors, c_errors)
        param_mapping.update(pq_params)
        param_mapping.update(h_params)
        param_mapping.update(c_params)
    else:
        logger.opt(
            lazy=True,
            record=True,
        ).debug(
            '{op_id} does not declare any parameters',
            op_id=lambda: operation.id,
        )

    if errors:
        logger.opt(record=True).error(
            'Collected {count} mismatch error{s} for {op_id} handler',
            count=len(errors),
            op_id=operation.id,
            s='s' if len(errors) > 1 else '',
        )
        raise exceptions.InvalidHandlerError(
            operation_id=operation.id,
            errors=errors,
        )

    return model.AnalysisResult(
        param_mapping=param_mapping,
        has_body=has_body,
    )
