"""Firebase Auth middleware for StockPulse."""
import os
import json
import time
import threading
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, auth as fb_auth
from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer = HTTPBearer()
_firebase_app = None

# Activity tracking. Firebase's own last_sign_in_timestamp only moves on an
# actual sign-in — a returning user with a live session refreshes their token
# silently and the timestamp never budges. These record real API use instead.
_SESSION_GAP = 1800          # 30 min of silence starts a new "visit"
_last_seen = {}              # uid -> {"at": epoch, "email": str}
_seen_lock = threading.Lock()
# Every authenticated request is logged when LOG_REQUESTS=1. Off by default:
# the picks scan polls /api/picks/status every 15s, which would bury the log.
_LOG_EVERY_REQUEST = os.getenv("LOG_REQUESTS", "").strip() in ("1", "true", "yes")


def _init_firebase():
    global _firebase_app
    if _firebase_app:
        return
    sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    if not sa_json:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON env var not set")
    cred = credentials.Certificate(json.loads(sa_json))
    _firebase_app = firebase_admin.initialize_app(cred)


def _record_activity(uid: str, email: str, method: str, path: str):
    """Log the request, and announce the start of a visit.

    A [visit] line is printed for the first request after 30 min of silence, so
    a normal day's log shows one line per person per session. [auth] lines carry
    every request but only when LOG_REQUESTS=1.
    """
    now = time.time()
    with _seen_lock:
        prev = _last_seen.get(uid)
        _last_seen[uid] = {"at": now, "email": email}
        new_visit = prev is None or (now - prev["at"]) > _SESSION_GAP
    who = email or uid[:8]
    if new_visit:
        print(f"[visit] {who} ({uid[:8]}) active — {method} {path}", flush=True)
    if _LOG_EVERY_REQUEST:
        print(f"[auth] {who} {method} {path}", flush=True)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    """Verify Firebase ID token. Returns the Firebase UID string."""
    _init_firebase()
    try:
        decoded = fb_auth.verify_id_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    uid = decoded["uid"]
    try:
        _record_activity(uid, decoded.get("email") or "", request.method, request.url.path)
    except Exception:
        pass   # never let logging break a request
    return uid


def require_owner(user_id: str = Security(get_current_user)) -> str:
    """Admin guard: only the account named by OWNER_UID may proceed.

    Used for destructive or diagnostic endpoints. If OWNER_UID is not set the
    endpoint is closed to everyone rather than open to everyone — an unset env
    var must never fail open.
    """
    owner_uid = os.getenv("OWNER_UID", "").strip()
    if not owner_uid or user_id != owner_uid:
        raise HTTPException(status_code=403, detail="Admin only")
    return user_id


def _iso(ms):
    """Firebase millisecond timestamp -> ISO8601 UTC, or None."""
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="seconds")


def list_all_users(limit: int = 1000) -> list:
    """Every registered account: who they are, when they joined, when last seen.

    created_at / last_sign_in come from Firebase. last_request comes from this
    process's memory and is null for anyone who has not called the API since the
    last restart — it is the more honest "still using it" signal of the two.
    """
    _init_firebase()
    owner_uid = os.getenv("OWNER_UID", "").strip()
    with _seen_lock:
        seen = dict(_last_seen)
    out = []
    for u in fb_auth.list_users().iterate_all():
        md = u.user_metadata
        activity = seen.get(u.uid)
        out.append({
            "uid": u.uid,
            "email": u.email,
            "name": u.display_name,
            "providers": sorted({p.provider_id for p in (u.provider_data or [])}),
            "is_owner": bool(owner_uid) and u.uid == owner_uid,
            "disabled": u.disabled,
            "created_at": _iso(md.creation_timestamp if md else None),
            "last_sign_in": _iso(md.last_sign_in_timestamp if md else None),
            "last_request": _iso(activity["at"] * 1000) if activity else None,
        })
        if len(out) >= limit:
            break
    out.sort(key=lambda r: r["last_sign_in"] or "", reverse=True)
    return out
