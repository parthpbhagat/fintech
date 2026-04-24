import sys
import os

# Add parent directory to path so we can import db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

def view_data():
    if not db.init_db():
        print("Failed to connect to TiDB Cloud.")
        return

    companies = db.get_all_companies()
    
    print("\n" + "="*80)
    print(f"{'TiDB CLOUD DATA VIEW':^80}")
    print("="*80)
    print(f"{'CIN':<25} | {'COMPANY NAME':<40} | {'STATUS':<10}")
    print("-" * 80)
    
    for c in companies:
        cin = c.get("cin", "N/A")
        name = c.get("name", "N/A")[:38]
        status = c.get("status", "N/A")
        print(f"{cin:<25} | {name:<40} | {status:<10}")
    
    print("-" * 80)
    print(f"Total Companies Found: {len(companies)}")
    print("="*80 + "\n")

if __name__ == "__main__":
    view_data()
