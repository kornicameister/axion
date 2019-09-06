import copy
import functools
import typing as t

from axion.specification import exceptions
from axion.specification import model

M = t.TypeVar('M', bound=model.OASType[t.Any])
V = t.TypeVar('V', bound=object)

__all__ = ('merge', )


def merge(
        oas_type: str,
        a: t.Dict[str, t.Any],
        b: t.Dict[str, t.Any],
) -> t.Dict[str, t.Any]:
    cls_to_fn = {
        'string': _string,
        'number': functools.partial(_number, 'number'),
        'integer': functools.partial(_number, 'integer'),
        'boolean': _boolean,
        'object': _object,
        'array': _array,
    }  # type: t.Dict[str, t.Callable[..., t.Dict[str, t.Any]]]
    try:
        return cls_to_fn[oas_type](a, b)
    except KeyError:
        return _any(a, b)


def _any(
        a: t.Dict[str, t.Any],
        b: t.Dict[str, t.Any],
) -> t.Dict[str, t.Any]:
    return {
        'default': _get_value('default', a.get('default'), b.get('default')),
        'example': _get_value('example', a.get('example'), b.get('example')),
        'nullable': _get_value('nullable', a.get('nullable'), b.get('nullable')),
        'deprecated': _get_value('deprecated', a.get('deprecated'), b.get('deprecated')),
        'readOnly': _get_value('readOnly', a.get('readOnly'), b.get('readOnly')),
        'writeOnly': _get_value('writeOnly', a.get('writeOnly'), b.get('writeOnly')),
    }


def _boolean(
        a: t.Dict[str, t.Any],
        b: t.Dict[str, t.Any],
) -> t.Dict[str, t.Any]:
    return {
        'type': 'boolean',
        'default': _get_value('default', a.get('default'), b.get('default')),
        'example': _get_value('example', a.get('example'), b.get('example')),
        'nullable': _get_value('nullable', a.get('nullable'), b.get('nullable')),
        'deprecated': _get_value('deprecated', a.get('deprecated'), b.get('deprecated')),
        'readOnly': _get_value('readOnly', a.get('readOnly'), b.get('readOnly')),
        'writeOnly': _get_value('writeOnly', a.get('writeOnly'), b.get('writeOnly')),
    }


def _string(
        a: t.Dict[str, t.Any],
        b: t.Dict[str, t.Any],
) -> t.Dict[str, t.Any]:
    return {
        'type': 'string',
        'default': _get_value('default', a.get('default'), b.get('default')),
        'example': _get_value('example', a.get('example'), b.get('example')),
        'nullable': _get_value('nullable', a.get('nullable'), b.get('nullable')),
        'deprecated': _get_value('deprecated', a.get('deprecated'), b.get('deprecated')),
        'readOnly': _get_value('readOnly', a.get('readOnly'), b.get('readOnly')),
        'writeOnly': _get_value('writeOnly', a.get('writeOnly'), b.get('writeOnly')),
        'minLength': _get_value('minLength', a.get('minLength'), b.get('minLength')),
        'maxLength': _get_value('maxLength', a.get('maxLength'), b.get('maxLength')),
        'pattern': _get_value('pattern', a.get('pattern'), b.get('pattern')),
        'format': _get_value('format', a.get('format'), b.get('format')),
    }


def _number(
        oas_type: str,
        a: t.Dict[str, t.Any],
        b: t.Dict[str, t.Any],
) -> t.Dict[str, t.Any]:
    return {
        'type': oas_type,
        'default': _get_value('default', a.get('default'), b.get('default')),
        'example': _get_value('example', a.get('example'), b.get('example')),
        'nullable': _get_value('nullable', a.get('nullable'), b.get('nullable')),
        'deprecated': _get_value('deprecated', a.get('deprecated'), b.get('deprecated')),
        'readOnly': _get_value('readOnly', a.get('readOnly'), b.get('readOnly')),
        'writeOnly': _get_value('writeOnly', a.get('writeOnly'), b.get('writeOnly')),
        'format': _get_value('format', a.get('format'), b.get('format')),
        'minimum': _get_value('minimum', a.get('minimum'), b.get('minimum')),
        'maximum': _get_value('maximum', a.get('maximum'), b.get('maximum')),
        'multipleOf': _get_value('multipleOf', a.get('multipleOf'), b.get('multipleOf')),
        'exclusiveMinimum': _get_value(
            'exclusiveMinimum',
            a.get('exclusiveMinimum'),
            b.get('exclusiveMinimum'),
        ),
        'exclusiveMaximum': _get_value(
            'exclusiveMaximum',
            a.get('exclusiveMaximum'),
            b.get('exclusiveMaximum'),
        ),
    }


