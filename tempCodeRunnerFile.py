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

    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """)

    print(cursor.fetchall())

    conn.commit()
    cursor.close()
    conn.close()

    print("Database initialized successfully.")

init_db()