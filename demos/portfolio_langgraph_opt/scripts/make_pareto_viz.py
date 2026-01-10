"""
Visualization pipeline for LangGraph topology search results.

Creates Pareto frontier plots and analysis reports.
"""

import argparse
import json
import os
import sys

# Add repo root to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, repo_root)

from demos.portfolio_langgraph_opt.src.pareto import compute_pareto_front, sort_pareto_front

# Try to import matplotlib
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Plots will not be generated.")


def parse_candidate_name(name: str) -> dict:
    """
    Parse candidate name into configuration dictionary.
    
    Format: R{0/1}-D{0/1}-B{0/1}-H{0/1}-S{A/B}-M{n}-AD{0/1}-AP{S/L}-CO{0/1/2}
    
    Args:
        name: Candidate name string
        
    Returns:
        Configuration dictionary with parsed values
    """
    parts = name.split('-')
    config = {}
    
    for part in parts:
        if part.startswith('R'):
            config['use_retriever'] = part[1:] == '1'
        elif part.startswith('D'):
            config['use_risk_decompose'] = part[1:] == '1'
        elif part.startswith('B'):
            config['use_behavior_check'] = part[1:] == '1'
        elif part.startswith('H'):
            config['use_hitl_gate'] = part[1:] == '1'
        elif part.startswith('S') and not part.startswith('SA') and not part.startswith('SB'):
            config['synth_style'] = part[1:]
        elif part.startswith('SA') or part.startswith('SB'):
            config['synth_style'] = part[1]
        elif part.startswith('M'):
            config['max_steps'] = int(part[1:])
        elif part.startswith('AD'):
            config['adaptive'] = part[2:] == '1'
        elif part.startswith('AP'):
            # Map AP codes to policy names
            ap_code = part[2:]
            if ap_code == 'S':
                config['adaptive_policy'] = 'strict'
            elif ap_code == 'L':
                config['adaptive_policy'] = 'lenient'
            else:
                config['adaptive_policy'] = ap_code
        elif part.startswith('CO'):
            # Map CO codes to carryover modes
            co_code = part[2:]
            if co_code == '0':
                config['carryover'] = 'none'
            elif co_code == '1':
                config['carryover'] = 'compact'
            elif co_code == '2':
                config['carryover'] = 'full'
            else:
                config['carryover'] = co_code
    
    return config


def generate_candidates_manifest(candidates: list[dict], baseline: dict, best: dict, output_path: str):
    """
    Generate candidates manifest JSON mapping names to configurations.
    
    Args:
        candidates: List of candidate dicts with names
        baseline: Baseline candidate dict
        best: Best candidate dict
        output_path: Path to write manifest JSON
    """
    manifest = {
        "by_name": {}
    }
    
    # Parse all candidates
    for candidate in candidates:
        name = candidate["name"]
        config = parse_candidate_name(name)
        manifest["by_name"][name] = config
    
    # Add baseline if not already present
    baseline_name = baseline["name"]
    if baseline_name not in manifest["by_name"]:
        manifest["by_name"][baseline_name] = parse_candidate_name(baseline_name)
    
    # Add best if not already present
    best_name = best["name"]
    if best_name not in manifest["by_name"]:
        manifest["by_name"][best_name] = parse_candidate_name(best_name)
    
    # Write manifest
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"Candidates manifest written to: {output_path}")


