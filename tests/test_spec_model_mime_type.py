import pytest

from axion.spec import model


@pytest.mark.parametrize((
    'raw_mime_type',
    'expected_json',
), [
    ('application/json', True),
    ('application/json+patch', True),
    ('application/xml', False),
    ('application/ld+json', True),
])
def test_spec_mime_type_is_json(
        raw_mime_type: str,
        expected_json: bool,
) -> None:
    assert model.MimeType(raw_mime_type).is_json() == expected_json
