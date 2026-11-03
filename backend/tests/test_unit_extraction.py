import asyncio
import httpx
import pytest

from backend.dam.extraction import extract, fallback_extract, segment


class TestSegment:
    def test_segment_standard_sentences(self):
        text = "First sentence. Second sentence! Third sentence?"
        segments = list(segment(text))
        assert len(segments) == 3
        assert segments[0][2] == "First sentence."
        assert segments[1][2] == "Second sentence!"
        assert segments[2][2] == "Third sentence?"
        for left, right, piece in segments:
            assert text[left:right] == piece

    def test_segment_abbreviations_not_split(self):
        text = "Mr. Smith and Mrs. Jones met with Dr. Ada and Prof. Higgins e.g. yesterday."
        segments = list(segment(text))
        assert len(segments) == 1
        assert "Dr. Ada" in segments[0][2]
        assert "Prof. Higgins" in segments[0][2]
        assert "e.g." in segments[0][2]

    def test_segment_multiple_consecutive_abbreviations(self):
        text = "Prof. Dr. Smith was born in London. He is well known."
        segments = list(segment(text))
        assert len(segments) == 2
        assert segments[0][2] == "Prof. Dr. Smith was born in London."
        assert segments[1][2] == "He is well known."

    def test_segment_decimal_numbers(self):
        text = "Pi is approximately 3.14159. Water freezes at 0.0 degrees."
        segments = list(segment(text))
        assert len(segments) == 2
        assert segments[0][2] == "Pi is approximately 3.14159."
        assert segments[1][2] == "Water freezes at 0.0 degrees."

    def test_segment_newlines_and_whitespace(self):
        text = "   Leading spaces.\n\nMultiple newlines.\nThird line without period"
        segments = list(segment(text))
        assert len(segments) == 3
        assert segments[0][2] == "Leading spaces."
        assert segments[1][2] == "Multiple newlines."
        assert segments[2][2] == "Third line without period"
        for left, right, piece in segments:
            assert text[left:right] == piece

    def test_segment_unicode_and_emojis(self):
        text = "🌍 Earth orbits the Sun.\n✨ Stars are distant suns."
        segments = list(segment(text))
        assert len(segments) == 2
        assert segments[0][2] == "🌍 Earth orbits the Sun."
        assert segments[1][2] == "✨ Stars are distant suns."
        for left, right, piece in segments:
            assert text[left:right] == piece

    def test_segment_empty_and_whitespace_only(self):
        assert list(segment("")) == []
        assert list(segment("   \t  \n  ")) == []


class TestFallbackExtract:
    def test_excludes_questions(self):
        claims = fallback_extract("Is the Moon made of rock? France is in Europe.")
        assert len(claims) == 1
        assert claims[0]["text"] == "France is in Europe."

    def test_excludes_conversational_openers(self):
        text = (
            "Hello! Hey there. Thanks for your help. Please take note. "
            "I think Python is awesome. I believe the earth is round. "
            "In my opinion, coffee is essential. Perhaps it is cold outside. "
            "Maybe it will rain. France is in Europe."
        )
        claims = fallback_extract(text)
        assert len(claims) == 1
        assert claims[0]["text"] == "France is in Europe."

    @pytest.mark.parametrize("opinion_word", [
        "best", "beautiful", "wonderful", "favorite", "favourite", "amazing", "should", "ought"
    ])
    def test_excludes_opinion_adjectives(self, opinion_word):
        text = f"Paris is a {opinion_word} city. France is located in Europe."
        claims = fallback_extract(text)
        assert len(claims) == 1
        assert claims[0]["text"] == "France is located in Europe."

    @pytest.mark.parametrize("verb", [
        "is", "are", "was", "were", "has", "have", "had", "contains",
        "orbits", "boils", "freezes", "equals", "founded", "born",
        "discovered", "invented", "wrote", "created", "located",
        "capital", "released", "became", "died"
    ])
    def test_includes_recognized_factual_verbs(self, verb):
        text = f"The subject {verb} the object."
        claims = fallback_extract(text)
        assert len(claims) == 1
        assert claims[0]["text"] == text

    def test_offsets_accuracy_across_multiline_text(self):
        text = "  First line.\nDr. Ada was born in 1815.\n  Alexander Fleming discovered penicillin.  "
        claims = fallback_extract(text)
        assert len(claims) >= 2
        for claim in claims:
            assert text[claim["start"]:claim["end"]] == claim["text"]


