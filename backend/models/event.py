from pydantic import BaseModel
from typing import Optional, List

class EventExtraction(BaseModel):
    is_event: bool
    title: Optional[str] = None
    start_time: Optional[str] = None  # ISO format
    end_time: Optional[str] = None    # ISO format
    location: Optional[str] = None
    description: Optional[str] = None
    sentiment: str
    importance_score: int  # 0-10
    reasoning: str
    is_academic: bool

class ProcessedEmail(BaseModel):
    id: str
    threadId: str
    subject: str
    from_email: str
    body_snippet: str
    extraction: Optional[EventExtraction] = None
    status: str # 'added', 'skipped', 'pending'
