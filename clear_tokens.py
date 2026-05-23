
from backend.models.database import SessionLocal
from backend.models.token import GoogleToken

def clear_tokens():
    db = SessionLocal()
    db.query(GoogleToken).delete()
    db.commit()
    db.close()
    print("Tokens cleared.")

if __name__ == "__main__":
    clear_tokens()
