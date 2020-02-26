from collections import OrderedDict
from functools import (partial, reduce)
from operator import attrgetter
from pathlib import Path
from typing import (
    Any,
    Callable,
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
from mypy.sametypes import is_same_type, simplify_union
from mypy.subtypes import is_equivalent as is_equivalent_type
from mypy.typeops import try_getting_instance_fallback
from mypy.types import (
    AnyType,
    CallableType,
    get_proper_type,
    NoneType,
    ProperType,
    Type,
    TypedDictType,
    TypeOfAny,
    UnionType,
)
from mypy_extensions import DefaultNamedArg
from typing_extensions import Final

from axion import oas
from axion.handler import model as handler_model
from axion.oas import model as oas_model
from axion.oas_mypy import app_ctor_analyzer
from axion.oas_mypy import conf
from axion.oas_mypy import errors

AXION_CTR: Final[str] = 'axion.Axion'
AXION_ENDPOINT: Final[str] = 'axion.oas.endpoint.oas_endpoint'

CONFIGFILE_KEY: Final[str] = 'axion-mypy'

_ARG_NO_DEFAULT_VALUE_MARKER = object()
HandlerArgDefaultValue = Any


class OASPlugin(Plugin):
    __slots__ = (
        '_cfg',
        '_specifications',
    )

    def __init__(self, options: Options) -> None:
        super().__init__(options)
        self._cfg = conf.OASPluginConfig(options)
        self._specifications = _load_specs(list(self._cfg.oas_dirs))

    def get_function_hook(
            self,
            fullname: str,
    ) -> Optional[Callable[[FunctionContext], Type]]:
        if AXION_CTR == fullname:
            return app_ctor_analyzer.hook
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


def _oas_handler_analyzer(
        specifications: Mapping[Path, oas_model.OASSpecification],
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
        return errors.not_oas_handler(
            msg=f'{f_name} is not OAS operation',
            ctx=f_ctx,
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
            lambda ofp: (ofp, handler_model.get_f_param(ofp.name)),
            oas.operation_filter_parameters(
                oas_operation,
                'path',
                'query',
            ),
    ):
        handler_arg_type: Optional[Type] = signature.pop(f_param, None)
        handler_arg_default_value = _get_default_value(f_param, oas_handler)
        oas_default_values = oas.parameter_default_values(oas_param)

        if handler_arg_type is None:
            # log the fact that argument is not there
            _oas_handler_msg(
                f_ctx.api.msg.fail,
                f_ctx,
                (
                    errors.ERROR_INVALID_OAS_ARG,
                    (
                        f'{f_name} does not declare OAS {oas.parameter_in(oas_param)} '
                        f'{oas_param.name}::{f_param} argument'
                    ),
                ),
            )
            continue

        oas_param_type = transform_parameter_to_type(
            oas_param,
            get_proper_type(handler_arg_type),
            handler_arg_default_value,
            f_ctx,
        )
        if not any((
                is_same_type(handler_arg_type, oas_param_type),
                is_equivalent_type(handler_arg_type, oas_param_type),
        )):
            errors.invalid_argument(
                msg=(
                    f'[{f_name}({f_param} -> {oas_param.name})] '
                    f'expected {format_type(oas_param_type)}, '
                    f'but got {format_type(handler_arg_type)}'
                ),
                ctx=f_ctx,
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
                            errors.ERROR_INVALID_OAS_VALUE,
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
                        f'{oas.parameter_in(oas_param)} {oas_param.name} parameter '
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
                    errors.ERROR_INVALID_OAS_VALUE,
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


def transform_parameter_to_type(
        param: oas.OASParameter,
        handler_arg_type: ProperType,
        handler_arg_default_value: HandlerArgDefaultValue,
        ctx: FunctionContext,
) -> Type:
    oas_is_required = param.required
    handler_has_default = (handler_arg_default_value is not _ARG_NO_DEFAULT_VALUE_MARKER)
    needs_optional = not oas_is_required and not handler_has_default

    if isinstance(param.schema, tuple):
        oas_type, _ = param.schema
        items = [transform_oas_type(
            oas_type,
            handler_arg_type,
            ctx,
        )]
    else:
        items = [
            transform_oas_type(
                v.schema,
                handler_arg_type,
                ctx,
            ) for v in param.schema.values()
        ]

    if needs_optional:
        items.append(NoneType())

    return simplify_union(
        UnionType.make_union(
            items=items,
            line=(handler_arg_type.line or handler_arg_type.end_line) or -1,
            column=handler_arg_type.column,
        ),
    )


def transform_oas_type(
        oas_type: oas_model.OASType[Any],
        handler_type: ProperType,
        ctx: FunctionContext,
) -> Type:
    m_type: Optional[Type] = None
    union_members: List[Type] = []

    assert isinstance(ctx.api, TypeChecker)

    if isinstance(oas_type, oas_model.OASStringType):
        m_type = ctx.api.str_type()
    elif isinstance(oas_type, oas_model.OASBooleanType):
        m_type = ctx.api.named_type('bool')
    elif isinstance(oas_type, oas_model.OASNumberType):
        m_type = ctx.api.named_type(
            'int' if issubclass(int, oas_type.number_cls) else 'float',
        )
    elif isinstance(oas_type, oas_model.OASOneOfType):
        union_members = [
            transform_oas_type(
                nested_type,
                handler_type,
                ctx,
            ) for include_type, nested_type in oas_type.schemas if include_type
        ]
    elif isinstance(oas_type, oas_model.OASArrayType):
        m_type = ctx.api.named_generic_type(
            name='set' if oas_type.unique_items else 'list',
            args=[transform_oas_type(
                oas_type.items_type,
                handler_type,
                ctx,
            )],
        )
    elif isinstance(oas_type, oas_model.OASObjectType):
        m_type = transform_oas_object_type(oas_type, handler_type, ctx)
    else:
        raise NotImplementedError(f'{oas_type} not yet implemented')

    if m_type is not None:
        m_type.set_line(handler_type)
        union_members.append(m_type)

    if oas_type.nullable:
        union_members.append(NoneType())

    ut = simplify_union(UnionType.make_union(items=union_members))
    ut.set_line(handler_type)
    return ut


def transform_oas_object_type(
        oas_type: oas_model.OASObjectType,
        handler_arg_type: ProperType,
        ctx: FunctionContext,
) -> Type:
    # NOTE(kornicameister) -> should land in documentation
    #
    # This test combines very interesting use case from POV of typing
    # imagine a query param that is optional (i.e.) may not be present in request
    # so that means that we have a None there
    # moving on. Each property in it...is not not requires so eech field
    # of either NamedTuple, TypedDict or @dataclass needs to be Optional
    # Image full declaration:
    #
    # class A(TypedDict):
    #   a: Optional[str]
    #   b: Optional[str]
    # def handler(query_a: Optional[A]):
    #   ...
    #
    # it does not exactly sounds user friendly :D
    #
    # typing using content must also include cases with
    # additionalProperties. For instance:
    # - additionalProperties: true means that any fixed key set structure
    #   (NamedTuple, TypedDict) cannot be used.
    #   because additionalProperties allows
    #   all dynamic properties to enter
    # even with types of the additionalProperties properties usage of fixed keys
    # structure is not possible

    # this should, match things like:
    # fixed keys:
    # - pydantic.BaseModel
    # - @dataclass
    # - NamedTuple
    # - TypedDict
    # generics:
    # - Mapping
    # - Dict

    assert isinstance(ctx.api, TypeChecker)

    vt = get_generic_type_vt(ctx, handler_arg_type, oas_type)
    td_type = get_typed_dict_type(ctx, handler_arg_type, oas_type)

    members: List[Type] = [
        ctx.api.named_generic_type(
            name='collections.abc.Mapping',
            args=[ctx.api.str_type(), vt],
        ),
        ctx.api.named_generic_type(
            name='dict',
            args=[ctx.api.str_type(), vt],
        ),
        td_type,
    ]
    if oas_type.nullable:
        members.append(NoneType())

    return simplify_union(UnionType.make_union(items=members))


def get_typed_dict_type(
        ctx: FunctionContext,
        handler_arg_type: ProperType,
        oas_type: oas_model.OASObjectType,
) -> TypedDictType:

    if isinstance(handler_arg_type, UnionType):
        td_type_fallback = next(
            try_getting_instance_fallback(get_proper_type(x))
            for x in handler_arg_type.relevant_items()
        )
    else:
        td_type_fallback = try_getting_instance_fallback(handler_arg_type)

    assert td_type_fallback is not None

    return TypedDictType(
        items=OrderedDict({
            oas_prop_name: transform_oas_type(oas_prop_type, handler_arg_type, ctx)
            for oas_prop_name, oas_prop_type in oas_type.properties.items()
        }),
        required_keys=oas_type.required,
        fallback=td_type_fallback,
        line=td_type_fallback.line,
        column=td_type_fallback.column,
    )


def get_generic_type_vt(
        ctx: FunctionContext,
        handler_arg_type: ProperType,
        oas_type: oas_model.OASObjectType,
) -> Type:
    property_types = {
        transform_oas_type(
            ov,
            handler_arg_type,
            ctx,
        )
        for ov in oas_type.properties.values()
    }
    if len(property_types) == 1:
        vt = next(iter(property_types))
    else:
        vt = AnyType(TypeOfAny.explicit)
    return vt


def _get_oas_operation(
    f_oas_id: str,
    specifications: Mapping[Path, oas_model.OASSpecification],
) -> Optional[oas_model.OASOperation]:
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


def _load_specs(oas_dirs: Iterable[Path]) -> Mapping[Path, oas_model.OASSpecification]:
    yml_files: List[Path] = reduce(
        list.__iadd__,
        map(lambda oas_dir: list(oas_dir.rglob('**/*.yml')), oas_dirs),
    )

    loaded_spec: Dict[Path, oas_model.OASSpecification] = {}

    for maybe_spec_file in yml_files:
        oas_spec = oas.load(maybe_spec_file.resolve())
        loaded_spec[maybe_spec_file.resolve()] = oas_spec
        # TODO(kornicameister) add path from which spec was loaded onto spec model

    return loaded_spec


def plugin(version: str) -> 'TypingType[OASPlugin]':
    from loguru import logger
    logger.disable('axion')

    return OASPlugin
