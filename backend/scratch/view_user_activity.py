import sys
import os
from datetime import datetime

# Add parent directory to path so we can import db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

def view_user_activity():
    if not db.init_db():
        return

    conn = db._get_connection()
    cur = conn.cursor(dictionary=True)
    
    print("\n" + "="*80)
    print(f"{'USER ACTIVITY MONITOR (TiDB Cloud)':^80}")
    print("="*80)
    
    # 1. Total Users
    cur.execute("SELECT COUNT(*) as total FROM users")
    total_users = cur.fetchone()['total']
    print(f"Total Registered Users: {total_users}")
    
    # 2. Latest 5 Signups
    print("\n--- LATEST SIGNUPS ---")
    print(f"{'NAME':<30} | {'EMAIL':<30} | {'DATE':<20}")
    cur.execute("SELECT name, email, created_at FROM users ORDER BY created_at DESC LIMIT 5")
    for r in cur.fetchall():
        print(f"{str(r['name'])[:28]:<30} | {str(r['email'])[:28]:<30} | {str(r['created_at'])}")
        
    # 3. Latest 10 Logins
    print("\n--- LATEST LOGINS ---")
    print(f"{'EMAIL':<35} | {'IP ADDRESS':<20} | {'LOGIN AT':<20}")
    cur.execute("SELECT user_email, ip_address, login_at FROM user_logins ORDER BY login_at DESC LIMIT 10")
    for r in cur.fetchall():
        print(f"{str(r['user_email'])[:33]:<35} | {str(r['ip_address']):<20} | {str(r['login_at'])}")
    
    print("="*80 + "\n")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    view_user_activity()
