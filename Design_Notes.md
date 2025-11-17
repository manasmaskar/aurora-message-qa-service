# Design Notes – Question Answer (QA) Service (v1.1.0)

This document provides a complete technical overview of the Question Answering (QA) service, including architecture, component design, reasoning behind implementation choices, and newly added **API integrity analysis findings** based on deep diagnostics conducted against the Aurora `/messages` API.

---

# 1. Architectural Overview

The system architecture is intentionally simple, modular, and deterministic:

```
app/
├── config.py
├── main.py
├── message_store.py
├── models.py
└── qa_logic.py

analysis_bonus/
├── analysis_api_deeper.py
├── analysis_api_integrity.py
├── analysis_bonus_activity.py
├── analysis_duplicates.py
├── analysis_user_fields.py
└── analysis_bonus.py

tests/
├── test.py
└── test_name_logic.py
```

### Core Components

1. **MessageStore**  
   Handles pagination, retries, deduplication, caching, and preprocessing of messages.

2. **QA Logic**  
   Performs intent detection, name normalization, keyword filtering, scoring, and answer construction.

3. **FastAPI Layer**  
   Simple routing and orchestration between request inputs and QA logic.

---

# 2. Component-Level Design

## 2.1 Configuration (`config.py`)

- `PAGE_SIZE = 100`  
- Request timeout = 2.0s  
- Cache TTL = 300s  
- Retry for unstable pages  
- Total messages in API: **reported 3349**, but only **~3249 retrievable**

These values were tuned after running integrity scripts showing inconsistent API behavior.

---

## 2.2 MessageStore (`message_store.py`)

### Responsibilities:
- Safe pagination retrieval
- Deduplication using message UUID
- Automatic retries on:
  - 404
  - 401
  - 405
  - Timeouts
- Caching on in-memory store
- Pre-normalization: grouping by lowercase sender names

### Why?
The Aurora API frequently returns:
- Missing partitions  
- Intermittent timeout errors  
- Inconsistent boundaries  
- Inaccurate total count  

Thus, MessageStore isolates all instability so the QA layer never breaks.

---

## 2.3 Deterministic QA Logic (`qa_logic.py`)

### Intent detection (v1.1.0 expanded)
A rule-based engine (no NLP libraries) supporting:

- COUNT  
- WHEN  
- WHERE  
- FAVORITE  
- BOOLEAN (yes/no)  
- LIST  
- WHAT_DOING  
- WHAT DID X SAY ABOUT Y  
- HISTORY / EVER / DURATION  
- OPINION  
- GENERIC fallback  

### Name normalization
- Lowercase match  
- Partial-first-name  
- Partial-last-name  
- Full-name priority  
- Avoid collisions (e.g., “Layla” vs “Layla K.”)

### Keyword filtering
Stopword removal -- keyword extraction -- candidate message filtering.

### Scoring framework
- Keyword overlap  
- Recency boost  
- Person match boost  
- Intent-specific weighting  
- Penalty for loose matches  

### Intent-specific answer formatting
Each intent has its own curated extraction/formatting pipeline.

---

# 3. Detailed API Integrity & Data Reliability Findings

The following findings come from running six deep-diagnostic tools under `analysis_bonus/`.

---

## 3.1 Pagination Reliability (analysis_api_deeper)

### **Reported total:**  
`3349`

### **Actual retrievable unique messages:**  
`3249`  
→ ~100 messages are **unreachable** on every run.

### **Observed behaviors:**
- Some skip positions **always fail**
- Certain pages intermittently return:
  - 404
  - 405
  - 401  
- Rare 5-second timeouts
- Boundary cases behave logically:
  - skip < 0 -- empty list
  - skip > max -- empty list

### **Interpretation:**  
The Aurora API uses **unstable backend pagination**, likely partitioned storage or sharded data with partial availability.

---

## 3.2 Throttling & Rate Behavior
Repeated hits on the same page:

```
0.157s  
0.162s  
0.163s  
0.167s  
0.245s
```

Sequential pages show similar fluctuations.

No 429 throttling was observed, but **intermittent 404/405** indicates backend instability.

---

## 3.3 Duplicate Detection (analysis_duplicates.py)

- Messages analyzed: **2949**
- Duplicate IDs: **0**
- Duplicate texts: **0**
- Short-window duplicates: **0**

**Conclusion:**  
The message dataset despite missing pages does **not contain duplicates**.

---

## 3.4 User Field Quality (analysis_user_fields.py)

Across 100 sampled messages:

- No missing `user_name`
- No missing `user_id`
- No user_id mapped to multiple names
- No corrupted or symbol-only names

**Conclusion:**  
User identity fields are consistent and clean.

---

## 3.5 Activity Analysis (analysis_bonus_activity.py)

### **Top active users:**
- Vikram Desai — 70 msgs
- Sophia Al-Farsi — 66
- Armand Dupont — 62
- Lily O’Sullivan — 60
- Fatima El-Tahir — 59
- Layla Kawaguchi — 59

### **Global message span:**  
~335–357 days

### **Max inactivity gaps:**  
20–39 days per user

### **Anomalies:**  
- Vikram Desai shows unusually high volume (>= 69.4 vs avg ~60)
- No single-message users  
- No major inactivity gaps

**Conclusion:**  
Chat behavior resembles a long-running, stable group conversation.

---

## 3.6 Naming Pattern Consistency (analysis_bonus.py)

Across 200 sampled messages:

- Distinct normalized names: 10  
- No raw spelling variants  
- No abbreviation conflicts  
- No first-name collisions  
- No inconsistent naming patterns

**Conclusion:**  
Name normalization is simplifying a stable dataset—not correcting corrupted names.

---

# 4. Why `/movies` and `/image` Endpoints Were Excluded

- They do not map to specific users  
- No linkage to `/messages`  
- Including them would require fabricating associations  
- Assessment requirements clearly focus on conversational QA via `/messages` only

Thus, excluding them maintains determinism and integrity.

---

# 5. Limitations

- Ambiguous names cannot always be resolved  
- Some relevant messages may lie within unretrievable API partitions  
- Intent classification is rule-based, not semantic  
- No embeddings or LLM reasoning (intentionally constrained)  

---

# 6. Future Work

- Multi-message summarization  
- Confidence scoring  
- More comprehensive testing  
- Optional vector search layer  
- Improved ambiguity handling  
- Enhanced observability (trace logs, metrics)

---

# 7. Summary

Version **1.1.0** significantly improves reliability and accuracy by adding:

- Expanded deterministic intent engine  
- Advanced name normalization  
- Intent-aware ranking & formatting  
- Defenses against unstable API behaviors  
- Detailed API integrity analysis  
- Stronger caching & retry logic  

Despite upstream issues, the system remains:

 - Deterministic  
 - Explainable  
 - Stable  
 - Aligned with assessment requirements  

