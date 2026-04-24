"""
db.py — MySQL database module for IBBI Data Pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FAULT-TOLERANT DESIGN:
  - If MySQL is unavailable, _DB_AVAILABLE = False
  - All read/write functions silently return empty/None
  - ZERO exceptions propagate to the API layer
  - Project always works (from memory/JSON) even if DB is down
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from dotenv import load_dotenv

# ── Load environment variables from .env ───────────────────────────────────
load_dotenv()

# ── Graceful import of mysql connector ──────────────────────────────────────
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    _CONNECTOR_AVAILABLE = True
except ImportError:
    _CONNECTOR_AVAILABLE = False
    print("[DB] mysql-connector-python not installed. DB features disabled.")


# ── Global availability flag ─────────────────────────────────────────────────
# Set to True only when init_db() succeeds. All functions check this first.
_DB_AVAILABLE: bool = False

# ── Connection config ────────────────────────────────────────────────────────
DB_CONFIG: dict[str, Any] = {
    "host":     os.getenv("MYSQL_HOST",     "localhost"),
    "port":     int(os.getenv("MYSQL_PORT", "3306")),
    "user":     os.getenv("MYSQL_USER",     "root"),
    "password": os.getenv("MYSQL_PASSWORD", "12345"),
    "database": os.getenv("MYSQL_DATABASE", "ibbi_db"),
    "charset":  "utf8mb4",
    "autocommit": True,
    "connection_timeout": 10,      # Slightly longer for cloud
}

# Add SSL config for TiDB Cloud if provided
ssl_ca = os.getenv("MYSQL_SSL_CA")
if ssl_ca:
    # Resolve path relative to backend folder if not absolute
    if not os.path.isabs(ssl_ca):
        ssl_ca = os.path.join(os.path.dirname(__file__), ssl_ca)
    
    if os.path.exists(ssl_ca):
        DB_CONFIG["ssl_ca"] = ssl_ca
        DB_CONFIG["ssl_verify_cert"] = True
    else:
        print(f"[DB] [WARN] SSL CA file not found at {ssl_ca}. SSL might fail.")



# ── Internal helpers ─────────────────────────────────────────────────────────
def _get_connection():
    if not _CONNECTOR_AVAILABLE:
        raise RuntimeError("mysql-connector-python not installed")
    return mysql.connector.connect(**DB_CONFIG)


def _ensure_database() -> None:
    """Create ibbi_db schema if it does not exist."""
    cfg = {k: v for k, v in DB_CONFIG.items() if k != "database"}
    try:
        conn = mysql.connector.connect(**cfg)
        cur = conn.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] _ensure_database failed: {e}")


# ── Public initialiser ───────────────────────────────────────────────────────
def init_db() -> bool:
    """
    Create database + tables. Returns True on success, False on any error.
    Sets the global _DB_AVAILABLE flag — all other functions depend on it.
    NEVER raises an exception.
    """
    global _DB_AVAILABLE
    if not _CONNECTOR_AVAILABLE:
        _DB_AVAILABLE = False
        return False
    try:
        _ensure_database()
        conn = _get_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id                VARCHAR(255) NOT NULL PRIMARY KEY,
                cin               VARCHAR(100),
                name              TEXT         NOT NULL,
                status            VARCHAR(100),
                type              VARCHAR(50),
                source_section    VARCHAR(100),
                announcement_date VARCHAR(50),
                synced_at         DATETIME     NOT NULL,
                data_json         LONGTEXT     NOT NULL,
                INDEX idx_cin    (cin(50)),
                INDEX idx_status (status),
                INDEX idx_type   (type),
                INDEX idx_source (source_section)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                id                VARCHAR(255) NOT NULL PRIMARY KEY,
                company_id        VARCHAR(255),
                cin               VARCHAR(100),
                debtor_name       TEXT,
                announcement_type VARCHAR(255),
                announcement_date VARCHAR(50),
                synced_at         DATETIME     NOT NULL,
                data_json         LONGTEXT     NOT NULL,
                INDEX idx_company_id (company_id(100)),
                INDEX idx_cin        (cin(50)),
                INDEX idx_date       (announcement_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS company_details (
                id          VARCHAR(255) NOT NULL PRIMARY KEY,
                cin         VARCHAR(100),
                name        TEXT,
                enriched_at DATETIME NOT NULL,
                data_json   LONGTEXT NOT NULL,
                INDEX idx_cin (cin(50))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id           VARCHAR(255) NOT NULL PRIMARY KEY,
                company_id   VARCHAR(255) NOT NULL,
                category     VARCHAR(100),
                synced_at    DATETIME NOT NULL,
                data_json    LONGTEXT NOT NULL,
                INDEX idx_company_id (company_id(100)),
                INDEX idx_category   (category)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS professionals (
                id                VARCHAR(255) NOT NULL PRIMARY KEY,
                registration_no   VARCHAR(255),
                name              TEXT,
                synced_at         DATETIME NOT NULL,
                data_json         LONGTEXT NOT NULL,
                INDEX idx_reg_no (registration_no(100))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id           INT AUTO_INCREMENT PRIMARY KEY,
                email        VARCHAR(255) UNIQUE NOT NULL,
                name         VARCHAR(255),
                phone_number VARCHAR(50),
                provider     VARCHAR(50) DEFAULT 'manual',
                is_verified  TINYINT DEFAULT 0,
                created_at   DATETIME NOT NULL,
                data_json    LONGTEXT,
                INDEX idx_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_logins (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                login_at   DATETIME NOT NULL,
                ip_address VARCHAR(100),
                INDEX idx_user_email (user_email),
                INDEX idx_login_at (login_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)


        conn.commit()
        cur.close()
        conn.close()
        _DB_AVAILABLE = True
        print("[DB] [OK] MySQL connected — ibbi_db tables ready.")
        return True

    except Exception as e:
        _DB_AVAILABLE = False
        print(f"[DB] [ERROR] MySQL connection failed: {e}")
        return False


# ── Status helper ────────────────────────────────────────────────────────────
def is_available() -> bool:
    """Return current DB availability status."""
    return _DB_AVAILABLE


# ── Write helpers (all silent on error) ─────────────────────────────────────
def upsert_companies(companies: list[dict[str, Any]]) -> None:
    """Save scraped companies to MySQL. Silent if DB unavailable."""
    if not _DB_AVAILABLE or not companies:
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        INSERT INTO companies
            (id, cin, name, status, type, source_section, announcement_date, synced_at, data_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            cin               = VALUES(cin),
            name              = VALUES(name),
            status            = VALUES(status),
            type              = VALUES(type),
            source_section    = VALUES(source_section),
            announcement_date = VALUES(announcement_date),
            synced_at         = VALUES(synced_at),
            data_json         = VALUES(data_json)
    """
    rows = [
        (
            str(c.get("id", ""))[:254],
            str(c.get("cin", "") or "")[:99],
            str(c.get("name", ""))[:499],
            str(c.get("status", "") or "")[:99],
            str(c.get("type", "") or "")[:49],
            str(c.get("sourceSection", "") or "")[:99],
            str(c.get("announcementDate", "") or "")[:49],
            now,
            json.dumps(c, ensure_ascii=False),
        )
        for c in companies
    ]
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.executemany(sql, rows)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] upsert_companies failed: {e}")


