import asyncio
import copy
import hashlib
import json
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from .extraction import detect_injections, extract
from .models import Cache, now
from . import judge
from .sources import CuratedSource, ModelKnowledgeSource, WikidataSource, WikipediaSource, lookup, normalize

DEFAULT_SOURCE = {'enabled': True, 'weight': 1}


def score(results, threshold):
    evidence = [item for result in results for item in result['evidence']]
    # Uncited model knowledge only counts when no cited source has evidence.
    cited = [item for item in evidence if not item.get('uncited')]
    if cited:
        evidence = cited
    if not evidence:
        verdict = "Not-Checkable" if not results or any(r['status'] != 'ok' for r in results) else "Unsupported"
        return {"verdict": verdict, "confidence_score": 0.0, "flagged": 0 < threshold, "evidence": [], "suggested_correction": None}
    support = contradiction = 0
    for item in evidence:
        age = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(item['observed_at'])).days)
        recency = max(0.5, 1 - age / 3650)
        strength = item['quality'] * item['trust_weight'] * recency
        if item['verdict'] == 'Supported':
            support += strength
        else:
            contradiction += strength
    total_weight = len(evidence)
    alternative = contradiction / total_weight
    confidence = round(max(0.0, min(1.0, support / total_weight)), 4)
    verdict = 'Supported' if support > contradiction else 'Contradicted'
    correction = next((e['correction'] for e in evidence if e.get('correction')), None)
    return {"verdict": verdict, "confidence_score": confidence, "flagged": confidence < threshold,
            "evidence": evidence, "suggested_correction": correction if verdict == 'Contradicted' and alternative > 0.7 else None,
            "correction_label": "Evidence-based suggestion; original text preserved" if correction and alternative > 0.7 else None}


def summarize(report):
    claims = report['claims']
    report['hallucination_score'] = round(sum(1 - c['confidence_score'] for c in claims if c['flagged']) / len(claims), 4) if claims else 0
    report['counts'] = {v: sum(c['verdict'] == v for c in claims) for v in ['Supported', 'Contradicted', 'Unsupported', 'Not-Checkable']}
    return report


class Pipeline:
    def __init__(self, sessions, live=False):
        self.sessions = sessions
        self.live = live
        self.semaphore = asyncio.Semaphore(12)

    async def run(self, text, context, settings, threshold, extracted=None):
        claims, extractor = extracted if extracted is not None else await extract(text, context)
        adapters = [CuratedSource(), WikidataSource(self.live)]
        if self.live:
            adapters.append(WikipediaSource())
        judge_cfg = judge.config()
        if judge_cfg:
            adapters.append(ModelKnowledgeSource())
        source_cfg = {a.name: settings['sources'].get(a.name, DEFAULT_SOURCE) for a in adapters}
        adapters = [a for a in adapters if source_cfg[a.name]['enabled']]
        judge_model = judge_cfg['model'] if judge_cfg else None
        async with AsyncExitStack() as stack:
            client = None
            async def process(claim):
                nonlocal client
                cache_id = hashlib.sha256(json.dumps([normalize(claim['text']), settings, self.live, judge_model], sort_keys=True).encode()).hexdigest()
                with self.sessions() as db:
                    cached = db.get(Cache, cache_id)
                    if cached and (datetime.now(timezone.utc) - datetime.fromisoformat(cached.created_at)).total_seconds() < 86400:
                        results = copy.deepcopy(cached.value)
                        hit = True
                    else:
                        results, hit = None, False
                if results is None:
                    async with self.semaphore:
                        if client is None:
                            client = await stack.enter_async_context(httpx.AsyncClient(headers={'User-Agent': 'DAM-University-Project/1.0 (https://github.com/SE-MiniProject-Team-39/dehallucination-module)'}, timeout=settings['source_timeout']))
                        results = await asyncio.gather(*(lookup(a, claim['text'], client, settings['source_timeout'], source_cfg[a.name]['weight']) for a in adapters))
                    # Failures are retried rather than cached for a full day.
                    if results and all(r['status'] == 'ok' for r in results):
                        with self.sessions() as db:
                            db.merge(Cache(id=cache_id, value=results, created_at=now()))
                            db.commit()
                return {**claim, "claim_id": str(uuid4()), **score(results, threshold), "source_results": results, "cached": hit}
            checked = await asyncio.gather(*(process(c) for c in claims))
        return summarize({"original_text": text, "claims": checked, "extractor": extractor,
                          "injection_warnings": detect_injections(text), "judge": judge_model,
                          "mode": "live" if self.live else "offline snapshot", "confidence_threshold": threshold})
