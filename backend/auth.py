"""
fintech Auth Module
───────────────────
Features:
  • Email + Password Signup / Login
  • Google OAuth 2.0 Login
  • Two-Factor Authentication via Email OTP (6-digit, 10-min expiry)
  • JWT-style tokens (HMAC-SHA256, no external library)
  • SQLite user store  (backend/data/users.db)

Environment variables (create backend/.env or set in shell):
  JWT_SECRET          – random secret string (auto-generated if missing)
  GOOGLE_CLIENT_ID    – from Google Cloud Console
  GOOGLE_CLIENT_SECRET
  GOOGLE_REDIRECT_URI – default: http://localhost:8005/auth/google/callback
  FRONTEND_URL        – default: http://localhost:8080
  EMAIL_USER          – Gmail address used to send OTPs
  EMAIL_PASS          – Gmail App Password (not your normal password)
  EMAIL_HOST          – default: smtp.gmail.com
  EMAIL_PORT          – default: 587
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import random
import re
import secrets
import smtplib
import sqlite3
import time
from datetime import datetime
from enum import Enum
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import requests as _requests
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
import db as db_module

# ─── Config ─────────────────────────────────────────────────────────────────

_BASE_DIR = Path(__file__).resolve().parent
AUTH_DB_PATH = _BASE_DIR.parent / "database" / "users.db"
AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

JWT_SECRET: str = os.getenv(
    "JWT_SECRET", "fintech-secret-" + secrets.token_hex(16)
)
JWT_EXPIRE_SECONDS: int = 7 * 24 * 3600          # 7 days
APP_ENV: str = os.getenv("APP_ENV", "development").strip().lower()

GOOGLE_CLIENT_ID: str     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI: str  = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8005/auth/google/callback"
)

FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8080")

EMAIL_USER: str = os.getenv("EMAIL_USER", "")
EMAIL_PASS: str = os.getenv("EMAIL_PASS", "")
EMAIL_HOST: str = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", "587"))
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")

OTP_EXPIRE_SECONDS: int = 10 * 60   # 10 minutes
OTP_MAX_ATTEMPTS:   int = 5
RATE_LIMIT_WINDOW_SECONDS: int = 15 * 60

if APP_ENV in {"production", "staging"} and JWT_SECRET.startswith("fintech-secret-"):
    raise RuntimeError("JWT_SECRET must be set explicitly in production or staging.")

auth_router = APIRouter(prefix="/auth", tags=["auth"])
_RATE_LIMIT_STORE: dict[str, list[float]] = {}


# ─── Database ────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(AUTH_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT UNIQUE NOT NULL,
                name        TEXT NOT NULL DEFAULT '',
                phone_number TEXT,
                password_hash TEXT,
                provider    TEXT NOT NULL DEFAULT 'manual',
                google_id   TEXT,
                avatar_url  TEXT,
                is_verified INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS otps (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT NOT NULL,
                otp_code    TEXT NOT NULL,
                purpose     TEXT NOT NULL,
                expires_at  REAL NOT NULL,
                attempts    INTEGER NOT NULL DEFAULT 0,
                used        INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );
        """)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "phone_number" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")


_init_db()


# ─── Password hashing (no external lib) ─────────────────────────────────────

def _hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + ":" + key.hex()


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


# ─── JWT-style tokens (HMAC-SHA256, no external lib) ────────────────────────

