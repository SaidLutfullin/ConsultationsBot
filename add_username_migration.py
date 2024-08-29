from sqlalchemy.sql import text
from config import BASE_NAME
from sqlalchemy import create_engine

def add_username():
    engine = create_engine(BASE_NAME, echo=True)
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE user ADD COLUMN username VARCHAR(255)"))

if __name__ == "__main__":
    add_username()