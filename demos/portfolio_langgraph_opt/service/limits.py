"""Safety limits and validation."""

# Hard caps
MAX_BUDGET = 64
MAX_SAMPLES = 6
MAX_UPLOAD_MB = 1
MAX_AGENT_YAML_KB = 100
TIMEOUT_SECONDS = 3600


def enforce_limits(run_cfg, eval_cfg):
    """
    Enforce safety caps on run and eval configurations.
    
    Args:
        run_cfg: RunConfig object
        eval_cfg: EvalConfig object
    
    Returns:
        List of warning messages
    """
    warnings = []
    
    # Cap budget
    if run_cfg.search.budget > MAX_BUDGET:
        warnings.append(f"Budget capped from {run_cfg.search.budget} to {MAX_BUDGET}")
        run_cfg.search.budget = MAX_BUDGET
    
    # Force lite mode
    run_cfg.output.lite_mode = True
    
    # Cap sampling
    total_samples = eval_cfg.sampling.k_low + eval_cfg.sampling.k_high + eval_cfg.sampling.k_mid
    if total_samples > MAX_SAMPLES:
        scale = MAX_SAMPLES / total_samples
        eval_cfg.sampling.k_low = max(1, int(eval_cfg.sampling.k_low * scale))
        eval_cfg.sampling.k_high = max(1, int(eval_cfg.sampling.k_high * scale))
        eval_cfg.sampling.k_mid = MAX_SAMPLES - eval_cfg.sampling.k_low - eval_cfg.sampling.k_high
        warnings.append(f"Sampling capped to {MAX_SAMPLES} total")
    
    return warnings


def validate_upload_size(content_bytes):
    """Validate upload size."""
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if len(content_bytes) > max_bytes:
        raise ValueError(f"Upload exceeds {MAX_UPLOAD_MB} MB limit")


def validate_agent_yaml_size(content):
    """Validate agent YAML size."""
    max_bytes = MAX_AGENT_YAML_KB * 1024
    size = len(content.encode('utf-8'))
    if size > max_bytes:
        raise ValueError(f"Agent YAML exceeds {MAX_AGENT_YAML_KB} KB limit")
