import os
import json
import random
from collections import defaultdict
import argparse

# Paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
RUN_RESULT_DIR = os.path.join(ROOT_DIR, 'run_result')
AGENTS_SOLUTION_DIR = os.path.join(ROOT_DIR, 'agents_solution')
LITE_SCORES_PATH = os.path.join(BASE_DIR, 'seg_method', 'lite.json')
OUTPUT_DIR = os.path.join(ROOT_DIR, 'algorithm_chosen_agent_solutions')
METADATA_DIR = os.path.join(OUTPUT_DIR, 'metadata')
CHOSEN_DIR = os.path.join(OUTPUT_DIR, 'chosen')

# Seed for reproducible random tie-breaking
RANDOM_SEED = 42

# Configurable model name for the output
OUTPUT_MODEL_NAME = "Agent_Selection_v1"

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: File not found: {path}")
        return {}
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return {}

def load_jsonl_to_dict(path):
    """Loads a JSONL file into a dict mapping instance_id to the full record."""
    data = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    record = json.loads(line)
                    if 'instance_id' in record:
                        data[record['instance_id']] = record
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        # Some agents might not have a solution file if they are baselines or errored
        print(f"Warning: Solution file not found: {path}")
    return data

def parse_run_result_filename(filename):
    """
    Parses filenames like 'JoyCode__gpt-5.1-500-1.json'
    Returns (agent_name, llm_name) or None if format doesn't match.
    """
    if filename.startswith('gold_') or filename.startswith('none_'):
        return None, None
    
    name_part = os.path.splitext(filename)[0]
    parts = name_part.split('__')
    if len(parts) != 2:
        return None, None
    
    agent_name = parts[0]
    remainder = parts[1]
    
    # Expecting remainder like 'gpt-5.1-500-1'
    # We want to extract 'gpt-5.1', 'gpt-5.2', 'gpt-o3'
    # Splitting by '-' might be tricky if LLM name has hyphens, 
    # but based on file list: 'gpt-5.1-500-1', 'gpt-o3-500-1'
    # It seems safe to take everything before the last two parts '-500-1'
    
    remainder_parts = remainder.split('-')
    if len(remainder_parts) >= 3 and remainder_parts[-2] == '500' and remainder_parts[-1] == '1':
        llm_name = '-'.join(remainder_parts[:-2])
        return agent_name, llm_name
    
    return None, None

