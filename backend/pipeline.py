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
MCA_MASTER_DATA_URL = "https://www.mca.gov.in/content/mca/global/en/mca/master-data/MDS.html"
GST_TAXPAYER_SEARCH_URL = "https://services.gst.gov.in/services/searchtp"
UDYAM_SEARCH_URL = "https://udyamregistration.gov.in/Udyam_Verify.aspx"
PUBLIC_COMPANY_PROFILE_BASE_URL = "https://www.instafinancials.com/company"
FALCON_COMPANY_PROFILE_BASE_URL = "https://www.falconebiz.com"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
BASE_DIR = Path(__file__).resolve().parent
MASTER_DATA_DIR = BASE_DIR / "data" / "company_master"
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
    gstin = clean_text(company.get("gstin", ""))
    registry_url = clean_text(company.get("registryUrl", ""))
    profile_url = clean_text(company.get("profileUrl", ""))
    source_urls: dict[str, str] = {}

    if registry_url:
        source_urls["ibbiAnnouncement"] = registry_url
    source_urls["ibbiPublicAnnouncement"] = IBBI_PUBLIC_ANNOUNCEMENT_URL
    source_urls["ibbiClaims"] = build_claims_registry_url(cin) if cin and cin != "N/A" else IBBI_CLAIMS_SEARCH_URL
    source_urls["mcaMasterData"] = MCA_MASTER_DATA_URL
    source_urls["gstTaxpayerSearch"] = f"{GST_TAXPAYER_SEARCH_URL}?gstin={quote(gstin)}" if gstin and gstin != "N/A" else GST_TAXPAYER_SEARCH_URL
    source_urls["udyamVerify"] = UDYAM_SEARCH_URL
    if profile_url:
        source_urls["publicProfileMirror"] = profile_url
    return source_urls


