import json
import os
import re
from collections import defaultdict

RESULTS_DIR = r"c:\Users\naolt\Downloads\class projects\dkang\results\run_result"

def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def parse_filename(filename):
    """
    Parses the filename to extract Agent Name and TestGen LLM.
    Handles 'gold_' and 'none_' special cases.
    """
    name_no_ext = os.path.splitext(filename)[0]
    
    if name_no_ext.startswith("gold_"):
        return "GOLD", name_no_ext.replace("gold_", "")
    if name_no_ext.startswith("none_"):
        return "NONE", name_no_ext.replace("none_", "")
    
    # Pattern: [Agent]__[LLM]
    # We need to be careful as Agent or LLM might contain underscores or other separators.
    # Based on file list: "JoyCode__gpt-5.1-500-1.json" -> Agent: JoyCode, LLM: gpt-5.1-500-1
    parts = name_no_ext.split("__")
    if len(parts) == 2:
        return parts[0], parts[1]
    
    # Fallback for complex names if standard split fails, or return as is
    return name_no_ext, "Unknown"

def get_meaningful_tests(gold_data, none_data):
    """
    Identifies 'meaningful' tests for each instance.
    Meaningful Test = (Resolved in Gold) - (Resolved in None)
    Returns a dict: { instance_id: set(meaningful_test_names) }
    """
    meaningful_map = {}
    
    all_instances = set(gold_data.keys()) | set(none_data.keys())
    
    for instance_id in all_instances:
        gold_resolved = set(gold_data.get(instance_id, {}).get("details", {}).get("resolved", []))
        none_resolved = set(none_data.get(instance_id, {}).get("details", {}).get("resolved", []))
        
        # Meaningful = Gold resolved BUT None failed (or didn't resolve)
        meaningful = gold_resolved - none_resolved
        if meaningful:
            meaningful_map[instance_id] = meaningful
            
    return meaningful_map

def get_all_instance():
    files = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".json")]
    # 1. Group files by LLM to find pairs
    files_by_llm = defaultdict(list)
    gold_files = {}
    none_files = {}
    union = set()
    
    # Pre-scan to identify Gold/None baselines
    for f in files:
        agent, llm = parse_filename(f)
        if agent == "GOLD":
            gold_files[llm] = f
        elif agent == "NONE":
            none_files[llm] = f
        else:
            files_by_llm[llm].append(f)
    # 2. Analyze per LLM group
    for llm in files_by_llm:
        # print(f"\n{'='*80}")
        # print(f"ANALYSIS GROUP: Test Generation LLM = {llm}")
        # print(f"{'='*80}")

        # Try to find matching gold/none files
        # The LLM string in 'gold_<llm>' might slightly differ from 'Agent__<llm>' 
        # e.g., gold_gpt-5.1 vs Agent__gpt-5.1-500-1. 
        # We need a robust matching strategy.
        
        # Heuristic: Check if the LLM string from the agent filename starts with the gold filename's LLM string or vice versa
        # actually looking at the file list:
        # gold_gpt-5.1.json
        # JoyCode__gpt-5.1-500-1.json
        # It seems 'gpt-5.1' is a substring of 'gpt-5.1-500-1'.
        
        matched_gold_key = None
        for k in gold_files:
            if k in llm or llm in k:
                matched_gold_key = k
                break
        
        matched_none_key = None
        for k in none_files:
            if k in llm or llm in k:
                matched_none_key = k
                break
        
        if not matched_gold_key or not matched_none_key:
            print(f"  [WARNING] Baseline files (Gold/None) missing for LLM '{llm}'. Skipping meaningful diffs.")
            print(f"  Expected matching keys for Gold: {list(gold_files.keys())}, None: {list(none_files.keys())}")
            continue

        # print(f"  Using Baseline: Gold='{gold_files[matched_gold_key]}' | None='{none_files[matched_none_key]}'")
        
        gold_data = load_json(os.path.join(RESULTS_DIR, gold_files[matched_gold_key]))
        none_data = load_json(os.path.join(RESULTS_DIR, none_files[matched_none_key]))
        
        meaningful_tests_map = get_meaningful_tests(gold_data, none_data)
        
        total_meaningful_instances = len(meaningful_tests_map)
        total_meaningful_tests_count = sum(len(tests) for tests in meaningful_tests_map.values())
        for instances in meaningful_tests_map.keys():
            union.add(instances)
        
        # print(f"  Total Instances with Meaningful Tests: {total_meaningful_instances}")
        # print(f"  Total Meaningful Tests (Gold Resolved - None Resolved): {total_meaningful_tests_count}")
        # print("-" * 80)
    print(len(union))


