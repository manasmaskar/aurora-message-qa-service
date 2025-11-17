# qa_logic.py

'''
Heuristical approach to question answering mechanism to avoid NLP!!
'''

from typing import List, Dict, Any
import re
import time

from .models import Message
from .config import (STOPWORDS, 
                    MAX_MESSAGES_TO_SCAN,  
                    LOCAL_STOPWORDS, 
                    PREFERENCE_WORDS, 
                    LOCATION_HINT_WORDS)


def _detect_question_type(question:str) -> str:
    '''
    Pure rule based intent detection.
    Priority Rule implementation, 
        a. Count>when>favorite>where>boolean>what_doing>list_which>what_say>opinion>history>generic
    '''

    q = question.lower().strip()
    padded = f" {q}"

    # For Count
    if "how many" in q:
        return "count"
    
    # For Time
    if (
        q.startswith("when ")
        or " when " in padded
        or " what time " in q
        or " what day " in q
        or " which day " in q
        or " since when " in q
    ):
        return "when"
    
    # For Favorite/Preference
    if any(word in q for word in ["favorite", "favourite", "prefer", "preference"]):
        return "favorite"
    
    # For Where (Location specifically)
    if (
        q.startswith("where ")
        or " where " in padded
        or " which city " in q
        or " which place " in q
        or " which country " in q
        or " which location " in q
        or " which locations " in  q
    ):
        return "where"
    
    # For Boolean
    if q.endswith("?"):
        tokens = q.split()
        if tokens:
            first = tokens[0]
            if first in {
                "is", "are", "do", "does", "did",
                "has", "have", "was", "were",
                "can", "could", "will", "would", "should",
            }:
                return "boolean"
            
    # For what doing, more precisely any activity or anything a member wants to do when they visit the place or similar message queries.

    if re.search(r"\bwhat is\b.*\b(doing|working on|working|planning|up to)\b", q):
        return "what_doing"
    if re.search(r"\bwhat's\b.*\b(doing|working on|planning|up to)\b", q):
        return "what_doing"
    
    # For list, example " List all the places Layla wants to visit while being in London"
    if "list all " in q or "show all " in q:
        return "list_which"
    if " which " in padded or q.startswith("which "):
        return "list_which" # This covered in for which case handling. 
    
    # For revisiting a conversation, Example --> "What did X say about visiting Y place?"
    if (
        "what did" in q and " say " in padded and " about " in padded
    ) or (
        "what has" in q and " said " in padded and " about " in padded
    ):
        return "what_say"
    
    # Handling messages before suggesting to a member Example --> What does X member think about this 
    if any(word in q for word in ["think", "feels", "feel", "feeling", "opinion"]):
        return "opinion"

    # Handling previous behavior or the experience of what the member has said. 
    if (
        "when did" in q 
        or "since when" in q
        or "how long" in q 
        or ("has " in q and " ever " in q)
    ):
        return "history"
    
    # In case some random question is asked how to handle it gracefully. 
    return "generic"

def _extract_member_name(question: str, user_name: List[str]) -> str | None:

    '''
    Earlier version of this function was handling all the names as new entity, example -->
    "John" and "John Doe" may or may not be similar people who are being referred which might give false answers. 
    So  the new logic is giving priority to few criteria and they are as follow -->
    1. Exact full-name match (case-insensitive, substring).
    2. Unique first-name match.
       (only if that first name maps to exactly one member).
    3. If multiple candidates share the same first name, return None
       to avoid accidental merges.
    '''
    q_low = question.lower()

    # 1) Full-name substring matches
    full_matches: list[str] = [
        name for name in user_name
        if name and name.lower() in q_low
    ]
    if len(full_matches) == 1:
        return full_matches[0]
    elif len(full_matches) > 1:
        # Prefer the longest / most specific full name
        return max(full_matches, key=len)

    # Build first-name and last-name indices
    first_name_index: dict[str, list[str]] = {}
    last_name_index: dict[str, list[str]] = {}

    for name in user_name:
        if not name:
            continue
        parts = name.split()
        if not parts:
            continue

        first = parts[0].strip().lower()
        last = parts[-1].strip().lower()

        if first:
            first_name_index.setdefault(first, []).append(name)
        if last:
            last_name_index.setdefault(last, []).append(name)

    # Tokenize the question
    words = re.findall(r"[a-z0-9]+", q_low)

    # 2) Unique first-name match
    for w in words:
        candidates = first_name_index.get(w)
        if not candidates:
            continue
        if len(candidates) == 1:
            return candidates[0]
        # more than one → ambiguous → skip

    # 3) Unique last-name match (e.g. "Desai")
    for w in words:
        candidates = last_name_index.get(w)
        if not candidates:
            continue
        if len(candidates) == 1:
            return candidates[0]
        # more than one → ambiguous → skip

    return None

