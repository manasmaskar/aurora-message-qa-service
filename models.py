# models.py

'''
Pydantic models used across the service for type safety and validation.
'''

from pydantic import BaseModel
from typing import List


class Message(BaseModel):
    id: str
    user_id: str
    user_name: str
    timestamp: str
    message: str


class PaginatedMessages(BaseModel):
    total: int
    items: List[Message]


class AskResponse(BaseModel):
    answer: str
