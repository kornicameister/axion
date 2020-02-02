from configparser import ConfigParser
from functools import (partial, reduce, singledispatch)
from operator import attrgetter
from pathlib import Path
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    Type as TypingType,
)

from mypy.checker import TypeChecker
from mypy.errorcodes import ErrorCode
from mypy.messages import format_type
from mypy.nodes import FuncDef
from mypy.options import Options
from mypy.plugin import (FunctionContext, MethodContext, Plugin)
from mypy.sametypes import SameTypeVisitor
from mypy.types import (
    AnyType,
    CallableType,
    get_proper_type,
    Instance,
    LiteralType,
    NoneType,
    Type,
    TypeOfAny,
    UnionType,
)
from mypy_extensions import DefaultNamedArg
from typing_extensions import Final

from axion import (
    _plugins as axion_plugins,
)
from axion.handler.model import get_f_param
from axion.oas import (
    load as load_oas_spec,
    OASOperation,
    OASParameter,
    OASSpecification,
    operation_filter_parameters,
    parameter_default_values,
    parameter_in,
)
from axion.oas.model import (
    OASArrayType,
    OASBooleanType,
    OASNumberType,
    OASObjectType,
    OASStringType,
)

AXION_CTR: Final[str] = 'axion.Axion'
AXION_ENDPOINT: Final[str] = 'axion.oas.endpoint.oas_endpoint'

CONFIGFILE_KEY: Final[str] = 'axion-mypy'

ERROR_UNKNOWN_PLUGIN: Final[ErrorCode] = ErrorCode(
    'axion-no-plugin',
    'Unknown axion plugin',
    'Plugin',
)
ERROR_NOT_OAS_OP: Final[ErrorCode] = ErrorCode(
    'axion-no-op',
    'Handler does not match any OAS operation',
    'OAS',
)
ERROR_INVALID_OAS_ARG: Final[ErrorCode] = ErrorCode(
    'axion-arg-type',
    'Handler argument type does not conform to OAS specification',
    'OAS',
)
ERROR_INVALID_OAS_VALUE: Final[ErrorCode] = ErrorCode(
    'axion-arg-value',
    'Handler argument (default) value does not conform to OAS specification',
    'OAS',
)

_ARG_NO_DEFAULT_VALUE_MARKER = object()
HandlerArgDefaultValue = Any


class OASPluginConfig:
    __slots__ = ('oas_dirs', )

    def __init__(self, options: Options) -> None:
        if options.config_file is None:  # pragma: no cover
            return

        plugin_config = ConfigParser()
        plugin_config.read(options.config_file)

        self.oas_dirs = (
            Path(rd) for rd in plugin_config.get(
                CONFIGFILE_KEY,
                'oas_directories',
                fallback='',
            ).split(',')
        )


class OASPlugin(Plugin):
    __slots__ = (
        '_cfg',
        '_specifications',
    )

    def __init__(self, options: Options) -> None:
        super().__init__(options)
        self._cfg = OASPluginConfig(options)
        self._specifications = _load_specs(list(self._cfg.oas_dirs))

    def get_function_hook(
            self,
            fullname: str,
    ) -> Optional[Callable[[FunctionContext], Type]]:
        if AXION_CTR == fullname:
            return _axion_ctor_analyzer
        elif AXION_ENDPOINT == fullname:
            return partial(
                _oas_handler_analyzer,
                self._specifications,
            )
        return super().get_function_hook(fullname)

    def get_method_hook(
            self,
            fullname: str,
    ) -> Optional[Callable[[MethodContext], Type]]:
        # TODO(kornicameister) add_api customizations
        # enforcing settings middlewares for aiohttp plugin maybe
        return super().get_method_hook(fullname)


def _axion_ctor_analyzer(f_ctx: FunctionContext) -> Type:
    plugin_id_idx = f_ctx.callee_arg_names.index('plugin_id')
    plugin_id_type = f_ctx.arg_types[plugin_id_idx][0]

    assert isinstance(plugin_id_type, Instance)
    assert isinstance(plugin_id_type.last_known_value, LiteralType)

    plugin_id = plugin_id_type.last_known_value.value

    if plugin_id not in axion_plugins():
        err_ctx = f_ctx.context
        err_ctx.line = f_ctx.args[plugin_id_idx][0].line

        f_ctx.api.fail(
            f'{plugin_id} is not axion plugin',
            ctx=err_ctx,
            code=ERROR_UNKNOWN_PLUGIN,
        )

    return f_ctx.default_return_type


