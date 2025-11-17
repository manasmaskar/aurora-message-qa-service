# config.py
'''
Configuration file for the model, grouped for clarity and easier iterative development which will be done in updates.
'''


MESSAGES_API_BASE_URL = "https://november7-730026606190.europe-west1.run.app"
MESSAGES_ENDPOINT = f"{MESSAGES_API_BASE_URL}/messages/"

CACHE_TTL_SECONDS = 300
MAX_MESSAGES_TO_CACHE = 5000
MAX_MESSAGES_TO_SCAN = 2000
PAGE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 2.0

STOPWORDS = {
    "what", "when", "where", "who", "why", "how", "many",
    "does", "do", "did", "is", "are", "was", "were",
    "the", "a", "an", "to", "of", "for", "about", "on", "in",
    "message", "messages", "say", "said", "talk", "talked",
    "favorite", "favourite", "prefer", "preference",
}

# Improve the qa logic for questions to handle unseen messages, where, location and other clauses enhancements.
EXTRA_STOPWORDS = {
    "ever", "has", "have", "will", "would", "can", "could", "should",
}

LOCAL_STOPWORDS = STOPWORDS | EXTRA_STOPWORDS

# Words that indicate preference-style content
PREFERENCE_WORDS = ["favorite", "favourite", "prefer", "preference"]

# Words that hint the message is about a place / travel / location
LOCATION_HINT_WORDS = {
    "city", "cities", "country", "countries",
    "travel", "travelling", "traveling", "trip", "trips",
    "visit", "visiting", "visited",
    "move", "moving", "live", "living", "stay", "staying",
    "hotel", "resort", "retreat", "beach", "mountain", "mountains",
    "maldives", "paris", "london",
}