"""Evaluation module for portfolio advisory candidates."""

import json
import os
import random
from typing import Any


def load_cases(jsonl_path: str) -> list[dict]:
    """
    Load cases from JSONL file with validation.
    
    Args:
        jsonl_path: Path to JSONL file
        
    Returns:
        List of case dictionaries
        
    Raises:
        ValueError: If file format is invalid or required fields missing
    """
    cases = []
    
    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    case = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON at line {line_num}: {e}")
                
                # Validate required fields
                required_fields = ["case_id", "client_profile", "portfolio", 
                                   "requested_action", "gold_rubric"]
                for field in required_fields:
                    if field not in case:
                        raise ValueError(f"Missing required field '{field}' in case at line {line_num}")
                
                # Validate nested structures
                if "must_cover" not in case["gold_rubric"]:
                    raise ValueError(f"Missing 'must_cover' in gold_rubric at line {line_num}")
                if "must_avoid" not in case["gold_rubric"]:
                    raise ValueError(f"Missing 'must_avoid' in gold_rubric at line {line_num}")
                
                cases.append(case)
    
    except FileNotFoundError:
        raise ValueError(f"Cases file not found: {jsonl_path}")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Error loading cases: {e}")
    
    if not cases:
        raise ValueError(f"No valid cases found in {jsonl_path}")
    
    return cases