def analyze_results():
    files = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".json")]
    
    # 1. Group files by LLM to find pairs
    files_by_llm = defaultdict(list)
    gold_files = {}
    none_files = {}
    
    # Pre-scan to identify Gold/None baselines
    for f in files:
        agent, llm = parse_filename(f)
        if agent == "GOLD":
            gold_files[llm] = f
        elif agent == "NONE":
            none_files[llm] = f
        else:
            files_by_llm[llm].append(f)

    # 2. Analyze per LLM group
    for llm in files_by_llm:
        print(f"\n{'='*80}")
        print(f"ANALYSIS GROUP: Test Generation LLM = {llm}")
        print(f"{'='*80}")

        # Try to find matching gold/none files
        # The LLM string in 'gold_<llm>' might slightly differ from 'Agent__<llm>' 
        # e.g., gold_gpt-5.1 vs Agent__gpt-5.1-500-1. 
        # We need a robust matching strategy.
        
        # Heuristic: Check if the LLM string from the agent filename starts with the gold filename's LLM string or vice versa
        # actually looking at the file list:
        # gold_gpt-5.1.json
        # JoyCode__gpt-5.1-500-1.json
        # It seems 'gpt-5.1' is a substring of 'gpt-5.1-500-1'.
        
        matched_gold_key = None
        for k in gold_files:
            if k in llm or llm in k:
                matched_gold_key = k
                break
        
        matched_none_key = None
        for k in none_files:
            if k in llm or llm in k:
                matched_none_key = k
                break
        
        if not matched_gold_key or not matched_none_key:
            print(f"  [WARNING] Baseline files (Gold/None) missing for LLM '{llm}'. Skipping meaningful diffs.")
            print(f"  Expected matching keys for Gold: {list(gold_files.keys())}, None: {list(none_files.keys())}")
            continue

        print(f"  Using Baseline: Gold='{gold_files[matched_gold_key]}' | None='{none_files[matched_none_key]}'")
        
        gold_data = load_json(os.path.join(RESULTS_DIR, gold_files[matched_gold_key]))
        none_data = load_json(os.path.join(RESULTS_DIR, none_files[matched_none_key]))
        
        meaningful_tests_map = get_meaningful_tests(gold_data, none_data)
        
        total_meaningful_instances = len(meaningful_tests_map)
        total_meaningful_tests_count = sum(len(tests) for tests in meaningful_tests_map.values())
        
        print(f"  Total Instances with Meaningful Tests: {total_meaningful_instances}")
        print(f"  Total Meaningful Tests (Gold Resolved - None Resolved): {total_meaningful_tests_count}")
        print("-" * 80)
        
        # Store agent stats
        agent_stats = []
        
        # Track unique solves: {instance_id: {test_name: [list of agents who solved it]}}
        unique_solver_tracker = defaultdict(lambda: defaultdict(list))

        for filename in files_by_llm[llm]:
            agent_name, _ = parse_filename(filename)
            filepath = os.path.join(RESULTS_DIR, filename)
            data = load_json(filepath)
            
            if not data:
                continue

            resolved_meaningful_count = 0
            resolved_meaningful_instances_count = 0
            
            for instance_id, needed_tests in meaningful_tests_map.items():
                agent_resolved = set(data.get(instance_id, {}).get("details", {}).get("resolved", []))
                
                # Check which meaningful tests this agent resolved
                solved_here = needed_tests.intersection(agent_resolved)
                resolved_meaningful_count += len(solved_here)
                
                if len(solved_here) > 0:
                    resolved_meaningful_instances_count += 1
                
                # Track for unique solver analysis
                for t in solved_here:
                    unique_solver_tracker[instance_id][t].append(agent_name)

            # Metadata stats
            total_resolved_raw = 0
            for k, v in data.items():
                total_resolved_raw += v.get("n_resolved_tests", 0)

            stats = {
                "Agent": agent_name,
                "Total Resolved (Raw)": total_resolved_raw,
                "Meaningful Resolved": resolved_meaningful_count,
                "Meaningful Instances": resolved_meaningful_instances_count,
                "Percentage Meaningful": (resolved_meaningful_count / total_meaningful_tests_count * 100) if total_meaningful_tests_count > 0 else 0.0
            }
            agent_stats.append(stats)

        # Sort by Meaningful Resolved Descending
        agent_stats.sort(key=lambda x: x["Meaningful Resolved"], reverse=True)

        # Print Table
        headers = ["Agent", "Mean. Tests", "% Tests", "Mean. Inst.", "Total Raw"]
        row_format = "{:<40} | {:<12} | {:<10} | {:<12} | {:<10}"
        
        print(row_format.format(*headers))
        print("-" * 105)
        for stat in agent_stats:
            print(row_format.format(
                stat["Agent"], 
                stat["Meaningful Resolved"], 
                f"{stat['Percentage Meaningful']:.2f}%",
                f"{stat['Meaningful Instances']}/{total_meaningful_instances}",
                stat["Total Resolved (Raw)"]
            ))

        # --- UNIQUE SOLVES ANALYSIS ---
        print("\n  [UNIQUE SOLVES ANALYSIS]")
        print("  Meaningful tests solved by ONLY ONE agent in this group:")
        
        unique_counts = defaultdict(int) 
        
        found_any_unique = False
        for instance_id, tests_map in unique_solver_tracker.items():
            for test_name, solvers in tests_map.items():
                if len(solvers) == 1:
                    found_any_unique = True
                    solo_agent = solvers[0]
                    unique_counts[solo_agent] += 1
                    # Optional: Print detailed unique solves (can be verbose)
                    # print(f"    {solo_agent} resolved {instance_id}::{test_name}")

        if not found_any_unique:
            print("    None found.")
        else:
            sorted_uniques = sorted(unique_counts.items(), key=lambda x: x[1], reverse=True)
            for agent, count in sorted_uniques:
                print(f"    {agent}: {count} unique solves")

if __name__ == "__main__":
    get_all_instance()
