# analysis_activity.py
import sys
from datetime import datetime
from typing import Dict, List

import requests

from app.config import MESSAGES_ENDPOINT, PAGE_SIZE, REQUEST_TIMEOUT_SECONDS


def fetch_all_messages(limit: int = 2000) -> List[Dict]:
    messages: List[Dict] = []
    skip = 0

    while len(messages) < limit:
        params = {"skip": skip, "limit": PAGE_SIZE}
        try:
            resp = requests.get(
                MESSAGES_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            print(f"Request error while fetching messages: {exc}", file=sys.stderr)
            break

        if resp.status_code != 200:
            print(
                f"Unexpected status {resp.status_code} from messages endpoint: "
                f"{resp.text[:200]}",
                file=sys.stderr,
            )
            break

        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        messages.extend(items)

        total = data.get("total", len(messages))
        if len(messages) >= total or len(messages) >= limit:
            break

        skip += PAGE_SIZE

    return messages


def parse_timestamp(raw: str) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        if text.endswith("Z"):
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None


def build_activity_stats(messages: List[Dict]) -> Dict[str, Dict]:
    activity: Dict[str, Dict] = {}

    for msg in messages:
        name = (msg.get("user_name") or "").strip()
        ts_raw = (
            msg.get("timestamp")
            or msg.get("created_at")
            or msg.get("created")
            or ""
        )
        ts = parse_timestamp(ts_raw)

        if not name or ts is None:
            continue

        entry = activity.setdefault(
            name,
            {"count": 0, "timestamps": []},
        )
        entry["count"] += 1
        entry["timestamps"].append(ts)

    for name, entry in activity.items():
        ts_list = sorted(entry["timestamps"])
        entry["timestamps"] = ts_list
        entry["first"] = ts_list[0]
        entry["last"] = ts_list[-1]
        if len(ts_list) > 1:
            max_gap_days = 0.0
            for a, b in zip(ts_list, ts_list[1:]):
                gap_days = (b - a).total_seconds() / 86400.0
                if gap_days > max_gap_days:
                    max_gap_days = gap_days
            entry["max_gap_days"] = max_gap_days
        else:
            entry["max_gap_days"] = 0.0

    return activity


def print_activity_summary(activity: Dict[str, Dict]):
    print("\n=== Activity summary by user ===\n")

    if not activity:
        print("No activity data available.\n")
        return

    rows = []
    for name, entry in activity.items():
        rows.append(
            (
                name,
                entry["count"],
                entry["first"],
                entry["last"],
                entry["max_gap_days"],
            )
        )

    rows.sort(key=lambda r: (-r[1], r[0]))

    for name, count, first, last, max_gap in rows:
        span_days = (last - first).total_seconds() / 86400.0 if first and last else 0.0
        print(
            f"{name}: {count} msg(s), span ~{span_days:.1f} days, "
            f"max inactivity gap ~{max_gap:.1f} days"
        )

    print()
    return rows


def print_activity_anomalies(rows: List[tuple]):
    print("=== Suspected activity anomalies ===\n")

    if not rows:
        print("No rows to analyze.\n")
        return

    counts = [r[1] for r in rows]
    if len(counts) == 1:
        avg_count = counts[0]
        std = 0.0
    else:
        avg_count = sum(counts) / len(counts)
        var = sum((c - avg_count) ** 2 for c in counts) / len(counts)
        std = var ** 0.5

    high_threshold = avg_count + 2 * std if std > 0 else max(counts)
    low_threshold = 1
    big_gap_threshold_days = 60.0

    singles = [r for r in rows if r[1] == low_threshold]
    heavy = [r for r in rows if r[1] >= high_threshold]
    big_gap_users = [r for r in rows if r[4] >= big_gap_threshold_days]

    if singles:
        print("Users with only 1 message:")
        for name, count, first, last, _ in singles:
            print(f"  - {name}: 1 message between {first} and {last}")
        print()
    else:
        print("No single-message users found.\n")

    if heavy:
        print(
            f"Users with unusually high volume (>= {high_threshold:.1f} messages "
            f"vs avg {avg_count:.1f}):"
        )
        for name, count, first, last, _ in heavy:
            print(
                f"  - {name}: {count} messages between {first} and {last}"
            )
        print()
    else:
        print("No unusually high-volume users found.\n")

    if big_gap_users:
        print(
            f"Users with long inactivity gaps (>= {big_gap_threshold_days:.0f} days):"
        )
        for name, count, first, last, max_gap in big_gap_users:
            print(
                f"  - {name}: max gap ~{max_gap:.1f} days "
                f"(overall span {first} to {last}, {count} messages)"
            )
        print()
    else:
        print("No users with large inactivity gaps found.\n")


def main():
    print("Running activity analysis against:", MESSAGES_ENDPOINT)
    messages = fetch_all_messages()
    print(f"Loaded {len(messages)} messages\n")

    activity = build_activity_stats(messages)
    rows = print_activity_summary(activity)
    print_activity_anomalies(rows)


if __name__ == "__main__":
    main()
