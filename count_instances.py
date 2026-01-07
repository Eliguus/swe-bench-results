import os
import json
import glob
from collections import defaultdict

def count_instances():
    # Define the directory containing the result files
    target_dir = os.path.join("results", "run_result")
    
    if not os.path.exists(target_dir):
        # Fallback if running from a different root
        target_dir = "run_result"
    
    if not os.path.exists(target_dir):
        print(f"Directory not found: {target_dir}")
        return

    print(f"Analyzing results in: {target_dir}")
    print("=" * 60)

    files = glob.glob(os.path.join(target_dir, "*.json"))
    files.sort()

    # Data structures
    # results_by_llm[llm][agent] = {set of resolved instances}
    # agent_totals_by_llm[llm][agent] = count of instances in that file
    # all_instances_by_llm[llm] = {set of all instances found in any file for this LLM}
    
    results_by_llm = defaultdict(lambda: defaultdict(set))
    agent_totals_by_llm = defaultdict(lambda: defaultdict(int))
    all_instances_by_llm = defaultdict(set)

    for file_path in files:
        filename = os.path.basename(file_path)
        if not filename.endswith(".json"):
            continue
            
        name_part = filename[:-5] # remove .json
        
        # Determine Agent and LLM based on separator
        if "__" in name_part:
            parts = name_part.split("__")
            agent = parts[0]
            llm = parts[1]
        else:
            # Fallback for gold_gpt-5.1.json etc.
            parts = name_part.split("_")
            if len(parts) >= 2:
                agent = parts[0]
                llm = "_".join(parts[1:])
            else:
                agent = name_part
                llm = "unknown"

        if os.path.isdir(file_path):
            continue

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Count total instances for this agent
            agent_totals_by_llm[llm][agent] = len(data)
                
            for instance_id, info in data.items():
                all_instances_by_llm[llm].add(instance_id)
                
                # Check if resolved
                is_resolved = False
                if isinstance(info, dict) and "n_resolved_tests" in info:
                    if info["n_resolved_tests"] > 0:
                        is_resolved = True
                
                if is_resolved:
                     results_by_llm[llm][agent].add(instance_id)

        except Exception as e:
            print(f"Error reading {filename}: {e}")
            continue

    # Generate Report
    for llm in sorted(results_by_llm.keys()):
        print(f"\nLLM: {llm}")
        print("-" * 60)
        
        global_total = len(all_instances_by_llm[llm])
        print(f"Total Unique Instances (Global): {global_total}")
        
        # Calculate Union of Resolved (At least 1 resolved)
        all_resolved_by_any = set()
        for agent in results_by_llm[llm]:
            all_resolved_by_any.update(results_by_llm[llm][agent])
        
        count_at_least_one = len(all_resolved_by_any)
        percent_at_least_one = (count_at_least_one / global_total * 100) if global_total > 0 else 0
        print(f"Instances with at least 1 resolved: {count_at_least_one} ({percent_at_least_one:.2f}%)")
        print("-" * 30)
        
        # Table Header
        # Agent | Total Included | Resolved | % of Included | % of Global
        print(f"{'Agent':<50} | {'Total':<8} | {'Resolved':<8} | {'% (Global)':<10}")
        print("-" * 88)
        
        # Sort agents by resolved count, descending
        agents_stats = []
        for agent in results_by_llm[llm].keys():
            # Ensure we get all agents, even if 0 resolved (though they handled in results_by_llm keys if they are there)
            # Better to iterate over agent_totals_by_llm to catch agents with 0 resolutions?
            pass
            
        agents_list = list(agent_totals_by_llm[llm].keys())
        
        stats_list = []
        for agent in agents_list:
            total_included = agent_totals_by_llm[llm][agent]
            resolved_count = len(results_by_llm[llm][agent])
            
            # % of Global Total
            pct_global = (resolved_count / global_total * 100) if global_total > 0 else 0
            
            stats_list.append((agent, total_included, resolved_count, pct_global))
            
        stats_list.sort(key=lambda x: x[2], reverse=True)
        
        for agent, total_inc, resolved, pct_glob in stats_list:
            print(f"{agent:<50} | {total_inc:<8} | {resolved:<8} | {pct_glob:.2f}%")

        # Calculate Solvability Distribution
        instance_solve_counts = defaultdict(int)
        for agent, resolved_set in results_by_llm[llm].items():
            for instance_id in resolved_set:
                instance_solve_counts[instance_id] += 1
        
        solve_count_histogram = defaultdict(int)
        # Tests solved by 0 agents
        unsolved_count = global_total - len(instance_solve_counts)
        solve_count_histogram[0] = unsolved_count
        
        for instance_id, count in instance_solve_counts.items():
            solve_count_histogram[count] += 1
            
        print("-" * 30)
        print("Solvability Distribution:")
        print("(# Agents who solved it) -> (# Tests)")
        print(f"{'# Agents':<10} | {'# Tests':<10} | {'% of Tests':<10}")
        print("-" * 40)
        for n in sorted(solve_count_histogram.keys()):
            cnt = solve_count_histogram[n]
            pct = (cnt / global_total * 100) if global_total > 0 else 0
            print(f"{n:<10} | {cnt:<10} | {pct:.2f}%")

if __name__ == "__main__":
    count_instances()
