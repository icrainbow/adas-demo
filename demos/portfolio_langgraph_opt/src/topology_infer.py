from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple
import yaml


MAX_NODES = 64
MAX_EDGES = 256
MAX_DOT_BYTES = 25_000


def build_candidate_dot(candidate_name: str, selected_agents: List[str], registry_dir: str) -> str:
    """
    Build a Graphviz DOT topology using registry YAML inputs/outputs.
    Deterministic, bounded, visualization-only.
    """
    agents = list(selected_agents or [])

    # Hard cap node count to avoid runaway DOT
    if len(agents) + 2 > MAX_NODES:
        agents = agents[: (MAX_NODES - 2)]

    io_map = _load_io_map(registry_dir)

    # Build edges based on IO overlap, respecting selected order
    edges: List[Tuple[str, str]] = []
    produced_by: Dict[str, Set[str]] = {}  # output_token -> set(agent_id)

    # Prime produced_by with outputs from previous agents as we walk
    for i, agent_id in enumerate(agents):
        ins = set(io_map.get(agent_id, {}).get("inputs", []))
        # find producers among earlier agents by checking overlap with their outputs
        producers: Set[str] = set()
        if ins:
            for token in ins:
                producers |= produced_by.get(token, set())

        if producers:
            # deterministic order: earlier selected order
            for p in agents[:i]:
                if p in producers:
                    edges.append((p, agent_id))
        else:
            edges.append(("entry", agent_id))

        # record this agent's outputs as available for later consumers
        outs = set(io_map.get(agent_id, {}).get("outputs", []))
        for token in outs:
            produced_by.setdefault(token, set()).add(agent_id)

    # Add sink -> end edges
    out_degree: Dict[str, int] = {a: 0 for a in agents}
    in_degree: Dict[str, int] = {a: 0 for a in agents}

    for s, t in edges:
        if s in out_degree:
            out_degree[s] += 1
        if t in in_degree:
            in_degree[t] += 1

    sinks = [a for a in agents if out_degree.get(a, 0) == 0]
    for s in sinks:
        edges.append((s, "end"))

    # Enforce edge cap deterministically
    if len(edges) > MAX_EDGES:
        edges = edges[:MAX_EDGES]

    dot = _to_dot(candidate_name=candidate_name, agents=agents, edges=edges)

    b = len(dot.encode("utf-8"))
    if b > MAX_DOT_BYTES:
        raise ValueError(f"DOT too large: {b} bytes (cap {MAX_DOT_BYTES}).")
    return dot


def _load_io_map(registry_dir: str) -> Dict[str, Dict[str, List[str]]]:
    """
    Load id -> {inputs:[], outputs:[]} from YAML files in registry_dir.
    Backward compatible: missing fields become [].
    """
    base = Path(registry_dir)
    if not base.exists() or not base.is_dir():
        return {}

    io_map: Dict[str, Dict[str, List[str]]] = {}

    for p in sorted(base.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}

        agent_id = data.get("id") or p.stem
        inputs = data.get("inputs") or []
        outputs = data.get("outputs") or []

        # Normalize to list[str]
        if not isinstance(inputs, list):
            inputs = []
        if not isinstance(outputs, list):
            outputs = []

        inputs = [str(x) for x in inputs]
        outputs = [str(x) for x in outputs]

        io_map[str(agent_id)] = {"inputs": inputs, "outputs": outputs}

    return io_map


def _to_dot(candidate_name: str, agents: List[str], edges: List[Tuple[str, str]]) -> str:
    lines: List[str] = []
    lines.append("digraph Topology {")
    lines.append("  rankdir=LR;")
    safe_label = str(candidate_name).replace('"', '\\"')
    lines.append(f'  labelloc="t"; label="{safe_label} ({len(agents)} agents)";')
    lines.append('  node [shape=box];')
    lines.append('  entry [label="Start"];')
    lines.append('  end [label="End"];')

    for i, a in enumerate(agents):
        aa = str(a).replace('"', '\\"')
        lines.append(f'  agent_{i} [label="{aa}"];')

    # Map ids to node names
    node_of: Dict[str, str] = {"entry": "entry", "end": "end"}
    for i, a in enumerate(agents):
        node_of[a] = f"agent_{i}"

    # Emit edges
    for s, t in edges:
        if s not in node_of or t not in node_of:
            continue
        lines.append(f"  {node_of[s]} -> {node_of[t]};")

    lines.append("}")
    return "\n".join(lines)
