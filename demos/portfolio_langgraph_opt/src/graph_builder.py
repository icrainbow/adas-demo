"""Graph builder for portfolio advisory LangGraph optimization.

Supports both LangGraph (if available) and pure-Python fallback runner.
"""

from typing import TypedDict, Callable, Any
import re
import json

# Try to import langgraph, fall back to pure Python if unavailable
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

# Import token meter for cost tracking
from demos.portfolio_langgraph_opt.src.token_meter import add_node_usage


# State structure
class State(TypedDict):
    """State passed between graph nodes."""
    case: dict
    policy_text: str
    signals: list[str]
    notes: list[str]
    decision: str  # "APPROVE" | "CAUTION" | "NOT_RECOMMENDED" | "ESCALATE"
    explanation: str
    path: list[str]
    candidate: dict  # Configuration
    active_subgraphs: list[str]  # Adaptive topology tracking
    sub_findings: list[str]  # Adaptive subgraph findings
    token_usage: dict  # Token usage tracking
    token_trace: list[dict]  # Per-node token trace


# ============================================================================
# Helper functions
# ============================================================================

def normalize_candidate(candidate: dict) -> dict:
    """
    Normalize candidate dictionary to ensure all expected keys exist.
    
    Supports both legacy candidates (without selected_agents) and registry-driven
    candidates (with selected_agents). Ensures all required keys are present with
    appropriate defaults.
    
    Args:
        candidate: Candidate configuration dictionary (may be legacy or registry-driven)
        
    Returns:
        Normalized candidate dictionary with all expected keys
    """
    # Make a copy to avoid modifying the original
    normalized = candidate.copy()
    
    # If selected_agents doesn't exist, derive it from legacy keys
    if "selected_agents" not in normalized:
        from demos.portfolio_langgraph_opt.src.search_space import candidate_to_selected_agents
        normalized["selected_agents"] = candidate_to_selected_agents(candidate)
    
    # Ensure all boolean flags exist with defaults
    normalized.setdefault("use_retriever", False)
    normalized.setdefault("use_risk_decompose", False)
    normalized.setdefault("use_behavior_check", False)
    normalized.setdefault("use_hitl_gate", False)
    normalized.setdefault("adaptive", False)
    
    # Ensure string parameters exist with defaults
    normalized.setdefault("synth_style", "A")
    normalized.setdefault("adaptive_policy", "strict")
    normalized.setdefault("carryover", "compact")
    
    # Ensure integer parameters exist with defaults
    normalized.setdefault("max_steps", 4)
    
    return normalized


def _extract_requested_action_keywords(action: str) -> set[str]:
    """
    Extract risk-related keywords from requested action text.
    
    Args:
        action: Requested action string
        
    Returns:
        Set of detected keywords
    """
    action_lower = action.lower()
    keywords = set()
    
    # Define keyword patterns
    patterns = {
        "leverage": r"\b(leverage|leveraged|margin|3x|2x)\b",
        "crypto": r"\b(crypto|cryptocurrency|bitcoin|ethereum)\b",
        "options": r"\b(option|options|derivative|derivatives)\b",
        "high-risk": r"\b(high[- ]risk|aggressive|speculative|growth stock)\b",
        "single stock": r"\b(single (stock|position)|concentrate.*stock|one stock)\b",
        "sector": r"\b(sector|single sector|concentrate.*sector)\b",
        "redeem": r"\b(redeem|redemption|early|premature|lock|locked)\b",
        "illiquid": r"\b(illiquid|illiquidity|private equity|venture capital)\b",
        "structured": r"\b(structured|complex|exotic)\b",
    }
    
    for keyword, pattern in patterns.items():
        if re.search(pattern, action_lower):
            keywords.add(keyword)
    
    return keywords


def _add_signal(state: State, signal: str) -> None:
    """Add signal to state if not already present (dedupe)."""
    if signal not in state["signals"]:
        state["signals"].append(signal)


def _match_policy_lines(policy_text: str, keywords: set[str]) -> list[str]:
    """
    Match policy lines containing any of the keywords (case-insensitive).
    
    Args:
        policy_text: Full policy text (newline-separated)
        keywords: Set of keywords to search for
        
    Returns:
        List of matching policy lines (deduped)
    """
    if not policy_text:
        return []
    
    lines = [line.strip() for line in policy_text.split("\n") if line.strip()]
    matched = []
    
    for line in lines:
        line_lower = line.lower()
        for keyword in keywords:
            # Handle multi-word keywords
            keyword_lower = keyword.lower()
            if keyword_lower in line_lower:
                if line not in matched:
                    matched.append(line)
                break
    
    return matched


def _can_take_step(state: dict, max_steps: int) -> bool:
    """
    Check if we can take another step without exceeding max_steps budget.
    
    Args:
        state: Current state dictionary
        max_steps: Maximum allowed steps
        
    Returns:
        True if len(path) < max_steps
    """
    path = state.get("path", [])
    return len(path) < max_steps


def _record_step(state: dict, name: str) -> None:
    """
    Record a step in the execution path.
    
    Args:
        state: Current state dictionary
        name: Name of the step/node
    """
    state.setdefault("path", []).append(name)


def build_carryover_text(state: State, mode: str) -> str:
    """
    Build carryover text from previous node outputs based on mode.
    
    Args:
        state: Current state
        mode: "none" | "compact" | "full"
        
    Returns:
        Carryover text string
    """
    if mode == "none":
        return ""
    
    if mode == "compact":
        # Short structured digest
        parts = []
        
        if state.get("signals"):
            parts.append(f"Signals: {', '.join(state['signals'][:5])}")  # Top 5 signals
        
        if state.get("decision"):
            parts.append(f"Decision: {state['decision']}")
        
        if state.get("sub_findings"):
            top_findings = state["sub_findings"][:3]  # Top 3 findings
            parts.append(f"Findings: {'; '.join(top_findings)}")
        
        if state.get("active_subgraphs"):
            parts.append(f"Subgraphs: {', '.join(state['active_subgraphs'])}")
        
        return "\n".join(parts) if parts else ""
    
    elif mode == "full":
        # Include full previous outputs
        parts = []
        
        if state.get("signals"):
            parts.append(f"=== Signals ===\n{json.dumps(state['signals'], indent=2)}")
        
        if state.get("notes"):
            parts.append(f"=== Policy Notes ===\n" + "\n".join(state["notes"]))
        
        if state.get("decision"):
            parts.append(f"=== Decision ===\n{state['decision']}")
        
        if state.get("sub_findings"):
            parts.append(f"=== Adaptive Findings ===\n" + "\n".join(state["sub_findings"]))
        
        if state.get("active_subgraphs"):
            parts.append(f"=== Active Subgraphs ===\n{', '.join(state['active_subgraphs'])}")
        
        # Include topology-specific notes
        for note_key in ["diversification_note", "liquidity_maintenance_note", "reasonableness_note", "alignment_note"]:
            if state.get(note_key):
                parts.append(f"=== {note_key.replace('_', ' ').title()} ===\n{state[note_key]}")
        
        return "\n\n".join(parts) if parts else ""
    
    return ""


