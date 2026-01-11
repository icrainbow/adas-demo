#!/usr/bin/env python3
"""
Generate YAML registry files for all agents used in the portfolio LangGraph demo.

This script creates YAML files in:
demos/portfolio_langgraph_opt/src/agents/registry/

IDEMPOTENT: Only creates files that don't exist. Skips existing files.

Each YAML follows the AgentDef schema defined in registry_schema.py.
"""

import os
import yaml


# Agent specifications matching the demo's existing toggles and variants
AGENT_SPECS = [
    # Processing nodes
    {
        "id": "retriever",
        "version": "1.0.0",
        "stage": "processing",
        "node_type": "node",
        "enabled_by_default": False,
        "description": "Policy text retriever that matches relevant policy lines to case keywords",
        "params": {
            "matching_algorithm": "keyword",
            "max_results": 5
        },
        "constraints": {
            "requires": [],
            "requires_any": [],
            "mutex_with": [],
            "only_with": [],
            "at_most_one_group": ""
        },
        "ordering": {
            "priority": 100,
            "depends_on": [],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 150,
            "relative_latency": 1.2,
            "complexity": "low"
        }
    },
    {
        "id": "risk_decompose",
        "version": "1.0.0",
        "stage": "processing",
        "node_type": "node",
        "enabled_by_default": False,
        "description": "Risk decomposition - identifies risk factors and dimensions in case",
        "params": {
            "dimensions": ["liquidity", "concentration", "leverage", "suitability"]
        },
        "constraints": {
            "requires": [],
            "requires_any": [],
            "mutex_with": [],
            "only_with": [],
            "at_most_one_group": ""
        },
        "ordering": {
            "priority": 200,
            "depends_on": [],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 250,
            "relative_latency": 1.3,
            "complexity": "medium"
        }
    },
    {
        "id": "behavior_check",
        "version": "1.0.0",
        "stage": "processing",
        "node_type": "node",
        "enabled_by_default": False,
        "description": "Behavioral pattern analysis - checks for known violation patterns",
        "params": {
            "pattern_library": "standard",
            "threshold": 0.7
        },
        "constraints": {
            "requires": [],
            "requires_any": [],
            "mutex_with": [],
            "only_with": [],
            "at_most_one_group": ""
        },
        "ordering": {
            "priority": 250,
            "depends_on": [],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 200,
            "relative_latency": 1.1,
            "complexity": "medium"
        }
    },
    {
        "id": "hitl_gate",
        "version": "1.0.0",
        "stage": "processing",
        "node_type": "node",
        "enabled_by_default": False,
        "description": "Human-in-the-loop gate - escalates uncertain cases to human review",
        "params": {
            "confidence_threshold": 0.8,
            "escalation_criteria": ["ambiguous_policy", "high_stakes"]
        },
        "constraints": {
            "requires": [],
            "requires_any": [],
            "mutex_with": ["carryover_full"],
            "only_with": [],
            "at_most_one_group": ""
        },
        "ordering": {
            "priority": 280,
            "depends_on": [],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 50,
            "relative_latency": 1.0,
            "complexity": "low"
        }
    },
    
    # Synthesis styles (at_most_one_group: synth_style)
    {
        "id": "synth_style_A",
        "version": "1.0.0",
        "stage": "synthesis",
        "node_type": "style",
        "enabled_by_default": True,
        "description": "Synthesis style A - structured rubric-driven response generation",
        "params": {
            "format": "structured",
            "rubric_driven": True,
            "verbosity": "medium"
        },
        "constraints": {
            "requires": [],
            "requires_any": [],
            "mutex_with": ["synth_style_B"],
            "only_with": [],
            "at_most_one_group": "synth_style"
        },
        "ordering": {
            "priority": 400,
            "depends_on": [],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 300,
            "relative_latency": 1.0,
            "complexity": "medium"
        }
    },
    {
        "id": "synth_style_B",
        "version": "1.0.0",
        "stage": "synthesis",
        "node_type": "style",
        "enabled_by_default": False,
        "description": "Synthesis style B - narrative-focused response generation",
        "params": {
            "format": "narrative",
            "rubric_driven": False,
            "verbosity": "high"
        },
        "constraints": {
            "requires": [],
            "requires_any": [],
            "mutex_with": ["synth_style_A"],
            "only_with": [],
            "at_most_one_group": "synth_style"
        },
        "ordering": {
            "priority": 400,
            "depends_on": [],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 350,
            "relative_latency": 1.1,
            "complexity": "medium"
        }
    },
    
    # Carryover strategies (at_most_one_group: carryover)
    {
        "id": "carryover_none",
        "version": "1.0.0",
        "stage": "strategy",
        "node_type": "policy",
        "enabled_by_default": False,
        "description": "No carryover - each step starts fresh without previous context",
        "params": {
            "carryover_mode": "none",
            "context_window": 0
        },
        "constraints": {
            "requires": [],
            "requires_any": [],
            "mutex_with": ["carryover_compact", "carryover_full"],
            "only_with": [],
            "at_most_one_group": "carryover"
        },
        "ordering": {
            "priority": 50,
            "depends_on": [],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 0,
            "relative_latency": 1.0,
            "complexity": "low"
        }
    },
    {
        "id": "carryover_compact",
        "version": "1.0.0",
        "stage": "strategy",
        "node_type": "policy",
        "enabled_by_default": True,
        "description": "Compact carryover - passes summarized context between steps",
        "params": {
            "carryover_mode": "compact",
            "context_window": 2,
            "summarization": "key_points"
        },
        "constraints": {
            "requires": [],
            "requires_any": [],
            "mutex_with": ["carryover_none", "carryover_full"],
            "only_with": [],
            "at_most_one_group": "carryover"
        },
        "ordering": {
            "priority": 50,
            "depends_on": [],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 100,
            "relative_latency": 1.1,
            "complexity": "low"
        }
    },
    {
        "id": "carryover_full",
        "version": "1.0.0",
        "stage": "strategy",
        "node_type": "policy",
        "enabled_by_default": False,
        "description": "Full carryover - passes complete context history between steps",
        "params": {
            "carryover_mode": "full",
            "context_window": -1,
            "summarization": "none"
        },
        "constraints": {
            "requires": [],
            "requires_any": [],
            "mutex_with": ["carryover_none", "carryover_compact", "hitl_gate"],
            "only_with": [],
            "at_most_one_group": "carryover"
        },
        "ordering": {
            "priority": 50,
            "depends_on": [],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 300,
            "relative_latency": 1.3,
            "complexity": "medium"
        }
    },
    
    # Adaptive toggle (at_most_one_group: adaptive)
    {
        "id": "adaptive_off",
        "version": "1.0.0",
        "stage": "strategy",
        "node_type": "policy",
        "enabled_by_default": True,
        "description": "Adaptive disabled - static graph topology for all cases",
        "params": {
            "adaptive_enabled": False
        },
        "constraints": {
            "requires": [],
            "requires_any": [],
            "mutex_with": ["adaptive_on"],
            "only_with": [],
            "at_most_one_group": "adaptive"
        },
        "ordering": {
            "priority": 300,
            "depends_on": [],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 0,
            "relative_latency": 1.0,
            "complexity": "low"
        }
    },
    {
        "id": "adaptive_on",
        "version": "1.0.0",
        "stage": "strategy",
        "node_type": "policy",
        "enabled_by_default": False,
        "description": "Adaptive subgraphs enabled - dynamic topology based on case signals",
        "params": {
            "adaptive_enabled": True,
            "available_subgraphs": ["liquidity", "concentration", "leverage", "suitability"]
        },
        "constraints": {
            "requires": ["risk_decompose"],
            "requires_any": [],
            "mutex_with": ["adaptive_off"],
            "only_with": [],
            "at_most_one_group": "adaptive"
        },
        "ordering": {
            "priority": 300,
            "depends_on": [],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 100,
            "relative_latency": 1.5,
            "complexity": "high"
        }
    },
    
    # Adaptive policies (at_most_one_group: adaptive_policy)
    {
        "id": "adaptive_policy_strict",
        "version": "1.0.0",
        "stage": "strategy",
        "node_type": "policy",
        "enabled_by_default": False,
        "description": "Strict adaptive policy - conservative subgraph selection",
        "params": {
            "policy": "strict",
            "threshold": 0.8,
            "fallback": "reject"
        },
        "constraints": {
            "requires": ["adaptive_on"],
            "requires_any": [],
            "mutex_with": ["adaptive_policy_lenient"],
            "only_with": [],
            "at_most_one_group": "adaptive_policy"
        },
        "ordering": {
            "priority": 310,
            "depends_on": ["adaptive_on"],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 50,
            "relative_latency": 1.0,
            "complexity": "low"
        }
    },
    {
        "id": "adaptive_policy_lenient",
        "version": "1.0.0",
        "stage": "strategy",
        "node_type": "policy",
        "enabled_by_default": False,
        "description": "Lenient adaptive policy - permissive subgraph selection",
        "params": {
            "policy": "lenient",
            "threshold": 0.5,
            "fallback": "default"
        },
        "constraints": {
            "requires": ["adaptive_on"],
            "requires_any": [],
            "mutex_with": ["adaptive_policy_strict"],
            "only_with": [],
            "at_most_one_group": "adaptive_policy"
        },
        "ordering": {
            "priority": 310,
            "depends_on": ["adaptive_on"],
            "before": []
        },
        "cost_hint": {
            "tokens_per_case": 50,
            "relative_latency": 1.0,
            "complexity": "low"
        }
    }
]


