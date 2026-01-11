"""Configuration loading and saving with atomic writes."""

import os
import yaml
import tempfile
from dataclasses import dataclass, asdict


@dataclass
class EvalWeights:
    coverage_weight: float = 100.0
    violation_penalty: float = 200.0
    hitl_penalty: float = 10.0
    step_penalty: float = 1.0
    token_penalty: float = 0.01


@dataclass
class EvalSampling:
    k_low: int = 2
    k_high: int = 2
    k_mid: int = 2


@dataclass
class EvalConfig:
    weights: EvalWeights
    sampling: EvalSampling
    
    @classmethod
    def from_dict(cls, data):
        weights_data = data.get('weights', {})
        sampling_data = data.get('sampling', {})
        return cls(
            weights=EvalWeights(**weights_data),
            sampling=EvalSampling(**sampling_data)
        )
    
    def to_dict(self):
        return {
            'version': 1.0,
            'weights': asdict(self.weights),
            'sampling': asdict(self.sampling)
        }


@dataclass
class RunDataset:
    cases_path: str = "demos/portfolio_langgraph_opt/data/cases.jsonl"
    policy_path: str = "demos/portfolio_langgraph_opt/data/policy_snippets.txt"


@dataclass
class RunSearch:
    mode: str = "grid"
    budget: int = 16
    seed: int = 7


@dataclass
class RunOutput:
    output_dir: str = "demos/portfolio_langgraph_opt/runs"
    emit_dot: bool = True
    lite_mode: bool = True


@dataclass
class RunSafety:
    max_budget: int = 64
    max_file_upload_mb: int = 1
    max_concurrency: int = 1
    timeout_seconds: int = 3600


@dataclass
class RunConfig:
    dataset: RunDataset
    search: RunSearch
    output: RunOutput
    safety: RunSafety
    
    @classmethod
    def from_dict(cls, data):
        dataset_data = data.get('dataset', {})
        search_data = data.get('search', {})
        output_data = data.get('output', {})
        safety_data = data.get('safety', {})
        return cls(
            dataset=RunDataset(**dataset_data),
            search=RunSearch(**search_data),
            output=RunOutput(**output_data),
            safety=RunSafety(**safety_data)
        )
    
    def to_dict(self):
        return {
            'version': 1.0,
            'dataset': asdict(self.dataset),
            'search': asdict(self.search),
            'output': asdict(self.output),
            'safety': asdict(self.safety)
        }


def load_eval_config(path="demos/portfolio_langgraph_opt/config/eval.yaml"):
    """Load evaluation configuration."""
    if not os.path.exists(path):
        return EvalConfig(weights=EvalWeights(), sampling=EvalSampling())
    
    with open(path, 'r') as f:
        data = yaml.safe_load(f) or {}
    
    return EvalConfig.from_dict(data)


def save_eval_config(config, path="demos/portfolio_langgraph_opt/config/eval.yaml"):
    """Save evaluation configuration with atomic write."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Atomic write: temp file + rename
        with tempfile.NamedTemporaryFile(mode='w', delete=False, 
                                         dir=os.path.dirname(path),
                                         suffix='.yaml') as tmp:
            yaml.dump(config.to_dict(), tmp, default_flow_style=False)
            tmp_path = tmp.name
        
        os.replace(tmp_path, path)
        return {"success": True, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def load_run_config(path="demos/portfolio_langgraph_opt/config/run.yaml"):
    """Load run configuration."""
    if not os.path.exists(path):
        return RunConfig(
            dataset=RunDataset(),
            search=RunSearch(),
            output=RunOutput(),
            safety=RunSafety()
        )
    
    with open(path, 'r') as f:
        data = yaml.safe_load(f) or {}
    
    return RunConfig.from_dict(data)


def save_run_config(config, path="demos/portfolio_langgraph_opt/config/run.yaml"):
    """Save run configuration with atomic write."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Atomic write: temp file + rename
        with tempfile.NamedTemporaryFile(mode='w', delete=False,
                                         dir=os.path.dirname(path),
                                         suffix='.yaml') as tmp:
            yaml.dump(config.to_dict(), tmp, default_flow_style=False)
            tmp_path = tmp.name
        
        os.replace(tmp_path, path)
        return {"success": True, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}
