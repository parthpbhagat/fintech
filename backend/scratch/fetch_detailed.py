import urllib.request
from bs4 import BeautifulSoup
url = 'https://ibbi.gov.in/claims/front-claim-details/19085'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response:
    html = response.read().decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    tables = soup.find_all('table')
    t = tables[0]
    for tr in t.find_all('tr'):
        cells = tr.find_all(['th', 'td'])
        row_txt = []
        for c in cells:
            txt = c.get_text(strip=True)[:25]
            a = c.find('a', href=True)
            if a:
                txt += ' [' + a['href'] + ']'
            row_txt.append(txt)
        print('  ', row_txt)
