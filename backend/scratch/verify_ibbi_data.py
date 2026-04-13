import requests
import json

BASE_URL = "http://localhost:8000" # As seen in metadata or typical default
# Wait, metadata says pipeline.py is running. Let's check port.

def test_enrichment(cin):
    print(f"Testing enrichment for CIN: {cin}")
    url = f"http://localhost:8005/company/{cin}?fresh=1"
    try:
        response = requests.get(url, timeout=60)
        data = response.json()
        
        print("\n--- Directors ---")
        for d in data.get("directors", []):
            print(f"- {d.get('name')} ({d.get('designation')})")
            
        print("\n--- Charges ---")
        for c in data.get("charges", []):
            print(f"- {c.get('bankName')}: {c.get('details')}")
            
        print("\n--- News ---")
        for n in data.get("news", []):
            print(f"- {n.get('date')}: {n.get('title')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_enrichment("L74899DL1990PLC041350") # Era Infra Engineering
