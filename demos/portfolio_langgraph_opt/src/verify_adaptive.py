"""
Regression check script to verify AD0 vs AD1 differences.
Quick test to ensure adaptive candidates produce observable differences.
"""

import sys
import os

# Add repo root to path for imports
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, repo_root)

from demos.portfolio_langgraph_opt.src.evaluate import load_cases, load_policy_text, evaluate_candidate


def main():
    print("=" * 70)
    print("ADAPTIVE VERIFICATION TEST")
    print("=" * 70)
    print()
    
    # Load data
    cases_path = "demos/portfolio_langgraph_opt/data/cases.jsonl"
    policy_path = "demos/portfolio_langgraph_opt/data/policy_snippets.txt"
    
    try:
        cases = load_cases(cases_path)
        policy_text = load_policy_text(policy_path)
        print(f"Loaded {len(cases)} cases")
        print()
    except Exception as e:
        print(f"Error loading data: {e}")
        return 1
    
    # Use first 5 cases for quick test
    test_cases = cases[:5]
    
    # Define two candidates: same topology, different adaptive flag
    candidate_ad0 = {
        "use_retriever": False,
        "use_risk_decompose": False,
        "use_behavior_check": False,
        "use_hitl_gate": False,
        "synth_style": "A",
        "max_steps": 4,
        "adaptive": False,
        "adaptive_policy": "strict"
    }
    
    candidate_ad1 = {
        "use_retriever": False,
        "use_risk_decompose": False,
        "use_behavior_check": False,
        "use_hitl_gate": False,
        "synth_style": "A",
        "max_steps": 4,
        "adaptive": True,
        "adaptive_policy": "strict"
    }
    
    # Evaluate both
    print("Evaluating AD0 (adaptive=False)...")
    try:
        result_ad0 = evaluate_candidate(candidate_ad0, test_cases, policy_text)
    except Exception as e:
        print(f"Error evaluating AD0: {e}")
        return 1
    
    print("Evaluating AD1 (adaptive=True)...")
    try:
        result_ad1 = evaluate_candidate(candidate_ad1, test_cases, policy_text)
    except Exception as e:
        print(f"Error evaluating AD1: {e}")
        return 1
    
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()
    
    # Extract samples for comparison
    samples_ad0 = result_ad0["samples"]
    samples_ad1 = result_ad1["samples"]
    
    # Count cases with non-empty signals
    signal_counts_ad0 = sum(1 for s in samples_ad0 if s["signals"])
    signal_counts_ad1 = sum(1 for s in samples_ad1 if s["signals"])
    
    print(f"Cases with non-empty signals:")
    print(f"  AD0: {signal_counts_ad0}/{len(samples_ad0)}")
    print(f"  AD1: {signal_counts_ad1}/{len(samples_ad1)}")
    print()
    
    # Count cases where path differs
    path_differs = 0
    for s0, s1 in zip(samples_ad0, samples_ad1):
        if s0["path"] != s1["path"]:
            path_differs += 1
    
    print(f"Cases where path differs: {path_differs}/{len(samples_ad0)}")
    print()
    
    # Find a case where adaptive activated
    adaptive_example = None
    for s in samples_ad1:
        if "Adaptive subgraphs activated:" in s["explanation"]:
            adaptive_example = s
            break
    
    if adaptive_example:
        print("=" * 70)
        print("EXAMPLE: Adaptive Activation Detected")
        print("=" * 70)
        print()
        print(f"Case ID: {adaptive_example['case_id']}")
        print(f"Requested Action: {adaptive_example['requested_action']}")
        print()
        print(f"Signals: {adaptive_example['signals']}")
        print()
        print(f"Path: {' -> '.join(adaptive_example['path'])}")
        print()
        print("Explanation (first 20 lines):")
        print("-" * 70)
        lines = adaptive_example['explanation'].split('\n')
        for i, line in enumerate(lines[:20]):
            print(line)
        if len(lines) > 20:
            print(f"... ({len(lines) - 20} more lines)")
        print()
    else:
        print("WARNING: No adaptive activation detected in AD1 samples")
        print()
    
    # Summary
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print()
    
    success = True
    if signal_counts_ad1 == 0:
        print("❌ FAIL: No signals detected in any AD1 case")
        success = False
    else:
        print(f"✓ PASS: Signals detected in {signal_counts_ad1} AD1 cases")
    
    if path_differs == 0:
        print("❌ FAIL: No path differences between AD0 and AD1")
        success = False
    else:
        print(f"✓ PASS: Path differs in {path_differs} cases")
    
    if not adaptive_example:
        print("❌ FAIL: No adaptive subgraph activation in explanations")
        success = False
    else:
        print("✓ PASS: Adaptive subgraph activation marker found")
    
    print()
    
    if success:
        print("✓ ALL CHECKS PASSED")
        return 0
    else:
        print("❌ SOME CHECKS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