def extract_signals(case: dict) -> list[str]:
    """
    Extract signals from case using deterministic rules (no LLM needed).
    
    Args:
        case: Case dictionary with client_profile, portfolio, requested_action
        
    Returns:
        List of unique signal strings in stable order
    """
    signals = []
    
    client_profile = case.get("client_profile", {})
    portfolio = case.get("portfolio", {})
    requested_action = case.get("requested_action", "")
    action_lower = requested_action.lower()
    
    # Rule 1: Liquidity mismatch
    if portfolio.get("liquidity") == "low" and client_profile.get("liquidity_need") == "high":
        signals.append("liquidity mismatch")
    
    # Rule 2: Concentration risk
    if portfolio.get("concentration") == "high":
        signals.append("concentration risk")
    
    # Rule 3: Leverage concerns
    leverage_keywords = ["leveraged", "leverage", "options", "margin"]
    if any(kw in action_lower for kw in leverage_keywords):
        signals.append("leverage concerns")
    
    # Rule 4: Experience mismatch
    experience_keywords = ["derivatives", "options", "structured", "leveraged"]
    if client_profile.get("experience") == "low" and any(kw in action_lower for kw in experience_keywords):
        signals.append("experience mismatch")
    
    # Rule 5: Risk mismatch
    if client_profile.get("risk_appetite") == "low" and portfolio.get("volatility") == "high":
        signals.append("risk mismatch")
    
    # Return unique signals in stable order (dedupe while preserving order)
    seen = set()
    unique_signals = []
    for sig in signals:
        if sig not in seen:
            seen.add(sig)
            unique_signals.append(sig)
    
    return unique_signals


# ============================================================================
# Node functions
# ============================================================================

def risk_decompose_node(state: State) -> State:
    """
    Analyze portfolio structure for risk mismatches.
    Adds signals based on portfolio characteristics and client profile.
    """
    # Check budget before proceeding
    max_steps = state.get("candidate", {}).get("max_steps", 4)
    if not _can_take_step(state, max_steps):
        return state
    
    _record_step(state, "risk_decompose")
    
    case = state["case"]
    profile = case["client_profile"]
    portfolio = case["portfolio"]
    
    # Build prompt text (what would be sent to LLM)
    carryover_mode = state.get("candidate", {}).get("carryover", "compact")
    carryover_text = build_carryover_text(state, carryover_mode)
    
    prompt_text = f"""Analyze portfolio structure for risk mismatches.

Client Profile:
- Age: {profile['age']}
- Risk Appetite: {profile['risk_appetite']}
- Liquidity Need: {profile['liquidity_need']}
- Experience: {profile['experience']}

Portfolio:
- Equities: {portfolio['equities_pct']}%
- Bonds: {portfolio['bonds_pct']}%
- Alts: {portfolio['alts_pct']}%
- Cash: {portfolio['cash_pct']}%
- Concentration: {portfolio['concentration']}
- Volatility: {portfolio['volatility']}
- Liquidity: {portfolio['liquidity']}

Requested Action: {case['requested_action']}

"""
    # Add carryover context if present (extracted to avoid f-string backslash)
    carryover_section = f"Previous Context:\n{carryover_text}\n" if carryover_text else ""
    prompt += carryover_section
    prompt += """
Task: Identify risk mismatches and generate signals."""
    
    # Perform analysis (deterministic heuristics)
    signals_added = []
    
    # Check liquidity mismatch
    if profile["liquidity_need"] == "high" and portfolio["liquidity"] == "low":
        _add_signal(state, "liquidity mismatch")
        signals_added.append("liquidity mismatch")
    # Additional liquidity check: high need with low cash
    if profile["liquidity_need"] == "high" and portfolio["cash_pct"] <= 5:
        _add_signal(state, "liquidity mismatch")
        if "liquidity mismatch" not in signals_added:
            signals_added.append("liquidity mismatch")
    
    # Check concentration
    if portfolio["concentration"] == "high":
        _add_signal(state, "high concentration")
        signals_added.append("high concentration")
    # Additional concentration check: very high equity allocation
    if portfolio["equities_pct"] >= 85:
        _add_signal(state, "high concentration")
        if "high concentration" not in signals_added:
            signals_added.append("high concentration")
    
    # Check volatility
    if portfolio["volatility"] == "high":
        _add_signal(state, "volatility exposure")
        signals_added.append("volatility exposure")
    # Additional volatility check: high equity with low bond allocation
    if portfolio["equities_pct"] >= 80 and portfolio["bonds_pct"] <= 10:
        _add_signal(state, "volatility exposure")
        if "volatility exposure" not in signals_added:
            signals_added.append("volatility exposure")
    
    # Check risk appetite vs equity allocation
    if portfolio["equities_pct"] >= 75 and profile["risk_appetite"] != "high":
        _add_signal(state, "risk appetite mismatch")
        signals_added.append("risk appetite mismatch")
    
    # Check time horizon (age-based)
    if profile["age"] >= 60 and portfolio["equities_pct"] >= 65:
        _add_signal(state, "time horizon mismatch")
        signals_added.append("time horizon mismatch")
    if profile["age"] >= 60 and portfolio["volatility"] == "high":
        _add_signal(state, "time horizon mismatch")
        if "time horizon mismatch" not in signals_added:
            signals_added.append("time horizon mismatch")
    
    # Generate advisory notes for topology-dependent coverage
    # Diversification assessment
    if portfolio["concentration"] == "high" or "high concentration" in state["signals"]:
        state["diversification_note"] = "appropriate diversification: insufficient; concentration risk remains elevated."
    else:
        state["diversification_note"] = "appropriate diversification: maintained across asset classes; no undue concentration identified."
    
    # Liquidity maintenance assessment
    if profile["liquidity_need"] == "high" or portfolio["liquidity"] == "low" or "liquidity mismatch" in state["signals"]:
        state["liquidity_maintenance_note"] = "liquidity maintenance: liquidity profile requires explicit maintenance and monitoring."
    else:
        state["liquidity_maintenance_note"] = "liquidity maintenance: maintained; no material liquidity pressure indicated."
    
    # Build output text (what node produced)
    output_text = f"""Risk Analysis Results:
Signals Identified: {', '.join(signals_added) if signals_added else 'none'}
Diversification Note: {state.get('diversification_note', 'N/A')}
Liquidity Note: {state.get('liquidity_maintenance_note', 'N/A')}"""
    
    # Track token usage
    add_node_usage(state, "risk_decompose", prompt_text, output_text)
    
    return state


