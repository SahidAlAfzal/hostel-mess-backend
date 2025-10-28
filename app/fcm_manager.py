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
    This function is run in a threadpool.
    """
    with conn.cursor() as cur:
        # --- FIX: Query the correct table (users) and column (push_token) ---
        cur.execute("SELECT push_token FROM users WHERE push_token IS NOT NULL AND push_token != '' AND is_active = TRUE AND is_mess_active = TRUE")
        results = cur.fetchall()
        
    return [row['push_token'] for row in results]


async def send_notification_to_all(title: str, body: str):
    """
    The main function we will call to send a notification to all users.
    This implementation prefers messaging.send_multicast (with 500-token chunks),
    and falls back to sending one-by-one with messaging.send if send_multicast/send_all
    are not available in the installed firebase_admin version.
    """
    if not firebase_admin._apps:
        print("FCM Error: Firebase app not initialized. Cannot send notification.")
        return

    conn = None # Initialize conn to None
    try:
        # --- FIX: Get connection directly from the pool ---
        conn = database.pool.getconn() # type: ignore
        # --- FIX: Set the cursor factory ---
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

    # FCM limits multicast to 500 tokens per request
    MAX_TOKENS_PER_BATCH = 500

    success_count = 0
    failure_count = 0

    # Chunk tokens and send
    def chunked(iterable, size):
        for i in range(0, len(iterable), size):
            yield iterable[i:i + size]

    try:
        if hasattr(messaging, "send_multicast"):
            # Use send_multicast in chunks of up to 500 tokens
            for chunk in chunked(push_tokens, MAX_TOKENS_PER_BATCH):
                multicast = messaging.MulticastMessage(
                    notification=messaging.Notification(title=title, body=body),
                    tokens=chunk
                )
                resp = await run_in_threadpool(messaging.send_multicast, multicast)
                success_count += getattr(resp, "success_count", 0)
                failure_count += getattr(resp, "failure_count", 0)
                # Log individual failures if present
                for idx, r in enumerate(getattr(resp, "responses", [])):
                    if not getattr(r, "success", False):
                        print(f"Failed for token {chunk[idx]}: {getattr(r, 'exception', None)}")
        else:
            # Fallback: send messages one-by-one
            for chunk in chunked(push_tokens, MAX_TOKENS_PER_BATCH):
                for token in chunk:
                    message = messaging.Message(
                        notification=messaging.Notification(title=title, body=body),
                        token=token
                    )
                    try:
                        await run_in_threadpool(messaging.send, message)
                        success_count += 1
                    except Exception as e:
                        failure_count += 1
                        print(f"Failed for token {token}: {e}")

        print(f"Successfully sent notification to {success_count} users.")
        if failure_count > 0:
            print(f"Failed to send to {failure_count} users.")
    except Exception as e:
        print(f"FATAL: Error sending FCM notifications: {e}")