# Agent Registry

## Purpose

The Agent Registry provides a declarative way to define portfolio advisory graph components ("agents") as YAML files with explicit dependency and compatibility constraints. This enables:

- **Declarative configuration**: Define agents and their properties in YAML
- **Constraint validation**: Automatically enforce compatibility rules
- **Modular composition**: Mix and match agents with confidence
- **Configuration search**: Generate valid candidate configurations programmatically

## What is an "Agent"?

In this system, an "agent" is any configurable component of the advisory graph, including:

- **Nodes**: `retriever`, `risk_decompose`, `behavior_check`, `hitl_gate`
- **Styles**: `synth_style_A`, `synth_style_B` (synthesis behavior variants)
- **Strategies**: `carryover_none`, `carryover_compact`, `carryover_full` (context passing modes)
- **Policies**: `adaptive_on`, `adaptive_off`, `adaptive_policy_strict`, `adaptive_policy_lenient`

Treating styles and strategies as "agents" allows uniform constraint handling.

## YAML Schema

Each agent is defined in a separate `.yaml` file in this directory.

### Required Fields

```yaml
id: string                    # Unique identifier (e.g., "retriever", "synth_style_A")
version: string               # Semantic version (e.g., "1.0.0")
stage: string                 # Execution stage: "preprocessing" | "processing" | "synthesis" | "strategy"
node_type: string             # Type: "node" | "style" | "strategy" | "policy"
enabled_by_default: boolean   # Whether enabled in baseline configuration
params: object                # Configuration parameters (can be empty {})
constraints: object           # Combination constraints (see below)
ordering: object              # Execution order hints
cost_hint: object             # Resource usage estimates
```

### Constraints Schema

The `constraints` object defines how agents can be combined:

```yaml
constraints:
  requires: [agent_id, ...]           # Must have ALL listed agents active
  requires_any: [agent_id, ...]       # Must have AT LEAST ONE of listed agents
  mutex_with: [agent_id, ...]         # Cannot coexist with any listed agents
  only_with: [agent_id, ...]          # If active, ONLY these agents can be active (strict whitelist)
  at_most_one_group: string           # Group name - at most one agent in this group can be active
```

### Constraint Semantics

#### `requires`
**Meaning**: "I need ALL of these agents to function."

**Example**:
```yaml
# adaptive_policy_strict requires adaptive_on
constraints:
  requires: ["adaptive_on"]
```

**Validation**: If this agent is active, all listed agents must also be active.

#### `requires_any`
**Meaning**: "I need AT LEAST ONE of these agents to function."

**Example**:
```yaml
# synth node requires at least one signal source
constraints:
  requires_any: ["retriever", "risk_decompose", "behavior_check"]
```

**Validation**: If this agent is active, at least one of the listed agents must be active.

#### `mutex_with`
**Meaning**: "I cannot work with these agents."

**Example**:
```yaml
# carryover_none cannot work with carryover_compact
constraints:
  mutex_with: ["carryover_compact", "carryover_full"]
```

**Validation**: If this agent is active, none of the listed agents can be active.

#### `only_with`
**Meaning**: "If I'm active, ONLY these agents (and me) can be active - strict whitelist."

**Example**:
```yaml
# minimal_mode only allows retriever and synth_style_A
constraints:
  only_with: ["retriever", "synth_style_A"]
```

**Validation**: If this agent is active, the set of all active agents must be a subset of `[this_agent] + only_with`.

**Note**: `only_with` is very restrictive and rarely used. Most constraints use `requires`, `mutex_with`, or `at_most_one_group`.

#### `at_most_one_group`
**Meaning**: "Only one agent in this named group can be active."

**Example**:
```yaml
# synth_style_A and synth_style_B both specify:
at_most_one_group: "synth_style"
```

**Validation**: Across all agents, at most one agent with the same `at_most_one_group` value can be active.

**Use Cases**:
- **Mutually exclusive options**: synth styles, carryover modes, adaptive on/off
- **Single-choice selections**: policies, strategies
- **Alternative implementations**: different versions of same functionality

### Ordering Schema

```yaml
ordering:
  priority: integer           # Execution priority (higher runs earlier)
  depends_on: [agent_id, ...] # Must execute after these agents
  before: [agent_id, ...]     # Must execute before these agents
```

### Cost Hint Schema

```yaml
cost_hint:
  tokens_per_case: integer    # Estimated token cost per case
  relative_latency: float     # Relative execution time (1.0 = baseline)
  complexity: string          # "low" | "medium" | "high"
```

## Example Agent Definition

