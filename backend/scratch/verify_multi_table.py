import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote

def clean_text(text):
    return " ".join(text.split())

def test_multi_table_scrape(field_id):
    url = f"https://ibbi.gov.in/en/insolvency-professional/details?fieldid={field_id}&type=AFA_Details"
    print(f"Fetching {url}")
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    if resp.ok:
        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")
        print(f"Found {len(tables)} tables")
        
        for i, table in enumerate(tables):
            print(f"\n--- TABLE {i+1} ---")
            headers = [clean_text(th.get_text(" ", strip=True)) for th in table.find_all("th")]
            if not headers:
                print("Vertical table")
                for tr in table.find_all("tr"):
                    cells = tr.find_all(["td", "th"])
                    if len(cells) >= 2:
                        k = clean_text(cells[0].get_text(" ", strip=True))
                        v = clean_text(cells[1].get_text(" ", strip=True))
                        print(f"{k}: {v}")
            else:
                print(f"Horizontal table. Headers: {headers}")
                for tr in table.find_all("tr")[1:3]: # Just 2 rows
                    cells = tr.find_all("td")
                    if len(cells) >= len(headers):
                        row = [clean_text(td.get_text(" ", strip=True)) for td in cells]
                        print(f"Row: {row}")

if __name__ == "__main__":
    test_multi_table_scrape("MTA%3D") # Navneet Kumar Gupta
