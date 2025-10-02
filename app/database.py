import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
import os

# Read the DATABASE_URL from environment variables for deployment.
DATABASE_URL = os.getenv("DATABASE_URL")

# If the DATABASE_URL is not set (e.g., when running locally),
# build it from individual parts as a fallback.
if DATABASE_URL is None:
    print("DATABASE_URL not found, falling back to local development settings.")
    DB_NAME = os.getenv("DB_NAME", "hosteldb")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "yourpassword") # Replace with your local password
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DATABASE_URL = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create the connection pool directly when the application starts.
# If the database is cold, this is the point where the deployment might fail.
pool = SimpleConnectionPool(minconn=1, maxconn=20, dsn=DATABASE_URL)
print("Database connection pool created.")

# This is the standard function to get a connection for each API request.
def get_db_connection():
    conn = None
    try:
        # Get a connection from the pool.
        conn = pool.getconn()
        conn.cursor_factory = RealDictCursor
        # Yield the connection to the endpoint.
        yield conn
    finally:
        # This block always runs, ensuring the connection is returned to the pool.
        if conn:
            pool.putconn(conn)

