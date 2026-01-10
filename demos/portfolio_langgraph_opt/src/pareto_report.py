"""
CLI utility to compute Pareto frontier from existing results JSON.

Usage:
    python demos/portfolio_langgraph_opt/src/pareto_report.py --in <results_json> --out <pareto_json>
"""

import argparse
import json
import os
import sys

# Add repo root to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, repo_root)

from demos.portfolio_langgraph_opt.src.pareto import compute_pareto_front, sort_pareto_front


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Compute Pareto frontier from portfolio search results"
    )
    
    parser.add_argument(
        "--in",
        dest="input_file",
        required=True,
        help="Input results JSON file from portfolio_search.py"
    )
    
    parser.add_argument(
        "--out",
        dest="output_file",
        required=True,
        help="Output Pareto JSON file path"
    )
    
    return parser.parse_args()


def extract_rows_from_results(results: dict) -> list[dict]:
    """
    Extract candidate rows from results JSON.
    
    Args:
        results: Results dict from portfolio_search.py
        
    Returns:
        List of candidate rows with metrics
    """
    rows = []
    
    # Extract baseline if present
    if "baseline" in results:
        baseline = results["baseline"]
        baseline_cand = baseline.get("candidate", {})
        
        # Try to construct name from candidate dict
        try:
            from demos.portfolio_langgraph_opt.src.search_space import candidate_to_name
            name = candidate_to_name(baseline_cand)
        except:
            name = "baseline"
        
        metrics = baseline.get("metrics", {})
        row = {
            "candidate_name": name,
            "score": baseline.get("score", 0),
            "avg_coverage": metrics.get("avg_coverage", 0),
            "avg_steps": metrics.get("avg_steps", 0),
            "hitl_rate": metrics.get("hitl_rate", 0),
            "violation_rate": metrics.get("violation_rate", 0),
            "avg_total_tokens": metrics.get("avg_total_tokens"),
            "avg_prompt_tokens": metrics.get("avg_prompt_tokens"),
            "avg_completion_tokens": metrics.get("avg_completion_tokens")
        }
        rows.append(row)
    
    # Extract candidates from all_scores if present
    if "all_scores" in results:
        for entry in results["all_scores"]:
            name = entry.get("name", "unknown")
            metrics = entry.get("metrics", {})
            
            row = {
                "candidate_name": name,
                "score": entry.get("score", 0),
                "avg_coverage": metrics.get("avg_coverage", 0),
                "avg_steps": metrics.get("avg_steps", 0),
                "hitl_rate": metrics.get("hitl_rate", 0),
                "violation_rate": metrics.get("violation_rate", 0),
                "avg_total_tokens": metrics.get("avg_total_tokens"),
                "avg_prompt_tokens": metrics.get("avg_prompt_tokens"),
                "avg_completion_tokens": metrics.get("avg_completion_tokens")
            }
            rows.append(row)
    
    return rows


def main():
    """Main CLI entry point."""
    args = parse_args()
    
    print("=" * 70)
    print("Pareto Frontier Report Generator")
    print("=" * 70)
    print(f"Input: {args.input_file}")
    print(f"Output: {args.output_file}")
    print()
    
    # Load results JSON
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        print(f"Loaded results from {args.input_file}")
    except Exception as e:
        print(f"Error loading input file: {e}")
        sys.exit(1)
    
    # Extract rows
    rows = extract_rows_from_results(results)
    print(f"Extracted {len(rows)} candidate rows")
    
    if not rows:
        print("Warning: No candidate data found in results")
        sys.exit(1)
    
    # Compute Pareto front
    pareto_front = compute_pareto_front(rows)
    pareto_front_sorted = sort_pareto_front(pareto_front)
    
    print(f"Pareto frontier: {len(pareto_front_sorted)} candidates")
    print()
    
    # Write Pareto JSON
    pareto_output = {
        "pareto_front": pareto_front_sorted,
        "all_rows": rows
    }
    
    try:
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(pareto_output, f, indent=2)
        print(f"Pareto JSON written to: {args.output_file}")
    except Exception as e:
        print(f"Error writing Pareto JSON: {e}")
        sys.exit(1)
    
    # Write Pareto Markdown (same naming rule as portfolio_search.py)
    pareto_md_path = args.output_file.replace(".json", ".md")
    
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
        
        print(f"Pareto markdown written to: {pareto_md_path}")
    except Exception as e:
        print(f"Warning: Failed to write Pareto markdown: {e}")
    
    print()
    print("=" * 70)
    print("Report generation complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
