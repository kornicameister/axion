import pytest

from axion.oas import model


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


@pytest.mark.parametrize((
    'raw_mime_type',
    'expected_text',
), [
    ('application/json', False),
    ('text/plain', True),
    ('text/css', True),
    ('text/html', True),
])
def test_spec_mime_type_is_text(
        raw_mime_type: str,
        expected_text: bool,
) -> None:
    assert model.MimeType(raw_mime_type).is_text() == expected_text


@pytest.mark.parametrize((
    'mime_type',
    'is_discrete',
), [
    ('application/json', False),
    ('text/plain', False),
    ('multipart/form-data', True),
    ('message/global', True),
])
def test_is_discrete(
        mime_type: str,
        is_discrete: bool,
) -> None:
    assert model.MimeType(mime_type).is_discrete == is_discrete


def test_mime_type_eq() -> None:
    assert model.MimeType('application/json') == model.MimeType('application/json')
    assert model.MimeType('application/json') != 'application/json'
