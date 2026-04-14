from __future__ import annotations

import asyncio
import concurrent.futures
import csv
import hashlib
import io
import json
import os
import random
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
import base64
from ibbi_selenium_scraper import scrape_ibbi_claims_with_selenium

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from dotenv import load_dotenv
from auth import auth_router
import db as db_module

# ── Load environment variables ──────────────────────────────────────────────
load_dotenv()

IBBI_EXPORT_URL = "https://ibbi.gov.in/public-announcement?ann=&title=&date=&export_excel=export_excel"
IBBI_PUBLIC_ANNOUNCEMENT_URL = "https://ibbi.gov.in/en/public-announcement"
IBBI_CLAIMS_SEARCH_URL = "https://ibbi.gov.in/claims/claim-process"
IBBI_CLAIMS_VERSION_URL = "https://ibbi.gov.in/claims/version-details"
IBBI_CLAIMS_DETAIL_URL = "https://ibbi.gov.in/claims/frontClaimDetails"
IBBI_CLAIMS_INNER_PROCESS_URL = "https://ibbi.gov.in/claims/innerProcess"
IBBI_CLAIMS_AJAX_URL = "https://ibbi.gov.in/claims/front-claim-details-ajax"
IBBI_CLAIMS_PUBLIC_PROCESS_URL = "https://ibbi.gov.in/claims/pubProcess"
IBBI_CLAIMS_PROCESS_LIST_URL = "https://ibbi.gov.in/claims/claimProcess"
IBBI_CLAIMS_RP_PROCESS_URL = "https://ibbi.gov.in/claims/rpProcess"
IBBI_CLAIMS_ORDER_PROCESS_URL = "https://ibbi.gov.in/claims/orderProcess"
IBBI_CLAIMS_AUCTION_NOTICE_PROCESS_URL = "https://ibbi.gov.in/claims/auctionNoticeProcess"
IBBI_PRESS_RELEASES_URL = "https://ibbi.gov.in/media/press-releases"
IBBI_IP_REGISTER_URL = "https://ibbi.gov.in/ips-register/view-ip/1"
IBBI_IP_DETAILS_URL = "https://ibbi.gov.in/insolvency-professional/details"

# ── Claims Category Mapping for Deep Scraping (IBBI Form Mapping) ─────────────
CLAIMS_CATEGORY_MAPPINGS = {
    "secured financial creditors": 3,
    "unsecured financial creditors": 4,
    "operational creditors (workmen)": 5,
    "operational creditors (employees)": 6,
    "operational creditors (government dues)": 7,
    "operational creditors (other than workmen, employees and government dues)": 8,
    "other stakeholders": 9,
}

BASE_DIR = Path(__file__).resolve().parent
COMPANY_DETAIL_STORE_PATH = BASE_DIR.parent / "database" / "company_details_store.json"
CACHE_TTL_SECONDS = 5 * 60
PROFILE_CACHE_TTL_SECONDS = 30 * 60
REQUEST_TIMEOUT_SECONDS = 45
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080").strip()
ALLOWED_ORIGINS = [
    FRONTEND_URL,
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8081",
    "http://127.0.0.1:5173",
]

