# Question Answering(QA) Service

A deterministic question-answering service built on top of the Public Messages API.  
This version unifies the simple baseline from **v1.0.0** with the advanced intent, ranking, and reliability improvements of **v1.1.0** into one polished and production-ready.

---

# Overview

This service answers natural-language questions about “members” by analyzing their messages from the public Aurora `/messages` API.  
It is designed to be:

- **Deterministic** (no ML, no NLP libraries)
- **Explainable**
- **Robust against upstream API inconsistencies**
- **Fast and lightweight**

The system is built with **FastAPI** and organized into:

1. **MessageStore** – Loads, paginates, deduplicates, and caches messages.  
2. **QA Logic** – Performs rule-based intent detection, name mapping, keyword scoring, and answer generation.  
3. **`/ask` Endpoint** – Exposes a clean interface:  
   ```json
   { "answer": "…" }
   ```

---

# Features (v1.1.0 Additions)

### 1. Rule-Based Intent Detection (Fully Deterministic)
Supports 12 distinct intent types:

- COUNT (“how many…”)
- WHEN / time
- WHERE / location
- FAVORITE / preference
- BOOLEAN yes/no
- LIST / which, enumerate
- WHAT_DOING (“what is X doing / working on / planning”)
- WHAT DID X SAY ABOUT Y
- OPINION / thoughts / feelings
- HISTORY / EVER / DURATION
- GENERIC fallback

This is **pure Python logic**, no NLP libraries.

---

### 2. Name Normalization Layer
Supports:
- First-name matching  
- Last-name matching  
- Full-name priority  
- Lowercase normalization  
- Protection against merging people with same first name  

Examples:  
“Vikram” → “Vikram Desai”  
“Desai” → “Vikram Desai”

---

### 3. Recency-Weighted Retrieval + Keyword Scoring
Ranking is based on:

- Keyword overlap  
- Recency boost  
- Name-match bonus  
- Intent-specific scoring rules  
- Deduplication and pagination safeguards  

---

### 4. Intent-Aware Answer Formatting
Each intent produces a structured answer:

- **Count** → numeric summary  
- **When** → timestamp extraction  
- **Where** → location phrase extraction  
- **Boolean** → yes/no/inconclusive  
- **List** → multi-item messages  
- **What Doing** → activity messages  
- **Opinion** → sentiment or expressed view  
- **History** → earliest relevant message  
- **Generic** → fallback best match  

---

# API Reliability Observations

Using the diagnostics suite:

- API reports **total = 3349**
- Only **3249 unique messages** are retrievable
- **0 duplicate IDs**
- Intermittent **404**, **401**, and occasional timeouts observed
- Some pagination windows are unstable

**Handling Strategy:**
- Retry unstable pages  
- Deduplicate by ID  
- Treat reported total as an approximate upper bound  
- Gracefully degrade when data cannot be fetched  

---

# Architecture

```text
.
├── app/
│   ├── config.py          # Upstream API config, constants, stopwords
│   ├── main.py            # FastAPI app entrypoint and /ask route
│   ├── message_store.py   # MessageStore: pagination, caching, retry logic
│   ├── models.py          # Pydantic models for requests/responses
│   └── qa_logic.py        # Intent detection, ranking, answer construction
│
├── analysis_bonus/
│   └── analysis_api_suite.py   # API diagnostics and reliability tests (probe for pagination, totals, etc.)
│
├── tests/
│   ├── test_name_logic.py  # Tests for name normalization and intent/name logic
│   └── test.py             # Additional unit tests / smoke tests
│
├── Design_Notes.md
├── README.md
├── requirements.txt
└── .gitignore
```

### Processing Flow

```text
User Question
   ↓
Intent Detection
   ↓
Name Normalization
   ↓
Keyword Extraction
   ↓
Paginated Message Retrieval (with caching)
   ↓
Recency-Weighted Ranking
   ↓
Intent-Aware Answer Formatting
   ↓
Final Answer
```

---

# How to Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the service
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Open interactive docs
```
http://localhost:8000/docs
```

---

# API Contract

### POST `/ask`

**Request**
```json
{
  "question": "When is Layla planning her trip to London?"
}
```

**Response**
```json
{
  "answer": "Layla said: "I am planning my trip to London next Monday!""
}
```

---

# Example Inputs & Outputs

## 1. Time Question
```json
{ "question": "When is Layla planning her trip to London?" }
```
```json
{"answer": "Layla said: "I am planning my trip to London next Monday!""}
```

## 2. Count Question
```json
{ "question": "How many cars does Vikram Desai have?" }
```
```json
{"answer": "Vikram Desai mentioned a count in this message: "I have three cars parked at my place now.""}
```

## 3. Preference Question
```json
{ "question": "What are Amira’s favourite restaurants?" }
```
```json
{"answer": "Amira said: "My favorite restaurants are the Italian place downtown and Kyoto Sushi.""}
```

## 4. Generic Question
```json
{ "question": "What has Vikram been talking about this week?" }
```
```json
{"answer": "Vikram said: "I’ve been working on my new project this entire week.""}
```

---

# Version History

### **v1.1.0 – Enhanced QA, Retrieval, and Stability**
- Added full rule-based intent classifier  
- Added name normalization  
- Added recency-weighted ranking  
- Added intent-aware answer formatting  
- Added API diagnostics suite  
- Added retries, dedup, and robustness improvements  

### **v1.0.0 – Initial Release**
- Basic `/ask` endpoint  
- Simple keyword matching  
- Basic message pagination  
- Simple extraction logic  
- Factual answer generation  

---

# Future Enhancements
- Multi-message reasoning  
- Confidence estimation  
- Optional FAISS or embedding-based similarity search  
- Entities and relationship extraction  

---

# aurora-message-qa-service
A deterministic FastAPI question-answering service built on top of the public Aurora API.
