"""YAML-driven search space generator for case-specific agent combinations."""

import os
import re
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple
import yaml

from demos.portfolio_langgraph_opt.src.agents import load_registry, validate_combo
from demos.portfolio_langgraph_opt.src.agents.registry_schema import AgentDef
from demos.portfolio_langgraph_opt.src.search_space import selected_agents_to_candidate


def load_search_space_for_case(case_id: Optional[str], registry_dir: Optional[str]):
    """
    Load search space module for a specific case.
    
    Resolution order:
    1. If case_id is None: return default module (KYC, unchanged)
    2. If YAML spec exists at src/cases/<case_id>/search_space.yaml:
       - Load registry from canonical case agents dir
       - Return SearchSpaceAdapter(spec, registry, case_id)
    3. Else: return default module (fallback)
    
    Args:
        case_id: Case identifier (e.g., "legal_case")
        registry_dir: Registry directory path (ignored for adapter; uses canonical per-case dir)
        
    Returns:
        Module-like object with default_candidate/all_candidates_small/candidate_to_name
    """
    # Fallback to default module if no case_id
    if case_id is None:
        import demos.portfolio_langgraph_opt.src.search_space as default_module
        return default_module
    
    # Validate case_id format
    if not re.match(r'^[A-Za-z0-9_-]+$', case_id):
        raise ValueError(f"Invalid case_id format: {case_id}")
    
    # Determine paths
    repo_root = Path(__file__).parent.parent.parent.parent
    yaml_path = repo_root / "demos/portfolio_langgraph_opt/src/cases" / case_id / "search_space.yaml"
    agents_dir = repo_root / "demos/portfolio_langgraph_opt/src/cases" / case_id / "agents"
    
    # If YAML spec exists, use adapter
    if yaml_path.exists():
        if not agents_dir.exists():
            raise ValueError(f"Case agents directory not found: {agents_dir}")
        
        # Load registry from canonical case agents directory
        registry = load_registry(str(agents_dir))
        
        # Load and validate YAML spec
        spec = load_yaml_spec(str(yaml_path))
        
        # Return adapter
        return SearchSpaceAdapter(spec, registry, case_id)
    
    # Fallback to default module
    import demos.portfolio_langgraph_opt.src.search_space as default_module
    return default_module


