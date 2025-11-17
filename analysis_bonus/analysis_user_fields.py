# analysis_user_fields.py
import sys
from typing import Dict, List, Any

import requests

from app.config import MESSAGES_ENDPOINT, PAGE_SIZE

LOCAL_REQUEST_TIMEOUT = 5.0
LOCAL_LIMIT = 3000


def fetch_all_messages(limit: int = LOCAL_LIMIT) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    skip = 0

    while len(messages) < limit:
        params = {"skip": skip, "limit": PAGE_SIZE}
        try:
            resp = requests.get(
                MESSAGES_ENDPOINT,
                params=params,
                timeout=LOCAL_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            print(f"Request error while fetching messages: {exc}", file=sys.stderr)
            break

        if resp.status_code in (401, 402, 404):
            print(
                f"Reached boundary of messages (status {resp.status_code}): "
                f"{resp.text[:200]}",
                file=sys.stderr,
            )
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


def is_name_symbols_or_numbers(name: str) -> bool:
    text = name.strip()
    if not text:
        return False
    has_alpha = any(ch.isalpha() for ch in text)
    return not has_alpha


def analyze_user_fields(messages: List[Dict[str, Any]]):
    empty_user_name = []
    null_user_id = []
    id_to_names: Dict[Any, set] = {}
    weird_names = []

    for msg in messages:
        user_name = msg.get("user_name")
        user_id = msg.get("user_id")

        if user_name is None or str(user_name).strip() == "":
            empty_user_name.append(msg)

        if user_id is None or str(user_id).strip() == "":
            null_user_id.append(msg)

        if user_id is not None and str(user_id).strip() != "":
            name_str = "" if user_name is None else str(user_name)
            slot = id_to_names.setdefault(user_id, set())
            slot.add(name_str)

        if isinstance(user_name, str) and is_name_symbols_or_numbers(user_name):
            weird_names.append(msg)

    inconsistent_ids = {
        uid: names for uid, names in id_to_names.items() if len(names) > 1
    }

    return {
        "empty_user_name": empty_user_name,
        "null_user_id": null_user_id,
        "inconsistent_ids": inconsistent_ids,
        "weird_names": weird_names,
    }


def print_user_field_report(messages: List[Dict[str, Any]], report: Dict[str, Any]):
    total = len(messages)
    empty_user_name = report["empty_user_name"]
    null_user_id = report["null_user_id"]
    inconsistent_ids = report["inconsistent_ids"]
    weird_names = report["weird_names"]

    print("=== User field quality report ===\n")
    print(f"Messages analyzed: {total}")
    print(f"Messages with empty or missing user_name: {len(empty_user_name)}")
    print(f"Messages with null or missing user_id: {len(null_user_id)}")
    print(f"User IDs mapped to multiple names: {len(inconsistent_ids)}")
    print(f"Messages with symbol/number-only names: {len(weird_names)}\n")

    if inconsistent_ids:
        print("User IDs with multiple distinct names:")
        for uid, names in inconsistent_ids.items():
            print(f"  user_id={uid}:")
            for n in sorted(names):
                print(f"    - {repr(n)}")
        print()
    else:
        print("No user_id values mapped to multiple names.\n")

    if weird_names:
        print("Examples of names consisting only of symbols or numbers:")
        for msg in weird_names[:10]:
            print(f"  {repr(msg.get('user_name'))}")
        if len(weird_names) > 10:
            print(f"  ... {len(weird_names) - 10} more\n")
        else:
            print()
    else:
        print("No names made only of symbols or numbers found.\n")


def main():
    print("Running user field analysis against:", MESSAGES_ENDPOINT)
    messages = fetch_all_messages()
    print(f"Loaded {len(messages)} messages\n")

    report = analyze_user_fields(messages)
    print_user_field_report(messages, report)


if __name__ == "__main__":
    main()
