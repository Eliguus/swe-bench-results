
import json
import os

RESULTS_DIR = r"c:\Users\naolt\Downloads\class projects\dkang\results\all_results"

def get_instances(filename):
    path = os.path.join(RESULTS_DIR, filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        instances = set()
        if isinstance(data, dict):
            # Check keys
            for k in data.keys():
                if "__" in k: instances.add(k)
            # Check known lists
            for key in ["resolved", "no_generation", "generated", "with_logs"]:
                if key in data and isinstance(data[key], list):
                    instances.update(data[key])
        return instances
    except:
        return set()

verified_file = "results_rag_gpt4.json"
lite_file = "results_artemis_agent_v2.json"

v_set = get_instances(verified_file)
l_set = get_instances(lite_file)

print(f"Verified ({verified_file}): {len(v_set)}")
print(f"Lite ({lite_file}): {len(l_set)}")
print(f"Intersection: {len(v_set.intersection(l_set))}")
print(f"Lite - Verified: {len(l_set - v_set)}")
print(f"Verified - Lite: {len(v_set - l_set)}")

if l_set.issubset(v_set):
    print("Lite is a subset of Verified.")
else:
    print("Lite is NOT a subset of Verified.")
