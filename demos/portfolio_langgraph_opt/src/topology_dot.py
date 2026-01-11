"""Generate Graphviz DOT from candidate configuration.

DRIFT GUARD:
topology_dot.py mirrors the wiring logic in graph_builder.py.
If you modify graph_builder.py control flow or node ordering:
  1. Update generate_dot() function to match
  2. Update unit tests in tests/test_topology_dot.py
  3. Run tests to verify consistency
"""


def generate_dot(candidate):
    """
    Generate Graphviz DOT from candidate configuration.
    
    Mirrors the wiring logic in graph_builder.py.
    
    Args:
        candidate: Candidate dict with flags:
            - use_retriever: bool
            - use_risk_decompose: bool
            - use_behavior_check: bool
            - use_hitl_gate: bool
            - synth_style: "A" | "B"
            - adaptive: bool
            - adaptive_policy: "strict" | "lenient"
            - carryover: "none" | "compact" | "full"
            - max_steps: int
    
    Returns:
        DOT string compatible with Graphviz
    """
    nodes = []
    edges = []
    
    # Start node
    nodes.append('START [shape=circle, label="START"]')
    current = "START"
    
    # Retriever (optional)
    if candidate.get("use_retriever"):
        nodes.append('retriever [shape=box, fillcolor=lightblue, style=filled, label="Retriever"]')
        edges.append(f'{current} -> retriever')
        current = "retriever"
    
    # Risk decompose (optional)
    if candidate.get("use_risk_decompose"):
        nodes.append('risk_decompose [shape=box, fillcolor=lightblue, style=filled, label="Risk\\nDecompose"]')
        edges.append(f'{current} -> risk_decompose')
        current = "risk_decompose"
    
    # Behavior check (optional)
    if candidate.get("use_behavior_check"):
        nodes.append('behavior_check [shape=box, fillcolor=lightblue, style=filled, label="Behavior\\nCheck"]')
        edges.append(f'{current} -> behavior_check')
        current = "behavior_check"
    
    # Adaptive subgraph (if enabled)
    current_adaptive = None
    if candidate.get("adaptive"):
        policy = candidate.get("adaptive_policy", "strict")
        nodes.append(f'adaptive_subgraph [shape=box, fillcolor=lightyellow, style=filled, label="Adaptive\\nSubgraph\\n({policy})"]')
        edges.append(f'{current} -> adaptive_subgraph [style=dashed, color=orange, label="conditional"]')
        current_adaptive = "adaptive_subgraph"
    
    # HITL gate (optional)
    if candidate.get("use_hitl_gate"):
        nodes.append('hitl_gate [shape=diamond, fillcolor=lightcoral, style=filled, label="HITL\\nGate"]')
        if current_adaptive:
            edges.append(f'{current_adaptive} -> hitl_gate')
            edges.append(f'{current} -> hitl_gate [style=dashed]')
        else:
            edges.append(f'{current} -> hitl_gate')
        current = "hitl_gate"
        current_adaptive = None
    
    # Synthesis (always present)
    synth_style = candidate.get("synth_style", "A")
    carryover = candidate.get("carryover", "compact")
    nodes.append(f'synth [shape=box, fillcolor=lightgreen, style=filled, label="Synthesis\\nStyle {synth_style}\\n(carryover: {carryover})"]')
    
    if current_adaptive:
        edges.append(f'{current_adaptive} -> synth')
        edges.append(f'{current} -> synth [style=dashed]')
    else:
        edges.append(f'{current} -> synth')
    
    # End node
    nodes.append('END [shape=doublecircle, label="END"]')
    edges.append('synth -> END')
    
    # Build DOT
    dot = ['digraph G {']
    dot.append('  rankdir=LR;')
    dot.append('  node [fontname="Arial"];')
    dot.append('')
    
    for node in nodes:
        dot.append(f'  {node};')
    
    dot.append('')
    
    for edge in edges:
        dot.append(f'  {edge};')
    
    dot.append('}')
    
    return '\n'.join(dot)
