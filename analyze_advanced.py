import json
import os
import re
from collections import defaultdict
import itertools

# Configuration
RESULTS_DIR = r"c:\Users\naolt\Downloads\class projects\dkang\results\run_result"
RESULTS_DIR_ALT = r"c:\Users\naolt\Downloads\class projects\dkang\results\results"

def get_results_dir():
    if os.path.exists(RESULTS_DIR):
        return RESULTS_DIR
    if os.path.exists(RESULTS_DIR_ALT):
        return RESULTS_DIR_ALT
    return "."

ACTIVE_RESULTS_DIR = get_results_dir()

def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def parse_filename(filename):
    name_no_ext = os.path.splitext(filename)[0]
    if name_no_ext.startswith("gold_"):
        return "GOLD", name_no_ext.replace("gold_", "")
    if name_no_ext.startswith("none_"):
        return "NONE", name_no_ext.replace("none_", "")
    parts = name_no_ext.split("__")
    if len(parts) == 2:
        return parts[0], parts[1]
    return name_no_ext, "Unknown"

def get_meaningful_tests(gold_data, none_data):
    meaningful_map = {}
    all_instances = set(gold_data.keys()) | set(none_data.keys())
    for instance_id in all_instances:
        gold_resolved = set(gold_data.get(instance_id, {}).get("details", {}).get("resolved", []))
        none_resolved = set(none_data.get(instance_id, {}).get("details", {}).get("resolved", []))
        meaningful = gold_resolved - none_resolved
        if meaningful:
            meaningful_map[instance_id] = meaningful
    return meaningful_map

def analyze_advanced():
    print(f"Reading from: {ACTIVE_RESULTS_DIR}")
    files = [f for f in os.listdir(ACTIVE_RESULTS_DIR) if f.endswith(".json")]
    
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

    for llm in files_by_llm:
        print(f"\n{'='*80}")
        print(f"ADVANCED ANALYSIS: TestGen LLM = {llm}")
        print(f"{'='*80}")
        
        # Match baseline files
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
            print(f"  [SKIPPING] Missing Gold/None baselines")
            continue

        gold_data = load_json(os.path.join(ACTIVE_RESULTS_DIR, gold_files[matched_gold_key]))
        none_data = load_json(os.path.join(ACTIVE_RESULTS_DIR, none_files[matched_none_key]))
        
        # 1. Prepare Data
        meaningful_map = get_meaningful_tests(gold_data, none_data)
        
        agent_meaningful_solved = {} # {agent: set((inst, test))}
        agent_regression_count = {}  # {agent: count}
        
        # For Regression: We need to know what passed in NONE
        # Regression = Passed in NONE but FAILED in Agent
        none_passed_map = {} # {inst: set(tests)}
        for inst, details in none_data.items():
            none_passed_map[inst] = set(details.get("details", {}).get("resolved", []))
            
        print(f"  Loading {len(files_by_llm[llm])} agents...")
        
        for filename in files_by_llm[llm]:
            agent_name, _ = parse_filename(filename)
            fpath = os.path.join(ACTIVE_RESULTS_DIR, filename)
            data = load_json(fpath)
            if not data: continue
            
            # --- METRIC 1: REGRESSION ANALYSIS ---
            regressions = 0
            solved_meaningful = set()
            
            for inst, info in data.items():
                resolved = set(info.get("details", {}).get("resolved", []))
                
                # Check Regression (Was passed in NONE, but NOT in resolved)
                if inst in none_passed_map:
                    base_passed = none_passed_map[inst]
                    # Regression = Base passed - Agent passed
                    # Note: Only count if the test actually exists in this agent's run (missing tests vs failed tests)
                    # For simplicity, we assume broken = failed or missing
                    broken = base_passed - resolved
                    regressions += len(broken)
                
                # Check Meaningful
                if inst in meaningful_map:
                    hits = resolved & meaningful_map[inst]
                    for t in hits:
                        solved_meaningful.add((inst, t))
            
            agent_regression_count[agent_name] = regressions
            agent_meaningful_solved[agent_name] = solved_meaningful

        if not agent_meaningful_solved:
            print("  No agent data.")
            continue

        # --- REPORT 1: REGRESSION (SAFETY) ---
        print("\n  [METRIC 1: REGRESSION ANALYSIS (Lower is Safer)]")
        print("  Tests passed by baseline (None) but broken by agent:")
        sorted_reg = sorted(agent_regression_count.items(), key=lambda x: x[1])
        for ag, count in sorted_reg:
            print(f"    {ag:<40}: -{count} regressions")

        # --- REPORT 2: PAIRWISE COMPLEMENTARITY ---
        print("\n  [METRIC 2: BEST PAIRS (Partnership Score)]")
        # Find combination of 2 agents with highest Union of meaningful solved
        best_pair = None
        best_pair_score = -1
        
        param_list = list(agent_meaningful_solved.keys())
        
        # Calculate single max for comparison
        best_single_score = max(len(s) for s in agent_meaningful_solved.values())
        
        for a1, a2 in itertools.combinations(param_list, 2):
            union_set = agent_meaningful_solved[a1] | agent_meaningful_solved[a2]
            score = len(union_set)
            if score > best_pair_score:
                best_pair_score = score
                best_pair = (a1, a2)
        
        if best_pair:
            print(f"    Best Team: {best_pair[0]} + {best_pair[1]}")
            print(f"    Combined Score: {best_pair_score} (Gain: +{best_pair_score - best_single_score})")
        
        # --- METRIC 3: DIFFICULTY CLUSTERING ---
        print("\n  [METRIC 3: DIFFICULTY CLUSTERING]")
        # 1. Count global solve rate for each meaningful test
        test_solve_counts = defaultdict(int) # {(inst, test): count}
        possible_agents = len(agent_meaningful_solved)
        
        for solved_set in agent_meaningful_solved.values():
            for it in solved_set:
                test_solve_counts[it] += 1
                
        # 2. Classify Tests
        hard_tests = set()
        unique_tests = set()
        
        for it, count in test_solve_counts.items():
            if count == 1:
                unique_tests.add(it)
            # Define "Hard": Solved by < 20% of agents (or just <= 2 if small group?)
            # Let's use < 20%
            if (count / possible_agents) < 0.2:
                hard_tests.add(it)
                
        print(f"    Total Meaningful Tests Solved at least once: {len(test_solve_counts)}")
        print(f"    Hard Tests (<20% solve rate): {len(hard_tests)}")
        print(f"    Unique Tests (1 agent only):  {len(unique_tests)}")
        
        # 3. Profile Agents
        print("\n    Agent Hard Problem Performance:")
        agent_hard_scores = []
        for ag, solved_set in agent_meaningful_solved.items():
            hard_solved = len(solved_set & hard_tests)
            unique_solved = len(solved_set & unique_tests)
            agent_hard_scores.append((ag, hard_solved, unique_solved))
            
        # Sort by Hard Solved desc
        agent_hard_scores.sort(key=lambda x: x[1], reverse=True)
        
        print(f"    {'Agent':<40} | {'Hard':<6} | {'Unique':<6}")
        print("    " + "-"*60)
        for ag, h, u in agent_hard_scores:
            print(f"    {ag:<40} | {h:<6} | {u:<6}")

if __name__ == "__main__":
    analyze_advanced()
