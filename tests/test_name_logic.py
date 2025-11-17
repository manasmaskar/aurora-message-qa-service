import requests
from urllib.parse import quote

BASE = "http://127.0.0.1:8000"

TEST_QUESTIONS = [
    "What is Vikram working on?",
    "What is Layla planning?",
    "What did Amira say about Paris?",
    "When did John move to Mars?",
    "What is Desai doing this week?",
    "What is Vikram Desai doing this week?",
]

for q in TEST_QUESTIONS:
    url = f"{BASE}/ask?question={quote(q)}"
    print("\n>>>", q)
    resp = requests.get(url)
    print("Response:", resp.json())
