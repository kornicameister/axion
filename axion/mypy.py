# noqa: T001
from configparser import ConfigParser
from functools import (
    partial,
    reduce,
    singledispatch,
)
from operator import attrgetter
from pathlib import Path
from typing import (
    cast,
    Callable,
    Dict,
    Mapping,
    Optional,
    Tuple,
    Type as TypingType,
)

from mypy.checker import TypeChecker
from mypy.errorcodes import ErrorCode
from mypy.messages import format_type
from mypy.nodes import (
    ARG_NAMED,
    ARG_NAMED_OPT,
    ARG_OPT,
    ARG_POS,
    ARG_STAR2,
    MDEF,
    Argument,
    AssignmentStmt,
    Block,
    CallExpr,
    ClassDef,
    Context,
    Decorator,
    EllipsisExpr,
    FuncBase,
    FuncDef,
    JsonDict,
    MemberExpr,
    NameExpr,
    PassStmt,
    PlaceholderNode,
    ListExpr,
    RefExpr,
    StrExpr,
    SymbolNode,
    SymbolTableNode,
    TempNode,
    TypeInfo,
    TypeVarExpr,
    Var,
    MypyFile,
)
from mypy.options import Options
from mypy.plugin import (
    CheckerPluginInterface,
    ClassDefContext,
    MethodContext,
    FunctionContext,
    Plugin,
    SemanticAnalyzerPluginInterface,
    DynamicClassDefContext,
    AttributeContext,
    MethodSigContext,
    AnalyzeTypeContext,
    ReportConfigContext,
)
from mypy.plugins import dataclasses
from mypy.sametypes import SameTypeVisitor
from mypy.server.trigger import make_wildcard_trigger
from mypy.types import (
    AnyType, CallableType, Instance, NoneType, Type, TypeOfAny, TypeType, TypeVarDef,
    TypeVarType, UnionType, get_proper_type, LiteralType, ProperType, TypeList
)
from mypy.typevars import fill_typevars
from mypy.util import get_unique_redefinition_name
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
    parameter_in,
)
from axion.oas.model import (
    OASArrayType,
    OASBooleanType,
    OASNumberType,
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
ERROR_INVALID_OAS_HANDLER: Final[ErrorCode] = ErrorCode(
    'axion-arg-type',
    'Handler does not conform to OAS specification',
    'OAS',
)


class OASPluginConfig:
    __slots__ = ('oas_dir', )

    def __init__(self, options: Options) -> None:
        if options.config_file is None:  # pragma: no cover
            return

        plugin_config = ConfigParser()
        plugin_config.read(options.config_file)

        oas_dir = Path(
            plugin_config.get(
                CONFIGFILE_KEY,
                'oas_dir',
                fallback=str(Path.cwd()),
            ),
        )
        if not oas_dir.is_absolute():
            oas_dir = Path.cwd() / oas_dir

        self.oas_dir = oas_dir


class OASPlugin(Plugin):
    __slots__ = (
        '_cfg',
        '_specifications',
    )

    def __init__(self, options: Options) -> None:
        super().__init__(options)
        self._cfg = OASPluginConfig(options)
        self._specifications = _load_specs(self._cfg.oas_dir)

    def get_function_hook(
            self,
            fullname: str,
    ) -> Optional[Callable[[FunctionContext], Type]]:
        if AXION_CTR == fullname:
            return _axion_ctor_analyzer
        elif AXION_ENDPOINT == fullname:
            sbl = self.lookup_fully_qualified(fullname)
            # TODO(kornicameister) TypeInfo ?
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
        if 'add_api' == fullname:
            print('Here it is')
        return super().get_method_hook(fullname)


def _axion_ctor_analyzer(f_ctx: FunctionContext) -> Type:
    plugin_id_idx = f_ctx.callee_arg_names.index('plugin_id')
    plugin_id_type = f_ctx.arg_types[plugin_id_idx][0]
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

    f_name = oas_handler.name
    oas_operation = _get_oas_operation(
        oas_handler.definition.fullname,
        specifications,
    )

    if oas_operation is None:
        return _oas_handler_error(
            f_ctx,
            (ERROR_NOT_OAS_OP, f'{f_name} is not OAS operation'),
            line_number=getattr(oas_handler.definition, 'line', None),
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
        handler_arg: Optional[Type] = signature.pop(f_param, None)

        if handler_arg is None:
            # log the fact that argument is not there
            _oas_handler_error(
                f_ctx,
                (
                    ERROR_INVALID_OAS_HANDLER,
                    (
                        f'{f_name} does not declare OAS {parameter_in(oas_param)} '
                        f'{oas_param.name}::{f_param} argument'
                    ),
                ),
            )
            continue

        oas_arg = get_proper_type(
            _make_type_from_oas_param(
                oas_param,
                handler_arg,
                cast(TypeChecker, f_ctx.api),
            ),
        )

        # TODO(kornicameister) maybe SubType visitor or chain of visitors is better
        # TODO(kornicameister) check if oas.default matches argument default value
        # TODO(kornicameister) suggest putting default into OAS handler definition if OAS has it
        # TODO(kornicameister) do not treat lack of Optional for required.false if there is a default value
        visitor = SameTypeVisitor(oas_arg)
        if not handler_arg.accept(visitor):
            _oas_handler_error(
                f_ctx,
                (
                    ERROR_INVALID_OAS_HANDLER,
                    f'[{f_param} -> {oas_param.name}] expected {format_type(oas_arg)}, '
                    f'but got {format_type(handler_arg)}',
                ),
                line_number=handler_arg.line,
            )
            continue

    if signature:
        # unconsumed handler arguments
        ...

    return f_ctx.default_return_type


def _make_type_from_oas_param(
        param: OASParameter,
        orig_arg: Type,
        api: TypeChecker,
) -> Type:
    if not isinstance(param.schema, tuple):
        return AnyType()

    oas_type, _ = param.schema
    oas_is_required = param.required

    oas_mtype = _make_type_from_oas_type(oas_type, orig_arg, api)
    oas_mtype = oas_mtype if oas_is_required else UnionType.make_union(
        items=[NoneType(), oas_mtype],
        line=orig_arg.line,
        column=orig_arg.column,
    )

    return oas_mtype


# TODO(kornicameister) this should be thrown out of here
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
        [NoneType(), m_type],
        line=orig_arg.line,
        column=orig_arg.column,
    ) if oas_type.nullable else m_type


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


def _oas_handler_error(
        f_ctx: FunctionContext,
        msg: Tuple[ErrorCode, str],
        line_number: Optional[int] = None,
) -> Type:
    ctx = f_ctx.context
    ctx.line = line_number or ctx.line

    f_ctx.api.msg.fail(
        msg=msg[1],
        context=ctx,
        code=msg[0],
    )

    return f_ctx.default_return_type


def _load_specs(oas_dir: Path) -> Mapping[Path, OASSpecification]:
    oas_dir = oas_dir.resolve()
    yml_files = oas_dir.rglob('**/*.yml')

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
