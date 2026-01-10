"""Agent registry schema validation using dataclasses."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Constraints:
    """Agent combination constraints."""
    requires: list[str] = field(default_factory=list)
    requires_any: list[str] = field(default_factory=list)
    mutex_with: list[str] = field(default_factory=list)
    only_with: list[str] = field(default_factory=list)
    at_most_one_group: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> "Constraints":
        """Create Constraints from dictionary with validation."""
        if not isinstance(data, dict):
            raise ValueError(f"Constraints must be dict, got {type(data)}")
        
        # Validate list fields
        for field_name in ["requires", "requires_any", "mutex_with", "only_with"]:
            value = data.get(field_name, [])
            if not isinstance(value, list):
                raise ValueError(f"constraints.{field_name} must be list, got {type(value)}")
            if not all(isinstance(item, str) for item in value):
                raise ValueError(f"constraints.{field_name} must contain strings only")
        
        # Validate string field
        at_most_one_group = data.get("at_most_one_group", "")
        if not isinstance(at_most_one_group, str):
            raise ValueError(f"constraints.at_most_one_group must be string, got {type(at_most_one_group)}")
        
        return cls(
            requires=data.get("requires", []),
            requires_any=data.get("requires_any", []),
            mutex_with=data.get("mutex_with", []),
            only_with=data.get("only_with", []),
            at_most_one_group=at_most_one_group
        )


@dataclass
class Ordering:
    """Agent execution ordering hints."""
    priority: int = 100
    depends_on: list[str] = field(default_factory=list)
    before: list[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Ordering":
        """Create Ordering from dictionary with validation."""
        if not isinstance(data, dict):
            raise ValueError(f"Ordering must be dict, got {type(data)}")
        
        priority = data.get("priority", 100)
        if not isinstance(priority, int):
            raise ValueError(f"ordering.priority must be int, got {type(priority)}")
        
        depends_on = data.get("depends_on", [])
        if not isinstance(depends_on, list):
            raise ValueError(f"ordering.depends_on must be list, got {type(depends_on)}")
        if not all(isinstance(item, str) for item in depends_on):
            raise ValueError(f"ordering.depends_on must contain strings only")
        
        before = data.get("before", [])
        if not isinstance(before, list):
            raise ValueError(f"ordering.before must be list, got {type(before)}")
        if not all(isinstance(item, str) for item in before):
            raise ValueError(f"ordering.before must contain strings only")
        
        return cls(
            priority=priority,
            depends_on=depends_on,
            before=before
        )


@dataclass
class CostHint:
    """Resource usage estimates for agent."""
    tokens_per_case: int = 0
    relative_latency: float = 1.0
    complexity: str = "low"
    
    @classmethod
    def from_dict(cls, data: dict) -> "CostHint":
        """Create CostHint from dictionary with validation."""
        if not isinstance(data, dict):
            raise ValueError(f"CostHint must be dict, got {type(data)}")
        
        tokens_per_case = data.get("tokens_per_case", 0)
        if not isinstance(tokens_per_case, int):
            raise ValueError(f"cost_hint.tokens_per_case must be int, got {type(tokens_per_case)}")
        
        relative_latency = data.get("relative_latency", 1.0)
        if not isinstance(relative_latency, (int, float)):
            raise ValueError(f"cost_hint.relative_latency must be number, got {type(relative_latency)}")
        
        complexity = data.get("complexity", "low")
        if not isinstance(complexity, str):
            raise ValueError(f"cost_hint.complexity must be string, got {type(complexity)}")
        if complexity not in ["low", "medium", "high"]:
            raise ValueError(f"cost_hint.complexity must be 'low', 'medium', or 'high', got '{complexity}'")
        
        return cls(
            tokens_per_case=tokens_per_case,
            relative_latency=float(relative_latency),
            complexity=complexity
        )


@dataclass
class AgentDef:
    """Agent definition from registry YAML."""
    id: str
    version: str
    stage: str
    node_type: str
    enabled_by_default: bool
    description: str
    params: dict[str, Any]
    constraints: Constraints
    ordering: Ordering
    cost_hint: CostHint
    
    @classmethod
    def from_dict(cls, data: dict, source_file: str = "") -> "AgentDef":
        """
        Create AgentDef from dictionary with validation.
        
        Args:
            data: Dictionary from YAML parsing
            source_file: Source file path for error messages
            
        Returns:
            Validated AgentDef instance
            
        Raises:
            ValueError: If validation fails with descriptive message
        """
        source_prefix = f"[{source_file}] " if source_file else ""
        
        if not isinstance(data, dict):
            raise ValueError(f"{source_prefix}Agent definition must be dict, got {type(data)}")
        
        # Required fields
        required_fields = ["id", "version", "stage", "node_type", "enabled_by_default", 
                          "params", "constraints", "ordering", "cost_hint"]
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            raise ValueError(f"{source_prefix}Missing required fields: {missing_fields}")
        
        # Validate id
        agent_id = data["id"]
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError(f"{source_prefix}id must be non-empty string")
        
        # Validate version
        version = data["version"]
        if not isinstance(version, str) or not version.strip():
            raise ValueError(f"{source_prefix}version must be non-empty string")
        
        # Validate stage
        stage = data["stage"]
        if not isinstance(stage, str):
            raise ValueError(f"{source_prefix}stage must be string, got {type(stage)}")
        valid_stages = ["preprocessing", "processing", "synthesis", "strategy"]
        if stage not in valid_stages:
            raise ValueError(f"{source_prefix}stage must be one of {valid_stages}, got '{stage}'")
        
        # Validate node_type
        node_type = data["node_type"]
        if not isinstance(node_type, str):
            raise ValueError(f"{source_prefix}node_type must be string, got {type(node_type)}")
        valid_types = ["node", "style", "strategy", "policy"]
        if node_type not in valid_types:
            raise ValueError(f"{source_prefix}node_type must be one of {valid_types}, got '{node_type}'")
        
        # Validate enabled_by_default
        enabled_by_default = data["enabled_by_default"]
        if not isinstance(enabled_by_default, bool):
            raise ValueError(f"{source_prefix}enabled_by_default must be bool, got {type(enabled_by_default)}")
        
        # Optional description
        description = data.get("description", "")
        if not isinstance(description, str):
            raise ValueError(f"{source_prefix}description must be string, got {type(description)}")
        
        # Validate params
        params = data["params"]
        if not isinstance(params, dict):
            raise ValueError(f"{source_prefix}params must be dict, got {type(params)}")
        
        # Validate nested objects
        try:
            constraints = Constraints.from_dict(data["constraints"])
        except ValueError as e:
            raise ValueError(f"{source_prefix}{e}")
        
        try:
            ordering = Ordering.from_dict(data["ordering"])
        except ValueError as e:
            raise ValueError(f"{source_prefix}{e}")
        
        try:
            cost_hint = CostHint.from_dict(data["cost_hint"])
        except ValueError as e:
            raise ValueError(f"{source_prefix}{e}")
        
        return cls(
            id=agent_id,
            version=version,
            stage=stage,
            node_type=node_type,
            enabled_by_default=enabled_by_default,
            description=description,
            params=params,
            constraints=constraints,
            ordering=ordering,
            cost_hint=cost_hint
        )
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (f"AgentDef(id='{self.id}', version='{self.version}', "
                f"stage='{self.stage}', node_type='{self.node_type}')")
