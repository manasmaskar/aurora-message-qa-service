# analysis_duplicates.py
import sys
from datetime import datetime
from typing import Dict, List, Any

import requests

from app.config import MESSAGES_ENDPOINT, PAGE_SIZE

LOCAL_REQUEST_TIMEOUT = 5.0
MAX_FAILURES = 5          # allow 5 consecutive “Oops!” pages
MAX_TOTAL = 10000         # hard max just to be safe


def fetch_all_messages(limit: int = MAX_TOTAL) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    skip = 0
    failures = 0

    while len(messages) < limit:
        params = {"skip": skip, "limit": PAGE_SIZE}

        try:
            resp = requests.get(
                MESSAGES_ENDPOINT,
                params=params,
                timeout=LOCAL_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            print(f"[WARN] Request error at skip={skip}: {exc}", file=sys.stderr)
            failures += 1
            if failures >= MAX_FAILURES:
                break
            skip += PAGE_SIZE
            continue

        if resp.status_code != 200:
            print(
                f"[WARN] Non-200 at skip={skip}: {resp.status_code} {resp.text[:60]}",
                file=sys.stderr,
            )
            failures += 1
            if failures >= MAX_FAILURES:
                break
            skip += PAGE_SIZE
            continue

        failures = 0  # reset failures because we got a good page

        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        messages.extend(items)

        # if API gives a “total”, use it to avoid unnecessary fetches
        total = data.get("total", None)
        if isinstance(total, int) and len(messages) >= total:
            break

        skip += PAGE_SIZE

    return messages[:limit]


def parse_timestamp(raw: str) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        if text.endswith("Z"):
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None


def extract_id(msg: Dict[str, Any]) -> Any:
    return msg.get("id") or msg.get("message_id")


def extract_text(msg: Dict[str, Any]) -> str:
    if msg.get("text"):
        return str(msg["text"])
    if msg.get("message"):
        return str(msg["message"])
    return ""


def extract_timestamp(msg: Dict[str, Any]) -> datetime | None:
    return parse_timestamp(
        msg.get("timestamp") or msg.get("created_at") or msg.get("created")
    )


def analyze_duplicates(messages: List[Dict[str, Any]]):
    id_map: Dict[Any, List[Dict[str, Any]]] = {}
    text_map: Dict[str, List[Dict[str, Any]]] = {}

    for msg in messages:
        mid = extract_id(msg)
        txt = extract_text(msg).strip()
        ts = extract_timestamp(msg)

        if mid is not None:
            id_map.setdefault(mid, []).append(msg)

        if txt:
            text_map.setdefault(txt, []).append({"msg": msg, "timestamp": ts})

    duplicate_ids = {mid: lst for mid, lst in id_map.items() if len(lst) > 1}
    duplicate_texts = {txt: lst for txt, lst in text_map.items() if len(lst) > 1}

    # same text repeated within 10 mins
    window = 600
    short_window = {}

    for txt, lst in text_map.items():
        if len(lst) < 2:
            continue

        with_ts = [x for x in lst if x["timestamp"]]
        if len(with_ts) < 2:
            continue

        with_ts.sort(key=lambda x: x["timestamp"])
        hits = []

        for a, b in zip(with_ts, with_ts[1:]):
            delta = (b["timestamp"] - a["timestamp"]).total_seconds()
            if 0 <= delta <= window:
                hits.append(a)
                hits.append(b)

        if hits:
            short_window[txt] = list({h["msg"]["id"]: h for h in hits}.values())

    return duplicate_ids, duplicate_texts, short_window


def print_report(messages, dup_ids, dup_texts, short_window):
    print("=== Duplicate Message Report ===\n")
    print(f"Messages analyzed: {len(messages)}")
    print(f"Duplicate message IDs: {len(dup_ids)}")
    print(f"Duplicate message texts: {len(dup_texts)}")
    print(f"Short-window repeated texts: {len(short_window)}\n")

    if dup_ids:
        print("Examples of duplicate IDs:")
        for mid, lst in list(dup_ids.items())[:5]:
            print(f"  ID {mid}: {len(lst)} occurrences")
        print()

    if dup_texts:
        print("Examples of duplicate texts:")
        for txt, lst in list(dup_texts.items())[:5]:
            print(f'  "{txt[:80]}..." ({len(lst)} occurrences)')
        print()

    if short_window:
        print("Texts repeated within 10 minutes:")
        for txt, lst in list(short_window.items())[:5]:
            print(f'  "{txt[:80]}..." repeated {len(lst)} times close together')
        print()


def main():
    print("Fetching full message dataset…")
    msgs = fetch_all_messages()
    print(f"Loaded {len(msgs)} messages\n")

    dup_ids, dup_texts, short_window = analyze_duplicates(msgs)
    print_report(msgs, dup_ids, dup_texts, short_window)


if __name__ == "__main__":
    main()