def build_company_data_sources(company: dict[str, Any]) -> list[dict[str, str]]:
    urls = build_company_source_urls(company)
    sources: list[dict[str, str]] = []
    source_section = normalize_source_section(company.get("sourceSection", ""))
    status = normalize_company_status(company.get("status", "Active"), "Active")
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
    sources.append(
        {
            "id": "mca_master_data",
            "name": "MCA Master Data",
            "portalType": "government",
            "mode": "manual-assisted",
            "status": "requires-captcha",
            "url": urls["mcaMasterData"],
            "note": "MCA endpoints are captcha-protected, so this app keeps this as assisted lookup.",
            "checkedAt": checked_at,
        }
    )
    sources.append(
        {
            "id": "gst_taxpayer_search",
            "name": "GST Taxpayer Search",
            "portalType": "government",
            "mode": "manual-assisted",
            "status": "available",
            "url": urls["gstTaxpayerSearch"],
            "note": "GST profile can be verified directly from the GST portal.",
            "checkedAt": checked_at,
        }
    )
    sources.append(
        {
            "id": "udyam_verify",
            "name": "Udyam Verify",
            "portalType": "government",
            "mode": "manual-assisted",
            "status": "available",
            "url": urls["udyamVerify"],
            "note": "Useful for MSME/Udyam verification where available.",
            "checkedAt": checked_at,
        }
    )

    profile_url = clean_text(company.get("profileUrl", ""))
    if profile_url:
        sources.append(
            {
                "id": "public_profile_mirror",
                "name": "Public Company Profile Mirror",
                "portalType": "public-registry-mirror",
                "mode": "live-scrape",
                "status": "connected",
                "url": profile_url,
                "note": "Supplementary enrichment for directors, charges, and contact fields.",
                "checkedAt": checked_at,
            }
        )

    if source_section == "master":
        sources.append(
            {
                "id": "local_company_master",
                "name": "Local Company Master",
                "portalType": "internal-dataset",
                "mode": "batch-load",
                "status": "connected",
                "url": "",
                "note": "Seed dataset loaded from backend/data/company_master.",
                "checkedAt": checked_at,
            }
        )

    type_note = normalize_company_type(company.get("type", ""), fallback_name=company.get("name", ""))
    sources.append(
        {
            "id": "company_type_classifier",
            "name": "Type Classification",
            "portalType": "internal-rule",
            "mode": "derived",
            "status": "connected",
            "url": "",
            "note": f"Company categorized as {type_note} (supports Private, Public, LLP, OPC).",
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
    if (not enriched.get("addresses")) and enriched["registeredAddress"] != "N/A":
        enriched["addresses"] = parse_public_address(enriched["registeredAddress"])

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


def build_master_company(row: dict[str, Any]) -> dict[str, Any] | None:
    name = find_first_value(
        row,
        "company name",
        "company_name",
        "name",
        "llp name",
        "entity name",
        "legal name",
    )
    if not name:
        return None

    cin = find_first_value(row, "cin", "cin no", "cin number", "company cin", "llpin", "llp identification number")
    status = find_first_value(row, "company status", "status", "llp status") or "Active"
    company_type = find_first_value(row, "company type", "entity type", "class", "company class")
    company_type = normalize_company_type(company_type, fallback_name=name)

    category = find_first_value(row, "company category", "category", "sub category", "company subtype") or "Company Master"
    company_subcategory = find_first_value(row, "company subcategory", "sub category", "company subtype", "llp subtype")
    registered_address = find_first_value(
        row,
        "registered address",
        "registered office address",
        "address",
        "company address",
        "registered office",
    ) or "N/A"
    listing_status = find_first_value(row, "listing status", "listed", "listed status")
    listing_status = "Listed" if listing_status.lower() in {"listed", "yes", "y", "true"} else "Unlisted"

    company_id = cin or slugify(name)
    incorporation_date = find_first_value(row, "date of incorporation", "incorporation date", "date of inc", "inc date") or "N/A"
    roc_code = find_first_value(row, "roc", "roc code", "registrar of companies", "roc/region")
    if not roc_code:
        roc_code = derive_roc_code(cin or company_id, registered_address)

    registration_number = find_first_value(row, "registration number", "registration no", "reg no", "company registration number")
    if not registration_number and cin and cin != "N/A":
        registration_number = cin[-6:] if len(cin) >= 6 else cin

    auth_cap = parse_money_amount(find_first_value(row, "authorised capital", "authorized capital", "auth cap", "authcapital"))
    paid_up = parse_money_amount(find_first_value(row, "paid up capital", "paid-up capital", "puc", "paidupcapital"))
    industry = find_first_value(row, "industry", "main business", "business activity", "activity")
    nic_code = find_first_value(row, "nic", "nic code", "niccode")
    filing_status = find_first_value(row, "filing status", "compliance status")
    active_compliance = find_first_value(row, "active compliance", "active compliant", "compliant")
    addresses = parse_public_address(registered_address)
    last_updated = find_first_value(row, "last updated", "updated on", "last update date") or incorporation_date

    return {
        "id": company_id,
        "name": name,
        "cin": cin or "N/A",
        "pan": find_first_value(row, "pan", "pan number") or "N/A",
        "incorporationDate": incorporation_date,
        "status": status if status in {"Active", "Inactive", "Under CIRP", "Liquidation", "Dissolved"} else "Active",
        "type": normalize_company_type(company_type, fallback_name=name),
        "category": category,
        "origin": find_first_value(row, "origin", "country of origin", "jurisdiction") or "Indian",
        "registeredAddress": registered_address,
        "businessAddress": find_first_value(row, "business address", "address for correspondence", "corporate address") or registered_address,
        "phone": find_first_value(row, "phone", "mobile", "contact number", "telephone") or "N/A",
        "email": find_first_value(row, "email", "email id", "company email") or "N/A",
        "website": find_first_value(row, "website", "web site", "url") or "N/A",
        "listingStatus": listing_status,
        "lastAGMDate": find_first_value(row, "last agm date", "date of agm", "agm date") or "N/A",
        "lastBSDate": find_first_value(row, "last bs date", "balance sheet date", "last balance sheet date") or "N/A",
        "gstin": find_first_value(row, "gstin", "gst number") or "N/A",
        "lei": find_first_value(row, "lei") or "N/A",
        "epfo": find_first_value(row, "epfo") or "N/A",
        "iec": find_first_value(row, "iec", "import export code") or "N/A",
        "authCap": auth_cap,
        "puc": paid_up,
        "soc": 0,
        "revenue": [],
        "pat": [],
        "netWorth": [],
        "promoterHolding": [],
        "receivable": "N/A",
        "payable": "N/A",
        "overview": f"{name} is available in the local company master dataset. No IBBI insolvency event is currently mapped for this company.",
        "charges": [],
        "financials": [],
        "ownership": [],
        "compliance": [],
        "documents": [],
        "directors": [],
        "news": [],
        "trendData": [],
        "applicant_name": "N/A",
        "ip_name": "N/A",
        "commencement_date": "N/A",
        "last_date_claims": "N/A",
        "announcementType": "No active IBBI event matched",
        "announcementDate": "N/A",
        "announcementDateIso": "",
        "lastDateOfSubmission": "N/A",
        "lastDateOfSubmissionIso": "",
        "insolvencyProfessionalAddress": "N/A",
        "remarks": "Source: local company master dataset.",
        "registryUrl": "",
        "announcementCount": 0,
        "applicants": [],
        "insolvencyProfessionals": [],
        "announcementHistory": [],
        "sourceSection": "master",
        "sourceUrls": {},
        "dataSources": [],
        "rocCode": roc_code or "N/A",
        "registrationNumber": registration_number or "N/A",
        "companySubcategory": company_subcategory or "N/A",
        "nicCode": nic_code or "N/A",
        "industry": industry or "N/A",
        "filingStatus": filing_status or "N/A",
        "activeCompliance": active_compliance or "N/A",
        "lastUpdatedOn": normalize_display_date(last_updated),
        "addresses": addresses,
    }


def parse_money_amount(value: str) -> float:
    cleaned = clean_text(value).replace("₹", "").replace(",", "").replace("(", "").replace(")", "")
    if not cleaned or cleaned.upper() == "NA":
        return 0
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    return float(match.group(0)) if match else 0


def build_public_profile_url(name: str, cin: str) -> str:
    return f"{PUBLIC_COMPANY_PROFILE_BASE_URL}/{slugify(name)}-{clean_text(cin)}"


def parse_public_address(raw_address: str) -> list[dict[str, str]]:
    cleaned_raw = sanitize_public_value(raw_address)
    if cleaned_raw == "N/A":
        return []

    normalized_raw = re.sub(r"\.\s*Region\s*:\s*.*$", "", cleaned_raw, flags=re.I)
    parts = [clean_text(part) for part in re.split(r"[;,]", normalized_raw) if clean_text(part)]
    city = district = state = postal_code = ""
    country = "India" if "india" in normalized_raw.lower() or re.search(r"\bIN\b", normalized_raw) else ""

    postal_index = next((index for index, part in enumerate(parts) if re.search(r"\b\d{6}\b", part)), -1)
    country_index = next((index for index, part in enumerate(parts) if part.lower() in {"india", "in"}), -1)
    state_index = -1
    if country_index > 0:
        state_index = country_index - 1
    elif postal_index > 0:
        state_index = postal_index - 1
    if postal_index >= 0:
        postal_match = re.search(r"\b(\d{6})\b", parts[postal_index])
        postal_code = clean_text(postal_match.group(1)) if postal_match else ""
        if parts[postal_index] == postal_code:
            parts.pop(postal_index)
            if country_index > postal_index:
                country_index -= 1
            if state_index > postal_index:
                state_index -= 1
    if state_index >= 0 and state_index < len(parts):
        state = parts[state_index]
    city_index = state_index - 1 if state_index > 0 else -1
    district_index = city_index - 1 if city_index > 0 else -1
    if city_index >= 0 and city_index < len(parts):
        city = parts[city_index]
    if district_index >= 0 and district_index < len(parts):
        district = parts[district_index]

    line_cutoff = district_index if district_index > 0 else city_index if city_index > 0 else min(len(parts), 4)
    if line_cutoff <= 0:
        line_cutoff = min(len(parts), 4)
    line_parts = parts[:line_cutoff]

    return [
        {
            "type": "Registered Address",
            "line1": line_parts[0] if len(line_parts) > 0 else "",
            "line2": line_parts[1] if len(line_parts) > 1 else "",
            "line3": line_parts[2] if len(line_parts) > 2 else "",
            "line4": line_parts[3] if len(line_parts) > 3 else "",
            "locality": "",
            "district": district,
            "city": city or (parts[-1] if parts else ""),
            "state": state,
            "postalCode": postal_code,
            "country": country or "India",
            "raw": cleaned_raw,
        }
    ]


def extract_table_pairs(table: Any) -> dict[str, str]:
    pairs: dict[str, str] = {}
    if table is None:
        return pairs

    for row in table.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        if len(cells) == 4:
            pairs[clean_text(cells[0].get_text(" ", strip=True))] = clean_text(cells[1].get_text(" ", strip=True))
            pairs[clean_text(cells[2].get_text(" ", strip=True))] = clean_text(cells[3].get_text(" ", strip=True))
        elif len(cells) >= 2:
            pairs[clean_text(cells[0].get_text(" ", strip=True))] = clean_text(cells[1].get_text(" ", strip=True))
    return pairs


def extract_compact_pairs(table: Any) -> dict[str, str]:
    pairs: dict[str, str] = {}
    if table is None:
        return pairs

    known_prefixes = [
        "Authorized Capital",
        "Authorised Capital",
        "Paid-up Capital",
        "Paid-up capital",
        "Company Status",
        "Total Directors",
        "Total Partners",
        "AGM",
        "Balance Sheet",
    ]
    for row in table.select("tr"):
        text = clean_text(row.get_text(" ", strip=True))
        for prefix in known_prefixes:
            if text.lower().startswith(prefix.lower()):
                pairs[prefix] = clean_text(text[len(prefix) :])
                break
    return pairs


def build_falcon_profile_url(name: str, cin: str, company_type: str) -> str:
    entity_path = "LLP" if company_type == "LLP" or "-" in clean_text(cin) else "company"
    return f"{FALCON_COMPANY_PROFILE_BASE_URL}/{entity_path}/{slugify(name).upper()}-{clean_text(cin)}"


def scrape_falcon_directors(table: Any) -> list[dict[str, Any]]:
    directors: list[dict[str, Any]] = []
    if table is None:
        return directors

    for row in table.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        directors.append(
            {
                "din": clean_text(cells[0].get_text(" ", strip=True)),
                "name": clean_text(cells[1].get_text(" ", strip=True)),
                "designation": clean_text(cells[2].get_text(" ", strip=True)),
                "appointmentDate": normalize_display_date(cells[3].get_text(" ", strip=True)),
                "status": "Active",
                "totalDirectorships": "",
                "disqualified164": "",
                "dinDeactivated": "",
                "profileUrl": "",
                "contactEmail": "",
                "contactPhone": "",
                "contactWebsite": "",
                "contactAddress": "",
                "contactSource": "",
                "contactNote": "",
            }
        )
    return directors


def scrape_public_director_profile(session: requests.Session, profile_url: str) -> dict[str, str]:
    normalized_profile_url = clean_text(profile_url)
    if not normalized_profile_url:
        return {}

    response = session.get(normalized_profile_url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    merged_pairs: dict[str, str] = {}
    for table in soup.select("table"):
        merged_pairs.update(extract_table_pairs(table))
    for compact_table in soup.select("table.table-sm"):
        merged_pairs.update(extract_compact_pairs(compact_table))

    email = sanitize_public_value(
        merged_pairs.get("Business Email")
        or merged_pairs.get("Email")
        or merged_pairs.get("Email ID")
        or merged_pairs.get("E-mail")
        or "N/A"
    )
    phone = sanitize_public_value(
        merged_pairs.get("Business Phone")
        or merged_pairs.get("Contact Number")
        or merged_pairs.get("Phone")
        or merged_pairs.get("Telephone")
        or "N/A"
    )
    website = sanitize_public_value(merged_pairs.get("Website") or merged_pairs.get("Company Website") or "N/A")

    return {
        "profileUrl": normalized_profile_url,
        "contactEmail": email,
        "contactPhone": phone,
        "contactWebsite": website,
        "nationality": sanitize_public_value(merged_pairs.get("Nationality", "N/A")),
        "occupation": sanitize_public_value(merged_pairs.get("Occupation", "N/A")),
        "contactSource": "Public director profile",
    }


def scrape_falcon_company_profile(session: requests.Session, company: dict[str, Any]) -> dict[str, Any] | None:
    cin = clean_text(company.get("cin", ""))
    if not cin or cin == "N/A":
        return None

    profile_url = build_falcon_profile_url(company["name"], cin, company.get("type", ""))
    response = session.get(profile_url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    if "404" in response.text and "falconebiz" not in response.text.lower():
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return None

    core_pairs = extract_table_pairs(tables[0]) if len(tables) > 0 else {}
    tax_pairs: dict[str, str] = {}
    contact_pairs: dict[str, str] = {}
    for table in tables[1:]:
        pairs = extract_table_pairs(table)
        if not pairs:
            continue
        if not tax_pairs and any(key in pairs for key in {"GST Number", "PAN", "Nature", "Registration Date", "State"}):
            tax_pairs = pairs
        if not contact_pairs and any(key in pairs for key in {"Email", "Address", "Website", "Contact Number"}):
            contact_pairs = pairs
    directors_table = next((table for table in tables if "m-table" in (table.get("class") or [])), None)
    compact_table = next((table for table in tables if "table-sm" in (table.get("class") or [])), None)
    compact_pairs = extract_compact_pairs(compact_table)

    if not core_pairs and not contact_pairs and not compact_pairs:
        return None

    registered_address = sanitize_public_value(contact_pairs.get("Address", company.get("registeredAddress", "N/A")))
    email = sanitize_public_value(contact_pairs.get("Email", company.get("email", "N/A")))
    website = sanitize_public_value(contact_pairs.get("Website", company.get("website", "N/A")))
    phone = sanitize_public_value(contact_pairs.get("Contact Number", company.get("phone", "N/A")))
    directors = scrape_falcon_directors(directors_table)

    falcon_company = dict(company)
    falcon_company.update(
        {
            "profileUrl": company.get("profileUrl") or profile_url,
            "status": normalize_company_status(core_pairs.get("Company Status", compact_pairs.get("Company Status", company.get("status", "Active"))), company.get("status", "Active")),
            "incorporationDate": normalize_display_date(core_pairs.get("Date of Incorporation", company.get("incorporationDate", "N/A"))),
            "rocCode": sanitize_public_value(core_pairs.get("RoC", company.get("rocCode", "N/A"))),
            "registrationNumber": sanitize_public_value(core_pairs.get("Registration Number", company.get("registrationNumber", "N/A"))),
            "authCap": parse_money_amount(core_pairs.get("Authorized Capital", compact_pairs.get("Authorized Capital", compact_pairs.get("Authorised Capital", "")))) or company.get("authCap", 0),
            "puc": parse_money_amount(core_pairs.get("Paid-up capital", compact_pairs.get("Paid-up capital", compact_pairs.get("Paid-up Capital", "")))) or company.get("puc", 0),
            "industry": sanitize_public_value(core_pairs.get("Activity", tax_pairs.get("Nature", company.get("industry", "N/A")))),
            "registeredAddress": registered_address,
            "businessAddress": registered_address if registered_address != "N/A" else company.get("businessAddress", "N/A"),
            "addresses": parse_public_address(registered_address),
            "email": email,
            "website": website,
            "phone": phone,
            "gstin": sanitize_public_value(tax_pairs.get("GST Number", company.get("gstin", "N/A"))),
            "pan": sanitize_public_value(tax_pairs.get("PAN", company.get("pan", "N/A"))),
            "lastAGMDate": normalize_display_date(compact_pairs.get("AGM", company.get("lastAGMDate", "N/A"))),
            "lastBSDate": normalize_display_date(core_pairs.get("Date of Latest Balance Sheet", compact_pairs.get("Balance Sheet", company.get("lastBSDate", "N/A")))),
            "directors": directors,
            "remarks": f"{company.get('remarks', '')} FalconEbiz profile fields enriched.".strip(),
        }
    )
    return falcon_company


def merge_company_enrichment(base_company: dict[str, Any], update: dict[str, Any] | None) -> dict[str, Any]:
    if not update:
        return base_company

    merged = dict(base_company)
    override_fields = {
        "status",
        "type",
        "incorporationDate",
        "rocCode",
        "registrationNumber",
        "authCap",
        "puc",
        "lastAGMDate",
        "lastBSDate",
        "industry",
        "registeredAddress",
        "businessAddress",
        "profileUrl",
        "phone",
        "email",
        "website",
        "pan",
        "gstin",
    }
    list_fields = {"addresses", "directors", "charges"}

    for field, value in update.items():
        if field in list_fields:
            if not is_missing_value(value):
                merged[field] = value
            continue
        if field in override_fields:
            if field in {"email", "pan", "gstin"} and is_masked_public_value(value) and not is_missing_value(merged.get(field)):
                continue
            if not is_missing_value(value):
                merged[field] = value
            continue
        if is_missing_value(merged.get(field)) and not is_missing_value(value):
            merged[field] = value

    return merged


def attach_director_contact_details(session: requests.Session, company: dict[str, Any]) -> list[dict[str, Any]]:
    directors = company.get("directors") or []
    if not directors:
        return []

    company_email = sanitize_public_value(company.get("email", "N/A"))
    company_phone = sanitize_public_value(company.get("phone", "N/A"))
    company_website = sanitize_public_value(company.get("website", "N/A"))
    company_address = sanitize_public_value(company.get("registeredAddress", "N/A"))
    company_contact_available = any(value != "N/A" for value in [company_email, company_phone, company_website, company_address])

    enriched_directors: list[dict[str, Any]] = []
    for director in directors:
        enriched_director = dict(director)
        profile_url = clean_text(enriched_director.get("profileUrl", ""))

        if profile_url:
            try:
                director_profile = scrape_public_director_profile(session, profile_url)
                for field, value in director_profile.items():
                    if is_missing_value(enriched_director.get(field)) and not is_missing_value(value):
                        enriched_director[field] = value
            except Exception:
                pass

        if is_missing_value(enriched_director.get("contactEmail")) and company_email != "N/A":
            enriched_director["contactEmail"] = company_email
        if is_missing_value(enriched_director.get("contactPhone")) and company_phone != "N/A":
            enriched_director["contactPhone"] = company_phone
        if is_missing_value(enriched_director.get("contactWebsite")) and company_website != "N/A":
            enriched_director["contactWebsite"] = company_website
        if is_missing_value(enriched_director.get("contactAddress")) and company_address != "N/A":
            enriched_director["contactAddress"] = company_address

        if is_missing_value(enriched_director.get("contactSource")):
            enriched_director["contactSource"] = "Company public contact route" if company_contact_available else "No public contact route"

        if is_missing_value(enriched_director.get("contactNote")):
            enriched_director["contactNote"] = (
                "Direct personal contact was not published in the current public sources. Use the company's public contact channels."
                if company_contact_available
                else "No public director or company contact route was published in the current sources."
            )

        enriched_directors.append(enriched_director)

    return enriched_directors


def attach_company_freshness(company: dict[str, Any], *, snapshot_synced_at: str, profile_cached_at: str) -> dict[str, Any]:
    enriched = dict(company)
    enriched["snapshotSyncedAt"] = snapshot_synced_at or "N/A"
    enriched["profileCachedAt"] = profile_cached_at or "N/A"
    enriched["profileCacheTtlSeconds"] = PROFILE_CACHE_TTL_SECONDS
    return enriched


def derive_search_terms(company_name: str) -> list[str]:
    cleaned_name = clean_text(company_name)
    terms = [cleaned_name]
    simplified = re.sub(
        r"\b(PRIVATE LIMITED|LIMITED LIABILITY PARTNERSHIP|LLP|LIMITED|PRIVATE|PVT\.?\s*LTD\.?)\b",
        "",
        cleaned_name,
        flags=re.I,
    )
    simplified = clean_text(simplified)
    if simplified and simplified.upper() != cleaned_name.upper():
        terms.append(simplified)
    return list(dict.fromkeys(term for term in terms if term))


def fetch_google_news(session: requests.Session, company: dict[str, Any], limit: int = 5) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen_keys: set[str] = set()

    for term in derive_search_terms(company["name"]):
        response = session.get(
            GOOGLE_NEWS_RSS_URL,
            params={"q": f'"{term}" when:365d', "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        feed = BeautifulSoup(response.text, "xml")
        for item in feed.find_all("item"):
            title = clean_text(item.title.get_text(" ", strip=True) if item.title else "")
            link = clean_text(item.link.get_text(" ", strip=True) if item.link else "")
            source = clean_text(item.source.get_text(" ", strip=True) if item.source else "Google News")
            pub_date = normalize_display_date(item.pubDate.get_text(" ", strip=True) if item.pubDate else "")
            if not title:
                continue
            key = f"{title.lower()}|{source.lower()}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            items.append(
                build_news_item(
                    company["id"],
                    title,
                    source,
                    pub_date,
                    f"Latest public news mention for {company['name']} surfaced via Google News RSS.",
                    link,
                )
            )
            if len(items) >= limit:
                return items
    return items


def build_registry_updates(company: dict[str, Any]) -> list[dict[str, str]]:
    updates: list[dict[str, str]] = []
    if not is_missing_value(company.get("lastUpdatedOn")):
        updates.append(
            build_news_item(
                company["id"],
                f"{company['name']} registry profile refreshed",
                "Company Registry",
                company["lastUpdatedOn"],
                f"Public registry profile for {company['name']} shows its latest refresh on {company['lastUpdatedOn']}.",
                company.get("profileUrl", ""),
            )
        )
    if not is_missing_value(company.get("incorporationDate")):
        updates.append(
            build_news_item(
                company["id"],
                f"{company['name']} incorporation record",
                "Company Registry",
                company["incorporationDate"],
                f"{company['name']} was incorporated on {company['incorporationDate']}.",
                company.get("profileUrl", ""),
            )
        )
    if not is_missing_value(company.get("lastAGMDate")):
        updates.append(
            build_news_item(
                company["id"],
                f"{company['name']} AGM filing recorded",
                "Company Registry",
                company["lastAGMDate"],
                f"Latest AGM date available for {company['name']} is {company['lastAGMDate']}.",
                company.get("profileUrl", ""),
            )
        )
    if not is_missing_value(company.get("lastBSDate")):
        updates.append(
            build_news_item(
                company["id"],
                f"{company['name']} balance sheet update",
                "Company Registry",
                company["lastBSDate"],
                f"Latest balance sheet date available for {company['name']} is {company['lastBSDate']}.",
                company.get("profileUrl", ""),
            )
        )
    for director in (company.get("directors") or [])[:3]:
        if is_missing_value(director.get("appointmentDate")):
            continue
        updates.append(
            build_news_item(
                company["id"],
                f"{director['name']} associated with {company['name']}",
                "Company Registry",
                director["appointmentDate"],
                f"{director['name']} is listed as {director['designation']} from {director['appointmentDate']}.",
                director.get("profileUrl", "") or company.get("profileUrl", ""),
            )
        )
    for announcement in (company.get("announcementHistory") or [])[:3]:
        updates.append(
            build_news_item(
                company["id"],
                f"{announcement['announcementType']} for {company['name']}",
                "IBBI",
                announcement["announcementDate"],
                announcement["remarks"],
                announcement["registryUrl"],
            )
        )
    return updates


def build_company_news(session: requests.Session, company: dict[str, Any]) -> list[dict[str, str]]:
    try:
        external_news = fetch_google_news(session, company, limit=5)
    except Exception:
        external_news = []

    combined = external_news + build_registry_updates(company)
    deduped: dict[str, dict[str, str]] = {}
    for item in combined:
        key = f"{clean_text(item['title']).lower()}|{clean_text(item['date']).lower()}"
        deduped.setdefault(key, item)
    return sorted(
        deduped.values(),
        key=lambda item: (parse_date(item["date"]), clean_text(item["title"]).upper()),
        reverse=True,
    )[:8]


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

    profile_url = clean_text(company.get("profileUrl", ""))
    if profile_url:
        documents.append(
            {
                "formId": "PUBLIC_PROFILE",
                "fileName": "public-company-profile.html",
                "year": current_year,
                "dateOfFiling": normalize_display_date(company.get("lastUpdatedOn") or company.get("incorporationDate") or "N/A"),
                "category": "Public Profile Source",
                "source": "Public Source",
                "url": profile_url,
                "downloadUrl": profile_url,
            }
        )
        if "instafinancials.com/company/" in profile_url:
            documents.append(
                {
                    "formId": "DIRECTORS_SOURCE",
                    "fileName": "directors-listing.html",
                    "year": current_year,
                    "dateOfFiling": normalize_display_date(company.get("lastUpdatedOn") or "N/A"),
                    "category": "Directors Source",
                    "source": "InstaFinancials",
                    "url": f"{profile_url}/company-directors",
                    "downloadUrl": f"{profile_url}/company-directors",
                }
            )
            documents.append(
                {
                    "formId": "CHARGES_SOURCE",
                    "fileName": "charges-listing.html",
                    "year": current_year,
                    "dateOfFiling": normalize_display_date(company.get("lastUpdatedOn") or "N/A"),
                    "category": "Charges Source",
                    "source": "InstaFinancials",
                    "url": f"{profile_url}/company-charges",
                    "downloadUrl": f"{profile_url}/company-charges",
                }
            )

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

    source_urls = company.get("sourceUrls") or {}
    for source_key, source_url in source_urls.items():
        clean_source_url = clean_text(source_url)
        if not clean_source_url:
            continue
        documents.append(
            {
                "formId": f"SOURCE_{slugify(source_key)}",
                "fileName": f"{slugify(source_key)}.html",
                "year": current_year,
                "dateOfFiling": normalize_display_date(company.get("announcementDate") or company.get("lastUpdatedOn") or "N/A"),
                "category": "Government / Source Portal",
                "source": source_key,
                "url": clean_source_url,
                "downloadUrl": clean_source_url,
            }
        )

    discovered_pdf_urls: set[str] = set()
    for announcement in company.get("announcementHistory") or []:
        for url in [announcement.get("registryUrl", ""), announcement.get("remarks", "")]:
            for extracted_url in extract_urls(url):
                if is_probable_pdf_url(extracted_url):
                    discovered_pdf_urls.add(extracted_url)

    for item in company.get("news") or []:
        for extracted_url in extract_urls(item.get("url", "")):
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
                "source": "Discovered from source links",
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


def scrape_public_directors(session: requests.Session, profile_url: str) -> list[dict[str, Any]]:
    response = session.get(f"{profile_url}/company-directors", timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    directors: list[dict[str, Any]] = []

    section_map = {
        "directorContentHolder_currentDirectorsContainer": "Active",
        "directorContentHolder_pastDirectorsContainer": "Resigned",
    }
    for container_id, director_status in section_map.items():
        container = soup.find(id=container_id)
        if not container:
            continue
        table = container.find("table")
        if not table:
            continue
        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 7:
                continue
            name_link = cells[0].find("a")
            din_link = cells[1].find("a")
            directors.append(
                {
                    "din": clean_text(din_link.get_text(" ", strip=True) if din_link else cells[1].get_text(" ", strip=True)),
                    "name": clean_text(name_link.get_text(" ", strip=True) if name_link else cells[0].get_text(" ", strip=True)),
                    "designation": clean_text(cells[2].get_text(" ", strip=True)),
                    "appointmentDate": clean_text(cells[3].get_text(" ", strip=True)),
                    "status": director_status,
                    "totalDirectorships": clean_text(cells[4].get_text(" ", strip=True)),
                    "disqualified164": clean_text(cells[5].get_text(" ", strip=True)),
                    "dinDeactivated": clean_text(cells[6].get_text(" ", strip=True)),
                    "profileUrl": urljoin(f"{profile_url}/", name_link["href"]) if name_link and name_link.has_attr("href") else "",
                    "contactEmail": "",
                    "contactPhone": "",
                    "contactWebsite": "",
                    "contactAddress": "",
                    "contactSource": "",
                    "contactNote": "",
                }
            )
    return directors


def scrape_public_charges(session: requests.Session, profile_url: str) -> list[dict[str, Any]]:
    response = session.get(f"{profile_url}/company-charges", timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    charges: list[dict[str, Any]] = []

    def add_rows(section_id: str, status: str) -> None:
        section = soup.find(id=section_id)
        if not section:
            return
        table = section.find("table")
        if not table:
            return
        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) == 1:
                continue
            if len(cells) < 7:
                continue
            charges.append(
                {
                    "chargeId": clean_text(cells[0].get_text(" ", strip=True)),
                    "bankName": clean_text(cells[1].get_text(" ", strip=True)),
                    "amount": parse_money_amount(cells[2].get_text(" ", strip=True)),
                    "status": status,
                    "creationDate": clean_text(cells[3].get_text(" ", strip=True)),
                    "modificationDate": clean_text(cells[5].get_text(" ", strip=True)),
                    "outstandingYears": clean_text(cells[4].get_text(" ", strip=True)),
                    "assetsSecured": clean_text(cells[6].get_text(" ", strip=True)),
                }
            )

    add_rows("openChargesSection", "Open")
    add_rows("satisfiedChargesSection", "Closed")
    return charges


def scrape_public_company_profile(session: requests.Session, company: dict[str, Any]) -> dict[str, Any] | None:
    cin = clean_text(company.get("cin", ""))
    if not cin or cin == "N/A":
        return None

    profile_url = build_public_profile_url(company["name"], cin)
    response = session.get(profile_url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    if "404 Error" in response.text:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    highlights_table = soup.select_one("#companyHighlightsDataContainer table")
    pairs = extract_table_pairs(highlights_table)

    highlight_cards: dict[str, dict[str, str]] = {}
    for card in soup.select(".highlight-card"):
        title = clean_text(card.find("h3").get_text(" ", strip=True) if card.find("h3") else "")
        if not title:
            continue
        highlight_cards[title] = {
            "status": clean_text((card.select_one(".status") or card.select_one(".value")).get_text(" ", strip=True) if card.select_one(".status") or card.select_one(".value") else ""),
            "date": clean_text(card.select_one(".date").get_text(" ", strip=True) if card.select_one(".date") else ""),
            "text": clean_text(card.get_text(" ", strip=True)),
        }

    company_status_card = highlight_cards.get("Company Status", {})
    incorp_card = highlight_cards.get("Incorp. Date", {})
    balance_card = highlight_cards.get("Balance Sheet Date", {})
    industry_card = highlight_cards.get("Industry", {})

    authorised_match = re.search(r"Authorised Capital.*?₹([\d,]+)", response.text, re.S | re.I)
    paid_up_match = re.search(r"Paid up Capital.*?₹([\d,]+)", response.text, re.S | re.I)
    last_updated_match = re.search(r"As on\s*<strong>\s*([^<]+)", response.text, re.I)

    raw_address = sanitize_public_value(pairs.get("Address", company.get("registeredAddress", "N/A")))
    scraped_company = dict(company)
    scraped_company.update(
        {
            "profileUrl": profile_url,
            "lastUpdatedOn": normalize_display_date(last_updated_match.group(1)) if last_updated_match else "N/A",
            "status": normalize_company_status(company_status_card.get("status"), company.get("status", "Active")),
            "incorporationDate": normalize_display_date(incorp_card.get("status") or company.get("incorporationDate", "N/A")),
            "lastBSDate": normalize_display_date(balance_card.get("status") or company.get("lastBSDate", "N/A")),
            "lastAGMDate": normalize_display_date(re.sub(r"^AGM Date", "", balance_card.get("date", ""), flags=re.I).strip() or company.get("lastAGMDate", "N/A")),
            "industry": sanitize_public_value(industry_card.get("status") or company.get("industry", "N/A")),
            "nicCode": clean_text(re.sub(r"^NIC Code", "", industry_card.get("date", ""), flags=re.I)),
            "authCap": parse_money_amount(authorised_match.group(1)) if authorised_match else company.get("authCap", 0),
            "puc": parse_money_amount(paid_up_match.group(1)) if paid_up_match else company.get("puc", 0),
            "registrationNumber": sanitize_public_value(pairs.get("Registration No", company.get("registrationNumber", "N/A"))),
            "rocCode": sanitize_public_value(pairs.get("ROC Code", company.get("rocCode", "N/A"))),
            "category": pairs.get("Company Category", company.get("category", "")) or company.get("category", ""),
            "companySubcategory": pairs.get("Company SubCategory", company.get("companySubcategory", "")),
            "type": "Private" if "Private" in pairs.get("Company Class", "") else company.get("type", "Public"),
            "activeCompliance": sanitize_public_value(pairs.get("Active Compliant", company.get("activeCompliance", "N/A"))),
            "statusUnderCirp": sanitize_public_value(pairs.get("Status Under CIRP", company.get("statusUnderCirp", "N/A"))),
            "filingStatus": sanitize_public_value(pairs.get("Filing Status For Last 2 Years", company.get("filingStatus", "N/A"))),
            "email": sanitize_public_value(pairs.get("Email ID", company.get("email", "N/A"))),
            "phone": sanitize_public_value(pairs.get("Phone", company.get("phone", "N/A"))),
            "website": sanitize_public_value(pairs.get("Website", company.get("website", "N/A"))),
            "registeredAddress": raw_address or company.get("registeredAddress", "N/A"),
            "businessAddress": raw_address or company.get("businessAddress", "N/A"),
            "addresses": parse_public_address(raw_address),
            "directors": scrape_public_directors(session, profile_url),
            "charges": scrape_public_charges(session, profile_url),
            "remarks": f"{company.get('remarks', '')} Public profile fields enriched from InstaFinancials.".strip(),
        }
    )
    return scraped_company


def merge_master_with_ibbi(master_company: dict[str, Any], ibbi_company: dict[str, Any]) -> dict[str, Any]:
    merged = dict(master_company)

    for field in [
        "status",
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
        "applicants",
        "insolvencyProfessionals",
        "announcementHistory",
        "trendData",
    ]:
        merged[field] = ibbi_company.get(field, merged.get(field))

    merged["category"] = master_company.get("category") or ibbi_company.get("category")
    merged["sourceSection"] = "master+ibbi"
    return attach_company_source_metadata(merged)


def load_local_master_companies() -> tuple[list[dict[str, Any]], int]:
    if not MASTER_DATA_DIR.exists():
        return [], 0

    companies: list[dict[str, Any]] = []
    loaded_files = 0

    for file_path in sorted(MASTER_DATA_DIR.iterdir()):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        if suffix not in {".csv", ".tsv", ".json"}:
            continue

        rows: list[dict[str, Any]] = []
        if suffix in {".csv", ".tsv"}:
            delimiter = "," if suffix == ".csv" else "\t"
            with file_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as file_obj:
                rows = list(csv.DictReader(file_obj, delimiter=delimiter))
        elif suffix == ".json":
            with file_path.open("r", encoding="utf-8") as file_obj:
                payload = json.load(file_obj)
            if isinstance(payload, list):
                rows = [item for item in payload if isinstance(item, dict)]

        for row in rows:
            company = build_master_company(row)
            if company:
                companies.append(company)

        loaded_files += 1

    deduped: dict[str, dict[str, Any]] = {}
    for company in companies:
        key = company["cin"] if company.get("cin") and company["cin"] != "N/A" else slugify(company["name"])
        deduped[key] = company

    name_deduped: dict[str, dict[str, Any]] = {}
    for company in deduped.values():
        name_key = clean_text(company["name"]).upper()
        if name_key and name_key not in name_deduped:
            name_deduped[name_key] = company

    return list(name_deduped.values()), loaded_files


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
        master_companies, master_files_loaded = load_local_master_companies()
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

        ibbi_companies = [build_company(history) for history in grouped.values()]
        master_by_key = {
            (company["cin"] if company.get("cin") and company["cin"] != "N/A" else slugify(company["name"])): company
            for company in master_companies
        }

        companies: list[dict[str, Any]] = []
        for ibbi_company in ibbi_companies:
            key = ibbi_company["cin"] if ibbi_company["cin"] != "N/A" else slugify(ibbi_company["name"])
            master_company = master_by_key.pop(key, None)
            if master_company:
                companies.append(merge_master_with_ibbi(master_company, ibbi_company))
            else:
                ibbi_company["sourceSection"] = "ibbi"
                companies.append(ibbi_company)

        companies.extend(master_by_key.values())
        companies = [attach_company_source_metadata(company) for company in companies]
        companies.sort(key=lambda item: (rank_company(item, item["name"])[1], clean_text(item["name"]).upper()), reverse=True)
        all_announcements.sort(key=lambda item: parse_date(item["announcementDate"]), reverse=True)

        self._companies = companies
        self._master_companies = master_companies
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
            "masterCompanies": len(master_companies),
            "masterFilesLoaded": master_files_loaded,
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
                cached_company["directors"] = attach_director_contact_details(self._session, cached_company)
                cached_company["documents"] = build_company_documents(cached_company)
                self._profile_cache[cache_key] = {
                    "data": cached_company,
                    "fetched_at": fetched_at,
                    "cached_at": cache_entry.get("cached_at", cached_at),
                }
                return cached_company

        if not force:
            persisted_company = self._get_persisted_company_detail(company)
            if persisted_company:
                persisted_company = attach_company_source_metadata(persisted_company)
                persisted_company["documents"] = build_company_documents(persisted_company)
                persisted_company = attach_company_freshness(
                    persisted_company,
                    snapshot_synced_at=self._stats.get("lastSyncedAt", "N/A"),
                    profile_cached_at=clean_text(persisted_company.get("profileCachedAt", "")) or cached_at,
                )
                persisted_company["directors"] = attach_director_contact_details(self._session, persisted_company)
                if cache_key:
                    self._profile_cache[cache_key] = {
                        "data": persisted_company,
                        "fetched_at": time.time(),
                        "cached_at": persisted_company.get("profileCachedAt", cached_at),
                    }
                return persisted_company

        enriched = dict(company)

        try:
            enriched = merge_company_enrichment(enriched, scrape_public_company_profile(self._session, enriched))
        except Exception:
            pass

        try:
            enriched = merge_company_enrichment(enriched, scrape_falcon_company_profile(self._session, enriched))
        except Exception:
            pass

        try:
            enriched["news"] = build_company_news(self._session, enriched)
        except Exception:
            enriched["news"] = build_registry_updates(enriched)

        enriched["directors"] = attach_director_contact_details(self._session, enriched)
        enriched = attach_company_source_metadata(enriched)
        enriched["documents"] = build_company_documents(enriched)

        geocode_key = clean_text(
            (enriched.get("addresses") or [{}])[0].get("raw") if enriched.get("addresses") else enriched.get("registeredAddress", "")
        )
        if geocode_key:
            try:
                if geocode_key not in self._geocode_cache:
                    self._geocode_cache[geocode_key] = geocode_company_address(self._session, geocode_key) or {}
                if self._geocode_cache.get(geocode_key):
                    enriched["mapLocation"] = self._geocode_cache[geocode_key]
                    if enriched.get("addresses"):
                        if "latitude" in self._geocode_cache[geocode_key]:
                            enriched["addresses"][0]["latitude"] = self._geocode_cache[geocode_key]["latitude"]
                        if "longitude" in self._geocode_cache[geocode_key]:
                            enriched["addresses"][0]["longitude"] = self._geocode_cache[geocode_key]["longitude"]
            except Exception:
                pass

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
        {
            "id": "mca_master_data",
            "name": "MCA Master Data",
            "portalType": "government",
            "mode": "manual-assisted",
            "url": MCA_MASTER_DATA_URL,
        },
        {
            "id": "gst_taxpayer_search",
            "name": "GST Taxpayer Search",
            "portalType": "government",
            "mode": "manual-assisted",
            "url": GST_TAXPAYER_SEARCH_URL,
        },
        {
            "id": "udyam_verify",
            "name": "Udyam Verify",
            "portalType": "government",
            "mode": "manual-assisted",
            "url": UDYAM_SEARCH_URL,
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
