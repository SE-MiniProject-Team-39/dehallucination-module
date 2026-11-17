import pytest

from backend.dam.extraction import fallback_extract


@pytest.mark.parametrize('opening,closing', [('"', '"'), ("'", "'"), ('“', '”'), ('‘', '’')])
def test_quoted_question_is_not_a_factual_claim(opening, closing):
    assert fallback_extract(f'{opening}What is the capital of France?{closing}') == []


@pytest.mark.parametrize('opening,closing', [('"', '"'), ('“', '”')])
def test_fact_before_quoted_question_is_preserved(opening, closing):
    text = f'{opening}Earth orbits the Sun.{closing} {opening}What is the capital of France?{closing}'
    claims = fallback_extract(text)
    assert [claim['text'] for claim in claims] == ['Earth orbits the Sun.']
    assert all(text[c['start']:c['end']] == c['text'] for c in claims)


def test_unicode_quoted_facts_have_exact_offsets(core_client):
    text = '🌍\n“Earth orbits the Sun.” "The capital of France is Paris."'
    response = core_client.post('/verify', json={'text': text, 'source_app_id': 'demo-app'})
    assert response.status_code == 200
    report = response.json()
    assert report['original_text'] == text
    assert [c['text'] for c in report['claims']] == ['Earth orbits the Sun.', 'The capital of France is Paris.']
    assert all(text[c['start']:c['end']] == c['text'] for c in report['claims'])
    assert all(c['verdict'] == 'Supported' for c in report['claims'])


def test_internal_apostrophes_and_existing_boundaries_are_preserved():
    text = "Dr. Ada was born in London. Earth's diameter is 12742.5 km.\nEarth orbits the Sun."
    claims = fallback_extract(text)
    assert [c['text'] for c in claims] == [
        'Dr. Ada was born in London.', "Earth's diameter is 12742.5 km.", 'Earth orbits the Sun.'
    ]
    assert all(text[c['start']:c['end']] == c['text'] for c in claims)
