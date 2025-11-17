# test_questions.py
import requests
from urllib.parse import quote

BASE_URL = "http://127.0.0.1:8000/ask"


TESTS = [
    ("count", "How many trips has Layla mentioned?"),
    ("count", "How many times did Vikram talk about his car?"),
    ("count", "How many cities has Amira talked about?"),
    ("count", "How many times did Layla say when she's travelling?"),
    ("count", "How many times has John mentioned Mars?"),
    ("when", "When is Layla planning her trip to London?"),
    ("when", "When did Vikram mention about buying a car?"),
    ("when", "When is Amira flying to Paris?"),
    ("when", "Since when is Layla talking about moving?"),
    ("when", "When did John say he moved to Mars?"),
    ("favorite", "What are Amira’s favourite restaurants?"),
    ("favorite", "What does Vikram prefer for holidays, beaches or mountains?"),
    ("favorite", "What are city is Layla's favorite to live in?"),
    ("favorite", "What is Layla's favorite cryptocurrency?"),
    ("where", "Where is Layla traveling next month?"),
    ("where", "Where does Vikram live now?"),
    ("where", "Where city is Amira visiting next?"),
    ("where", "Where country is Layla moving to?"),
    ("what_doing", "What is Vikram working on this week?"),
    ("boolean", "Is Vikram traveling this weekend?"),
    ("boolean", "Has AMira mentioned ever sushi?"),
    ("list_which", "Which cities has Layla mentioned visiting?"),
    ("list_which", "List all trips Vikram has talked about?"),
    ("what_say", "What did Layla say about her London trip?"),
    ("opinion", "What does Layla think about Paris?"),
    ("history", "Has Amira ever talked about sushi?"),
    ("generic", "What has Vikram been talking about this week?"),
]

for intent, q in TESTS:
    url = f"{BASE_URL}?question={quote(q)}"
    print(f"\n[{intent}] {q}")
    try:
        resp = requests.get(url, timeout=5)
        print("Status:", resp.status_code)
        print("Response:", resp.text)
    except Exception as e:
        print("Error:", e)
