import sys
import os

# Add parent directory to path so we can import db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

def insert_test_data():
    print("Initializing DB connection...")
    if not db.init_db():
        print("Failed to connect to TiDB Cloud.")
        return

    test_companies = [
        {
            "id": "L17110MH1973PLC019786",
            "cin": "L17110MH1973PLC019786",
            "name": "RELIANCE INDUSTRIES LIMITED",
            "status": "Active",
            "type": "Public",
            "sourceSection": "Testing",
            "announcementDate": "2024-01-01"
        },
        {
            "id": "L22210MH1995PLC084781",
            "cin": "L22210MH1995PLC084781",
            "name": "TATA CONSULTANCY SERVICES LIMITED",
            "status": "Active",
            "type": "Public",
            "sourceSection": "Testing",
            "announcementDate": "2024-01-02"
        },
        {
            "id": "L85110KA1981PLC013115",
            "cin": "L85110KA1981PLC013115",
            "name": "INFOSYS LIMITED",
            "status": "Active",
            "type": "Public",
            "sourceSection": "Testing",
            "announcementDate": "2024-01-03"
        }
    ]

    print(f"Inserting {len(test_companies)} companies into TiDB Cloud...")
    db.upsert_companies(test_companies)
    print("Done! Check your TiDB Cloud dashboard or run a query.")

if __name__ == "__main__":
    insert_test_data()
