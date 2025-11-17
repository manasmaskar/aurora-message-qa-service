# analysis_api_suite.py
import sys
import time
from collections import Counter, defaultdict
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

import requests

from app.config import MESSAGES_ENDPOINT, PAGE_SIZE

REQUEST_TIMEOUT = 5.0
MAX_PAGES = 80
MAX_FAILURES = 8
MAX_RETRIES_PER_PAGE = 3  # new: retry each page a few times
DUP_WINDOW_SECONDS = 600


def parse_ts(raw: Optional[str]):
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(text)
    except ValueError:
        if text.endswith("Z"):
            try:
                from datetime import datetime

                return datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None


def extract_id(msg: Dict[str, Any]):
    return msg.get("id") or msg.get("message_id")


def extract_ts(msg: Dict[str, Any]):
    return parse_ts(
        msg.get("timestamp") or msg.get("created_at") or msg.get("created")
    )


def fetch_page_with_retries(skip: int, limit: int) -> Dict[str, Any]:
    """
    Fetch a single page from the messages API, with limited retries.
    Returns a dict with status, elapsed, body (full text), items, total.
    """
    last_exc: Optional[Exception] = None
    status: Optional[int] = None
    elapsed: Optional[float] = None
    body: Optional[str] = None
    items: List[Dict[str, Any]] = []
    total: Optional[int] = None

    for attempt in range(1, MAX_RETRIES_PER_PAGE + 1):
        start = time.time()
        try:
            resp = requests.get(
                MESSAGES_ENDPOINT,
                params={"skip": skip, "limit": limit},
                timeout=REQUEST_TIMEOUT,
            )
            elapsed = time.time() - start
            status = resp.status_code
            body = resp.text

            if status == 200:
                try:
                    data = resp.json()
                    items = data.get("items", [])
                    total = data.get("total")
                except Exception:
                    # JSON parse error: keep body for debugging, items stays empty
                    items = []
                    total = None
                # good page, stop retrying
                break
            else:
                # non-200: keep status/body, maybe retry
                last_exc = None
        except Exception as exc:
            elapsed = time.time() - start
            status = None
            body = str(exc)
            last_exc = exc

        # small delay between retries to avoid hammering
        time.sleep(0.2)

    # if everything failed with exceptions, ensure body is set
    if status is None and last_exc is not None and body is None:
        body = repr(last_exc)

    return {
        "skip": skip,
        "status": status,
        "elapsed": elapsed,
        "body": body,
        "items": items,
        "count": len(items),
        "total": total,
        "body_len": len(body) if body is not None else 0,
    }


def probe_pages() -> List[Dict[str, Any]]:
    pages: List[Dict[str, Any]] = []
    skip = 0
    failures = 0

    for _ in range(MAX_PAGES):
        page = fetch_page_with_retries(skip, PAGE_SIZE)
        pages.append(page)

        status = page["status"]
        items = page["items"]
        total = page["total"]

        if status != 200:
            failures += 1
            if failures >= MAX_FAILURES:
                break
        else:
            failures = 0

        if status == 200 and (not items):
            # no more data
            break

        if total is not None and (skip + PAGE_SIZE) >= total:
            # reached or passed last page according to server
            break

        skip += PAGE_SIZE

    return pages


def analyze_pagination_completeness(pages: List[Dict[str, Any]]):
    print("=== Pagination completeness ===\n")
    suspicious_pages = []

    for p in pages:
        if p["status"] != 200:
            continue
        count = p["count"]
        total = p["total"]
        skip = p["skip"]
        if count < PAGE_SIZE and (total is None or skip + PAGE_SIZE < total):
            suspicious_pages.append(p)

    if suspicious_pages:
        print("Pages with fewer items than limit while more data appears to exist:")
        for p in suspicious_pages:
            print(
                f"  skip={p['skip']}, count={p['count']}, total={p['total']}"
            )
        print()
    else:
        print("No obvious incomplete pages relative to limit observed.\n")


def analyze_total_accuracy(pages: List[Dict[str, Any]]):
    print("=== Total count accuracy ===\n")

    totals = [p["total"] for p in pages if p["status"] == 200 and p["total"] is not None]
    if not totals:
        print("No total values reported by API.\n")
        return

    distinct_totals = sorted(set(totals))
    print(f"Reported totals: {distinct_totals}")

    ids = set()
    for p in pages:
        if p["status"] != 200:
            continue
        for m in p["items"]:
            mid = extract_id(m)
            if mid is not None:
                ids.add(mid)

    actual = len(ids)
    print(f"Unique message IDs collected: {actual}")
    print()

    mismatch_found = False
    for t in distinct_totals:
        if t != actual:
            print(f"Mismatch: reported total={t}, collected IDs={actual}")
            mismatch_found = True
    if not mismatch_found:
        print("Reported total matches number of unique collected IDs.\n")
    else:
        print()


