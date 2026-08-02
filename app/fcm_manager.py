import logging
import os

import firebase_admin
from firebase_admin import credentials, messaging
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from .models import User

logger = logging.getLogger(__name__)

# --- FCM Initialization ---
cred_path = "/etc/secrets/firebase-credentials.json"
_firebase_ready = False

if os.path.exists(cred_path):
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _firebase_ready = True
        logger.info("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        logger.error(f"FATAL: Firebase Admin SDK failed to initialize: {e}")
else:
    logger.warning("Firebase credentials file not found. Push notifications disabled.")


def get_all_user_tokens(db: Session) -> list[str]:
    """
    Fetch all active user tokens using SQLAlchemy ORM.
    Sync/blocking — always call via run_in_threadpool from async code.
    """
    results = db.query(User.push_token).filter(
        User.push_token.isnot(None),
        User.push_token != '',
        User.is_active == True,
        User.is_mess_active == True
    ).all()

    return [row[0] for row in results]


def deactivate_invalid_tokens(db: Session, invalid_tokens: list[str]) -> int:
    """
    Clears push_token for users whose FCM token is no longer valid
    (app uninstalled, token expired/rotated, etc.).
    Sync/blocking — always call via run_in_threadpool from async code.

    NOTE: this commits the transaction itself. If the caller manages its
    own transaction/session lifecycle, remove the db.commit() call here
    and let the caller commit instead.

    Returns the number of rows updated.
    """
    if not invalid_tokens:
        return 0

    updated = db.query(User).filter(
        User.push_token.in_(invalid_tokens)
    ).update({User.push_token: None}, synchronize_session=False)
    db.commit()
    return updated


# --- 1. Broadcast Notification (Broadcast to Everyone) ---
async def send_notification_to_all(db: Session, title: str, body: str) -> dict:
    """
    Used for general announcements (e.g., new notices, updated menus).
    Takes a DB session to query all active tokens.
    """
    if not _firebase_ready:
        logger.error("FCM Error: Firebase app not initialized.")
        return {"success": 0, "failure": 0, "invalid_tokens": []}

    try:
        push_tokens = await run_in_threadpool(get_all_user_tokens, db)
    except Exception as e:
        logger.error(f"Database error fetching tokens: {e}")
        return {"success": 0, "failure": 0, "invalid_tokens": []}

    if not push_tokens:
        logger.info("No user tokens found for broadcast.")
        return {"success": 0, "failure": 0, "invalid_tokens": []}

    result = await send_notification(push_tokens, title, body)

    # Prune any tokens FCM reports as dead so we stop wasting sends on them.
    if result.get("invalid_tokens"):
        try:
            await run_in_threadpool(deactivate_invalid_tokens, db, result["invalid_tokens"])
        except Exception as e:
            logger.error(f"Failed to deactivate invalid tokens: {e}")

    return result


# --- 2. Targeted Notification (Specific User / Device Tokens) ---
async def send_notification(tokens: list[str], title: str, body: str) -> dict:
    """
    Used for individual/targeted alerts (e.g., 'Booking Confirmed').
    Does NOT require a DB session because tokens are passed in directly.

    Returns:
        {
            "success": int,
            "failure": int,
            "invalid_tokens": list[str],  # tokens FCM reports as dead/unregistered
        }
    """
    if not _firebase_ready:
        logger.error("FCM Error: Firebase app not initialized.")
        return {"success": 0, "failure": len(tokens), "invalid_tokens": []}

    if not tokens:
        logger.info("No tokens provided for notification.")
        return {"success": 0, "failure": 0, "invalid_tokens": []}

    MAX_TOKENS_PER_BATCH = 500
    success_count = 0
    failure_count = 0
    invalid_tokens: list[str] = []

    def chunked(iterable, size):
        for i in range(0, len(iterable), size):
            yield iterable[i:i + size]

    for chunk in chunked(tokens, MAX_TOKENS_PER_BATCH):
        try:
            multicast = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                tokens=chunk
            )
            resp = await run_in_threadpool(messaging.send_each_for_multicast, multicast)
            success_count += resp.success_count
            failure_count += resp.failure_count

            for token, single_resp in zip(chunk, resp.responses):
                if not single_resp.success:
                    exc = single_resp.exception
                    logger.warning(f"FCM send failed for token {token}: {exc}")
                    if isinstance(exc, messaging.UnregisteredError):
                        invalid_tokens.append(token)

        except Exception as e:
            # This chunk failed outright (e.g. network/auth error). Count it
            # as failed but keep the results already collected from chunks
            # that succeeded, instead of discarding everything.
            logger.error(f"FCM batch error for a chunk of {len(chunk)} tokens: {e}")
            failure_count += len(chunk)

    logger.info(f"Successfully sent notification to {success_count} users. Failed: {failure_count}")
    return {"success": success_count, "failure": failure_count, "invalid_tokens": invalid_tokens}