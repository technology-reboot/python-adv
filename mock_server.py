"""Tiny fake product API used by the requests, async and parallel sessions.

Run (from the codealong folder):  uvicorn mock_server:app --port 8001
"""
import asyncio  # for non-blocking sleep
import csv  # read the products file
from pathlib import Path  # file paths

from fastapi import FastAPI, HTTPException  # web framework + HTTP error helper

app = FastAPI()  # the application object uvicorn serves

with open(Path("data") / "products.csv", newline="", encoding="utf-8") as f:  # load data once at startup
    PRODUCTS = list(csv.DictReader(f))  # list of dicts, one per product
flaky_calls = {"n": 0}  # counts calls to /api/flaky


@app.get("/api/products")  # GET /api/products?page=1&page_size=15
def products(page: int = 1, page_size: int = 15):  # query params with defaults, auto-validated as ints
    start = (page - 1) * page_size  # index of the first item on this page
    items = PRODUCTS[start : start + page_size]  # slice out this page
    more = start + page_size < len(PRODUCTS)  # are there items beyond this page?
    return {"items": items, "next_page": page + 1 if more else None}  # next page number or None


@app.get("/api/products/{pid}")  # GET one product; {pid} is a path parameter
async def product(pid: int):  # async so the sleep doesn't block the server
    await asyncio.sleep(0.5)  # pretend to be slow
    for p in PRODUCTS:  # linear search
        if int(p["id"]) == pid:  # CSV values are strings, so convert
            return p  # found -> returned as JSON
    raise HTTPException(404, "not found")  # unknown id -> HTTP 404


@app.get("/api/flaky")  # fails the first 2 calls, then works
def flaky():
    flaky_calls["n"] += 1  # count this call
    if flaky_calls["n"] <= 2:  # first two calls
        raise HTTPException(503, "try again")  # 503 Service Unavailable
    return {"status": "ok", "after_calls": flaky_calls["n"]}  # success from the 3rd call on
