import sys
import os
from datetime import datetime

# Add parent directory to path so we can import db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

def view_today_updates():
    if not db.init_db():
        return

    conn = db._get_connection()
    cur = conn.cursor(dictionary=True)
    
    # Get current date in YYYY-MM-DD format
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    print("\n" + "="*80)
    print(f"{'NEW COMPANIES ADDED TO DATABASE TODAY (' + today + ')':^80}")
    print("="*80)
    print(f"{'COMPANY NAME':<45} | {'CIN':<25}")
    print("-" * 80)
    
    # Query announcements added today
    # Using synced_at to see when it actually hit our database
    query = "SELECT debtor_name, cin FROM announcements WHERE DATE(synced_at) = %s LIMIT 50"
    cur.execute(query, (today,))
    rows = cur.fetchall()
    
    if not rows:
        print(f"{'No new companies added today yet.':^80}")
    else:
        # Use a set to avoid duplicates if multiple announcements for same company
        seen = set()
        count = 0
        for r in rows:
            name = r['debtor_name']
            cin = r['cin']
            if name not in seen:
                print(f"{name[:43]:<45} | {cin:<25}")
                seen.add(name)
                count += 1
        
        print("-" * 80)
        print(f"Total Unique Companies Added Today: {count}")
    
    print("="*80 + "\n")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    view_today_updates()
