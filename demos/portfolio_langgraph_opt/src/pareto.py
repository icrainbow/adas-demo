"""
Pareto frontier computation for multi-objective optimization.

Objectives:
- Maximize avg_coverage
- Minimize avg_total_tokens
"""


def is_dominated(a: dict, b: dict) -> bool:
    """
    Check if candidate a is dominated by candidate b.
    
    A candidate a is dominated by b if:
    - b has coverage >= a.coverage AND tokens <= a.tokens
    - AND at least one inequality is strict
    
    Args:
        a: Candidate dict with avg_coverage and avg_total_tokens
        b: Candidate dict with avg_coverage and avg_total_tokens
        
    Returns:
        True if a is dominated by b, False otherwise
    """
    a_cov = a.get("avg_coverage", 0)
    a_tok = a.get("avg_total_tokens", 0)
    b_cov = b.get("avg_coverage", 0)
    b_tok = b.get("avg_total_tokens", 0)
    
    # b dominates a if b is at least as good in both objectives
    # and strictly better in at least one
    coverage_better_or_equal = b_cov >= a_cov
    tokens_better_or_equal = b_tok <= a_tok
    
    # At least one must be strictly better
    coverage_strictly_better = b_cov > a_cov
    tokens_strictly_better = b_tok < a_tok
    
    if coverage_better_or_equal and tokens_better_or_equal:
        if coverage_strictly_better or tokens_strictly_better:
            return True
    
    return False


def compute_pareto_front(rows: list[dict]) -> list[dict]:
    """
    Compute Pareto frontier from candidate rows.
    
    Filters out candidates that have None or missing token metrics.
    
    Args:
        rows: List of candidate dicts with avg_coverage and avg_total_tokens
        
    Returns:
        List of non-dominated candidates (Pareto frontier)
    """
    # Filter out rows with missing token metrics
    valid_rows = []
    for row in rows:
        tokens = row.get("avg_total_tokens")
        coverage = row.get("avg_coverage")
        if tokens is not None and coverage is not None:
            valid_rows.append(row)
    
    if not valid_rows:
        return []
    
    # Find non-dominated candidates
    pareto_front = []
    
    for candidate in valid_rows:
        dominated = False
        for other in valid_rows:
            if candidate is other:
                continue
            if is_dominated(candidate, other):
                dominated = True
                break
        
        if not dominated:
            pareto_front.append(candidate)
    
    return pareto_front


def sort_pareto_front(front: list[dict]) -> list[dict]:
    """
    Sort Pareto front by tokens ascending, then coverage descending.
    
    Args:
        front: List of Pareto-optimal candidates
        
    Returns:
        Sorted list
    """
    return sorted(front, key=lambda x: (x.get("avg_total_tokens", 0), -x.get("avg_coverage", 0)))
