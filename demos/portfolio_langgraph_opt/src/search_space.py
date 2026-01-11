"""Search space definition for portfolio advisory LangGraph optimization.

This module supports both legacy candidate dictionaries and registry-driven agent combinations.
"""

from typing import Optional
import itertools

# Lazy imports to avoid circular dependencies
_registry_cache = None
_registry_dir = None


def set_registry_dir(registry_dir: Optional[str]):
    """
    Set the registry directory for all subsequent calls.
    Must be called before load_registry_cached().
    """
    global _registry_dir, _registry_cache
    _registry_dir = registry_dir
    _registry_cache = None  # Clear cache when changing directory


def load_registry_cached():
    """
    Load agent registry once and cache it.
    
    Returns:
        Dictionary mapping agent ID to AgentDef
    """
    global _registry_cache
    if _registry_cache is None:
        from demos.portfolio_langgraph_opt.src.agents import load_registry
        _registry_cache = load_registry(_registry_dir)
    return _registry_cache


CANDIDATE_KEYS = ["use_retriever", "use_risk_decompose", "use_behavior_check", "use_hitl_gate", 
                  "synth_style", "max_steps", "adaptive", "adaptive_policy", "carryover"]


def selected_agents_to_candidate(selected_agents: list[str], max_steps: int = 4) -> dict:
    """
    Convert a list of selected agent IDs to a candidate dictionary.
    
    Maps agent IDs to legacy candidate keys for backward compatibility:
    - retriever => use_retriever: True
    - risk_decompose => use_risk_decompose: True
    - behavior_check => use_behavior_check: True
    - hitl_gate => use_hitl_gate: True
    - synth_style_A => synth_style: "A"
    - synth_style_B => synth_style: "B"
    - carryover_none => carryover: "none"
    - carryover_compact => carryover: "compact"
    - carryover_full => carryover: "full"
    - adaptive_on => adaptive: True
    - adaptive_off => adaptive: False
    - adaptive_policy_strict => adaptive_policy: "strict"
    - adaptive_policy_lenient => adaptive_policy: "lenient"
    
    Args:
        selected_agents: List of agent IDs
        max_steps: Maximum execution steps (default: 4)
        
    Returns:
        Candidate dictionary with standard keys plus "selected_agents"
    """
    selected_set = set(selected_agents)
    
    # Initialize with defaults
    candidate = {
        "use_retriever": False,
        "use_risk_decompose": False,
        "use_behavior_check": False,
        "use_hitl_gate": False,
        "synth_style": "A",  # Default to A
        "max_steps": max_steps,
        "adaptive": False,  # Default to off
        "adaptive_policy": "strict",  # Default to strict
        "carryover": "compact",  # Default to compact
        "selected_agents": sorted(selected_agents)  # Non-breaking extra key for viz
    }
    
    # Map agent IDs to candidate flags
    if "retriever" in selected_set:
        candidate["use_retriever"] = True
    if "risk_decompose" in selected_set:
        candidate["use_risk_decompose"] = True
    if "behavior_check" in selected_set:
        candidate["use_behavior_check"] = True
    if "hitl_gate" in selected_set:
        candidate["use_hitl_gate"] = True
    
    # Synthesis style (one of)
    if "synth_style_A" in selected_set:
        candidate["synth_style"] = "A"
    elif "synth_style_B" in selected_set:
        candidate["synth_style"] = "B"
    
    # Carryover mode (one of)
    if "carryover_none" in selected_set:
        candidate["carryover"] = "none"
    elif "carryover_compact" in selected_set:
        candidate["carryover"] = "compact"
    elif "carryover_full" in selected_set:
        candidate["carryover"] = "full"
    
    # Adaptive mode (one of)
    if "adaptive_on" in selected_set:
        candidate["adaptive"] = True
    elif "adaptive_off" in selected_set:
        candidate["adaptive"] = False
    
    # Adaptive policy (one of, only matters if adaptive is on)
    if "adaptive_policy_strict" in selected_set:
        candidate["adaptive_policy"] = "strict"
    elif "adaptive_policy_lenient" in selected_set:
        candidate["adaptive_policy"] = "lenient"
    
    return candidate


