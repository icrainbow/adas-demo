#!/usr/bin/env python3
"""
End-to-end smoke test for portfolio LangGraph optimization demo.

Tests the complete flow:
1. Start API server
2. Configure optimization via API endpoints
3. Start optimization
4. Verify results are produced
5. Verify viz page can load results

No browser automation - uses only stdlib HTTP requests.
"""

import os
import sys
import time
import json
import subprocess
import urllib.request
import urllib.error
from urllib.parse import urlencode

# Test configuration
TEST_PORT = 8081
SERVER_STARTUP_TIMEOUT = 10
OPTIMIZATION_TIMEOUT = 180
BASE_URL = f"http://localhost:{TEST_PORT}"


def start_server():
    """Start the API server in a subprocess."""
    print("Starting API server...")
    
    # Change to repo root
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    
    # Start server with custom port
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    
    process = subprocess.Popen(
        [sys.executable, "-m", "demos.portfolio_langgraph_opt.service.api_server", str(TEST_PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=repo_root,
        env=env,
        text=True
    )
    
    # Wait for server to start
    print(f"Waiting for server to start on port {TEST_PORT}...")
    start_time = time.time()
    while time.time() - start_time < SERVER_STARTUP_TIMEOUT:
        try:
            urllib.request.urlopen(f"{BASE_URL}/api/agents", timeout=1)
            print("✓ Server started successfully")
            return process
        except (urllib.error.URLError, ConnectionRefusedError):
            time.sleep(0.5)
    
    # Timeout
    process.kill()
    raise RuntimeError("Server failed to start within timeout")


def http_get(path):
    """Make GET request and return JSON response."""
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, method='GET')
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode('utf-8'))


def http_post(path, data=None):
    """Make POST request and return JSON response."""
    url = f"{BASE_URL}{path}"
    headers = {'Content-Type': 'application/json'}
    
    if data is not None:
        body = json.dumps(data).encode('utf-8')
    else:
        body = None
    
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"HTTP Error {e.code}: {error_body}")
        raise


def test_config_endpoints():
    """Test configuration endpoints."""
    print("\n=== Testing Configuration Endpoints ===")
    
    # Get eval config
    print("GET /api/config/eval...")
    eval_config = http_get("/api/config/eval")
    assert 'weights' in eval_config, "eval_config missing 'weights'"
    print("✓ Eval config loaded")
    
    # Get run config
    print("GET /api/config/run...")
    run_config = http_get("/api/config/run")
    assert 'dataset' in run_config, "run_config missing 'dataset'"
    assert 'search' in run_config, "run_config missing 'search'"
    print("✓ Run config loaded")
    
    # Save configs (use minimal budget for speed)
    run_config['search']['budget'] = 4  # Minimal for smoke test
    run_config['search']['seed'] = 42
    run_config['search']['mode'] = 'grid'
    
    print("POST /api/config/run/save...")
    result = http_post("/api/config/run/save", run_config)
    assert result.get('success'), f"Failed to save run config: {result}"
    print("✓ Run config saved")
    
    print("POST /api/config/eval/save...")
    result = http_post("/api/config/eval/save", eval_config)
    assert result.get('success'), f"Failed to save eval config: {result}"
    print("✓ Eval config saved")


def test_optimization():
    """Test optimization execution."""
    print("\n=== Testing Optimization ===")
    
    print("POST /api/optimize/start...")
    start_time = time.time()
    result = http_post("/api/optimize/start", {})
    
    if not result.get('success'):
        error = result.get('error', 'Unknown error')
        raise AssertionError(f"Optimization failed: {error}")
    
    run_id = result.get('run_id')
    assert run_id, "No run_id in response"
    print(f"✓ Optimization started: {run_id}")
    
    results_path = result.get('results_json_path')
    assert results_path, "No results_json_path in response"
    print(f"✓ Results path: {results_path}")
    
    # Verify output files exist
    assert os.path.exists(results_path), f"Results file not found: {results_path}"
    print(f"✓ Results file exists")
    
    # Load and validate results JSON
    with open(results_path, 'r') as f:
        results = json.load(f)
    
    assert 'baseline' in results, "Results missing 'baseline'"
    assert 'best' in results, "Results missing 'best'"
    assert 'all_scores' in results, "Results missing 'all_scores'"
    
    all_scores = results['all_scores']
    assert len(all_scores) > 0, "No candidates in all_scores"
    print(f"✓ Results valid: {len(all_scores)} candidates")
    
    elapsed = time.time() - start_time
    print(f"✓ Optimization completed in {elapsed:.1f}s")
    
    return run_id


def test_results_accessibility(run_id):
    """Test that results are accessible via HTTP."""
    print("\n=== Testing Results Accessibility ===")
    
    # Test viz page loads
    print("GET /viz/index.html...")
    try:
        with urllib.request.urlopen(f"{BASE_URL}/viz/index.html", timeout=5) as response:
            assert response.status == 200, f"Viz page returned {response.status}"
            print("✓ Viz page accessible")
    except urllib.error.URLError as e:
        raise AssertionError(f"Could not load viz page: {e}")
    
    # Test results JSON accessible via HTTP
    print(f"GET /runs/{run_id}/results.json...")
    try:
        results = http_get(f"/runs/{run_id}/results.json")
        assert 'baseline' in results, "Results missing 'baseline'"
        assert 'best' in results, "Results missing 'best'"
        assert 'all_scores' in results, "Results missing 'all_scores'"
        print("✓ Results accessible via HTTP")
        
        # Check if at least one candidate has topology info
        has_topology = False
        for entry in results['all_scores']:
            if isinstance(entry, dict):
                # Check for DOT string
                if 'candidate_spec' in entry and 'dot' in entry.get('candidate_spec', {}):
                    has_topology = True
                    print("✓ Topology data available (real DOT)")
                    break
                # Check for derived candidate config for fallback DOT generation
                if 'candidate_spec' in entry and 'derived' in entry.get('candidate_spec', {}):
                    has_topology = True
                    print("✓ Topology data available (candidate_spec.derived for inferred DOT)")
                    break
                # Or check if candidate field exists for fallback DOT generation
                if 'candidate' in entry:
                    has_topology = True
                    print("✓ Topology data available (candidate config for inferred DOT)")
                    break
        
        if not has_topology:
            print("⚠ Warning: No topology data found (viz may fail to render)")

        
    except urllib.error.URLError as e:
        raise AssertionError(f"Could not load results via HTTP: {e}")


def main():
    """Main test entry point."""
    server_process = None
    
    try:
        print("=" * 70)
        print("E2E Smoke Test: Portfolio LangGraph Optimization")
        print("=" * 70)
        
        # Start server
        server_process = start_server()
        
        # Run tests
        test_config_endpoints()
        run_id = test_optimization()
        test_results_accessibility(run_id)
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print(f"\nTo view results in browser:")
        print(f"  {BASE_URL}/viz/index.html?results=/runs/{run_id}/results.json")
        print("=" * 70)
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}", file=sys.stderr)
        return 1
    
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # Cleanup
        if server_process:
            print("\nShutting down server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
            print("✓ Server shut down")


if __name__ == "__main__":
    sys.exit(main())
