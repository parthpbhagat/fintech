import requests
from bs4 import BeautifulSoup

def debug_analytics(field_id):
    url = f"https://ibbi.gov.in/en/insolvency-professional/details?fieldid={field_id}&type=Assignment_Analytics"
    print(f"Fetching {url}")
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    if resp.ok:
        print("Response OK")
        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")
        print(f"Found {len(tables)} tables")
        for i, table in enumerate(tables):
            print(f"Table {i+1} headers: {[th.text.strip() for th in table.find_all('th')]}")
            # print rows
            rows = table.find_all("tr")
            print(f"Table {i+1} rows: {len(rows)}")
    else:
        print(f"Response Error: {resp.status_code}")

if __name__ == "__main__":
    debug_analytics("MjMy") # Nilesh Sharma