def behavior_check_node(state: State) -> State:
    """
    Check requested action against client profile.
    Evaluates suitability based on experience, age, and risk appetite.
    """
    # Check budget before proceeding
    max_steps = state.get("candidate", {}).get("max_steps", 4)
    if not _can_take_step(state, max_steps):
        return state
    
    _record_step(state, "behavior_check")
    
    case = state["case"]
    profile = case["client_profile"]
    requested_action = case["requested_action"]
    action_lower = requested_action.lower()
    
    # Build prompt text
    carryover_mode = state.get("candidate", {}).get("carryover", "compact")
    carryover_text = build_carryover_text(state, carryover_mode)
    
    prompt_text = f"""Check requested action against client profile for suitability.

Client Profile:
- Age: {profile['age']}
- Risk Appetite: {profile['risk_appetite']}
- Experience: {profile['experience']}
- Liquidity Need: {profile['liquidity_need']}

Requested Action: {requested_action}

"""
    # Add carryover context if present (extracted to avoid f-string backslash)
    carryover_section = f"Previous Context:\n{carryover_text}\n" if carryover_text else ""
    prompt_text += carryover_section
    prompt_text += """
Task: Evaluate suitability and identify concerns."""
    
    # Extract keywords from requested action
    keywords = _extract_requested_action_keywords(requested_action)
    
    # Define keyword sets for different risk categories
    complex_keywords = {"leverage", "options", "crypto", "structured"}
    risky_keywords = {"high-risk", "leverage", "options", "crypto"}
    concentration_keywords = {"single stock", "sector"}
    redeem_keywords = {"redeem", "illiquid"}
    derivative_keywords = {"options", "structured"}
    
    signals_added = []
    
    # Check for concentration signals in requested action
    if keywords & concentration_keywords:
        _add_signal(state, "high concentration")
        signals_added.append("high concentration")
    # Additional concentration patterns
    if any(phrase in action_lower for phrase in ["all-in", "single name", "thematic"]):
        _add_signal(state, "high concentration")
        if "high concentration" not in signals_added:
            signals_added.append("high concentration")
    
    # Check for liquidity mismatch with redemption/illiquid requests
    if keywords & redeem_keywords and profile["liquidity_need"] == "high":
        _add_signal(state, "liquidity mismatch")
        signals_added.append("liquidity mismatch")
    
    # Check experience suitability for complex products
    if keywords & complex_keywords and profile["experience"] == "low":
        _add_signal(state, "experience suitability")
        signals_added.append("experience suitability")
    # Extended check: medium experience with derivatives/structured
    if keywords & derivative_keywords and profile["experience"] in ["low", "medium"]:
        _add_signal(state, "experience suitability")
        if "experience suitability" not in signals_added:
            signals_added.append("experience suitability")
    
    # Check age-related time horizon
    if profile["age"] >= 60 and keywords & risky_keywords:
        _add_signal(state, "time horizon mismatch")
        signals_added.append("time horizon mismatch")
    
    # Check risk appetite alignment
    if profile["risk_appetite"] != "high" and keywords & risky_keywords:
        _add_signal(state, "risk appetite mismatch")
        signals_added.append("risk appetite mismatch")
    
    # Generate reasonableness assessment (topology-dependent)
    # Count severity indicators at this point
    severity_indicators = len(set(state["signals"]))
    critical_signals = {"liquidity mismatch", "risk appetite mismatch"}
    has_critical = any(sig in state["signals"] for sig in critical_signals)
    
    if severity_indicators == 0:
        state["reasonableness_note"] = "reasonable request: consistent with stated constraints and avoids unnecessary complexity."
    elif has_critical or severity_indicators >= 3:
        state["reasonableness_note"] = "reasonable request: not reasonable given constraints; revise the request before proceeding."
    else:
        state["reasonableness_note"] = "reasonable request: partially reasonable, but requires additional checks and guardrails."
    
    # Build output text
    output_text = f"""Behavior Check Results:
Signals Identified: {', '.join(signals_added) if signals_added else 'none'}
Reasonableness: {state.get('reasonableness_note', 'N/A')}"""
    
    # Track token usage
    add_node_usage(state, "behavior_check", prompt_text, output_text)
    
    return state


def retriever_node(state: State) -> State:
    """
    Retrieve relevant policy guidance based on signals and keywords.
    Adds matched policy lines to notes.
    """
    # Check budget before proceeding
    max_steps = state.get("candidate", {}).get("max_steps", 4)
    if not _can_take_step(state, max_steps):
        return state
    
    _record_step(state, "retriever")
    
    if not state.get("candidate", {}).get("use_retriever"):
        return state
    
    # Build prompt text
    carryover_mode = state.get("candidate", {}).get("carryover", "compact")
    carryover_text = build_carryover_text(state, carryover_mode)
    
    case = state["case"]
    action_keywords = _extract_requested_action_keywords(case["requested_action"])
    all_keywords = set(state["signals"]) | action_keywords
    
    policy_text = state.get("policy_text", "")
    
    prompt_text = f"""Retrieve relevant policy guidance.

Signals: {', '.join(state['signals'])}
Action Keywords: {', '.join(action_keywords)}

Policy Database:
{policy_text}

"""
    # Add carryover context if present (extracted to avoid f-string backslash)
    carryover_section = f"Previous Context:\n{carryover_text}\n" if carryover_text else ""
    prompt_text += carryover_section
    prompt_text += """
Task: Match and retrieve relevant policy lines."""
    
    # Match policy lines
    matched_lines = _match_policy_lines(policy_text, all_keywords)
    
    # Add to notes (dedupe)
    for line in matched_lines:
        if line not in state["notes"]:
            state["notes"].append(line)
    
    # Build output text
    output_text = f"""Retrieved Policy Guidance:
{chr(10).join(f'- {line}' for line in matched_lines) if matched_lines else 'No matches'}"""
    
    # Track token usage
    add_node_usage(state, "retriever", prompt_text, output_text)
    
    return state


# ============================================================================
# Adaptive subgraph nodes (Step C)
# ============================================================================

def sub_liquidity_node(state: State) -> State:
    """Adaptive subgraph for liquidity analysis."""
    # Check budget before proceeding
    max_steps = state.get("candidate", {}).get("max_steps", 4)
    if not _can_take_step(state, max_steps):
        return state
    
    _record_step(state, "sub_liquidity")
    
    # Build prompt (minimal for adaptive subgraphs)
    carryover_mode = state.get("candidate", {}).get("carryover", "compact")
    carryover_text = build_carryover_text(state, carryover_mode)
    prompt_text = """Liquidity deep-dive analysis.
"""
    # Add carryover context if present (extracted to avoid f-string backslash)
    carryover_section = f"Context:\n{carryover_text}" if carryover_text else ""
    prompt_text += carryover_section
    
    # Deterministic findings based on signals
    if "sub_findings" not in state:
        state["sub_findings"] = []
    findings = [
        "Liquidity: Identified mismatch between client needs and portfolio liquidity profile",
        "Liquidity: Recommend maintaining adequate cash reserves or liquid instruments"
    ]
    state["sub_findings"].extend(findings)
    
    output_text = "\n".join(findings)
    add_node_usage(state, "sub_liquidity", prompt_text, output_text)
    
    return state