def upsert_announcements(announcements: list[dict[str, Any]], synced_at: str = "") -> None:
    """Save announcements to MySQL."""
    if not _DB_AVAILABLE or not announcements:
        return
    try:
        now = datetime.fromisoformat(synced_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    sql = """
        INSERT INTO announcements
            (id, company_id, cin, debtor_name, announcement_type, announcement_date, synced_at, data_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            company_id        = VALUES(company_id),
            cin               = VALUES(cin),
            debtor_name       = VALUES(debtor_name),
            announcement_type = VALUES(announcement_type),
            announcement_date = VALUES(announcement_date),
            synced_at         = VALUES(synced_at),
            data_json         = VALUES(data_json)
    """
    rows = []
    for a in announcements:
        cin = str(a.get("cin", "") or "")
        company_id = cin if cin and cin != "N/A" else str(a.get("id", ""))
        rows.append((
            str(a.get("id", ""))[:254],
            company_id[:254],
            cin[:99],
            str(a.get("debtorName", "") or "")[:499],
            str(a.get("announcementType", "") or "")[:254],
            str(a.get("announcementDate", "") or "")[:49],
            now,
            json.dumps(a, ensure_ascii=False),
        ))
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.executemany(sql, rows)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] upsert_announcements failed: {e}")


def upsert_company_detail(company: dict[str, Any]) -> None:
    """Save enriched company profile."""
    if not _DB_AVAILABLE:
        return
    company_id = str(company.get("id", "")).strip()
    cin = str(company.get("cin", "") or "").strip()
    if not company_id and not cin:
        return

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        INSERT INTO company_details (id, cin, name, enriched_at, data_json)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            cin         = VALUES(cin),
            name        = VALUES(name),
            enriched_at = VALUES(enriched_at),
            data_json   = VALUES(data_json)
    """
    data_json = json.dumps(company, ensure_ascii=False)
    ids_to_save: list[str] = []
    if company_id:
        ids_to_save.append(company_id)
    if cin and cin.upper() != "N/A" and cin != company_id:
        ids_to_save.append(cin)

    rows = [
        (pk[:254], cin[:99], str(company.get("name", ""))[:499], now, data_json)
        for pk in ids_to_save
    ]
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.executemany(sql, rows)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] upsert_company_detail failed: {e}")


def upsert_claims(company_id: str, claims: list[dict[str, Any]]) -> None:
    """Save scraped claims to MySQL."""
    if not _DB_AVAILABLE or not claims:
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        INSERT INTO claims (id, company_id, category, synced_at, data_json)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            company_id = VALUES(company_id),
            category   = VALUES(category),
            synced_at  = VALUES(synced_at),
            data_json  = VALUES(data_json)
    """
    rows = []
    for c in claims:
        claim_id = str(c.get("id") or f"{company_id}-{hash(str(c))}")[:254]
        rows.append((
            claim_id,
            company_id[:254],
            str(c.get("category", "Other"))[:99],
            now,
            json.dumps(c, ensure_ascii=False)
        ))
    
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.executemany(sql, rows)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] upsert_claims failed: {e}")


