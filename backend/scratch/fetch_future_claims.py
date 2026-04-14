import urllib.request
from bs4 import BeautifulSoup
url = 'https://ibbi.gov.in/claims/claim-process/L51909MH2007PLC268269'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        
        tables = soup.find_all('table')
        print(f'Total Tables: {len(tables)}')
        for i, t in enumerate(tables):
            print(f'Table {i}:')
            for tr in t.find_all('tr')[:10]:
                cells = [c.get_text(strip=True)[:40] for c in tr.find_all(['th', 'td'])]
                print('  ', cells)
        
        docs = soup.find_all('a', href=True)
        print('\nClaims documents:')
        for d in docs:
            href = d.get('href', '')
            if 'uploads' in href.lower():
                print(f' - {d.get_text(strip=True)} -> {href}')
except Exception as e:
    print(e)
