import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor # Import this helper
import os
import time

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
pool = SimpleConnectionPool(minconn=1, maxconn=20, dsn=DATABASE_URL)
print("Database connection pool created.")


# --- THIS IS THE RESILIENT FUNCTION ---
def get_db_connection():
    """
    Gets a connection from the pool. Includes a retry mechanism to handle
    database cold starts and abrupt connection closures on free-tier services.
    """
    retries = 3
    delay = 1 # seconds
    for i in range(retries):
        try:
            conn = pool.getconn()
            conn.cursor_factory = RealDictCursor
            try:
                # Yield the connection to the endpoint
                yield conn
            finally:
                # This block always runs, ensuring the connection is returned to the pool
                pool.putconn(conn)
            # If we get here, the connection was successful and returned, so we exit the function
            return
        
        except psycopg2.Error as e: # Catching a broader range of psycopg2 errors
            print(f"Database connection attempt {i + 1} of {retries} failed: {e}")
            if i < retries - 1:
                print(f"Database might be waking up. Retrying in {delay} second(s)...")
                time.sleep(delay)
            else:
                # If we're out of retries, raise the final exception
                print("Database connection failed after multiple retries.")
                raise e

