"""Search space definition for portfolio advisory LangGraph optimization."""

CANDIDATE_KEYS = ["use_retriever", "use_risk_decompose", "use_behavior_check", "use_hitl_gate", "synth_style", "max_steps", "adaptive", "adaptive_policy"]


def default_candidate() -> dict:
    """Return a safe baseline candidate configuration."""
    return {
        "use_retriever": False,
        "use_risk_decompose": False,
        "use_behavior_check": False,
        "use_hitl_gate": False,
        "synth_style": "A",
        "max_steps": 4,
        "adaptive": False,
        "adaptive_policy": "strict"
    }


def all_candidates_small() -> list[dict]:
    """
    Generate a deterministic grid of 32 candidate configurations.
    
    Grid dimensions:
    - use_retriever: [True, False]
    - use_risk_decompose: [True, False]
    - use_behavior_check: [True, False]
    - use_hitl_gate: [True, False]
    - synth_style: ["A", "B"]
    - max_steps: 4 (fixed)
    - adaptive: False (fixed)
    - adaptive_policy: "strict" (fixed)
    
    Returns:
        List of 32 candidate dictionaries in fixed order.
    """
    candidates = []
    
    for use_retriever in [True, False]:
        for use_risk_decompose in [True, False]:
            for use_behavior_check in [True, False]:
                for use_hitl_gate in [True, False]:
                    for synth_style in ["A", "B"]:
                        candidate = {
                            "use_retriever": use_retriever,
                            "use_risk_decompose": use_risk_decompose,
                            "use_behavior_check": use_behavior_check,
                            "use_hitl_gate": use_hitl_gate,
                            "synth_style": synth_style,
                            "max_steps": 4,
                            "adaptive": False,
                            "adaptive_policy": "strict"
                        }
                        candidates.append(candidate)
    
    return candidates


def candidate_to_name(c: dict) -> str:
    """
    Convert candidate dict to stable short name.
    
    Format: R{0/1}-D{0/1}-B{0/1}-H{0/1}-S{A/B}-M{max_steps}-AD{0/1}-AP{S/L}
    
    Args:
        c: Candidate dictionary
        
    Returns:
        Short name string (e.g., "R0-D0-B0-H0-SA-M4-AD0-APS")
    """
    r = 1 if c["use_retriever"] else 0
    d = 1 if c["use_risk_decompose"] else 0
    b = 1 if c["use_behavior_check"] else 0
    h = 1 if c["use_hitl_gate"] else 0
    s = c["synth_style"]
    m = c["max_steps"]
    ad = 1 if c.get("adaptive", False) else 0
    ap = "S" if c.get("adaptive_policy", "strict") == "strict" else "L"
    
    return f"R{r}-D{d}-B{b}-H{h}-S{s}-M{m}-AD{ad}-AP{ap}"


def validate_candidate(c: dict) -> None:
    """
    Validate candidate dictionary structure and values.
    
    Args:
        c: Candidate dictionary to validate
        
    Raises:
        ValueError: If validation fails with descriptive message
    """
    # Check that c is a dict
    if not isinstance(c, dict):
        raise ValueError(f"Candidate must be a dict, got {type(c)}")
    
    # Check keys
    c_keys = set(c.keys())
    expected_keys = set(CANDIDATE_KEYS)
    
    if c_keys != expected_keys:
        missing = expected_keys - c_keys
        extra = c_keys - expected_keys
        msg_parts = []
        if missing:
            msg_parts.append(f"missing keys: {missing}")
        if extra:
            msg_parts.append(f"extra keys: {extra}")
        raise ValueError(f"Invalid candidate keys: {', '.join(msg_parts)}")
    
    # Validate boolean flags
    for key in ["use_retriever", "use_risk_decompose", "use_behavior_check", "use_hitl_gate", "adaptive"]:
        if not isinstance(c[key], bool):
            raise ValueError(f"{key} must be bool, got {type(c[key])}")
    
    # Validate synth_style
    if c["synth_style"] not in ["A", "B"]:
        raise ValueError(f"synth_style must be 'A' or 'B', got {c['synth_style']}")
    
    # Validate adaptive_policy
    if c["adaptive_policy"] not in ["strict", "lenient"]:
        raise ValueError(f"adaptive_policy must be 'strict' or 'lenient', got {c['adaptive_policy']}")
    
    # Validate max_steps
    if not isinstance(c["max_steps"], int):
        raise ValueError(f"max_steps must be int, got {type(c['max_steps'])}")
    if c["max_steps"] < 1:
        raise ValueError(f"max_steps must be >= 1, got {c['max_steps']}")
