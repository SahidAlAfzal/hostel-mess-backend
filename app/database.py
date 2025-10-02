import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
import os
import time

# --- DATABASE_URL Setup ---
# This robustly handles both production (Render) and local environments.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found, falling back to local development settings.")
    # You can set these in your local .env or here as defaults
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "yourpassword") # IMPORTANT: Use your local password here
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "hosteldb")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DATABASE_URL = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Initial Pool Creation with Retry Logic ---
# This function makes your application resilient to database cold starts during deployment.
def create_pool():
    retries, delay = 5, 2
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
                print("FATAL: Could not create database pool after multiple retries.")
                raise e

# Create the pool when the application starts.
pool = create_pool()

# --- FastAPI Dependency for Getting a Connection ---
# This is the correct pattern using 'yield' that works with Depends().
def get_db_connection():
    """
    FastAPI dependency that yields a database connection from the pool.
    """
    conn = None
    try:
        conn = pool.getconn() # type: ignore
        conn.cursor_factory = RealDictCursor
        yield conn
    finally:
        if conn:
            pool.putconn(conn) # type: ignore
    