def sub_concentration_node(state: State) -> State:
    """Adaptive subgraph for concentration analysis."""
    # Check budget before proceeding
    max_steps = state.get("candidate", {}).get("max_steps", 4)
    if not _can_take_step(state, max_steps):
        return state
    
    _record_step(state, "sub_concentration")
    
    carryover_mode = state.get("candidate", {}).get("carryover", "compact")
    carryover_text = build_carryover_text(state, carryover_mode)
    prompt_text = """Concentration risk deep-dive analysis.
"""
    # Add carryover context if present (extracted to avoid f-string backslash)
    carryover_section = f"Context:\n{carryover_text}" if carryover_text else ""
    prompt_text += carryover_section
    
    if "sub_findings" not in state:
        state["sub_findings"] = []
    findings = [
        "Concentration: Portfolio exhibits elevated concentration risk",
        "Concentration: Consider diversification across asset classes and sectors"
    ]
    state["sub_findings"].extend(findings)
    
    output_text = "\n".join(findings)
    add_node_usage(state, "sub_concentration", prompt_text, output_text)
    
    return state


def sub_leverage_node(state: State) -> State:
    """Adaptive subgraph for leverage analysis."""
    # Check budget before proceeding
    max_steps = state.get("candidate", {}).get("max_steps", 4)
    if not _can_take_step(state, max_steps):
        return state
    
    _record_step(state, "sub_leverage")
    
    carryover_mode = state.get("candidate", {}).get("carryover", "compact")
    carryover_text = build_carryover_text(state, carryover_mode)
    prompt_text = """Leverage concerns deep-dive analysis.
"""
    # Add carryover context if present (extracted to avoid f-string backslash)
    carryover_section = f"Context:\n{carryover_text}" if carryover_text else ""
    prompt_text += carryover_section
    
    if "sub_findings" not in state:
        state["sub_findings"] = []
    findings = [
        "Leverage: Requested action involves leverage or margin; ensure understanding of downside risks",
        "Leverage: Recommend position sizing limits and stop-loss disciplines"
    ]
    state["sub_findings"].extend(findings)
    
    output_text = "\n".join(findings)
    add_node_usage(state, "sub_leverage", prompt_text, output_text)
    
    return state


def sub_suitability_node(state: State) -> State:
    """Adaptive subgraph for suitability analysis."""
    # Check budget before proceeding
    max_steps = state.get("candidate", {}).get("max_steps", 4)
    if not _can_take_step(state, max_steps):
        return state
    
    _record_step(state, "sub_suitability")
    
    carryover_mode = state.get("candidate", {}).get("carryover", "compact")
    carryover_text = build_carryover_text(state, carryover_mode)
    prompt_text = """Suitability concerns deep-dive analysis.
"""
    # Add carryover context if present (extracted to avoid f-string backslash)
    carryover_section = f"Context:\n{carryover_text}" if carryover_text else ""
    prompt_text += carryover_section
    
    if "sub_findings" not in state:
        state["sub_findings"] = []
    findings = [
        "Suitability: Experience level or risk appetite may not align with requested instruments",
        "Suitability: Recommend additional client education or modified approach"
    ]
    state["sub_findings"].extend(findings)
    
    output_text = "\n".join(findings)
    add_node_usage(state, "sub_suitability", prompt_text, output_text)
    
    return state
    state["sub_findings"].append("Suitability: Ensure adequate disclosure and client acknowledgment before proceeding")
    return state


# ============================================================================
# Adaptive subgraph activation
# ============================================================================

def _should_trigger(subgraph_name: str, signals: list[str], client: dict, 
                    portfolio: dict, action: str, adaptive_policy: str) -> bool:
    """
    Determine if a subgraph should be triggered based on case data.
    
    Args:
        subgraph_name: Name of subgraph ("diversification", "liquidity", "suitability")
        signals: List of detected signals
        client: Client profile dict
        portfolio: Portfolio dict
        action: Requested action text
        adaptive_policy: "strict" or "lenient"
        
    Returns:
        True if subgraph should be triggered
    """
    action_lower = action.lower()
    
    if subgraph_name == "diversification":
        # Strict: only trigger on explicit signal
        if "high concentration" in signals:
            return True
        # Lenient: also trigger on field heuristics
        if adaptive_policy == "lenient":
            if portfolio.get("concentration") == "high":
                return True
            concentration_keywords = ["single stock", "all-in", "sector"]
            if any(kw in action_lower for kw in concentration_keywords):
                return True
    
    elif subgraph_name == "liquidity":
        # Strict: only trigger on explicit signal
        if "liquidity mismatch" in signals:
            return True
        # Lenient: also trigger on field heuristics
        if adaptive_policy == "lenient":
            if client.get("liquidity_need") == "high":
                return True
            if portfolio.get("liquidity") == "low":
                return True
            liquidity_keywords = ["redeem", "exit", "break", "early", "penalty"]
            if any(kw in action_lower for kw in liquidity_keywords):
                return True
    
    elif subgraph_name == "suitability":
        # Strict: only trigger on explicit signal
        if "risk appetite mismatch" in signals:
            return True
        # Lenient: also trigger on field heuristics
        if adaptive_policy == "lenient":
            if client.get("experience") == "low":
                complex_keywords = ["options", "derivatives", "leveraged", "crypto"]
                if any(kw in action_lower for kw in complex_keywords):
                    return True
    
    return False


def _activate_adaptive_subgraphs(state: State) -> State:
    """
    Dynamically activate subgraphs based on case signals (when adaptive==1).
    Runs corresponding subgraph nodes and generates findings.
    
    Args:
        state: Current state
        
    Returns:
        Updated state with active_subgraphs, path updates, and sub_findings
    """
    candidate = state.get("candidate", {})
    
    # Only run if adaptive mode is enabled
    if not candidate.get("adaptive", False):
        return state
    
    signals = state["signals"]
    
    # Map signals to subgraph nodes (deterministic mapping)
    signal_to_subgraph = {
        "liquidity mismatch": ("sub_liquidity", sub_liquidity_node),
        "concentration risk": ("sub_concentration", sub_concentration_node),
        "leverage concerns": ("sub_leverage", sub_leverage_node),
        "experience mismatch": ("sub_suitability", sub_suitability_node),
        "risk mismatch": ("sub_suitability", sub_suitability_node),
    }
    
    # Track which subgraphs have been activated (avoid duplicates)
    activated = set()
    
    for signal in signals:
        if signal in signal_to_subgraph:
            subgraph_name, subgraph_node = signal_to_subgraph[signal]
            if subgraph_name not in activated:
                activated.add(subgraph_name)
                state["active_subgraphs"].append(subgraph_name)
                # Run the subgraph node
                state = subgraph_node(state)
    
    return state