def load_yaml_spec(yaml_path: str) -> dict:
    """
    Load and validate YAML search space specification.
    
    Args:
        yaml_path: Path to YAML spec file
        
    Returns:
        Validated spec dictionary
        
    Raises:
        ValueError: If spec is invalid with detailed message
    """
    with open(yaml_path, 'r', encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    
    if not isinstance(spec, dict):
        raise ValueError(f"YAML spec must be a dict, got {type(spec)} in {yaml_path}")
    
    # Validate required top-level keys
    required_keys = ['version', 'case_id', 'limits', 'must_have', 'option_groups', 'dependencies', 'defaults']
    for key in required_keys:
        if key not in spec:
            raise ValueError(f"Missing required key '{key}' in {yaml_path}")
    
    # Validate limits
    if not isinstance(spec['limits'], dict):
        raise ValueError(f"'limits' must be dict in {yaml_path}")
    if 'max_candidates_small' not in spec['limits']:
        raise ValueError(f"'limits.max_candidates_small' missing in {yaml_path}")
    if 'hard_cap' not in spec['limits']:
        raise ValueError(f"'limits.hard_cap' missing in {yaml_path}")
    
    max_small = spec['limits']['max_candidates_small']
    hard_cap = spec['limits']['hard_cap']
    if not isinstance(max_small, int) or not isinstance(hard_cap, int):
        raise ValueError(f"limits values must be integers in {yaml_path}")
    if hard_cap < max_small:
        raise ValueError(f"hard_cap ({hard_cap}) < max_candidates_small ({max_small}) in {yaml_path}")
    
    # Validate must_have
    if not isinstance(spec['must_have'], list):
        raise ValueError(f"'must_have' must be list in {yaml_path}")
    
    # Validate option_groups
    if not isinstance(spec['option_groups'], list):
        raise ValueError(f"'option_groups' must be list in {yaml_path}")
    
    for i, group in enumerate(spec['option_groups']):
        if not isinstance(group, dict):
            raise ValueError(f"option_groups[{i}] must be dict in {yaml_path}")
        if 'name' not in group or 'mode' not in group:
            raise ValueError(f"option_groups[{i}] missing 'name' or 'mode' in {yaml_path}")
        
        mode = group['mode']
        if mode not in ['toggle', 'choose_one']:
            raise ValueError(f"option_groups[{i}] mode must be 'toggle' or 'choose_one' in {yaml_path}")
        
        if mode == 'toggle':
            if 'agents' not in group:
                raise ValueError(f"option_groups[{i}] mode=toggle requires 'agents' in {yaml_path}")
            if not isinstance(group['agents'], list):
                raise ValueError(f"option_groups[{i}].agents must be list in {yaml_path}")
        elif mode == 'choose_one':
            if 'choices' not in group:
                raise ValueError(f"option_groups[{i}] mode=choose_one requires 'choices' in {yaml_path}")
            if not isinstance(group['choices'], list):
                raise ValueError(f"option_groups[{i}].choices must be list in {yaml_path}")
            for j, choice in enumerate(group['choices']):
                if not isinstance(choice, dict):
                    raise ValueError(f"option_groups[{i}].choices[{j}] must be dict in {yaml_path}")
                if 'id' not in choice or 'include' not in choice:
                    raise ValueError(f"option_groups[{i}].choices[{j}] missing 'id' or 'include' in {yaml_path}")
                if not isinstance(choice['include'], list):
                    raise ValueError(f"option_groups[{i}].choices[{j}].include must be list in {yaml_path}")
    
    return spec


class SearchSpaceAdapter:
    """Adapter that implements search space interface using YAML spec."""
    
    def __init__(self, spec: dict, registry: Dict[str, AgentDef], case_id: str):
        self.spec = spec
        self.registry = registry
        self.case_id = case_id
        self._validate_agent_ids_exist()
        self._candidates_cache = None
    
    def _validate_agent_ids_exist(self) -> None:
        """Validate that all agent IDs in spec exist in registry."""
        registry_ids = set(self.registry.keys())
        
        for agent_id in self.spec['must_have']:
            if agent_id not in registry_ids:
                raise ValueError(f"must_have agent '{agent_id}' not found in registry")
        
        for group in self.spec['option_groups']:
            if group['mode'] == 'toggle':
                for agent_id in group['agents']:
                    if agent_id not in registry_ids:
                        raise ValueError(f"Group '{group['name']}' references unknown agent '{agent_id}'")
            elif group['mode'] == 'choose_one':
                for choice in group['choices']:
                    for agent_id in choice['include']:
                        if agent_id not in registry_ids:
                            raise ValueError(f"Group '{group['name']}' choice '{choice['id']}' references unknown agent '{agent_id}'")
    
    def _apply_dependencies(self, selected: Set[str]) -> bool:
        """Check if selection satisfies dependency rules."""
        for dep in self.spec['dependencies']:
            if_includes = dep['if_includes']
            must_include = dep['must_include']
            if any(agent_id in selected for agent_id in if_includes):
                if not all(agent_id in selected for agent_id in must_include):
                    return False
        return True
    
    def _generate_candidates(self) -> List[dict]:
        """Generate all valid candidates with streaming and early-stop."""
        candidates = []
        max_candidates = self.spec['limits']['max_candidates_small']
        must_have = self.spec['must_have']
        
        # Build option lists per group
        group_options: List[List[List[str]]] = []
        for group in self.spec['option_groups']:
            if group['mode'] == 'toggle':
                options = [[], group['agents']]
            elif group['mode'] == 'choose_one':
                options = [choice['include'] for choice in group['choices']]
            else:
                options = [[]]
            group_options.append(options)
        
        # Recursive generator with early-stop
        def generate_selections(group_idx: int, current_selection: List[str]) -> None:
            if len(candidates) >= max_candidates:
                return
            
            if group_idx >= len(group_options):
                selected_set = set(current_selection)
                if not self._apply_dependencies(selected_set):
                    return
                is_valid, errors = validate_combo(selected_set, self.registry)
                if not is_valid:
                    return
                selected_sorted = sorted(list(selected_set))
                candidate = selected_agents_to_candidate(selected_sorted, max_steps=4)
                candidates.append(candidate)
                return
            
            for option_agents in group_options[group_idx]:
                if len(candidates) >= max_candidates:
                    return
                merged_selection = current_selection + option_agents
                generate_selections(group_idx + 1, merged_selection)
        
        generate_selections(0, must_have)
        return candidates
    
    def default_candidate(self) -> dict:
        """Generate default candidate from spec defaults."""
        selected = list(self.spec['must_have'])
        defaults_selected = self.spec['defaults']['selected']
        
        for item in defaults_selected:
            if not isinstance(item, dict):
                raise ValueError(f"defaults.selected item must be dict, got {type(item)}")
            
            for group_name, selection_value in item.items():
                group = None
                for g in self.spec['option_groups']:
                    if g['name'] == group_name:
                        group = g
                        break
                
                if group is None:
                    raise ValueError(f"defaults.selected references unknown group '{group_name}'")
                
                if group['mode'] == 'toggle':
                    # Accept both string and boolean values
                    if selection_value in ['on', True]:
                        selected.extend(group['agents'])
                    elif selection_value not in ['off', False]:
                        raise ValueError(f"Toggle group '{group_name}' default must be 'on'/'off' or True/False, got '{selection_value}'")
                elif group['mode'] == 'choose_one':
                    choice = None
                    for c in group['choices']:
                        if c['id'] == selection_value:
                            choice = c
                            break
                    if choice is None:
                        raise ValueError(f"defaults.selected for group '{group_name}' references unknown choice '{selection_value}'")
                    selected.extend(choice['include'])
        
        selected_set = set(selected)
        if not self._apply_dependencies(selected_set):
            raise ValueError("Default candidate violates dependency rules")
        is_valid, errors = validate_combo(selected_set, self.registry)
        if not is_valid:
            raise ValueError(f"Default candidate violates registry constraints: {errors}")
        
        selected_sorted = sorted(list(selected_set))
        candidate = selected_agents_to_candidate(selected_sorted, max_steps=4)
        return candidate
    
    def all_candidates_small(self) -> List[dict]:
        """Generate all valid candidates bounded by max_candidates_small."""
        if self._candidates_cache is None:
            self._candidates_cache = self._generate_candidates()
        return self._candidates_cache
    
    def candidate_to_name(self, c: dict) -> str:
        """Convert candidate dict to stable short name."""
        selected_agents = c.get('selected_agents', [])
        selected_sorted = sorted(selected_agents)
        hash_input = "|".join(selected_sorted)
        hash_digest = hashlib.md5(hash_input.encode('utf-8')).hexdigest()
        hash8 = hash_digest[:8]
        
        candidates = self.all_candidates_small()
        try:
            idx = candidates.index(c)
        except ValueError:
            idx = 0
        
        case_upper = self.case_id.upper().replace('_', '-')
        return f"{case_upper}-{idx:03d}-{hash8}"
