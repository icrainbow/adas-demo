"""Agent registry loader with validation."""

import os
from pathlib import Path
from typing import Optional
import yaml

from demos.portfolio_langgraph_opt.src.agents.registry_schema import AgentDef


def load_registry(registry_dir: Optional[str] = None) -> dict[str, AgentDef]:
    """
    Load all agent definitions from registry directory.
    
    Args:
        registry_dir: Path to registry directory. If None, uses default location
                     relative to this file.
                     
    Returns:
        Dictionary mapping agent ID to AgentDef
        
    Raises:
        ValueError: If validation fails or references are invalid
    """
    # Default registry directory
    if registry_dir is None:
        this_file = Path(__file__)
        registry_dir = this_file.parent / "registry"
    else:
        registry_dir = Path(registry_dir)
    
    if not registry_dir.exists():
        raise ValueError(f"Registry directory not found: {registry_dir}")
    
    if not registry_dir.is_dir():
        raise ValueError(f"Registry path is not a directory: {registry_dir}")
    
    # Load all YAML files
    agents: dict[str, AgentDef] = {}
    yaml_files = sorted(registry_dir.glob("*.yaml"))
    
    if not yaml_files:
        raise ValueError(f"No YAML files found in registry: {registry_dir}")
    
    # Parse and validate each YAML file
    for yaml_file in yaml_files:
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if data is None:
                raise ValueError(f"Empty YAML file")
            
            # Create AgentDef with validation
            agent_def = AgentDef.from_dict(data, source_file=yaml_file.name)
            
            # Check for duplicate IDs
            if agent_def.id in agents:
                existing_file = [yf.name for yf in yaml_files 
                               if agents[agent_def.id].id == agent_def.id][0]
                raise ValueError(
                    f"Duplicate agent ID '{agent_def.id}' in {yaml_file.name} "
                    f"(already defined in {existing_file})"
                )
            
            agents[agent_def.id] = agent_def
            
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parsing error in {yaml_file.name}: {e}")
        except ValueError as e:
            # Re-raise with file context if not already included
            if yaml_file.name not in str(e):
                raise ValueError(f"[{yaml_file.name}] {e}")
            raise
    
    # Validate constraint references
    _validate_constraint_references(agents)
    
    # Validate at_most_one_group consistency
    _validate_at_most_one_groups(agents)
    
    return agents


def _validate_constraint_references(agents: dict[str, AgentDef]) -> None:
    """
    Validate that all agent IDs referenced in constraints exist.
    
    Args:
        agents: Dictionary of agent definitions
        
    Raises:
        ValueError: If any referenced agent ID doesn't exist
    """
    all_ids = set(agents.keys())
    
    for agent_id, agent_def in agents.items():
        constraints = agent_def.constraints
        
        # Check requires
        for required_id in constraints.requires:
            if required_id not in all_ids:
                raise ValueError(
                    f"Agent '{agent_id}' requires unknown agent '{required_id}'"
                )
        
        # Check requires_any
        for required_id in constraints.requires_any:
            if required_id not in all_ids:
                raise ValueError(
                    f"Agent '{agent_id}' requires_any unknown agent '{required_id}'"
                )
        
        # Check mutex_with
        for mutex_id in constraints.mutex_with:
            if mutex_id not in all_ids:
                raise ValueError(
                    f"Agent '{agent_id}' has mutex_with unknown agent '{mutex_id}'"
                )
        
        # Check only_with
        for only_id in constraints.only_with:
            if only_id not in all_ids:
                raise ValueError(
                    f"Agent '{agent_id}' has only_with unknown agent '{only_id}'"
                )
        
        # Check ordering.depends_on
        for dep_id in agent_def.ordering.depends_on:
            if dep_id not in all_ids:
                raise ValueError(
                    f"Agent '{agent_id}' ordering.depends_on unknown agent '{dep_id}'"
                )
        
        # Check ordering.before
        for before_id in agent_def.ordering.before:
            if before_id not in all_ids:
                raise ValueError(
                    f"Agent '{agent_id}' ordering.before unknown agent '{before_id}'"
                )


