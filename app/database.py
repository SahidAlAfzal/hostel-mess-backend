import psycopg2 # type: ignore
from psycopg2.pool import SimpleConnectionPool # type: ignore
from psycopg2.extras import RealDictCursor # type: ignore
import time


DB_NAME = "hosteldb"
DB_USER = "postgres"
DB_HOST = "localhost"
DB_PASSWORD = "1234"

dsn = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST}"


#create a pool
pool = SimpleConnectionPool(minconn=1,maxconn=60,dsn=dsn)



#establish connection
def get_db_connection():
    conn = None
    try:
        conn = pool.getconn()
        # RealDictCursor makes the database return a dictionary-like object
        conn.cursor_factory = RealDictCursor
        yield conn
    finally:
        if conn:
            pool.putconn(conn)

