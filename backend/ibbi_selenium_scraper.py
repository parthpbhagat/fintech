import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin

def clean_text(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.replace("\n", " ").replace("\r", " ").replace("\t", " ").split()).strip()

def scrape_ibbi_claims_with_selenium(cin: str) -> dict:
    """Legacy function, acts as a wrapper returning basic dict for backward compatibility in parts of the project."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("window-size=1920,1080")
    
    data = {}
    try:
        driver = webdriver.Chrome(options=options)
        urls = {
            "seleniumClaimProcess": f"https://ibbi.gov.in/claims/claim-process/{cin}",
            "seleniumInnerProcess": f"https://ibbi.gov.in/claims/inner-process/{cin}"
        }
        for key, url in urls.items():
            driver.get(url)
            time.sleep(3)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            tables = soup.find_all("table")
            if tables:
                headers = [clean_text(th.get_text()) for th in tables[0].find_all(["th"])]
                if not headers:
                    first_row = tables[0].find("tr")
                    if first_row:
                        headers = [clean_text(td.get_text()) for td in first_row.find_all(["td"])]
                rows = []
                for tr in tables[0].find_all("tr")[1:]:
                    tds = tr.find_all("td")
                    row_dict = {}
                    for i, td in enumerate(tds):
                        h = headers[i] if i < len(headers) else f"col_{i}"
                        row_dict[h] = clean_text(td.get_text())
                    if row_dict:
                        rows.append(row_dict)
                data[key] = {
                    "id": key,
                    "title": "Claims Process (Selenium)" if "claim" in key else "Inner Process Details (Selenium)",
                    "url": url,
                    "headers": headers,
                    "rows": rows
                }
    except Exception as e:
        print(f"[SELENIUM] Error scraping {cin}: {e}")
    finally:
        try: driver.quit()
        except: pass
    return data

def scrape_all_claims_with_selenium(cin: str) -> list:
    """
    Deep scrapes the IBBI claims specifically structured for the merged claims API.
    Visits the parent process directory, extracts versions, then clicks/visits every 
    inner detail page and extracts the full summary + precise document links.
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("window-size=1920,1080")
    
    result_versions = []
    
    try:
        driver = webdriver.Chrome(options=options)
        base_url = f"https://ibbi.gov.in/claims/claim-process/{cin}"
        driver.get(base_url)
        time.sleep(4) # Wait for complete page load
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # 1. Extract Versions
        versions = []
        table = soup.find("table")
        if not table:
            return []
            
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all("td")
            if len(cells) >= 5:
                rp_name = clean_text(cells[1].get_text())
                version_name = clean_text(cells[2].get_text())
                date = clean_text(cells[3].get_text())
                
                # The 'View Details' column usually has a link
                a_tag = cells[4].find("a", href=True)
                detail_url = a_tag["href"] if a_tag else None
                if detail_url and not detail_url.startswith("http"):
                    detail_url = urljoin("https://ibbi.gov.in", detail_url)
                    
                if version_name and detail_url:
                    versions.append({
                        "version": version_name,
                        "rp_name": rp_name,
                        "date": date,
                        "detail_url": detail_url
                    })
                    
        # 2. Extract Data for Each Version
        for v in versions:
            driver.get(v["detail_url"])
            time.sleep(4) # Wait for tabs and dynamically loaded claims table
            
            detail_soup = BeautifulSoup(driver.page_source, "html.parser")
            
            # Find the summary table for this version
            summary_rows = []
            detail_table = detail_soup.find("table")
            if detail_table:
                # The summary table is 11 columns wide ideally
                # Skip first 3 irregular header rows, but let's do it safely by finding digits or category keywords
                for tr in detail_table.find_all("tr"):
                    cells = tr.find_all(["td", "th"])
                    if len(cells) < 3: continue
                    
                    texts = []
                    for c in cells:
                        text = clean_text(c.get_text())
                        if not text:
                            # Check for input or textarea
                            inp = c.find(["input", "textarea"])
                            if inp and inp.has_attr("value"):
                                text = clean_text(inp["value"])
                            elif inp:
                                text = clean_text(inp.get_text())
                        texts.append(text)
                    
                    # Identify category row (either starts with a number like '1.' or is 'Total')
                    category_text = texts[1] if len(texts) > 1 else ""
                    is_row = False
                    if texts and texts[0]:
                        first_cell = texts[0].replace(".", "").strip()
                        if first_cell.isdigit() or "Total" in texts[0]:
                            is_row = True
                    if not is_row and ("Total" in category_text or "Category" in category_text):
                        is_row = False # Header likely
                    elif not is_row and len(texts) >= 6 and any(t.replace(",","").replace(".","").isdigit() for t in texts[2:6]):
                        is_row = True # Fallback for rows without Sr No

                    if is_row:
                        row_data = {
                            "srNo": texts[0] if len(texts) > 0 else "",
                            "category": texts[1] if len(texts) > 1 else "",
                            "receivedCount": texts[2] if len(texts) > 2 else "0",
                            "receivedAmount": texts[3] if len(texts) > 3 else "0",
                            "admittedCount": texts[4] if len(texts) > 4 else "0",
                            "admittedAmount": texts[5] if len(texts) > 5 else "0",
                            "contingentAmount": texts[6] if len(texts) > 6 else "0",
                            "rejectedAmount": texts[7] if len(texts) > 7 else "0",
                            "underVerificationAmount": texts[8] if len(texts) > 8 else "0",
                            "remarks": texts[10] if len(texts) > 10 else ""
                        }
                        
                        # Crucial step: Extract specific PDF links in 'Details in Annexure' (Column index 9)
                        doc_url = ""
                        if len(cells) > 9:
                            a_doc = cells[9].find("a", href=True)
                            if a_doc:
                                doc_url = urljoin("https://ibbi.gov.in", a_doc["href"])
                        row_data["documentLink"] = doc_url
                        
                        summary_rows.append(row_data)

            # 3. Extract global document links associated with this claim version
            global_docs = []
            for a_tag in detail_soup.find_all("a", href=True):
                href = a_tag["href"]
                if "uploads/claim" in href.lower() or "claims/generate" in href.lower() or "generate" in href.lower():
                    # It's highly likely a global claim document or an annexure
                    doc_title = clean_text(a_tag.get_text()) or href.split("/")[-1]
                    # Exclude the ones we already attached to summary rows to prevent dupes
                    link_full = urljoin("https://ibbi.gov.in", href)
                    if not any(link_full == sr["documentLink"] for sr in summary_rows):
                        global_docs.append({
                            "title": doc_title,
                            "url": link_full
                        })

            result_versions.append({
                "version": v["version"],
                "rp_name": v["rp_name"],
                "date": v["date"],
                "summaryTable": summary_rows,
                "globalDocs": global_docs
            })

    except Exception as e:
        print(f"[SELENIUM SCRAPING DEEP] Error scraping {cin}: {e}")
    finally:
        try: driver.quit()
        except: pass
        
    return result_versions