class TestExtractLLM:
    def test_extract_without_llm_url(self, monkeypatch):
        monkeypatch.delenv("DAM_LLM_URL", raising=False)
        claims, mode = asyncio.run(extract("The capital of France is Paris."))
        assert mode == "rule-based"
        assert len(claims) == 1
        assert claims[0]["text"] == "The capital of France is Paris."

    def test_extract_with_successful_llm_response(self, monkeypatch):
        monkeypatch.setenv("DAM_LLM_URL", "https://llm.example.test/v1/chat/completions")
        monkeypatch.setenv("DAM_LLM_KEY", "test-key")
        monkeypatch.setenv("DAM_LLM_MODEL", "test-model")

        text = "Paris is the capital of France. Water boils at 100C."
        # Valid non-overlapping spans
        span1 = {"start": 0, "end": 31}
        span2 = {"start": 33, "end": 51}

        async def mock_post(self, *args, **kwargs):
            return httpx.Response(
                200,
                request=httpx.Request("POST", args[0]),
                json={
                    "choices": [{
                        "message": {
                            "content": f'{{"claims": [{{"start": {span1["start"]}, "end": {span1["end"]}}}, {{"start": {span2["start"]}, "end": {span2["end"]}}}]}}'
                        }
                    }]
                }
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        claims, mode = asyncio.run(extract(text))
        assert mode == "llm"
        assert len(claims) == 2
        assert claims[0]["text"] == text[span1["start"]:span1["end"]]
        assert claims[1]["text"] == text[span2["start"]:span2["end"]]

    def test_extract_llm_http_error_fallback(self, monkeypatch):
        monkeypatch.setenv("DAM_LLM_URL", "https://llm.example.test/v1/chat/completions")

        async def mock_post_error(self, *args, **kwargs):
            return httpx.Response(500, request=httpx.Request("POST", args[0]))

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_error)
        claims, mode = asyncio.run(extract("The capital of France is Paris."))
        assert mode == "rule-based (LLM unavailable or invalid response)"
        assert len(claims) == 1
        assert claims[0]["text"] == "The capital of France is Paris."

    def test_extract_llm_malformed_json_fallback(self, monkeypatch):
        monkeypatch.setenv("DAM_LLM_URL", "https://llm.example.test/v1/chat/completions")

        async def mock_post_bad_json(self, *args, **kwargs):
            return httpx.Response(
                200,
                request=httpx.Request("POST", args[0]),
                json={"choices": [{"message": {"content": "not valid json"}}]}
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_bad_json)
        claims, mode = asyncio.run(extract("The capital of France is Paris."))
        assert mode == "rule-based (LLM unavailable or invalid response)"
        assert len(claims) == 1

    def test_extract_llm_overlapping_spans_fallback(self, monkeypatch):
        monkeypatch.setenv("DAM_LLM_URL", "https://llm.example.test/v1/chat/completions")

        async def mock_post_overlapping(self, *args, **kwargs):
            return httpx.Response(
                200,
                request=httpx.Request("POST", args[0]),
                json={"choices": [{"message": {"content": '{"claims": [{"start": 0, "end": 20}, {"start": 10, "end": 25}]}'}}]}
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_overlapping)
        claims, mode = asyncio.run(extract("The capital of France is Paris."))
        assert mode == "rule-based (LLM unavailable or invalid response)"
