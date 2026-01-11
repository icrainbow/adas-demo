"""Optimization service - runs portfolio search."""

import os
import json
import subprocess
from datetime import datetime
from .config_loader import load_eval_config, load_run_config
from .agent_service import list_agents
from .limits import enforce_limits, TIMEOUT_SECONDS


LOCK_FILE = "demos/portfolio_langgraph_opt/runs/.lock"
ALLOWED_ARGS = ['cases', 'policy', 'mode', 'budget', 'seed', 'out']


def start_optimization(case_id: str = None):
    """
    Start optimization run.
    
    Args:
        case_id: Optional case ID to use specific agent registry
    """
    try:
        # Check lock
        if os.path.exists(LOCK_FILE):
            return {"success": False, "error": "Another optimization is running"}
        
        # Acquire lock
        os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
        with open(LOCK_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
        
        try:
            # Load configs
            eval_cfg = load_eval_config()
            run_cfg = load_run_config()
            
            # Enforce caps
            warnings = enforce_limits(run_cfg, eval_cfg)
            warning_msg = "; ".join(warnings) if warnings else None
            
            # Create run directory
            run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
            output_dir = os.path.join(run_cfg.output.output_dir, run_id)
            os.makedirs(output_dir, exist_ok=True)
            
            # Save config snapshot
            snapshot_dir = os.path.join(output_dir, "config_snapshot")
            os.makedirs(snapshot_dir, exist_ok=True)
            
            # Copy configs
            import shutil
            import yaml
            
            eval_path = "demos/portfolio_langgraph_opt/config/eval.yaml"
            run_path = "demos/portfolio_langgraph_opt/config/run.yaml"
            
            if os.path.exists(eval_path):
                shutil.copy(eval_path, os.path.join(snapshot_dir, "eval.yaml"))
            if os.path.exists(run_path):
                shutil.copy(run_path, os.path.join(snapshot_dir, "run.yaml"))
            
            # Save agent manifest for the selected case
            agents_data = list_agents(case_id=case_id)
            manifest_path = os.path.join(snapshot_dir, "agents_manifest.json")
            with open(manifest_path, 'w') as f:
                json.dump(agents_data, f, indent=2)
            
            # Compute registry_dir from case_id
            registry_dir = None
            if case_id:
                from .case_service import case_root
                case_path = case_root(case_id)
                registry_dir = os.path.join(case_path, "agents")
            
            # Build subprocess command
            results_json_path = os.path.join(output_dir, "results.json")
            cmd = [
                "python3",
                "demos/portfolio_langgraph_opt/portfolio_search.py",
                "--cases", run_cfg.dataset.cases_path,
                "--policy", run_cfg.dataset.policy_path,
                "--mode", run_cfg.search.mode,
                "--budget", str(run_cfg.search.budget),
                "--seed", str(run_cfg.search.seed),
                "--out", results_json_path
            ]
            
            # Add registry_dir if specified
            if registry_dir:
                cmd.extend(["--registry_dir", registry_dir])
            
            # Run subprocess
            log_path = os.path.join(output_dir, "run.log")
            with open(log_path, 'w') as log_file:
                process = subprocess.run(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    timeout=TIMEOUT_SECONDS
                )
            
            if process.returncode != 0:
                return {
                    "success": False,
                    "error": f"Optimization failed with exit code {process.returncode}. Check {log_path}"
                }
            
            # Generate DOT files
            _generate_dot_files(output_dir, results_json_path)
            
            # Generate output paths
            pareto_json_path = results_json_path.replace(".json", "_pareto.json")
            pareto_md_path = results_json_path.replace(".json", "_pareto.md")
            
            return {
                "success": True,
                "run_id": run_id,
                "output_dir": output_dir,
                "results_json_path": results_json_path,
                "pareto_json_path": pareto_json_path if os.path.exists(pareto_json_path) else None,
                "pareto_md_path": pareto_md_path if os.path.exists(pareto_md_path) else None,
                "log_path": log_path,
                "effective_budget": run_cfg.search.budget,
                "warning": warning_msg
            }
        
        finally:
            # Release lock
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
    
    except subprocess.TimeoutExpired:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
        return {"success": False, "error": "Optimization timed out after 1 hour"}
    
    except Exception as e:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
        return {"success": False, "error": str(e)}


def _generate_dot_files(run_dir, results_json_path):
    """Generate DOT files for best and pareto candidates."""
    try:
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
        from demos.portfolio_langgraph_opt.src.topology_dot import generate_dot
        
        # Load results
        with open(results_json_path, 'r') as f:
            results = json.load(f)
        
        # Get pareto names
        pareto_names = []
        pareto_json_path = os.path.join(run_dir, "results_pareto.json")
        
        if os.path.exists(pareto_json_path):
            with open(pareto_json_path, 'r') as f:
                pareto_data = json.load(f)
            
            if isinstance(pareto_data, list):
                pareto_names = pareto_data
            elif isinstance(pareto_data, dict) and "pareto_frontier" in pareto_data:
                frontier = pareto_data["pareto_frontier"]
                if isinstance(frontier, list):
                    for item in frontier:
                        if isinstance(item, str):
                            pareto_names.append(item)
                        elif isinstance(item, dict) and "candidate_name" in item:
                            pareto_names.append(item["candidate_name"])
        else:
            pareto_names = results.get("pareto_frontier", [])
        
        # Create dot directory
        dot_dir = os.path.join(run_dir, "dot")
        os.makedirs(dot_dir, exist_ok=True)
        
        # Best candidate
        best_data = results.get("best", {})
        if isinstance(best_data, dict):
            best_candidate = best_data.get("candidate", best_data)
        else:
            best_candidate = best_data
        
        if best_candidate:
            best_dot = generate_dot(best_candidate)
            with open(os.path.join(dot_dir, "best.dot"), 'w') as f:
                f.write(best_dot)
        
        # Pareto candidates (cap at 15)
        all_scores = results.get("all_scores", [])
        for name in pareto_names[:15]:
            candidate = _find_candidate_by_name(all_scores, name)
            if candidate:
                candidate_dict = candidate.get("candidate", candidate)
                dot = generate_dot(candidate_dict)
                safe_name = name.replace("/", "_").replace("\\", "_")
                with open(os.path.join(dot_dir, f"{safe_name}.dot"), 'w') as f:
                    f.write(dot)
    
    except Exception as e:
        print(f"Warning: DOT generation failed: {e}")


def _find_candidate_by_name(all_scores, name):
    """Find candidate in all_scores by name."""
    if isinstance(all_scores, list):
        for entry in all_scores:
            if isinstance(entry, dict):
                if entry.get("candidate_name") == name:
                    return entry
    elif isinstance(all_scores, dict):
        return all_scores.get(name)
    return None