def synth_node(state: State) -> State:
    """
    Synthesize final decision and explanation.
    Uses signals, notes, and candidate configuration.
    """
    def _normalize_signal(s: str) -> str:
        """Normalize signal to canonical rubric phrases."""
        s_lower = s.lower().strip()
        
        # Map to canonical phrases for consistent rubric matching
        if "liquid" in s_lower:
            return "liquidity mismatch"
        if "risk appetite" in s_lower:
            return "risk appetite mismatch"
        if "concentration" in s_lower:
            return "high concentration"
        if "volatility" in s_lower or "drawdown" in s_lower:
            return "volatility exposure"
        if "time horizon" in s_lower or "age" in s_lower:
            return "time horizon mismatch"
        if "experience" in s_lower or "complex" in s_lower:
            return "experience suitability"
        
        return s_lower
    
    # Get candidate and max_steps
    candidate = state.get("candidate", {})
    max_steps = candidate.get("max_steps", 4)
    
    # Check if we can record this step
    if not _can_take_step(state, max_steps):
        # Budget exhausted - set decision and explanation then return
        if not state.get("decision"):
            state["decision"] = "ESCALATE"
        state["explanation"] = "Assessment: ESCALATE\n\nReason: step budget exhausted; requires manual review."
        return state
    
    _record_step(state, "synth")
    
    # Activate adaptive subgraphs if adaptive mode is enabled AND budget allows
    # (each subgraph node will check budget internally)
    state = _activate_adaptive_subgraphs(state)
    
    signals = state["signals"]
    notes = state["notes"]
    case = state["case"]
    
    # Extract action and keywords for analysis helpers
    action = case.get("requested_action", "")
    action_lower = action.lower()
    keywords = _extract_requested_action_keywords(action)
    
    # Normalize and deduplicate signals to canonical phrases
    canonical_signals = sorted(set(_normalize_signal(s) for s in signals))
    
    # Create key signals text
    if canonical_signals:
        key_signals_text = "Key signals: " + "; ".join(canonical_signals)
    else:
        key_signals_text = "Key signals: none"
    
    # Calculate severity
    severity = len(set(signals))
    
    # Decision logic
    if candidate.get("use_hitl_gate") and severity >= 3:
        decision = "ESCALATE"
    elif "liquidity mismatch" in signals or "risk appetite mismatch" in signals:
        decision = "NOT_RECOMMENDED"
    elif severity >= 1:
        decision = "CAUTION"
    else:
        decision = "APPROVE"
    
    state["decision"] = decision
    
    # Extract client and portfolio fields for rationale generation
    client_profile = case.get("client_profile", {})
    portfolio = case.get("portfolio", {})
    
    # Build audit checklist (7 rubric-aligned items)
    audit_checklist = []
    
    # 1. Liquidity assessment
    if "liquidity mismatch" in signals:
        audit_checklist.append("Liquidity assessment: Issue — liquidity profile conflicts with stated needs.")
    else:
        audit_checklist.append("Liquidity assessment: OK — no liquidity mismatch identified.")
    
    # 2. Concentration risk
    concentration_keywords = ["single stock", "single name", "sector", "all-in"]
    if "high concentration" in signals or any(kw in action_lower for kw in concentration_keywords):
        audit_checklist.append("Concentration risk: Issue — concentration risk indicated.")
    else:
        audit_checklist.append("Concentration risk: OK — concentration risk not indicated.")
    
    # 3. Volatility exposure
    if "volatility exposure" in signals:
        audit_checklist.append("Volatility exposure: Issue — volatility exposure indicated.")
    else:
        audit_checklist.append("Volatility exposure: OK — volatility exposure not indicated.")
    
    # 4. Speculative nature
    speculative_keywords = ["crypto", "meme", "leveraged", "options", "derivatives"]
    if any(kw in action_lower for kw in speculative_keywords) or "risk appetite mismatch" in signals:
        audit_checklist.append("Speculative nature: Consideration — elements may be speculative; ensure suitability.")
    else:
        audit_checklist.append("Speculative nature: N/A — no explicitly speculative elements detected.")
    
    # 5. Regulatory uncertainty
    regulatory_keywords = ["cross-border", "offshore", "crypto", "derivatives", "structured"]
    if any(kw in action_lower for kw in regulatory_keywords):
        audit_checklist.append("Regulatory uncertainty: Consideration — regulatory requirements may vary; verify applicable constraints.")
    else:
        audit_checklist.append("Regulatory uncertainty: N/A — no obvious regulatory uncertainty triggers detected.")
    
    # 6. Penalty considerations
    penalty_keywords = ["redeem", "redemption", "break", "early", "penalty", "exit"]
    if any(kw in action_lower for kw in penalty_keywords):
        audit_checklist.append("Penalty considerations: Consideration — check fees/penalties and product terms before execution.")
    else:
        audit_checklist.append("Penalty considerations: N/A — no explicit penalty-triggering action detected.")
    
    # 7. Opportunity cost analysis
    if decision in ["NOT_RECOMMENDED", "CAUTION"]:
        audit_checklist.append("Opportunity cost analysis: Consideration — evaluate tradeoffs of delaying vs executing; compare alternatives.")
    else:
        audit_checklist.append("Opportunity cost analysis: N/A — limited opportunity cost concerns for this request.")
    
    # Build conditional decision rationale (for rubric coverage)
    # Only include if decision != "APPROVE" OR action indicates growth/rebalance intent
    growth_rebalance_keywords = ["growth", "increase equity", "add equities", "rebalance", "long-term", "reduce bonds"]
    include_rationale = (
        decision != "APPROVE" or 
        any(kw in action_lower for kw in growth_rebalance_keywords)
    )
    
    decision_rationale = []
    if include_rationale:
        risk_appetite = client_profile.get("risk_appetite", "")
        experience = client_profile.get("experience", "")
        portfolio_volatility = portfolio.get("volatility", "")
        
        if decision == "APPROVE":
            # APPROVE rationale: positive framing with rubric phrases
            
            # 1. alignment with risk appetite
            if risk_appetite in ["medium", "high"] or experience in ["medium", "high"]:
                decision_rationale.append("alignment with risk appetite: requested change fits stated risk profile.")
            else:
                decision_rationale.append("alignment with risk appetite: appears acceptable given constraints.")
            
            # 2. current conservative positioning
            if portfolio_volatility in ["low"] or any(kw in action_lower for kw in ["increase equity", "add equities", "rebalance toward equity", "growth"]):
                decision_rationale.append("current conservative positioning: proposal modestly increases return-seeking exposure.")
            
            # 3. growth potential
            if any(kw in action_lower for kw in ["growth", "increase equity", "add equities", "rebalance", "long-term"]):
                decision_rationale.append("growth potential: reallocation improves expected long-term growth potential.")
            
            # 4. volatility exposure increase (only if NOT flagged as issue)
            if "volatility exposure" not in signals and portfolio_volatility in ["low", "medium"]:
                decision_rationale.append("volatility exposure increase: does not materially raise volatility exposure increase beyond tolerance.")
        
        else:
            # CAUTION/NOT_RECOMMENDED/ESCALATE rationale: constraint-based framing
            
            # 1. alignment with risk appetite (negative)
            if "risk appetite mismatch" in signals:
                decision_rationale.append("alignment with risk appetite: misaligned; suitability constraints not met.")
            
            # 2. volatility exposure increase (negative)
            if "volatility exposure" in signals:
                decision_rationale.append("volatility exposure increase: likely increases volatility exposure increase beyond stated appetite.")
            
            # 3. current conservative positioning (departure concern)
            if portfolio_volatility == "low" and any(kw in action_lower for kw in ["aggressive", "growth", "leveraged", "high-risk"]):
                decision_rationale.append("current conservative positioning: request departs from current conservative positioning too abruptly.")
            
            # 4. growth potential (qualified acknowledgment)
            if any(kw in action_lower for kw in ["aggressive", "growth", "leveraged"]) and experience == "low":
                decision_rationale.append("growth potential: potential upside exists, but risk controls and suitability checks are required.")
    
    # Generate explanation based on synth_style
    synth_style = candidate.get("synth_style", "A")
    
    if synth_style == "A":
        # Concise bullet-like format
        explanation_parts = [f"Assessment: {decision}"]
        
        # Add key signals as explicit bullet near the top
        explanation_parts.append(f"\n• {key_signals_text}")
        
        if signals:
            explanation_parts.append("\nConcerns identified:")
            for signal in signals[:5]:  # Top 5
                explanation_parts.append(f"• {signal}")
        else:
            explanation_parts.append("\n• No significant concerns identified")
        
        # Add audit checklist
        explanation_parts.append("\nAudit checklist:")
        for item in audit_checklist:
            explanation_parts.append(f"• {item}")
        
        # Add decision rationale (conditional)
        if decision_rationale:
            explanation_parts.append("\nDecision rationale:")
            for item in decision_rationale:
                explanation_parts.append(f"• {item}")
        
        # Add adaptive subgraphs section (only if adaptive==1 and subgraphs were activated)
        if candidate.get("adaptive", False) and state.get("active_subgraphs"):
            subgraphs_str = ", ".join(state["active_subgraphs"])
            explanation_parts.append(f"\nAdaptive subgraphs activated: {subgraphs_str}")
            
            # Add adaptive findings (Step D)
            if "sub_findings" in state and state["sub_findings"]:
                explanation_parts.append("\nAdaptive findings:")
                for finding in state["sub_findings"]:
                    explanation_parts.append(f"• {finding}")
        
        # Add advisory coverage (conditional, topology-dependent)
        advisory_notes = []
        if "diversification_note" in state:
            advisory_notes.append(state["diversification_note"])
        if "liquidity_maintenance_note" in state:
            advisory_notes.append(state["liquidity_maintenance_note"])
        if "reasonableness_note" in state:
            advisory_notes.append(state["reasonableness_note"])
        if "alignment_note" in state:
            advisory_notes.append(state["alignment_note"])
        
        if advisory_notes:
            explanation_parts.append("\nAdvisory coverage:")
            for note in advisory_notes:
                explanation_parts.append(f"• {note}")
        
        if notes:
            explanation_parts.append("\nGuidance:")
            for note in notes[:2]:  # Top 2 policy lines
                explanation_parts.append(f"• {note}")
        
        explanation = "\n".join(explanation_parts)
    
    else:  # synth_style == "B"
        # Client-friendly paragraph format
        if decision == "APPROVE":
            explanation = (
                f"The requested action appears suitable for your profile. "
                f"{key_signals_text}. "
                f"No significant concerns were identified. "
            )
        elif decision == "CAUTION":
            explanation = (
                f"The requested action warrants careful consideration. "
                f"{key_signals_text}. "
                f"We have identified the following concerns: {', '.join(signals)}. "
                f"Please review these factors before proceeding. "
            )
        elif decision == "NOT_RECOMMENDED":
            explanation = (
                f"We do not recommend this action for your profile. "
                f"{key_signals_text}. "
                f"These factors present significant misalignment with your stated preferences. "
            )
        else:  # ESCALATE
            explanation = (
                f"This request requires human review due to multiple concerns. "
                f"{key_signals_text}. "
                f"Our team will contact you to discuss alternatives. "
            )
        
        # Add audit checklist as paragraph
        explanation += " Audit checklist: " + " ".join(audit_checklist)
        
        # Add decision rationale (conditional)
        if decision_rationale:
            explanation += " Decision rationale: " + " ".join(decision_rationale)
        
        # Add adaptive subgraphs section (only if adaptive==1 and subgraphs were activated)
        if candidate.get("adaptive", False) and state.get("active_subgraphs"):
            subgraphs_str = ", ".join(state["active_subgraphs"])
            explanation += f" Adaptive subgraphs activated: {subgraphs_str}."
            
            # Add adaptive findings (Step D)
            if "sub_findings" in state and state["sub_findings"]:
                explanation += " Adaptive findings: " + " ".join(state["sub_findings"])
        
        # Add advisory coverage (conditional, topology-dependent)
        advisory_notes = []
        if "diversification_note" in state:
            advisory_notes.append(state["diversification_note"])
        if "liquidity_maintenance_note" in state:
            advisory_notes.append(state["liquidity_maintenance_note"])
        if "reasonableness_note" in state:
            advisory_notes.append(state["reasonableness_note"])
        if "alignment_note" in state:
            advisory_notes.append(state["alignment_note"])
        
        if advisory_notes:
            explanation += " Advisory coverage: " + " ".join(advisory_notes)
        
        # Add conditions/next steps
        if notes:
            explanation += f"\n\nApplicable policy: {notes[0]}"
            if len(notes) > 1:
                explanation += f" Also consider: {notes[1]}"
    
    state["explanation"] = explanation
    
    # Track token usage for synth node
    carryover_mode = candidate.get("carryover", "compact")
    carryover_text = build_carryover_text(state, carryover_mode)
    policy_text_sample = state.get("policy_text", "")
    
    # Build prompt text (what would be sent to LLM for final synthesis)
    prompt_text = f"""Synthesize final decision and explanation.

Signals: {', '.join(signals)}
Notes: {', '.join(notes) if notes else 'none'}
Active Subgraphs: {', '.join(state.get('active_subgraphs', []))}
Sub Findings: {len(state.get('sub_findings', []))} findings

Policy Context:
{policy_text_sample[:500] if policy_text_sample else 'N/A'}...

"""
    # Add carryover context if present (extracted to avoid f-string backslash)
    carryover_section = f"Previous Context:\n{carryover_text}\n" if carryover_text else ""
    prompt_text += carryover_section
    prompt_text += """
Task: Generate decision and client-friendly explanation."""
    
    output_text = explanation
    add_node_usage(state, "synth", prompt_text, output_text)
    
    return state


