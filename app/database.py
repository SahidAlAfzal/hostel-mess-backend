import psycopg2
from psycopg2.pool import SimpleConnectionPool
import os # Import the 'os' module to read environment variables

DB_NAME = os.getenv("DB_NAME", "hosteldb")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234") 
DB_HOST = os.getenv("DB_HOST", "localhost")

# Define the connection string using the variables above
dsn = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST}"

# This part remains the same
pool = SimpleConnectionPool(minconn=1, maxconn=10, dsn=dsn)
print("Database connection pool created.")

def get_db_connection():
    conn = None
    try:
        conn = pool.getconn()
        conn.cursor_factory = psycopg2.extras.RealDictCursor # type: ignore
        yield conn
    finally:
        if conn:
            pool.putconn(conn)


