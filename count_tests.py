import json
import os
from collections import defaultdict

RESULTS_DIR = r"c:\Users\naolt\Downloads\class projects\dkang\results\run_result"


# ============================================================
# IO HELPERS
# ============================================================

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return None


def parse_filename(filename):
    name = os.path.splitext(filename)[0]

    if name.startswith("gold_"):
        return "GOLD", name.replace("gold_", "")
    if name.startswith("none_"):
        return "NONE", name.replace("none_", "")

    parts = name.split("__")
    return (parts[0], parts[1]) if len(parts) == 2 else (name, "Unknown")


# ============================================================
# MEANINGFUL TESTS
# ============================================================

def get_meaningful_tests(gold_data, none_data):
    meaningful = {}
    for inst in set(gold_data) | set(none_data):
        gold_res = set(gold_data.get(inst, {}).get("details", {}).get("resolved", []))
        none_res = set(none_data.get(inst, {}).get("details", {}).get("resolved", []))
        diff = gold_res - none_res
        if diff:
            meaningful[inst] = diff
    return meaningful


# ============================================================
# TEST UNIVERSES
# ============================================================

def agent_test_universe(agent_data):
    universe = {}
    for inst, data in agent_data.items():
        d = data.get("details", {})
        universe[inst] = set(d.get("resolved", [])) | set(d.get("failed", []))
    return universe


def gold_test_universe(gold_data):
    universe = {}
    for inst, data in gold_data.items():
        d = data.get("details", {})
        universe[inst] = set(d.get("resolved", [])) | set(d.get("failed", []))
    return universe


# ============================================================
# AGENT METRICS
# ============================================================

def analyze_agent(agent_data, agent_universe, gold_universe):
    tests_available = sum(len(v) for v in agent_universe.values())
    tests_attempted = tests_available  # resolved ∪ failed by definition

    solved_any = solved_half = solved_all = 0

    for inst, gold_tests in gold_universe.items():
        if not gold_tests:
            continue

        resolved = set(
            agent_data.get(inst, {}).get("details", {}).get("resolved", [])
        )

        if resolved:
            solved_any += 1

        if len(resolved) >= 0.5 * len(gold_tests):
            solved_half += 1

        if resolved == gold_tests:
            solved_all += 1

    inst_total = len(gold_universe)

    return {
        "tests_available": tests_available,
        "tests_attempted": tests_attempted,
        "inst_cov_pct": solved_any / inst_total * 100 if inst_total else 0.0,
        "solved_any": solved_any,
        "solved_half": solved_half,
        "solved_all": solved_all,
    }


# ============================================================
# MAIN
# ============================================================

def analyze_results():
    files = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".json")]

    files_by_llm = defaultdict(list)
    gold_files, none_files = {}, {}

    for f in files:
        agent, llm = parse_filename(f)
        if agent == "GOLD":
            gold_files[llm] = f
        elif agent == "NONE":
            none_files[llm] = f
        else:
            files_by_llm[llm].append(f)

    for llm in files_by_llm:
        print(f"\n{'=' * 90}")
        print(f"ANALYSIS GROUP: Test Generation LLM = {llm}")
        print(f"{'=' * 90}")

        gk = next(k for k in gold_files if k in llm or llm in k)
        nk = next(k for k in none_files if k in llm or llm in k)

        gold_data = load_json(os.path.join(RESULTS_DIR, gold_files[gk]))
        none_data = load_json(os.path.join(RESULTS_DIR, none_files[nk]))

        meaningful = get_meaningful_tests(gold_data, none_data)
        total_meaningful_tests = sum(len(v) for v in meaningful.values())

        print(f"\n  Meaningful Instances: {len(meaningful)}")
        print(f"  Meaningful Tests: {total_meaningful_tests}")
        print("-" * 90)

        headers = [
            "Agent", "Mean.Tests", "%Mean",
            "TestsAvail", "TestsAttempted",
            "InstCov%", "Solved≥1", "Solved≥50%", "Solved100%"
        ]

        fmt = "{:<40} | {:<10} | {:<6} | {:<11} | {:<14} | {:<8} | {:<8} | {:<10} | {:<9}"
        print(fmt.format(*headers))
        print("-" * 150)

        gold_universe = gold_test_universe(gold_data)

        for fname in files_by_llm[llm]:
            agent, _ = parse_filename(fname)
            agent_data = load_json(os.path.join(RESULTS_DIR, fname))
            if not agent_data:
                continue

            mean_res = sum(
                len(set(agent_data.get(i, {}).get("details", {}).get("resolved", [])) & t)
                for i, t in meaningful.items()
            )

            pct_mean = mean_res / total_meaningful_tests * 100 if total_meaningful_tests else 0.0

            agent_universe = agent_test_universe(agent_data)
            stats = analyze_agent(agent_data, agent_universe, gold_universe)

            print(fmt.format(
                agent,
                mean_res,
                f"{pct_mean:.2f}",
                stats["tests_available"],
                stats["tests_attempted"],
                f"{stats['inst_cov_pct']:.2f}",
                stats["solved_any"],
                stats["solved_half"],
                stats["solved_all"]
            ))


if __name__ == "__main__":
    analyze_results()
