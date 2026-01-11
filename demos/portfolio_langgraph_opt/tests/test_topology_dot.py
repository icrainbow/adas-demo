"""Drift guard unit tests for topology_dot.py"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from topology_dot import generate_dot


def test_baseline_candidate():
    """Test DOT for baseline candidate (synth only)."""
    candidate = {
        "use_retriever": False,
        "use_risk_decompose": False,
        "use_behavior_check": False,
        "use_hitl_gate": False,
        "synth_style": "A",
        "adaptive": False,
        "carryover": "compact",
        "max_steps": 4
    }
    dot = generate_dot(candidate)
    
    assert "START" in dot
    assert "synth" in dot
    assert "END" in dot
    assert "START -> synth" in dot
    assert "synth -> END" in dot
    assert "retriever" not in dot
    assert "risk_decompose" not in dot


def test_full_pipeline_candidate():
    """Test DOT for candidate with all processing nodes."""
    candidate = {
        "use_retriever": True,
        "use_risk_decompose": True,
        "use_behavior_check": True,
        "use_hitl_gate": False,
        "synth_style": "B",
        "adaptive": False,
        "carryover": "none",
        "max_steps": 4
    }
    dot = generate_dot(candidate)
    
    assert "retriever" in dot
    assert "risk_decompose" in dot
    assert "behavior_check" in dot
    assert "synth" in dot
    assert "START -> retriever" in dot
    assert "retriever -> risk_decompose" in dot
    assert "risk_decompose -> behavior_check" in dot
    assert "behavior_check -> synth" in dot


def test_adaptive_candidate():
    """Test DOT for candidate with adaptive mode."""
    candidate = {
        "use_retriever": False,
        "use_risk_decompose": True,
        "use_behavior_check": False,
        "use_hitl_gate": False,
        "synth_style": "A",
        "adaptive": True,
        "adaptive_policy": "strict",
        "carryover": "compact",
        "max_steps": 4
    }
    dot = generate_dot(candidate)
    
    assert "adaptive" in dot.lower()
    assert "dashed" in dot or "conditional" in dot


if __name__ == "__main__":
    print("Running topology_dot tests...")
    test_baseline_candidate()
    print("✓ test_baseline_candidate passed")
    test_full_pipeline_candidate()
    print("✓ test_full_pipeline_candidate passed")
    test_adaptive_candidate()
    print("✓ test_adaptive_candidate passed")
    print("All tests passed!")
