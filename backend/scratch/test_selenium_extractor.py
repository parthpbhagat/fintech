import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import json

def extract_table_data(html: str):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    all_table_data = []
    
    # Sometimes details are in a simple div grid instead of table, but we will focus on tables
    for idx, table in enumerate(tables):
        headers = []
        thead = table.find("thead")
        if thead:
            for th in thead.find_all("th"):
                headers.append(th.get_text(" ", strip=True))
        else:
            first_row = table.find("tr")
            if first_row and first_row.find("th"):
                for th in first_row.find_all(["th", "td"]):
                    headers.append(th.get_text(" ", strip=True))

        rows = []
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds: continue
            row_dict = {}
            for i, td in enumerate(tds):
                header = headers[i] if i < len(headers) else f"col_{i}"
                if not header: header = f"col_{i}"
                row_dict[header] = td.get_text(" ", strip=True)
            rows.append(row_dict)
            
        if headers or rows:
            all_table_data.append({
                "headers": headers,
                "rows": rows
            })
    return all_table_data

def test_ibbi_selenium(cin: str):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("window-size=1920,1080")
    
    driver = webdriver.Chrome(options=options)
    
    urls_to_test = [
        f"https://ibbi.gov.in/claims/claim-process/{cin}",
        f"https://ibbi.gov.in/claims/inner-process/{cin}"
    ]
    
    output = {}
    
    for url in urls_to_test:
        driver.get(url)
        time.sleep(3) # Wait for Ajax
        html = driver.page_source
        tables = extract_table_data(html)
        output[url] = tables
            
    driver.quit()
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    cin = sys.argv[1] if len(sys.argv) > 1 else "L29150PN1989PLC054143"
    test_ibbi_selenium(cin)