def _array(
        a: t.Dict[str, t.Any],
        b: t.Dict[str, t.Any],
) -> t.Dict[str, t.Any]:
    return {
        'type': 'array',
        'default': _get_value('default', a.get('default'), b.get('default')),
        'example': _get_value('example', a.get('example'), b.get('example')),
        'nullable': _get_value('nullable', a.get('nullable'), b.get('nullable')),
        'deprecated': _get_value('deprecated', a.get('deprecated'), b.get('deprecated')),
        'readOnly': _get_value('readOnly', a.get('readOnly'), b.get('readOnly')),
        'writeOnly': _get_value('writeOnly', a.get('writeOnly'), b.get('writeOnly')),
        'minLength': _get_value('minLength', a.get('minLength'), b.get('minLength')),
        'maxLength': _get_value('maxLength', a.get('maxLength'), b.get('maxLength')),
        'uniqueItems': _get_value(
            'uniqueItems',
            a.get('uniqueItems'),
            b.get('uniqueItems'),
        ),
        'items': _get_value('items', a.get('items'), b.get('items')),
    }


def _object(
        a: t.Dict[str, t.Any],
        b: t.Dict[str, t.Any],
) -> t.Dict[str, t.Any]:
    new_properties = _merge_object_properties(
        a=a.get('properties'),
        b=b.get('properties'),
    )
    new_required = a.get('required', set()).union(b.get('required', set()))
    new_additional_properties = _merge_object_additional_properties(
        a.get('additionalProperties'),
        b.get('additionalProperties'),
    )
    new_discriminator = _merge_discriminator(
        a.get('discriminator'),
        b.get('discriminator'),
    )
    return {
        'type': 'object',
        'default': _get_value('default', a.get('default'), b.get('default')),
        'example': _get_value('example', a.get('example'), b.get('example')),
        'nullable': _get_value('nullable', a.get('nullable'), b.get('nullable')),
        'deprecated': _get_value('deprecated', a.get('deprecated'), b.get('deprecated')),
        'readOnly': _get_value('readOnly', a.get('readOnly'), b.get('readOnly')),
        'writeOnly': _get_value('writeOnly', a.get('writeOnly'), b.get('writeOnly')),
        'minProperties': _get_value(
            'minProperties',
            a.get('minProperties'),
            b.get('minProperties'),
        ),
        'maxProperties': _get_value(
            'maxProperties',
            a.get('maxProperties'),
            b.get('maxProperties'),
        ),
        'properties': new_properties,
        'discriminator': new_discriminator,
        'required': new_required,
        'additionalProperties': new_additional_properties,
    }


def _merge_discriminator(
        a: t.Optional[t.Dict[str, t.Any]] = None,
        b: t.Optional[t.Dict[str, t.Any]] = None,
) -> t.Optional[t.Dict[str, t.Any]]:
    if a is not None and b is not None:
        property_name = _get_value(
            'discriminator.propertyName',
            a['propertyName'],
            b['propertyName'],
        )
        new_mapping: t.Dict[str, str] = {}

        a_mapping = a.get('mapping', {}) or {}
        b_mapping = b.get('mapping', {}) or {}

        for prop_name in set(a_mapping.keys()).union(b_mapping.keys()):
            prop_a = a_mapping.get(prop_name)
            prop_b = b_mapping.get(prop_name)
            new_mapping[prop_name] = t.cast(
                str,
                _get_value(
                    f'discriminator.mapping["{prop_name}"]',
                    prop_a,
                    prop_b,
                ),
            )

        return {
            'propertyName': property_name,
            'mapping': new_mapping,
        }
    elif a is None and b is not None:
        return copy.deepcopy(b)
    elif a is not None and b is None:
        return copy.deepcopy(a)
    return None


