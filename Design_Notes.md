# Design Notes – Question Answer (QA) Service (Version 1)

This document explains the architectural choices behind Version 1 of the Question Answering Service, the reasoning behind key design decisions, and the known limitations of the current implementation. The goal of this version is simplicity, correctness, and predictable behavior using only the `/messages` endpoint from the public API.

---

## 1. Architectural Overview

The system is organized into three focused modules:

### **1.1 Configuration Rationale (config.py)**
- Inspection of the `/messages` endpoint showed a total of **3349 messages**, which is small enough to store fully in memory.
- Caching the entire dataset reduces repeated API calls and enables all QA logic to operate on a consistent in-memory snapshot.
- `MAX_MESSAGES_TO_CACHE = 5000` is selected as an optimal upper bound, allowing room for dataset expansion while ensuring that a sufficiently large set of messages is retained to capture user context without omitting important information..
- `MAX_MESSAGES_TO_SCAN = 2000` ensures predictable per-request performance by limiting how many messages are scored for each question.
- `PAGE_SIZE = 100` enables efficient pagination when loading the message dataset.
- `CACHE_TTL_SECONDS = 300` refreshes the cache periodically without placing excessive load on the upstream API.
- `REQUEST_TIMEOUT_SECONDS = 2.0` prevents slow or stalled upstream responses from blocking the service.
- These values collectively balance performance, safety, and simplicity for the current data scale.

### **1.1 MessageStore (message_store.py)**
- Responsible for fetching data from the upstream `/messages` API.
- Handles pagination and respects safety caps to avoid excessive load.
- Maintains a TTL-based in-memory cache to ensure fresh but stable data.
- Groups messages by lowercased sender name for easier lookups.
- Provides a clean snapshot to the QA layer, abstracting away network I/O.

This ensures that the QA logic works with a consistent view of all messages, without repeatedly querying the API.

---

### **1.2 QA Logic (qa_logic.py)**
The QA layer is intentionally lightweight and deterministic. It performs:

#### **Intent Detection**
Classifies questions into:
- **Time questions** – “when”, “what time”
- **Count questions** – “how many”
- **Preference questions** – “favorite”, “favourite”, “prefer”, “preference”
- **Generic questions** – fallback when no specific intent is detected

These categories directly match the examples provided in the assignment.

#### **Keyword Extraction**
- Removes common stopwords.
- Extracts meaningful words from the question.
- Used for filtering and scoring messages.

#### **Candidate Message Selection**
- Finds messages containing at least one keyword.
- Reduces the search space before scoring.

#### **Message Scoring**
Messages are scored using:
- **Keyword overlap**  
- **Recency** (newer messages have slightly higher weight)

The top-scoring message becomes the basis of the answer.

#### **Answer Construction**
Depending on intent, answers are formatted to be short, direct, and based on the best matching message.

---

### **1.3 FastAPI Application (main.py)**
- Exposes the `/ask` endpoint.
- On startup, preloads the message cache.
- For each question:
  - Ensures fresh message data.
  - Delegates to the QA logic.
  - Returns a structured `{"answer": "..."}` JSON response.

This layer is intentionally minimal to keep the control flow easy to follow.

### Health and Status Endpoints

- The service provides lightweight `/health` and `/status` endpoints for operational visibility.
- These endpoints allow external systems or deployment environments to verify that the application is running.
- Both endpoints offer simple, non-sensitive responses that confirm service availability and basic readiness.
- This supports integration with health probes, container orchestrators, or monitoring tools without exposing internal logic.

---

## 2. Data Scope and Intentional Exclusions

The Aurora API contains additional endpoints:

- `/movies`
- `/image`

After inspecting these endpoints:

### **Movies**
- Only global movie metadata is available.
- No linkage to any member.
- Cannot answer questions like:  
  *“What movies has Layla watched?”*

### **Images**
- `/image` returns a random image without metadata.
- No member-specific images, profile photos, or anything related.

### Therefore, Version 1 intentionally supports only message-based questions.

Unsupported questions return clear fallback responses rather than misleading answers. This is a deliberate decision to maintain correctness and avoid inventing associations that do not exist in the API.

---

## 3. Limitations (Known & Expected for Version 1)

### **3.1 Member identity is inferred from names**
Since the upstream API exposes only a free-text `sender` field, cannot disambiguate:
- Users with the same name  
- Variations or typos of the same name  

### **3.2 Message scanning is capped**
For performance reasons:
- Only a limited number of cached messages are scanned.
- Very large datasets could hide relevant messages outside this cap.

### **3.3 Heuristic intent detection**
The system handles assignment-related questions well, but:
- Synonyms or unusual phrasing may not match expected patterns.
- Some queries fall back to generic answers.

### **3.4 Unstructured and potentially ambiguous data**
Messages may contain:
- Contradictions  
- Relative dates (e.g., “next Monday”)  
- Partial information  

This version uses a simple “best match” strategy rather than deep reasoning.

### **3.5 Unsupported domains**
Member-specific movie or image questions cannot be answered with the provided API and are intentionally marked as unsupported.

---

## 4. Future Work (Further improvements)


### **4.1 Enhanced Intent Detection**
- Expand synonyms and phrasing patterns.
- Detect more question categories (e.g., “where”, “why”, “what is X about”).

### **4.2 Conflict Resolution Strategies**
- When contradictory messages exist, prefer:
  - Newest messages  
  - Or explicitly mention uncertainty  

### **4.5 Extended API Usage for Non-Member Queries**
- General movie metadata (e.g., “What is the rating of Inception?”).

### **4.6 Proper Logging and Metrics**
Replace simple print statements with structured logs and error metrics.

---

## 5. Summary

Version 1 is intentionally scoped around the `/messages` API and provides a clean, maintainable baseline that answers the primary question types from the assignment. The system is designed to be easy to understand, deterministic, and conservative, returning factual information when available and clear fallbacks when not.

These design choices ensure correctness and transparency while leaving a clear path for future enhancements.
