import time
import requests

BASE = "http://localhost:8001"  # address of the mock server

class FeedError(Exception):  # our error for "gave up after all retries"
    pass

def get_json(session, path, retries=4):  # GET a path and return parsed JSON
    """GET with timeout, status check and retry with backoff for 5xx / network errors."""
    for attempt in range(1, retries + 1):  # attempts 1..retries
        try:
            resp = session.get(f"{BASE}{path}", timeout=5)  # ALWAYS set a timeout
            if resp.status_code >= 500:  # server-side failure
                raise requests.HTTPError(f"server said {resp.status_code}")  # treat as retryable
            resp.raise_for_status()  # 4xx -> exception
            return resp.json()  # success: parse the JSON body
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:  # retryable problems
            print(f"  attempt {attempt} failed: {exc}")  # show what went wrong
            if attempt == retries:  # no attempts left
                raise FeedError(path) from exc  # give up with our own error
            time.sleep(0.2 * 2**attempt)  # exponential backoff

def all_products(session):  # fetch every page of products
    """Follow pagination until there are no more pages."""
    page, items = 1, []  # start at page 1 with an empty result list
    while True:
        data = get_json(session, f"/api/products?page={page}&page_size=15")  # fetch one page
        items += data["items"]  # append this page's items
        if not data["next_page"]:  # None means last page
            return items  # done
        page = data["next_page"]  # move on to the next page

if __name__ == "__main__":  # demo only when run directly
    with requests.Session() as s:  # Session = connection reuse + shared headers
        s.headers["Accept"] = "application/json"  # header sent with every request
        print("products:", len(all_products(s)))  # total products across all pages
        print("flaky ->", get_json(s, "/api/flaky"))  # endpoint that fails twice, retry makes it succeed