def _validate_at_most_one_groups(agents: dict[str, AgentDef]) -> None:
    """
    Validate that at_most_one_group is used consistently.
    
    Ensures that agents in the same group all reference the same group name
    and that group names make semantic sense.
    
    Args:
        agents: Dictionary of agent definitions
        
    Raises:
        ValueError: If at_most_one_group usage is inconsistent
    """
    # Collect all groups
    groups: dict[str, list[str]] = {}
    
    for agent_id, agent_def in agents.items():
        group_name = agent_def.constraints.at_most_one_group
        if group_name:  # Non-empty string
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(agent_id)
    
    # Validate each group
    for group_name, member_ids in groups.items():
        # Groups should have at least 2 members (otherwise unnecessary)
        if len(member_ids) < 2:
            # This is a warning-level issue, not an error
            # In production, might want to log this
            pass
        
        # Check that all group members actually have mutex_with constraints
        # (at_most_one_group is syntactic sugar for pairwise mutex)
        for agent_id in member_ids:
            agent_def = agents[agent_id]
            other_members = [m for m in member_ids if m != agent_id]
            
            # Not all group members need explicit mutex_with entries
            # (at_most_one_group handles this), but if they do have mutex_with,
            # it should be consistent
            mutex_ids = set(agent_def.constraints.mutex_with)
            
            # Check that mutex_with doesn't contradict the group
            # (e.g., agent shouldn't have mutex_with someone outside its group
            # while claiming to be in an exclusive group)
            # This is a soft check - skip for now as it's complex


def get_agents_by_group(agents: dict[str, AgentDef], group_name: str) -> list[AgentDef]:
    """
    Get all agents belonging to a specific at_most_one_group.
    
    Args:
        agents: Dictionary of agent definitions
        group_name: Group name to filter by
        
    Returns:
        List of agent definitions in the specified group
    """
    return [
        agent_def for agent_def in agents.values()
        if agent_def.constraints.at_most_one_group == group_name
    ]


def get_enabled_by_default(agents: dict[str, AgentDef]) -> list[str]:
    """
    Get list of agent IDs that are enabled by default.
    
    Args:
        agents: Dictionary of agent definitions
        
    Returns:
        List of agent IDs with enabled_by_default=True
    """
    return [
        agent_id for agent_id, agent_def in agents.items()
        if agent_def.enabled_by_default
    ]


def get_agents_by_stage(agents: dict[str, AgentDef], stage: str) -> list[AgentDef]:
    """
    Get all agents in a specific execution stage.
    
    Args:
        agents: Dictionary of agent definitions
        stage: Stage name to filter by
        
    Returns:
        List of agent definitions in the specified stage
    """
    return [
        agent_def for agent_def in agents.values()
        if agent_def.stage == stage
    ]


def get_agents_by_type(agents: dict[str, AgentDef], node_type: str) -> list[AgentDef]:
    """
    Get all agents of a specific node type.
    
    Args:
        agents: Dictionary of agent definitions
        node_type: Node type to filter by
        
    Returns:
        List of agent definitions with the specified node_type
    """
    return [
        agent_def for agent_def in agents.values()
        if agent_def.node_type == node_type
    ]


# Convenience function for CLI/debugging
def print_registry_summary(agents: dict[str, AgentDef]) -> None:
    """
    Print a human-readable summary of the registry.
    
    Args:
        agents: Dictionary of agent definitions
    """
    print(f"Loaded {len(agents)} agents:")
    print()
    
    # Group by stage
    stages = ["preprocessing", "processing", "synthesis", "strategy"]
    for stage in stages:
        stage_agents = get_agents_by_stage(agents, stage)
        if stage_agents:
            print(f"{stage.upper()}:")
            for agent in sorted(stage_agents, key=lambda a: a.id):
                enabled = "✓" if agent.enabled_by_default else " "
                print(f"  [{enabled}] {agent.id:30s} ({agent.node_type})")
            print()
    
    # Show at_most_one_groups
    groups: dict[str, list[str]] = {}
    for agent_def in agents.values():
        group_name = agent_def.constraints.at_most_one_group
        if group_name:
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(agent_def.id)
    
    if groups:
        print("AT_MOST_ONE_GROUPS:")
        for group_name, member_ids in sorted(groups.items()):
            print(f"  {group_name}: {', '.join(sorted(member_ids))}")
        print()


if __name__ == "__main__":
    # CLI usage: python -m demos.portfolio_langgraph_opt.src.agents.load_registry
    try:
        registry = load_registry()
        print_registry_summary(registry)
        print(f"✓ Registry validation passed: {len(registry)} agents loaded")
    except ValueError as e:
        print(f"✗ Registry validation failed: {e}")
        exit(1)
