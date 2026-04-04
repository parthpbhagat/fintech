from __future__ import annotations

import csv
import io
import json
import os
import re
import time
from datetime import datetime
from html import unescape
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import quote, urljoin

import requests
import uvicorn
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from auth import auth_router

IBBI_EXPORT_URL = "https://ibbi.gov.in/public-announcement?ann=&title=&date=&export_excel=export_excel"
IBBI_PUBLIC_ANNOUNCEMENT_URL = "https://ibbi.gov.in/en/public-announcement"
IBBI_CLAIMS_SEARCH_URL = "https://ibbi.gov.in/claims/claim-process"
IBBI_CLAIMS_VERSION_URL = "https://ibbi.gov.in/claims/version-details"
IBBI_CLAIMS_DETAIL_URL = "https://ibbi.gov.in/claims/frontClaimDetails"
BASE_DIR = Path(__file__).resolve().parent
COMPANY_DETAIL_STORE_PATH = BASE_DIR / "data" / "company_details_store.json"
CACHE_TTL_SECONDS = 5 * 60
PROFILE_CACHE_TTL_SECONDS = 30 * 60
REQUEST_TIMEOUT_SECONDS = 45
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080").strip()
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", FRONTEND_URL).split(",") if origin.strip()]

app = FastAPI(title="fintech API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/auth/") else "public, max-age=60"
    return response


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = unescape(str(value)).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,\n\t")


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return normalized.strip("-") or "ibbi-company"


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_text(value).lower())


def parse_date(value: str) -> datetime:
    value = clean_text(value)
    if not value:
        return datetime.min
    normalized = re.sub(r"(\d{1,2})\s*(st|nd|rd|th)\b", r"\1", value, flags=re.I)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    formats = [
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d %B, %Y",
        "%d %b, %Y",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S GMT",
    ]
    for date_format in formats:
        try:
            return datetime.strptime(normalized, date_format)
        except ValueError:
            continue
    return datetime.min


def to_iso_date(value: str) -> str:
    parsed = parse_date(value)
    return parsed.strftime("%Y-%m-%d") if parsed != datetime.min else ""


def normalize_display_date(value: str) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return "N/A"
    parsed = parse_date(cleaned)
    return parsed.strftime("%Y-%m-%d") if parsed != datetime.min else cleaned


def utc_now_iso(*, timespec: str = "seconds") -> str:
    return datetime.utcnow().isoformat(timespec=timespec) + "Z"


def sanitize_public_value(value: Any) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return "N/A"
    blocked_tokens = (
        "CLICK HERE TO LOGIN",
        "CLICK HERE TO UPDATE",
        "UNLOCK NOW",
        "LOGIN AND UPDATE",
        "KNOW MORE",
    )
    if any(token in cleaned.upper() for token in blocked_tokens):
        return "N/A"
    return cleaned


def is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        cleaned = clean_text(value)
        return not cleaned or cleaned.upper() in {"N/A", "NA", "NULL", "NONE", "-"}
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    if isinstance(value, (int, float)):
        return value == 0
    return False


