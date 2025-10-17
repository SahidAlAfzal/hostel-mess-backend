import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
import os
import time # Import the 'time' module

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found, falling back to local dev.")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "hosteldb")
    DATABASE_URL = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"

# A function to create the pool with retry logic for startup.
def create_pool():
    retries, delay = 5, 2
    for i in range(retries):
        try:
            pool = SimpleConnectionPool(minconn=1, maxconn=40, dsn=DATABASE_URL)
            print("Database connection pool created successfully.")
            return pool
        except psycopg2.OperationalError as e:
            print(f"Initial pool connection attempt {i+1} failed: {e}")
            if i < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("FATAL: Could not create database pool after multiple retries.")
                raise e

pool = create_pool()

# --- FastAPI Dependency with Runtime Retry Logic ---
def get_db_connection():
    """
    FastAPI dependency that yields a database connection from the pool.
    Includes retry logic to handle idle connection timeouts.
    """
    retries = 3
    delay = 1
    for i in range(retries):
        try:
            conn = pool.getconn() # type: ignore
            # Test the connection with a simple query before yielding it
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            
            conn.cursor_factory = RealDictCursor
            try:
                yield conn
                # If we get here, the request was successful, so we break the loop
                break 
            finally:
                pool.putconn(conn) # type: ignore
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            print(f"Database connection error: {e}. Attempt {i+1} of {retries}.")
            if i < retries - 1:
                print(f"Retrying in {delay} second(s)...")
                time.sleep(delay)
            else:
                print("FATAL: Database connection failed after multiple retries.")
                raise e