"""Agent registry management."""

import os
import yaml
from datetime import datetime
from .limits import validate_agent_yaml_size


REGISTRY_DIR = "demos/portfolio_langgraph_opt/src/agents/registry"
DELETED_DIR = "demos/portfolio_langgraph_opt/src/agents/registry/_deleted"


def list_agents():
    """List all active agents from registry."""
    try:
        agents = []
        
        if not os.path.exists(REGISTRY_DIR):
            return {"agents": [], "total": 0, "errors": []}
        
        for filename in os.listdir(REGISTRY_DIR):
            if filename.endswith('.yaml') and not filename.startswith('_'):
                filepath = os.path.join(REGISTRY_DIR, filename)
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
                    pass  # Skip invalid files
        
        return {"agents": agents, "total": len(agents), "errors": []}
    
    except Exception as e:
        return {"agents": [], "total": 0, "errors": [str(e)]}


def upsert_agents(yaml_text):
    """Insert or update agents from YAML text."""
    try:
        validate_agent_yaml_size(yaml_text)
        
        data = yaml.safe_load(yaml_text)
        if not data:
            return {"success": False, "updated": [], "errors": ["Empty YAML"]}
        
        # Handle single agent or list
        if isinstance(data, dict):
            agents = [data]
        elif isinstance(data, list):
            agents = data
        else:
            return {"success": False, "updated": [], "errors": ["YAML must be dict or list"]}
        
        os.makedirs(REGISTRY_DIR, exist_ok=True)
        
        updated = []
        errors = []
        
        for agent_data in agents:
            try:
                agent_id = agent_data.get('id')
                if not agent_id:
                    errors.append("Agent missing 'id' field")
                    continue
                
                filepath = os.path.join(REGISTRY_DIR, f"{agent_id}.yaml")
                with open(filepath, 'w') as f:
                    yaml.dump(agent_data, f, default_flow_style=False)
                
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


def soft_delete_agents(agent_ids):
    """Soft-delete agents by moving to _deleted/ directory."""
    try:
        os.makedirs(DELETED_DIR, exist_ok=True)
        
        deleted = []
        errors = []
        
        for agent_id in agent_ids:
            try:
                src_path = os.path.join(REGISTRY_DIR, f"{agent_id}.yaml")
                if not os.path.exists(src_path):
                    errors.append(f"Agent {agent_id} not found")
                    continue
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dst_path = os.path.join(DELETED_DIR, f"{timestamp}__{agent_id}.yaml")
                
                os.rename(src_path, dst_path)
                deleted.append(agent_id)
            
            except Exception as e:
                errors.append(f"Failed to delete {agent_id}: {str(e)}")
        
        return {
            "success": len(errors) == 0,
            "deleted": deleted,
            "errors": errors
        }
    
    except Exception as e:
        return {"success": False, "deleted": [], "errors": [str(e)]}