def is_masked_public_value(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    cleaned = clean_text(value)
    return "*" in cleaned or "XXXXX" in cleaned.upper()


def normalize_company_status(value: str, fallback: str = "Active") -> str:
    cleaned = clean_text(value).lower()
    if "cirp" in cleaned:
        return "Under CIRP"
    if "liquid" in cleaned:
        return "Liquidation"
    if "dissolv" in cleaned:
        return "Dissolved"
    if "inactive" in cleaned:
        return "Inactive"
    if "active" in cleaned:
        return "Active"
    return fallback


def build_news_item(
    company_id: str,
    title: str,
    source: str,
    date: str,
    summary: str,
    url: str,
) -> dict[str, str]:
    normalized_date = normalize_display_date(date)
    safe_title = clean_text(title) or "Company update"
    return {
        "id": f"{company_id}-{slugify(source)}-{slugify(safe_title)}-{to_iso_date(normalized_date) or slugify(normalized_date)}",
        "title": safe_title,
        "source": clean_text(source) or "Public Source",
        "date": normalized_date,
        "summary": clean_text(summary) or "No summary available.",
        "url": clean_text(url),
        "companyId": company_id,
    }


def normalize_source_section(value: str) -> str:
    cleaned = clean_text(value).lower()
    if not cleaned:
        return ""
    if "master+ibbi" in cleaned:
        return "master+ibbi"
    if "master" in cleaned:
        return "master"
    if "claims" in cleaned:
        return "claims"
    if "ibbi" in cleaned:
        return "ibbi"
    return cleaned


def normalize_company_type(value: str, *, fallback_name: str = "") -> str:
    normalized = clean_text(value).lower()
    if "llp" in normalized:
        return "LLP"
    if "opc" in normalized:
        return "OPC"
    if "private" in normalized:
        return "Private"
    if "public" in normalized:
        return "Public"
    if fallback_name:
        return infer_company_type(fallback_name)
    return "Public"


def extract_urls(value: str) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    pattern = re.compile(r"https?://[^\s<>'\"),]+", re.I)
    return [clean_text(url) for url in pattern.findall(text) if clean_text(url)]


def is_probable_pdf_url(url: str) -> bool:
    cleaned = clean_text(url).lower()
    if not cleaned:
        return False
    return ".pdf" in cleaned or "download" in cleaned and ("document" in cleaned or "attachment" in cleaned)


def build_company_source_urls(company: dict[str, Any]) -> dict[str, str]:
    cin = clean_text(company.get("cin", ""))
    registry_url = clean_text(company.get("registryUrl", ""))
    source_urls: dict[str, str] = {}

    if registry_url:
        source_urls["ibbiAnnouncement"] = registry_url
    source_urls["ibbiPublicAnnouncement"] = IBBI_PUBLIC_ANNOUNCEMENT_URL
    source_urls["ibbiClaims"] = build_claims_registry_url(cin) if cin and cin != "N/A" else IBBI_CLAIMS_SEARCH_URL
    return source_urls


def build_company_data_sources(company: dict[str, Any]) -> list[dict[str, str]]:
    urls = build_company_source_urls(company)
    sources: list[dict[str, str]] = []
    checked_at = utc_now_iso(timespec="minutes")

    sources.append(
        {
            "id": "ibbi_public_announcement",
            "name": "IBBI Public Announcement",
            "portalType": "government",
            "mode": "live-scrape",
            "status": "connected",
            "url": urls.get("ibbiAnnouncement") or urls["ibbiPublicAnnouncement"],
            "note": "Primary insolvency announcement source.",
            "checkedAt": checked_at,
        }
    )
    sources.append(
        {
            "id": "ibbi_claims",
            "name": "IBBI Claims Process",
            "portalType": "government",
            "mode": "live-scrape",
            "status": "connected",
            "url": urls["ibbiClaims"],
            "note": "Claims workflow and claim version pages.",
            "checkedAt": checked_at,
        }
    )
    return sources


def attach_company_source_metadata(company: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(company)
    enriched["type"] = normalize_company_type(enriched.get("type", ""), fallback_name=enriched.get("name", ""))
    if (not is_valid_roc_code(enriched.get("rocCode"))) or "N/A" in clean_text(enriched.get("rocCode", "")).upper():
        enriched["rocCode"] = derive_roc_code(enriched.get("cin", ""), enriched.get("registeredAddress", ""))
    if is_missing_value(enriched.get("registrationNumber")) and not is_missing_value(enriched.get("cin")):
        cin_value = clean_text(enriched.get("cin", ""))
        if cin_value and cin_value != "N/A":
            enriched["registrationNumber"] = cin_value[-6:] if len(cin_value) >= 6 else cin_value

    # Backfill frequently-missing company fields so UI does not show blank/null.
    enriched["companySubcategory"] = sanitize_public_value(enriched.get("companySubcategory", enriched.get("category", "N/A")))
    enriched["filingStatus"] = sanitize_public_value(enriched.get("filingStatus", "N/A"))
    enriched["activeCompliance"] = sanitize_public_value(enriched.get("activeCompliance", "N/A"))
    enriched["industry"] = sanitize_public_value(enriched.get("industry", "N/A"))
    enriched["lastUpdatedOn"] = normalize_display_date(
        enriched.get("lastUpdatedOn") or enriched.get("announcementDate") or enriched.get("incorporationDate") or "N/A"
    )
    enriched["email"] = sanitize_public_value(enriched.get("email", "N/A"))
    enriched["phone"] = sanitize_public_value(enriched.get("phone", "N/A"))
    enriched["website"] = sanitize_public_value(enriched.get("website", "N/A"))
    enriched["registeredAddress"] = sanitize_public_value(enriched.get("registeredAddress", "N/A"))
    if is_missing_value(enriched.get("businessAddress")):
        enriched["businessAddress"] = enriched["registeredAddress"]
    if not enriched.get("addresses"):
        enriched["addresses"] = []

    enriched["sourceUrls"] = build_company_source_urls(enriched)
    enriched["dataSources"] = build_company_data_sources(enriched)
    return enriched


def matches_company_filters(
    company: dict[str, Any],
    *,
    status: str = "",
    company_type: str = "",
    source: str = "",
) -> bool:
    normalized_status = clean_text(status).lower()
    normalized_type = clean_text(company_type).lower()
    normalized_source = normalize_source_section(source)

    if normalized_status and clean_text(company.get("status", "")).lower() != normalized_status:
        return False
    if normalized_type and clean_text(company.get("type", "")).lower() != normalized_type:
        return False
    if normalized_source and normalize_source_section(company.get("sourceSection", "")) != normalized_source:
        return False
    return True


def geocode_company_address(session: requests.Session, address: str) -> dict[str, Any] | None:
    cleaned_address = sanitize_public_value(address)
    if cleaned_address == "N/A":
        return None

    return {
        "formattedAddress": cleaned_address,
        "embedUrl": f"https://maps.google.com/maps?q={quote(cleaned_address)}&t=&z=15&ie=UTF8&iwloc=&output=embed",
        "mapUrl": f"https://www.google.com/maps/search/?api=1&query={quote(cleaned_address)}",
    }


def build_company_contact_summary(company: dict[str, Any]) -> str:
    parts = []
    email = sanitize_public_value(company.get("email", "N/A"))
    phone = sanitize_public_value(company.get("phone", "N/A"))
    website = sanitize_public_value(company.get("website", "N/A"))
    registered_address = sanitize_public_value(company.get("registeredAddress", "N/A"))

    if email != "N/A":
        parts.append(f"Email: {email}")
    if phone != "N/A":
        parts.append(f"Phone: {phone}")
    if website != "N/A":
        parts.append(f"Website: {website}")
    if registered_address != "N/A":
        parts.append(f"Address: {registered_address}")

    return " | ".join(parts) if parts else "No public company contact details are currently available."


def derive_status(announcement_type: str) -> str:
    normalized = announcement_type.lower()
    if "liquidation" in normalized:
        return "Liquidation"
    if "dissolution" in normalized:
        return "Dissolved"
    if "bankruptcy" in normalized:
        return "Inactive"
    return "Under CIRP"


def infer_company_type(name: str) -> str:
    normalized = name.upper()
    if "LLP" in normalized:
        return "LLP"
    if "(OPC)" in normalized or " OPC " in f" {normalized} ":
        return "OPC"
    if "PRIVATE" in normalized:
        return "Private"
    return "Public"


def derive_roc_code(cin_or_llpin: str, address: str = "") -> str:
    identifier = clean_text(cin_or_llpin).upper()
    if identifier and identifier != "N/A":
        cin_match = re.match(r"^[A-Z]\d{5}([A-Z]{2})\d{4}", identifier)
        if cin_match:
            return f"ROC-{cin_match.group(1)}"
        llp_match = re.match(r"^([A-Z]{3})-\d{4,6}$", identifier)
        if llp_match:
            return f"ROC-{llp_match.group(1)}"
        # Additional fallback for noisy CIN values where state code is still present.
        state_match = re.search(r"[A-Z]\d{5}([A-Z]{2})", identifier)
        if state_match:
            return f"ROC-{state_match.group(1)}"
        if len(identifier) >= 8 and identifier[6:8].isalpha():
            return f"ROC-{identifier[6:8]}"

    normalized_address = clean_text(address).lower()
    if not normalized_address:
        return "N/A"
    for state_code, keywords in {
        "GJ": ["gujarat"],
        "MH": ["maharashtra", "mumbai"],
        "DL": ["delhi", "new delhi"],
        "KA": ["karnataka", "bengaluru", "bangalore"],
        "TN": ["tamil nadu", "chennai"],
        "WB": ["west bengal", "kolkata"],
        "RJ": ["rajasthan"],
        "UP": ["uttar pradesh"],
        "HR": ["haryana"],
        "PB": ["punjab"],
        "TS": ["telangana", "hyderabad"],
        "AP": ["andhra pradesh"],
    }.items():
        if any(keyword in normalized_address for keyword in keywords):
            return f"ROC-{state_code}"
    return "N/A"


def is_valid_roc_code(value: Any) -> bool:
    cleaned = clean_text(value).upper()
    return bool(re.fullmatch(r"ROC-[A-Z]{2,3}", cleaned))


def looks_like_cin(value: str) -> bool:
    cleaned = clean_text(value).upper()
    return bool(re.fullmatch(r"[A-Z0-9]{10,25}", cleaned))


def find_first_value(row: dict[str, Any], *aliases: str) -> str:
    normalized_map = {normalize_key(key): clean_text(value) for key, value in row.items()}
    for alias in aliases:
        value = normalized_map.get(normalize_key(alias), "")
        if value:
            return value
    return ""


def build_registry_url(search_term: str) -> str:
    cleaned = clean_text(search_term)
    if not cleaned:
        return IBBI_PUBLIC_ANNOUNCEMENT_URL
    return (
        f"{IBBI_PUBLIC_ANNOUNCEMENT_URL}?ann=&date=&direction=desc"
        f"&sort=FLD_PA_ANNOUNCE_DATE&title={quote(cleaned)}"
    )


def normalize_keys(row: dict[str, Any]) -> dict[str, str]:
    return {clean_text(key): clean_text(value) for key, value in row.items()}


def build_announcement(row: dict[str, str]) -> dict[str, Any]:
    announcement_type = row.get("Announcement Type", "")
    announcement_date = row.get("Date of Announcement", "")
    last_date = row.get("Last date of Submission", "")
    debtor_name = row.get("Name of Corporate Debtor", "")
    cin = row.get("CIN No.", "")
    applicant_name = row.get("Name of Applicant", "")
    insolvency_professional = row.get("Name of Insolvency Professional", "")

    announcement_id = cin or f"{slugify(debtor_name)}-{to_iso_date(announcement_date) or 'undated'}"
    return {
        "id": announcement_id,
        "announcementType": announcement_type,
        "announcementDate": announcement_date,
        "announcementDateIso": to_iso_date(announcement_date),
        "lastDateOfSubmission": last_date,
        "lastDateOfSubmissionIso": to_iso_date(last_date),
        "debtorName": debtor_name,
        "cin": cin or "N/A",
        "applicantName": applicant_name or "N/A",
        "insolvencyProfessional": insolvency_professional or "N/A",
        "insolvencyProfessionalAddress": row.get("Address of Insolvency Professional", "") or "N/A",
        "remarks": row.get("Remarks", "") or "No remarks published by IBBI.",
        "status": derive_status(announcement_type),
        "registryUrl": build_registry_url(cin or debtor_name),
    }


def build_company(announcements: list[dict[str, Any]]) -> dict[str, Any]:
    history = sorted(announcements, key=lambda item: parse_date(item["announcementDate"]), reverse=True)
    latest = history[0]
    name = latest["debtorName"]
    cin = latest["cin"]
    company_id = cin if cin != "N/A" else slugify(name)
    insolvency_professionals = sorted(
        {entry["insolvencyProfessional"] for entry in history if entry["insolvencyProfessional"] != "N/A"}
    )
    applicants = sorted({entry["applicantName"] for entry in history if entry["applicantName"] != "N/A"})

    summary = (
        f"{name} currently appears in {len(history)} IBBI public announcement"
        f"{'' if len(history) == 1 else 's'}. Latest update: {latest['announcementType']} on "
        f"{latest['announcementDate'] or 'date not published'}."
    )

    return {
        "id": company_id,
        "name": name,
        "cin": cin,
        "pan": "N/A",
        "incorporationDate": "N/A",
        "status": latest["status"],
        "type": normalize_company_type(infer_company_type(name), fallback_name=name),
        "category": latest["announcementType"],
        "origin": "Indian",
        "registeredAddress": "N/A",
        "businessAddress": "N/A",
        "phone": "N/A",
        "email": "N/A",
        "website": "N/A",
        "listingStatus": "Unlisted",
        "lastAGMDate": "N/A",
        "lastBSDate": "N/A",
        "gstin": "N/A",
        "lei": "N/A",
        "epfo": "N/A",
        "iec": "N/A",
        "authCap": 0,
        "puc": 0,
        "soc": 0,
        "revenue": [],
        "pat": [],
        "netWorth": [],
        "promoterHolding": [],
        "receivable": "N/A",
        "payable": "N/A",
        "overview": summary,
        "charges": [],
        "financials": [],
        "ownership": [],
        "compliance": [],
        "documents": [],
        "directors": [],
        "news": [],
        "trendData": list(range(len(history), 0, -1)),
        "applicant_name": latest["applicantName"],
        "ip_name": latest["insolvencyProfessional"],
        "commencement_date": latest["announcementDate"],
        "last_date_claims": latest["lastDateOfSubmission"],
        "announcementType": latest["announcementType"],
        "announcementDate": latest["announcementDate"],
        "announcementDateIso": latest["announcementDateIso"],
        "lastDateOfSubmission": latest["lastDateOfSubmission"],
        "lastDateOfSubmissionIso": latest["lastDateOfSubmissionIso"],
        "insolvencyProfessionalAddress": latest["insolvencyProfessionalAddress"],
        "remarks": latest["remarks"],
        "registryUrl": latest["registryUrl"],
        "announcementCount": len(history),
        "announcementHistory": history,
        "applicants": applicants,
        "insolvencyProfessionals": insolvency_professionals,
        "sourceUrls": {},
        "dataSources": [],
    }


def rank_company(company: dict[str, Any], query: str) -> tuple[int, datetime, str]:
    query_upper = query.upper()
    name = clean_text(company["name"]).upper()
    cin = clean_text(company["cin"]).upper()
    pan = clean_text(company.get("pan", "")).upper()
    gstin = clean_text(company.get("gstin", "")).upper()
    email = clean_text(company.get("email", "")).upper()
    applicant = clean_text(company.get("applicant_name", "")).upper()
    professional = clean_text(company.get("ip_name", "")).upper()

    score = 0
    if cin and cin == query_upper:
        score += 160
    if pan and pan == query_upper:
        score += 150
    if gstin and gstin == query_upper:
        score += 150
    if name == query_upper:
        score += 140
    if name.startswith(query_upper):
        score += 110
    if query_upper in name:
        score += 90
    if query_upper in cin:
        score += 80
    if query_upper in pan:
        score += 75
    if query_upper in gstin:
        score += 75
    if query_upper in applicant:
        score += 50
    if query_upper in professional:
        score += 45
    if query_upper in email:
        score += 35

    latest_date = parse_date(company.get("announcementDate", ""))
    return score, latest_date, name


def parse_claim_search_rows(html: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    pattern = re.compile(
        r'<a href="/claims/version-details/([A-Z0-9]+)"[^>]*>(.*?)</a>\s*</td>\s*'
        r"<td>(.*?)</td>\s*<td>(.*?)</td>\s*</td>\s*<td>(.*?)</td>\s*<td>.*?"
        r'href="/claims/front[-]?claim-details/(\d+)"',
        re.S | re.I,
    )
    for cin, name, ip_name, under_process, latest_claim_date, detail_id in pattern.findall(html):
        rows.append(
            {
                "cin": clean_text(cin),
                "name": clean_text(name),
                "ip_name": clean_text(ip_name),
                "under_process": clean_text(under_process),
                "latest_claim_date": clean_text(latest_claim_date),
                "detail_id": clean_text(detail_id),
            }
        )
    return rows


def parse_claim_version_rows(html: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    pattern = re.compile(
        r"<td>(Version\s+\d+)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>.*?"
        r'href="/claims/frontClaimDetails/(\d+)"',
        re.S | re.I,
    )
    for version, version_date, rp_name, detail_id in pattern.findall(html):
        rows.append(
            {
                "version": clean_text(version),
                "version_date": clean_text(version_date),
                "rp_name": clean_text(rp_name),
                "detail_id": clean_text(detail_id),
            }
        )
    return rows


def parse_claim_detail_inputs(html: str) -> dict[str, str]:
    values: dict[str, str] = {}
    pattern = re.compile(r"<label>(.*?)</label>.*?<input[^>]*value=\"(.*?)\"", re.S | re.I)
    for label, value in pattern.findall(html):
        values[clean_text(label)] = clean_text(value)
    return values


def build_claims_registry_url(cin: str) -> str:
    return f"{IBBI_CLAIMS_VERSION_URL}/{quote(cin)}"


def build_claims_company_from_search_row(row: dict[str, str]) -> dict[str, Any]:
    process = row["under_process"]
    announcement_type = f"IBBI Claims Process - {process}" if process else "IBBI Claims Process"
    return {
        "id": row["cin"] or slugify(row["name"]),
        "name": row["name"],
        "cin": row["cin"] or "N/A",
        "pan": "N/A",
        "incorporationDate": "N/A",
        "status": "Liquidation" if process.lower() == "liquidation" else "Under CIRP",
        "type": normalize_company_type(infer_company_type(row["name"]), fallback_name=row["name"]),
        "category": announcement_type,
        "origin": "Indian",
        "registeredAddress": "N/A",
        "businessAddress": "N/A",
        "phone": "N/A",
        "email": "N/A",
        "website": "N/A",
        "listingStatus": "Unlisted",
        "lastAGMDate": "N/A",
        "lastBSDate": "N/A",
        "gstin": "N/A",
        "lei": "N/A",
        "epfo": "N/A",
        "iec": "N/A",
        "authCap": 0,
        "puc": 0,
        "soc": 0,
        "revenue": [],
        "pat": [],
        "netWorth": [],
        "promoterHolding": [],
        "receivable": "N/A",
        "payable": "N/A",
        "overview": f"{row['name']} appears in the IBBI claims process listing. Latest claim list date: {row['latest_claim_date'] or 'N/A'}.",
        "charges": [],
        "financials": [],
        "ownership": [],
        "compliance": [],
        "documents": [],
        "directors": [],
        "news": [],
        "trendData": [1],
        "applicant_name": "N/A",
        "ip_name": row["ip_name"] or "N/A",
        "commencement_date": row["latest_claim_date"] or "N/A",
        "last_date_claims": row["latest_claim_date"] or "N/A",
        "announcementType": announcement_type,
        "announcementDate": row["latest_claim_date"] or "N/A",
        "announcementDateIso": to_iso_date(row["latest_claim_date"]),
        "lastDateOfSubmission": row["latest_claim_date"] or "N/A",
        "lastDateOfSubmissionIso": to_iso_date(row["latest_claim_date"]),
        "insolvencyProfessionalAddress": "N/A",
        "remarks": "Source: IBBI claims process listing.",
        "registryUrl": build_claims_registry_url(row["cin"]),
        "announcementCount": 1,
        "announcementHistory": [],
        "applicants": [],
        "insolvencyProfessionals": [row["ip_name"]] if row["ip_name"] else [],
        "sourceSection": "claims",
        "sourceUrls": {},
        "dataSources": [],
    }










def build_company_documents(company: dict[str, Any]) -> list[dict[str, Any]]:
    company_id = clean_text(company.get("id", ""))
    current_year = datetime.utcnow().year
    documents: list[dict[str, Any]] = [
        {
            "formId": "PROFILE_JSON",
            "fileName": f"{slugify(company.get('name', company_id))}-profile.json",
            "year": current_year,
            "dateOfFiling": normalize_display_date(company.get("lastUpdatedOn") or company.get("announcementDate") or datetime.utcnow().strftime("%Y-%m-%d")),
            "category": "Profile Snapshot",
            "source": "Internal Export",
            "url": f"/company/{quote(company_id)}/documents/profile.json",
            "downloadUrl": f"/company/{quote(company_id)}/documents/profile.json",
        },
        {
            "formId": "PROFILE_TXT",
            "fileName": f"{slugify(company.get('name', company_id))}-summary.txt",
            "year": current_year,
            "dateOfFiling": normalize_display_date(company.get("lastUpdatedOn") or company.get("announcementDate") or datetime.utcnow().strftime("%Y-%m-%d")),
            "category": "Company Summary",
            "source": "Internal Export",
            "url": f"/company/{quote(company_id)}/documents/summary.txt",
            "downloadUrl": f"/company/{quote(company_id)}/documents/summary.txt",
        },
    ]

    if company.get("registryUrl"):
        documents.append(
            {
                "formId": "IBBI_REGISTRY",
                "fileName": "ibbi-registry-reference.html",
                "year": current_year,
                "dateOfFiling": normalize_display_date(company.get("announcementDate") or company.get("lastUpdatedOn") or "N/A"),
                "category": "IBBI Registry Source",
                "source": "IBBI",
                "url": company["registryUrl"],
                "downloadUrl": company["registryUrl"],
            }
        )

    discovered_pdf_urls: set[str] = set()
    for announcement in company.get("announcementHistory") or []:
        for url in [announcement.get("registryUrl", ""), announcement.get("remarks", "")]:
            for extracted_url in extract_urls(url):
                if is_probable_pdf_url(extracted_url):
                    discovered_pdf_urls.add(extracted_url)

    for pdf_index, pdf_url in enumerate(sorted(discovered_pdf_urls), start=1):
        documents.append(
            {
                "formId": f"SOURCE_PDF_{pdf_index}",
                "fileName": f"source-document-{pdf_index}.pdf",
                "year": current_year,
                "dateOfFiling": normalize_display_date(company.get("announcementDate") or company.get("lastUpdatedOn") or "N/A"),
                "category": "Source PDF",
                "source": "IBBI Public Announcement",
                "url": pdf_url,
                "downloadUrl": pdf_url,
            }
        )

    deduped: dict[str, dict[str, Any]] = {}
    for document in documents:
        key = f"{document['formId']}|{clean_text(document.get('url', ''))}"
        deduped.setdefault(key, document)
    return list(deduped.values())


def build_company_summary_text(company: dict[str, Any]) -> str:
    lines = [
        f"Company: {company.get('name', 'N/A')}",
        f"CIN/LLPIN: {company.get('cin', 'N/A')}",
        f"Status: {company.get('status', 'N/A')}",
        f"Type: {company.get('type', 'N/A')}",
        f"Incorporation Date: {company.get('incorporationDate', 'N/A')}",
        f"ROC: {company.get('rocCode', 'N/A')}",
        f"Category: {company.get('category', 'N/A')}",
        f"Industry: {company.get('industry', 'N/A')}",
        f"Registered Address: {company.get('registeredAddress', 'N/A')}",
        f"Phone: {company.get('phone', 'N/A')}",
        f"Email: {company.get('email', 'N/A')}",
        f"Website: {company.get('website', 'N/A')}",
        f"Public Contact Summary: {build_company_contact_summary(company)}",
        f"Last AGM: {company.get('lastAGMDate', 'N/A')}",
        f"Last Balance Sheet: {company.get('lastBSDate', 'N/A')}",
        f"Authorised Capital: {company.get('authCap', 0)}",
        f"Paid Up Capital: {company.get('puc', 0)}",
        f"Source Section: {company.get('sourceSection', 'N/A')}",
        f"IBBI Snapshot Synced At: {company.get('snapshotSyncedAt', 'N/A')}",
        f"Profile Cached At: {company.get('profileCachedAt', 'N/A')}",
        "",
        "Overview:",
        clean_text(company.get("overview", "N/A")),
    ]
    if company.get("directors"):
        lines.extend(["", "Directors:"])
        for director in company["directors"][:10]:
            lines.append(
                f"- {director.get('name', 'N/A')} | {director.get('designation', 'N/A')} | {director.get('appointmentDate', 'N/A')}"
            )
    if company.get("news"):
        lines.extend(["", "Latest Updates:"])
        for item in company["news"][:10]:
            lines.append(f"- {item.get('date', 'N/A')} | {item.get('title', 'N/A')} | {item.get('source', 'N/A')}")
    return "\n".join(lines)


def attach_company_freshness(company: dict[str, Any], *, snapshot_synced_at: str, profile_cached_at: str) -> dict[str, Any]:
    enriched = dict(company)
    enriched["snapshotSyncedAt"] = snapshot_synced_at or "N/A"
    enriched["profileCachedAt"] = profile_cached_at or "N/A"
    enriched["profileCacheTtlSeconds"] = PROFILE_CACHE_TTL_SECONDS
    return enriched




def load_persisted_company_details() -> dict[str, dict[str, Any]]:
    if not COMPANY_DETAIL_STORE_PATH.exists():
        return {}
    try:
        with COMPANY_DETAIL_STORE_PATH.open("r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
        if not isinstance(payload, dict):
            return {}
        records: dict[str, dict[str, Any]] = {}
        for key, value in payload.items():
            if isinstance(key, str) and isinstance(value, dict):
                records[key] = value
        return records
    except Exception:
        return {}


class IBBIDataCache:
    def __init__(self) -> None:
        self._lock = Lock()
        self._companies: list[dict[str, Any]] = []
        self._stats: dict[str, Any] = {}
        self._recent_announcements: list[dict[str, Any]] = []
        self._last_refreshed = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-IN,en;q=0.9",
            }
        )
        self._master_companies: list[dict[str, Any]] = []
        self._profile_cache: dict[str, dict[str, Any]] = {}
        self._geocode_cache: dict[str, dict[str, Any]] = {}
        self._persisted_company_details: dict[str, dict[str, Any]] = load_persisted_company_details()

    def get_snapshot(self, force: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
        with self._lock:
            is_stale = (time.time() - self._last_refreshed) > CACHE_TTL_SECONDS
            if force or not self._companies or is_stale:
                self._refresh()
            return self._companies, self._stats, self._recent_announcements

    def _refresh(self) -> None:
        grouped: dict[str, list[dict[str, Any]]] = {}
        all_announcements: list[dict[str, Any]] = []
        professionals: set[str] = set()
        ibbi_error = ""

        try:
            response = self._session.get(IBBI_EXPORT_URL, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            text = response.content.decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(text), delimiter="\t")

            for raw_row in reader:
                row = normalize_keys(raw_row)
                announcement = build_announcement(row)
                key = announcement["cin"] if announcement["cin"] != "N/A" else slugify(announcement["debtorName"])
                grouped.setdefault(key, []).append(announcement)
                all_announcements.append(announcement)
                if announcement["insolvencyProfessional"] != "N/A":
                    professionals.add(announcement["insolvencyProfessional"])
        except Exception as error:
            ibbi_error = clean_text(str(error))

        companies = [build_company(history) for history in grouped.values()]
        companies = [attach_company_source_metadata(company) for company in companies]
        companies.sort(key=lambda item: (rank_company(item, item["name"])[1], clean_text(item["name"]).upper()), reverse=True)
        all_announcements.sort(key=lambda item: parse_date(item["announcementDate"]), reverse=True)

        self._companies = companies
        self._recent_announcements = [
            {
                "id": f"{announcement['id']}-{index}",
                "title": announcement["announcementType"],
                "source": "IBBI Public Announcement",
                "date": announcement["announcementDate"],
                "summary": (
                    f"{announcement['debtorName']} | Applicant: {announcement['applicantName']} | "
                    f"IP: {announcement['insolvencyProfessional']}"
                ),
                "url": announcement["registryUrl"],
                "companyId": announcement["cin"] if announcement["cin"] != "N/A" else slugify(announcement["debtorName"]),
            }
            for index, announcement in enumerate(all_announcements[:50])
        ]
        self._stats = {
            "totalAnnouncements": len(all_announcements),
            "totalCompanies": len(companies),
            "totalProfessionals": len(professionals),
            "ibbiStatus": "degraded" if ibbi_error else "ok",
            "ibbiError": ibbi_error,
            "lastSyncedAt": utc_now_iso(),
        }
        self._last_refreshed = time.time()

    def _persist_company_detail(self, company: dict[str, Any]) -> None:
        company_id = clean_text(company.get("id", "")).upper()
        company_cin = clean_text(company.get("cin", "")).upper()
        if not company_id and not company_cin:
            return

        record = dict(company)
        if company_id:
            self._persisted_company_details[company_id] = record
        if company_cin and company_cin != "N/A":
            self._persisted_company_details[company_cin] = record

        try:
            COMPANY_DETAIL_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with COMPANY_DETAIL_STORE_PATH.open("w", encoding="utf-8") as file_obj:
                json.dump(self._persisted_company_details, file_obj, ensure_ascii=False)
        except Exception:
            pass

    def _get_persisted_company_detail(self, company: dict[str, Any]) -> dict[str, Any] | None:
        company_id = clean_text(company.get("id", "")).upper()
        company_cin = clean_text(company.get("cin", "")).upper()
        persisted = None
        if company_id:
            persisted = self._persisted_company_details.get(company_id)
        if not persisted and company_cin and company_cin != "N/A":
            persisted = self._persisted_company_details.get(company_cin)
        return dict(persisted) if isinstance(persisted, dict) else None

    def enrich_company_profile(self, company: dict[str, Any], force: bool = False) -> dict[str, Any]:
        cache_key = clean_text(company.get("cin", "") or company.get("id", "")).upper()
        cached_at = utc_now_iso()
        if cache_key and cache_key in self._profile_cache and not force:
            cache_entry = self._profile_cache[cache_key]
            fetched_at = float(cache_entry.get("fetched_at", 0))
            if (time.time() - fetched_at) <= PROFILE_CACHE_TTL_SECONDS:
                cached_base = attach_company_source_metadata(cache_entry["data"])
                cached_company = attach_company_freshness(
                    cached_base,
                    snapshot_synced_at=self._stats.get("lastSyncedAt", "N/A"),
                    profile_cached_at=cache_entry.get("cached_at", "N/A"),
                )
                return cached_company

        enriched = attach_company_source_metadata(dict(company))
        enriched["documents"] = build_company_documents(enriched)
        enriched = attach_company_freshness(
            enriched,
            snapshot_synced_at=self._stats.get("lastSyncedAt", "N/A"),
            profile_cached_at=cached_at,
        )

        if cache_key:
            self._profile_cache[cache_key] = {
                "data": enriched,
                "fetched_at": time.time(),
                "cached_at": cached_at,
            }
        self._persist_company_detail(enriched)
        return enriched

    def search_claim_process(self, query: str, limit: int = 12) -> list[dict[str, str]]:
        response = self._session.get(
            IBBI_CLAIMS_SEARCH_URL,
            params={"corporate_debtor": clean_text(query)},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        rows = parse_claim_search_rows(response.text)
        return rows[:limit]

    def fetch_claims_company(self, identifier: str) -> dict[str, Any] | None:
        cleaned = clean_text(identifier)
        candidate_row: dict[str, str] | None = None

        if looks_like_cin(cleaned):
            version_response = self._session.get(
                f"{IBBI_CLAIMS_VERSION_URL}/{quote(cleaned.upper())}",
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if version_response.status_code != 200:
                return None
            version_html = version_response.text
            company_name_match = re.search(
                r"<li>\s*([^<]+)\s*</li>\s*<!--<div class=\"cinDetl\">",
                version_html,
                re.S | re.I,
            )
            company_name = clean_text(company_name_match.group(1)) if company_name_match else cleaned.upper()
            version_rows = parse_claim_version_rows(version_html)
            if not version_rows:
                return None
            latest_version = version_rows[0]
            candidate_row = {
                "cin": cleaned.upper(),
                "name": company_name,
                "ip_name": latest_version["rp_name"],
                "under_process": "CIRP",
                "latest_claim_date": latest_version["version_date"],
                "detail_id": latest_version["detail_id"],
            }
        else:
            rows = self.search_claim_process(cleaned, limit=10)
            if not rows:
                return None
            ranked_rows = sorted(
                rows,
                key=lambda row: (
                    200 if clean_text(row["name"]).upper() == cleaned.upper() else 0,
                    150 if clean_text(row["name"]).upper().startswith(cleaned.upper()) else 0,
                    100 if cleaned.upper() in clean_text(row["name"]).upper() else 0,
                    parse_date(row["latest_claim_date"]),
                    clean_text(row["name"]).upper(),
                ),
                reverse=True,
            )
            candidate_row = ranked_rows[0]
            version_response = self._session.get(
                f"{IBBI_CLAIMS_VERSION_URL}/{quote(candidate_row['cin'])}",
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            version_response.raise_for_status()
            version_html = version_response.text
            version_rows = parse_claim_version_rows(version_html)
            if version_rows:
                candidate_row["detail_id"] = version_rows[0]["detail_id"]
                candidate_row["ip_name"] = version_rows[0]["rp_name"] or candidate_row["ip_name"]
                candidate_row["latest_claim_date"] = version_rows[0]["version_date"] or candidate_row["latest_claim_date"]

        if not candidate_row:
            return None

        detail_id = candidate_row.get("detail_id")
        details: dict[str, str] = {}
        if detail_id:
            detail_response = self._session.get(
                f"{IBBI_CLAIMS_DETAIL_URL}/{quote(detail_id)}",
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if detail_response.status_code == 200:
                details = parse_claim_detail_inputs(detail_response.text)

        company = build_claims_company_from_search_row(candidate_row)
        commencement_label = next(
            (label for label in details if label.lower().startswith("date of commencement of")),
            "",
        )
        commencement_date = details.get(commencement_label, "") if commencement_label else ""
        claim_list_date = details.get("List of Claim as on date", "")
        company["status"] = "Liquidation" if "liquidation" in commencement_label.lower() or clean_text(candidate_row["under_process"]).lower() == "liquidation" else "Under CIRP"
        company["category"] = f"IBBI Claims Process - {clean_text(candidate_row['under_process']) or company['status']}"
        company["announcementType"] = company["category"]
        company["announcementDate"] = claim_list_date or candidate_row["latest_claim_date"] or commencement_date or "N/A"
        company["announcementDateIso"] = to_iso_date(company["announcementDate"])
        company["commencement_date"] = commencement_date or "N/A"
        company["last_date_claims"] = claim_list_date or candidate_row["latest_claim_date"] or "N/A"
        company["lastDateOfSubmission"] = company["last_date_claims"]
        company["lastDateOfSubmissionIso"] = to_iso_date(company["last_date_claims"])
        company["ip_name"] = details.get("Name of IP", candidate_row["ip_name"]) or "N/A"
        company["applicant_name"] = details.get("Name of Applicant", "N/A")
        company["overview"] = (
            f"{company['name']} appears in the IBBI claims process listing. "
            f"Process: {clean_text(candidate_row['under_process']) or company['status']}. "
            f"Latest claim list date: {company['announcementDate']}."
        )
        company["registryUrl"] = build_claims_registry_url(company["cin"])
        company["remarks"] = "Source: IBBI claims process listing and latest claim-details page."
        company["sourceSection"] = "claims"
        company["announcementHistory"] = [
            {
                "id": company["id"],
                "announcementType": company["announcementType"],
                "announcementDate": company["announcementDate"],
                "announcementDateIso": company["announcementDateIso"],
                "lastDateOfSubmission": company["lastDateOfSubmission"],
                "lastDateOfSubmissionIso": company["lastDateOfSubmissionIso"],
                "debtorName": company["name"],
                "cin": company["cin"],
                "applicantName": company["applicant_name"],
                "insolvencyProfessional": company["ip_name"],
                "insolvencyProfessionalAddress": company["insolvencyProfessionalAddress"],
                "remarks": company["remarks"],
                "status": company["status"],
                "registryUrl": company["registryUrl"],
            }
        ]
        return attach_company_source_metadata(company)


cache = IBBIDataCache()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stats")
def get_stats() -> dict[str, Any]:
    _, stats, _ = cache.get_snapshot()
    return stats


@app.get("/featured")
def get_featured_companies(limit: int = Query(default=10, ge=1, le=20)) -> list[dict[str, Any]]:
    companies, _, _ = cache.get_snapshot()
    return companies[:limit]


@app.get("/recent-announcements")
def get_recent_announcements(limit: int = Query(default=18, ge=1, le=50)) -> list[dict[str, Any]]:
    _, _, announcements = cache.get_snapshot()
    return announcements[:limit]


@app.get("/search")
def search_realtime(
    q: str = Query(min_length=2),
    limit: int = Query(default=12, ge=1, le=50),
    status: str = Query(default=""),
    type: str = Query(default=""),
    source: str = Query(default=""),
    fresh: bool = Query(default=False),
) -> list[dict[str, Any]]:
    companies, _, _ = cache.get_snapshot(force=fresh)
    query = clean_text(q)
    matches = [
        company
        for company in companies
        if rank_company(company, query)[0] > 0
        and matches_company_filters(company, status=status, company_type=type, source=source)
    ]

    try:
        claims_rows = cache.search_claim_process(query, limit=limit)
    except Exception:
        claims_rows = []

    existing_ids = {clean_text(company["id"]).upper() for company in matches}
    existing_ids.update(clean_text(company["cin"]).upper() for company in matches if company.get("cin"))
    for row in claims_rows:
        cin = clean_text(row["cin"]).upper()
        if cin and cin not in existing_ids:
            matches.append(attach_company_source_metadata(build_claims_company_from_search_row(row)))

    matches.sort(key=lambda company: rank_company(company, query), reverse=True)
    return matches[:limit]


@app.get("/companies")
def list_companies(
    q: str = Query(default=""),
    status: str = Query(default=""),
    type: str = Query(default=""),
    source: str = Query(default=""),
    limit: int = Query(default=40, ge=1, le=200),
    fresh: bool = Query(default=False),
) -> list[dict[str, Any]]:
    companies, _, _ = cache.get_snapshot(force=fresh)
    query = clean_text(q)

    filtered = [
        company
        for company in companies
        if matches_company_filters(company, status=status, company_type=type, source=source)
        and (not query or rank_company(company, query)[0] > 0)
    ]
    filtered.sort(
        key=lambda company: rank_company(company, query or company["name"]),
        reverse=True,
    )
    return filtered[:limit]


@app.get("/company/{id_or_cin}")
def get_company(id_or_cin: str, fresh: bool = Query(default=False)) -> dict[str, Any]:
    companies, _, _ = cache.get_snapshot(force=fresh)
    target = clean_text(id_or_cin).upper()

    for company in companies:
        if company["id"].upper() == target or company["cin"].upper() == target or slugify(company["name"]).upper() == target:
            return cache.enrich_company_profile(attach_company_source_metadata(company), force=fresh)

    claims_company = cache.fetch_claims_company(id_or_cin)
    if claims_company:
        return cache.enrich_company_profile(claims_company, force=fresh)

    raise HTTPException(status_code=404, detail="Company profile not found on IBBI.")


@app.get("/company/{id_or_cin}/documents/profile.json")
def download_company_profile_json(id_or_cin: str) -> JSONResponse:
    company = get_company(id_or_cin)
    safe_name = f"{slugify(company['name'])}-profile.json"
    return JSONResponse(
        content=company,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.get("/company/{id_or_cin}/documents/summary.txt")
def download_company_summary_text(id_or_cin: str) -> PlainTextResponse:
    company = get_company(id_or_cin)
    safe_name = f"{slugify(company['name'])}-summary.txt"
    return PlainTextResponse(
        build_company_summary_text(company),
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.get("/sources")
def list_sources() -> list[dict[str, str]]:
    return [
        {
            "id": "ibbi_public_announcement",
            "name": "IBBI Public Announcement",
            "portalType": "government",
            "mode": "live-scrape",
            "url": IBBI_PUBLIC_ANNOUNCEMENT_URL,
        },
        {
            "id": "ibbi_claims",
            "name": "IBBI Claims Process",
            "portalType": "government",
            "mode": "live-scrape",
            "url": IBBI_CLAIMS_SEARCH_URL,
        },
    ]


@app.get("/company/{id_or_cin}/sources")
def get_company_sources(id_or_cin: str, fresh: bool = Query(default=False)) -> list[dict[str, str]]:
    company = get_company(id_or_cin, fresh=fresh)
    return company.get("dataSources", [])


@app.get("/refresh")
def refresh_cache() -> dict[str, Any]:
    companies, stats, announcements = cache.get_snapshot(force=True)
    return {
        "status": "refreshed",
        "companies": len(companies),
        "announcements": len(announcements),
        "lastSyncedAt": stats["lastSyncedAt"],
    }


if __name__ == "__main__":
    print("fintech API starting on http://localhost:8005")
    uvicorn.run(app, host="0.0.0.0", port=8005)
