from pathlib import Path

import yarl

from axion.oas import loader
from axion.oas import model


def test_spec_render_complex_schema() -> None:
    spec_location = Path('tests/specifications/complex.yml')
    loaded_spec = loader.load_spec(spec_location)

    # asserting
    assert loaded_spec.version

    # assert servers
    assert len(loaded_spec.servers) == 1
    assert loaded_spec.servers[0].url == 'http://lotr-service'
    assert not loaded_spec.servers[0].variables

    # assert that 4 operations were loaded
    assert len(loaded_spec.operations) == 4

    rings_get_all_op = next(
        filter(
            lambda op: op.id == 'frodo.lotr.rings.get_all',
            loaded_spec.operations,
        ),
        None,
    )
    rings_make_one_op = next(
        filter(
            lambda op: op.id == 'frodo.lotr.rings.make_one',
            loaded_spec.operations,
        ),
        None,
    )
    rings_put_one_op = next(
        filter(
            lambda op: op.id == 'frodo.lotr.rings.put_one',
            loaded_spec.operations,
        ),
        None,
    )
    rings_get_one_op = next(
        filter(
            lambda op: op.id == 'frodo.lotr.rings.get_one',
            loaded_spec.operations,
        ),
        None,
    )

    assert rings_get_all_op
    assert rings_get_all_op.path == yarl.URL('/rings')
    assert rings_get_all_op.http_method == model.HTTPMethod.GET
    assert not rings_get_all_op.deprecated
    assert not rings_get_all_op.request_body
    assert len(rings_get_all_op.responses) == 3
    assert 200 in rings_get_all_op.responses
    assert 400 in rings_get_all_op.responses
    assert 'default' in rings_get_all_op.responses
    assert len(rings_get_all_op.parameters) == 3

    assert rings_make_one_op
    assert rings_make_one_op.path == yarl.URL('/rings')
    assert rings_make_one_op.http_method == model.HTTPMethod.POST
    assert not rings_make_one_op.deprecated
    assert rings_make_one_op.request_body
    assert rings_make_one_op.request_body.required
    assert 'application/json' in rings_make_one_op.request_body
    assert model.MimeType('application/json') in rings_make_one_op.request_body
    assert len(rings_make_one_op.responses) == 4
    assert 201 in rings_make_one_op.responses
    assert 404 in rings_make_one_op.responses
    assert 409 in rings_make_one_op.responses
    assert 'default' in rings_make_one_op.responses
    assert len(rings_make_one_op.parameters) == 2

    assert rings_put_one_op
    assert rings_put_one_op.path == yarl.URL('/rings/{ring_id}')
    assert rings_put_one_op.http_method == model.HTTPMethod.PUT
    assert rings_put_one_op.deprecated
    assert rings_put_one_op.request_body
    assert rings_put_one_op.request_body.required
    assert 'application/json' in rings_put_one_op.request_body
    assert model.MimeType('application/json') in rings_put_one_op.request_body
    assert len(rings_put_one_op.responses) == 3
    assert 201 in rings_put_one_op.responses
    assert 204 in rings_put_one_op.responses
    assert 400 in rings_put_one_op.responses
    assert len(rings_put_one_op.parameters) == 2

    assert rings_get_one_op
    assert rings_get_one_op.path == yarl.URL('/rings/{ring_id}')
    assert rings_get_one_op.http_method == model.HTTPMethod.GET
    assert not rings_get_one_op.deprecated
    assert not rings_get_one_op.request_body
    assert len(rings_get_one_op.responses) == 7
    assert 200 in rings_get_one_op.responses
    assert 400 in rings_get_one_op.responses
    assert 404 in rings_get_one_op.responses
    assert 408 in rings_get_one_op.responses
    assert 422 in rings_get_one_op.responses
    assert 503 in rings_get_one_op.responses
    assert 'default' in rings_get_one_op.responses
    assert len(rings_get_one_op.parameters) == 4