def candidate_to_selected_agents(candidate: dict) -> list[str]:
    """
    Convert a candidate dictionary to a list of agent IDs.
    
    For backward compatibility with resume files that may have old candidates
    without the "selected_agents" key.
    
    Args:
        candidate: Candidate dictionary
        
    Returns:
        List of agent IDs
    """
    # If candidate already has selected_agents, return it
    if "selected_agents" in candidate:
        return candidate["selected_agents"]
    
    # Derive from legacy keys
    agents = []
    
    # Processing nodes
    if candidate.get("use_retriever", False):
        agents.append("retriever")
    if candidate.get("use_risk_decompose", False):
        agents.append("risk_decompose")
    if candidate.get("use_behavior_check", False):
        agents.append("behavior_check")
    if candidate.get("use_hitl_gate", False):
        agents.append("hitl_gate")
    
    # Synthesis style (exactly one required)
    synth_style = candidate.get("synth_style", "A")
    agents.append(f"synth_style_{synth_style}")
    
    # Carryover mode (exactly one required)
    carryover = candidate.get("carryover", "compact")
    agents.append(f"carryover_{carryover}")
    
    # Adaptive mode (exactly one required)
    adaptive = candidate.get("adaptive", False)
    agents.append("adaptive_on" if adaptive else "adaptive_off")
    
    # Adaptive policy (optional, only if adaptive is on)
    if adaptive:
        policy = candidate.get("adaptive_policy", "strict")
        agents.append(f"adaptive_policy_{policy}")
    
    return sorted(agents)


def default_candidate() -> dict:
    """Return a safe baseline candidate configuration."""
    baseline_agents = ["synth_style_A", "carryover_compact", "adaptive_off"]
    return selected_agents_to_candidate(baseline_agents, max_steps=4)


def all_candidates_small() -> list[dict]:
    """
    Generate a deterministic grid of candidate configurations using registry constraints.
    
    Uses agent combinations with constraint validation to ensure only valid configurations.
    
    Dimensions:
    - Optional nodes: retriever, risk_decompose, behavior_check, hitl_gate (16 combos)
    - Synthesis style: synth_style_A OR synth_style_B (2 options, exactly one)
    - Carryover: carryover_none OR carryover_compact (2 options, exactly one, excluding full for size)
    - Adaptive: adaptive_off OR adaptive_on (2 options, exactly one)
    - Adaptive policy: none OR adaptive_policy_strict (when adaptive_on)
    
    Expected count: 16 × 2 × 2 × 2 = 128 candidates (same as before)
    
    Returns:
        List of candidate dictionaries with selected_agents key
    """
    from demos.portfolio_langgraph_opt.src.agents import validate_combo
    
    registry = load_registry_cached()
    candidates = []
    
    # Optional processing nodes (all combinations)
    optional_nodes = ["retriever", "risk_decompose", "behavior_check", "hitl_gate"]
    
    # Required groups (one-of)
    synth_styles = ["synth_style_A", "synth_style_B"]
    carryover_modes = ["carryover_none", "carryover_compact"]  # Excluding full for size
    adaptive_modes = ["adaptive_off", "adaptive_on"]
    
    # Enumerate all combinations
    for node_combo in itertools.product([False, True], repeat=len(optional_nodes)):
        selected_optional = [node for node, include in zip(optional_nodes, node_combo) if include]
        
        for synth_style in synth_styles:
            for carryover in carryover_modes:
                for adaptive in adaptive_modes:
                    # Base agents: optional nodes + required groups
                    selected = selected_optional + [synth_style, carryover, adaptive]
                    
                    # If adaptive_on, always add adaptive_policy_strict (keeping it simple for small grid)
                    if adaptive == "adaptive_on":
                        selected.append("adaptive_policy_strict")
                    
                    # Validate combination
                    is_valid, errors = validate_combo(set(selected), registry)
                    if is_valid:
                        candidate = selected_agents_to_candidate(selected, max_steps=4)
                        candidates.append(candidate)
                    else:
                        # This shouldn't happen with our careful enumeration
                        # If it does, it means constraints are stricter than expected
                        pass
    
    # Note: Count should still be 128 as before since our constraints match the original logic
    # If count differs, it means constraints eliminated some invalid configurations
    return candidates


