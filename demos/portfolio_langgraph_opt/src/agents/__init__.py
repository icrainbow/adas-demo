"""Agent registry system for portfolio advisory graph."""

from demos.portfolio_langgraph_opt.src.agents.load_registry import (
    load_registry,
    get_agents_by_group,
    get_enabled_by_default,
    get_agents_by_stage,
    get_agents_by_type,
    print_registry_summary
)
from demos.portfolio_langgraph_opt.src.agents.registry_schema import (
    AgentDef,
    Constraints,
    Ordering,
    CostHint
)
from demos.portfolio_langgraph_opt.src.agents.constraints import (
    validate_combo,
    validate_combo_or_raise,
    get_missing_required_agents,
    get_conflicting_agents,
    get_group_violations,
    suggest_fixes
)

__all__ = [
    # Loader functions
    "load_registry",
    "get_agents_by_group",
    "get_enabled_by_default",
    "get_agents_by_stage",
    "get_agents_by_type",
    "print_registry_summary",
    # Schema classes
    "AgentDef",
    "Constraints",
    "Ordering",
    "CostHint",
    # Constraint validation
    "validate_combo",
    "validate_combo_or_raise",
    "get_missing_required_agents",
    "get_conflicting_agents",
    "get_group_violations",
    "suggest_fixes",
]
