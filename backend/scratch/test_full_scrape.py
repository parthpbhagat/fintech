import sys
import os

# Add the current directory to sys.path so we can import local modules
sys.path.append(os.getcwd())

import db as db_module
from pipeline import cache

def test_scrape():
    print("Initializing DB...")
    db_module.init_db()
    
    print("Starting Professional Scrape...")
    profs = cache.scrape_insolvency_professionals()
    print(f"Scraped {len(profs)} professionals.")
    
    if profs:
        print("Scrape successful and saved to TiDB!")

if __name__ == "__main__":
    test_scrape()
