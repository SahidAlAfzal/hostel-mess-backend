import firebase_admin
from firebase_admin import credentials, messaging
import os
from .database import get_db_connection

cred_path = "/etc/secrets/firebase-credentials.json"

# Initialize Firebase Admin only once
if not firebase_admin._apps:
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized successfully.")
    else:
        print("WARNING: Firebase credentials not found at", cred_path)


def send_notification_to_all(title, body, data=None):
    """
    Sends an FCM notification to all device tokens stored in the database.
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as c:  # type: ignore
            # Assuming you have a 'user_tokens' table storing FCM tokens
            c.execute("SELECT fcm_token FROM user_tokens WHERE fcm_token IS NOT NULL;")
            tokens = [row[0] for row in c.fetchall()]
    except Exception as e:
        print(f" Error fetching tokens: {e}")
        return

    if not tokens:
        print(" No FCM tokens found in database.")
        return

    messages = []
    for token in tokens:
        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=token,
            data=data or {}
        )
        messages.append(msg)

    success_count = 0
    failure_count = 0

    for msg in messages:
        try:
            messaging.send(msg)
            success_count += 1
        except Exception as e:
            failure_count += 1
            print(f" Failed for {msg.token}: {e}")

    print(f" FCM Summary: {success_count} success, {failure_count} failed.")