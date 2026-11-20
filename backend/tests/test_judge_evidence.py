"""LLM evidence judge: Wikipedia passage judging, uncited model knowledge, and scoring."""
import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from backend.dam import judge
from backend.dam.extraction import fallback_extract
from backend.dam.main import create_app
from backend.dam.pipeline import score
from backend.dam.sources import ModelKnowledgeSource, WikipediaSource, evidence

PASSAGE = "The capital of Australia is Canberra. Sydney is its largest city."


def _transport(passage_answer, knowledge_answer):
    def handler(request):
        url = str(request.url)
        if "list=search" in url:
            return httpx.Response(200, json={"query": {"search": [{"title": "Canberra"}]}})
        if "prop=extracts" in url:
            return httpx.Response(200, json={"query": {"pages": {"1": {"pageid": 1, "title": "Canberra", "extract": PASSAGE}}}})
        if url.endswith("/api/chat"):
            system = json.loads(request.content)["messages"][0]["content"]
            answer = passage_answer if "PASSAGES" in system else knowledge_answer
            return httpx.Response(200, json={"message": {"content": json.dumps(answer)}})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def _judge_env(monkeypatch):
    monkeypatch.setenv("DAM_JUDGE_URL", "http://127.0.0.1:11434/api/chat")
    monkeypatch.setenv("DAM_JUDGE_MODEL", "qwen2.5:7b")


def test_judge_is_off_without_a_model(monkeypatch):
    monkeypatch.delenv("DAM_JUDGE_MODEL", raising=False)
    assert judge.config() is None


def test_wikipedia_passage_judging_cites_the_passage(monkeypatch):
    _judge_env(monkeypatch)
    transport = _transport({"label": "CONTRADICTED", "quote": "The capital of Australia is Canberra."}, {})

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await WikipediaSource().query("The capital of Australia is Sydney.", client)
    [item] = asyncio.run(run())
    assert item["verdict"] == "Contradicted"
    assert item["snippet"] == "The capital of Australia is Canberra."
    assert item["correction"] == "The capital of Australia is Canberra."
    assert item["url"] == "https://en.wikipedia.org/?curid=1"
    assert item["quality"] == 0.85 and item["judged_by"] == "qwen2.5:7b"


def test_invented_quote_is_discarded(monkeypatch):
    _judge_env(monkeypatch)
    transport = _transport({"label": "SUPPORTED", "quote": "A sentence the passage never contained."}, {})

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await WikipediaSource().query("Canberra is the capital of Australia.", client)
    [item] = asyncio.run(run())
    assert item["verdict"] == "Supported"
    assert "never contained" not in item["snippet"]


def test_unparseable_judge_label_gives_no_evidence(monkeypatch):
    _judge_env(monkeypatch)
    transport = _transport({"label": "PROBABLY"}, {})

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await WikipediaSource().query("The capital of Australia is Sydney.", client)
    assert asyncio.run(run()) == []


def test_model_knowledge_is_uncited_and_low_weight(monkeypatch):
    _judge_env(monkeypatch)
    transport = _transport({}, {"label": "FALSE", "reason": "Humans cannot breathe in a vacuum."})

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await ModelKnowledgeSource().query("Humans can breathe in space.", client)
    [item] = asyncio.run(run())
    assert item["verdict"] == "Contradicted" and item["uncited"] and item["quality"] == 0.45
    assert item["url"] == "llm:qwen2.5:7b"


def test_cited_evidence_outranks_uncited_model_knowledge():
    wiki = {**evidence("wikipedia", "Supported text.", "https://en.wikipedia.org/?curid=1", "Supported"),
            "quality": 0.85, "trust_weight": 1}
    model = {**evidence("model", "Disagrees.", "llm:x", "Contradicted"), "quality": 0.45, "uncited": True, "trust_weight": 1}
    result = score([{"source": "wikipedia", "status": "ok", "evidence": [wiki]},
                    {"source": "model", "status": "ok", "evidence": [model]}], 0.5)
    assert result["verdict"] == "Supported" and result["evidence"] == [wiki]


def test_model_knowledge_alone_stays_flagged():
    model = {**evidence("model", "Agrees.", "llm:x", "Supported"), "quality": 0.45, "uncited": True, "trust_weight": 1}
    result = score([{"source": "model", "status": "ok", "evidence": [model]}], 0.5)
    assert result["verdict"] == "Supported" and result["flagged"]


def test_any_declarative_statement_is_a_claim():
    text = "The architecture relies on attention mechanisms. I think pizza is great. Why is the sky blue?"
    assert [c["text"] for c in fallback_extract(text)] == ["The architecture relies on attention mechanisms."]


def test_settings_include_model_source_and_accept_old_payloads(tmp_path, monkeypatch):
    monkeypatch.setenv("DAM_ADMIN_PASSWORD", "admin-pass")
    app = create_app("sqlite:///" + (tmp_path / "judge.db").as_posix(), testing=True)
    with TestClient(app) as client:
        login = client.post("/api/login", json={"username": "admin", "password": "admin-pass"}).json()
        headers = {"X-CSRF-Token": login["csrf"]}
        current = client.get("/api/settings").json()
        assert "model" in current["sources"]
        old = {**current, "sources": {k: v for k, v in current["sources"].items() if k != "model"}}
        saved = client.put("/api/settings", json=old, headers=headers)
        assert saved.status_code == 200 and "model" in saved.json()["sources"]
