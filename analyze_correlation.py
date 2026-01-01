import json
import os
import re
from collections import defaultdict

# Configurations
GENERATED_RESULTS_DIR = r"c:\Users\naolt\Downloads\class projects\dkang\results\run_result"
GENERATED_RESULTS_DIR_ALT = r"c:\Users\naolt\Downloads\class projects\dkang\results\results"
REAL_RESULTS_DIR = r"c:\Users\naolt\Downloads\class projects\dkang\results\filtered_results"

def get_generated_dir():
    if os.path.exists(GENERATED_RESULTS_DIR):
        return GENERATED_RESULTS_DIR
    if os.path.exists(GENERATED_RESULTS_DIR_ALT):
        return GENERATED_RESULTS_DIR_ALT
    return "."

ACTIVE_GEN_DIR = get_generated_dir()

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

def load_real_results(agent_name):
    """
    Load the real SWE-bench verified results for a given agent.
    File format: filtered_results/results_[agent].json
    """
    # Try exact match first
    fname = f"results_{agent_name}.json"
    fpath = os.path.join(REAL_RESULTS_DIR, fname)
    if os.path.exists(fpath):
        data = load_json(fpath)
        return set(data.get("resolved", [])) if data else set()
    
    # Fuzzy match if needed (e.g. Lingxi names might differ slightly)
    # The user filenames in filtered_results seem to match the "Agent" part of our split.
    # Check listing
    try:
        candidates = os.listdir(REAL_RESULTS_DIR)
        for c in candidates:
            if agent_name in c:
                 data = load_json(os.path.join(REAL_RESULTS_DIR, c))
                 return set(data.get("resolved", [])) if data else set()
    except Exception:
        pass
        
    return None

def analyze_correlation():
    print(f"Generated Results: {ACTIVE_GEN_DIR}")
    print(f"Real Results:      {REAL_RESULTS_DIR}")
    
    gen_files = [f for f in os.listdir(ACTIVE_GEN_DIR) if f.endswith(".json")]
    
    # 1. Group by LLM
    files_by_llm = defaultdict(list)
    gold_files = {}
    none_files = {}
    
    for f in gen_files:
        agent, llm = parse_filename(f)
        if agent == "GOLD":
            gold_files[llm] = f
        elif agent == "NONE":
            none_files[llm] = f
        else:
            files_by_llm[llm].append(f)

    for llm in files_by_llm:
        print(f"\n{'='*80}")
        print(f"CORRELATION ANALYSIS: TestGen LLM = {llm}")
        print(f"{'='*80}")
        
        # Match baseline
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
            print("  [SKIPPING] Missing baseline.")
            continue
            
        gold_data = load_json(os.path.join(ACTIVE_GEN_DIR, gold_files[matched_gold_key]))
        none_data = load_json(os.path.join(ACTIVE_GEN_DIR, none_files[matched_none_key]))
        meaningful_map = get_meaningful_tests(gold_data, none_data)
        
        print(f"  Validating against Real Results for {len(files_by_llm[llm])} agents...")
        
        # Aggregate stats
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_tn = 0
        
        # Per-agent stats
        agent_stats = []
        
        for filename in files_by_llm[llm]:
            agent_name, _ = parse_filename(filename)
            
            # Load Generated Results
            gen_data = load_json(os.path.join(ACTIVE_GEN_DIR, filename))
            if not gen_data: continue
            
            # Load Real Results
            real_resolved_set = load_real_results(agent_name)
            if real_resolved_set is None:
                # print(f"  [WARN] No real results found for agent '{agent_name}'. Skipping.")
                continue
                
            # Compare for each Instance in Meaningful Map
            # We ONLY care about instances where we HAVE generated meaningful tests.
            # If we don't have tests for an instance, we can't predict anything.
            
            tp = 0 # Predicted Pass (Gen) & Actual Pass (Real)
            fp = 0 # Predicted Pass (Gen) & Actual Fail (Real) -> "False Hope"
            fn = 0 # Predicted Fail (Gen) & Actual Pass (Real) -> "Tests too strict"
            tn = 0 # Predicted Fail (Gen) & Actual Fail (Real)
            
            for inst, needed_tests in meaningful_map.items():
                # Did Agent Pass Generated Tests?
                # Definition of "Pass Generated": Solved ALL meaningful tests? Or AT LEAST ONE?
                # Usually "Pass" means solving the issue. If tests are unit tests, maybe "All" is better.
                # However, earlier we saw agents solving 196/197 instances.
                # Let's say: If agent solves AT LEAST ONE meaningful test => We predict "PASS".
                # (You can swap this to "ALL" if the tests are atomic requirements)
                
                agent_resolved_tests = set(gen_data.get(inst, {}).get("details", {}).get("resolved", []))
                meaningful_hits = agent_resolved_tests & needed_tests
                
                predicted_pass = len(meaningful_hits) > 0 # Loose criteria
                # predicted_pass = len(meaningful_hits) == len(needed_tests) # Strict criteria
                
                actual_pass = inst in real_resolved_set
                
                if predicted_pass and actual_pass:
                    tp += 1
                elif predicted_pass and not actual_pass:
                    fp += 1
                elif not predicted_pass and actual_pass:
                    fn += 1
                elif not predicted_pass and not actual_pass:
                    tn += 1
            
            # Calculate agent metrics
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            agent_stats.append({
                "Agent": agent_name,
                "Prec": precision,
                "Recall": recall,
                "F1": f1,
                "TP": tp, "FP": fp, "FN": fn
            })
            
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_tn += tn

        # Sort by F1
        agent_stats.sort(key=lambda x: x["F1"], reverse=True)
        
        print("\n  [CORRELATION METRICS]")
        print("  Can Generated Tests predict Real Success?")
        print(f"  {'Agent':<40} | {'Prec':<6} | {'Recall':<6} | {'F1':<6} | {'FP (False Hope)':<15} | {'FN (Missed)':<10}")
        print("  " + "-"*100)
        
        for s in agent_stats:
            print(f"  {s['Agent']:<40} | {s['Prec']:.2f}   | {s['Recall']:.2f}   | {s['F1']:.2f}   | {s['FP']:<15} | {s['FN']:<10}")
            
        # Aggregate
        agg_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        agg_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        print("-" * 100)
        print(f"  AGGREGATE for {llm}: Precision={agg_prec:.2f}, Recall={agg_rec:.2f}")
        
        if agg_prec < 0.5:
            print("  [INSIGHT] Low Precision: Generated tests are too easy or pass when the real issue isn't fixed.")
        if agg_rec < 0.5:
            print("  [INSIGHT] Low Recall: Generated tests are too hard/strict OR we didn't generate tests for enough instances.")

if __name__ == "__main__":
    analyze_correlation()