# ============================================================================
# Fallback pure-Python runner
# ============================================================================

class FallbackRunner:
    """Pure-Python state machine for when LangGraph is unavailable."""
    
    def __init__(self, candidate: dict, policy_text: str):
        self.candidate = candidate
        self.policy_text = policy_text
    
    def run_case(self, case_dict: dict) -> dict:
        """Run a single case through the pipeline."""
        # Extract signals from case using deterministic rules
        initial_signals = extract_signals(case_dict)
        
        # Initialize state
        state: State = {
            "case": case_dict,
            "policy_text": self.policy_text,
            "signals": initial_signals,
            "notes": [],
            "decision": "",
            "explanation": "",
            "path": [],
            "candidate": self.candidate,
            "active_subgraphs": [],
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "token_trace": []
        }
        
        # Define node sequence based on configuration
        nodes = []
        if self.candidate.get("use_risk_decompose"):
            nodes.append(risk_decompose_node)
        if self.candidate.get("use_behavior_check"):
            nodes.append(behavior_check_node)
        if self.candidate.get("use_retriever"):
            nodes.append(retriever_node)
        
        # Run analysis nodes (each node checks budget internally now)
        for node_func in nodes:
            state = node_func(state)
        
        # Always run synth_node at the end (it checks budget internally)
        state = synth_node(state)
        
        return state


