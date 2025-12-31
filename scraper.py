import os
import re
import shutil
import subprocess
import sys

def run_git_command(args, cwd=None):
    """Run a git command and return output."""
    try:
        # Check if git is available
        result = subprocess.run(
            args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command {' '.join(args)}: {e.stderr}", flush=True)
        raise

def main():
    print("Starting Robust Git-Clone Scraper...", flush=True)
    
    repo_url = "https://github.com/SWE-bench/experiments.git"
    temp_dir = "temp_experiments_clone_v2"
    output_dir = "all_results"
    target_path = "evaluation/verified"
    
    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. Clone with sparse checkout
    if os.path.exists(temp_dir):
        print(f"Cleaning up previous temp directory {temp_dir}...", flush=True)
        try:
             # robust cleanup
             def on_rm_error(func, path, exc_info):
                os.chmod(path, 0o777)
                func(path)
             shutil.rmtree(temp_dir, onerror=on_rm_error)
        except Exception as e:
            print(f"Warning: Could not clean up {temp_dir}: {e}", flush=True)
            # Consider failing or using a different dir if this happens?
            # We'll proceed and hope for the best or error out during clone.

    print(f"Cloning {repo_url} (sparse)...", flush=True)
    try:
        # Modern sparse clone
        subprocess.run(["git", "clone", "--filter=blob:none", "--sparse", repo_url, temp_dir], check=True)
        
        # Set sparse checkout path
        print(f"Setting sparse checkout to {target_path}...", flush=True)
        run_git_command(["git", "sparse-checkout", "set", target_path], cwd=temp_dir)
        
        print("Clone setup complete. Processing...", flush=True)
        
        count = 0
        base_search_path = os.path.join(temp_dir, target_path)
        
        if not os.path.exists(base_search_path):
            print(f"Error: Target path {base_search_path} does not exist. Sparse checkout might have failed.", flush=True)
            return

        # Iterate through experiment directories
        # We expect: evaluation/verified/<ExpDir>/results/results.json
        
        for exp_dir_name in os.listdir(base_search_path):
            exp_path = os.path.join(base_search_path, exp_dir_name)
            if not os.path.isdir(exp_path):
                continue
                
            results_path = os.path.join(exp_path, "results")
            results_json_path = os.path.join(results_path, "results.json")
            
            if not os.path.exists(results_json_path):
                # Maybe results are not in a 'results' subdir? (unlikely for verified, but check)
                # Some might be just <ExpDir>/results.json? 
                continue
                
            # Strategy: Find Agent Name
            agent_name = None
            
            # 1. Try to find [Agent]__[LLM] file in results_path
            try:
                for filename in os.listdir(results_path):
                    if filename == "results.json" or filename.startswith("resolved_by"):
                        continue
                    
                    if "__" in filename:
                        match = re.search(r'(.+)__(.+)', filename)
                        if match:
                            raw_agent = match.group(1)
                            # Clean if it has extension
                            if raw_agent.endswith(".json"):
                                raw_agent = raw_agent.rsplit('.', 1)[0]
                            agent_name = raw_agent
                            pass # Found it
            except OSError:
                pass
            
            # 2. Fallback: Parse directory name
            if not agent_name:
                # ExpDir format usuall: YYYYMMDD_AgentName_...
                # Strip date
                match = re.match(r'^\d{8}_(.+)', exp_dir_name)
                if match:
                    agent_name = match.group(1)
                    # Heuristic: if it looks like Agent_Model, can we split?
                    # But verifying this is hard without the file. 
                    # We will use the directory suffix as the best guess.
                    # e.g. "JoyCode", "agentless-1.5_gpt4o"
                else:
                    agent_name = exp_dir_name # Just use the whole dir name if no date
            
            if agent_name:
                # Save file
                dest_filename = f"results_{agent_name}.json"
                # Sanitize filename just in case
                dest_filename = re.sub(r'[<>:"/\\|?*]', '_', dest_filename)
                
                dest_path = os.path.join(output_dir, dest_filename)
                
                shutil.copy2(results_json_path, dest_path)
                print(f"  - Extracted: {agent_name} (from {exp_dir_name})", flush=True)
                count += 1
            else:
                print(f"  - Skipped: {exp_dir_name} (Could not determine agent name)", flush=True)

        print(f"\nScraping completed. Extracted {count} result files.", flush=True)

    except Exception as e:
        print(f"Fatal Error: {e}", flush=True)
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            print("Cleaning up...", flush=True)
            try:
                 def on_rm_error(func, path, exc_info):
                    os.chmod(path, 0o777)
                    func(path)
                 shutil.rmtree(temp_dir, onerror=on_rm_error)
            except Exception as e:
                print(f"Cleanup warning: {e}", flush=True)

if __name__ == "__main__":
    main()
