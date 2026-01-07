
import os
import json
import sys

# Try to import datasets, if fails, print instruction
try:
    from datasets import load_dataset
except ImportError:
    print("Error: 'datasets' library not found. Please run: pip install datasets")
    sys.exit(1)

def main():
    print("Loading datasets from Hugging Face...")
    try:
        # Load Verified
        print("Fetching princeton-nlp/SWE-bench_Verified...")
        ds_verified = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
        verified_ids = set(ds_verified["instance_id"])
        print(f"Loaded {len(verified_ids)} Verified instances.")

        # Load Lite
        print("Fetching princeton-nlp/SWE-bench_Lite...")
        ds_lite = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
        lite_ids = set(ds_lite["instance_id"])
        print(f"Loaded {len(lite_ids)} Lite instances.")

    except Exception as e:
        print(f"Error loading datasets: {e}")
        return

    # Intersection (Should be Lite since Lite subset Verified)
    valid_ids = verified_ids.intersection(lite_ids)
    print(f"Intersection (Verified & Lite): {len(valid_ids)} instances.")
    
    if not valid_ids:
        print("Warning: Intersection is empty! Proceeding to create empty files or abort?")
        # Just abort to be safe implies something went wrong
        return

    # Paths - using absolute path from knowledge or relative to script location
    # User's path: c:\Users\naolt\Downloads\class projects\dkang\results
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(base_dir, "agents_solution")
    output_dir = os.path.join(base_dir, "filtered_agents_solution")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # Filter
    if not os.path.exists(input_dir):
         print(f"Error: Input directory {input_dir} does not exist.")
         return

    print(f"Filtering JSONL files from {input_dir}...")
    files = [f for f in os.listdir(input_dir) if f.endswith(".jsonl")]

    for filename in files:
        in_path = os.path.join(input_dir, filename)
        out_path = os.path.join(output_dir, filename)
        
        kept_count = 0
        original_count = 0
        
        with open(in_path, 'r', encoding='utf-8') as fin, open(out_path, 'w', encoding='utf-8') as fout:
            for line in fin:
                line = line.strip()
                if not line: continue
                original_count += 1
                try:
                    record = json.loads(line)
                    inst_id = record.get("instance_id")
                    if inst_id in valid_ids:
                        fout.write(line + "\n")
                        kept_count += 1
                except json.JSONDecodeError:
                    continue
        
        print(f"  {filename}: Kept {kept_count}/{original_count} instances.")

    print(f"Done. Filtered files saved to {output_dir}")

if __name__ == "__main__":
    main()
