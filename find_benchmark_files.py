
import os
import json

RESULTS_DIR = r"c:\Users\naolt\Downloads\class projects\dkang\results\all_results"

def count_instances_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Collect all instance IDs from lists in the JSON
        instances = set()
        
        # Handle different schemas
        # Schema 1: {"resolved": [...], "no_generation": [...]} (used in some files)
        # Schema 2: {"instance_id": {...}, ...} (map logic)
        
        if isinstance(data, list):
             # Some might be list of dicts?
             pass
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    # Likely a list of instance IDs
                    for item in value:
                        if isinstance(item, str) and "__" in item: # Heuristic for instance_id
                            instances.add(item)
                elif isinstance(value, dict):
                    # Maybe {instance: {details...}}
                    if "__" in key:
                        instances.add(key)
        
        return len(instances)
    except Exception as e:
        return 0

def main():
    print(f"Scanning {RESULTS_DIR}...")
    files = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".json")]
    
    candidates = []
    
    for f in files:
        path = os.path.join(RESULTS_DIR, f)
        count = count_instances_in_file(path)
        
        # Check for interesting counts
        # Lite ~ 300
        # Verified ~ 500
        # Full ~ 2294
        
        if 290 <= count <= 310:
            candidates.append((f, count, "Likely Lite"))
        elif 490 <= count <= 510:
            candidates.append((f, count, "Likely Verified"))
        elif count > 1000:
             # Just to see if we have full runs
             pass
             
    print("\n--- POSIBLE DATASET DEFINITION FILES ---")
    for fname, count, label in candidates:
        print(f"{label}: {fname} ({count} instances)")

if __name__ == "__main__":
    main()
