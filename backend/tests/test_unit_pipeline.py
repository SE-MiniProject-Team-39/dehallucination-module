from datetime import datetime, timezone, timedelta
import pytest

from backend.dam.pipeline import Pipeline, score, summarize
from backend.dam.sources import evidence


class TestPipelineScore:
    def test_score_empty_results_not_checkable(self):
        res = score([], threshold=0.5)
        assert res["verdict"] == "Not-Checkable"
        assert res["confidence_score"] == 0.0
        assert res["flagged"] is True
        assert res["evidence"] == []
        assert res["suggested_correction"] is None

    def test_score_failed_source_not_checkable(self):
        results = [
            {"source": "curated", "status": "timeout", "evidence": []},
            {"source": "wikidata", "status": "unavailable", "evidence": []},
        ]
        res = score(results, threshold=0.5)
        assert res["verdict"] == "Not-Checkable"
        assert res["confidence_score"] == 0.0
        assert res["flagged"] is True

    def test_score_ok_sources_no_evidence_unsupported(self):
        results = [
            {"source": "curated", "status": "ok", "evidence": []},
            {"source": "wikidata", "status": "ok", "evidence": []},
        ]
        res = score(results, threshold=0.5)
        assert res["verdict"] == "Unsupported"
        assert res["confidence_score"] == 0.0
        assert res["flagged"] is True
        assert res["evidence"] == []

    def test_score_threshold_zero_not_flagged(self):
        results = [{"source": "curated", "status": "ok", "evidence": []}]
        res = score(results, threshold=0.0)
        assert res["verdict"] == "Unsupported"
        assert res["flagged"] is False

    def test_score_supported_evidence(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        ev = evidence("wikidata", "Paris is capital", "https://wikidata.org", "Supported", observed_at=now_iso)
        ev["trust_weight"] = 1.0
        ev["quality"] = 1.0
        res = score([{"status": "ok", "evidence": [ev]}], threshold=0.5)
        assert res["verdict"] == "Supported"
        assert res["confidence_score"] == 1.0
        assert res["flagged"] is False
        assert res["suggested_correction"] is None

    def test_score_tie_chooses_contradicted(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        ev1 = evidence("s1", "Fact 1", "https://s1.org", "Supported", observed_at=now_iso)
        ev1.update(quality=1.0, trust_weight=1.0)
        ev2 = evidence("s2", "Fact 2", "https://s2.org", "Contradicted", correction="Corrected", observed_at=now_iso)
        ev2.update(quality=1.0, trust_weight=1.0)

        res = score([{"status": "ok", "evidence": [ev1, ev2]}], threshold=0.5)
        # support (1.0) is not > contradiction (1.0) -> tie yields Contradicted
        assert res["verdict"] == "Contradicted"
        assert res["confidence_score"] == 0.5
        assert res["flagged"] is False  # confidence 0.5 is not < threshold 0.5

    def test_score_recency_floor_at_10_years(self):
        ten_years_ago = (datetime.now(timezone.utc) - timedelta(days=3650)).isoformat()
        twenty_years_ago = (datetime.now(timezone.utc) - timedelta(days=7300)).isoformat()

        ev_10 = evidence("s", "Fact", "urn:s", "Supported", observed_at=ten_years_ago)
        ev_10.update(quality=1.0, trust_weight=1.0)
        score_10 = score([{"status": "ok", "evidence": [ev_10]}], 0.5)["confidence_score"]

        ev_20 = evidence("s", "Fact", "urn:s", "Supported", observed_at=twenty_years_ago)
        ev_20.update(quality=1.0, trust_weight=1.0)
        score_20 = score([{"status": "ok", "evidence": [ev_20]}], 0.5)["confidence_score"]

        # Recency is clamped at 0.5 minimum floor
        assert score_10 == 0.5
        assert score_20 == 0.5

    def test_score_future_observed_at_clamped(self):
        future_iso = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        ev = evidence("s", "Fact", "urn:s", "Supported", observed_at=future_iso)
        ev.update(quality=1.0, trust_weight=1.0)
        res = score([{"status": "ok", "evidence": [ev]}], 0.5)
        assert res["confidence_score"] == 1.0

    def test_suggested_correction_requires_high_alternative_weight(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        # 1 contradicted evidence with quality 0.6 -> alternative = 0.6 / 1 = 0.6 <= 0.7 -> no correction
        ev_low = evidence("s", "Claim", "urn:s", "Contradicted", correction="Better claim", observed_at=now_iso)
        ev_low.update(quality=0.6, trust_weight=1.0)
        res_low = score([{"status": "ok", "evidence": [ev_low]}], 0.5)
        assert res_low["verdict"] == "Contradicted"
        assert res_low["suggested_correction"] is None

        # 1 contradicted evidence with quality 0.95 -> alternative = 0.95 / 1 = 0.95 > 0.7 -> correction included
        ev_high = evidence("s", "Claim", "urn:s", "Contradicted", correction="Better claim", observed_at=now_iso)
        ev_high.update(quality=0.95, trust_weight=1.0)
        res_high = score([{"status": "ok", "evidence": [ev_high]}], 0.5)
        assert res_high["verdict"] == "Contradicted"
        assert res_high["suggested_correction"] == "Better claim"
        assert res_high["correction_label"] == "Evidence-based suggestion; original text preserved"


class TestPipelineSummarize:
    def test_summarize_empty_claims(self):
        report = {"claims": []}
        summarize(report)
        assert report["hallucination_score"] == 0
        assert report["counts"] == {
            "Supported": 0, "Contradicted": 0, "Unsupported": 0, "Not-Checkable": 0
        }

    def test_summarize_all_supported_unflagged(self):
        report = {
            "claims": [
                {"verdict": "Supported", "confidence_score": 0.9, "flagged": False},
                {"verdict": "Supported", "confidence_score": 0.85, "flagged": False},
            ]
        }
        summarize(report)
        assert report["hallucination_score"] == 0
        assert report["counts"]["Supported"] == 2
        assert report["counts"]["Contradicted"] == 0

    def test_summarize_mixed_claims_score(self):
        report = {
            "claims": [
                {"verdict": "Supported", "confidence_score": 0.9, "flagged": False},
                {"verdict": "Contradicted", "confidence_score": 0.1, "flagged": True},
                {"verdict": "Unsupported", "confidence_score": 0.0, "flagged": True},
                {"verdict": "Not-Checkable", "confidence_score": 0.0, "flagged": True},
            ]
        }
        summarize(report)
        # Flagged claims:
        # claim 2: 1 - 0.1 = 0.9
        # claim 3: 1 - 0.0 = 1.0
        # claim 4: 1 - 0.0 = 1.0
        # sum = 2.9 / 4 = 0.725
        assert report["hallucination_score"] == 0.725
        assert report["counts"] == {
            "Supported": 1, "Contradicted": 1, "Unsupported": 1, "Not-Checkable": 1
        }
