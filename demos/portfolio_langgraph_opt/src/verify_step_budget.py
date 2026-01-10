"""
Verify that max_steps budget is enforced for both AD0 and AD1 candidates.
Tests that path length never exceeds candidate["max_steps"].
"""
import os
import sys

# Adjust sys.path for relative imports
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, repo_root)

from demos.portfolio_langgraph_opt.src.evaluate import load_cases, load_policy_text, evaluate_candidate
from demos.portfolio_langgraph_opt.src.search_space import all_candidates_small, candidate_to_name


def main():
    print("=" * 80)
    print("STEP BUDGET VERIFICATION")
    print("=" * 80)
    
    # Enable full results return
    os.environ["PORTFOLIO_RETURN_ALL"] = "1"
    
    # Load data
    cases_path = "demos/portfolio_langgraph_opt/data/cases.jsonl"
    policy_path = "demos/portfolio_langgraph_opt/data/policy_snippets.txt"
    
    print(f"\nLoading data from:")
    print(f"  Cases: {cases_path}")
    print(f"  Policy: {policy_path}")
    
    cases = load_cases(cases_path)
    policy = load_policy_text(policy_path)
    
    print(f"  Loaded {len(cases)} cases")
    
    # Find specific candidates to test: R1-D1-B1-H1-SA-M4-AD0-APS and R1-D1-B1-H1-SA-M4-AD1-APS
    all_cands = all_candidates_small()
    
    target_ad0_name = "R1-D1-B1-H1-SA-M4-AD0-APS"
    target_ad1_name = "R1-D1-B1-H1-SA-M4-AD1-APS"
    
    ad0_candidate = None
    ad1_candidate = None
    
    for c in all_cands:
        name = candidate_to_name(c)
        if name == target_ad0_name:
            ad0_candidate = c
        elif name == target_ad1_name:
            ad1_candidate = c
    
    if not ad0_candidate or not ad1_candidate:
        print("\nERROR: Could not find target candidates")
        print(f"  Looking for: {target_ad0_name} and {target_ad1_name}")
        print(f"  Available candidates: {len(all_cands)}")
        sys.exit(1)
    
    print(f"\nTesting candidates:")
    print(f"  AD0: {target_ad0_name}")
    print(f"  AD1: {target_ad1_name}")
    print(f"  max_steps: {ad0_candidate['max_steps']}")
    
    # Evaluate both candidates
    print("\n" + "-" * 80)
    print("Evaluating AD0 (adaptive=False)...")
    res_ad0 = evaluate_candidate(ad0_candidate, cases, policy)
    
    print("Evaluating AD1 (adaptive=True)...")
    res_ad1 = evaluate_candidate(ad1_candidate, cases, policy)
    
    # Analyze results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    def analyze_result(res, label):
        all_results = res.get("all_results", [])
        if not all_results:
            print(f"\n{label}: No per-case results available")
            return False
        
        max_steps = res["candidate"]["max_steps"]
        path_lengths = [len(r["path"]) for r in all_results]
        max_path_len = max(path_lengths)
        avg_path_len = sum(path_lengths) / len(path_lengths)
        
        # Check for violations
        violations = [r for r in all_results if len(r["path"]) > max_steps]
        
        print(f"\n{label}:")
        print(f"  max_steps budget: {max_steps}")
        print(f"  max path length: {max_path_len}")
        print(f"  avg path length: {avg_path_len:.2f}")
        print(f"  violations (path > max_steps): {len(violations)}")
        
        if violations:
            print(f"  VIOLATION DETAILS:")
            for v in violations[:5]:  # Show first 5
                print(f"    Case {v['case_id']}: path={v['path']} (len={len(v['path'])})")
        
        # Metrics
        metrics = res.get("metrics", {})
        print(f"  avg_coverage: {metrics.get('avg_coverage', 0):.3f}")
        print(f"  violation_rate: {metrics.get('violation_rate', 0):.3f}")
        print(f"  hitl_rate: {metrics.get('hitl_rate', 0):.3f}")
        print(f"  avg_steps: {metrics.get('avg_steps', 0):.2f}")
        print(f"  adaptive_marker_rate: {metrics.get('adaptive_marker_rate', 0):.3f}")
        print(f"  score: {res.get('score', 0):.2f}")
        
        return len(violations) == 0
    
    ad0_pass = analyze_result(res_ad0, "AD0")
    ad1_pass = analyze_result(res_ad1, "AD1")
    
    # Final verdict
    print("\n" + "=" * 80)
    print("VERDICT")
    print("=" * 80)
    
    if ad0_pass and ad1_pass:
        print("\n✓ PASS: Both AD0 and AD1 respect max_steps budget")
        return 0
    else:
        print("\n✗ FAIL: Step budget violations detected")
        if not ad0_pass:
            print("  AD0 has violations")
        if not ad1_pass:
            print("  AD1 has violations")
        return 1


if __name__ == "__main__":
    sys.exit(main())
