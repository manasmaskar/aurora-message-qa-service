# analysis_api_integrity.py
import sys
import time
from datetime import datetime
from typing import Dict, List, Any

import requests

from app.config import MESSAGES_ENDPOINT, PAGE_SIZE

REQUEST_TIMEOUT = 5.0
MAX_FAILURES = 5
MAX_TOTAL = 15000


def parse_ts(raw):
    if not raw:
        return None
    t = raw.strip()
    try:
        return datetime.fromisoformat(t)
    except ValueError:
        if t.endswith("Z"):
            try:
                return datetime.fromisoformat(t.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None


def extract_id(msg):
    return msg.get("id") or msg.get("message_id")


def extract_ts(msg):
    return parse_ts(msg.get("timestamp") or msg.get("created_at") or msg.get("created"))


def fetch_pages():
    pages = []
    skip = 0
    fails = 0

    while True:
        params = {"skip": skip, "limit": PAGE_SIZE}
        start = time.time()

        try:
            resp = requests.get(MESSAGES_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT)
        except Exception as exc:
            print(f"[WARN] Request error at skip={skip}: {exc}", file=sys.stderr)
            fails += 1
            if fails >= MAX_FAILURES:
                break
            skip += PAGE_SIZE
            continue

        elapsed = time.time() - start

        status = resp.status_code
        if status != 200:
            print(f"[WARN] Non-200 at skip={skip}: {status} {resp.text[:60]}", file=sys.stderr)
            fails += 1
            if fails >= MAX_FAILURES:
                break
            skip += PAGE_SIZE
            continue

        fails = 0
        data = resp.json()
        items = data.get("items", [])
        total = data.get("total", None)

        pages.append(
            {
                "skip": skip,
                "count": len(items),
                "status": status,
                "elapsed": elapsed,
                "items": items,
                "total": total,
            }
        )

        if not items:
            break

        if total and skip + PAGE_SIZE >= total:
            break

        skip += PAGE_SIZE

    return pages


def analyze_page_boundaries(pages):
    overlaps = []
    gaps = []
    inconsistent_counts = False
    observed_totals = []

    all_ids = []

    for p in pages:
        ids = [extract_id(m) for m in p["items"] if extract_id(m) is not None]
        all_ids.extend(ids)
        if p["total"] is not None:
            observed_totals.append(p["total"])

    if observed_totals and len(set(observed_totals)) > 1:
        inconsistent_counts = True

    sorted_ids = [i for i in sorted(all_ids) if isinstance(i, int)]

    for i in range(1, len(sorted_ids)):
        if sorted_ids[i] == sorted_ids[i - 1]:
            overlaps.append(sorted_ids[i])

    for i in range(1, len(sorted_ids)):
        if sorted_ids[i] != sorted_ids[i - 1] + 1:
            gaps.append((sorted_ids[i - 1], sorted_ids[i]))

    return overlaps, gaps, inconsistent_counts


def analyze_slow_pages(pages):
    slow = [p for p in pages if p["elapsed"] > 1.0]
    return slow


def analyze_failures(pages):
    failures = [p for p in pages if p["status"] != 200]
    return failures


def analyze_timestamp_order(pages):
    ts_list = []
    for p in pages:
        for m in p["items"]:
            ts = extract_ts(m)
            if ts:
                ts_list.append(ts)

    ts_list_sorted = sorted(ts_list)

    anomalies = []
    for a, b in zip(ts_list_sorted, ts_list_sorted[1:]):
        if b < a:
            anomalies.append((a, b))

    return anomalies


def print_report(pages, overlaps, gaps, inconsistent_counts, slow_pages, ts_anomalies):
    total_msgs = sum(len(p["items"]) for p in pages)
    print("\n=== API Integrity Report ===\n")
    print(f"Pages fetched: {len(pages)}")
    print(f"Messages fetched: {total_msgs}\n")

    print(f"Inconsistent total counts reported: {inconsistent_counts}")
    print(f"Page overlaps: {len(overlaps)}")
    print(f"ID gaps: {len(gaps)}")
    print(f"Slow pages (>1s): {len(slow_pages)}")
    print(f"Timestamp ordering anomalies: {len(ts_anomalies)}\n")

    if slow_pages:
        print("Examples of slow pages:")
        for p in slow_pages[:3]:
            print(f"  skip={p['skip']} elapsed={p['elapsed']:.3f}s")
        print()

    if overlaps:
        print("Sample overlaps:")
        print(overlaps[:10])
        print()

    if gaps:
        print("Sample gaps:")
        print(gaps[:10])
        print()

    if ts_anomalies:
        print("Timestamp anomalies (out of order):")
        print(ts_anomalies[:5])
        print()


def main():
    pages = fetch_pages()

    overlaps, gaps, inconsistent = analyze_page_boundaries(pages)
    slow = analyze_slow_pages(pages)
    ts_anom = analyze_timestamp_order(pages)

    print_report(pages, overlaps, gaps, inconsistent, slow, ts_anom)


if __name__ == "__main__":
    main()
