<<<<<<< HEAD
# Question Answering(QA) Service

This project implements a small HTTP service that answers natural-language questions about members, using the `/messages` endpoint from the public Aurora API. The goal of this version is to provide a simple, clear, and deterministic baseline capable of retrieving relevant information from messages and returning short factual answers when possible.

The service is built with FastAPI and consists of three main layers:

1. **MessageStore** – loads, paginates, and caches messages from the upstream Aurora API.  
2. **QA Logic** – performs lightweight intent detection, message filtering, scoring, and answer construction.  
3. **FastAPI `/ask` endpoint** – exposes a simple `{"answer": "…"}` interface for client queries.

## Version History

### v1.0.0
- Initial Release.
- Added message pagination and caching. 
- Implemented lightweight extraction (time counts and preferences).
- Added ranking heuristics and `{/ask}`.
- Included example inputs and outputs below.
---

## How to Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the API 
```bash
uvicorn main:app 
```
Service will run at 
```bash
http://127.0.0.1:8000/ask
```

## API Contract


### POST `/ask`

### Request
```json
{
  "question": "When is Layla planning her trip to London?"
}
```
{"answer": "Layla said: \"I am planning my trip to London next Monday!\""}

### Example Inputs & Outputs
## I. Time Question
```json
{ "question": "When is Layla planning her trip to London?" }
```
{"answer": "Layla said: \"I am planning my trip to London next Monday!\""}

## II. Count Question
```json
{ "question": "How many cars does Vikram Desai have?" }
```
{"answer": "Vikram Desai mentioned a count in this message: \"I have three cars parked at my place now.\""}

## III. Preference Question
```json
{ "question": "What are Amira’s favourite restaurants?" }
```
{answer": "Amira said: \"My favorite restaurants are the Italian place downtown and Kyoto Sushi.\""}

## IV. Generic Question 
```json
{ "question": "What has Vikram been talking about this week?" }
```
{"answer": "Vikram said: \"I’ve been working on my new project this entire week.\""}
=======
# aurora-message-qa-service
A deterministic FastAPI question-answering service built on public API
>>>>>>> 379a90ed547e6d6303c311b933378f5484d97bed
