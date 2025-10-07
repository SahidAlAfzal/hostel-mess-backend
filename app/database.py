import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
import os
import time 

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    print("DATABASE_URL not found, falling back to local development settings.")
    DB_NAME = os.getenv("DB_NAME", "hosteldb")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "1234") # Replace with your local password
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DATABASE_URL = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# A function to create the pool with retry logic for startup.
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
                print("FATAL: Could not create database pool after multiple retries.")
                raise e

#function to create the pool.
pool = create_pool()

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
            conn = pool.getconn() # type: ignore
            conn.cursor_factory = RealDictCursor
            try:
                # Yield the connection to the endpoint
                yield conn
            finally:
                # This block always runs, ensuring the connection is returned to the pool
                pool.putconn(conn) # type: ignore
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