from sqlalchemy import Column, String, DateTime, Integer, Boolean, JSON
from .database import Base
import datetime

class ProcessedEmailRecord(Base):
    __tablename__ = "processed_emails"

    id = Column(String, primary_key=True, index=True) # Gmail Message ID
    user_email = Column(String, index=True)
    status = Column(String) # 'added', 'skipped', 'error'
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)
    extraction_data = Column(JSON)
