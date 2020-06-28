import typing as t

from loguru import logger
import typing_extensions as te

from axion import oas
from axion.handler import exceptions
from axion.handler import model

LOG: te.Final = logger.opt(lazy=True)


def analyze(
    parameters: t.Sequence[oas.OASParameter],
    signature: t.Dict[str, t.Type[t.Any]],
) -> t.Tuple[t.Set[exceptions.Error], model.ParamMapping]:
    errors: t.Set[exceptions.Error] = set()
    param_mapping: t.Dict[model.OASParam, model.FunctionArgName] = {}

    for op_param in parameters:
        LOG.debug('Analyzing parameter={p}', p=lambda: op_param)
        try:
            handler_param_name = model.get_f_param(op_param.name)

            handler_param_type = signature.pop(handler_param_name)
            op_param_type = model.convert_oas_param_to_ptype(op_param)

            LOG.trace(
                'parameter={p} => p_type={p_type} f_type={f_type}',
                p=lambda: op_param,
                p_type=lambda: op_param_type,
                f_type=lambda: handler_param_type,
            )

            if handler_param_type != op_param_type:
                errors.add(
                    exceptions.Error(
                        param_name=op_param.name,
                        reason=exceptions.IncorrectTypeReason(
                            actual=handler_param_type,
                            expected=[op_param_type],
                        ),
                    ),
                )
            else:
                key = model.OASParam(
                    param_in=oas.parameter_in(op_param),
                    param_name=op_param.name,
                )
                param_mapping[key] = handler_param_name
        except KeyError:
            errors.add(
                exceptions.Error(
                    param_name=op_param.name,
                    reason='missing',
                ),
            )

    return errors, param_mapping