def main():
    print("Starting Agent Selection Algorithm...")
    
    # 1. Setup Directories
    os.makedirs(METADATA_DIR, exist_ok=True)
    os.makedirs(CHOSEN_DIR, exist_ok=True)
    
    # 2. Load Tie-Breaking Scores
    print(f"Loading tie-breaking scores from {LITE_SCORES_PATH}...")
    lite_scores = load_json(LITE_SCORES_PATH)
    
    # 3. Scan Run Results and Group by LLM
    print(f"Scanning {RUN_RESULT_DIR}...")
    files_by_llm = defaultdict(list)
    
    for filename in os.listdir(RUN_RESULT_DIR):
        if not filename.endswith('.json'): continue
        
        agent_name, llm_name = parse_run_result_filename(filename)
        if agent_name and llm_name:
            files_by_llm[llm_name].append({
                'agent_name': agent_name,
                'filename': filename,
                'path': os.path.join(RUN_RESULT_DIR, filename)
            })

    # Cache for agent solution modifications to avoid re-reading files unnecessarily across LLMs
    # (Though currently we process per LLM, agent files are same across LLMs? 
    # Actually agents_solution filenames are just agent names, e.g. JoyCode.jsonl)
    # We will load instances on demand or pre-load per agent. 
    # Given file sizes are small (~1-2MB), we can cache them.
    agent_solutions_cache = {}

    def get_agent_solution(agent_name, instance_id):
        if agent_name not in agent_solutions_cache:
            sol_path = os.path.join(AGENTS_SOLUTION_DIR, f"{agent_name}.jsonl")
            agent_solutions_cache[agent_name] = load_jsonl_to_dict(sol_path)
            
        return agent_solutions_cache[agent_name].get(instance_id)

    # 4. Process Each LLM Group
    for llm_name, agents_info in files_by_llm.items():
        print(f"\nProcessing LLM: {llm_name}")
        
        # Load all agent result data for this LLM
        agent_results = {} # agent_name -> {instance_id -> n_resolved}
        all_instances = set()
        
        for info in agents_info:
            agent_name = info['agent_name']
            data = load_json(info['path'])
            
            # Allow mapping instance results to simpler lookup
            results_map = {}
            for inst_id, res in data.items():
                results_map[inst_id] = res.get('n_resolved_tests', 0)
                all_instances.add(inst_id)
            
            agent_results[agent_name] = results_map
            
        print(f"  Found {len(agent_results)} agents and {len(all_instances)} unique instances.")
        
        metadata_output = []
        chosen_output = []
        
        # Initialize random seed for this LLM to ensures deterministic behavior per LLM
        rng = random.Random(RANDOM_SEED)
        
        for instance_id in sorted(list(all_instances)):
            # Gather scores for this instance
            candidates = []
            max_resolved = -1
            
            for agent_name, results in agent_results.items():
                resolved_count = results.get(instance_id, 0) # Default to 0 if instance missing for agent
                if resolved_count > max_resolved:
                    max_resolved = resolved_count
                    candidates = [agent_name]
                elif resolved_count == max_resolved:
                    candidates.append(agent_name)
            
            # Tie-breaking logic
            tie_status = "no_tie"
            chosen_agent = candidates[0]
            tie_break_score = None
            
            if len(candidates) > 1:
                # Secondary Criteria: lite.json score
                tie_status = "score_break"
                best_score = -1
                score_candidates = []
                
                for cand in candidates:
                    score = lite_scores.get(cand, 0)
                    if score > best_score:
                        best_score = score
                        score_candidates = [cand]
                    elif score == best_score:
                        score_candidates.append(cand)
                
                tie_break_score = best_score
                
                if len(score_candidates) == 1:
                    chosen_agent = score_candidates[0]
                else:
                    # Tertiary Criteria: Random
                    tie_status = "random_break"
                    chosen_agent = rng.choice(score_candidates)
            
            # Prepare Metadata Entry
            meta_entry = {
                "instance_id": instance_id,
                "chosen_agent": chosen_agent,
                "n_resolved_tests": max_resolved,
                "tie_status": tie_status,
                "tie_break_score": tie_break_score, # Only relevant if tie occurred
                "candidate_agents": candidates, # Who was tied at top resolved count
                "total_agents_evaluated": len(agent_results)
            }
            metadata_output.append(meta_entry)
            
            # Prepare Chosen Solution Entry
            solution_record = get_agent_solution(chosen_agent, instance_id)
            if solution_record:
                # Create a copy to avoid modifying cache
                final_record = solution_record.copy()
                final_record['model_name_or_path'] = OUTPUT_MODEL_NAME

                chosen_output.append(final_record)
            else:
                # If solution not found (shouldn't happen for valid agents), create placeholder or warn
                # For now we will skip/warn, but strict requirements imply we need a solution
                print(f"    [WARNING] Solution payload missing for {chosen_agent} on {instance_id}")

        # Write Outputs for this LLM
        meta_path = os.path.join(METADATA_DIR, f"{llm_name}.jsonl")
        print(f"  Writing metadata to {meta_path}...")
        with open(meta_path, 'w', encoding='utf-8') as f:
            for entry in metadata_output:
                f.write(json.dumps(entry) + '\n')
                
        chosen_path = os.path.join(CHOSEN_DIR, f"{llm_name}.jsonl")
        print(f"  Writing chosen solutions to {chosen_path}...")
        with open(chosen_path, 'w', encoding='utf-8') as f:
            for entry in chosen_output:
                f.write(json.dumps(entry) + '\n')
                
    print("\nProcessing Complete.")

if __name__ == "__main__":
    main()
