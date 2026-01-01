import json
import os
import re
from collections import defaultdict

# Use the same results directory as before (adjust if user moved things)
RESULTS_DIR = r"c:\Users\naolt\Downloads\class projects\dkang\results\run_result"
# Also checking the 'results' dir the user mentioned in a diff, just in case
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
    """
    Parses the filename to extract Agent Name and TestGen LLM.
    """
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
        
        meaningful = gold_resolved - none_resolved
        if meaningful:
            meaningful_map[instance_id] = meaningful
            
    return meaningful_map

def analyze_oracle():
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
        print(f"ORACLE ANALYSIS: TestGen LLM = {llm}")
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
            print(f"  [SKIPPING] Missing Gold/None baselines for {llm}")
            continue

        gold_data = load_json(os.path.join(ACTIVE_RESULTS_DIR, gold_files[matched_gold_key]))
        none_data = load_json(os.path.join(ACTIVE_RESULTS_DIR, none_files[matched_none_key]))
        
        meaningful_map = get_meaningful_tests(gold_data, none_data)
        total_possible_meaningful = sum(len(t) for t in meaningful_map.values())
        print(f"  Total Meaningful Tests Avail: {total_possible_meaningful}")
        
        # Load all agent data for this group
        agents_data = {} # {agent_name: {instance_id: set(resolved_tests)}}
        
        print(f"  Loading {len(files_by_llm[llm])} agents...")
        for filename in files_by_llm[llm]:
            agent_name, _ = parse_filename(filename)
            fpath = os.path.join(ACTIVE_RESULTS_DIR, filename)
            data = load_json(fpath)
            if not data: continue
            
            # Pre-process resolved sets for efficiency
            # Only keep resolved tests that are 'meaningful'
            processed_agent_data = {}
            for inst, needed in meaningful_map.items():
                resolved = set(data.get(inst, {}).get("details", {}).get("resolved", []))
                # Intersection with meaningful
                meaningful_resolved = resolved & needed
                if meaningful_resolved:
                    processed_agent_data[inst] = meaningful_resolved
            
            agents_data[agent_name] = processed_agent_data

        if not agents_data:
            print("  No agent data found.")
            continue

        # --- METRIC 1: Best Single Agent ---
        best_single_agent = None
        best_single_score = -1
        
        for agent, data in agents_data.items():
            # Sum of len of resolved sets
            score = sum(len(s) for s in data.values())
            if score > best_single_score:
                best_single_score = score
                best_single_agent = agent
        
        print(f"\n  [BEST SINGLE AGENT]")
        print(f"    Agent: {best_single_agent}")
        print(f"    Score: {best_single_score} / {total_possible_meaningful}")
        print(f"    %:     {best_single_score/total_possible_meaningful*100:.2f}%")
        
        # --- METRIC 2: Oracle (Select Best Agent Per Instance) ---
        # For each instance, we want to choose the agent that solved the MOST meaningful tests
        # Oracle Score = Sum(Max(len(resolved) for agents))
        
        oracle_score = 0
        instance_best_agents = defaultdict(list)
        
        for inst in meaningful_map:
            max_resolved_for_inst = 0
            best_agents_for_inst = []
            
            for agent, data in agents_data.items():
                resolved_count = len(data.get(inst, set()))
                if resolved_count > max_resolved_for_inst:
                    max_resolved_for_inst = resolved_count
                    best_agents_for_inst = [agent]
                elif resolved_count == max_resolved_for_inst and resolved_count > 0:
                    best_agents_for_inst.append(agent)
            
            oracle_score += max_resolved_for_inst
            for ag in best_agents_for_inst:
                instance_best_agents[ag].append(inst)

        print(f"\n  [ORACLE - BEST AGENT PER INSTANCE]")
        print(f"    Oracle Score: {oracle_score} / {total_possible_meaningful}")
        print(f"    %:            {oracle_score/total_possible_meaningful*100:.2f}%")
        print(f"    Gain vs Best: +{oracle_score - best_single_score} tests")

        # --- METRIC 3: Perfect Ensemble (Union of all agents) ---
        # If we could combine partial solutions from multiple agents on the same instance
        # Ensemble Score = Sum(len(Union(resolved) for agents))
        
        ensemble_score = 0
        specialist_contributions = defaultdict(int) # tests uniquely contributed to the ensemble by an agent
        
        for inst in meaningful_map:
            union_resolved = set()
            for data in agents_data.values():
                if inst in data:
                    union_resolved.update(data[inst])
            
            ensemble_score += len(union_resolved)
            
            # Identify who contributed uniquely to this union?
            # A test T is uniquely covered by Agent A if A solved T and no one else did
            for test in union_resolved:
                solvers = []
                for agent, data in agents_data.items():
                    if inst in data and test in data[inst]:
                        solvers.append(agent)
                
                if len(solvers) == 1:
                    specialist_contributions[solvers[0]] += 1
        
        print(f"\n  [PERFECT ENSEMBLE - UNION OF ALL AGENTS]")
        print(f"    Ensemble Score: {ensemble_score}")
        print(f"    Gain vs Oracle: +{ensemble_score - oracle_score} tests (tests missed by 'best agent' but caught by another)")
        
        # --- METRIC 4: Specialist Analysis ---
        # Which agents are "Specialists"? 
        # Agents contributing to the Oracle/Ensemble on instances where the "Best Single Agent" failed or underperformed.
        
        best_agent_data = agents_data.get(best_single_agent, {})
        
        # Difficult Instances: Instances where Best Single Agent got 0, but SOMEONE got > 0
        difficult_wins = defaultdict(int) 
        
        for inst, needed in meaningful_map.items():
            best_agent_score = len(best_agent_data.get(inst, set()))
            
            # Find agents who beat the best agent here
            for agent, data in agents_data.items():
                if agent == best_single_agent: continue
                
                agent_score = len(data.get(inst, set()))
                if agent_score > best_agent_score:
                    difficult_wins[agent] += (agent_score - best_agent_score)
        
        print(f"\n  [SPECIALIST ANALYSIS]")
        print(f"    Agents that outperformed {best_single_agent} on specific instances:")
        sorted_diff = sorted(difficult_wins.items(), key=lambda x: x[1], reverse=True)
        for ag, boost in sorted_diff:
            print(f"      {ag}: +{boost} tests gained")
            
        print(f"\n    Agents with Unique Solves (Global):")
        sorted_unique = sorted(specialist_contributions.items(), key=lambda x: x[1], reverse=True)
        for ag, count in sorted_unique:
            print(f"      {ag}: {count} unique tests")

if __name__ == "__main__":
    analyze_oracle()