def _oas_handler_analyzer(
        specifications: Mapping[Path, OASSpecification],
        f_ctx: FunctionContext,
) -> Type:
    # TODO(kornicameister) make `OASSpectification.operations` a mapping
    # to allow easy access

    oas_handler = f_ctx.arg_types[0][0]

    assert isinstance(oas_handler, CallableType)
    assert oas_handler.definition

    f_name = oas_handler.name
    oas_operation = _get_oas_operation(
        oas_handler.definition.fullname,
        specifications,
    )

    if oas_operation is None:
        return _oas_handler_msg(
            f_ctx.api.msg.fail,
            f_ctx,
            (ERROR_NOT_OAS_OP, f'{f_name} is not OAS operation'),
            line_number=oas_handler.definition.line,
        )

    signature: Dict[str, Type] = {
        k: v
        for k, v in dict(
            zip(
                oas_handler.arg_names,
                oas_handler.arg_types,
            ),
        ).items() if k is not None
    }.copy()

    for oas_param, f_param in map(
            lambda ofp: (ofp, get_f_param(ofp.name)),
            operation_filter_parameters(
                oas_operation,
                'path',
                'query',
            ),
    ):
        handler_arg_type: Optional[Type] = signature.pop(f_param, None)
        handler_arg_default_value = _get_default_value(f_param, oas_handler)
        oas_default_values = parameter_default_values(oas_param)

        if handler_arg_type is None:
            # log the fact that argument is not there
            _oas_handler_msg(
                f_ctx.api.msg.fail,
                f_ctx,
                (
                    ERROR_INVALID_OAS_ARG,
                    (
                        f'{f_name} does not declare OAS {parameter_in(oas_param)} '
                        f'{oas_param.name}::{f_param} argument'
                    ),
                ),
            )
            continue

        # TODO(kornicameister) maybe SubType visitor or chain of visitors is better
        # TODO(kornicameister) do not treat lack of Optional for required.false if there
        # is a default value on handler level

        # validate type
        oas_arg = get_proper_type(
            _make_type_from_oas_param(
                oas_param,
                handler_arg_type,
                handler_arg_default_value,
                cast(TypeChecker, f_ctx.api),
            ),
        )
        if not handler_arg_type.accept(SameTypeVisitor(oas_arg)):
            _oas_handler_msg(
                f_ctx.api.msg.fail,
                f_ctx,
                (
                    ERROR_INVALID_OAS_ARG,
                    f'[{f_name}({f_param} -> {oas_param.name})] '
                    f'expected {format_type(oas_arg)}, '
                    f'but got {format_type(handler_arg_type)}',
                ),
                line_number=handler_arg_type.line,
            )
            continue

        # validate default value
        if handler_arg_default_value is not _ARG_NO_DEFAULT_VALUE_MARKER:
            if oas_default_values:
                default_matches = handler_arg_default_value in oas_default_values
                if not default_matches:
                    _oas_handler_msg(
                        f_ctx.api.msg.fail,
                        f_ctx,
                        (
                            ERROR_INVALID_OAS_VALUE,
                            f'[{f_name}({f_param} -> {oas_param.name})] '
                            f'Incorrect default value. '
                            f'Expected one of {",".join(map(str, oas_default_values))} '
                            f'but got {handler_arg_default_value}',
                        ),
                        line_number=handler_arg_type.line,
                    )
                    continue
            else:
                _oas_handler_msg(
                    f_ctx.api.msg.note,
                    f_ctx,
                    (
                        None,
                        f'[{f_name}({f_param} -> {oas_param.name})] '
                        f'OAS does not define a default value. '
                        f'A default value of "{handler_arg_default_value}" '
                        f'should be placed in OAS '
                        f'{parameter_in(oas_param)} {oas_param.name} parameter '
                        f'under "default" key '
                        f'given there is an attempt of defining it outside of the OAS.',
                    ),
                    line_number=handler_arg_type.line,
                )
        elif oas_default_values:
            _oas_handler_msg(
                f_ctx.api.msg.fail,
                f_ctx,
                (
                    ERROR_INVALID_OAS_VALUE,
                    f'[{f_name}({f_param} -> {oas_param.name})] OAS '
                    f'defines "{oas_default_values[0]}" as a '
                    f'default value. It should be reflected in argument default value.',
                ),
                line_number=handler_arg_type.line,
            )
            continue

    if signature:
        # unconsumed handler arguments
        ...

    return f_ctx.default_return_type


def _get_default_value(
        arg_name: str,
        oas_handler: CallableType,
) -> HandlerArgDefaultValue:
    assert oas_handler.definition
    assert isinstance(oas_handler.definition, FuncDef)

    arg_expr = next(
        map(
            attrgetter('initializer'),
            filter(
                lambda arg: arg.variable.name == arg_name,
                oas_handler.definition.arguments,
            ),
        ),
        None,
    )
    if arg_expr is not None:
        maybe_value = getattr(arg_expr, 'value', _ARG_NO_DEFAULT_VALUE_MARKER)
        if maybe_value is not _ARG_NO_DEFAULT_VALUE_MARKER:
            # covers literal values
            return maybe_value
    return _ARG_NO_DEFAULT_VALUE_MARKER


