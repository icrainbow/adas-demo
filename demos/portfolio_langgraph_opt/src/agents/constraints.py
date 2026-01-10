"""Constraint validation engine for agent combinations."""

from typing import Dict, Set, List, Tuple
from demos.portfolio_langgraph_opt.src.agents.registry_schema import AgentDef


def validate_combo(selected: Set[str], registry: Dict[str, AgentDef]) -> Tuple[bool, List[str]]:
    """
    Validate whether a set of selected agents satisfies all constraints.
    
    Args:
        selected: Set of agent IDs to validate
        registry: Dictionary mapping agent ID to AgentDef
        
    Returns:
        Tuple of (is_valid, error_messages)
        - is_valid: True if combination is valid, False otherwise
        - error_messages: List of human-readable error descriptions (empty if valid)
        
    Validation Rules:
        1. requires: If agent A is selected, all agents in A.constraints.requires must be selected
        2. requires_any: If agent A is selected, at least one agent from A.constraints.requires_any must be selected
        3. mutex_with: If agent A is selected, no agent in A.constraints.mutex_with can be selected
        4. only_with: If agent A is selected and only_with is non-empty, 
                     selected must be subset of (A.constraints.only_with + {A})
        5. at_most_one_group: For each group, at most one agent with that group name can be selected
    """
    errors: List[str] = []
    
    # Validate that all selected agent IDs exist in registry
    for agent_id in selected:
        if agent_id not in registry:
            errors.append(f"Unknown agent ID: '{agent_id}'")
    
    if errors:
        # Can't proceed with further validation if IDs are invalid
        return (False, errors)
    
    # Check each constraint type for selected agents
    for agent_id in selected:
        agent = registry[agent_id]
        constraints = agent.constraints
        
        # 1. Check 'requires' constraint
        for required_id in constraints.requires:
            if required_id not in selected:
                errors.append(
                    f"Agent '{agent_id}' requires '{required_id}' but it is not selected"
                )
        
        # 2. Check 'requires_any' constraint
        if constraints.requires_any:
            # At least one of the required_any agents must be selected
            if not any(req_id in selected for req_id in constraints.requires_any):
                errors.append(
                    f"Agent '{agent_id}' requires at least one of {constraints.requires_any}, "
                    f"but none are selected"
                )
        
        # 3. Check 'mutex_with' constraint
        for mutex_id in constraints.mutex_with:
            if mutex_id in selected:
                errors.append(
                    f"Agent '{agent_id}' is mutually exclusive with '{mutex_id}', "
                    f"but both are selected"
                )
        
        # 4. Check 'only_with' constraint
        if constraints.only_with:
            # If only_with is specified, selected must be subset of (only_with + {agent_id})
            allowed_set = set(constraints.only_with) | {agent_id}
            disallowed = selected - allowed_set
            if disallowed:
                errors.append(
                    f"Agent '{agent_id}' specifies only_with={constraints.only_with}, "
                    f"but these agents are also selected: {sorted(disallowed)}"
                )
    
    # 5. Check 'at_most_one_group' constraint
    # Collect all agents by group
    groups: Dict[str, List[str]] = {}
    for agent_id in selected:
        agent = registry[agent_id]
        group_name = agent.constraints.at_most_one_group
        if group_name:  # Non-empty group name
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(agent_id)
    
    # Check that each group has at most one member
    for group_name, members in groups.items():
        if len(members) > 1:
            errors.append(
                f"Group '{group_name}' allows at most one agent, "
                f"but {len(members)} are selected: {sorted(members)}"
            )
    
    # Return validation result
    is_valid = len(errors) == 0
    return (is_valid, errors)


def validate_combo_or_raise(selected: Set[str], registry: Dict[str, AgentDef]) -> None:
    """
    Validate agent combination and raise ValueError if invalid.
    
    Args:
        selected: Set of agent IDs to validate
        registry: Dictionary mapping agent ID to AgentDef
        
    Raises:
        ValueError: If combination is invalid, with all error messages combined
    """
    is_valid, errors = validate_combo(selected, registry)
    if not is_valid:
        error_msg = "Invalid agent combination:\n  - " + "\n  - ".join(errors)
        raise ValueError(error_msg)


def get_missing_required_agents(selected: Set[str], registry: Dict[str, AgentDef]) -> Set[str]:
    """
    Get set of agents that are required by selected agents but not included.
    
    Useful for suggesting additions to make a configuration valid.
    
    Args:
        selected: Set of agent IDs
        registry: Dictionary mapping agent ID to AgentDef
        
    Returns:
        Set of agent IDs that should be added to satisfy 'requires' constraints
    """
    missing = set()
    
    for agent_id in selected:
        if agent_id not in registry:
            continue
        agent = registry[agent_id]
        for required_id in agent.constraints.requires:
            if required_id not in selected:
                missing.add(required_id)
    
    return missing


def get_conflicting_agents(selected: Set[str], registry: Dict[str, AgentDef]) -> Set[str]:
    """
    Get set of agents that conflict with selected agents (mutex_with).
    
    Useful for understanding why a combination is invalid.
    
    Args:
        selected: Set of agent IDs
        registry: Dictionary mapping agent ID to AgentDef
        
    Returns:
        Set of agent IDs that conflict with selected agents
    """
    conflicts = set()
    
    for agent_id in selected:
        if agent_id not in registry:
            continue
        agent = registry[agent_id]
        for mutex_id in agent.constraints.mutex_with:
            if mutex_id in selected:
                conflicts.add(mutex_id)
    
    return conflicts


def get_group_violations(selected: Set[str], registry: Dict[str, AgentDef]) -> Dict[str, List[str]]:
    """
    Get groups that have more than one selected agent (violations).
    
    Args:
        selected: Set of agent IDs
        registry: Dictionary mapping agent ID to AgentDef
        
    Returns:
        Dictionary mapping group name to list of violating agent IDs
    """
    groups: Dict[str, List[str]] = {}
    
    for agent_id in selected:
        if agent_id not in registry:
            continue
        agent = registry[agent_id]
        group_name = agent.constraints.at_most_one_group
        if group_name:
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(agent_id)
    
    # Return only groups with violations (more than 1 member)
    return {name: members for name, members in groups.items() if len(members) > 1}


def suggest_fixes(selected: Set[str], registry: Dict[str, AgentDef]) -> Dict[str, any]:
    """
    Analyze an invalid combination and suggest fixes.
    
    Args:
        selected: Set of agent IDs
        registry: Dictionary mapping agent ID to AgentDef
        
    Returns:
        Dictionary with suggested fixes:
        - 'add': Set of agents to add
        - 'remove': Set of agents to remove
        - 'group_conflicts': Dict of group violations
    """
    suggestions = {
        'add': get_missing_required_agents(selected, registry),
        'remove': get_conflicting_agents(selected, registry),
        'group_conflicts': get_group_violations(selected, registry)
    }
    
    return suggestions
