import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
import os
import time

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found, falling back to local dev.")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "hosteldb")
    DATABASE_URL = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"

# Create the pool with retry logic for startup
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

# FastAPI Dependency - Simplified and Fixed
def get_db_connection():
    """
    FastAPI dependency that yields a database connection from the pool.
    Handles stale connections gracefully.
    """
    conn = None
    try:
        conn = pool.getconn() # type: ignore
        
        # Test if connection is still alive
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            # Connection is stale, close it and get a new one
            print("Stale connection detected, getting fresh connection...")
            pool.putconn(conn, close=True) # type: ignore
            conn = pool.getconn() # type: ignore
            # Test the new connection
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        
        conn.cursor_factory = RealDictCursor
        yield conn
        
    except Exception as e:
        print(f"Database connection error: {e}")
        raise e
    finally:
        # CRITICAL: Always return connection to pool, even on error
        if conn is not None:
            pool.putconn(conn) # type: ignore 


# Optional: Add a cleanup function to close all connections gracefully
def close_pool():
    """Call this on application shutdown"""
    if pool:
        pool.closeall()
        print("Database connection pool closed.")