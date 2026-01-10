"""
Convert wiring descriptors to DOT (Graphviz) format for visualization.
"""


def wiring_to_dot(wiring: dict) -> str:
    """
    Convert a wiring descriptor to DOT/Graphviz format.
    
    Args:
        wiring: Wiring descriptor dict with nodes, edges, clusters, meta
        
    Returns:
        DOT format string
    """
    lines = []
    
    # Header
    candidate_name = wiring.get("meta", {}).get("candidate_name", "Graph")
    lines.append(f'digraph "{candidate_name}" {{')
    lines.append('  rankdir=LR;')
    lines.append('  node [fontname="Arial", fontsize=10];')
    lines.append('  edge [fontname="Arial", fontsize=9];')
    lines.append('')
    
    # Process clusters first (as subgraphs)
    clusters = wiring.get("clusters", [])
    cluster_nodes = set()
    for i, cluster in enumerate(clusters):
        cluster_id = cluster.get("id", f"cluster_{i}")
        cluster_label = cluster.get("label", cluster_id)
        node_ids = cluster.get("node_ids", [])
        cluster_nodes.update(node_ids)
        
        style = cluster.get("style", {})
        color = style.get("color", "lightgrey")
        
        lines.append(f'  subgraph cluster_{cluster_id} {{')
        lines.append(f'    label="{cluster_label}";')
        lines.append(f'    style=dashed;')
        lines.append(f'    color="{color}";')
        lines.append('')
        
        # Add nodes in this cluster
        for node_id in node_ids:
            lines.append(f'    {_quote_id(node_id)};')
        
        lines.append('  }')
        lines.append('')
    
    # Process nodes
    nodes = wiring.get("nodes", [])
    for node in nodes:
        node_id = node.get("id", "unknown")
        node_label = node.get("label", node_id)
        node_kind = node.get("kind", "default")
        enabled = node.get("enabled", True)
        
        # Skip cluster nodes (already added in subgraph)
        if node_id in cluster_nodes:
            continue
        
        # Determine node attributes based on kind and enabled status
        attrs = _get_node_attrs(node_kind, enabled)
        
        # Build node statement
        attr_str = ", ".join(f'{k}="{v}"' for k, v in attrs.items())
        lines.append(f'  {_quote_id(node_id)} [{attr_str}, label="{node_label}"];')
    
    lines.append('')
    
    # Process edges
    edges = wiring.get("edges", [])
    for edge in edges:
        from_node = edge.get("from", "unknown")
        to_node = edge.get("to", "unknown")
        edge_kind = edge.get("kind", "main")
        edge_label = edge.get("label")
        
        # Determine edge attributes
        edge_attrs = _get_edge_attrs(edge_kind)
        
        if edge_label:
            edge_attrs["label"] = edge_label
        
        # Build edge statement
        if edge_attrs:
            attr_str = ", ".join(f'{k}="{v}"' for k, v in edge_attrs.items())
            lines.append(f'  {_quote_id(from_node)} -> {_quote_id(to_node)} [{attr_str}];')
        else:
            lines.append(f'  {_quote_id(from_node)} -> {_quote_id(to_node)};')
    
    lines.append('}')
    
    return '\n'.join(lines)


def _quote_id(node_id: str) -> str:
    """Quote node ID if it contains special characters."""
    if any(c in node_id for c in [' ', '-', '.']):
        return f'"{node_id}"'
    return node_id


def _get_node_attrs(kind: str, enabled: bool) -> dict:
    """Get node attributes based on kind and enabled status."""
    attrs = {}
    
    # Base shape by kind
    if kind == "control":
        attrs["shape"] = "circle"
        attrs["fillcolor"] = "lightgrey"
    elif kind == "processing":
        attrs["shape"] = "box"
        attrs["fillcolor"] = "lightblue"
    elif kind == "synthesis":
        attrs["shape"] = "box"
        attrs["fillcolor"] = "lightgreen"
    elif kind == "adaptive":
        attrs["shape"] = "box"
        attrs["fillcolor"] = "lightyellow"
    else:
        attrs["shape"] = "box"
        attrs["fillcolor"] = "white"
    
    # Style based on enabled
    if enabled:
        attrs["style"] = "filled"
        attrs["color"] = "black"
    else:
        attrs["style"] = "dashed,filled"
        attrs["color"] = "grey"
        attrs["fillcolor"] = "white"
        attrs["fontcolor"] = "grey"
    
    return attrs


def _get_edge_attrs(kind: str) -> dict:
    """Get edge attributes based on kind."""
    attrs = {}
    
    if kind == "main":
        attrs["color"] = "black"
        attrs["style"] = "solid"
    elif kind == "adaptive":
        attrs["color"] = "blue"
        attrs["style"] = "dashed"
    elif kind == "conditional":
        attrs["color"] = "orange"
        attrs["style"] = "dashed"
    
    return attrs
