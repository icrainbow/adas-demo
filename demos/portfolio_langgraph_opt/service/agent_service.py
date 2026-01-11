"""Agent registry management."""

import os
import re
import yaml
from typing import Optional
from .limits import validate_agent_yaml_size
from .case_service import validate_case_id, case_root, get_default_case_id


REGISTRY_DIR = "demos/portfolio_langgraph_opt/src/agents/registry"


def _agent_dir_for(case_id: Optional[str]) -> str:
    """
    Resolution:
    - If case_id provided: src/cases/<case_id>/agents
    - Else if default_case_id exists: src/cases/<default>/agents
    - Else: legacy REGISTRY_DIR
    """
    if case_id is not None:
        if not validate_case_id(case_id):
            raise ValueError(f"Invalid case_id format: {case_id}")
        return str((case_root(case_id) / "agents").resolve())

    default_cid = get_default_case_id()
    if default_cid:
        return str((case_root(default_cid) / "agents").resolve())

    return REGISTRY_DIR


def list_agents(case_id: Optional[str] = None):
    """List all active agents from registry or case."""
    try:
        agents_dir = _agent_dir_for(case_id)
        agents = []
        errors = []
        
        if not os.path.exists(agents_dir):
            return {"agents": [], "total": 0, "errors": []}
        
        for filename in os.listdir(agents_dir):
            if filename.endswith('.yaml') and not filename.startswith('_'):
                filepath = os.path.join(agents_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        agent_data = yaml.safe_load(f)
                    
                    if agent_data:
                        agents.append({
                            "id": agent_data.get("id", ""),
                            "name": agent_data.get("name", agent_data.get("id", "")),
                            "purpose": agent_data.get("purpose", ""),
                            "role": agent_data.get("role", ""),
                            "inputs": agent_data.get("inputs", []),
                            "outputs": agent_data.get("outputs", []),
                            "token_budget_hint": agent_data.get("token_budget_hint", 0)
                        })
                except Exception as e:
                    errors.append(f"{filename}: {str(e)}")
        
        # Sort by id for deterministic output
        agents.sort(key=lambda a: a["id"])
        
        return {"agents": agents, "total": len(agents), "errors": errors}
    
    except Exception as e:
        return {"agents": [], "total": 0, "errors": [str(e)]}


def upsert_agents(yaml_text: str, case_id: Optional[str] = None):
    """Insert or update agents from YAML text."""
    try:
        validate_agent_yaml_size(yaml_text)
        
        data = yaml.safe_load(yaml_text)
        if not data:
            return {"success": False, "updated": [], "errors": ["Empty YAML"]}
        
        # Determine target directory
        target_dir = _agent_dir_for(case_id)
        
        # Handle single agent or list
        if isinstance(data, dict):
            agents = [data]
        elif isinstance(data, list):
            agents = data
        else:
            return {"success": False, "updated": [], "errors": ["YAML must be dict or list"]}
        
        os.makedirs(target_dir, exist_ok=True)
        
        updated = []
        errors = []
        
        for agent_data in agents:
            try:
                agent_id = agent_data.get('id')
                if not agent_id:
                    errors.append("Agent missing 'id' field")
                    continue
                
                # Validate agent_id format
                if not re.match(r'^[A-Za-z0-9_-]+$', agent_id):
                    errors.append(f"Invalid agent ID format: {agent_id}")
                    continue
                
                filepath = os.path.join(target_dir, f"{agent_id}.yaml")
                with open(filepath, 'w') as f:
                    yaml.dump(agent_data, f, default_flow_style=False, sort_keys=False)
                
                updated.append(agent_id)
            except Exception as e:
                errors.append(f"Failed to save {agent_data.get('id', '?')}: {str(e)}")
        
        return {
            "success": len(errors) == 0,
            "updated": updated,
            "errors": errors
        }
    
    except Exception as e:
        return {"success": False, "updated": [], "errors": [str(e)]}


def delete_agents(agent_ids: list, case_id: Optional[str] = None):
    """Hard delete agents by removing YAML files from registry or case."""
    try:
        target_dir = _agent_dir_for(case_id)
    except Exception as e:
        return {"success": False, "deleted": [], "errors": [str(e)]}
    
    deleted = []
    errors = []
    
    for agent_id in agent_ids:
        # Sanitize agent_id to prevent path traversal
        if not re.match(r'^[A-Za-z0-9_-]+$', agent_id):
            errors.append(f"Invalid agent ID format: {agent_id}")
            continue
        
        filepath = os.path.join(target_dir, f"{agent_id}.yaml")
        
        if not os.path.exists(filepath):
            errors.append(f"Agent {agent_id} not found")
            continue
        
        try:
            os.remove(filepath)
            deleted.append(agent_id)
        except Exception as e:
            errors.append(f"Failed to delete {agent_id}: {str(e)}")
    
    return {
        "success": len(errors) == 0,
        "deleted": deleted,
        "errors": errors
    }