def generate_yaml_files():
    """Generate YAML files for all agent specs (idempotent - skip existing)."""
    output_dir = "demos/portfolio_langgraph_opt/src/agents/registry"
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    created_files = []
    skipped_files = []
    
    for spec in AGENT_SPECS:
        agent_id = spec["id"]
        output_path = os.path.join(output_dir, f"{agent_id}.yaml")
        
        # Skip if file already exists (idempotent behavior)
        if os.path.exists(output_path):
            skipped_files.append(f"{agent_id}.yaml")
            continue
        
        # Write YAML with clean formatting
        with open(output_path, 'w') as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        created_files.append(f"{agent_id}.yaml")
    
    return created_files, skipped_files


def main():
    """Main entry point."""
    print("=" * 70)
    print("Generating Agent Registry YAML Files (Idempotent)")
    print("=" * 70)
    
    created_files, skipped_files = generate_yaml_files()
    
    if created_files:
        print(f"\n✓ Created {len(created_files)} YAML file(s):\n")
        for filename in sorted(created_files):
            print(f"  - {filename}")
    else:
        print(f"\n✓ Created 0 YAML files (all already exist)")
    
    if skipped_files:
        print(f"\n⊘ Skipped (already existed): {len(skipped_files)} file(s):\n")
        for filename in sorted(skipped_files):
            print(f"  - {filename}")
    
    print(f"\nOutput directory: demos/portfolio_langgraph_opt/src/agents/registry/")
    print("=" * 70)


if __name__ == "__main__":
    main()
