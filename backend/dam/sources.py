"""Adapters return evidence, never infer truth from retrieval similarity alone."""
import asyncio
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from . import judge

FACTS = json.loads(Path(__file__).with_name("corpus.json").read_text(encoding="utf-8"))


def normalize(text):
    return re.sub(r'[^\w\s]', '', text.casefold()).strip()


def proposition(text):
    # Templates only represent positive, unqualified, single relationships.
    # Negation, time qualifiers and compound statements require entailment logic.
    if re.search(r'\b(not|never|no|and|or|but|may|might|could|would|which|where|because|since|formerly|previously|today|currently|once|also)\b|[,;:]|\d', text, re.I):
        return None
    patterns = [
        (r'(?:the )?capital of (.+?) is (.+?)[.!]?$', 'capital', False),
        (r'(.+?) is (?:the )?capital of (.+?)[.!]?$', 'capital', True),
        (r'(.+?) was written by (.+?)[.!]?$', 'author', False),
        (r'(?:the )?(.+?) orbits (?:the )?(.+?)[.!]?$', 'orbits', False),
    ]
    for pattern, relation, reverse in patterns:
        match = re.fullmatch(pattern, text.strip(), re.I)
        if match:
            subject, value = match.groups()[::-1] if reverse else match.groups()
            return normalize(subject), relation, normalize(value)
    return None


def matching_fact(text):
    parsed = proposition(text)
    if parsed:
        for fact in FACTS:
            if parsed[:2] == (normalize(fact['subject']), fact['relation']):
                return fact, parsed[2]
    return None, None


def evidence(source, statement, url, verdict, correction=None, observed_at=None):
    return {"source": source, "snippet": statement, "url": url, "verdict": verdict,
            "correction": correction, "quality": 0.95,
            "observed_at": observed_at or "2026-09-05T00:00:00+00:00"}


class CuratedSource:
    name = "curated"

    async def query(self, text, client):
        fact, value = matching_fact(text)
        if not fact:
            return []
        verdict = "Supported" if value == normalize(fact['value']) else "Contradicted"
        return [evidence(self.name, fact['statement'], fact['url'], verdict,
                         fact['statement'] if verdict == "Contradicted" else None)]


class WikidataSource:
    name = "wikidata"

    def __init__(self, live=False):
        self.live = live

    async def query(self, text, client):
        fact, value = matching_fact(text)
        if not self.live:
            # Explicit offline snapshot, not a claimed live knowledge-graph lookup.
            if not fact:
                return []
            verdict = "Supported" if value == normalize(fact['value']) else "Contradicted"
            item = evidence(self.name, fact['statement'], fact['url'], verdict,
                            fact['statement'] if verdict == "Contradicted" else None)
            item['snapshot'] = True
            return [item]
        parsed = proposition(text)
        if not parsed:
            # Still perform a structured entity search for every extracted claim.
            result = await client.get("https://www.wikidata.org/w/api.php", params={
                "action": "wbsearchentities", "search": text[:160], "language": "en", "format": "json", "limit": 1})
            result.raise_for_status()
            return []  # Entity matches alone do not establish a relationship.
        subject, relation, claimed = parsed
        prop = {"capital": "P36", "author": "P50", "orbits": "P397"}[relation]
        query = '''SELECT ?valueLabel WHERE {
          ?entity rdfs:label %s@en . ?entity wdt:%s ?value .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        } LIMIT 10''' % (json.dumps(fact['subject'] if fact else subject.title()), prop)
        result = await client.get("https://query.wikidata.org/sparql", params={"query": query, "format": "json"})
        result.raise_for_status()
        values = [row['valueLabel']['value'] for row in result.json()['results']['bindings']]
        if not values:
            return []
        # Multiple values can be historically qualified; only claim support if matching.
        supported = claimed in [normalize(v) for v in values]
        if not supported and len(values) != 1:
            return []
        actual = next((v for v in values if normalize(v) == claimed), values[0])
        template = {"capital": "The capital of {s} is {v}.", "author": "{s} was written by {v}.", "orbits": "{s} orbits {v}."}[relation]
        statement = template.format(s=fact['subject'] if fact else subject.title(), v=actual)
        return [evidence(self.name, statement, "https://query.wikidata.org/#" + quote(query),
                         "Supported" if supported else "Contradicted", None if supported else statement,
                         datetime.now(timezone.utc).isoformat())]


STOPWORDS = set("a an the of in on at to for and or is are was were be been by with as that this it its from into than "
                "all any every can does do did has have had".split())