def _create_token(payload: dict[str, Any]) -> str:
    payload = dict(payload)
    payload["exp"] = time.time() + JWT_EXPIRE_SECONDS
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    sig = hmac.new(JWT_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{sig}"


def _verify_token(token: str) -> dict[str, Any] | None:
    try:
        encoded, sig = token.rsplit(".", 1)
        expected = hmac.new(JWT_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padding = "=" * (4 - len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ─── OTP helpers ─────────────────────────────────────────────────────────────

def _generate_otp() -> str:
    return str(random.SystemRandom().randint(100_000, 999_999))


def _store_otp(email: str, purpose: str) -> str:
    otp = _generate_otp()
    now = datetime.utcnow().isoformat()
    expires_at = time.time() + OTP_EXPIRE_SECONDS
    with _get_conn() as conn:
        # Invalidate previous unused OTPs for same email+purpose
        conn.execute(
            "UPDATE otps SET used=1 WHERE email=? AND purpose=? AND used=0",
            (email, purpose),
        )
        conn.execute(
            "INSERT INTO otps (email, otp_code, purpose, expires_at, created_at) VALUES (?,?,?,?,?)",
            (email, otp, purpose, expires_at, now),
        )
    return otp


def _verify_otp(email: str, otp_code: str, purpose: str) -> bool:
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT id, attempts, expires_at FROM otps
               WHERE email=? AND purpose=? AND used=0
               ORDER BY id DESC LIMIT 1""",
            (email, purpose),
        ).fetchone()
        if not row:
            return False
        if row["expires_at"] < time.time():
            conn.execute("UPDATE otps SET used=1 WHERE id=?", (row["id"],))
            return False
        if row["attempts"] >= OTP_MAX_ATTEMPTS:
            return False

        # Simple string comparison (constant-time via hmac.compare_digest)
        stored_otp = conn.execute("SELECT otp_code FROM otps WHERE id=?", (row["id"],)).fetchone()
        if not stored_otp or not hmac.compare_digest(stored_otp["otp_code"], otp_code):
            conn.execute("UPDATE otps SET attempts=attempts+1 WHERE id=?", (row["id"],))
            return False

        conn.execute("UPDATE otps SET used=1 WHERE id=?", (row["id"],))
        return True


# ─── Email sender ─────────────────────────────────────────────────────────────

def _send_otp_email(to_email: str, otp: str, purpose: str) -> None:
    if not EMAIL_USER or not EMAIL_PASS:
        # Dev mode: just print OTP to console
        print(f"\n{'='*50}")
        print(f"[DEV MODE] OTP for {to_email} ({purpose}): {otp}")
        print(f"(Set EMAIL_USER and EMAIL_PASS in backend/.env to send real emails)")
        print(f"{'='*50}\n")
        return

    subject_map = {
        "signup": "Verify your fintech account",
        "login": "Your fintech login code",
    }
    subject = subject_map.get(purpose, "Your fintech verification code")

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;">
      <h2 style="color:#1E293B;margin-bottom:4px;">fin<span style="color:#81BC06;">tech</span></h2>
      <p style="color:#64748B;font-size:14px;margin-top:0;">Company Intelligence Platform</p>
      <hr style="border:none;border-top:1px solid #E2E8F0;margin:20px 0;">
      <h3 style="color:#1E293B;">{'Verify your email' if purpose == 'signup' else 'Login verification code'}</h3>
      <p style="color:#475569;font-size:14px;">Enter this 6-digit code to continue:</p>
      <div style="background:#F1F5F9;border-radius:12px;padding:24px;text-align:center;margin:20px 0;">
        <span style="font-size:36px;font-weight:900;letter-spacing:12px;color:#1E293B;">{otp}</span>
      </div>
      <p style="color:#94A3B8;font-size:12px;">This code expires in 10 minutes. Do not share it with anyone.</p>
    </div>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, to_email, msg.as_string())
    except Exception as exc:
        print(f"[EMAIL ERROR] Could not send OTP email: {exc}")
        print(f"[FALLBACK] OTP for {to_email}: {otp}")


def _normalize_phone_number(phone: str) -> str:
    normalized = re.sub(r"[^\d+]", "", phone.strip())
    if normalized.startswith("00"):
        normalized = "+" + normalized[2:]
    if normalized.startswith("0") and len(normalized) == 11:
        normalized = "+91" + normalized[1:]
    if normalized.isdigit() and len(normalized) == 10:
        normalized = "+91" + normalized
    return normalized


def _is_valid_phone_number(phone: str) -> bool:
    return bool(re.fullmatch(r"\+\d{10,15}", phone))


def _send_otp_sms(phone_number: str, otp: str, purpose: str) -> None:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_FROM_NUMBER:
        print(f"\n{'='*50}")
        print(f"[DEV MODE] SMS OTP for {phone_number} ({purpose}): {otp}")
        print("(Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER to send real SMS)")
        print(f"{'='*50}\n")
        return

    body = f"fintech OTP ({purpose}): {otp}. Valid for 10 minutes. Do not share."
    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    response = _requests.post(
        endpoint,
        data={"To": phone_number, "From": TWILIO_FROM_NUMBER, "Body": body},
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        timeout=20,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"SMS delivery failed ({response.status_code}): {response.text}")


def _send_otp_to_user(email: str, otp: str, purpose: str, phone_override: str = "") -> None:
    phone = _normalize_phone_number(phone_override)
    if not phone:
        user = _get_user_by_email(email)
        if user:
            phone = _normalize_phone_number(user.get("phone_number") or "")
    if not phone or not _is_valid_phone_number(phone):
        raise HTTPException(status_code=400, detail="Valid mobile number is required for OTP verification.")
    _send_otp_sms(phone, otp, purpose)


# ─── User helpers ─────────────────────────────────────────────────────────────

def _get_user_by_email(email: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return dict(row) if row else None


def _create_user(
    email: str,
    name: str,
    password: str | None,
    provider: str,
    google_id: str = "",
    avatar_url: str = "",
    phone_number: str = "",
) -> dict:
    now = datetime.utcnow().isoformat()
    ph = _hash_password(password) if password else None
    verified = 1 if provider == "google" else 0
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO users (email, name, phone_number, password_hash, provider, google_id,
               avatar_url, is_verified, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (email, name, phone_number, ph, provider, google_id, avatar_url, verified, now),
        )
        res = {
            "id": cur.lastrowid,
            "email": email,
            "name": name,
            "phone_number": phone_number,
            "provider": provider,
            "avatar_url": avatar_url,
            "is_verified": verified,
            "created_at": now
        }
        # Also sync to TiDB Cloud for central tracking
        try:
            db_module.upsert_user(res)
        except Exception as e:
            print(f"[DB] Error syncing user to TiDB: {e}")
        return res


def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "provider": user["provider"],
        "phone_number": user.get("phone_number") or "",
        "avatar_url": user.get("avatar_url") or "",
        "is_verified": bool(user.get("is_verified")),
    }


class OTPPurpose(str, Enum):
    login = "login"
    signup = "signup"


def _clean_email(value: str) -> str:
    return value.strip().lower()


def _is_valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))


def _is_strong_password(value: str) -> bool:
    if len(value) < 8:
        return False
    has_letter = any(char.isalpha() for char in value)
    has_digit = any(char.isdigit() for char in value)
    return has_letter and has_digit


def _rate_limit_key(bucket: str, identifier: str) -> str:
    return f"{bucket}:{identifier}"


def _check_rate_limit(bucket: str, identifier: str, limit: int) -> None:
    now = time.time()
    key = _rate_limit_key(bucket, identifier)
    attempts = [timestamp for timestamp in _RATE_LIMIT_STORE.get(key, []) if (now - timestamp) <= RATE_LIMIT_WINDOW_SECONDS]
    if len(attempts) >= limit:
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a few minutes and try again.")
    attempts.append(now)
    _RATE_LIMIT_STORE[key] = attempts


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for
    client = request.client.host if request.client else ""
    return client or "unknown"


def _verify_bearer_token(authorization: str) -> dict[str, Any]:
    token = authorization.removeprefix("Bearer ").strip()
    payload = _verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return payload


# ─── Pydantic request models ──────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: str
    password: str
    name: str = ""
    phone_number: str


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyOTPRequest(BaseModel):
    email: str
    otp: str
    purpose: OTPPurpose = OTPPurpose.login


class ResendOTPRequest(BaseModel):
    email: str
    purpose: OTPPurpose = OTPPurpose.login


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


class UpdatePhoneRequest(BaseModel):
    email: str
    phone_number: str


# ─── Auth endpoints ───────────────────────────────────────────────────────────

@auth_router.post("/signup")
def signup(body: SignupRequest, request: Request) -> JSONResponse:
    email = _clean_email(body.email)
    client_ip = _client_ip(request)
    _check_rate_limit("signup_ip", client_ip, limit=10)
    _check_rate_limit("signup_email", email, limit=5)
    phone_number = _normalize_phone_number(body.phone_number)
    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address.")
    if not _is_valid_phone_number(phone_number):
        raise HTTPException(status_code=400, detail="Valid mobile number is required in +91XXXXXXXXXX format.")

    if not _is_strong_password(body.password):
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters and include letters and numbers.")

    existing = _get_user_by_email(email)
    if existing:
        if existing["provider"] == "google":
            raise HTTPException(status_code=409, detail="This email is registered via Google. Please use Google login.")
        raise HTTPException(status_code=409, detail="Email already registered. Please login.")

    name = body.name.strip() or email.split("@")[0].capitalize()
    _create_user(email, name, body.password, "manual", phone_number=phone_number)

    otp = _store_otp(email, "signup")
    _send_otp_to_user(email, otp, "signup", phone_override=phone_number)

    return JSONResponse(
        status_code=200,
        content={"status": "otp_sent", "email": email,
                 "message": "Account created. Enter the OTP sent to your mobile number to verify."},
    )


@auth_router.post("/login")
def login(body: LoginRequest, request: Request) -> JSONResponse:
    email = _clean_email(body.email)
    client_ip = _client_ip(request)
    _check_rate_limit("login_ip", client_ip, limit=20)
    _check_rate_limit("login_email", email, limit=10)
    user = _get_user_by_email(email)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if user["provider"] == "google":
        raise HTTPException(status_code=401, detail="This account uses Google login. Please sign in with Google.")

    if not user["password_hash"] or not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    phone_number = _normalize_phone_number(user.get("phone_number") or "")
    if not _is_valid_phone_number(phone_number):
        raise HTTPException(status_code=400, detail="Mobile number missing on account. Please contact support to update phone.")

    otp = _store_otp(email, "login")
    _send_otp_to_user(email, otp, "login")

    return JSONResponse(
        status_code=200,
        content={"status": "otp_sent", "email": email,
                 "message": "Login credentials verified. Enter the OTP sent to your mobile number."},
    )


@auth_router.post("/verify-otp")
def verify_otp(body: VerifyOTPRequest, request: Request) -> JSONResponse:
    email = _clean_email(body.email)
    _check_rate_limit("verify_otp_ip", _client_ip(request), limit=30)
    _check_rate_limit("verify_otp_email", email, limit=20)
    otp = body.otp.strip()
    if not re.fullmatch(r"\d{6}", otp):
        raise HTTPException(status_code=400, detail="OTP must be a 6 digit code.")

    if not _verify_otp(email, otp, body.purpose.value):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP. Please try again.")

    user = _get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Mark as verified on first login
    if not user["is_verified"]:
        with _get_conn() as conn:
            conn.execute("UPDATE users SET is_verified=1 WHERE email=?", (email,))
        user["is_verified"] = 1

    token = _create_token({"sub": email, "user_id": user["id"]})
    
    # Log the login event in TiDB Cloud
    try:
        db_module.log_user_login(email, _client_ip(request))
    except Exception as e:
        print(f"[DB] Error logging login to TiDB: {e}")

    return JSONResponse(
        content={
            "token": token,
            "user": _public_user(user),
            "message": "Login successful.",
        }
    )


@auth_router.post("/resend-otp")
def resend_otp(body: ResendOTPRequest, request: Request) -> JSONResponse:
    email = _clean_email(body.email)
    _check_rate_limit("resend_otp_ip", _client_ip(request), limit=10)
    _check_rate_limit("resend_otp_email", email, limit=5)
    user = _get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    otp = _store_otp(email, body.purpose.value)
    _send_otp_to_user(email, otp, body.purpose.value)

    return JSONResponse(content={"status": "otp_sent", "message": "New OTP sent to your mobile number."})


@auth_router.post("/forgot-password/request")
def request_forgot_password(body: ForgotPasswordRequest, request: Request) -> JSONResponse:
    email = _clean_email(body.email)
    _check_rate_limit("forgot_password_ip", _client_ip(request), limit=10)
    _check_rate_limit("forgot_password_email", email, limit=5)
    user = _get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    phone_number = _normalize_phone_number(user.get("phone_number") or "")
    if not _is_valid_phone_number(phone_number):
        raise HTTPException(status_code=400, detail="Mobile number missing on account.")

    otp = _store_otp(email, "reset_password")
    _send_otp_to_user(email, otp, "reset_password")
    return JSONResponse(content={"status": "otp_sent", "message": "Password reset OTP sent to registered mobile number."})


@auth_router.post("/forgot-password/confirm")
def confirm_forgot_password(body: ResetPasswordRequest, request: Request) -> JSONResponse:
    email = _clean_email(body.email)
    _check_rate_limit("reset_password_ip", _client_ip(request), limit=15)
    _check_rate_limit("reset_password_email", email, limit=10)
    otp = body.otp.strip()
    new_password = body.new_password.strip()
    if not re.fullmatch(r"\d{6}", otp):
        raise HTTPException(status_code=400, detail="OTP must be a 6 digit code.")
    if not _is_strong_password(new_password):
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters and include letters and numbers.")
    if not _verify_otp(email, otp, "reset_password"):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

    user = _get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    with _get_conn() as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE email=?", (_hash_password(new_password), email))
    return JSONResponse(content={"status": "password_reset", "message": "Password updated successfully. Please login again."})


@auth_router.post("/update-phone")
def update_phone_number(body: UpdatePhoneRequest, authorization: str = Header(default="")) -> JSONResponse:
    payload = _verify_bearer_token(authorization)
    email = _clean_email(body.email)
    if payload.get("sub") != email:
        raise HTTPException(status_code=403, detail="You can update only your own account.")
    phone_number = _normalize_phone_number(body.phone_number)
    if not _is_valid_phone_number(phone_number):
        raise HTTPException(status_code=400, detail="Valid mobile number is required in +91XXXXXXXXXX format.")
    user = _get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    with _get_conn() as conn:
        conn.execute("UPDATE users SET phone_number=? WHERE email=?", (phone_number, email))
    return JSONResponse(content={"status": "updated", "message": "Mobile number updated successfully."})


@auth_router.get("/google")
def google_login(request: Request) -> RedirectResponse:
    _check_rate_limit("google_login_ip", _client_ip(request), limit=10)
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env",
        )
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    from urllib.parse import urlencode
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(url)


@auth_router.get("/google/callback")
def google_callback(code: str = "", error: str = "") -> RedirectResponse:
    if error or not code:
        return RedirectResponse(f"{FRONTEND_URL}/?auth_error=google_cancelled")

    try:
        # Exchange code for tokens
        token_resp = _requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        # Get user info
        user_info_resp = _requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            timeout=15,
        )
        user_info_resp.raise_for_status()
        info = user_info_resp.json()

        email = info.get("email", "").lower()
        name = info.get("name", "") or email.split("@")[0]
        google_id = info.get("sub", "")
        avatar_url = info.get("picture", "")

        if not email:
            return RedirectResponse(f"{FRONTEND_URL}/?auth_error=google_no_email")

        user = _get_user_by_email(email)
        if not user:
            user = _create_user(email, name, None, "google", google_id, avatar_url)
        elif user["provider"] == "manual":
            # Link Google to existing manual account
            with _get_conn() as conn:
                conn.execute(
                    "UPDATE users SET google_id=?, avatar_url=?, is_verified=1 WHERE email=?",
                    (google_id, avatar_url, email),
                )
            user = _get_user_by_email(email)
        else:
            user = _get_user_by_email(email)

        # Send 2FA OTP even for Google logins
        phone_number = _normalize_phone_number((user or {}).get("phone_number") or "")
        if not _is_valid_phone_number(phone_number):
            from urllib.parse import urlencode
            params = urlencode({"email": email, "provider": "google", "auth_error": "mobile_required"})
            return RedirectResponse(f"{FRONTEND_URL}/?{params}")
        otp = _store_otp(email, "login")
        _send_otp_to_user(email, otp, "login")

        from urllib.parse import urlencode
        params = urlencode({"email": email, "provider": "google"})
        return RedirectResponse(f"{FRONTEND_URL}/?{params}&otp_sent=1")

    except Exception as exc:
        print(f"[GOOGLE AUTH ERROR] {exc}")
        return RedirectResponse(f"{FRONTEND_URL}/?auth_error=google_failed")


@auth_router.get("/me")
def get_me(authorization: str = Header(default="")) -> JSONResponse:
    payload = _verify_bearer_token(authorization)
    user = _get_user_by_email(payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return JSONResponse(content=_public_user(user))
