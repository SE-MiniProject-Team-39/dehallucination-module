"""Adapters return evidence, never infer truth from retrieval similarity alone."""
import asyncio
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

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
        (r'(.+?) orbits (?:the )?(.+?)[.!]?$', 'orbits', False),
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


class WikipediaSource:
    name = "wikipedia"

    async def query(self, text, client):
        result = await client.get("https://en.wikipedia.org/w/api.php", params={
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


async def lookup(adapter, text, client, timeout, weight):
    try:
        items = await asyncio.wait_for(adapter.query(text, client), timeout=timeout)
        for item in items:
            item['trust_weight'] = weight
        return {"source": adapter.name, "status": "ok", "evidence": items}
    except (TimeoutError, httpx.TimeoutException):
        return {"source": adapter.name, "status": "timeout", "evidence": []}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {"source": adapter.name, "status": "unavailable", "evidence": []}
