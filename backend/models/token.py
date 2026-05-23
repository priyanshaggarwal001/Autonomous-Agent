from sqlalchemy import Column, Integer, String, JSON
from .database import Base

class GoogleToken(Base):
    __tablename__ = "google_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, unique=True, index=True)
    token_data = Column(JSON)  # Stores credentials as dict
