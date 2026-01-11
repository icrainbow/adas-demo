#!/usr/bin/env python3
"""
全面修复 legal_case agents YAML - 使其符合 KYC schema
"""
import yaml
from pathlib import Path

LEGAL_DIR = Path("/Users/shenyanran/Dev/AdasDemo/ADAS/demos/portfolio_langgraph_opt/src/cases/legal_case/agents")

VALID_STAGES = ['preprocessing', 'processing', 'synthesis', 'strategy']

# Role -> stage 映射
ROLE_TO_STAGE = {
    'preprocessing': 'preprocessing',
    'extraction': 'processing',
    'verification': 'processing',
    'synthesis': 'synthesis',
    'quality': 'processing',
    'risk': 'processing',
    'advisory': 'synthesis'
}

for yaml_file in sorted(LEGAL_DIR.glob("*.yaml")):
    with open(yaml_file, 'r') as f:
        data = yaml.safe_load(f)
    
    # Fix stage based on role
    role = data.get('role', '')
    if 'stage' not in data or data['stage'] not in VALID_STAGES:
        data['stage'] = ROLE_TO_STAGE.get(role, 'processing')
    
    # Ensure correct field order and values
    if 'version' not in data:
        data['version'] = '1.0.0'
    
    if 'node_type' not in data or data['node_type'] not in ['node', 'style', 'strategy', 'policy']:
        data['node_type'] = 'node'
    
    if 'enabled_by_default' not in data:
        data['enabled_by_default'] = False
    
    if 'description' not in data:
        data['description'] = data.get('purpose', 'Legal agent')
    
    # Fix params
    if 'params' not in data:
        data['params'] = {}
    if not data['params']:
        data['params'] = {'model': 'gpt-4', 'temperature': 0.1}
    
    # Fix constraints
    if 'constraints' not in data:
        data['constraints'] = {}
    for key in ['requires', 'requires_any', 'mutex_with', 'only_with']:
        if key not in data['constraints']:
            data['constraints'][key] = []
    # at_most_one_group should be empty string or absent
    if 'at_most_one_group' in data['constraints']:
        if data['constraints']['at_most_one_group'] is None:
            data['constraints']['at_most_one_group'] = ''
    else:
        data['constraints']['at_most_one_group'] = ''
    
    # Fix ordering
    if 'ordering' not in data:
        data['ordering'] = {}
    if 'priority' not in data['ordering']:
        data['ordering']['priority'] = 100
    for key in ['depends_on', 'before']:
        if key not in data['ordering']:
            data['ordering'][key] = []
    # Remove old keys
    for old_key in ['must_come_before', 'must_come_after']:
        if old_key in data['ordering']:
            del data['ordering'][old_key]
    
    # Fix cost_hint
    if 'cost_hint' not in data:
        data['cost_hint'] = {}
    if 'tokens_per_case' not in data['cost_hint']:
        tokens_hint = data.get('token_budget_hint', 1500)
        data['cost_hint']['tokens_per_case'] = int(tokens_hint * 0.1)
    if 'relative_latency' not in data['cost_hint']:
        data['cost_hint']['relative_latency'] = 1.0
    if 'complexity' not in data['cost_hint']:
        data['cost_hint']['complexity'] = 'medium'
    # Remove old keys
    for old_key in ['token_multiplier', 'time_estimate_seconds']:
        if old_key in data['cost_hint']:
            del data['cost_hint'][old_key]
    
    # Write back
    with open(yaml_file, 'w') as f:
        yaml.dump(data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
    
    print(f"✅ Fixed: {yaml_file.name} (stage={data['stage']}, role={data.get('role')})")

print(f"\n✅ All {len(list(LEGAL_DIR.glob('*.yaml')))} legal agents fixed to match KYC schema")