def _make_type_from_oas_param(
        param: OASParameter,
        handler_arg_type: Type,
        handler_arg_default_value: HandlerArgDefaultValue,
        api: TypeChecker,
) -> Type:
    if isinstance(param.schema, tuple):
        oas_type, _ = param.schema

        oas_is_required = param.required
        oas_is_nullable = oas_type.nullable

        handler_has_default = (
            handler_arg_default_value is not _ARG_NO_DEFAULT_VALUE_MARKER
        )
        needs_optional = (
            oas_is_nullable or (not oas_is_required)
        ) and not handler_has_default

        oas_mtype = _make_type_from_oas_type(oas_type, handler_arg_type, api)
        oas_mtype = UnionType.make_union(
            items=[NoneType(), oas_mtype],
            line=handler_arg_type.line,
            column=handler_arg_type.column,
        ) if needs_optional else oas_mtype

        return oas_mtype
    else:
        union_members = [
            _make_type_from_oas_type(
                oas_type=v.schema,
                orig_arg=handler_arg_type,
                api=api,
            ) for v in param.schema.values()
        ]
        return UnionType.make_union(
            items=union_members,
            line=handler_arg_type.line,
            column=handler_arg_type.column,
        )


@singledispatch
def _make_type_from_oas_type(
        oas_type: None,
        orig_arg: Type,
        api: TypeChecker,
) -> Type:
    raise NotImplementedError(f'{oas_type} not yet implemented')


@_make_type_from_oas_type.register
def _from_oas_string(
        oas_type: OASStringType,
        orig_arg: Type,
        api: TypeChecker,
) -> Type:
    m_type = api.named_type('str')
    return UnionType.make_union(
        [NoneType(), m_type],
        line=orig_arg.line,
        column=orig_arg.column,
    ) if oas_type.nullable else m_type


@_make_type_from_oas_type.register
def _from_oas_bool(
        oas_type: OASBooleanType,
        orig_arg: Type,
        api: TypeChecker,
) -> Type:
    m_type = api.named_type('bool')
    return UnionType.make_union(
        [NoneType(), m_type],
        line=orig_arg.line,
        column=orig_arg.column,
    ) if oas_type.nullable else m_type


@_make_type_from_oas_type.register
def _from_oas_number(
        oas_type: OASNumberType,
        orig_arg: Type,
        api: TypeChecker,
) -> Type:
    m_type = api.named_type('int' if issubclass(int, oas_type.number_cls) else 'float')
    return UnionType.make_union(
        [NoneType(), m_type],
        line=orig_arg.line,
        column=orig_arg.column,
    ) if oas_type.nullable else m_type


@_make_type_from_oas_type.register
def _from_oas_array(
        oas_type: OASArrayType,
        orig_arg: Type,
        api: TypeChecker,
) -> Type:
    m_type = api.named_generic_type(
        name='set' if oas_type.unique_items else 'list',
        args=[_make_type_from_oas_type(oas_type.items_type, orig_arg, api)],
    )
    return UnionType.make_union(
        items=[NoneType(), m_type],
        line=orig_arg.line,
        column=orig_arg.column,
    ) if oas_type.nullable else m_type


@_make_type_from_oas_type.register
def _from_oas_object(
        oas_type: OASObjectType,
        orig_arg: Type,
        api: TypeChecker,
) -> Type:
    # this is so far the most generic thing we can have in here
    # this should, however, match things like:
    # pydantic.BaseModel
    # @dataclass
    # NamedTuple
    # ior even a dict or mapping where there's at most one distinct property type
    mm_type = api.named_generic_type(
        name='mapping',
        args=[api.str_type(), AnyType(TypeOfAny.unannotated)],
    )
    md_type = api.named_generic_type(
        name='dict',
        args=[api.str_type(), AnyType(TypeOfAny.unannotated)],
    )

    members: List[Type] = [mm_type, md_type]
    if oas_type.nullable:
        members.append(NoneType())

    return UnionType.make_union(
        items=members,
        line=orig_arg.line,
        column=orig_arg.column,
    )


def _get_oas_operation(
        f_oas_id: str,
        specifications: Mapping[Path, OASSpecification],
) -> Optional[OASOperation]:
    return next(
        filter(
            lambda op: op and op.id == f_oas_id,
            reduce(
                list.__iadd__,
                map(
                    attrgetter('operations'),
                    specifications.values(),
                ),
            ),
        ),
        None,
    )


def _oas_handler_msg(
        msg_fn: Callable[[
            str,
            Any,
            DefaultNamedArg(Optional[ErrorCode], 'code'),
        ], None],
        f_ctx: FunctionContext,
        msg: Tuple[Optional[ErrorCode], str],
        line_number: Optional[int] = None,
) -> Type:
    ctx = f_ctx.context
    ctx.line = line_number or ctx.line

    msg_fn(msg[1], ctx, msg[0])  # type: ignore

    return f_ctx.default_return_type


def _load_specs(oas_dirs: Iterable[Path]) -> Mapping[Path, OASSpecification]:
    yml_files: List[Path] = reduce(
        list.__iadd__,
        map(lambda oas_dir: list(oas_dir.rglob('**/*.yml')), oas_dirs),
    )

    loaded_spec: Dict[Path, OASSpecification] = {}

    for maybe_spec_file in yml_files:
        oas_spec = load_oas_spec(maybe_spec_file.resolve())
        loaded_spec[maybe_spec_file.resolve()] = oas_spec
        # TODO(kornicameister) add path from which spec was loaded onto spec model

    return loaded_spec


def plugin(version: str) -> 'TypingType[OASPlugin]':
    from loguru import logger
    logger.disable('axion')

    return OASPlugin