def parse_results(results_path: str) -> tuple[list[dict], dict, dict]:
    """
    Parse results JSON into flat candidate list.
    
    Returns:
        (all_candidates, baseline_data, best_data)
    """
    with open(results_path, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    # Import candidate_to_name
    from demos.portfolio_langgraph_opt.src.search_space import candidate_to_name
    
    candidates = []
    
    # Parse all_scores
    for entry in results.get("all_scores", []):
        name = entry.get("name", "unknown")
        metrics = entry.get("metrics", {})
        
        candidates.append({
            "name": name,
            "avg_total_tokens": metrics.get("avg_total_tokens", 0),
            "avg_coverage": metrics.get("avg_coverage", 0),
            "score": entry.get("score", 0)
        })
    
    # Extract baseline
    baseline = results.get("baseline", {})
    baseline_candidate = baseline.get("candidate", {})
    baseline_metrics = baseline.get("metrics", {})
    baseline_name = candidate_to_name(baseline_candidate) if baseline_candidate else "baseline"
    baseline_data = {
        "name": baseline_name,
        "avg_total_tokens": baseline_metrics.get("avg_total_tokens", 0),
        "avg_coverage": baseline_metrics.get("avg_coverage", 0),
        "score": baseline.get("score", 0)
    }
    
    # Extract best
    best = results.get("best", {})
    best_candidate = best.get("candidate", {})
    best_metrics = best.get("metrics", {})
    best_name = candidate_to_name(best_candidate) if best_candidate else "best"
    best_data = {
        "name": best_name,
        "avg_total_tokens": best_metrics.get("avg_total_tokens", 0),
        "avg_coverage": best_metrics.get("avg_coverage", 0),
        "score": best.get("score", 0)
    }
    
    return candidates, baseline_data, best_data


def plot_pareto_frontier(candidates: list[dict], baseline: dict, best: dict, output_path: str):
    """Create token-based Pareto frontier plot."""
    if not MATPLOTLIB_AVAILABLE:
        print(f"Skipping plot generation: {output_path}")
        return
    
    # Compute Pareto frontier
    pareto_front = compute_pareto_front(candidates)
    pareto_sorted = sort_pareto_front(pareto_front)
    
    # Extract data
    all_tokens = [c["avg_total_tokens"] for c in candidates]
    all_coverage = [c["avg_coverage"] for c in candidates]
    
    pareto_tokens = [c["avg_total_tokens"] for c in pareto_sorted]
    pareto_coverage = [c["avg_coverage"] for c in pareto_sorted]
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot all candidates
    ax.scatter(all_tokens, all_coverage, c='lightgray', s=50, alpha=0.6, label='All candidates')
    
    # Plot Pareto frontier points
    ax.scatter(pareto_tokens, pareto_coverage, c='blue', s=100, alpha=0.8, label='Pareto frontier', zorder=3)
    
    # Draw Pareto frontier line
    if len(pareto_sorted) > 1:
        ax.plot(pareto_tokens, pareto_coverage, 'b--', alpha=0.5, linewidth=1.5, zorder=2)
    
    # Annotate top 3 Pareto points
    for i, point in enumerate(pareto_sorted[:3]):
        ax.annotate(
            point["name"],
            (point["avg_total_tokens"], point["avg_coverage"]),
            xytext=(10, 5),
            textcoords='offset points',
            fontsize=8,
            alpha=0.8
        )
    
    # Highlight baseline and best
    ax.scatter([baseline["avg_total_tokens"]], [baseline["avg_coverage"]], 
               c='green', s=150, marker='*', label='Baseline', zorder=4)
    ax.scatter([best["avg_total_tokens"]], [best["avg_coverage"]], 
               c='red', s=150, marker='*', label='Best (by score)', zorder=4)
    
    ax.set_xlabel('Average Total Tokens', fontsize=12)
    ax.set_ylabel('Average Coverage', fontsize=12)
    ax.set_title('Pareto Frontier: Coverage vs. Token Cost', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Token-based Pareto plot saved to: {output_path}")


def plot_cost_pareto(candidates: list[dict], baseline: dict, best: dict, 
                      output_path: str, token_price_per_1k: float = 0.01):
    """Create cost-based Pareto frontier plot."""
    if not MATPLOTLIB_AVAILABLE:
        print(f"Skipping plot generation: {output_path}")
        return
    
    # Add cost field to candidates
    candidates_with_cost = []
    for c in candidates:
        cost_per_case = c["avg_total_tokens"] / 1000 * token_price_per_1k
        candidates_with_cost.append({
            "name": c["name"],
            "cost_per_case": cost_per_case,
            "avg_coverage": c["avg_coverage"],
            "score": c["score"]
        })
    
    # Compute Pareto frontier on cost
    pareto_front = compute_pareto_front([
        {
            "name": c["name"],
            "avg_total_tokens": c["cost_per_case"],  # Use cost as "tokens" for Pareto computation
            "avg_coverage": c["avg_coverage"],
            "score": c["score"]
        }
        for c in candidates_with_cost
    ])
    
    pareto_sorted = sorted(pareto_front, key=lambda x: x["avg_total_tokens"])
    
    # Extract data
    all_cost = [c["cost_per_case"] for c in candidates_with_cost]
    all_coverage = [c["avg_coverage"] for c in candidates_with_cost]
    
    pareto_cost = [c["avg_total_tokens"] for c in pareto_sorted]
    pareto_coverage = [c["avg_coverage"] for c in pareto_sorted]
    
    # Baseline and best costs
    baseline_cost = baseline["avg_total_tokens"] / 1000 * token_price_per_1k
    best_cost = best["avg_total_tokens"] / 1000 * token_price_per_1k
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot all candidates
    ax.scatter(all_cost, all_coverage, c='lightgray', s=50, alpha=0.6, label='All candidates')
    
    # Plot Pareto frontier points
    ax.scatter(pareto_cost, pareto_coverage, c='blue', s=100, alpha=0.8, label='Pareto frontier', zorder=3)
    
    # Draw Pareto frontier line
    if len(pareto_sorted) > 1:
        ax.plot(pareto_cost, pareto_coverage, 'b--', alpha=0.5, linewidth=1.5, zorder=2)
    
    # Annotate top 3 Pareto points
    for i, point in enumerate(pareto_sorted[:3]):
        # Find original name
        orig = next((c for c in candidates_with_cost if abs(c["cost_per_case"] - point["avg_total_tokens"]) < 0.0001), None)
        if orig:
            ax.annotate(
                orig["name"],
                (point["avg_total_tokens"], point["avg_coverage"]),
                xytext=(10, 5),
                textcoords='offset points',
                fontsize=8,
                alpha=0.8
            )
    
    # Highlight baseline and best
    ax.scatter([baseline_cost], [baseline["avg_coverage"]], 
               c='green', s=150, marker='*', label='Baseline', zorder=4)
    ax.scatter([best_cost], [best["avg_coverage"]], 
               c='red', s=150, marker='*', label='Best (by score)', zorder=4)
    
    ax.set_xlabel(f'Cost per Case (USD @ ${token_price_per_1k:.3f}/1k tokens)', fontsize=12)
    ax.set_ylabel('Average Coverage', fontsize=12)
    ax.set_title('Pareto Frontier: Coverage vs. Cost', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Cost-based Pareto plot saved to: {output_path}")


def generate_markdown_report(candidates: list[dict], baseline: dict, best: dict,
                             output_path: str, token_price_per_1k: float = 0.01):
    """Generate markdown analysis report."""
    
    # Compute Pareto frontier
    pareto_front = compute_pareto_front(candidates)
    pareto_sorted = sort_pareto_front(pareto_front)
    
    # Find cheapest Pareto point
    cheapest_pareto = min(pareto_sorted, key=lambda x: x["avg_total_tokens"])
    
    # Compute costs
    baseline_cost = baseline["avg_total_tokens"] / 1000 * token_price_per_1k
    best_cost = best["avg_total_tokens"] / 1000 * token_price_per_1k
    cheapest_cost = cheapest_pareto["avg_total_tokens"] / 1000 * token_price_per_1k
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Pareto Frontier Analysis\n\n")
        
        f.write("## Summary\n\n")
        f.write(f"**Total Candidates Evaluated:** {len(candidates) + 1} (including baseline)\n\n")
        f.write(f"**Pareto Frontier Size:** {len(pareto_sorted)} candidates\n\n")
        
        f.write("### Key Configurations\n\n")
        
        # Baseline
        f.write("**Baseline:**\n")
        f.write(f"- Configuration: `{baseline['name']}`\n")
        f.write(f"- Coverage: {baseline['avg_coverage']:.3f}\n")
        f.write(f"- Tokens: {baseline['avg_total_tokens']:.1f}\n")
        f.write(f"- Cost: ${baseline_cost:.4f} per case\n")
        f.write(f"- Score: {baseline['score']:.2f}\n\n")
        
        # Best by score
        f.write("**Best (by score):**\n")
        f.write(f"- Configuration: `{best['name']}`\n")
        f.write(f"- Coverage: {best['avg_coverage']:.3f}\n")
        f.write(f"- Tokens: {best['avg_total_tokens']:.1f}\n")
        f.write(f"- Cost: ${best_cost:.4f} per case\n")
        f.write(f"- Score: {best['score']:.2f}\n\n")
        
        # Cheapest Pareto
        f.write("**Cheapest Pareto-Optimal:**\n")
        f.write(f"- Configuration: `{cheapest_pareto['name']}`\n")
        f.write(f"- Coverage: {cheapest_pareto['avg_coverage']:.3f}\n")
        f.write(f"- Tokens: {cheapest_pareto['avg_total_tokens']:.1f}\n")
        f.write(f"- Cost: ${cheapest_cost:.4f} per case\n")
        f.write(f"- Score: {cheapest_pareto['score']:.2f}\n\n")
        
        f.write("## Trade-off Analysis\n\n")
        
        # Calculate improvements and costs
        coverage_improvement = best['avg_coverage'] - baseline['avg_coverage']
        token_increase = best['avg_total_tokens'] - baseline['avg_total_tokens']
        cost_increase = best_cost - baseline_cost
        
        f.write(f"The Pareto frontier reveals the fundamental trade-off between coverage quality and computational cost. ")
        f.write(f"The baseline configuration achieves {baseline['avg_coverage']:.1%} coverage at just ")
        f.write(f"${baseline_cost:.4f} per case, making it the most cost-efficient option. ")
        f.write(f"However, upgrading to the best-scoring configuration improves coverage by ")
        f.write(f"{coverage_improvement:.1%} (to {best['avg_coverage']:.1%}), but increases token usage by ")
        f.write(f"{token_increase:.0f} tokens ({token_increase/baseline['avg_total_tokens']*100:.0f}% increase), ")
        f.write(f"raising the cost to ${best_cost:.4f} per case—a {cost_increase/baseline_cost*100:.0f}% cost increase. ")
        
        f.write(f"For practitioners seeking a middle ground, the cheapest Pareto-optimal configuration ")
        f.write(f"(`{cheapest_pareto['name']}`) offers {cheapest_pareto['avg_coverage']:.1%} coverage at ")
        f.write(f"${cheapest_cost:.4f} per case. ")
        
        f.write(f"The Pareto frontier contains {len(pareto_sorted)} configurations, each representing a ")
        f.write(f"distinct efficiency point where no other configuration achieves both higher coverage ")
        f.write(f"and lower cost simultaneously. Organizations should select configurations based on their ")
        f.write(f"specific constraints: cost-sensitive deployments may prefer the baseline, while ")
        f.write(f"quality-critical applications may justify the premium for higher coverage.\n\n")
        
        f.write("## Pareto Frontier Members\n\n")
        f.write("| Rank | Configuration | Coverage | Tokens | Cost/Case | Score |\n")
        f.write("|------|---------------|----------|--------|-----------|-------|\n")
        
        for i, point in enumerate(pareto_sorted, 1):
            cost = point["avg_total_tokens"] / 1000 * token_price_per_1k
            f.write(f"| {i} | `{point['name']}` | {point['avg_coverage']:.3f} | ")
            f.write(f"{point['avg_total_tokens']:.1f} | ${cost:.4f} | {point['score']:.2f} |\n")
    
    print(f"Markdown report saved to: {output_path}")


def main():
    """Main visualization pipeline."""
    parser = argparse.ArgumentParser(description="Generate Pareto frontier visualizations")
    parser.add_argument(
        "--input",
        default="demos/portfolio_langgraph_opt/outputs/results_v11_pareto_smoke.json",
        help="Input results JSON file"
    )
    parser.add_argument(
        "--output-dir",
        default="demos/portfolio_langgraph_opt/artifacts",
        help="Output directory for artifacts"
    )
    parser.add_argument(
        "--token-price",
        type=float,
        default=0.01,
        help="Token price per 1k tokens in USD"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Pareto Frontier Visualization Pipeline")
    print("=" * 70)
    print(f"Input: {args.input}")
    print(f"Output directory: {args.output_dir}")
    print(f"Token price: ${args.token_price:.3f} per 1k tokens")
    print()
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Parse results
    print("Parsing results...")
    candidates, baseline, best = parse_results(args.input)
    print(f"  Loaded {len(candidates)} candidates")
    print()
    
    # Generate visualizations
    print("Generating visualizations...")
    
    pareto_png = os.path.join(args.output_dir, "pareto.png")
    plot_pareto_frontier(candidates, baseline, best, pareto_png)
    
    pareto_cost_png = os.path.join(args.output_dir, "pareto_cost.png")
    plot_cost_pareto(candidates, baseline, best, pareto_cost_png, args.token_price)
    
    pareto_md = os.path.join(args.output_dir, "pareto.md")
    generate_markdown_report(candidates, baseline, best, pareto_md, args.token_price)
    
    # Generate candidates manifest
    manifest_json = os.path.join(args.output_dir, "candidates_manifest.json")
    generate_candidates_manifest(candidates, baseline, best, manifest_json)
    
    print()
    print("=" * 70)
    print("Visualization pipeline complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
