# analysis_bonus.py
import collections
import sys
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


def normalize_name(raw: str) -> str:
    return " ".join(raw.split()).lower()


def build_name_structures(messages: List[Dict]):
    norm_to_variants: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    first_name_groups: Dict[str, set] = collections.defaultdict(set)
    first_last_initial_groups: Dict[str, set] = collections.defaultdict(set)

    for msg in messages:
        raw_name = (msg.get("user_name") or "").strip()
        if not raw_name:
            continue

        norm = normalize_name(raw_name)
        norm_to_variants[norm][raw_name] += 1

        parts = raw_name.split()
        if not parts:
            continue

        first = parts[0].strip()
        last = parts[-1].strip()

        if first:
            first_key = first.lower()
            first_name_groups[first_key].add(raw_name)

            if last:
                last_initial = last[0].lower()
                key = f"{first_key}_{last_initial}"
                first_last_initial_groups[key].add(raw_name)

    return norm_to_variants, first_name_groups, first_last_initial_groups


def print_inconsistent_variants(norm_to_variants: Dict[str, collections.Counter]) -> int:
    print("=== Name variants by normalized form ===\n")
    count_multi = 0

    for norm, counter in sorted(norm_to_variants.items()):
        variants = list(counter.items())
        if len(variants) <= 1:
            continue

        count_multi += 1
        print(f'Normalized name: "{norm}"')
        for raw, c in sorted(variants, key=lambda x: (-x[1], x[0])):
            print(f'  - "{raw}" ({c} message(s))')
        print()

    if count_multi == 0:
        print("No normalized names with multiple raw spellings found.\n")

    return count_multi


def print_first_name_clusters(first_name_groups: Dict[str, set]) -> int:
    print("=== First-name clusters (possible same person with different full names) ===\n")
    count_clusters = 0

    for first, names in sorted(first_name_groups.items()):
        if len(names) <= 1:
            continue

        count_clusters += 1
        print(f'First name: "{first}"')
        for full in sorted(names):
            print(f"  - {full}")
        print()

    if count_clusters == 0:
        print("No first-name clusters with multiple distinct full-name forms found.\n")

    return count_clusters


def print_first_last_initial_clusters(first_last_initial_groups: Dict[str, set]) -> int:
    print("=== First + last-initial clusters (possible abbreviations vs full last names) ===\n")
    count_clusters = 0

    for key, names in sorted(first_last_initial_groups.items()):
        if len(names) <= 1:
            continue

        count_clusters += 1
        first, initial = key.split("_", 1)
        print(f'First name "{first}", last initial "{initial}":')
        for full in sorted(names):
            print(f"  - {full}")
        print()

    if count_clusters == 0:
        print("No first+last-initial clusters with multiple distinct forms found.\n")

    return count_clusters


def print_summary(
    norm_to_variants: Dict[str, collections.Counter],
    first_name_groups: Dict[str, set],
    first_last_initial_groups: Dict[str, set],
    loaded_count: int,
):
    distinct_norm = len(norm_to_variants)
    multi_variant = sum(1 for v in norm_to_variants.values() if len(v) > 1)
    first_clusters = sum(1 for names in first_name_groups.values() if len(names) > 1)
    first_last_init_clusters = sum(
        1 for names in first_last_initial_groups.values() if len(names) > 1
    )

    print("=== Summary ===")
    print(f"Messages analyzed: {loaded_count}")
    print(f"Distinct normalized names: {distinct_norm}")
    print(f"Names with multiple raw variants: {multi_variant}")
    print(f"First-name clusters with >1 distinct full name: {first_clusters}")
    print(f"First+last-initial clusters with >1 distinct full name: {first_last_init_clusters}")
    if any([multi_variant, first_clusters, first_last_init_clusters]):
        print("Potential inconsistent naming patterns detected above.")
    else:
        print("No inconsistent naming patterns detected in this sample.")


def main():
    print("Running naming analysis against:", MESSAGES_ENDPOINT)
    messages = fetch_all_messages()
    print(f"Loaded {len(messages)} messages\n")

    norm_to_variants, first_name_groups, first_last_initial_groups = build_name_structures(messages)

    print_inconsistent_variants(norm_to_variants)
    print_first_name_clusters(first_name_groups)
    print_first_last_initial_clusters(first_last_initial_groups)
    print_summary(norm_to_variants, first_name_groups, first_last_initial_groups, len(messages))


if __name__ == "__main__":
    main()
