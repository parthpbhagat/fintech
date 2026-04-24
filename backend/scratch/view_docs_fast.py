import sys
import os
import json

# Add parent directory to path so we can import db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

def view_docs_fast():
    if not db.init_db():
        return

    conn = db._get_connection()
    cur = conn.cursor(dictionary=True)
    
    # Fast SQL query to find rows with PDFs
    query = "SELECT name, data_json FROM companies WHERE data_json LIKE '%pdf%' LIMIT 10"
    cur.execute(query)
    rows = cur.fetchall()
    
    print("\n" + "="*100)
    print(f"{'FAST DOCUMENT VIEW (SQL FILTERED)':^100}")
    print("="*100)
    print(f"{'COMPANY NAME':<40} | {'DOCUMENT URL (PDF)':<55}")
    print("-" * 100)
    
    for r in rows:
        data = json.loads(r['data_json'])
        doc_url = data.get("documentUrl", "N/A")
        print(f"{r['name'][:38]:<40} | {doc_url[:55]}")
    
    print("="*100 + "\n")
    cur.close()
    conn.close()

if __name__ == "__main__":
    view_docs_fast()
