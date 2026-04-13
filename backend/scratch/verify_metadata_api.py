import requests

BASE_URL = "http://localhost:8005"

def test_metadata_api():
    name = "Test Professional"
    print(f"Testing for {name}")
    
    # 1. POST
    data = {"links": [{"id": 1, "label": "Test Link", "url": "https://example.com"}]}
    resp = requests.post(f"{BASE_URL}/professional/{name}/metadata", json=data)
    print(f"POST Response: {resp.status_code} - {resp.json()}")
    
    # 2. GET
    resp = requests.get(f"{BASE_URL}/professional/{name}/metadata")
    print(f"GET Response: {resp.status_code} - {resp.json()}")

if __name__ == "__main__":
    test_metadata_api()
