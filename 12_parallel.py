"""Session 12 - Parallel programming: threads (I/O), processes (CPU), race conditions.

Run (from the codealong folder):  python day2/12_parallel.py
"""
import threading  # threads and locks
import time  # sleeping and timing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor  # high-level pools of workers


# --- 1. I/O-bound -> threads (the GIL is released while waiting) ---------------
def fake_download(n):
    time.sleep(0.3)  # pretend network call
    return n  # return something so we can collect results


# --- 2. CPU-bound -> processes (each has its own GIL) --------------------------
def cpu_heavy(n):
    return sum(i * i for i in range(n))  # pure computation, keeps the CPU busy


# --- 3. Race condition: += on a shared value is NOT atomic ---------------------
def run_counter(use_lock):  # returns the final counter value
    counter = {"n": 0}  # shared state (dict so threads can mutate it)
    lock = threading.Lock()  # mutual-exclusion lock

    def work():  # what each thread runs
        for _ in range(20_000):  # 20,000 increments per thread
            if use_lock:  # safe version
                with lock:  # only one thread inside at a time
                    tmp = counter["n"]  # read ...
                    time.sleep(0)  # (lets another thread in - makes the bug show up reliably)
                    counter["n"] = tmp + 1  # ... modify, write
            else:  # unsafe version
                tmp = counter["n"]  # read the shared value
                time.sleep(0)  # yield to other threads between read and write
                counter["n"] = tmp + 1  # write back a possibly stale value -> lost update

    threads = [threading.Thread(target=work) for _ in range(4)]  # create 4 threads
    [t.start() for t in threads]  # start them all
    [t.join() for t in threads]  # wait until all finish
    return counter["n"]  # expected 80000


def timed(label, fn):  # run fn and print how long it took
    start = time.perf_counter()  # start timer
    result = fn()  # run the work
    print(f"{label:28} {time.perf_counter() - start:.2f}s")  # padded label + seconds
    return result  # pass the result through


if __name__ == "__main__":  # this guard is REQUIRED for processes on Windows
    print("--- I/O-bound: 10 x 0.3s downloads")
    timed("sequential", lambda: [fake_download(i) for i in range(10)])  # ~3s
    with ThreadPoolExecutor(max_workers=10) as pool:  # 10 threads
        timed("ThreadPoolExecutor", lambda: list(pool.map(fake_download, range(10))))  # ~0.3s, waits overlap

    print("--- CPU-bound: 4 x sum of squares")
    jobs = [5_000_000] * 4  # four identical heavy jobs
    timed("sequential", lambda: [cpu_heavy(n) for n in jobs])  # baseline
    with ThreadPoolExecutor(max_workers=4) as pool:  # threads share one GIL
        timed("threads (no speedup, GIL)", lambda: list(pool.map(cpu_heavy, jobs)))  # about the same as sequential
    with ProcessPoolExecutor(max_workers=4) as pool:  # separate processes, separate GILs
        timed("processes (real speedup)", lambda: list(pool.map(cpu_heavy, jobs)))  # runs on multiple cores

    print("--- Race condition: 4 threads x 20000 increments (expected 80000)")
    print("no lock:  ", run_counter(use_lock=False), "<- lost updates!")  # far below 80000
    print("with lock:", run_counter(use_lock=True))  # exactly 80000
