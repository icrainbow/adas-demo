"""Portfolio advisory graph search and optimization."""

import argparse
import json
import os
import random
import sys

# Add repo root to path for imports
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, repo_root)

from demos.portfolio_langgraph_opt.src.search_space import validate_candidate
from demos.portfolio_langgraph_opt.src.search_space_generator import load_search_space_for_case
from demos.portfolio_langgraph_opt.src.evaluate import (
    load_cases,
    load_policy_text,
    evaluate_candidate
)
from demos.portfolio_langgraph_opt.src.pareto import (
    compute_pareto_front,
    sort_pareto_front
)
from demos.portfolio_langgraph_opt.src.dot_export import wiring_to_dot


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Search and optimize portfolio advisory graph configurations"
    )
    
    parser.add_argument(
        "--cases",
        default="demos/portfolio_langgraph_opt/data/cases.jsonl",
        help="Path to cases JSONL file"
    )
    
    parser.add_argument(
        "--policy",
        default="demos/portfolio_langgraph_opt/data/policy_snippets.txt",
        help="Path to policy text file"
    )
    
    parser.add_argument(
        "--mode",
        choices=["grid", "random"],
        default="grid",
        help="Search mode: grid (sequential) or random (sampled)"
    )
    
    parser.add_argument(
        "--budget",
        type=int,
        default=16,
        help="Number of candidates to evaluate (min 1, max 32)"
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed for reproducibility"
    )
    
    parser.add_argument(
        "--out",
        default="demos/portfolio_langgraph_opt/outputs/results.json",
        help="Output JSON file path"
    )
    
    parser.add_argument(
        "--registry_dir",
        default=None,
        help="Path to agent registry directory (defaults to kyc_case/agents)"
    )
    
    parser.add_argument(
        "--resume_path",
        default=None,
        help="Path to existing results JSON to resume from (optional)"
    )
    
    parser.add_argument(
        "--emit_dot",
        action="store_true",
        help="Export DOT (Graphviz) graph representation for each candidate"
    )
    
    args = parser.parse_args()
    
    # Validate budget
    if args.budget < 1 or args.budget > 32:
        parser.error("--budget must be between 1 and 32")
    
    return args