def _merge_object_additional_properties(
        a: t.Optional[t.Union[bool, t.Dict[str, t.Any]]] = None,
        b: t.Optional[t.Union[bool, t.Dict[str, t.Any]]] = None,
) -> t.Optional[t.Union[bool, t.Dict[str, t.Any]]]:
    if a is None and b is None:
        return None
    elif a is not None and b is None:
        return copy.deepcopy(a)
    elif a is None and b is not None:
        return copy.deepcopy(b)

    if isinstance(a, bool) and isinstance(b, bool):
        return _get_value('additionalProperties', a, b)
    elif isinstance(a, dict) and isinstance(b, dict):
        oas_type_ref = _get_value(
            'additionalProperties.$ref',
            a.get('$ref'),
            b.get('$ref'),
        )  # type: t.Optional[str]
        oas_type = _get_value(
            'additionalProperties.type',
            a.get('type'),
            b.get('type'),
        )  # type: t.Optional[str]
        if oas_type_ref and oas_type:
            raise exceptions.OASConflict(
                f'additionalProperties value differs between mixed schemas. '
                f'One defines inline schema with '
                f'type={oas_type} and the other has $ref={oas_type_ref} '
                f'When using "anyOf,oneOf,allOf" values in '
                f'same location must be equal. '
                f'Either make it so or remove one of the duplicating properties.',
            )
        elif oas_type_ref:
            return {'$ref': oas_type_ref}
        elif oas_type:
            return merge(oas_type, a, b)
        else:
            raise Exception('Should not happen')  # pragma: no cover
    else:
        raise exceptions.OASConflict(
            f'additionalProperties value differs between mixed schemas. '
            f'a={type(a).__qualname__} != b={type(b).__qualname__}. '
            f'When using "anyOf,oneOf,allOf" values in '
            f'same location must be equal. '
            f'Either make it so or remove one of the duplicating properties.',
        )


def _merge_object_properties(
        a: t.Optional[t.Dict[str, t.Dict[str, t.Any]]] = None,
        b: t.Optional[t.Dict[str, t.Dict[str, t.Any]]] = None,
) -> t.Optional[t.Dict[str, t.Dict[str, t.Any]]]:
    if a is not None and b is not None:
        new_properties: t.Dict[str, t.Dict[str, t.Any]] = {}

        for prop_name in set(a.keys()).union(b.keys()):

            prop_a = a.get(prop_name)
            prop_b = b.get(prop_name)

            if prop_a is None and prop_b is not None:
                new_properties[prop_name] = copy.deepcopy(prop_b)
            elif prop_a is not None and prop_b is None:
                new_properties[prop_name] = copy.deepcopy(prop_a)
            elif prop_a is not None and prop_b is not None:
                oas_type_ref = _get_value(
                    f'properties.{prop_name}.$ref',
                    prop_a.get('$ref'),
                    prop_b.get('$ref'),
                )  # type: t.Optional[str]
                oas_type = _get_value(
                    f'properties.{prop_name}.type',
                    prop_a.get('type'),
                    prop_b.get('type'),
                )  # type: t.Optional[str]
                if oas_type_ref is not None:
                    new_properties[prop_name] = {
                        '$ref': oas_type_ref,
                    }
                elif oas_type is not None:
                    new_properties[prop_name] = merge(
                        oas_type,
                        prop_a,
                        prop_b,
                    )

        return new_properties
    elif a is None and b is not None:
        return copy.deepcopy(b)
    elif a is not None and b is None:
        return copy.deepcopy(a)
    return None


def _get_value(
        oas_property: str,
        a: t.Optional[V],
        b: t.Optional[V],
) -> t.Optional[V]:
    if a is None and b is None:
        return None
    elif a is None and b is not None:
        return copy.deepcopy(b)
    elif a is not None and b is None:
        return copy.deepcopy(a)
    elif a != b:
        raise exceptions.OASConflict(
            f'{oas_property} value differs between mixed schemas. '
            f'a={a} != b={b}. When using "anyOf,oneOf,allOf" values in '
            f'same location must be equal. '
            f'Either make it so or remove one of the duplicating properties.',
        )
    else:
        return copy.deepcopy(a)
