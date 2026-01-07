import argparse
import os
import json
from collections import defaultdict

DEFAULT_RESULTS_DIR = r"c:\Users\naolt\Downloads\class projects\dkang\results\run_result"

# -------------------------------------------------------------------
# IO HELPERS
# -------------------------------------------------------------------

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return {}

def parse_filename(filename):
    name = os.path.splitext(filename)[0]

    if name.startswith("gold_"):
        return "GOLD", name.replace("gold_", "")
    if name.startswith("none_"):
        return "NONE", name.replace("none_", "")

    parts = name.split("__")
    return (parts[0], parts[1]) if len(parts) == 2 else (name, "Unknown")

# -------------------------------------------------------------------
# MAIN PROCESS
# -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze results from a directory.")
    parser.add_argument("--data_dir", default=DEFAULT_RESULTS_DIR, help="Directory containing result JSON files.")
    args = parser.parse_args()

    if not os.path.isdir(args.data_dir):
        print(f"Error: Directory not found: {args.data_dir}")
        return

    files = [f for f in os.listdir(args.data_dir) if f.endswith(".json")]
    files_by_llm = defaultdict(list)
    gold_files = {}
    none_files = {}

    for f in files:
        agent, llm = parse_filename(f)
        if agent == "GOLD":
            gold_files[llm] = f
        elif agent == "NONE":
            none_files[llm] = f
        else:
            files_by_llm[llm].append(f)

    for llm in sorted(files_by_llm.keys()):
        print("=" * 110)
        print(f"ANALYSIS GROUP: Test Generation LLM = {llm}")
        print("=" * 110)
        print()

        # Find corresponding GOLD and NONE files
        gk = next((k for k in gold_files if k in llm or llm in k), None)
        nk = next((k for k in none_files if k in llm or llm in k), None)

        if not gk or not nk:
            print(f"  [WARNING] Missing GOLD or NONE file for {llm}. Skipping...")
            continue

        gold_data = load_json(os.path.join(args.data_dir, gold_files[gk]))
        none_data = load_json(os.path.join(args.data_dir, none_files[nk]))

        # Define Meaningful Tests: Resolved by GOLD but NOT by NONE
        meaningful_map = {} # inst -> set of test names
        all_instances = set(gold_data.keys()) | set(none_data.keys())
        
        for inst in all_instances:
            g_res = set(gold_data.get(inst, {}).get("details", {}).get("resolved", []))
            n_res = set(none_data.get(inst, {}).get("details", {}).get("resolved", []))
            diff = g_res - n_res
            if diff:
                meaningful_map[inst] = diff
        
        total_meaningful_tests = sum(len(x) for x in meaningful_map.values())

        # Header
        # Agent | Meaningful (Sol/Tot) | Mean % | Total (Sol/Tot) | Total %
        header = (
            f"{'Agent':<35} | "
            f"{'Meaningful':<15} | "
            f"{'% Mean':<8} | "
            f"{'Total':<15} | "
            f"{'% Total':<8}"
        )
        print(header)
        print("-" * len(header))

        for fname in sorted(files_by_llm[llm]):
            agent, _ = parse_filename(fname)
            agent_path = os.path.join(args.data_dir, fname)
            agent_data = load_json(agent_path)
            
            # Meaningful Stats
            meaningful_solved = 0
            for inst, tests in meaningful_map.items():
                agent_res = set(agent_data.get(inst, {}).get("details", {}).get("resolved", []))
                meaningful_solved += len(agent_res & tests)
            
            mean_pct = (meaningful_solved / total_meaningful_tests * 100) if total_meaningful_tests else 0.0

            # Total Stats (Agent Available vs Solved)
            total_solved = 0
            total_avail = 0
            
            for inst, data in agent_data.items():
                d = data.get("details", {})
                res = set(d.get("resolved", []))
                fail = set(d.get("unresolved", []))
                total_solved += len(res)
                total_avail += len(res) + len(fail)

            tot_pct = (total_solved / total_avail * 100) if total_avail else 0.0

            print(
                f"{agent:<35} | "
                f"{f'{meaningful_solved}/{total_meaningful_tests}':<15} | "
                f"{mean_pct:6.1f} % | "
                f"{f'{total_solved}/{total_avail}':<15} | "
                f"{tot_pct:6.1f} %"
            )
        print()

if __name__ == "__main__":
    main()
