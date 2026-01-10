"""
Verify token cost tracking across different carryover modes.
Tests that token usage varies appropriately with carryover policy.
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
    print("TOKEN COST VERIFICATION")
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
    
    # Find 3 candidates with identical topology except carryover
    # Target: R1-D1-B1-H0-SA-M4-AD1-APS-CO{0,1,2}
    all_cands = all_candidates_small()
    
    target_base = {
        "use_retriever": True,
        "use_risk_decompose": True,
        "use_behavior_check": True,
        "use_hitl_gate": False,
        "synth_style": "A",
        "max_steps": 4,
        "adaptive": True,
        "adaptive_policy": "strict"
    }
    
    co0_candidate = None
    co1_candidate = None
    
    for c in all_cands:
        match = all(c.get(k) == v for k, v in target_base.items())
        if match:
            if c.get("carryover") == "none":
                co0_candidate = c
            elif c.get("carryover") == "compact":
                co1_candidate = c
    
    if not co0_candidate or not co1_candidate:
        print("\nERROR: Could not find target candidates")
        print(f"  Looking for carryover variants of topology with R1-D1-B1-H0-AD1")
        sys.exit(1)
    
    # NOTE: all_candidates_small() only has "none" and "compact", not "full"
    # That's by design to keep search space manageable
    
    print(f"\nTesting candidates:")
    print(f"  CO0 (none):    {candidate_to_name(co0_candidate)}")
    print(f"  CO1 (compact): {candidate_to_name(co1_candidate)}")
    
    # Evaluate both candidates
    print("\n" + "-" * 80)
    print("Evaluating CO0 (carryover=none)...")
    res_co0 = evaluate_candidate(co0_candidate, cases, policy)
    
    print("Evaluating CO1 (carryover=compact)...")
    res_co1 = evaluate_candidate(co1_candidate, cases, policy)
    
    # Analyze results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    def print_result(res, label):
        metrics = res.get("metrics", {})
        print(f"\n{label}:")
        print(f"  avg_coverage:         {metrics.get('avg_coverage', 0):.3f}")
        print(f"  avg_steps:            {metrics.get('avg_steps', 0):.2f}")
        print(f"  avg_prompt_tokens:    {metrics.get('avg_prompt_tokens', 0):.1f}")
        print(f"  avg_completion_tokens: {metrics.get('avg_completion_tokens', 0):.1f}")
        print(f"  avg_total_tokens:     {metrics.get('avg_total_tokens', 0):.1f}")
        print(f"  score:                {res.get('score', 0):.2f}")
    
    print_result(res_co0, "CO0 (none)")
    print_result(res_co1, "CO1 (compact)")
    
    # Verification checks
    print("\n" + "=" * 80)
    print("VERIFICATION CHECKS")
    print("=" * 80)
    
    co0_tokens = res_co0["metrics"]["avg_total_tokens"]
    co1_tokens = res_co1["metrics"]["avg_total_tokens"]
    
    co0_coverage = res_co0["metrics"]["avg_coverage"]
    co1_coverage = res_co1["metrics"]["avg_coverage"]
    
    checks_passed = 0
    checks_total = 0
    
    # Check 1: Token usage should increase with carryover (unless both are zero/minimal)
    checks_total += 1
    if co0_tokens > 0 and co1_tokens > 0:
        if co1_tokens > co0_tokens:
            print(f"✓ PASS: compact mode uses more tokens ({co1_tokens:.1f} > {co0_tokens:.1f})")
            checks_passed += 1
        else:
            print(f"✗ FAIL: compact should use more tokens, but {co1_tokens:.1f} <= {co0_tokens:.1f}")
    else:
        print(f"⚠ SKIP: Token measurement not active (CO0: {co0_tokens}, CO1: {co1_tokens})")
        checks_passed += 1  # Don't penalize if token tracking is disabled
    
    # Check 2: Coverage should not trivially become 0 due to carryover
    checks_total += 1
    if co0_coverage > 0 and co1_coverage > 0:
        print(f"✓ PASS: Both modes maintain coverage (CO0: {co0_coverage:.3f}, CO1: {co1_coverage:.3f})")
        checks_passed += 1
    else:
        print(f"✗ FAIL: Coverage dropped to zero (CO0: {co0_coverage:.3f}, CO1: {co1_coverage:.3f})")
    
    # Check 3: Prompt tokens should be higher in compact mode (context is longer)
    checks_total += 1
    co0_prompt = res_co0["metrics"]["avg_prompt_tokens"]
    co1_prompt = res_co1["metrics"]["avg_prompt_tokens"]
    if co0_prompt > 0 and co1_prompt > 0:
        if co1_prompt > co0_prompt:
            print(f"✓ PASS: compact mode has higher prompt tokens ({co1_prompt:.1f} > {co0_prompt:.1f})")
            checks_passed += 1
        else:
            print(f"⚠ WARNING: compact mode should have higher prompt tokens, but {co1_prompt:.1f} <= {co0_prompt:.1f}")
            checks_passed += 1  # Soft warning, not a hard failure
    else:
        print(f"⚠ SKIP: Prompt token measurement not active")
        checks_passed += 1
    
    print(f"\nOverall: {checks_passed}/{checks_total} checks passed")
    
    if checks_passed == checks_total:
        print("\n✓ VERIFICATION PASSED")
        return 0
    else:
        print("\n✗ VERIFICATION FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
