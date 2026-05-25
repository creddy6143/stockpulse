"""Firebase Auth middleware for StockPulse."""
import os
import json

import firebase_admin
from firebase_admin import credentials, auth as fb_auth
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer = HTTPBearer()
_firebase_app = None


def _init_firebase():
    global _firebase_app
    if _firebase_app:
        return
    sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    if not sa_json:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON env var not set")
    cred = credentials.Certificate(json.loads(sa_json))
    _firebase_app = firebase_admin.initialize_app(cred)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    """Verify Firebase ID token. Returns the Firebase UID string."""
    _init_firebase()
    try:
        decoded = fb_auth.verify_id_token(creds.credentials)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
