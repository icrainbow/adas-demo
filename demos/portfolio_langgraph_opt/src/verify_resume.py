"""
Verification script for resume capability.

Tests that the search script can:
1. Run a small search and save results
2. Resume from those results
3. Skip already-evaluated candidates
4. Append new results correctly
"""

import json
import os
import subprocess
import sys
import tempfile


def run_search(cases, policy, budget, output_path, resume_path=None):
    """Run portfolio_search.py with given parameters."""
    cmd = [
        sys.executable,
        "demos/portfolio_langgraph_opt/portfolio_search.py",
        "--cases", cases,
        "--policy", policy,
        "--mode", "grid",
        "--budget", str(budget),
        "--seed", "42",
        "--out", output_path
    ]
    
    if resume_path:
        cmd.extend(["--resume_path", resume_path])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


def main():
    print("=" * 70)
    print("Resume Capability Verification")
    print("=" * 70)
    print()
    
    # Check that data files exist
    cases_path = "demos/portfolio_langgraph_opt/data/cases.jsonl"
    policy_path = "demos/portfolio_langgraph_opt/data/policy_snippets.txt"
    
    if not os.path.exists(cases_path):
        print(f"❌ Error: Cases file not found: {cases_path}")
        sys.exit(1)
    
    if not os.path.exists(policy_path):
        print(f"❌ Error: Policy file not found: {policy_path}")
        sys.exit(1)
    
    print(f"✓ Found cases: {cases_path}")
    print(f"✓ Found policy: {policy_path}")
    print()
    
    # Create temp directory for test outputs
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test 1: Run initial search with budget=4
        print("TEST 1: Initial search (budget=4)")
        print("-" * 70)
        
        output1 = os.path.join(tmpdir, "test_initial.json")
        result1 = run_search(cases_path, policy_path, 4, output1)
        
        if result1.returncode != 0:
            print(f"❌ Initial search failed")
            print(result1.stderr)
            sys.exit(1)
        
        with open(output1, 'r') as f:
            data1 = json.load(f)
        
        initial_count = len(data1["all_scores"])
        initial_names = {entry["name"] for entry in data1["all_scores"]}
        
        print(f"✓ Initial search completed")
        print(f"  Evaluated: {initial_count} candidates")
        print(f"  Names: {', '.join(sorted(initial_names))}")
        print()
        
        # Test 2: Resume from initial results with same budget (should skip all)
        print("TEST 2: Resume with same budget (should skip all)")
        print("-" * 70)
        
        output2 = os.path.join(tmpdir, "test_resume_same.json")
        result2 = run_search(cases_path, policy_path, 4, output2, resume_path=output1)
        
        if result2.returncode != 0:
            print(f"❌ Resume search failed")
            print(result2.stderr)
            sys.exit(1)
        
        # Check that "Skipping" appears in output
        if "Skipping" not in result2.stdout and "already evaluated" not in result2.stdout:
            print(f"❌ Expected skip messages in output")
            print(result2.stdout)
            sys.exit(1)
        
        with open(output2, 'r') as f:
            data2 = json.load(f)
        
        resume_same_count = len(data2["all_scores"])
        
        print(f"✓ Resume with same budget completed")
        print(f"  Candidates in output: {resume_same_count}")
        
        if resume_same_count != initial_count:
            print(f"❌ Expected {initial_count} candidates, got {resume_same_count}")
            sys.exit(1)
        
        print(f"✓ Candidate count matches (no duplicates)")
        print()
        
        # Test 3: Resume with larger budget (should evaluate new ones only)
        print("TEST 3: Resume with larger budget (should add new candidates)")
        print("-" * 70)
        
        output3 = os.path.join(tmpdir, "test_resume_expand.json")
        result3 = run_search(cases_path, policy_path, 8, output3, resume_path=output1)
        
        if result3.returncode != 0:
            print(f"❌ Resume expand search failed")
            print(result3.stderr)
            sys.exit(1)
        
        with open(output3, 'r') as f:
            data3 = json.load(f)
        
        expand_count = len(data3["all_scores"])
        expand_names = {entry["name"] for entry in data3["all_scores"]}
        new_names = expand_names - initial_names
        
        print(f"✓ Resume expand completed")
        print(f"  Total candidates: {expand_count}")
        print(f"  Initial: {initial_count}")
        print(f"  New: {len(new_names)}")
        
        if expand_count <= initial_count:
            print(f"❌ Expected more candidates after expansion")
            sys.exit(1)
        
        if not initial_names.issubset(expand_names):
            print(f"❌ Initial candidates missing from expanded results")
            sys.exit(1)
        
        print(f"✓ All initial candidates preserved")
        print(f"✓ New candidates added: {', '.join(sorted(new_names))}")
        print()
        
        # Test 4: Verify baseline is reused
        print("TEST 4: Verify baseline reuse")
        print("-" * 70)
        
        baseline1 = data1["baseline"]
        baseline3 = data3["baseline"]
        
        if baseline1["score"] != baseline3["score"]:
            print(f"❌ Baseline score changed: {baseline1['score']} -> {baseline3['score']}")
            sys.exit(1)
        
        print(f"✓ Baseline score consistent: {baseline1['score']:.2f}")
        print()
        
        # Test 5: Verify no duplicate candidates in final output
        print("TEST 5: Verify no duplicate candidates")
        print("-" * 70)
        
        all_names_list = [entry["name"] for entry in data3["all_scores"]]
        unique_names = set(all_names_list)
        
        if len(all_names_list) != len(unique_names):
            duplicates = [name for name in unique_names if all_names_list.count(name) > 1]
            print(f"❌ Found duplicate candidates: {duplicates}")
            sys.exit(1)
        
        print(f"✓ No duplicates found in {len(all_names_list)} candidates")
        print()
    
    print("=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)
    print()
    print("Resume capability verified:")
    print("  ✓ Can load existing results")
    print("  ✓ Skips already-evaluated candidates")
    print("  ✓ Appends new results correctly")
    print("  ✓ Preserves baseline across runs")
    print("  ✓ No duplicate candidates in output")
    print()


if __name__ == "__main__":
    main()
