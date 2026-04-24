import sys
import os
import json

# Add parent directory to path so we can import db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

def view_documents():
    if not db.init_db():
        print("Failed to connect to TiDB Cloud.")
        return

    # Get companies and check their JSON data
    companies = db.get_all_companies()
    
    print("\n" + "="*100)
    print(f"{'STORED DOCUMENTS (PDF/URLS) IN TIDB CLOUD':^100}")
    print("="*100)
    print(f"{'COMPANY NAME':<40} | {'DOCUMENT TYPE / LINK':<55}")
    print("-" * 100)
    
    count = 0
    for c in companies:
        # Check if documentUrl exists in the data_json
        doc_url = c.get("documentUrl") or c.get("registryUrl")
        if doc_url and (".pdf" in doc_url.lower() or "http" in doc_url.lower()):
            name = c.get("name", "N/A")[:38]
            print(f"{name:<40} | {doc_url[:55]}")
            count += 1
            if count >= 15: # Just show first 15 with docs
                break
    
    print("-" * 100)
    print(f"Total Companies with Documents checked: {count}")
    print("="*100 + "\n")

if __name__ == "__main__":
    view_documents()