app = FastAPI(title="fintech API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True, # Changed to True to support auth if needed
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
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


def extract_pdf_url_from_onclick(value: str, base_url: str = IBBI_PUBLIC_ANNOUNCEMENT_URL) -> str:
    text = clean_text(value)
    if not text:
        return ""
    match = re.search(r"""['"]\s*([^'"]+?\.pdf[^'"]*)\s*['"]""", text, re.I)
    if not match:
        return ""
    return clean_text(urljoin(base_url, match.group(1)))


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


def parse_public_announcement_rows(html: str, base_url: str = IBBI_PUBLIC_ANNOUNCEMENT_URL) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return rows

    headers = [clean_text(th.get_text(" ", strip=True)) for th in table.find_all("th")]
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells or len(cells) != len(headers):
            continue
        row: dict[str, str] = {}
        for header, cell in zip(headers, cells):
            row[header] = clean_text(cell.get_text(" ", strip=True))
            anchor = cell.find("a", href=True)
            onclick = clean_text(anchor.get("onclick", "")) if anchor else ""
            href = clean_text(anchor.get("href", "")) if anchor else ""
            if header.lower() == "public announcement":
                document_url = extract_pdf_url_from_onclick(onclick, base_url=base_url)
                if not document_url and href and href.lower() != "javascript:void(0)":
                    document_url = clean_text(urljoin(base_url, href))
                row["Public Announcement Url"] = document_url
        rows.append(row)
    return rows


def build_announcement(row: dict[str, str]) -> dict[str, Any]:
    announcement_type = find_first_value(row, "Announcement Type", "Type of PA")
    announcement_date = find_first_value(row, "Date of Announcement")
    last_date = find_first_value(row, "Last date of Submission")
    debtor_name = find_first_value(row, "Name of Corporate Debtor")
    cin = find_first_value(row, "CIN No.", "CIN No", "CIN")
    applicant_name = find_first_value(row, "Name of Applicant")
    insolvency_professional = find_first_value(row, "Name of Insolvency Professional")
    document_url = find_first_value(row, "Public Announcement Url")

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
        "insolvencyProfessionalAddress": find_first_value(row, "Address of Insolvency Professional") or "N/A",
        "remarks": find_first_value(row, "Remarks") or "No remarks published by IBBI.",
        "status": derive_status(announcement_type),
        "registryUrl": build_registry_url(cin or debtor_name),
        "documentUrl": document_url,
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



def parse_claim_summary_table(html: str) -> list[dict]:
    """Extracts summary table from claims details."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"class": "table"}) or soup.find("table")
    if not table: return []
    rows = []
    header_found = False
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells: continue
        texts = [c.get_text(" ", strip=True).strip() for c in cells]
        if "Category" in " ".join(texts):
            header_found = True
            continue
        if header_found and len(texts) >= 3:
            rows.append({
                "srNo": texts[0],
                "category": texts[1],
                "receivedCount": texts[2] if len(texts) > 2 else "0",
                "receivedAmount": texts[3] if len(texts) > 3 else "0",
                "admittedCount": texts[4] if len(texts) > 4 else "0",
                "admittedAmount": texts[5] if len(texts) > 5 else "0",
            })
    return rows


def parse_claim_detail_inputs(html: str) -> dict[str, str]:
    values: dict[str, str] = {}
    pattern = re.compile(r"<label>(.*?)</label>.*?<input[^>]*value=\"(.*?)\"", re.S | re.I)
    for label, value in pattern.findall(html):
        values[clean_text(label)] = clean_text(value)
    return values


def scrape_claim_category_details(session: requests.Session, detail_id: str, category_type: int, referer: str) -> list[dict[str, Any]]:
    """Fetches detailed creditor lists for a specific category via IBBI AJAX POST with session awareness."""
    url = IBBI_CLAIMS_AJAX_URL
    payload = {
        "pubProcessId": detail_id,
        "type": category_type,
        "id": detail_id
    }
    
    # Headers required to bypass 403 Forbidden
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": referer,
        "Origin": "https://ibbi.gov.in"
    }

    try:
        resp = session.post(url, data=payload, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  AJAX Error: {resp.status_code} for Type {category_type}")
            return []
        
        # Parse JSON response
        try:
            json_data = resp.json()
            if isinstance(json_data, list):
                return json_data
            if isinstance(json_data, dict) and "data" in json_data:
                return json_data["data"]
        except:
            # Fallback to HTML parsing if they return a partial table
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table")
            if not table:
                return []

            headers_list = []
            thead = table.find("thead") or table.find("tr")
            if thead:
                headers_list = [clean_text(th.get_text(" ", strip=True)) for th in thead.find_all(["th", "td"])]

            rows = []
            tbody = table.find("tbody")
            tr_list = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

            for tr in tr_list:
                cells = tr.find_all(["td", "th"])
                if len(cells) >= len(headers_list) and headers_list:
                    row_data = {}
                    for i, h in enumerate(headers_list):
                        if i < len(cells):
                            val = clean_text(cells[i].get_text(" ", strip=True))
                            row_data[h] = val
                    if any(row_data.values()):
                        rows.append(row_data)
            return rows
    except Exception as e:
        print(f"Error scraping claim category {category_type} (POST): {e}")
        return []


def build_claims_registry_url(cin: str) -> str:
    return f"{IBBI_CLAIMS_VERSION_URL}/{quote(cin)}"


def build_claims_process_url(base_url: str, cin: str) -> str:
    return f"{base_url}/{quote(cin)}"


def normalize_process_status(value: str, fallback: str = "Under CIRP") -> str:
    cleaned = clean_text(value).lower()
    if "liquid" in cleaned:
        return "Liquidation"
    if "cirp" in cleaned or "resolution" in cleaned or "irp" in cleaned or "rp" in cleaned:
        return "Under CIRP"
    if "dissolv" in cleaned:
        return "Dissolved"
    return fallback


def parse_process_detail_rows(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    rows: list[dict[str, str]] = []
    if not table:
        return rows

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        label = clean_text(cells[0].get_text(" ", strip=True))
        value = clean_text(cells[1].get_text(" ", strip=True))
        if label:
            rows.append(
                {
                    "id": slugify(label),
                    "label": label,
                    "value": value or "N/A",
                }
            )
    return rows


def parse_process_table_rows(
    html: str,
    *,
    base_url: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return [], []

    headers = [clean_text(th.get_text(" ", strip=True)) for th in table.find_all("th")]
    rows: list[dict[str, Any]] = []
    for row_index, tr in enumerate(table.find_all("tr")[1:], start=1):
        cells = tr.find_all("td")
        if not cells or (headers and len(cells) < len(headers)):
            continue
        values: dict[str, str] = {}
        links: dict[str, str] = {}
        for column_index, cell in enumerate(cells[: len(headers)]):
            header = headers[column_index]
            values[header] = clean_text(cell.get_text(" ", strip=True))
            anchor = cell.find("a", href=True)
            href = clean_text(anchor.get("href", "")) if anchor else ""
            onclick = clean_text(anchor.get("onclick", "")) if anchor else ""
            link_url = extract_pdf_url_from_onclick(onclick, base_url=base_url)
            if not link_url and href and href.lower() != "javascript:void(0)":
                link_url = clean_text(urljoin(base_url, href))
            if link_url:
                links[header] = link_url
        rows.append(
            {
                "id": f"row-{row_index}",
                "values": values,
                "links": links,
            }
        )
    return headers, rows


def extract_process_pdf_documents(company: dict[str, Any]) -> list[dict[str, Any]]:
    process_sections = company.get("corporateProcesses", {}) if isinstance(company.get("corporateProcesses"), dict) else {}
    current_year = datetime.utcnow().year
    filing_date = normalize_display_date(company.get("announcementDate") or company.get("lastUpdatedOn") or "N/A")
    documents: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for section in process_sections.values():
        if not isinstance(section, dict):
            continue
        title = clean_text(section.get("title", "Corporate Process"))
        for row in section.get("rows", []):
            if not isinstance(row, dict):
                continue
            links = row.get("links", {})
            values = row.get("values", {})
            if not isinstance(links, dict) or not isinstance(values, dict):
                continue
            for column_name, link_url in links.items():
                cleaned_url = clean_text(link_url)
                if not is_probable_pdf_url(cleaned_url) or cleaned_url in seen_urls:
                    continue
                seen_urls.add(cleaned_url)
                label_hint = clean_text(values.get(column_name, ""))
                file_label = slugify(f"{title}-{column_name}-{label_hint or cleaned_url}")[:60] or "source-document"
                documents.append(
                    {
                        "formId": f"PROCESS_{slugify(title).upper()}_{len(documents) + 1}",
                        "fileName": f"{file_label}.pdf",
                        "year": current_year,
                        "dateOfFiling": filing_date,
                        "category": title,
                        "source": "IBBI Corporate Processes",
                        "fileType": "pdf",
                        "url": cleaned_url,
                        "downloadUrl": cleaned_url,
                    }
                )
    return documents


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
            "fileType": "json",
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
            "fileType": "txt",
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
                "fileType": "html",
                "url": company["registryUrl"],
                "downloadUrl": company["registryUrl"],
            }
        )

    discovered_pdf_urls: set[str] = set()
    for announcement in company.get("announcementHistory") or []:
        for url in [
            announcement.get("registryUrl", ""),
            announcement.get("remarks", ""),
            announcement.get("documentUrl", ""),
        ]:
            for extracted_url in extract_urls(url):
                if is_probable_pdf_url(extracted_url):
                    discovered_pdf_urls.add(extracted_url)
            if is_probable_pdf_url(url):
                discovered_pdf_urls.add(clean_text(url))

    for pdf_index, pdf_url in enumerate(sorted(discovered_pdf_urls), start=1):
        documents.append(
            {
                "formId": f"SOURCE_PDF_{pdf_index}",
                "fileName": f"source-document-{pdf_index}.pdf",
                "year": current_year,
                "dateOfFiling": normalize_display_date(company.get("announcementDate") or company.get("lastUpdatedOn") or "N/A"),
                "category": "Source PDF",
                "source": "IBBI Public Announcement",
                "fileType": "pdf",
                "url": pdf_url,
                "downloadUrl": pdf_url,
            }
        )

    documents.extend(extract_process_pdf_documents(company))

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


def company_identifier_tokens(company: dict[str, Any]) -> set[str]:
    values = {
        clean_text(company.get("id", "")).upper(),
        clean_text(company.get("cin", "")).upper(),
        clean_text(company.get("name", "")).upper(),
        slugify(company.get("name", "")).upper(),
    }
    return {value for value in values if value and value != "N/A"}


def filter_announcements_for_company(
    announcements: list[dict[str, Any]],
    company: dict[str, Any],
) -> list[dict[str, Any]]:
    tokens = company_identifier_tokens(company)
    filtered: list[dict[str, Any]] = []
    for announcement in announcements:
        candidate_tokens = {
            clean_text(announcement.get("cin", "")).upper(),
            clean_text(announcement.get("debtorName", "")).upper(),
            slugify(announcement.get("debtorName", "")).upper(),
        }
        if tokens.intersection({token for token in candidate_tokens if token and token != "N/A"}):
            filtered.append(announcement)
    return filtered


def merge_company_with_live_announcements(
    company: dict[str, Any],
    live_announcements: list[dict[str, Any]],
) -> dict[str, Any]:
    matching_announcements = filter_announcements_for_company(live_announcements, company)
    if not matching_announcements:
        return company

    live_company = build_company(matching_announcements)
    merged = dict(company)
    for field in (
        "status",
        "category",
        "overview",
        "applicant_name",
        "ip_name",
        "commencement_date",
        "last_date_claims",
        "announcementType",
        "announcementDate",
        "announcementDateIso",
        "lastDateOfSubmission",
        "lastDateOfSubmissionIso",
        "insolvencyProfessionalAddress",
        "remarks",
        "registryUrl",
        "announcementCount",
        "announcementHistory",
        "applicants",
        "insolvencyProfessionals",
    ):
        merged[field] = live_company.get(field, merged.get(field))
    merged["sourceSection"] = "ibbi"
    return merged


def attach_corporate_process_data(company: dict[str, Any], process_data: dict[str, Any]) -> dict[str, Any]:
    if not process_data:
        return company

    enriched = dict(company)
    enriched["corporateProcesses"] = process_data

    details_section = process_data.get("detailsAboutCd", {})
    detail_rows = details_section.get("rows", []) if isinstance(details_section, dict) else []
    detail_map = {
        clean_text(row.get("label", "")).lower(): clean_text(row.get("value", ""))
        for row in detail_rows
        if isinstance(row, dict)
    }

    if detail_map.get("name of the corporate debtor"):
        enriched["name"] = detail_map["name of the corporate debtor"]
    if detail_map.get("process initiated"):
        enriched["status"] = normalize_process_status(detail_map["process initiated"], fallback=enriched.get("status", "Under CIRP"))
        enriched["category"] = sanitize_public_value(detail_map["process initiated"])
    if detail_map.get("name of the applicant"):
        enriched["applicant_name"] = detail_map["name of the applicant"]
    if detail_map.get("name of insolvency professional / liquidator"):
        enriched["ip_name"] = detail_map["name of insolvency professional / liquidator"]
    if detail_map.get("address of insolvency professional / liquidator"):
        enriched["insolvencyProfessionalAddress"] = detail_map["address of insolvency professional / liquidator"]
    if detail_map.get("cin no."):
        enriched["cin"] = detail_map["cin no."]

    # ── Inject extra rows for Capital if missing ──
    if "authorized capital" not in detail_map and enriched.get("authCap"):
        detail_rows.append({"id": "auth-cap", "label": "Authorized Capital", "value": str(enriched["authCap"])})
    if "paid up capital" not in detail_map and enriched.get("puc"):
        detail_rows.append({"id": "puc-cap", "label": "Paid up Capital", "value": str(enriched["puc"])})


    public_section = process_data.get("publicAnnouncement", {})
    public_rows = public_section.get("rows", []) if isinstance(public_section, dict) else []
    announcement_history: list[dict[str, Any]] = []
    for index, row in enumerate(public_rows, start=1):
        if not isinstance(row, dict):
            continue
        values = row.get("values", {})
        links = row.get("links", {})
        if not isinstance(values, dict):
            continue
        normalized_row = {
            "Type of PA": values.get("Public Announcement Type", ""),
            "Date of Announcement": values.get("Date of Announcement", ""),
            "Last date of Submission": values.get("Last date of Submission", ""),
            "Name of Corporate Debtor": enriched.get("name", ""),
            "Name of Applicant": values.get("Name of Applicant", ""),
            "Name of Insolvency Professional": values.get("Name of Insolvency Professional", ""),
            "Address of Insolvency Professional": values.get("Address of Insolvency Professional", ""),
            "Remarks": values.get("Remarks", ""),
            "Public Announcement Url": links.get("Public Announcement", ""),
            "CIN No.": enriched.get("cin", ""),
        }
        announcement = build_announcement(normalized_row)
        announcement["id"] = f"{announcement['id']}-{index}"
        announcement_history.append(announcement)
    if announcement_history:
        announcement_history.sort(key=lambda item: parse_date(item["announcementDate"]), reverse=True)
        latest = announcement_history[0]
        enriched["announcementHistory"] = announcement_history
        enriched["announcementCount"] = len(announcement_history)
        enriched["announcementType"] = latest["announcementType"]
        enriched["announcementDate"] = latest["announcementDate"]
        enriched["announcementDateIso"] = latest["announcementDateIso"]
        enriched["lastDateOfSubmission"] = latest["lastDateOfSubmission"]
        enriched["lastDateOfSubmissionIso"] = latest["lastDateOfSubmissionIso"]
        enriched["applicant_name"] = latest["applicantName"] or enriched.get("applicant_name", "N/A")
        enriched["ip_name"] = latest["insolvencyProfessional"] or enriched.get("ip_name", "N/A")
        enriched["insolvencyProfessionalAddress"] = latest["insolvencyProfessionalAddress"] or enriched.get(
            "insolvencyProfessionalAddress", "N/A"
        )
        enriched["remarks"] = latest["remarks"]
        enriched["registryUrl"] = clean_text(public_section.get("url", "")) or enriched.get("registryUrl", "")
        enriched["status"] = latest["status"] or enriched.get("status", "Under CIRP")
        enriched["category"] = latest["announcementType"] or enriched.get("category", "N/A")
        enriched["applicants"] = sorted({item["applicantName"] for item in announcement_history if item["applicantName"] != "N/A"})
        enriched["insolvencyProfessionals"] = sorted(
            {item["insolvencyProfessional"] for item in announcement_history if item["insolvencyProfessional"] != "N/A"}
        )
        enriched["overview"] = (
            f"{enriched['name']} appears in {len(announcement_history)} IBBI corporate-process public announcement"
            f"{'' if len(announcement_history) == 1 else 's'}. Latest update: {latest['announcementType']} on "
            f"{latest['announcementDate'] or 'date not published'}."
        )

    claims_section = process_data.get("claims", {})
    claim_rows = claims_section.get("rows", []) if isinstance(claims_section, dict) else []
    if claim_rows:
        latest_claim_row = claim_rows[0]
        values = latest_claim_row.get("values", {}) if isinstance(latest_claim_row, dict) else {}
        if isinstance(values, dict):
            enriched["last_date_claims"] = values.get("Latest Claim As On Date", enriched.get("last_date_claims", "N/A"))
            enriched["lastDateOfSubmission"] = enriched["last_date_claims"]
            enriched["lastDateOfSubmissionIso"] = to_iso_date(enriched["last_date_claims"])
            enriched["ip_name"] = values.get("Name of IRP / RP / Liquidator", enriched.get("ip_name", "N/A"))
            
        # ── Extract IBBI Charges from Claims Section ──
        # Secured Financial Creditors are essentially the charges
        charges = []
        for row in claim_rows:
            vals = row.get("values", {})
            cat = clean_text(vals.get("Category of stakeholders", "")).lower()
            if "secured" in cat and "financial" in cat:
                charges.append({
                    "chargeId": f"IBBI-{slugify(cat)[:10]}-{len(charges)+1}",
                    "bankName": vals.get("Category of stakeholders", "Financial Creditor"),
                    "amount": 0, 
                    "admittedAmount": 0,
                    "status": "In Process",
                    "creationDate": enriched.get("announcementDate", "N/A"),
                    "assetsSecured": "Corporate Assets",
                    "details": f"Claims Received: {vals.get('No. of Claims', '0')}, Amount: {vals.get('Amount (Rs.)', '0')}"
                })
        if charges:
            enriched["charges"] = charges

    # ── Extract Directors from Corporate Personals Section ──
    personals_section = process_data.get("corporatePersonals", {})
    personal_rows = personals_section.get("rows", []) if isinstance(personals_section, dict) else []
    if personal_rows:
        directors = []
        for row in personal_rows:
            vals = row.get("values", {})
            # Official header is "Name of Corporate Personal"
            name = clean_text(vals.get("Name of Corporate Personal", vals.get("Name", "")))
            if name:
                directors.append({
                    "id": f"dir-{slugify(name)}",
                    "name": name,
                    "designation": clean_text(vals.get("Designation", "Director")),
                    "date_of_appointment": clean_text(vals.get("Date of Appointment", vals.get("Appointment Date", "N/A"))),
                    "is_active": True,
                    "din": clean_text(vals.get("DIN", "N/A"))
                })
        if directors:
            enriched["directors"] = directors

    return attach_company_source_metadata(enriched)


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


def inject_simulated_data(company: dict[str, Any]) -> None:
    print(f"[SIMULATED] Generating financial metrics and charges for: {company.get('name', 'N/A')}")
    cin_val = company.get("cin")
    if not cin_val or cin_val == "N/A":
        seed_str = (company.get("id") or "default").upper()
    else:
        seed_str = cin_val.upper()
        
    seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    r = random.Random(seed)
    
    # 2. Simulate Charges
    if not company.get("charges") and r.random() > 0.3:
        num_charges = r.randint(1, 4)
        banks = ["State Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank", "Punjab National Bank", "Bank of Baroda", "Kotak Mahindra Bank"]
        charges = []
        for _ in range(num_charges):
            amount = r.randint(10_000_000, 5_000_000_000)
            charge_year = r.randint(2015, 2023)
            charges.append({
                "chargeId": f"CHG{r.randint(10000, 99999)}",
                "bankName": r.choice(banks),
                "amount": amount,
                "status": "Open" if r.random() > 0.4 else "Closed",
                "creationDate": f"{r.randint(1, 28):02d}-{r.randint(1, 12):02d}-{charge_year}",
                "modificationDate": f"{r.randint(1, 28):02d}-{r.randint(1, 12):02d}-{charge_year + r.randint(0, 1)}",
                "assetsSecured": r.choice(["Immovable property", "Book debts", "Movables", "Entire assets"])
            })
        charges.sort(key=lambda x: x["amount"], reverse=True)
        company["charges"] = charges

    # 3. Update Placeholders for financials (rounded to nearest 10 Lakhs)
    auth_cap = r.randint(10, 1000) * 1_000_000 
    company["authCap"] = auth_cap
    company["puc"] = int(r.randint(1, auth_cap // 1_000_000) * 1_000_000) if auth_cap > 0 else 0

    if not company.get("incorporationDate") or company.get("incorporationDate") == "N/A":
        company["incorporationDate"] = f"{r.randint(1, 28):02d}-{r.randint(1, 12):02d}-{r.randint(1990, 2018)}"
    company["lastAGMDate"] = f"{r.randint(1, 28):02d}-{r.randint(6, 12):02d}-{r.randint(2020, 2023)}"
    company["lastBSDate"] = f"31-03-{r.randint(2020, 2023)}"

    # 5. Build AI Insight Summary
    num_announcements = len(company.get("announcementHistory", []))
    company_status = company.get("status", "Unknown")
    risk_score = "High" if company_status in ["Liquidation", "Dissolved"] else ("Medium" if company_status == "Under CIRP" else "Low")
    insight_parts = [
        f"**[AI RISK INSIGHT]** The system evaluates this company with a **{risk_score.upper()} Risk Profile** due to its '{company_status}' status."
    ]
    if num_announcements > 0:
        insight_parts.append(f"It has {num_announcements} recorded announcements indicating sustained proceedings.")
    if company.get("charges"):
        insight_parts.append(f"There are {len(company.get('charges', []))} associated financial charges highlighting secured creditor involvement.")
    
    current_overview = company.get("overview", "")
    if "[AI RISK INSIGHT]" not in current_overview:
        company["overview"] = " ".join(insight_parts) + "\n\n" + current_overview






class SyncManager:
    """Manages background synchronization and batch enrichment of companies."""
    def __init__(self, cache_ref: 'IBBIDataCache'):
        self.cache = cache_ref
        self.active_job: dict[str, Any] | None = None
        self.logs: list[dict] = []
        self._lock = Lock()
        self.log_path = BASE_DIR.parent / "database" / "sync_logs.json"
        self._load_logs()

    def _load_logs(self):
        if self.log_path.exists():
            try:
                with open(self.log_path, 'r') as f:
                    data = json.load(f)
                    self.logs = data if isinstance(data, list) else []
            except Exception: self.logs = []

    def _save_logs(self):
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, 'w') as f:
                json.dump(self.logs[-50:], f, indent=2)
        except Exception: pass

    def start_full_sync(self):
        with self._lock:
            if self.active_job and self.active_job['status'] == 'running':
                return self.active_job
            
            self.active_job = {
                "id": f"sync-{int(time.time())}",
                "status": "running",
                "progress": 0,
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "startTime": utc_now_iso(),
                "endTime": None,
                "message": "Initializing full sync..."
            }
            import threading
            threading.Thread(target=self._run_sync, daemon=True).start()
            return self.active_job

    def get_status(self):
        with self._lock:
            return {
                "activeJob": self.active_job,
                "recentLogs": self.logs[-10:]
            }

    def _run_sync(self):
        try:
            # 1. Refresh background announcement snapshot first (fast)
            print("[SYNC] Starting announcement snapshot refresh...")
            self.cache.get_snapshot(force=True)
            companies = self.cache._companies
            
            if not companies:
                raise Exception("No companies found to sync.")

            with self._lock:
                self.active_job['total'] = len(companies)
                self.active_job['message'] = f"Syncing {len(companies)} companies..."

            # 2. Batch process enrichment
            batch_size = 4 # Conservative batch size
            for i in range(0, len(companies), batch_size):
                batch = companies[i:i+batch_size]
                futures = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
                    for company in batch:
                        futures.append(executor.submit(self._enrich_if_needed, company))
                    
                    for future in concurrent.futures.as_completed(futures):
                        res = future.result()
                        with self._lock:
                            self.active_job['progress'] += 1
                            if res == 'success': self.active_job['success'] += 1
                            elif res == 'skipped': self.active_job['skipped'] += 1
                            else: self.active_job['failed'] += 1
                
                # Small pause between batches to avoid IP rate limiting
                time.sleep(1.0)

            with self._lock:
                self.active_job['status'] = 'completed'
                self.active_job['endTime'] = utc_now_iso()
                self.active_job['message'] = f"Completed: {self.active_job['success']} enriched, {self.active_job['skipped']} skipped."
                self.logs.append(dict(self.active_job))
                self._save_logs()

        except Exception as e:
            with self._lock:
                self.active_job['status'] = 'failed'
                self.active_job['endTime'] = utc_now_iso()
                self.active_job['message'] = f"Critical sync failure: {str(e)}"
                self.logs.append(dict(self.active_job))
                self._save_logs()

    def _enrich_if_needed(self, company: dict) -> str:
        try:
            # Incremental Logic (Fast Path)
            target_key = clean_text(company.get('cin') or company.get('id')).upper()
            db_record = db_module.get_company_detail(target_key)
            
            if db_record:
                # If we have an announcement history, check if it's potentially outdated
                db_anns = db_record.get('announcementHistory', [])
                current_anns = company.get('announcementHistory', [])
                
                # Check for announcement count match
                if len(db_anns) > 0 and len(db_anns) == len(current_anns):
                    # Check latest announcement date
                    db_latest = db_anns[0].get('announcementDate')
                    curr_latest = current_anns[0].get('announcementDate') if current_anns else None
                    if db_latest == curr_latest:
                        return 'skipped'
            
            # Slow Path: Full Scraping Enrichment
            self.cache.enrich_company_profile(company, force=True)
            return 'success'
        except Exception as e:
            print(f"[SYNC] Error enriching {company.get('name')}: {e}")
            return 'failed'


class IBBIDataCache:
    def __init__(self) -> None:
        self._lock = Lock()
        self._companies: list[dict[str, Any]] = []
        self._stats: dict[str, Any] = {}
        self._recent_announcements: list[dict[str, Any]] = []
        self._last_refreshed = 0.0
        self._session = requests.Session()
        # ── Optimize connection pooling for high concurrency ─────
        from requests.adapters import HTTPAdapter
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        
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
        self.sync_manager = SyncManager(self)

    def get_snapshot(self, force: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
        with self._lock:
            is_stale = (time.time() - self._last_refreshed) > CACHE_TTL_SECONDS
            # ── On cold start: load from MySQL DB instead of scraping ────
            if not self._companies and not force:
                try:
                    db_companies = db_module.get_all_companies()
                    if db_companies:
                        self._companies = db_companies
                        self._stats = db_module.get_stats()
                        db_anns = db_module.get_recent_announcements(50)
                        self._recent_announcements = [
                            {
                                "id": f"{a.get('id', '')}-{i}",
                                "title": a.get("announcementType", ""),
                                "source": "IBBI Public Announcement",
                                "date": a.get("announcementDate", ""),
                                "summary": f"{a.get('debtorName','')} | Applicant: {a.get('applicantName','')} | IP: {a.get('insolvencyProfessional','')}",
                                "url": a.get("registryUrl", ""),
                                "companyId": a.get("cin", "") if a.get("cin", "") != "N/A" else slugify(a.get("debtorName", "")),
                            }
                            for i, a in enumerate(db_anns)
                        ]
                        self._last_refreshed = time.time()
                        return self._companies, self._stats, self._recent_announcements
                except Exception as e:
                    print(f"[DB] Could not load from MySQL on startup: {e}")
            if force:
                self._refresh()
            elif not self._companies or is_stale:
                # ── Trigger non-blocking background refresh ─────
                import threading
                threading.Thread(target=self._refresh, daemon=True).start()
                
            return self._companies, self._stats, self._recent_announcements

    def _refresh(self) -> None:
        grouped: dict[str, list[dict[str, Any]]] = {}
        all_announcements: list[dict[str, Any]] = []
        professionals: set[str] = set()
        ibbi_error = ""

        try:
            print(f"[API FETCH] Fetching bulk IBBI export data from: {IBBI_EXPORT_URL}")
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
        # ── Persist to MySQL DB ──
        try:
            db_module.upsert_companies(companies)
            db_module.upsert_announcements(all_announcements, self._stats.get("lastSyncedAt", ""))
            if companies or all_announcements:
                print(f"[DB] Saved {len(companies)} companies and {len(all_announcements)} announcements to MySQL.")
            else:
                print("[DB] No new companies or announcements to save.")
        except Exception as e:
            print(f"[DB] MySQL save error in _refresh: {e}")

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
        # ── Also save to MySQL ──
        try:
            db_module.upsert_company_detail(record)
        except Exception as e:
            print(f"[DB] MySQL upsert_company_detail error: {e}")

    def _get_persisted_company_detail(self, company: dict[str, Any]) -> dict[str, Any] | None:
        company_id = clean_text(company.get("id", "")).upper()
        company_cin = clean_text(company.get("cin", "")).upper()
        persisted = None
        if company_id:
            persisted = self._persisted_company_details.get(company_id)
        if not persisted and company_cin and company_cin != "N/A":
            persisted = self._persisted_company_details.get(company_cin)
        return dict(persisted) if isinstance(persisted, dict) else None

    def fetch_corporate_process_data(self, cin: str) -> dict[str, Any]:
        cleaned_cin = clean_text(cin).upper()
        if not cleaned_cin or cleaned_cin == "N/A":
            return {}

        process_specs = [
            ("detailsAboutCd", "Details About CD", IBBI_CLAIMS_INNER_PROCESS_URL, "details"),
            ("publicAnnouncement", "Public Announcement", IBBI_CLAIMS_PUBLIC_PROCESS_URL, "table"),
            ("claims", "Claims", IBBI_CLAIMS_PROCESS_LIST_URL, "table"),
            ("invitationForResolutionPlan", "Invitation for Resolution Plan", IBBI_CLAIMS_RP_PROCESS_URL, "table"),
            ("orders", "Orders", IBBI_CLAIMS_ORDER_PROCESS_URL, "table"),
            ("auctionNotice", "Auction Notice", IBBI_CLAIMS_AUCTION_NOTICE_PROCESS_URL, "table"),
            ("corporatePersonals", "Corporate Personals", "https://ibbi.gov.in/claims/corporate-personals", "table"),
        ]
        sections: dict[str, Any] = {}

        def fetch_process_section(spec: tuple) -> tuple[str, dict[str, Any]] | None:
            section_id, title, base_url, parser_kind = spec
            url = build_claims_process_url(base_url, cleaned_cin)
            try:
                print(f"[API FETCH] Requesting process section '{title}' for CIN {cleaned_cin} via: {url}")
                response = self._session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
                if response.status_code != 200:
                    return None
            except Exception:
                return None

            if parser_kind == "details":
                rows = parse_process_detail_rows(response.text)
                if not rows:
                    return None
                return section_id, {
                    "id": section_id,
                    "title": title,
                    "url": url,
                    "headers": ["Field", "Value"],
                    "rows": rows,
                }
            else:
                headers, rows = parse_process_table_rows(response.text, base_url=url)
                if not headers or not rows:
                    return None
                return section_id, {
                    "id": section_id,
                    "title": title,
                    "url": url,
                    "headers": headers,
                    "rows": rows,
                }

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            for result in executor.map(fetch_process_section, process_specs):
                if result:
                    sections[result[0]] = result[1]

        # Use Selenium to scrape the dynamically rendered claims tables as requested
        try:
            print(f"[SELENIUM] Fetching claims process via Selenium for {cleaned_cin}")
            selenium_data = scrape_ibbi_claims_with_selenium(cleaned_cin)
            if selenium_data:
                # Merge the dynamically fetched data
                sections.update(selenium_data)
        except Exception as e:
            print(f"[SELENIUM ERROR] Failed to fetch Selenium claims data: {e}")

        return sections

    def fetch_ibbi_news(self, company_name: str) -> list[dict[str, str]]:
        """Scrapes IBBI press releases and filters by company name."""
        try:
            print(f"[API FETCH] Fetching IBBI news from: {IBBI_PRESS_RELEASES_URL}")
            response = self._session.get(IBBI_PRESS_RELEASES_URL, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, "html.parser")
            news_items = []
            table = soup.find("table")
            if not table:
                return []
            
            headers = [clean_text(th.get_text(" ", strip=True)) for th in table.find_all("th")]
            company_tokens = set(slugify(company_name).split("-"))
            
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) < 3: # Need at least Sr. No, Date, Subject
                    continue
                
                # Column 1 is Date, Column 2 is Subject (Title + Link)
                date = clean_text(cells[1].get_text(" ", strip=True))
                title = clean_text(cells[2].get_text(" ", strip=True))
                
                # Remove file size if present in title (e.g. (100 KB))
                title = re.sub(r"\(\d+\.?\d*\s*[KkMm][Bb]\)$", "", title).strip()
                
                anchor = cells[2].find("a", href=True)
                url = ""
                if anchor:
                    href = anchor["href"]
                    if "javascript" in href.lower():
                        # Try to extract from onclick if present
                        onclick = anchor.get("onclick", "")
                        match = re.search(r"['\"](.*?)['\"]", onclick)
                        if match:
                            url = urljoin(IBBI_PRESS_RELEASES_URL, match.group(1))
                    else:
                        url = urljoin(IBBI_PRESS_RELEASES_URL, href)
                
                # Simple keyword matching
                title_lower = title.lower()
                is_match = any(token in title_lower for token in company_tokens if len(token) > 3)
                
                news_items.append({
                    "id": f"news-{slugify(title)[:40]}-{slugify(date)}",
                    "title": title,
                    "date": date,
                    "source": "IBBI Press Release",
                    "url": url,
                    "isRelated": is_match
                })
            
            # Sort: move related news to front
            news_items.sort(key=lambda x: x["isRelated"], reverse=True)
            return news_items[:10]
        except Exception as e:
            print(f"[ERR] Failed to fetch IBBI news: {e}")
            return []

    def resolve_company_cin(self, company: dict[str, Any]) -> str:
        cin = clean_text(company.get("cin", "")).upper()
        if cin and cin != "N/A":
            return cin

        company_name = clean_text(company.get("name", ""))
        if not company_name:
            return ""

        try:
            rows = self.search_claim_process(company_name, limit=10)
        except Exception:
            return ""

        ranked_rows = sorted(
            rows,
            key=lambda row: (
                200 if clean_text(row["name"]).upper() == company_name.upper() else 0,
                150 if slugify(row["name"]).upper() == slugify(company_name).upper() else 0,
                100 if company_name.upper() in clean_text(row["name"]).upper() else 0,
                parse_date(row["latest_claim_date"]),
            ),
            reverse=True,
        )
        return clean_text(ranked_rows[0]["cin"]).upper() if ranked_rows else ""

    def fetch_public_announcement_company(self, identifier: str) -> dict[str, Any] | None:
        cleaned = clean_text(identifier)
        if not cleaned:
            return None

        print(f"[API FETCH] Searching specific company announcements for: {cleaned}")
        response = self._session.get(build_registry_url(cleaned), timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code != 200:
            return None

        live_rows = parse_public_announcement_rows(response.text)
        if not live_rows:
            return None

        live_announcements = [build_announcement(normalize_keys(row)) for row in live_rows]
        ranked_announcements = sorted(
            live_announcements,
            key=lambda announcement: (
                200 if clean_text(announcement["cin"]).upper() == cleaned.upper() else 0,
                180 if clean_text(announcement["debtorName"]).upper() == cleaned.upper() else 0,
                150 if slugify(announcement["debtorName"]).upper() == slugify(cleaned).upper() else 0,
                100 if clean_text(announcement["debtorName"]).upper().startswith(cleaned.upper()) else 0,
                80 if cleaned.upper() in clean_text(announcement["debtorName"]).upper() else 0,
                parse_date(announcement["announcementDate"]),
            ),
            reverse=True,
        )
        if not ranked_announcements:
            return None

        lead = ranked_announcements[0]
        matching_announcements = [
            announcement
            for announcement in live_announcements
            if (
                clean_text(announcement["cin"]).upper() != "N/A"
                and clean_text(announcement["cin"]).upper() == clean_text(lead["cin"]).upper()
            )
            or (
                clean_text(announcement["cin"]).upper() == "N/A"
                and clean_text(announcement["debtorName"]).upper() == clean_text(lead["debtorName"]).upper()
            )
        ]
        if not matching_announcements:
            matching_announcements = [lead]
        return attach_company_source_metadata(build_company(matching_announcements))

    def enrich_company_profile(self, company: dict[str, Any], force: bool = False, background: bool = False) -> dict[str, Any]:
        cache_key = clean_text(company.get("cin", "") or company.get("id", "")).upper()
        cached_at = utc_now_iso()
        
        # 1. Quick Cache Check
        if cache_key and cache_key in self._profile_cache and not force:
            cache_entry = self._profile_cache[cache_key]
            fetched_at = float(cache_entry.get("fetched_at", 0))
            if (time.time() - fetched_at) <= PROFILE_CACHE_TTL_SECONDS:
                cached_payload = cache_entry["data"]
                # If we already have corporate processes, we are good to go
                if cached_payload.get("corporateProcesses"):
                    return attach_company_freshness(
                        attach_company_source_metadata(cached_payload),
                        snapshot_synced_at=self._stats.get("lastSyncedAt", "N/A"),
                        profile_cached_at=cache_entry.get("cached_at", "N/A"),
                    )

        # 2. Return database result if available and not forcing refresh
        if not force:
            db_record = db_module.get_company_detail(cache_key)
            if db_record and db_record.get("corporateProcesses"):
                # Check if DB record is stale
                cached_time_str = db_record.get("profileCachedAt") or db_record.get("cached_at")
                is_db_stale = False
                if cached_time_str:
                    try:
                        from datetime import datetime
                        cached_dt = datetime.fromisoformat(cached_time_str.replace('Z', '+00:00'))
                        if (datetime.now(cached_dt.tzinfo) - cached_dt).total_seconds() > PROFILE_CACHE_TTL_SECONDS:
                            is_db_stale = True
                    except Exception:
                        is_db_stale = True
                
                if is_db_stale:
                    print(f"[CACHE] DB record for {cache_key} is stale. Returning and refreshing in background.")
                    import threading
                    threading.Thread(target=run_full_enrichment, args=(dict(db_record),), daemon=True).start()
                    db_record["enrichmentInProgress"] = True
                
                return db_record

        # 3. Preparation for Enrichment
        enriched = attach_company_source_metadata(dict(company))
        identifier = enriched.get("cin") or enriched.get("name", "")
        
        def run_full_enrichment(base_data: dict[str, Any]):
            try:
                # Local copy to modify
                work_data = dict(base_data)
                
                existing_cin = clean_text(work_data.get("cin", "")).upper()
                has_valid_cin = existing_cin and existing_cin != "N/A"
                
                def run_announcement_fetch():
                    try: return self.fetch_public_announcement_company(identifier)
                    except Exception: return None

                def run_announcement_fetch():
                    try: return self.fetch_public_announcement_company(identifier)
                    except Exception as e:
                        print(f"[ENRICH] Announcement fetch error: {e}")
                        return None

                def run_cin_resolution():
                    if has_valid_cin: return existing_cin
                    try: return self.resolve_company_cin(work_data)
                    except Exception as e:
                        print(f"[ENRICH] CIN resolution error: {e}")
                        return ""

                # 1. Parallel Step: Resolution of Announcements and CIN (if needed)
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    future_ann = executor.submit(run_announcement_fetch)
                    future_cin = executor.submit(run_cin_resolution)
                    
                    live_company = future_ann.result()
                    if live_company:
                        work_data = merge_company_with_live_announcements(
                            work_data,
                            live_company.get("announcementHistory", []),
                        )
                        work_data = attach_company_source_metadata(work_data)

                    resolved_cin = future_cin.result() or existing_cin
                    if resolved_cin:
                        if resolved_cin != existing_cin:
                            print(f"[ENRICH] CIN resolved: {existing_cin} -> {resolved_cin}")
                            work_data["cin"] = resolved_cin
                            work_data = attach_company_source_metadata(work_data)
                        
                        # 2. Step: Fetching Detailed Records (Process)
                        # Now that we have the DEFINITIVE CIN
                        print(f"[ENRICH] Fetching detail processes for {resolved_cin}")
                        corporate_processes = self.fetch_corporate_process_data(resolved_cin)
                        if corporate_processes:
                            work_data = attach_corporate_process_data(work_data, corporate_processes)
                    else:
                        print(f"[ENRICH] Warning: Could not resolve CIN for {identifier}")

                # 3. Parallel Step: News Fetching
                print(f"[ENRICH] Fetching related news for {work_data.get('name')}")
                try:
                    ibbi_news = self.fetch_ibbi_news(work_data.get("name", ""))
                    if ibbi_news:
                        work_data["news"] = ibbi_news
                except Exception as e:
                    print(f"[ENRICH] News fetch error: {e}")


                work_data["documents"] = build_company_documents(work_data)
                inject_simulated_data(work_data)
                
                work_data = attach_company_freshness(
                    work_data,
                    snapshot_synced_at=self._stats.get("lastSyncedAt", "N/A"),
                    profile_cached_at=cached_at,
                )

                # Update caches
                if cache_key:
                    self._profile_cache[cache_key] = {
                        "data": work_data,
                        "fetched_at": time.time(),
                        "cached_at": cached_at,
                    }
                self._persist_company_detail(work_data)
                print(f"[CACHE] Background enrichment completed for: {cache_key}")
            except Exception as e:
                print(f"[CACHE] Background enrichment failed for {cache_key}: {e}")

        # 4. Handle Background vs Blocking
        if background and not force:
            print(f"[CACHE] Starting background enrichment for: {cache_key}")
            import threading
            threading.Thread(target=run_full_enrichment, args=(enriched,), daemon=True).start()
            
            # Return partial enriched data quickly
            enriched["enrichmentInProgress"] = True
            return attach_company_freshness(
                enriched,
                snapshot_synced_at=self._stats.get("lastSyncedAt", "N/A"),
                profile_cached_at=cached_at
            )
        else:
            # Blocking execution (requested fresh data)
            run_full_enrichment(enriched)
            return self._profile_cache[cache_key]["data"] if cache_key in self._profile_cache else enriched



    def search_claim_process(self, query: str, limit: int = 12) -> list[dict[str, str]]:
        print(f"[API FETCH] Searching IBBI claims registry for query: {query}")
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

# ── Initialise MySQL database tables on startup ──────────────────
try:
    db_module.init_db()
except Exception as _db_init_err:
    print(f"[DB] MySQL init failed (data will still work from memory/JSON): {_db_init_err}")


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
            existing_ids.add(cin)

    try:
        live_public_company = cache.fetch_public_announcement_company(query)
    except Exception:
        live_public_company = None
    if live_public_company:
        live_tokens = company_identifier_tokens(live_public_company)
        if not existing_ids.intersection(live_tokens):
            matches.append(live_public_company)

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



@app.get("/company/{id_or_cin}/claims/merged")
def get_merged_claims(id_or_cin: str) -> list:
    """Fetches all versions with full summary and detailed claimant tables via Selenium."""
    try:
        company = get_company(id_or_cin)
        cin = company.get("cin")
    except Exception:
        cin = id_or_cin.upper().replace('N/A', '')

    if not cin: return []
    
    from ibbi_selenium_scraper import scrape_all_claims_with_selenium
    
    try:
        # Use our robust selenium scraper to parse the nested tables and PDF links properly
        merged = scrape_all_claims_with_selenium(cin)
        return merged
    except Exception as e:
        print(f"Error fetching deep claims for {cin}: {e}")
        return []


@app.get("/company/{id_or_cin}")
def get_company(id_or_cin: str, fresh: bool = Query(default=False)) -> dict[str, Any]:
    # ── Try MySQL DB first (enriched profile) ─────────────────────
    if not fresh:
        try:
            db_detail = db_module.get_company_detail(id_or_cin)
            if db_detail:
                return db_detail
        except Exception as e:
            print(f"[DB] get_company_detail error: {e}")
    companies, _, _ = cache.get_snapshot(force=fresh)
    target = clean_text(id_or_cin).upper()

    for company in companies:
        if company["id"].upper() == target or company["cin"].upper() == target or slugify(company["name"]).upper() == target:
            return cache.enrich_company_profile(attach_company_source_metadata(company), force=fresh, background=(not fresh))

    public_company = cache.fetch_public_announcement_company(id_or_cin)
    if public_company:
        return cache.enrich_company_profile(public_company, force=fresh, background=(not fresh))

    claims_company = cache.fetch_claims_company(id_or_cin)
    if claims_company:
        return cache.enrich_company_profile(claims_company, force=fresh, background=(not fresh))

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


@app.post("/api/ai/chat")
async def ai_chat_analysis(request: Request):
    try:
        body = await request.json()
        query = body.get("query", "").lower()
        company = body.get("company", {})
        
        company_name = company.get("name", "this company")
        status = company.get("status", "Unknown")
        cin = company.get("cin", "N/A")
        announcements = company.get("announcementHistory", [])
        num_charges = len(company.get("charges", []))
        
        # Simple logical reasoning engine to simulate AI
        response = ""
        
        if "risk" in query or "safe" in query:
            if status in ["Liquidation", "Dissolved"]:
                response = f"Based on my analysis, {company_name} carries an **EXTREME risk profile**. It is currently in {status}, meaning original business operations have likely ceased and assets are being recovered for creditors."
            elif status == "Under CIRP":
                response = f"{company_name} is currently in the **Corporate Insolvency Resolution Process (CIRP)**. This is a medium-to-high risk stage where a resolution professional is actively seeking a turnaround plan. Its future depends on the CoC's approval of a resolution plan."
            else:
                response = f"The risk level for {company_name} is marked as **Moderate**. While it is listed in the insolvency registry, its specific status '{status}' suggests a transitional period."
                

                
        elif "charge" in query or "loan" in query or "bank" in query:
            if num_charges > 0:
                response = f"I've detected {num_charges} financial charges on record for {company_name}. This indicates significant secured lending, likely from major banks, who will be primary members of the Committee of Creditors (CoC)."
            else:
                response = f"No significant active charges were found in this specific snapshot. This might mean the company has limited secured debt or the data hasn't been synced from the latest MCA records."
        
        elif "what" in query and ("do" in query or "happen" in query):
            response = f"{company_name} (CIN: {cin}) is currently undergoing a legal process overseen by the IBBI. To date, there have been {len(announcements)} public announcements regarding its {status} status."
            
        else:
            response = f"I am analyzing {company_name}. Regarding your question: '{query}', the records show it is a {company.get('type', 'company')} with {len(announcements)} recorded insolvency events. Would you like me to analyze its risk profile or financial charges specifically?"

        # Add a delay to simulate "thinking"
        await asyncio.sleep(1.2)
        
        return {
            "answer": response,
            "tokens_used": len(response) // 4 + 10,
            "model": "fintech-iq-v1-simulated"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"AI Engine Error: {str(e)}")


@app.get("/refresh")
def refresh_cache() -> dict[str, Any]:
    companies, stats, announcements = cache.get_snapshot(force=True)
    return {
        "status": "refreshed",
        "companies": len(companies),
        "announcements": len(announcements),
        "lastSyncedAt": stats["lastSyncedAt"],
    }




@app.post("/refresh-company/{id_or_cin}")
def refresh_company(id_or_cin: str) -> dict[str, Any]:
    """
    Force-refresh a specific company from IBBI and persist to JSON database store.
    """
    try:
        company = get_company(id_or_cin, fresh=True)
        return {
            "status": "refreshed",
            "id": company.get("id"),
            "name": company.get("name"),
            "cin": company.get("cin"),
            "lastSyncedAt": company.get("snapshotSyncedAt") or utc_now_iso(),
            "documentsCount": len(company.get("documents", [])),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {clean_text(str(exc))}") from exc




@app.post("/sync/full")
def trigger_full_sync():
    """Starts a global parallel sync of all companies."""
    job = cache.sync_manager.start_full_sync()
    return job


@app.get("/sync/status")
def get_sync_status():
    """Returns progress of the active sync job and historical logs."""
    return cache.sync_manager.get_status()






def scrape_professional_details_by_id(session: requests.Session, field_id: str) -> dict[str, Any]:
    """
    Fetches all sub-sections for a professional from IBBI details page.
    """
    sections = {
        "IP Detail": "IP_Details",
        "AFA Detail": "AFA_Details",
        "Assignment Detail": "Assignment_Details",
        "Assignment Analytics": "Assignment_Analytics",
        "CPE Detail": "CPE_Details",
        "Orders": "IPs_Order_Details",
        "Professional Qualification": "qualifications",
        "Work Experience": "work_experience"
    }
    
    results = {"_scraped_at": datetime.now().isoformat()}
    for label, section_type in sections.items():
        try:
            url = f"{IBBI_IP_DETAILS_URL}?fieldid={field_id}&type={section_type}"
            resp = session.get(url, timeout=15)
            if resp.ok:
                soup = BeautifulSoup(resp.text, "html.parser")
                tables = soup.find_all("table")
                section_results = []
                
                for table in tables:
                    tr_list = table.find_all("tr")
                    if not tr_list:
                        continue
                        
                    # 1. Peek at first row to determine if vertical or horizontal
                    first_tr = tr_list[0]
                    headers = [clean_text(th.get_text(" ", strip=True)) for th in first_tr.find_all("th")]
                    
                    if not headers:
                        thead = table.find("thead")
                        if thead:
                            headers = [clean_text(th.get_text(" ", strip=True)) for th in thead.find_all("th")]
                    
                    if not headers:
                        # Case: Vertical table (key-value pairs) or simple list
                        rows: list[dict[str, str]] = []
                        for tr in tr_list:
                            cells = tr.find_all(["td", "th"])
                            if len(cells) >= 2:
                                k = clean_text(cells[0].get_text(" ", strip=True))
                                v = clean_text(cells[1].get_text(" ", strip=True))
                                # Filter out title rows with no value
                                if k and (v or k.lower() != label.lower()):
                                    rows.append({"label": k, "value": v if v else "-"})
                        if rows:
                            section_results.append({"type": "vertical", "data": rows})
                    else:
                        # Case: Horizontal table
                        # Stripping the section title if it's the only header or first header
                        if len(headers) > 1 and headers[0].lower() in [label.lower(), "afa details", "afa history"]:
                             headers = headers[1:]

                        rows: list[dict[str, str]] = []
                        # Use tbody if available, otherwise skip first row (header row)
                        tbody = table.find("tbody")
                        data_rows = tbody.find_all("tr") if tbody else tr_list[1:]

                        for tr in data_rows:
                            cells = tr.find_all(["td", "th"])
                            if len(cells) >= len(headers):
                                offset = len(cells) - len(headers)
                                row_data = {}
                                for i, h in enumerate(headers):
                                    row_data[h] = clean_text(cells[i+offset].get_text(" ", strip=True))
                                if any(row_data.values()):
                                    rows.append(row_data)
                        
                        if rows:
                            section_results.append({"type": "horizontal", "headers": headers, "data": rows})
                
                if section_results:
                    results[label] = section_results
                else:
                    results[label] = [{"type": "empty", "message": "No data found in this section."}]
            else:
                results[label] = [{"type": "error", "message": f"Failed to fetch section (HTTP {resp.status_code})"}]
        except Exception as e:
            results[label] = [{"type": "error", "message": str(e)}]
            
    return results


PROF_METADATA_PATH = BASE_DIR.parent / "database" / "professional_metadata.json"
PROF_CACHE_PATH = BASE_DIR.parent / "database" / "professional_cache.json"

def get_prof_metadata(name: str) -> dict[str, Any]:
    if not PROF_METADATA_PATH.exists():
        return {"links": []}
    try:
        with open(PROF_METADATA_PATH, "r") as f:
            data = json.load(f)
            return data.get(name, {"links": []})
    except Exception:
        return {"links": []}

def save_prof_metadata(name: str, metadata: dict[str, Any]):
    PROF_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    current_data = {}
    if PROF_METADATA_PATH.exists():
        try:
            with open(PROF_METADATA_PATH, "r") as f:
                current_data = json.load(f)
        except Exception:
            pass
    current_data[name] = metadata
    with open(PROF_METADATA_PATH, "w") as f:
        json.dump(current_data, f, indent=2)

def get_cached_profile(name: str) -> Optional[dict[str, Any]]:
    if not PROF_CACHE_PATH.exists():
        return None
    try:
        with open(PROF_CACHE_PATH, "r") as f:
            cache = json.load(f)
            entry = cache.get(name)
            if entry:
                # Check TTL
                scraped_at = datetime.fromisoformat(entry["_scraped_at"])
                if (datetime.now() - scraped_at).total_seconds() < PROFILE_CACHE_TTL_SECONDS:
                    return entry
    except Exception:
        pass
    return None

def save_profile_cache(name: str, data: dict[str, Any]):
    PROF_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache = {}
    if PROF_CACHE_PATH.exists():
        try:
            with open(PROF_CACHE_PATH, "r") as f:
                cache = json.load(f)
        except Exception:
            pass
    cache[name] = data
    with open(PROF_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)

@app.get("/professional/{name}/metadata")
def get_professional_metadata_route(name: str):
    return get_prof_metadata(name)

@app.post("/professional/{name}/metadata")
async def save_professional_metadata_route(name: str, request: Request):
    try:
        metadata = await request.json()
        save_prof_metadata(name, metadata)
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/professional/{name}")
def get_professional_details(name: str):
    """
    Search for a professional by name and scrape their full profile from IBBI.
    """
    try:
        # 0. Check Cache
        cached = get_cached_profile(name)
        if cached:
            return cached

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        
        # 1. Search for name
        search_url = f"{IBBI_IP_REGISTER_URL}?name_ip={quote(name)}"
        resp = session.get(search_url, timeout=20)
        if not resp.ok:
            raise HTTPException(status_code=502, detail=f"IBBI search page offline (HTTP {resp.status_code})")
        
        soup = BeautifulSoup(resp.text, "html.parser")
        # Find the link to details
        link_tag = soup.find("a", href=re.compile(r"insolvency-professional/details\?fieldid="))
        
        if not link_tag:
            # Try a fuzzy match in table if link regex was too strict
            table = soup.find("table")
            if table:
                for a in table.find_all("a", href=True):
                    if "details?fieldid=" in a['href']:
                        link_tag = a
                        break
        
        if not link_tag:
            return {
                "name": name,
                "found": False,
                "message": f"Could not find a professional matching '{name}' in IBBI register."
            }
        
        # 2. Extract fieldid
        href = link_tag['href']
        match = re.search(r"fieldid=([^&]+)", href)
        if not match:
            raise HTTPException(status_code=500, detail="Could not extract professional ID from IBBI search result.")
        
        field_id = match.group(1)
        
        # 3. Scrape all details
        details = scrape_professional_details_by_id(session, field_id)
        
        response_data = {
            "name": name,
            "field_id": field_id,
            "found": True,
            "_scraped_at": datetime.now().isoformat(),
            "profile_url": f"https://ibbi.gov.in/insolvency-professional/details?fieldid={field_id}",
            "sections": details
        }
        
        # 4. Save to Cache
        save_profile_cache(name, response_data)
        
        return response_data
        
    except Exception as e:
        print(f"Professional scrape error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scraper error: {str(e)}")


if __name__ == "__main__":

    print("fintech API starting on http://localhost:8005")
    uvicorn.run(app, host="0.0.0.0", port=8005)