def get_company_claims(company_id: str) -> list[dict[str, Any]]:
    """Fetch all claims for a specific company."""
    if not _DB_AVAILABLE:
        return []
    try:
        conn = _get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT data_json FROM claims WHERE company_id = %s", (company_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [json.loads(r["data_json"]) for r in rows]
    except Exception as e:
        print(f"[DB] get_company_claims failed: {e}")
        return []


def upsert_professionals(professionals: list[dict[str, Any]]) -> None:
    """Save insolvency professionals to MySQL."""
    if not _DB_AVAILABLE or not professionals:
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        INSERT INTO professionals (id, registration_no, name, synced_at, data_json)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            registration_no = VALUES(registration_no),
            name            = VALUES(name),
            synced_at       = VALUES(synced_at),
            data_json       = VALUES(data_json)
    """
    rows = []
    for p in professionals:
        reg_no = p.get("registration_number") or p.get("regNo") or ""
        p_name = p.get("name") or ""
        p_id = reg_no or f"prof-{hash(p_name)}"
        
        rows.append((
            str(p_id)[:254],
            str(reg_no)[:254],
            str(p_name)[:499],
            now,
            json.dumps(p, ensure_ascii=False)
        ))
    
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.executemany(sql, rows)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] upsert_professionals failed: {e}")


# ── Execution helper for Auth ──────────────────────────────────────────────
def execute_query(sql: str, params: tuple = (), commit: bool = False, fetch: bool = False, dictionary: bool = True) -> Any:
    """Generic helper for auth.py to run queries on MySQL. Silent on error."""
    if not _DB_AVAILABLE:
        return None
    try:
        conn = _get_connection()
        cur = conn.cursor(dictionary=dictionary)
        cur.execute(sql, params)
        
        res = None
        if fetch:
            res = cur.fetchall()
        elif commit:
            conn.commit()
            res = cur.lastrowid
            
        cur.close()
        conn.close()
        return res
    except Exception as e:
        print(f"[DB] execute_query failed: {e}")
        print(f"[DB] SQL: {sql}")
        return None


def upsert_user(user_data: dict[str, Any]) -> None:
    """Save/update user profile in MySQL."""
    if not _DB_AVAILABLE:
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    email = user_data.get("email")
    if not email: return
    
    sql = """
        INSERT INTO users (email, name, phone_number, provider, is_verified, created_at, data_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name         = VALUES(name),
            phone_number = VALUES(phone_number),
            provider     = VALUES(provider),
            is_verified  = VALUES(is_verified),
            data_json    = VALUES(data_json)
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(sql, (
            email,
            user_data.get("name"),
            user_data.get("phone_number"),
            user_data.get("provider", "manual"),
            1 if user_data.get("is_verified") else 0,
            user_data.get("created_at") or now,
            json.dumps(user_data, ensure_ascii=False)
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] upsert_user failed: {e}")


def log_user_login(email: str, ip_address: str = "") -> None:
    """Log a login event in TiDB Cloud."""
    if not _DB_AVAILABLE:
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO user_logins (user_email, login_at, ip_address) VALUES (%s, %s, %s)",
            (email, now, ip_address)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] log_user_login failed: {e}")


# ── Read helpers (return safe defaults on error) ─────────────────────────────
def get_all_companies() -> list[dict[str, Any]]:
    """Load all companies from MySQL."""
    if not _DB_AVAILABLE:
        return []
    try:
        conn = _get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT data_json FROM companies ORDER BY announcement_date DESC LIMIT 1000")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [json.loads(r["data_json"]) for r in rows]
    except Exception as e:
        print(f"[DB] get_all_companies failed: {e}")
        return []


def get_company_detail(id_or_cin: str) -> dict[str, Any] | None:
    """Fetch enriched profile by id or CIN."""
    if not _DB_AVAILABLE:
        return None
    key = id_or_cin.strip().upper()
    try:
        conn = _get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT data_json FROM company_details WHERE id = %s OR cin = %s LIMIT 1",
            (key, key),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return json.loads(row["data_json"]) if row else None
    except Exception as e:
        print(f"[DB] get_company_detail failed: {e}")
        return None


def get_recent_announcements(limit: int = 50) -> list[dict[str, Any]]:
    """Return latest announcements."""
    if not _DB_AVAILABLE:
        return []
    try:
        conn = _get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT data_json FROM announcements "
            "ORDER BY announcement_date DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [json.loads(r["data_json"]) for r in rows]
    except Exception as e:
        print(f"[DB] get_recent_announcements failed: {e}")
        return []


def get_stats() -> dict[str, Any]:
    """Return DB stats. Returns zeroed dict if DB unavailable."""
    if not _DB_AVAILABLE:
        return {}
    try:
        conn = _get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT COUNT(*) AS total FROM companies")
        total_companies = (cur.fetchone() or {}).get("total", 0)
        cur.execute("SELECT COUNT(*) AS total FROM announcements")
        total_ann = (cur.fetchone() or {}).get("total", 0)
        cur.execute("SELECT MAX(synced_at) AS last_sync FROM companies")
        row = cur.fetchone() or {}
        last_sync = row.get("last_sync")
        last_sync_str = (last_sync.isoformat() + "Z") if last_sync else ""
        cur.close()
        conn.close()
        return {
            "totalCompanies":    total_companies,
            "totalAnnouncements": total_ann,
            "totalProfessionals": 0,
            "lastSyncedAt":      last_sync_str,
            "ibbiStatus":        "ok",
            "ibbiError":         "",
        }
    except Exception as e:
        print(f"[DB] get_stats failed: {e}")
        return {}


# ── Standalone connectivity test ─────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing MySQL connection...")
    ok = init_db()
    if ok:
        print(f"[OK] DB ready! Tables created in {DB_CONFIG['database']}.")
    else:
        print("[ERROR] DB not available. Check MySQL is running and credentials are correct.")
