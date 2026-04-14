import urllib.request
from bs4 import BeautifulSoup

req = urllib.request.Request('https://ibbi.gov.in/claims/corporate-personals', headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response:
    html = response.read().decode('utf-8')

soup = BeautifulSoup(html, 'html.parser')
for a in soup.find_all('a', href=True):
    if 'claims/claim-process/' in a['href']:
        print(a['href'])