def _extract_keywords(question: str, member_name: str | None) -> List[str]:
    q = question.lower()
    if member_name:
        for part in member_name.lower().split():
            q = q.replace(part, " ")

    q = re.sub(r"[^a-z0-9]+", " ", q)
    words = [w for w in q.split() if w and w not in LOCAL_STOPWORDS]


    q = re.sub(r"[^a-z0-9]+", " ", q)
    words = [w for w in q.split() if w and w not in STOPWORDS]

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

    # WHEN (TIME)
    if qtype == "when":
        if member_name:
            return f"{uname} talked about that around {ts}."
        return f"A member talked about that around {ts}."

    # COUNT (reusing previous how_many behavior, keeping backward compatibility)
    if qtype in {"how_many", "count"}:
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

    # FAVORITE / PREFERENCE
        # FAVORITE / PREFERENCE
    if qtype == "favorite":
        topic_keywords = [
            kw for kw in keywords
            if kw not in PREFERENCE_WORDS
        ]

        pref_candidates: list[Message] = []

        for msg in candidates:
            text_l = msg.message.lower()
            if any(word in text_l for word in PREFERENCE_WORDS):
                # If we have a specific topic (e.g. restaurants, crypto, city),
                # require at least one topic keyword overlap to accept this message.
                if topic_keywords:
                    if any(kw in text_l for kw in topic_keywords):
                        pref_candidates.append(msg)
                else:
                    pref_candidates.append(msg)

        if pref_candidates:
            msg = pref_candidates[0]
            if member_name:
                return (
                    f"From what I can see, {msg.user_name} said: \"{msg.message}\". "
                    "That is the clearest preference statement I have on that topic."
                )
            else:
                return (
                    f"One member said: \"{msg.message}\". "
                    "That is the clearest preference statement I have on that topic."
                )

        if member_name:
            return (
                f"I could not find any messages where {member_name} clearly states a favorite or preference "
                "on that topic."
            )
        return "I could not find any messages that clearly state a favorite or preference on that topic."


    

        # WHERE (LOCATION)
    if qtype == "where":
        # Try to prefer messages that actually look like locations / travel / places
        def has_location_hint(text: str) -> bool:
            t = text.lower()
            return any(w in t for w in LOCATION_HINT_WORDS)

        # If current best_msg doesn't look location specific, try to find a better one.
        if not has_location_hint(best_msg.message):
            now_ts = time.time()
            best_loc = None
            best_loc_score = 0
            for msg in candidates:
                if has_location_hint(msg.message):
                    s = _score_message(msg, keywords, now_ts)
                    if s > best_loc_score:
                        best_loc = msg
                        best_loc_score = s
            if best_loc is not None and best_loc_score > 0:
                best_msg = best_loc
                uname = best_msg.user_name
                text = best_msg.message
            else:
                # No messages that look like places at all
                if member_name:
                    return (
                        f"I could not find any messages from {member_name} that clearly say where they are "
                        "or where they are going."
                    )
                return "I could not find any messages that clearly describe a place, city, or country for that question."

        # We have a generic location specific message, just quote it
        if member_name:
            return f"{uname} mentioned this place or location: \"{text}\""
        return f"A member mentioned this place or location: \"{text}\""

    # BOOLEAN, WHAT_DOING, LIST_WHICH, WHAT_SAY, OPINION, HISTORY, GENERIC
    if member_name:
        return f"{uname} said: \"{text}\""
    return f"A member said: \"{text}\""