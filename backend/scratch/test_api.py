import urllib.request
import json
# Targeted test for Version 17 of Future Retail
cin = 'L51909MH2007PLC268269'
url = f'http://127.0.0.1:8005/company/{cin}/claims/merged'
req = urllib.request.Request(url)
print(f"Requesting merged claims for {cin}... this might take a minute.")
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        print(f"Received {len(data)} versions")
        for v in data:
            if "Version 17" in v.get("version", ""):
                print(f"--- Analysis of {v.get('version')} ---")
                summary = v.get("summaryTable", [])
                print(f"Summary table has {len(summary)} rows")
                for row in summary:
                    cat = row.get("category", "")
                    rec_count = row.get("receivedCount")
                    rec_amt = row.get("receivedAmount")
                    adm_amt = row.get("admittedAmount")
                    print(f" - {cat}: Rec={rec_count}, RecAmt={rec_amt}, AdmAmt={adm_amt}")
                    if row.get("documentLink"):
                        print(f"   [DOC]: {row.get('documentLink')}")
except Exception as e:
    print(f"Error: {e}")
