import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

def test_ibbi_selenium(cin: str):
    print(f"Testing for CIN: {cin}")
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("window-size=1920,1080")
    
    driver = webdriver.Chrome(options=options)
    
    urls_to_test = [
        f"https://ibbi.gov.in/claims/inner-process/{cin}",
        f"https://ibbi.gov.in/claims/claim-process/{cin}",
        f"https://ibbi.gov.in/claims/innerProcess/{cin}",
        f"https://ibbi.gov.in/claims/claimProcess/{cin}"
    ]
    
    for url in urls_to_test:
        print(f"\n--- Loading URL: {url} ---")
        try:
            driver.get(url)
            time.sleep(2) # Give it some time to load
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            tables = soup.find_all("table")
            print(f"Found {len(tables)} tables")
            if len(tables) > 0:
                print(f"First table headers:")
                print([th.text.strip() for th in tables[0].find_all("th")])
            print("Title:", driver.title)
        except Exception as e:
            print("Error loading:", str(e))
            
    driver.quit()

if __name__ == "__main__":
    # Use a known CIN from the DB or a placeholder.
    # We can try a typical known CIN
    test_ibbi_selenium("L29150PN1989PLC054143") # Just a guess format. I'll test with a real one if needed.
