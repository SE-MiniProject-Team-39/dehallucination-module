"""Measure an already running local instance without displaying credentials."""
import asyncio
import json
import os
import statistics
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv


async def main():
    load_dotenv()
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000', timeout=35,
                                 headers={'Authorization': 'Bearer ' + os.environ['DAM_API_KEY']}) as client:
        payload = {'source_app_id': 'demo-app', 'text': 'The capital of France is Paris. The capital of Australia is Sydney.'}
        first = await client.post('/verify', json=payload)
        first.raise_for_status()
        async def submit():
            begin = time.perf_counter()
            response = await client.post('/verify', json=payload)
            response.raise_for_status()
            assert all(c['cached'] for c in response.json()['claims'])
            return (time.perf_counter() - begin) * 1000
        sequential = [await submit() for _ in range(10)]
        concurrent = await asyncio.gather(*(submit() for _ in range(20)))
        data = {'mode': 'offline snapshot, warmed cache, SQLite, one worker', 'sequential_samples': len(sequential),
                'sequential_median_ms': round(statistics.median(sequential), 2),
                'sequential_p95_ms': round(sorted(sequential)[-1], 2),
                'concurrent_requests': len(concurrent), 'concurrent_max_ms': round(max(concurrent), 2),
                'all_concurrent_http_200': True, 'note': 'Local warmed-cache measurements do not establish live-source latency or production queueing SLAs.'}
        Path('docs/local-performance.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(data, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
