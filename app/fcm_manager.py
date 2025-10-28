import firebase_admin
from firebase_admin import credentials, messaging
import os
from . import database # Import the database module to access the pool
from fastapi.concurrency import run_in_threadpool # Import this for async safety

# --- FCM Initialization ---
# This code runs once when the app starts
cred_path = "/etc/secrets/firebase-credentials.json"
if os.path.exists(cred_path):
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        print(f"FATAL: Firebase Admin SDK failed to initialize: {e}")
else:
    print("WARNING: Firebase credentials file not found. Push notifications will be disabled.")


def get_all_user_tokens(conn) -> list[str]:
    """
    Helper function to get all valid push tokens from the database.
    """
    with conn.cursor() as cur:
        # Get tokens from users who are active AND have mess access
        cur.execute("SELECT push_token FROM users WHERE push_token IS NOT NULL AND push_token != '' AND is_active = TRUE AND is_mess_active = TRUE")
        results = cur.fetchall()
        
    return [row['push_token'] for row in results]


async def send_notification_to_all(title: str, body: str):
    """
    The main function we will call to send a notification to all users.
    """
    if not firebase_admin._apps:
        print("FCM Error: Firebase app not initialized. Cannot send notification.")
        return

    conn = None # Initialize conn to None
    try:
        # --- FIX 1: Get connection directly from the pool ---
        # We can't use 'get_db_connection' here, so we access the pool directly.
        conn = database.pool.getconn() # type: ignore
        conn.cursor_factory = database.RealDictCursor # type: ignore
        
        # Run the synchronous database call in a thread pool to avoid blocking
        push_tokens = await run_in_threadpool(get_all_user_tokens, conn)
    except Exception as e:
        print(f"Error getting push tokens from database: {e}")
        return
    finally:
        if conn:
            database.pool.putconn(conn) # type: ignore

    if not push_tokens:
        print("Notification task ran, but no users are registered for notifications.")
        return

    # --- FCM Message ---
    # --- FIX 2: Change from MulticastMessage to a list of Message objects ---
    messages = [
        messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=token,
        )
        for token in push_tokens
    ]


    try:
        # --- FIX 3: Change from send_multicast to send_all ---
        # Run the blocking 'send_all' call in a thread pool
        response = await run_in_threadpool(messaging.send_all, messages) # type: ignore
        print(f'Successfully sent notification to {response.success_count} users.')
    except Exception as e:
        print(f"FATAL: Error sending FCM notifications: {e}")