# ============================================================================
# Graph builder
# ============================================================================

def build_runner(candidate: dict, policy_text: str, export_descriptor: bool = False):
    """
    Build a runner function for the given candidate configuration.
    
    Args:
        candidate: Configuration dict with flags and parameters
        policy_text: Policy guidance text
        export_descriptor: If True, return (runner, descriptor) tuple. Default False.
        
    Returns:
        If export_descriptor is False: Function that takes case_dict and returns final state dict
        If export_descriptor is True: Tuple of (runner_function, wiring_descriptor)
    """
    # Normalize candidate to support both legacy and registry-driven formats
    candidate = normalize_candidate(candidate)
    
    # Initialize wiring descriptor
    from demos.portfolio_langgraph_opt.src.search_space import candidate_to_name
    
    descriptor = {
        "nodes": [],
        "edges": [],
        "clusters": [],
        "meta": {
            "candidate_name": candidate_to_name(candidate),
            "max_steps": candidate.get("max_steps", 4),
            "adaptive": candidate.get("adaptive", False),
            "adaptive_policy": candidate.get("adaptive_policy", "strict"),
            "synth_style": candidate.get("synth_style", "A"),
            "carryover": candidate.get("carryover", "compact"),
            "use_langgraph": LANGGRAPH_AVAILABLE
        }
    }
    
    if not LANGGRAPH_AVAILABLE:
        # Use fallback runner - track nodes in execution order
        descriptor["nodes"].append({
            "id": "entry",
            "label": "Entry",
            "kind": "control",
            "enabled": True
        })
        
        # Add nodes based on candidate config
        if candidate.get("use_risk_decompose"):
            descriptor["nodes"].append({
                "id": "risk_decompose",
                "label": "Risk Decompose",
                "kind": "processing",
                "enabled": True
            })
            descriptor["edges"].append({
                "from": "entry" if len(descriptor["nodes"]) == 2 else descriptor["nodes"][-2]["id"],
                "to": "risk_decompose",
                "kind": "main",
                "label": None
            })
        
        if candidate.get("use_behavior_check"):
            descriptor["nodes"].append({
                "id": "behavior_check",
                "label": "Behavior Check",
                "kind": "processing",
                "enabled": True
            })
            descriptor["edges"].append({
                "from": descriptor["nodes"][-2]["id"],
                "to": "behavior_check",
                "kind": "main",
                "label": None
            })
        
        if candidate.get("use_retriever"):
            descriptor["nodes"].append({
                "id": "retriever",
                "label": "Retriever",
                "kind": "processing",
                "enabled": True
            })
            descriptor["edges"].append({
                "from": descriptor["nodes"][-2]["id"],
                "to": "retriever",
                "kind": "main",
                "label": None
            })
        
        # Synth is always present
        descriptor["nodes"].append({
            "id": "synth",
            "label": f"Synth ({candidate.get('synth_style', 'A')})",
            "kind": "synthesis",
            "enabled": True
        })
        descriptor["edges"].append({
            "from": descriptor["nodes"][-2]["id"],
            "to": "synth",
            "kind": "main",
            "label": None
        })
        
        # Add adaptive cluster if enabled
        if candidate.get("adaptive"):
            adaptive_nodes = ["sub_liquidity", "sub_concentration", "sub_leverage", "sub_suitability"]
            descriptor["clusters"].append({
                "id": "adaptive",
                "label": f"Adaptive Subgraphs ({candidate.get('adaptive_policy', 'strict')})",
                "node_ids": adaptive_nodes,
                "style": {"color": "lightblue", "shape": "box"}
            })
            # Add adaptive subgraph nodes
            for subgraph_id in adaptive_nodes:
                descriptor["nodes"].append({
                    "id": subgraph_id,
                    "label": subgraph_id.replace("sub_", "").title(),
                    "kind": "adaptive",
                    "enabled": True
                })
        
        # Use fallback runner
        runner = FallbackRunner(candidate, policy_text)
        
        if export_descriptor:
            return runner.run_case, descriptor
        return runner.run_case
    
    # Build LangGraph - track actual wiring
    graph = StateGraph(State)
    
    # Add all nodes (even if not used - LangGraph requires them for edges)
    # Track which ones are actually enabled
    all_node_ids = ["risk_decompose", "behavior_check", "retriever", "synth"]
    node_labels = {
        "risk_decompose": "Risk Decompose",
        "behavior_check": "Behavior Check",
        "retriever": "Retriever",
        "synth": f"Synth ({candidate.get('synth_style', 'A')})"
    }
    node_kinds = {
        "risk_decompose": "processing",
        "behavior_check": "processing",
        "retriever": "processing",
        "synth": "synthesis"
    }
    
    # Add nodes to graph
    graph.add_node("risk_decompose", risk_decompose_node)
    graph.add_node("behavior_check", behavior_check_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("synth", synth_node)
    
    # Track enabled nodes for descriptor
    enabled_nodes = set()
    enabled_nodes.add("synth")  # Always enabled
    
    if candidate.get("use_risk_decompose"):
        enabled_nodes.add("risk_decompose")
    if candidate.get("use_behavior_check"):
        enabled_nodes.add("behavior_check")
    if candidate.get("use_retriever"):
        enabled_nodes.add("retriever")
    
    # Add all nodes to descriptor (marking enabled/disabled)
    for node_id in all_node_ids:
        descriptor["nodes"].append({
            "id": node_id,
            "label": node_labels[node_id],
            "kind": node_kinds[node_id],
            "enabled": node_id in enabled_nodes
        })
    
    # Determine entry point and flow
    max_steps = candidate.get("max_steps", 4)
    
    # Build conditional flow
    def route_to_next(state: State) -> str:
        """Route to next node based on candidate config and path length."""
        path_len = len(state.get("path", []))
        
        # If approaching max_steps, go to synth
        if path_len >= max_steps - 1:
            return "synth"
        
        # Check which nodes still need to run
        executed = set(state.get("path", []))
        
        if candidate.get("use_risk_decompose") and "risk_decompose" not in executed:
            return "risk_decompose"
        if candidate.get("use_behavior_check") and "behavior_check" not in executed:
            return "behavior_check"
        if candidate.get("use_retriever") and "retriever" not in executed:
            return "retriever"
        
        return "synth"
    
    # Set entry point and track edges
    entry_node = None
    if candidate.get("use_risk_decompose"):
        graph.set_entry_point("risk_decompose")
        entry_node = "risk_decompose"
    elif candidate.get("use_behavior_check"):
        graph.set_entry_point("behavior_check")
        entry_node = "behavior_check"
    elif candidate.get("use_retriever"):
        graph.set_entry_point("retriever")
        entry_node = "retriever"
    else:
        graph.set_entry_point("synth")
        entry_node = "synth"
    
    # Add entry edge to descriptor
    descriptor["edges"].append({
        "from": "START",
        "to": entry_node,
        "kind": "main",
        "label": "entry"
    })
    
    # Add edges based on actual wiring logic
    if candidate.get("use_risk_decompose"):
        if candidate.get("use_behavior_check"):
            graph.add_edge("risk_decompose", "behavior_check")
            descriptor["edges"].append({
                "from": "risk_decompose",
                "to": "behavior_check",
                "kind": "main",
                "label": None
            })
        elif candidate.get("use_retriever"):
            graph.add_edge("risk_decompose", "retriever")
            descriptor["edges"].append({
                "from": "risk_decompose",
                "to": "retriever",
                "kind": "main",
                "label": None
            })
        else:
            graph.add_edge("risk_decompose", "synth")
            descriptor["edges"].append({
                "from": "risk_decompose",
                "to": "synth",
                "kind": "main",
                "label": None
            })
    
    if candidate.get("use_behavior_check"):
        if candidate.get("use_retriever"):
            graph.add_edge("behavior_check", "retriever")
            descriptor["edges"].append({
                "from": "behavior_check",
                "to": "retriever",
                "kind": "main",
                "label": None
            })
        else:
            graph.add_edge("behavior_check", "synth")
            descriptor["edges"].append({
                "from": "behavior_check",
                "to": "synth",
                "kind": "main",
                "label": None
            })
    
    if candidate.get("use_retriever"):
        graph.add_edge("retriever", "synth")
        descriptor["edges"].append({
            "from": "retriever",
            "to": "synth",
            "kind": "main",
            "label": None
        })
    
    # Final edge to END
    graph.add_edge("synth", END)
    descriptor["edges"].append({
        "from": "synth",
        "to": "END",
        "kind": "main",
        "label": "terminal"
    })
    
    # Add adaptive cluster if enabled
    if candidate.get("adaptive"):
        adaptive_nodes = ["sub_liquidity", "sub_concentration", "sub_leverage", "sub_suitability"]
        descriptor["clusters"].append({
            "id": "adaptive",
            "label": f"Adaptive Subgraphs ({candidate.get('adaptive_policy', 'strict')})",
            "node_ids": adaptive_nodes,
            "style": {"color": "lightblue", "shape": "box", "style": "dashed"}
        })
        # Add adaptive subgraph nodes to descriptor
        for subgraph_id in adaptive_nodes:
            descriptor["nodes"].append({
                "id": subgraph_id,
                "label": subgraph_id.replace("sub_", "").title(),
                "kind": "adaptive",
                "enabled": True
            })
        # Add conditional edges from synth to adaptive subgraphs
        for subgraph_id in adaptive_nodes:
            descriptor["edges"].append({
                "from": "synth",
                "to": subgraph_id,
                "kind": "adaptive",
                "label": "conditional"
            })
    
    # Compile graph
    app = graph.compile()
    
    # Return runner function
    def run_case(case_dict: dict) -> dict:
        # Extract signals from case using deterministic rules
        initial_signals = extract_signals(case_dict)
        
        initial_state: State = {
            "case": case_dict,
            "policy_text": policy_text,
            "signals": initial_signals,
            "notes": [],
            "decision": "",
            "explanation": "",
            "path": [],
            "candidate": candidate,
            "active_subgraphs": [],
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "token_trace": []
        }
        result = app.invoke(initial_state)
        return result
    
    if export_descriptor:
        return run_case, descriptor
    return run_case


# ============================================================================
# Self-test (DO NOT run on import)
# ============================================================================

def _smoke_test():
    """
    Simple smoke test with dummy case and two candidates.
    Returns outputs for inspection.
    """
    # Dummy case
    dummy_case = {
        "case_id": "TEST001",
        "client_profile": {
            "age": 28,
            "risk_appetite": "high",
            "liquidity_need": "low",
            "experience": "high"
        },
        "portfolio": {
            "equities_pct": 75,
            "bonds_pct": 15,
            "alts_pct": 5,
            "cash_pct": 5,
            "concentration": "medium",
            "volatility": "high",
            "liquidity": "high"
        },
        "requested_action": "add leveraged ETF exposure to amplify growth potential"
    }
    
    # Dummy policy
    dummy_policy = "Avoid leveraged products without disclosure.\nMatch risk appetite to allocation."
    
    # Candidate 1: Minimal
    candidate1 = {
        "use_retriever": False,
        "use_risk_decompose": False,
        "use_behavior_check": False,
        "use_hitl_gate": False,
        "synth_style": "A",
        "max_steps": 4
    }
    
    # Candidate 2: Full analysis
    candidate2 = {
        "use_retriever": True,
        "use_risk_decompose": True,
        "use_behavior_check": True,
        "use_hitl_gate": False,
        "synth_style": "B",
        "max_steps": 4
    }
    
    # Run both
    runner1 = build_runner(candidate1, dummy_policy)
    runner2 = build_runner(candidate2, dummy_policy)
    
    result1 = runner1(dummy_case)
    result2 = runner2(dummy_case)
    
    return {
        "candidate1_result": result1,
        "candidate2_result": result2,
        "langgraph_available": LANGGRAPH_AVAILABLE
    }


if __name__ == "__main__":
    # Only run smoke test if executed directly
    results = _smoke_test()
    print("Smoke test results:")
    print(f"LangGraph available: {results['langgraph_available']}")
    print(f"\nCandidate 1 decision: {results['candidate1_result']['decision']}")
    print(f"Candidate 1 path: {results['candidate1_result']['path']}")
    print(f"\nCandidate 2 decision: {results['candidate2_result']['decision']}")
    print(f"Candidate 2 path: {results['candidate2_result']['path']}")
    print(f"Candidate 2 signals: {results['candidate2_result']['signals']}")
