import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
import os
import time # Import the 'time' module

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    print("DATABASE_URL not found, falling back to local development settings.")
    DB_NAME = os.getenv("DB_NAME", "hosteldb")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "yourpassword") # Replace with your local password
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DATABASE_URL = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- THIS IS THE FIX ---
# A new function to create the pool with retry logic for startup.
def create_pool():
    retries = 5
    delay = 2 # seconds
    for i in range(retries):
        try:
            pool = SimpleConnectionPool(minconn=1, maxconn=20, dsn=DATABASE_URL)
            print("Database connection pool created successfully.")
            return pool
        except psycopg2.OperationalError as e:
            print(f"Initial pool connection attempt {i+1} failed: {e}")
            if i < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("Could not create database pool after multiple retries.")
                raise e

# We now call our resilient function to create the pool.
pool = create_pool()

# This function remains to handle connections for individual requests.
def get_db_connection():
    conn = None
    try:
        conn = pool.getconn() # type: ignore
        conn.cursor_factory = RealDictCursor
        yield conn
    finally:
        if conn:
            pool.putconn(conn) # type: ignore