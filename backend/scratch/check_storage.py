import sys
import os

# Add parent directory to path so we can import db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

def check_storage():
    if not db.init_db():
        return

    conn = db._get_connection()
    cur = conn.cursor(dictionary=True)
    
    # Query to get table sizes
    query = """
    SELECT 
        table_name, 
        table_rows,
        round(((data_length + index_length) / 1024 / 1024), 2) as size_mb 
    FROM information_schema.TABLES 
    WHERE table_schema = %s
    """
    
    database_name = os.getenv("MYSQL_DATABASE", "test")
    cur.execute(query, (database_name,))
    rows = cur.fetchall()
    
    print("\n" + "="*60)
    print(f"{'TIDB CLOUD STORAGE USAGE (' + database_name + ')':^60}")
    print("="*60)
    print(f"{'TABLE NAME':<25} | {'ROWS':<15} | {'SIZE (MB)':<15}")
    print("-" * 60)
    
    total_size = 0
    for r in rows:
        print(f"{r['table_name']:<25} | {r['table_rows']:<15} | {r['size_mb']:<15} MB")
        total_size += r['size_mb']
    
    print("-" * 60)
    print(f"{'TOTAL DATABASE SIZE':<43} | {total_size:.2f} MB")
    print("="*60 + "\n")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_storage()