def save_intermediate_results(out_path, args, case_count, baseline, baseline_score, 
                              baseline_result, best_result, best_score, all_scores):
    """Save intermediate results during search (for resume capability)."""
    emit_dot = getattr(args, 'emit_dot', False)
    
    # Build baseline entry
    baseline_entry = {
        "candidate": baseline,
        "score": baseline_score,
        "metrics": baseline_result["metrics"],
        "samples": baseline_result["samples"]
    }
    
    # Add DOT/wiring to baseline if available
    if emit_dot and "wiring" in baseline_result:
        baseline_wiring = baseline_result["wiring"]
        baseline_entry["dot"] = wiring_to_dot(baseline_wiring)
        baseline_entry["wiring"] = baseline_wiring
    
    # Build best entry
    best_entry = {
        "candidate": best_result["candidate"],
        "score": best_score,
        "metrics": best_result["metrics"],
        "samples": best_result["samples"]
    }
    
    # Add DOT/wiring to best if available
    if emit_dot and "wiring" in best_result:
        best_wiring = best_result["wiring"]
        best_entry["dot"] = wiring_to_dot(best_wiring)
        best_entry["wiring"] = best_wiring
    
    output = {
        "run": {
            "mode": args.mode,
            "budget": args.budget,
            "seed": args.seed,
            "case_count": case_count,
            "emit_dot": emit_dot
        },
        "baseline": baseline_entry,
        "best": best_entry,
        "all_scores": sorted(all_scores, key=lambda x: x["score"], reverse=True)
    }
    
    # Ensure output directory exists
    out_dir = os.path.dirname(out_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    
    # Write to temp file first, then rename (atomic operation)
    temp_path = out_path + ".tmp"
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        os.replace(temp_path, out_path)
    except Exception as e:
        print(f"  Warning: Failed to save intermediate results: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)


def main():
    """Main search and evaluation pipeline."""
    args = parse_args()
    
    # Set registry directory if provided
    if args.registry_dir:
        from demos.portfolio_langgraph_opt.src.search_space import set_registry_dir
        set_registry_dir(args.registry_dir)
        print(f"Using custom registry: {args.registry_dir}")
    
    # Load case-specific search space (YAML or default)
    import re
    from pathlib import Path
    
    case_id = None
    if args.registry_dir:
        # Infer case_id from registry_dir path: .../cases/<case_id>/agents
        parts = Path(args.registry_dir).parts
        if 'cases' in parts:
            cases_idx = parts.index('cases')
            if cases_idx + 1 < len(parts):
                inferred_case_id = parts[cases_idx + 1]
                # Validate format
                if re.match(r'^[A-Za-z0-9_-]+$', inferred_case_id):
                    case_id = inferred_case_id
    
    # Load search space module (YAML spec or default)
    ss = load_search_space_for_case(case_id=case_id, registry_dir=args.registry_dir)
    default_candidate = ss.default_candidate
    all_candidates_small = ss.all_candidates_small
    candidate_to_name = ss.candidate_to_name
    
    if case_id:
        print(f"Loaded search space for case: {case_id}")
    
    print("=" * 70)
    print("Portfolio Advisory Graph Search")
    print("=" * 70)
    print(f"Mode: {args.mode}")
    print(f"Budget: {args.budget}")
    print(f"Seed: {args.seed}")
    print(f"Cases: {args.cases}")
    print(f"Policy: {args.policy}")
    print(f"Registry: {args.registry_dir or 'default (kyc_case)'}")
    print(f"Emit DOT: {args.emit_dot}")
    if args.resume_path:
        print(f"Resume from: {args.resume_path}")
    print()
    
    # Load existing results if resuming
    existing_results = None
    existing_names = set()
    baseline_from_resume = None
    
    if args.resume_path:
        print("Loading existing results for resume...")
        try:
            with open(args.resume_path, 'r', encoding='utf-8') as f:
                existing_results = json.load(f)
            
            # Build set of already-evaluated candidate names
            existing_names = {entry["name"] for entry in existing_results.get("all_scores", [])}
            
            # Get baseline from existing results
            if "baseline" in existing_results:
                baseline_from_resume = existing_results["baseline"]
            
            print(f"  Found {len(existing_names)} already-evaluated candidates")
            print(f"  Will skip: {', '.join(sorted(existing_names)[:5])}{' ...' if len(existing_names) > 5 else ''}")
            print()
        except FileNotFoundError:
            print(f"  Resume file not found: {args.resume_path}")
            print(f"  Starting fresh run...")
            print()
        except Exception as e:
            print(f"  Warning: Failed to load resume file: {e}")
            print(f"  Starting fresh run...")
            print()
    
    # Load data
    print("Loading data...")
    try:
        cases = load_cases(args.cases)
        policy_text = load_policy_text(args.policy)
        print(f"Loaded {len(cases)} cases")
        print(f"Loaded policy text ({len(policy_text)} chars)")
        print()
    except Exception as e:
        print(f"Error loading data: {e}")
        sys.exit(1)
    
    # Get baseline and candidate list
    baseline = default_candidate()
    candidate_list = all_candidates_small()
    
    print(f"Generated {len(candidate_list)} candidates")
    
    # Select subset based on mode
    if args.mode == "random":
        # Shuffle with seed and take first budget
        rng = random.Random(args.seed)
        shuffled = candidate_list.copy()
        rng.shuffle(shuffled)
        candidate_subset = shuffled[:args.budget]
        print(f"Random sampling: selected {len(candidate_subset)} candidates")
    else:
        # Grid mode: take first budget candidates
        candidate_subset = candidate_list[:args.budget]
        print(f"Grid mode: evaluating first {len(candidate_subset)} candidates")
    
    print()
    
    # Evaluate baseline
    print("Evaluating baseline...")
    
    # Use baseline from resume if available
    if baseline_from_resume:
        print("  Using baseline from resume file...")
        baseline_result = baseline_from_resume
        baseline_score = baseline_result["score"]
        baseline = baseline_result["candidate"]
        print(f"Baseline score: {baseline_score:.2f} (from resume)")
    else:
        try:
            baseline_result = evaluate_candidate(baseline, cases, policy_text, export_descriptor=args.emit_dot)
            baseline_score = baseline_result["score"]
            print(f"Baseline score: {baseline_score:.2f}")
        except Exception as e:
            print(f"Error evaluating baseline: {e}")
            sys.exit(1)
    
    print(f"  Coverage: {baseline_result['metrics']['avg_coverage']:.3f}")
    print(f"  Violation rate: {baseline_result['metrics']['violation_rate']:.3f}")
    print(f"  HITL rate: {baseline_result['metrics']['hitl_rate']:.3f}")
    print(f"  Avg steps: {baseline_result['metrics']['avg_steps']:.2f}")
    print(f"  Avg total tokens: {baseline_result['metrics'].get('avg_total_tokens', 0):.1f}")
    print()
    
    # Evaluate candidates
    print(f"Evaluating {len(candidate_subset)} candidates...")
    
    # Initialize with existing results if resuming
    if existing_results and "all_scores" in existing_results:
        all_scores = existing_results["all_scores"].copy()
        print(f"  Loaded {len(all_scores)} existing results")
    else:
        all_scores = []
    
    all_results = []  # Store full results for Pareto analysis
    best_result = None
    best_score = float('-inf')
    
    # Track best from existing results
    if existing_results and "best" in existing_results:
        best_result = existing_results["best"]
        best_score = best_result["score"]
        print(f"  Best from existing results: {best_score:.2f}")
    
    evaluated_count = 0
    skipped_count = 0
    
    for i, candidate in enumerate(candidate_subset, 1):
        name = candidate_to_name(candidate)
        
        # Skip if already evaluated
        if name in existing_names:
            skipped_count += 1
            if skipped_count == 1 or skipped_count % 10 == 0:
                print(f"  Skipping {name} (already evaluated)")
            continue
        
        try:
            validate_candidate(candidate)
            result = evaluate_candidate(candidate, cases, policy_text, export_descriptor=args.emit_dot)
            score = result["score"]
            
            # Build candidate_spec
            candidate_spec = {
                "selected_agents": candidate.get("selected_agents", []),
                "derived": {
                    "use_retriever": candidate.get("use_retriever", False),
                    "use_risk_decompose": candidate.get("use_risk_decompose", False),
                    "use_behavior_check": candidate.get("use_behavior_check", False),
                    "use_hitl_gate": candidate.get("use_hitl_gate", False),
                    "synth_style": candidate.get("synth_style", "A"),
                    "max_steps": candidate.get("max_steps", 4),
                    "adaptive": candidate.get("adaptive", False),
                    "adaptive_policy": candidate.get("adaptive_policy", "strict"),
                    "carryover": candidate.get("carryover", "compact")
                }
            }
            
            # Add DOT and wiring if emit_dot is enabled
            if args.emit_dot and "wiring" in result:
                wiring = result["wiring"]
                candidate_spec["dot"] = wiring_to_dot(wiring)
                candidate_spec["wiring"] = wiring
            
            # Track all scores
            all_scores.append({
                "name": name,
                "score": score,
                "metrics": result["metrics"],
                "candidate_spec": candidate_spec
            })
            
            # Store full result for Pareto analysis
            all_results.append(result)
            
            # Track best
            if score > best_score:
                best_score = score
                best_result = result
            
            evaluated_count += 1
            
            # Progress update
            if evaluated_count % 5 == 0 or i == len(candidate_subset):
                print(f"  Evaluated {evaluated_count} new + {skipped_count} existing = {evaluated_count + skipped_count}/{len(candidate_subset)} (best: {best_score:.2f})")
            
            # Incremental save every 5 evaluations
            if evaluated_count % 5 == 0:
                save_intermediate_results(
                    args.out, 
                    args, 
                    len(cases), 
                    baseline, 
                    baseline_score, 
                    baseline_result,
                    best_result,
                    best_score,
                    all_scores
                )
        
        except Exception as e:
            print(f"  Warning: Failed to evaluate candidate {name}: {e}")
            continue
    
    print()
    print(f"  Total: {evaluated_count} new evaluations, {skipped_count} skipped")
    print()
    
    if best_result is None:
        print("Error: No candidates were successfully evaluated")
        sys.exit(1)
    
    # Print summary
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print()
    print(f"Baseline: {candidate_to_name(baseline)}")
    print(f"  Score: {baseline_score:.2f}")
    print(f"  Coverage: {baseline_result['metrics']['avg_coverage']:.3f}")
    print(f"  Violation rate: {baseline_result['metrics']['violation_rate']:.3f}")
    print(f"  HITL rate: {baseline_result['metrics']['hitl_rate']:.3f}")
    print(f"  Avg steps: {baseline_result['metrics']['avg_steps']:.2f}")
    print(f"  Avg tokens: {baseline_result['metrics'].get('avg_total_tokens', 0):.1f} (prompt: {baseline_result['metrics'].get('avg_prompt_tokens', 0):.1f}, completion: {baseline_result['metrics'].get('avg_completion_tokens', 0):.1f})")
    print()
    print(f"Best: {candidate_to_name(best_result['candidate'])}")
    print(f"  Score: {best_score:.2f}")
    print(f"  Coverage: {best_result['metrics']['avg_coverage']:.3f}")
    print(f"  Violation rate: {best_result['metrics']['violation_rate']:.3f}")
    print(f"  HITL rate: {best_result['metrics']['hitl_rate']:.3f}")
    print(f"  Avg steps: {best_result['metrics']['avg_steps']:.2f}")
    print(f"  Avg tokens: {best_result['metrics'].get('avg_total_tokens', 0):.1f} (prompt: {best_result['metrics'].get('avg_prompt_tokens', 0):.1f}, completion: {best_result['metrics'].get('avg_completion_tokens', 0):.1f})")
    print()
    print(f"Improvement: {best_score - baseline_score:.2f} points")
    print()
    
    # Create output object
    emit_dot = getattr(args, 'emit_dot', False)
    
    # Build baseline entry
    baseline_entry = {
        "candidate": baseline,
        "score": baseline_score,
        "metrics": baseline_result["metrics"],
        "samples": baseline_result["samples"]
    }
    
    # Add DOT/wiring to baseline if available
    if emit_dot and "wiring" in baseline_result:
        baseline_wiring = baseline_result["wiring"]
        baseline_entry["dot"] = wiring_to_dot(baseline_wiring)
        baseline_entry["wiring"] = baseline_wiring
    
    # Build best entry
    best_entry = {
        "candidate": best_result["candidate"],
        "score": best_score,
        "metrics": best_result["metrics"],
        "samples": best_result["samples"]
    }
    
    # Add DOT/wiring to best if available
    if emit_dot and "wiring" in best_result:
        best_wiring = best_result["wiring"]
        best_entry["dot"] = wiring_to_dot(best_wiring)
        best_entry["wiring"] = best_wiring
    
    output = {
        "run": {
            "mode": args.mode,
            "budget": args.budget,
            "seed": args.seed,
            "case_count": len(cases),
            "emit_dot": emit_dot
        },
        "baseline": baseline_entry,
        "best": best_entry,
        "all_scores": sorted(all_scores, key=lambda x: x["score"], reverse=True)
    }
    
    # Ensure output directory exists
    out_dir = os.path.dirname(args.out)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    
    # Write output JSON
    try:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        print(f"Results written to: {args.out}")
    except Exception as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)
    
    # Compute Pareto frontier
    print()
    print("Computing Pareto frontier...")
    
    # Build rows for Pareto analysis (baseline + all evaluated candidates)
    pareto_rows = []
    
    # Add baseline
    baseline_row = {
        "candidate_name": candidate_to_name(baseline),
        "score": baseline_score,
        "avg_coverage": baseline_result["metrics"]["avg_coverage"],
        "avg_steps": baseline_result["metrics"]["avg_steps"],
        "hitl_rate": baseline_result["metrics"]["hitl_rate"],
        "violation_rate": baseline_result["metrics"]["violation_rate"],
        "avg_total_tokens": baseline_result["metrics"].get("avg_total_tokens"),
        "avg_prompt_tokens": baseline_result["metrics"].get("avg_prompt_tokens"),
        "avg_completion_tokens": baseline_result["metrics"].get("avg_completion_tokens")
    }
    pareto_rows.append(baseline_row)
    
    # Add all evaluated candidates
    for result in all_results:
        row = {
            "candidate_name": candidate_to_name(result["candidate"]),
            "score": result["score"],
            "avg_coverage": result["metrics"]["avg_coverage"],
            "avg_steps": result["metrics"]["avg_steps"],
            "hitl_rate": result["metrics"]["hitl_rate"],
            "violation_rate": result["metrics"]["violation_rate"],
            "avg_total_tokens": result["metrics"].get("avg_total_tokens"),
            "avg_prompt_tokens": result["metrics"].get("avg_prompt_tokens"),
            "avg_completion_tokens": result["metrics"].get("avg_completion_tokens")
        }
        pareto_rows.append(row)
    
    # Compute Pareto front
    pareto_front = compute_pareto_front(pareto_rows)
    pareto_front_sorted = sort_pareto_front(pareto_front)
    
    print(f"  Pareto frontier: {len(pareto_front_sorted)} candidates")
    
    # Write Pareto JSON
    pareto_json_path = args.out.replace(".json", "_pareto.json")
    pareto_output = {
        "pareto_front": pareto_front_sorted,
        "all_rows": pareto_rows
    }
    
    try:
        with open(pareto_json_path, 'w', encoding='utf-8') as f:
            json.dump(pareto_output, f, indent=2)
        print(f"  Pareto JSON written to: {pareto_json_path}")
    except Exception as e:
        print(f"  Warning: Failed to write Pareto JSON: {e}")
    
    # Write Pareto Markdown
    pareto_md_path = args.out.replace(".json", "_pareto.md")
    
    try:
        with open(pareto_md_path, 'w', encoding='utf-8') as f:
            f.write("# Pareto Frontier\n\n")
            f.write("Candidates on the Pareto frontier (maximize coverage, minimize tokens):\n\n")
            
            # Table header
            f.write("| Candidate | Coverage | Total Tokens | Score | Avg Steps | HITL Rate | Violation Rate |\n")
            f.write("|-----------|----------|--------------|-------|-----------|-----------|----------------|\n")
            
            # Table rows
            for row in pareto_front_sorted:
                name = row["candidate_name"]
                cov = row["avg_coverage"]
                tok = row.get("avg_total_tokens", 0)
                score = row["score"]
                steps = row["avg_steps"]
                hitl = row["hitl_rate"]
                viol = row["violation_rate"]
                
                f.write(f"| {name} | {cov:.3f} | {tok:.1f} | {score:.2f} | {steps:.2f} | {hitl:.3f} | {viol:.3f} |\n")
        
        print(f"  Pareto markdown written to: {pareto_md_path}")
    except Exception as e:
        print(f"  Warning: Failed to write Pareto markdown: {e}")
    
    print()
    print("=" * 70)
    print("Search complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