def analyze_schema_consistency(pages: List[Dict[str, Any]]):
    print("=== Schema consistency ===\n")

    response_key_sets = set()
    item_key_sets = set()

    for p in pages:
        if p["status"] != 200:
            continue

        try:
            data = {"items": p["items"], "total": p["total"]}
            response_key_sets.add(tuple(sorted(data.keys())))
        except Exception:
            continue

        for m in p["items"]:
            item_key_sets.add(tuple(sorted(m.keys())))

    print("Distinct response-level key sets:")
    for ks in sorted(response_key_sets):
        print("  ", ks)
    print()

    print("Distinct message-level key sets:")
    for ks in sorted(item_key_sets)[:10]:
        print("  ", ks)
    if len(item_key_sets) > 10:
        print(f"  ... {len(item_key_sets) - 10} more variants\n")
    else:
        print()


def analyze_latency_vs_size(pages: List[Dict[str, Any]]):
    print("=== Latency vs response size ===\n")

    samples = [
        (p["skip"], p["elapsed"], p["body_len"])
        for p in pages
        if p["elapsed"] is not None and p["status"] is not None
    ]
    if not samples:
        print("No samples available.\n")
        return

    latencies = [s[1] for s in samples]
    sizes = [s[2] for s in samples]

    avg_lat = mean(latencies)
    std_lat = pstdev(latencies) if len(latencies) > 1 else 0.0

    print(f"Average latency: {avg_lat:.3f}s, std: {std_lat:.3f}s")

    samples_sorted_lat = sorted(samples, key=lambda x: x[1], reverse=True)
    samples_sorted_size = sorted(samples, key=lambda x: x[2], reverse=True)

    print("\nSlowest pages (by latency):")
    for skip, elapsed, body_len in samples_sorted_lat[:5]:
        print(
            f"  skip={skip}, elapsed={elapsed:.3f}s, body_len={body_len}"
        )

    print("\nLargest responses (by body length):")
    for skip, elapsed, body_len in samples_sorted_size[:5]:
        print(
            f"  skip={skip}, body_len={body_len}, elapsed={elapsed:.3f}s"
        )

    print()


def analyze_status_clustering(pages: List[Dict[str, Any]]):
    print("=== HTTP status pattern ===\n")

    by_status = Counter()
    for p in pages:
        by_status[p["status"]] += 1

    for status, count in sorted(by_status.items(), key=lambda x: (str(x[0]), x[1])):
        print(f"  status={status}: {count} page(s)")
    print()

    bad_pages = [p for p in pages if p["status"] not in (200, None)]
    if bad_pages:
        print("Non-200 pages:")
        for p in bad_pages:
            print(
                f"  skip={p['skip']}, status={p['status']}, "
                f"elapsed={p['elapsed']:.3f}s, body={repr(p['body'][:60])}"
            )
        print()
    else:
        print("No non-200 pages observed.\n")


def analyze_boundary_conditions():
    print("=== Boundary condition tests ===\n")
    special_skips = [-100, -1, 0, 10_000, 100_000]
    results = []

    for s in special_skips:
        params = {"skip": s, "limit": PAGE_SIZE}
        start = time.time()
        status = None
        body = None
        try:
            resp = requests.get(
                MESSAGES_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT
            )
            status = resp.status_code
            body = resp.text[:60]
            elapsed = time.time() - start
        except Exception as exc:
            elapsed = time.time() - start
            body = str(exc)

        results.append(
            {
                "skip": s,
                "status": status,
                "elapsed": elapsed,
                "body": body,
            }
        )

    for r in results:
        print(
            f"  skip={r['skip']}, status={r['status']}, "
            f"elapsed={r['elapsed']:.3f}s, body={repr(r['body'])}"
        )
    print()


