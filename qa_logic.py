# qa_logic.py

'''
Heuristical approach to question answering mechanism to avoid NLP!!
'''

from typing import List, Dict, Any
import re
import time

from models import Message
from config import STOPWORDS, MAX_MESSAGES_TO_SCAN


def _detect_question_type(question: str) -> str:
    q = question.lower()
    if q.startswith("when") or " when " in q or "what time" in q:
        return "when"
    if "how many" in q:
        return "how_many"
    if "favorite" in q or "favourite" in q or "prefer" in q or "preference" in q:
        return "favorite"
    return "generic"


def _extract_member_name(question: str, user_names: List[str]) -> str | None:
    q = question.lower()
    for name in sorted(user_names, key=len, reverse=True):
        if name.lower() in q:
            return name
    return None


def _extract_keywords(question: str, member_name: str | None) -> List[str]:
    q = question.lower()
    if member_name:
        for part in member_name.lower().split():
            q = q.replace(part, " ")

    q = re.sub(r"[^a-z0-9]+", " ", q)
    words = [w for w in q.split() if w and w not in STOPWORDS]

    seen: set[str] = set()
    keywords: List[str] = []
    for w in words:
        if w not in seen:
            seen.add(w)
            keywords.append(w)
    return keywords


def _candidate_messages(snapshot: Dict[str, Any], member_name: str | None) -> List[Message]:
    messages: List[Message] = snapshot["messages"]
    if member_name:
        key = member_name.strip().lower()
        by_user: Dict[str, List[Message]] = snapshot["messages_by_user"]
        user_msgs = by_user.get(key, [])
        candidates = user_msgs
    else:
        candidates = messages

    return candidates[:MAX_MESSAGES_TO_SCAN]


def _score_message(msg: Message, keywords: List[str], now_ts: float) -> int:
    text = msg.message.lower()
    overlap = sum(1 for kw in keywords if kw and kw in text)
    recency_bonus = 0
    return overlap + recency_bonus


def _best_match_message(
    candidates: List[Message],
    keywords: List[str],
) -> tuple[Message | None, int]:
    if not candidates or not keywords:
        return None, 0

    now_ts = time.time()
    best: Message | None = None
    best_score = 0

    for msg in candidates[:MAX_MESSAGES_TO_SCAN]:
        score = _score_message(msg, keywords, now_ts)
        if score > best_score:
            best = msg
            best_score = score

    return best, best_score


def answer_question(question: str, snapshot: Dict[str, Any]) -> str:
    question_clean = question.strip()
    if not question_clean:
        return "I did not receive a valid question. Please ask something about member messages."

    messages: List[Message] = snapshot["messages"]
    if not messages:
        return "I do not have any member messages available right now, so I cannot answer this yet."

    user_names: List[str] = snapshot["user_names"]

    qtype = _detect_question_type(question_clean)
    member_name = _extract_member_name(question_clean, user_names)
    keywords = _extract_keywords(question_clean, member_name)
    candidates = _candidate_messages(snapshot, member_name)

    if not candidates:
        if member_name:
            return f"I do not have any messages from {member_name}, so I cannot answer this question."
        return "I could not find any relevant messages to answer that question."

    best_msg, score = _best_match_message(candidates, keywords)

    if best_msg is None or (keywords and score == 0):
        if member_name:
            return (
                f"I have messages from {member_name}, but I could not find anything clear that would resolve the question. "
                "I would rather not guess."
            )
        return "I could not find any messages that clearly relate to the question, so I prefer not to guess."

    ts = best_msg.timestamp
    uname = best_msg.user_name
    text = best_msg.message

    if qtype == "when":
        if member_name:
            return f"{uname} talked about that around {ts}."
        return f"A member talked about that around {ts}."

    if qtype == "how_many":
        count = 0
        for msg in candidates:
            mtext = msg.message.lower()
            if any(kw in mtext for kw in keywords):
                count += 1
        if member_name:
            if count == 0:
                return f"I could not find any messages from {member_name} clearly about that."
            return f"{member_name} has talked about that in {count} message(s) that I can see."
        else:
            if count == 0:
                return "I could not find any messages clearly about that."
            return f"I found {count} message(s) related to that topic."

    if qtype == "favorite":
        pref_candidates = [
            msg
            for msg in candidates
            if any(word in msg.message.lower() for word in ["favorite", "favourite", "prefer", "preference"])
        ]
        if pref_candidates:
            msg = pref_candidates[0]
            if member_name:
                return (
                    f"From what I can see, {msg.user_name} said: \"{msg.message}\". "
                    "That is the clearest preference statement I have."
                )
            else:
                return (
                    f"One member said: \"{msg.message}\". "
                    "That is the clearest preference statement I have."
                )
        if member_name:
            return (
                f"I could not find any messages where {member_name} clearly states a favorite or preference "
                "on that topic."
            )
        return "I could not find any messages that clearly state a favorite or preference on that topic."

    if member_name:
        return f"{uname} said: \"{text}\""
    return f"A member said: \"{text}\""