def _content_words(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


WIKI_API = "https://en.wikipedia.org/w/api.php"


async def retrieve_passages(claim, client, k=3):
    """Top-k three-sentence windows from the best-matching Wikipedia articles."""
    found = await client.get(WIKI_API, params={"action": "query", "list": "search", "srsearch": claim[:250],
                                               "srlimit": 3, "format": "json"})
    found.raise_for_status()
    titles = [hit["title"] for hit in found.json().get("query", {}).get("search", [])]
    if not titles:
        return []
    docs = []
    leads = await client.get(WIKI_API, params={"action": "query", "prop": "extracts", "explaintext": 1, "exintro": 1,
                                               "exlimit": 3, "titles": "|".join(titles), "redirects": 1, "format": "json"})
    leads.raise_for_status()
    docs += [(p.get("pageid"), p.get("extract", "")) for p in leads.json().get("query", {}).get("pages", {}).values()]
    full = await client.get(WIKI_API, params={"action": "query", "prop": "extracts", "explaintext": 1, "titles": titles[0],
                                              "redirects": 1, "format": "json"})
    full.raise_for_status()
    docs += [(p.get("pageid"), p.get("extract", "")[:60000]) for p in full.json().get("query", {}).get("pages", {}).values()]
    wanted = set(_content_words(claim))
    windows = []
    for pageid, body in docs:
        if not pageid:
            continue
        sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", html.unescape(body)) if len(s.split()) > 3]
        for i in range(len(sentences)):
            window = " ".join(sentences[i:i + 3])
            overlap = len(wanted & set(_content_words(window))) / (len(wanted) or 1)
            windows.append((overlap, pageid, window))
    windows.sort(key=lambda w: -w[0])
    chosen, seen = [], set()
    for overlap, pageid, window in windows:
        if overlap == 0 or window in seen:
            continue
        seen.add(window)
        chosen.append({"text": window, "url": "https://en.wikipedia.org/?curid=" + str(pageid)})
        if len(chosen) == k:
            break
    return chosen


class WikipediaSource:
    name = "wikipedia"

    @property
    def timeout(self):
        cfg = judge.config()
        return cfg["timeout"] + 10 if cfg else None

    async def query(self, text, client):
        cfg = judge.config()
        if cfg:
            # Retrieve passages, then let the judge decide whether they support or
            # contradict the claim. The quote must come from the passages.
            passages = await retrieve_passages(text, client)
            if not passages:
                return []
            label, quote = await judge.judge_passages(text, passages, client, cfg)
            if not label:
                return []
            source = next((p for p in passages if quote and quote in re.sub(r"\s+", " ", p["text"])), passages[0])
            item = evidence(self.name, quote or source["text"], source["url"], label,
                            quote if label == "Contradicted" and quote else None, datetime.now(timezone.utc).isoformat())
            item["quality"] = 0.85
            item["judged_by"] = cfg["model"]
            return [item]
        result = await client.get(WIKI_API, params={
            "action": "query", "generator": "search", "gsrsearch": text[:250], "gsrlimit": 2,
            "prop": "extracts", "exintro": 1, "explaintext": 1, "format": "json"})
        result.raise_for_status()
        items = []
        for page in result.json().get('query', {}).get('pages', {}).values():
            for sentence in re.split(r'(?<=[.!?])\s+', html.unescape(page.get('extract', ''))):
                if normalize(sentence) == normalize(text):
                    items.append(evidence(self.name, sentence, "https://en.wikipedia.org/?curid=" + str(page['pageid']),
                                          "Supported", observed_at=datetime.now(timezone.utc).isoformat()))
        return items


class ModelKnowledgeSource:
    """The judge model's own knowledge: uncited, low quality, always flagged for review on its own."""
    name = "model"

    @property
    def timeout(self):
        cfg = judge.config()
        return cfg["timeout"] + 5 if cfg else None

    async def query(self, text, client):
        cfg = judge.config()
        if not cfg:
            return []
        label, reason = await judge.judge_knowledge(text, client, cfg)
        if not label:
            return []
        item = evidence(self.name, reason or ("Consistent with" if label == "Supported" else "Inconsistent with") +
                        " the model's general knowledge.", "llm:" + cfg["model"], label, None,
                        datetime.now(timezone.utc).isoformat())
        item["quality"] = 0.45
        item["uncited"] = True
        return [item]


async def lookup(adapter, text, client, timeout, weight):
    try:
        # Judged sources wait for a model, so they get their own (longer) budget.
        budget = max(timeout, getattr(adapter, "timeout", None) or 0)
        items = await asyncio.wait_for(adapter.query(text, client), timeout=budget)
        for item in items:
            item['trust_weight'] = weight
        return {"source": adapter.name, "status": "ok", "evidence": items}
    except (TimeoutError, httpx.TimeoutException):
        return {"source": adapter.name, "status": "timeout", "evidence": []}
    except Exception:
        # One failing adapter must never fail the whole verification request (REQ-8).
        # CancelledError is a BaseException and still propagates.
        return {"source": adapter.name, "status": "unavailable", "evidence": []}
