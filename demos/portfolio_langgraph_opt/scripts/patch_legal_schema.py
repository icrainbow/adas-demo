#!/usr/bin/env python3
"""
Quick patch: Add missing schema fields to all legal_case agents
"""
import yaml
from pathlib import Path

LEGAL_DIR = Path("/Users/shenyanran/Dev/AdasDemo/ADAS/demos/portfolio_langgraph_opt/src/cases/legal_case/agents")

# Default values for missing fields
DEFAULTS = {
    "version": "1.0.0",
    "stage": "processing",
    "node_type": "processor",
    "enabled_by_default": True,
    "params": {
        "model": "gpt-4",
        "temperature": 0.1
    },
    "constraints": {
        "requires": [],
        "requires_any": [],
        "mutex_with": [],
        "only_with": [],
        "at_most_one_group": None
    },
    "ordering": {
        "must_come_before": [],
        "must_come_after": []
    },
    "cost_hint": {
        "token_multiplier": 1.0,
        "time_estimate_seconds": 2
    }
}

count = 0
for yaml_file in sorted(LEGAL_DIR.glob("*.yaml")):
    with open(yaml_file, 'r') as f:
        data = yaml.safe_load(f)
    
    # Add missing fields
    modified = False
    for key, default_value in DEFAULTS.items():
        if key not in data:
            data[key] = default_value
            modified = True
    
    if modified:
        with open(yaml_file, 'w') as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
        count += 1
        print(f"✅ Patched: {yaml_file.name}")

print(f"\n✅ Patched {count} files")
