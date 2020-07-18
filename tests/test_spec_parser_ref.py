import typing as t

import pytest

from axion.oas.parser import ref


@pytest.mark.parametrize(('reference,expected_def'), [
    (
        '#/components/schemas/Category',
        {
            'type': 'object',
            'properties': {
                'id': {
                    'type': 'integer',
                    'format': 'int64',
                },
                'name': {
                    'type': 'string',
                },
            },
        },
    ),
    (
        '#/components/schemas/UltraCategory',
        {
            'type': 'object',
            'properties': {
                'id': {
                    'type': 'integer',
                    'format': 'int64',
                },
                'name': {
                    'type': 'string',
                },
            },
        },
    ),
    (
        '#/components/securitySchemes/apiKey',
        {
            'type': 'apiKey',
            'name': 'api_key',
            'in': 'header',
        },
    ),
    (
        '#/components/responses/NotFound',
        {
            'description': 'Entity not found.',
        },
    ),
    (
        '#/components/parameters/limitParam',
        {
            'name': 'limit',
            'in': 'query',
            'description': 'max records to return',
            'required': True,
            'schema': {
                'type': 'integer',
                'format': 'int32',
            },
        },
    ),
    (
        '#/components/headers/X-Rate-Limit',
        {
            'description': 'Rate limit for this API',
            'required': True,
            'schema': {
                'type': 'integer',
                'format': 'int32',
            },
        },
    ),
    (
        '#/components/requestBodies/Example',
        {
            'description': 'category to add to the system',
            'content': {
                'application/json': {
                    'schema': {
                        '$ref': '#/components/schemas/Category',
                    },
                    'examples': {
                        'user': {
                            'summary': 'Category Example',
                            'externalValue': 'http://category-example.json',
                        },
                    },
                },
            },
        },
    ),
])
def test_spec_load_follow_ref(
    reference: str,
    expected_def: t.Dict[str, t.Any],
) -> None:
    components = {
        'requestBodies': {
            'Example': {
                'description': 'category to add to the system',
                'content': {
                    'application/json': {
                        'schema': {
                            '$ref': '#/components/schemas/Category',
                        },
                        'examples': {
                            'user': {
                                'summary': 'Category Example',
                                'externalValue': 'http://category-example.json',
                            },
                        },
                    },
                },
            },
        },
        'schemas': {
            'Category': {
                'type': 'object',
                'properties': {
                    'id': {
                        'type': 'integer',
                        'format': 'int64',
                    },
                    'name': {
                        'type': 'string',
                    },
                },
            },
            'UltraCategory': {
                '$ref': '#/components/schemas/Category',
            },
        },
        'headers': {
            'X-Rate-Limit': {
                'description': 'Rate limit for this API',
                'required': True,
                'schema': {
                    'type': 'integer',
                    'format': 'int32',
                },
            },
        },
        'parameters': {
            'limitParam': {
                'name': 'limit',
                'in': 'query',
                'description': 'max records to return',
                'required': True,
                'schema': {
                    'type': 'integer',
                    'format': 'int32',
                },
            },
        },
        'responses': {
            'NotFound': {
                'description': 'Entity not found.',
            },
        },
        'securitySchemes': {
            'apiKey': {
                'type': 'apiKey',
                'name': 'api_key',
                'in': 'header',
            },
        },
    }
    assert expected_def == ref.resolve(components, reference)


def test_spec_load_follow_ref_no_such_ref() -> None:
    with pytest.raises(KeyError):
        ref.resolve({}, '#/components/schemas/Dummy')