def all_candidates_full() -> list[dict]:
    """
    Generate full grid including all 3 carryover modes using registry constraints.
    
    Uses agent combinations with constraint validation to ensure only valid configurations.
    
    Dimensions:
    - Optional nodes: retriever, risk_decompose, behavior_check, hitl_gate (16 combos)
    - Synthesis style: synth_style_A OR synth_style_B (2 options, exactly one)
    - Carryover: carryover_none OR carryover_compact OR carryover_full (3 options, exactly one)
    - Adaptive: adaptive_off OR adaptive_on (2 options, exactly one)
    - Adaptive policy: none OR adaptive_policy_strict (when adaptive_on)
    
    Expected count: 16 × 2 × 3 × 2 = 192 candidates (same as before)
    
    Returns:
        List of candidate dictionaries with selected_agents key
    """
    from demos.portfolio_langgraph_opt.src.agents import validate_combo
    
    registry = load_registry_cached()
    candidates = []
    
    # Optional processing nodes (all combinations)
    optional_nodes = ["retriever", "risk_decompose", "behavior_check", "hitl_gate"]
    
    # Required groups (one-of)
    synth_styles = ["synth_style_A", "synth_style_B"]
    carryover_modes = ["carryover_none", "carryover_compact", "carryover_full"]  # All 3
    adaptive_modes = ["adaptive_off", "adaptive_on"]
    
    # Enumerate all combinations
    for node_combo in itertools.product([False, True], repeat=len(optional_nodes)):
        selected_optional = [node for node, include in zip(optional_nodes, node_combo) if include]
        
        for synth_style in synth_styles:
            for carryover in carryover_modes:
                for adaptive in adaptive_modes:
                    # Base agents: optional nodes + required groups
                    selected = selected_optional + [synth_style, carryover, adaptive]
                    
                    # If adaptive_on, always add adaptive_policy_strict (keeping it simple)
                    if adaptive == "adaptive_on":
                        selected.append("adaptive_policy_strict")
                    
                    # Validate combination
                    is_valid, errors = validate_combo(set(selected), registry)
                    if is_valid:
                        candidate = selected_agents_to_candidate(selected, max_steps=4)
                        candidates.append(candidate)
                    else:
                        # This shouldn't happen with our careful enumeration
                        pass
    
    # Note: Count should still be 192 as before
    return candidates


def candidate_to_name(c: dict) -> str:
    """
    Convert candidate dict to stable short name.
    
    Format: R{0/1}-D{0/1}-B{0/1}-H{0/1}-S{A/B}-M{max_steps}-AD{0/1}-AP{S/L}-CO{0/1/2}
    
    Args:
        c: Candidate dictionary
        
    Returns:
        Short name string (e.g., "R0-D0-B0-H0-SA-M4-AD0-APS-CO1")
    """
    r = 1 if c["use_retriever"] else 0
    d = 1 if c["use_risk_decompose"] else 0
    b = 1 if c["use_behavior_check"] else 0
    h = 1 if c["use_hitl_gate"] else 0
    s = c["synth_style"]
    m = c["max_steps"]
    ad = 1 if c.get("adaptive", False) else 0
    ap = "S" if c.get("adaptive_policy", "strict") == "strict" else "L"
    
    # Carryover encoding
    carryover_map = {"none": 0, "compact": 1, "full": 2}
    co = carryover_map.get(c.get("carryover", "compact"), 1)
    
    return f"R{r}-D{d}-B{b}-H{h}-S{s}-M{m}-AD{ad}-AP{ap}-CO{co}"


def validate_candidate(c: dict) -> None:
    """
    Validate candidate dictionary structure and values.
    
    Now accepts optional "selected_agents" key for registry-driven candidates.
    
    Args:
        c: Candidate dictionary to validate
        
    Raises:
        ValueError: If validation fails with descriptive message
    """
    # Check that c is a dict
    if not isinstance(c, dict):
        raise ValueError(f"Candidate must be a dict, got {type(c)}")
    
    # Check keys (allow optional "selected_agents" key)
    c_keys = set(c.keys())
    expected_keys = set(CANDIDATE_KEYS)
    optional_keys = {"selected_agents"}
    
    # Remove optional keys for validation
    c_keys_required = c_keys - optional_keys
    
    if c_keys_required != expected_keys:
        missing = expected_keys - c_keys_required
        extra = c_keys_required - expected_keys
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
    
    # Validate carryover
    if c["carryover"] not in ["none", "compact", "full"]:
        raise ValueError(f"carryover must be 'none', 'compact', or 'full', got {c['carryover']}")
    
    # Validate max_steps
    if not isinstance(c["max_steps"], int):
        raise ValueError(f"max_steps must be int, got {type(c['max_steps'])}")
    if c["max_steps"] < 1:
        raise ValueError(f"max_steps must be >= 1, got {c['max_steps']}")
    
    # Validate optional selected_agents if present
    if "selected_agents" in c:
        if not isinstance(c["selected_agents"], list):
            raise ValueError(f"selected_agents must be list, got {type(c['selected_agents'])}")
        if not all(isinstance(a, str) for a in c["selected_agents"]):
            raise ValueError("selected_agents must contain strings only")
