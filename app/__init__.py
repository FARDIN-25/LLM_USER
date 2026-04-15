# app/init_db.py
from app.database import engine, Base
from app import models

def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created")

if __name__ == "__main__":
    init_db()