```yaml
# retriever.yaml
id: retriever
version: 1.0.0
stage: processing
node_type: node
enabled_by_default: false
params:
  matching_algorithm: "keyword"
  max_results: 5
constraints:
  requires: []
  requires_any: []
  mutex_with: []
  only_with: []
  at_most_one_group: ""
ordering:
  priority: 100
  depends_on: []
  before: ["synth"]
cost_hint:
  tokens_per_case: 150
  relative_latency: 1.2
  complexity: "low"
```

## Constraint Groups in This Registry

### 1. Synthesis Style (`at_most_one_group: "synth_style"`)
**Members**: `synth_style_A`, `synth_style_B`

**Rule**: Exactly one synthesis style must be active.

**Example Valid Configs**:
- `[synth_style_A]` ✓
- `[synth_style_B]` ✓
- `[synth_style_A, synth_style_B]` ✗ (at most one)
- `[]` ✗ (need exactly one for synthesis)

### 2. Carryover Mode (`at_most_one_group: "carryover"`)
**Members**: `carryover_none`, `carryover_compact`, `carryover_full`

**Rule**: Exactly one carryover mode must be active.

**Example Valid Configs**:
- `[carryover_none]` ✓
- `[carryover_compact]` ✓
- `[carryover_none, carryover_compact]` ✗ (at most one)

### 3. Adaptive Mode (`at_most_one_group: "adaptive"`)
**Members**: `adaptive_off`, `adaptive_on`

**Rule**: Exactly one adaptive mode must be active.

**Example Valid Configs**:
- `[adaptive_off]` ✓
- `[adaptive_on]` ✓
- `[adaptive_off, adaptive_on]` ✗ (at most one)

### 4. Adaptive Policy (`at_most_one_group: "adaptive_policy"`)
**Members**: `adaptive_policy_strict`, `adaptive_policy_lenient`

**Rule**: At most one adaptive policy can be active, AND requires `adaptive_on`.

**Example Valid Configs**:
- `[adaptive_off]` ✓ (no policy needed)
- `[adaptive_on, adaptive_policy_strict]` ✓
- `[adaptive_on, adaptive_policy_lenient]` ✓
- `[adaptive_policy_strict]` ✗ (requires adaptive_on)
- `[adaptive_on, adaptive_policy_strict, adaptive_policy_lenient]` ✗ (at most one policy)

## Validation Process

When loading the registry, the following validations occur:

1. **Schema Validation**: Each YAML file must conform to the schema
2. **ID Uniqueness**: No duplicate agent IDs
3. **Reference Validation**: All agent IDs in constraints must exist
4. **Group Consistency**: All agents in an `at_most_one_group` must reference the same group name
5. **Circular Dependency Detection**: No cycles in `requires` or `ordering.depends_on`

## Usage Example

```python
from demos.portfolio_langgraph_opt.src.agents.load_registry import load_registry

# Load all agents
registry = load_registry()

# Get agent by ID
retriever_def = registry["retriever"]

# Check constraints
if "adaptive_on" in registry:
    requires = registry["adaptive_policy_strict"].constraints.requires
    # ["adaptive_on"]

# Validate a configuration
active_agents = ["retriever", "risk_decompose", "synth_style_A", 
                 "carryover_compact", "adaptive_off"]
# Validation logic would check all constraints
```

## Registry Files

Current agents defined in this registry:

### Nodes
- `retriever.yaml` - Policy text retriever
- `risk_decompose.yaml` - Risk factor decomposition
- `behavior_check.yaml` - Behavioral analysis
- `hitl_gate.yaml` - Human-in-the-loop gate

### Synthesis Styles
- `synth_style_A.yaml` - Terse synthesis style
- `synth_style_B.yaml` - Verbose synthesis style

### Carryover Strategies
- `carryover_none.yaml` - No context carryover
- `carryover_compact.yaml` - Compact context carryover
- `carryover_full.yaml` - Full context carryover

### Adaptive Modes
- `adaptive_off.yaml` - Adaptive subgraphs disabled
- `adaptive_on.yaml` - Adaptive subgraphs enabled

### Adaptive Policies
- `adaptive_policy_strict.yaml` - Strict adaptive policy
- `adaptive_policy_lenient.yaml` - Lenient adaptive policy

## Future Extensions

Potential enhancements:

- **Dynamic cost models**: Load cost from historical data
- **Version compatibility**: Specify compatible version ranges
- **Conditional constraints**: Context-dependent rules
- **Agent hierarchies**: Parent/child agent relationships
- **Feature flags**: Enable/disable agents based on environment
- **A/B testing metadata**: Track experiment cohorts

---

**Note**: This registry is currently standalone and not yet integrated with the search pipeline. Integration will map legacy candidate dictionaries to agent sets.
