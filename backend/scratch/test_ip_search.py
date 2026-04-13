import requests
from bs4 import BeautifulSoup
import re

def test_search():
    url = "https://ibbi.gov.in/en/ips-register/view-ip/1"
    # To search, we might need to send post data.
    # Let's try to get the page first and see if there are any hidden inputs for search.
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })
    
    # Actually, many IBBI pages allow query params.
    search_url = f"{url}?name=Nilesh+Sharma"
    print(f"Searching: {search_url}")
    resp = session.get(search_url, timeout=20)
    print(f"Status: {resp.status_code}")
    
    soup = BeautifulSoup(resp.text, "html.parser")
    # Find links with insolvency-professional/details
    links = soup.find_all("a", href=re.compile(r"insolvency-professional/details\?fieldid="))
    for link in links:
        print(f"Found link: {link['href']}")
        # Extract name
        name = link.get_text(strip=True)
        print(f"Name: {name}")

if __name__ == "__main__":
    test_search()
