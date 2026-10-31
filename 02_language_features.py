"""Session 2 - Language features: decorators, context managers, generators, caching.

Run (from the codealong folder):  python day1/02_language_features.py
"""

import csv  # read CSV files
import functools  # wraps (keep metadata) and lru_cache (memoisation)
import time  # timing and sleeping
from contextlib import contextmanager  # turns a generator into a context manager
from pathlib import Path  # object-oriented file paths

DATA = Path("data")

# --- Decorator: wraps a function, keeps its name/docstring (functools.wraps) --
def timed(func):  # takes a function, returns a new wrapped function
    @functools.wraps(func)  # copy func's __name__/__doc__ onto wrapper
    def wrapper(*args, **kwargs):  # accept any arguments and pass them through
        start = time.perf_counter()  # high-resolution start time
        try:
            return func(*args, **kwargs)  # call the real function
        finally:  # runs even if func raises
            print(f"[timed] {func.__name__} took {time.perf_counter() - start:.4f}s")  # report elapsed time

    return wrapper  # the decorator replaces func with wrapper

# --- Decorator with arguments = a decorator factory ---------------------------
def retry(times=1, exceptions=(Exception,)):  # outer layer receives the decorator's settings
    def decorator(func):  # middle layer receives the function
        @functools.wraps(func)  # preserve func's metadata
        def wrapper(*args, **kwargs):  # inner layer runs on every call
            for attempt in range(1, times + 1):  # attempts numbered 1..times
                try:
                    return func(*args, **kwargs)  # success -> return immediately
                except exceptions as exc:  # only retry on the chosen exception types
                    print(f"[retry] attempt {attempt} failed: {exc}")  # log the failure
                    if attempt == times:  # out of attempts
                        raise  # re-raise the original error

        return wrapper  # decorator returns the wrapper

    return decorator  # factory returns the decorator

@timed  # measure how long the function takes
def count_orders():
    return sum(1 for _ in read_rows(DATA / "orders_dirty.csv"))  # count rows without loading the whole file
    
# --- Generators: lazy, one row at a time, constant memory ---------------------
def read_rows(path):  # generator function: contains yield
    with open(path, newline="", encoding="utf-8") as f:  # file closes automatically
        yield from csv.DictReader(f)  # hand out one row (dict) at a time

def read_rows_all(path):
    with open(path, mode="r", encoding="utf-8") as f:
        file_contents = f.read()


@contextmanager  # lets us use "with stopwatch(...)" without writing a class
def stopwatch(label):
    start = time.perf_counter()  # runs on entering the with-block
    try:
        yield  # the with-block body runs here
    finally:  # runs on exit, even after an error
        print(f"[stopwatch] {label}: {time.perf_counter() - start:.4f}s")  # print elapsed time

def batched(iterable, size):  # group items into lists of `size`
    batch = []  # current group being filled
    for item in iterable:  # pull items lazily
        batch.append(item)  # add to current group
        if len(batch) == size:  # group is full
            yield batch  # hand it to the caller
            batch = []  # start a new group
    if batch:  # leftover items (last group is smaller)
        yield batch  # hand out the partial group


calls = {"n": 0} 

@retry(times=2, exceptions=(ConnectionError,))  # retry up to 3 times on ConnectionError only
def flaky():
    calls["n"] += 1  # count each call
    if calls["n"] < 3:  # first two calls fail
        raise ConnectionError("network down")  # simulated network failure
    return "ok"  # third call succeeds

if __name__ == "__main__":
    #print("Orders", count_orders())
    #print("flaky" , flaky())

    with stopwatch("first 3 batches of 1000"):  # time the whole block
        for i, batch in enumerate(batched(read_rows(DATA / "orders_dirty.csv"), 1000)):  # batches of 1000 rows
            print("batch", i, "size", len(batch))  # show batch number and size
            if i == 2:  # stop after the third batch (index 2)
                break  # generators are lazy, so the rest is never read