def load_policy_text(path: str) -> str:
    """
    Load policy text from file.
    
    Args:
        path: Path to policy text file
        
    Returns:
        Policy text as string
        
    Raises:
        ValueError: If file cannot be read
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise ValueError(f"Policy file not found: {path}")
    except Exception as e:
        raise ValueError(f"Error loading policy text: {e}")


def _contains_any(text: str, phrases: list[str]) -> int:
    """
    Count how many phrases are present in text (case-insensitive substring match).
    
    Args:
        text: Text to search in
        phrases: List of phrases to search for
        
    Returns:
        Count of phrases found
    """
    if not text or not phrases:
        return 0
    
    text_lower = text.lower()
    count = 0
    
    for phrase in phrases:
        if phrase.lower() in text_lower:
            count += 1
    
    return count


def coverage_rate(explanation: str, must_cover: list[str]) -> float:
    """
    Compute coverage rate: fraction of must_cover phrases present in explanation.
    
    Args:
        explanation: Generated explanation text
        must_cover: List of phrases that should be covered
        
    Returns:
        Coverage rate as float in [0.0, 1.0]
    """
    if not must_cover:
        return 1.0  # No requirements means full coverage
    
    matches = _contains_any(explanation, must_cover)
    return matches / len(must_cover)


def violation(explanation: str, must_avoid: list[str]) -> bool:
    """
    Check if explanation contains any must_avoid phrases.
    
    Args:
        explanation: Generated explanation text
        must_avoid: List of phrases that should not appear
        
    Returns:
        True if any must_avoid phrase is present, False otherwise
    """
    if not must_avoid:
        return False
    
    return _contains_any(explanation, must_avoid) > 0


def _has_adaptive_marker(explanation: str) -> bool:
    """Check if explanation contains adaptive subgraph activation marker."""
    return "Adaptive subgraphs activated:" in (explanation or "")


def _select_samples_by_coverage(results: list[dict], k_low: int = 2, k_high: int = 2, k_mid: int = 2, seed: int = 7) -> list[dict]:
    """
    Pick representative samples: lowest coverage, highest coverage, plus a few mid-coverage.
    This avoids the 'only 2 samples' blind spot and makes AD0 vs AD1 comparisons reliable.
    
    Args:
        results: List of per-case result dictionaries
        k_low: Number of lowest-coverage samples to pick
        k_high: Number of highest-coverage samples to pick
        k_mid: Number of mid-coverage samples to pick
        seed: Random seed for mid-coverage selection
        
    Returns:
        List of selected sample dictionaries
    """
    if not results:
        return []
    
    r_sorted = sorted(results, key=lambda r: r.get("coverage", 0.0))
    low = r_sorted[:max(0, k_low)]
    high = r_sorted[-max(0, k_high):] if k_high > 0 else []
    
    # mid: pick from middle band excluding extremes
    middle = r_sorted[max(0, k_low): max(0, len(r_sorted) - k_high)]
    if middle and k_mid > 0:
        random.seed(seed)
        mid = random.sample(middle, k=min(k_mid, len(middle)))
    else:
        mid = []
    
    # keep stable order: low -> mid -> high
    picked = low + mid + high
    
    # de-dup by case_id (in case overlaps)
    seen = set()
    out = []
    for r in picked:
        cid = r.get("case_id")
        if cid in seen:
            continue
        seen.add(cid)
        out.append(r)
    
    return out


def evaluate_candidate(candidate: dict, cases: list[dict], policy_text: str) -> dict:
    """
    Evaluate a candidate configuration on all cases.
    
    Args:
        candidate: Configuration dictionary
        cases: List of case dictionaries
        policy_text: Policy guidance text
        
    Returns:
        Dictionary with score, metrics, and sample cases
        
    Raises:
        ValueError: If evaluation fails or data is invalid
    """
    # Import here to avoid circular dependencies
    try:
        from demos.portfolio_langgraph_opt.src.graph_builder import build_runner
        from demos.portfolio_langgraph_opt.src.search_space import validate_candidate, candidate_to_name
    except ImportError as e:
        raise ValueError(f"Failed to import required modules: {e}")
    
    # Validate candidate
    try:
        validate_candidate(candidate)
    except Exception as e:
        raise ValueError(f"Invalid candidate: {e}")
    
    # Compute candidate ID
    candidate_id = candidate_to_name(candidate)
    
    if not cases:
        raise ValueError("No cases provided for evaluation")
    
    # Build runner once for this candidate
    try:
        runner = build_runner(candidate, policy_text)
    except Exception as e:
        raise ValueError(f"Failed to build runner: {e}")
    
    # Collect per-case results
    results = []
    
    for i, case in enumerate(cases):
        try:
            # Run case through graph
            final_state = runner(case)
            
            # Validate output structure
            required_keys = ["explanation", "decision", "path", "signals"]
            for key in required_keys:
                if key not in final_state:
                    raise ValueError(f"Runner output missing key '{key}' for case {case.get('case_id', i)}")
            
            explanation = final_state["explanation"]
            decision = final_state["decision"]
            path = final_state["path"]
            signals = final_state["signals"]
            
            # Compute metrics
            rubric = case["gold_rubric"]
            cover = coverage_rate(explanation, rubric["must_cover"])
            viol = violation(explanation, rubric["must_avoid"])
            hitl = (decision == "ESCALATE")
            steps = len(path)
            adaptive_marker = _has_adaptive_marker(explanation)
            
            results.append({
                "case_id": case["case_id"],
                "requested_action": case["requested_action"],
                "signals": signals,
                "decision": decision,
                "path": path,
                "explanation": explanation,
                "rubric_must_cover": rubric["must_cover"],
                "coverage": cover,
                "violation": viol,
                "hitl": hitl,
                "steps": steps,
                "adaptive_marker": adaptive_marker
            })
        
        except Exception as e:
            raise ValueError(f"Error evaluating case {case.get('case_id', i)}: {e}")
    
    # Aggregate metrics
    n = len(results)
    avg_cover = sum(r["coverage"] for r in results) / n
    violation_rate = sum(1 for r in results if r["violation"]) / n
    hitl_rate = sum(1 for r in results if r["hitl"]) / n
    avg_steps = sum(r["steps"] for r in results) / n
    adaptive_marker_rate = sum(1 for r in results if r.get("adaptive_marker")) / n
    
    # Compute score (unchanged)
    score = 100 * avg_cover - 200 * violation_rate - 10 * hitl_rate - 1 * avg_steps
    
    # Select sample cases with improved sampling strategy
    sample_low = int(os.getenv("PORTFOLIO_SAMPLE_LOW", "2"))
    sample_high = int(os.getenv("PORTFOLIO_SAMPLE_HIGH", "2"))
    sample_mid = int(os.getenv("PORTFOLIO_SAMPLE_MID", "2"))
    sample_seed = int(os.getenv("PORTFOLIO_SAMPLE_SEED", "7"))
    
    picked = _select_samples_by_coverage(results, k_low=sample_low, k_high=sample_high, k_mid=sample_mid, seed=sample_seed)
    
    # Format samples (keep case details, add debug fields)
    samples = []
    for r in picked:
        samples.append({
            "case_id": r["case_id"],
            "requested_action": r["requested_action"],
            "signals": r["signals"],
            "decision": r["decision"],
            "path": r["path"],
            "explanation": r["explanation"],
            "rubric_must_cover": r["rubric_must_cover"],
            "coverage": r["coverage"],
            "steps": r["steps"],
            "adaptive_marker": r["adaptive_marker"]
        })
    
    # Build result dictionary
    result = {
        "candidate_id": candidate_id,
        "candidate": candidate,
        "score": score,
        "metrics": {
            "avg_coverage": avg_cover,
            "violation_rate": violation_rate,
            "hitl_rate": hitl_rate,
            "avg_steps": avg_steps,
            "adaptive_marker_rate": adaptive_marker_rate,
            "num_cases": n
        },
        "samples": samples
    }
    
    # Optional: return all per-case results (default off)
    return_all = os.getenv("PORTFOLIO_RETURN_ALL", "0") == "1"
    if return_all:
        all_results = []
        for r in results:
            all_results.append({
                "case_id": r["case_id"],
                "signals": r["signals"],
                "decision": r["decision"],
                "path": r["path"],
                "coverage": r["coverage"],
                "violation": r["violation"],
                "hitl": r["hitl"],
                "steps": r["steps"],
                "adaptive_marker": r["adaptive_marker"]
            })
        result["all_results"] = all_results
    
    return result
