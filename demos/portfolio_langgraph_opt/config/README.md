# Configuration Schema Documentation

## eval.yaml

Evaluation configuration for scoring candidates.

```yaml
version: 1.0
weights:
  coverage_weight: float      # Reward for coverage (default: 100.0)
  violation_penalty: float    # Penalty for violations (default: 200.0)
  hitl_penalty: float         # Penalty for HITL escalations (default: 10.0)
  step_penalty: float         # Penalty per step (default: 1.0)
  token_penalty: float        # Penalty per token (default: 0.01)

sampling:
  k_low: int                  # Low coverage samples (default: 2, max: 2)
  k_high: int                 # High coverage samples (default: 2, max: 2)
  k_mid: int                  # Mid coverage samples (default: 2, max: 2)
```

## run.yaml

Run configuration for optimization search.

```yaml
version: 1.0
dataset:
  cases_path: string          # Path to cases JSONL
  policy_path: string         # Path to policy text

search:
  mode: string                # "grid" or "random"
  budget: int                 # Max candidates to evaluate (UI cap: 64)
  seed: int                   # Random seed

output:
  output_dir: string          # Output directory path
  emit_dot: bool              # Generate DOT files
  lite_mode: bool             # Always true for UI runs

safety:
  max_budget: int             # Hard cap (64)
  max_file_upload_mb: int     # Upload size cap (1 MB)
  max_concurrency: int        # Must be 1
  timeout_seconds: int        # Subprocess timeout (3600)
```

## Agent Registry YAML

Location: `src/agents/registry/<id>.yaml`

```yaml
id: string                    # Unique identifier
name: string                  # Display name
purpose: string               # Brief description
role: string                  # node|style|gate|retrieval|analysis|synthesis
inputs: [string]              # Expected input keys
outputs: [string]             # Produced output keys
token_budget_hint: int        # Optional: estimated tokens per case
compatible_with: [string]     # Optional: compatible agent IDs
incompatible_with: [string]   # Optional: incompatible agent IDs
```
