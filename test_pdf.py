import requests
import re

print("Fetching PSL...")
resp = requests.get("http://localhost:8005/company/PSL")
data = resp.json()

target_urls = set()
for ann in data.get("announcementHistory", []):
    url = ann.get("registryUrl")
    if url and url.startswith("http"):
        target_urls.add(url)

headers = {"User-Agent": "Mozilla/5.0"}
with open("test_results.txt", "w", encoding="utf-8") as f:
    for url in target_urls:
        f.write(f"Testing URL: {url}\n")
        try:
            r = requests.get(url, headers=headers, timeout=10)
            f.write(f"Status: {r.status_code}\n")
            matches = re.findall(r'(https?://[^"\'\s]+\.pdf|/[^"\'\s]+\.pdf)', r.text, re.IGNORECASE)
            f.write(f"Found PDFs: {list(set(matches))}\n")
        except Exception as e:
            f.write(f"Error: {str(e)}\n")
