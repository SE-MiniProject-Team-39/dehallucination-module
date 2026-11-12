import asyncio
from datetime import datetime, timezone
import httpx
import pytest

from backend.dam.sources import (
    CuratedSource,
    WikidataSource,
    WikipediaSource,
    evidence,
    lookup,
    matching_fact,
    normalize,
    proposition,
)


class TestSourcesPropositionAndNormalize:
    def test_normalize_punctuation_and_case(self):
        assert normalize("  The Capital of FRANCE!  ") == "the capital of france"
        assert normalize("Hamlet, Prince of Denmark.") == "hamlet prince of denmark"

    def test_proposition_capital_patterns(self):
        # Pattern 1: (the )?capital of X is Y
        p1 = proposition("The capital of France is Paris.")
        assert p1 == ("france", "capital", "paris")

        p1_no_the = proposition("capital of Germany is Berlin.")
        assert p1_no_the == ("germany", "capital", "berlin")

        # Pattern 2: X is (the )?capital of Y (reverse)
        p2 = proposition("Paris is the capital of France.")
        assert p2 == ("france", "capital", "paris")

        p2_no_the = proposition("Tokyo is capital of Japan.")
        assert p2_no_the == ("japan", "capital", "tokyo")

    def test_proposition_author_pattern(self):
        p = proposition("Hamlet was written by William Shakespeare.")
        assert p == ("hamlet", "author", "william shakespeare")

    def test_proposition_orbits_pattern(self):
        p = proposition("Earth orbits the Sun.")
        assert p == ("earth", "orbits", "sun")

    @pytest.mark.parametrize("word", [
        "not", "never", "no", "and", "or", "but", "may", "might", "could", "would",
        "which", "where", "because", "since", "formerly", "previously", "today",
        "currently", "once", "also"
    ])
    def test_proposition_rejects_qualifiers_and_conjunctions(self, word):
        assert proposition(f"The capital of France is {word} Paris.") is None

    @pytest.mark.parametrize("punct", [",", ";", ":"])
    def test_proposition_rejects_subordinate_punctuation(self, punct):
        assert proposition(f"The capital of France{punct} is Paris.") is None

    def test_proposition_rejects_digits(self):
        assert proposition("The capital of France was Paris in 1999.") is None


class TestCuratedSource:
    def test_curated_supported(self):
        src = CuratedSource()
        items = asyncio.run(src.query("The capital of France is Paris.", client=None))
        assert len(items) == 1
        assert items[0]["verdict"] == "Supported"
        assert items[0]["correction"] is None

    def test_curated_contradicted(self):
        src = CuratedSource()
        items = asyncio.run(src.query("The capital of France is Lyon.", client=None))
        assert len(items) == 1
        assert items[0]["verdict"] == "Contradicted"
        assert items[0]["correction"] == "The capital of France is Paris."

    def test_curated_unknown_fact(self):
        src = CuratedSource()
        items = asyncio.run(src.query("The capital of Atlantis is Poseidon.", client=None))
        assert items == []


class TestWikidataLiveSourceGaps:
    def test_wikidata_live_non_proposition_entity_search(self):
        # When text is not a recognized proposition, WikidataSource(True) performs wbsearchentities
        called = False

        def handler(request):
            nonlocal called
            assert "wbsearchentities" in str(request.url)
            called = True
            return httpx.Response(200, json={"search": [{"id": "Q1", "label": "Universe"}]})

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                src = WikidataSource(live=True)
                return await src.query("The universe contains galaxies and stars.", client)

        res = asyncio.run(run())
        assert called is True
        assert res == []

    def test_wikidata_live_sparql_no_bindings(self):
        # When SPARQL query returns empty results
        def handler(request):
            return httpx.Response(200, json={"results": {"bindings": []}})

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                src = WikidataSource(live=True)
                return await src.query("The capital of France is Paris.", client)

        res = asyncio.run(run())
        assert res == []

    def test_wikidata_live_sparql_multiple_contradictory_values(self):
        # Multiple values historically qualified without matching claimed -> returns []
        def handler(request):
            return httpx.Response(200, json={
                "results": {"bindings": [
                    {"valueLabel": {"value": "Historical Capital 1"}},
                    {"valueLabel": {"value": "Historical Capital 2"}},
                ]}
            })

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                src = WikidataSource(live=True)
                return await src.query("The capital of France is London.", client)

        res = asyncio.run(run())
        assert res == []


class TestWikipediaSource:
    def test_wikipedia_query_match(self):
        def handler(request):
            return httpx.Response(200, json={
                "query": {
                    "pages": {
                        "123": {
                            "pageid": 123,
                            "extract": "The capital of France is Paris. It is a major European city."
                        }
                    }
                }
            })

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                src = WikipediaSource()
                return await src.query("The capital of France is Paris.", client)

        items = asyncio.run(run())
        assert len(items) == 1
        assert items[0]["source"] == "wikipedia"
        assert items[0]["verdict"] == "Supported"
        assert items[0]["url"] == "https://en.wikipedia.org/?curid=123"

    def test_wikipedia_query_no_match(self):
        def handler(request):
            return httpx.Response(200, json={"query": {"pages": {}}})

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                src = WikipediaSource()
                return await src.query("Unmatched claim.", client)

        items = asyncio.run(run())
        assert items == []


class TestLookupWrapper:
    def test_lookup_success(self):
        class MockAdapter:
            name = "mock"
            async def query(self, text, client):
                return [{"source": "mock", "snippet": text, "verdict": "Supported"}]

        res = asyncio.run(lookup(MockAdapter(), "Test", None, timeout=5, weight=0.8))
        assert res["status"] == "ok"
        assert res["source"] == "mock"
        assert res["evidence"][0]["trust_weight"] == 0.8

    def test_lookup_timeout(self):
        class TimeoutAdapter:
            name = "slow"
            async def query(self, text, client):
                await asyncio.sleep(0.5)

        res = asyncio.run(lookup(TimeoutAdapter(), "Test", None, timeout=0.01, weight=1.0))
        assert res["status"] == "timeout"
        assert res["evidence"] == []

    def test_lookup_error_isolation(self):
        class FailingAdapter:
            name = "failing"
            async def query(self, text, client):
                raise ValueError("Unexpected adapter parsing error")

        res = asyncio.run(lookup(FailingAdapter(), "Test", None, timeout=1, weight=1.0))
        assert res["status"] == "unavailable"
        assert res["evidence"] == []