def analyze_rate_limit_behavior():
    print("=== Rate / throttling probe ===\n")

    same_page_times = []
    same_page_statuses = []

    for _ in range(5):
        start = time.time()
        status = None
        try:
            resp = requests.get(
                MESSAGES_ENDPOINT,
                params={"skip": 0, "limit": PAGE_SIZE},
                timeout=REQUEST_TIMEOUT,
            )
            status = resp.status_code
            elapsed = time.time() - start
        except Exception:
            elapsed = time.time() - start
        same_page_times.append(elapsed)
        same_page_statuses.append(status)

    print("Repeated hits on skip=0:")
    for i, (st, t) in enumerate(zip(same_page_statuses, same_page_times), start=1):
        print(f"  attempt {i}: status={st}, elapsed={t:.3f}s")
    print()

    seq_times = []
    seq_statuses = []

    for k in range(5):
        skip = k * PAGE_SIZE
        start = time.time()
        status = None
        try:
            resp = requests.get(
                MESSAGES_ENDPOINT,
                params={"skip": skip, "limit": PAGE_SIZE},
                timeout=REQUEST_TIMEOUT,
            )
            status = resp.status_code
            elapsed = time.time() - start
        except Exception:
            elapsed = time.time() - start
        seq_times.append(elapsed)
        seq_statuses.append(status)

    print("Sequential small-range pages:")
    for k, (st, t) in enumerate(zip(seq_statuses, seq_times), start=0):
        print(
            f"  skip={k * PAGE_SIZE}: status={st}, elapsed={t:.3f}s"
        )
    print()


def analyze_duplicates(pages: List[Dict[str, Any]]):
    print("=== Duplicate ID analysis ===\n")

    counts = Counter()
    for p in pages:
        if p["status"] != 200:
            continue
        for m in p["items"]:
            mid = extract_id(m)
            if mid:
                counts[mid] += 1

    total_ids = len(counts)
    dup_ids = [mid for mid, cnt in counts.items() if cnt > 1]

    print(f"Total distinct IDs seen: {total_ids}")
    print(f"Number of IDs appearing more than once: {len(dup_ids)}")
    if dup_ids:
        print("Example duplicate IDs:")
        for mid in dup_ids[:10]:
            print(f"  {mid} (seen {counts[mid]} times)")
    print()


def analyze_total_stability():
    print("=== Total stability check (skip=0, limit=1) ===\n")
    totals = []
    statuses = []

    for i in range(5):
        start = time.time()
        status = None
        total = None
        try:
            resp = requests.get(
                MESSAGES_ENDPOINT,
                params={"skip": 0, "limit": 1},
                timeout=REQUEST_TIMEOUT,
            )
            status = resp.status_code
            data = resp.json()
            total = data.get("total")
        except Exception as exc:
            status = None
            total = None
        elapsed = time.time() - start

        totals.append(total)
        statuses.append(status)
        print(
            f"  attempt {i+1}: status={status}, total={total}, elapsed={elapsed:.3f}s"
        )

    distinct_totals = sorted({t for t in totals if t is not None})
    print(f"\nDistinct non-null totals observed: {distinct_totals}\n")


def analyze_problematic_skips(pages: List[Dict[str, Any]]):
    print("=== Recheck problematic skips ===\n")

    bad_skips = sorted({p["skip"] for p in pages if p["status"] not in (200, None)})
    if not bad_skips:
        print("No problematic skips detected in initial probe.\n")
        return

    print(f"Problematic skips from initial probe: {bad_skips}\n")

    for s in bad_skips:
        print(f"Re-testing skip={s}")
        for i in range(5):
            start = time.time()
            status = None
            body_snippet = None
            try:
                resp = requests.get(
                    MESSAGES_ENDPOINT,
                    params={"skip": s, "limit": PAGE_SIZE},
                    timeout=REQUEST_TIMEOUT,
                )
                status = resp.status_code
                body_snippet = resp.text[:80]
            except Exception as exc:
                status = None
                body_snippet = repr(exc)
            elapsed = time.time() - start
            print(
                f"  attempt {i+1}: status={status}, elapsed={elapsed:.3f}s, "
                f"body={repr(body_snippet)}"
            )
            time.sleep(0.3)
        print()


def main():
    print("Probing core pagination pages...\n")
    pages = probe_pages()
    print(f"Pages fetched: {len(pages)}")
    print(
        f"Messages fetched: {sum(p['count'] for p in pages if p['status'] == 200)}\n"
    )

    analyze_pagination_completeness(pages)
    analyze_total_accuracy(pages)
    analyze_schema_consistency(pages)
    analyze_latency_vs_size(pages)
    analyze_status_clustering(pages)
    analyze_duplicates(pages)
    analyze_boundary_conditions()
    analyze_rate_limit_behavior()
    analyze_total_stability()
    analyze_problematic_skips(pages)


if __name__ == "__main__":
    main()
