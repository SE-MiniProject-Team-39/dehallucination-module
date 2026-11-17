import asyncio
import json

import httpx
import pytest

from backend.dam.extraction import extract


def mock_spans(monkeypatch, spans):
    monkeypatch.setenv('DAM_LLM_URL', 'https://extractor.example.test/chat/completions')

    async def post(self, url, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'choices': [{'message': {'content': json.dumps({'claims': spans})}}]
        })

    monkeypatch.setattr(httpx.AsyncClient, 'post', post)


@pytest.mark.parametrize('prefix', ['   ', '\n\t '])
def test_whitespace_only_llm_span_uses_rule_fallback(monkeypatch, prefix):
    text = prefix + 'Earth orbits the Sun.'
    mock_spans(monkeypatch, [{'start': 0, 'end': len(prefix)}])
    claims, mode = asyncio.run(extract(text))
    assert mode.startswith('rule-based')
    assert [c['text'] for c in claims] == ['Earth orbits the Sun.']
    assert text[claims[0]['start']:claims[0]['end']] == claims[0]['text']


@pytest.mark.parametrize('spans', [
    [{'start': 0, 'end': 9999}],
    [{'start': True, 'end': 5}],
    [{'start': 0, 'end': 12}, {'start': 5, 'end': 20}],
])
def test_invalid_offsets_still_fall_back(monkeypatch, spans):
    mock_spans(monkeypatch, spans)
    claims, mode = asyncio.run(extract('Earth orbits the Sun.'))
    assert mode.startswith('rule-based')
    assert [c['text'] for c in claims] == ['Earth orbits the Sun.']


def test_valid_unicode_llm_span_retains_exact_input(monkeypatch):
    text = '🌍 Earth orbits the Sun.'
    mock_spans(monkeypatch, [{'start': 2, 'end': len(text)}])
    claims, mode = asyncio.run(extract(text))
    assert mode == 'llm'
    assert claims == [{'text': text[2:], 'start': 2, 'end': len(text)}]


def test_empty_llm_result_remains_a_valid_empty_result(monkeypatch):
    mock_spans(monkeypatch, [])
    assert asyncio.run(extract('Hello!')) == ([], 'llm')
