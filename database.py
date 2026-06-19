import os
import psycopg2

def init_db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT
    )
    """)

    # Problems table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS problems (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        title TEXT,
        difficulty TEXT,
        date TEXT
    )
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("Database initialized successfully.")