import psycopg2
from psycopg2.pool import SimpleConnectionPool
import os

# Supabase gives you DATABASE_URL (set it in Render's environment variables)
DATABASE_URL = os.getenv("DATABASE_URL")


if not DATABASE_URL:
    # fallback for local dev if DATABASE_URL not set
    DB_NAME = os.getenv("DB_NAME", "hosteldb")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"

if not DATABASE_URL:
    raise Exception("DATABASE_URL environment variable not set!")

# Create connection pool
pool = SimpleConnectionPool(minconn=1, maxconn=15, dsn=DATABASE_URL)
print("Database connection pool created.")

def get_db_connection():
    conn = None
    try:
        conn = pool.getconn()
        yield conn
    finally:
        if conn:
            pool.putconn(conn)