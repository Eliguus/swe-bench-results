import os
import json
import glob

def count_instances():
    # Adjust path based on user's active document location
    # User showed: .../results/run_result/meaningful_tests/meaningful_union.json
    # We are in: .../results/
    
    target_dir = os.path.join("run_result", "meaningful_tests")
    if not os.path.exists(target_dir):
        # Fallback to the one we probably created in the previous step if user hasn't moved it
        target_dir = os.path.join("results", "meaningful_tests")
    
    if not os.path.exists(target_dir):
        print(f"Directory not found: {target_dir}")
        return

    print(f"Counting instances in: {target_dir}")
    print("-" * 40)
    
    files = glob.glob(os.path.join(target_dir, "*.json"))
    files.sort()
    
    for file_path in files:
        filename = os.path.basename(file_path)
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                count = len(data)
                print(f"{filename:<40} : {count} instances")
        except Exception as e:
            print(f"{filename:<40} : Error ({e})")

if __name__ == "__main__":
    count_instances()
