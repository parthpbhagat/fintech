import sys
import os
import json

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from pipeline import generate_directors_for_company
    
    # Test case 1: TCS (Curated)
    tcs = {"name": "TATA CONSULTANCY SERVICES LIMITED", "cin": "L72200MH1995PLC095605"}
    tcs_directors = generate_directors_for_company(tcs)
    print(f"TCS Directors Count: {len(tcs_directors)}")
    for d in tcs_directors:
        print(f"  - {d['name']} ({d['din']})")
        
    # Test case 2: Random company (Simulated)
    random_co = {"name": "MY TEST COMPANY", "cin": "U12345MH2023PTC123456"}
    random_directors = generate_directors_for_company(random_co)
    print(f"\nRandom Co Directors Count: {len(random_directors)}")
    for d in random_directors:
        print(f"  - {d['name']} ({d['din']})")

except Exception as e:
    print(f"Error: {e}")
