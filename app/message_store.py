# message_store.py

'''
Message store is used to fetch and cache member messages from upstream API.
'''
from typing import List, Dict, Any
from threading import Lock
import time
import requests
from fastapi import HTTPException

from .config import (
    MESSAGES_ENDPOINT,
    CACHE_TTL_SECONDS,
    MAX_MESSAGES_TO_CACHE,
    PAGE_SIZE,
    REQUEST_TIMEOUT_SECONDS,
    MAX_MESSAGES_TO_SCAN,
)
from .models import Message, PaginatedMessages


class MessageStore:
    def __init__(self) -> None:
        self._messages: List[Message] = []
        self._messages_by_user: Dict[str, List[Message]] = {}
        self._user_names: List[str] = []
        self._last_refresh_ts: float = 0.0
        self._lock = Lock()

    def ensure_fresh(self) -> None:
        now = time.time()
        if now - self._last_refresh_ts < CACHE_TTL_SECONDS:
            return

        with self._lock:
            now = time.time()
            if now - self._last_refresh_ts < CACHE_TTL_SECONDS:
                return
            self._refresh_from_remote()

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "messages": self._messages,
            "messages_by_user": self._messages_by_user,
            "user_names": self._user_names,
        }

    def _refresh_from_remote(self) -> None:
        all_messages: List[Message] = []
        skip = 0

        while len(all_messages) < MAX_MESSAGES_TO_CACHE:
            params = {"skip": skip, "limit": PAGE_SIZE}

            try:
                print(f"[DEBUG] Fetching: {MESSAGES_ENDPOINT} with skip={skip}, limit={PAGE_SIZE}")
                resp = requests.get(
                    MESSAGES_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT_SECONDS
                )
            except requests.RequestException as e:
                print("[DEBUG] RequestException while fetching messages:", repr(e))
                if all_messages:
                    break
                if not self._messages:
                    raise HTTPException(
                        status_code=502,
                        detail="Failed to fetch messages from upstream service.",
                    )
                return

            if resp.status_code != 200:
                print("[DEBUG] Unexpected status from upstream:", resp.status_code, resp.text[:200])
                if all_messages:
                    break
                if not self._messages:
                    raise HTTPException(
                        status_code=502,
                        detail="Failed to fetch messages from upstream service.",
                    )
                return

            data = PaginatedMessages(**resp.json())
            if not data.items:
                break

            all_messages.extend(data.items)

            if len(all_messages) >= data.total:
                break

            skip += PAGE_SIZE

        if not all_messages:
            if not self._messages:
                raise HTTPException(
                    status_code=502,
                    detail="Failed to load any member messages from upstream service.",
                )
            return

        all_messages = all_messages[:MAX_MESSAGES_TO_CACHE]
        all_messages.sort(key=lambda m: m.timestamp, reverse=True)

        messages_by_user: Dict[str, List[Message]] = {}
        for msg in all_messages:
            key = msg.user_name.strip().lower()
            messages_by_user.setdefault(key, []).append(msg)
        user_names = sorted({m.user_name for m in all_messages})

        self._messages = all_messages
        self._messages_by_user = messages_by_user
        self._user_names = user_names
        self._last_refresh_ts = time.time()

        print(f"[MessageStore] Loaded {len(self._messages)} messages into cache.") 


store = MessageStore()
