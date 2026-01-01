import os
import json
import glob

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_json(data, path):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Saved: {path}")

def main():
    results_dir = "run_result"
    output_dir = os.path.join(results_dir, "meaningful_tests")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. Find all gold files
    gold_files = glob.glob(os.path.join(results_dir, "gold_*.json"))
    
    union_data = {} # Structure: { instance_id: { identifier: [tests] } }

    for gold_path in gold_files:
        filename = os.path.basename(gold_path)
        # Extract identifier: gold_gpt-5.1.json -> gpt-5.1
        identifier = filename[5:-5] 
        
        none_path = os.path.join(results_dir, f"none_{identifier}.json")
        
        if not os.path.exists(none_path):
            print(f"Warning: Corresponding none file not found for {filename}: {none_path}")
            continue
            
        print(f"Processing identifier: {identifier}")
        
        gold_data = load_json(gold_path)
        none_data = load_json(none_path)
        
        meaningful_data_for_id = {}
        
        # Iterate through all instances in gold (assuming same instances in none)
        all_instances = set(gold_data.keys()) | set(none_data.keys())
        
        for instance_id in all_instances:
            gold_res = set(gold_data.get(instance_id, {}).get("details", {}).get("resolved", []))
            none_res = set(none_data.get(instance_id, {}).get("details", {}).get("resolved", []))
            
            # Meaningful = Resolved in Gold AND NOT Resolved in None
            meaningful_tests = list(gold_res - none_res)
            meaningful_tests.sort()
            
            if meaningful_tests:
                meaningful_data_for_id[instance_id] = meaningful_tests
                
                # Add to union
                if instance_id not in union_data:
                    union_data[instance_id] = {}
                union_data[instance_id][identifier] = meaningful_tests

        # Save individual file
        output_path = os.path.join(output_dir, f"meaningful_{identifier}.json")
        save_json(meaningful_data_for_id, output_path)

    # 2. Save Union File
    union_path = os.path.join(output_dir, "meaningful_union.json")
    save_json(union_data, union_path)
    
    print("Done.")

if __name__ == "__main__":
    main()
