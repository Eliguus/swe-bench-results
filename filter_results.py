import os
import shutil
import re

def normalize_name(name):
    """
    Normalize strings for comparison:
    - Lowercase
    - Replace + and _ and - with spaces
    """
    clean = re.sub(r'[+_\-.]', ' ', name.lower())
    return " ".join(clean.split())

def is_match(wanted_norm, scraped_norm):
    """
    Stricter Heuristic:
    1. Exact match is best.
    2. Substring match (rarely wrong for agent names).
    3. Token overlap, BUT:
       - Ignore common model names (claude, gpt, sonnet, etc.) to avoid matching just on "claude-4".
       - Require the *first* token to match (usually the Agent Brand).
    """
    if wanted_norm == scraped_norm:
        return True
    
    # 0. Common model terms to ignore for fuzzy matching
    ignored_tokens = {
        'gpt', 'claude', 'sonnet', 'opus', 'haiku', 'gemini', 'pro', 'flash', 'preview', 
        'mini', 'turbo', '4', '3', '3.5', '5', '4o', 'o1', 'step', 'v1', 'v2', 'plus', 'tools'
    }

    w_tokens = [t for t in wanted_norm.split() if t not in ignored_tokens]
    s_tokens = [t for t in scraped_norm.split() if t not in ignored_tokens]

    # If all tokens were ignored (e.g. just "claude 4"), fall back to original tokens
    if not w_tokens: w_tokens = wanted_norm.split()
    if not s_tokens: s_tokens = scraped_norm.split()
    
    # 1. Primary Check: First token MUST match (or be very similar)
    # This prevents "Epam..." matching "Moatless..." just because of "claude"
    if w_tokens and s_tokens:
        if w_tokens[0] != s_tokens[0]:
             # Allow if one starts with string of other? e.g. "swe-agent" vs "swe_agent" handled by norm.
             # "live-swe-agent" vs "livesweagent" -> "live" vs "livesweagent". Mismatch.
             # Check if first token is substring of the other's first token
             if w_tokens[0] not in s_tokens[0] and s_tokens[0] not in w_tokens[0]:
                 return False

    w_set = set(w_tokens)
    s_set = set(s_tokens)
    
    # intersection
    common = w_set.intersection(s_set)
    
    min_len = min(len(w_set), len(s_set))
    if min_len == 0: return False
    
    # Require very high overlap if we are relying on tokens
    if len(common) >= min_len: # All tokens of the shorter one are present
        return True
        
    return False

def main():
    print("Starting Smart Result Filter...", flush=True)
    
    # Paths
    local_results_dir = "results"
    scraped_results_dir = "all_results"
    output_dir = "filtered_results"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}", flush=True)

    # 1. Identify Wanted Agents from local directory
    wanted_agents = {} # Norm -> Original
    
    print(f"Scanning {local_results_dir} for target agents...", flush=True)
    try:
        files = os.listdir(local_results_dir)
        for f in files:
            if f.startswith("gold_") or f.startswith("none_") or f.startswith("resolved_by"):
                continue
            
            # Format: Agent__LLM.json
            if "__" in f:
                parts = f.split("__")
                agent_name = parts[0]
                norm = normalize_name(agent_name)
                wanted_agents[norm] = agent_name
    except FileNotFoundError:
        print(f"Error: Directory {local_results_dir} not found.", flush=True)
        return

    print(f"Found {len(wanted_agents)} unique agents (normalized) to look for.", flush=True)

    # 2. Filter scraped results
    print(f"Scanning {scraped_results_dir} for matches...", flush=True)
    
    copied_count = 0
    matched_scraped_files = set()
    
    try:
        scraped_files = os.listdir(scraped_results_dir)
        
        for f in scraped_files:
            if not f.startswith("results_") or not f.endswith(".json"):
                continue
            
            # Extract agent name from results_<AgentName>.json
            agent_part = f[8:-5]
            scraped_norm = normalize_name(agent_part)
            
            # Check against all wanted agents
            match_found = None
            for wanted_norm, original_name in wanted_agents.items():
                if is_match(wanted_norm, scraped_norm):
                    match_found = original_name
                    break
            
            if match_found:
                # User wants to rename files to match local agent name
                # e.g. results_match_found.json
                
                # Sanitize match_found just in case (though local filenames should be safe)
                safe_match_name = match_found.replace("__", "_") # avoid double underscore confusion if any
                new_filename = f"results_{safe_match_name}.json"
                
                output_path = os.path.join(output_dir, new_filename)
                
                # Handle Collisions (e.g. multiple openhands scraped files mapping to one local OpenHands)
                if os.path.exists(output_path):
                     base, ext = os.path.splitext(new_filename)
                     counter = 1
                     while os.path.exists(os.path.join(output_dir, f"{base}_{counter}{ext}")):
                         counter += 1
                     new_filename = f"{base}_{counter}{ext}"
                     output_path = os.path.join(output_dir, new_filename)
                
                src_path = os.path.join(scraped_results_dir, f)
                shutil.copy2(src_path, output_path)
                print(f"  - MATCH: '{agent_part}' matches '{match_found}' -> Renamed to {new_filename}", flush=True)
                copied_count += 1
                matched_scraped_files.add(f)
            # else:
            #     print(f"  - No match for: {agent_part} (Norm: {scraped_norm})")

        # 3. Report missing
        print("\n--- Missing Agents ---")
        # Check which wanted agents didn't get a corresponding scraped file
        # This is approximate because multiple scraped files might match one wanted, or vice versa
        # But good for user feedback
        pass

    except FileNotFoundError:
        print(f"Error: Directory {scraped_results_dir} not found.", flush=True)
        return

    print(f"\nFiltering completed. Copied {copied_count} files to '{output_dir}'.", flush=True)

if __name__ == "__main__":
    main()
