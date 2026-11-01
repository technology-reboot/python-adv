"""Session 11 - Async: concurrent HTTP calls with asyncio + httpx.

Terminal 1 (from codealong):  uvicorn day1.mock_server:app --port 8001
Terminal 2 (from codealong):  python day2/11_async.py
(each /api/products/{id} call takes 0.5s on the server)
"""
import asyncio  # event loop and concurrency tools
import time  # measure elapsed time

import httpx  # HTTP client with async support

BASE = "http://localhost:8001"  # mock server address
IDS = list(range(1, 21))  # product ids 1..20


async def fetch(client, pid):  # coroutine: fetch one product
    resp = await client.get(f"{BASE}/api/products/{pid}", timeout=10)  # await = let other tasks run while waiting
    resp.raise_for_status()  # raise on 4xx/5xx
    return resp.json()  # parsed product dict


async def sequential():  # baseline: one call at a time
    async with httpx.AsyncClient() as client:  # async client, closed automatically
        return [await fetch(client, pid) for pid in IDS]  # one after another


async def concurrent():  # all calls in flight together
    async with httpx.AsyncClient() as client:
        return await asyncio.gather(*(fetch(client, pid) for pid in IDS))  # all at once


async def limited(max_parallel=5):  # concurrency with a cap
    sem = asyncio.Semaphore(max_parallel)  # be polite: cap concurrency

    async def guarded(client, pid):  # wrapper that waits for a free slot
        async with sem:  # at most max_parallel tasks inside at once
            return await fetch(client, pid)

    async with httpx.AsyncClient() as client:
        return await asyncio.gather(*(guarded(client, pid) for pid in IDS))  # run all, but throttled


async def with_errors():  # demonstrate error handling in gather
    """return_exceptions=True: one failure doesn't cancel the others."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(fetch(client, pid) for pid in [1, 2, 999]), return_exceptions=True)  # 999 doesn't exist -> 404
    ok = [r for r in results if not isinstance(r, Exception)]  # successful results
    bad = [r for r in results if isinstance(r, Exception)]  # exceptions returned as values
    return len(ok), len(bad)  # (2, 1)


async def main():  # entry coroutine
    for name, fn in [("sequential", sequential), ("gather", concurrent), ("semaphore(5)", limited)]:  # compare three strategies
        start = time.perf_counter()  # start timer
        items = await fn()  # run the strategy
        print(f"{name:14} {len(items)} items in {time.perf_counter() - start:.2f}s")  # ~10s, ~0.5s, ~2s
    print("with errors (ok, failed):", await with_errors())  # show partial failure handling


if __name__ == "__main__":  # demo only when run directly
    asyncio.run(main())  # start the event loop and run main()
