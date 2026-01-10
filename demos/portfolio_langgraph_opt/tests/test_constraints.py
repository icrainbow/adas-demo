"""Unit tests for agent constraint validation engine."""

import unittest
import sys
import os

# Add repo root to path for imports
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, repo_root)

from demos.portfolio_langgraph_opt.src.agents.load_registry import load_registry
from demos.portfolio_langgraph_opt.src.agents.constraints import (
    validate_combo,
    validate_combo_or_raise,
    get_missing_required_agents,
    get_conflicting_agents,
    get_group_violations,
    suggest_fixes
)


class TestConstraintsValidation(unittest.TestCase):
    """Test constraint validation engine with real registry."""
    
    @classmethod
    def setUpClass(cls):
        """Load registry once for all tests."""
        cls.registry = load_registry()
    
    def test_valid_baseline_configuration(self):
        """Test that default configuration is valid."""
        selected = {"synth_style_A", "carryover_compact", "adaptive_off"}
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertTrue(is_valid, f"Baseline should be valid, got errors: {errors}")
        self.assertEqual(len(errors), 0)
    
    def test_valid_with_processing_nodes(self):
        """Test valid configuration with processing nodes."""
        selected = {
            "retriever",
            "risk_decompose",
            "behavior_check",
            "synth_style_A",
            "carryover_compact",
            "adaptive_off"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertTrue(is_valid, f"Should be valid, got errors: {errors}")
        self.assertEqual(len(errors), 0)
    
    def test_adaptive_policy_strict_requires_adaptive_on(self):
        """Test that adaptive_policy_strict requires adaptive_on."""
        # Invalid: adaptive_policy_strict without adaptive_on
        selected = {
            "synth_style_A",
            "carryover_compact",
            "adaptive_off",
            "adaptive_policy_strict"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertFalse(is_valid, "Should be invalid: adaptive_policy_strict requires adaptive_on")
        self.assertTrue(any("requires 'adaptive_on'" in err for err in errors),
                       f"Expected requires error, got: {errors}")
    
    def test_adaptive_policy_strict_valid_with_adaptive_on(self):
        """Test that adaptive_policy_strict is valid when adaptive_on is selected."""
        selected = {
            "risk_decompose",  # Added: adaptive_on now requires risk_decompose
            "synth_style_A",
            "carryover_compact",
            "adaptive_on",
            "adaptive_policy_strict"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertTrue(is_valid, f"Should be valid, got errors: {errors}")
        self.assertEqual(len(errors), 0)
    
    def test_synth_styles_mutual_exclusion(self):
        """Test that synth_style_A and synth_style_B cannot coexist."""
        selected = {
            "synth_style_A",
            "synth_style_B",
            "carryover_compact",
            "adaptive_off"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertFalse(is_valid, "Should be invalid: both synth styles selected")
        # Should have both mutex_with error and at_most_one_group error
        self.assertTrue(any("synth_style" in err for err in errors),
                       f"Expected group error, got: {errors}")
    
    def test_carryover_none_and_full_invalid(self):
        """Test that carryover_none and carryover_full cannot coexist."""
        selected = {
            "synth_style_A",
            "carryover_none",
            "carryover_full",
            "adaptive_off"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertFalse(is_valid, "Should be invalid: multiple carryover modes")
        # Should have both mutex_with error and at_most_one_group error
        self.assertTrue(any("carryover" in err for err in errors),
                       f"Expected group error, got: {errors}")
    
    def test_at_most_one_group_adaptive(self):
        """Test that adaptive_on and adaptive_off cannot coexist."""
        selected = {
            "synth_style_A",
            "carryover_compact",
            "adaptive_on",
            "adaptive_off"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertFalse(is_valid, "Should be invalid: both adaptive modes selected")
        self.assertTrue(any("adaptive" in err and "at most one" in err.lower() for err in errors),
                       f"Expected group error, got: {errors}")
    
    def test_adaptive_policy_without_adaptive_on(self):
        """Test that adaptive policies require adaptive_on."""
        # Test with strict policy
        selected = {
            "synth_style_A",
            "carryover_compact",
            "adaptive_off",
            "adaptive_policy_strict"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        self.assertFalse(is_valid)
        
        # Test with lenient policy
        selected = {
            "synth_style_A",
            "carryover_compact",
            "adaptive_off",
            "adaptive_policy_lenient"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        self.assertFalse(is_valid)
    
    def test_multiple_adaptive_policies_invalid(self):
        """Test that only one adaptive policy can be active."""
        selected = {
            "synth_style_A",
            "carryover_compact",
            "adaptive_on",
            "adaptive_policy_strict",
            "adaptive_policy_lenient"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertFalse(is_valid, "Should be invalid: multiple adaptive policies")
        self.assertTrue(any("adaptive_policy" in err for err in errors),
                       f"Expected adaptive_policy group error, got: {errors}")
    
    def test_unknown_agent_id(self):
        """Test that unknown agent IDs are caught."""
        selected = {"synth_style_A", "unknown_agent", "carryover_compact"}
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertFalse(is_valid)
        self.assertTrue(any("Unknown agent ID" in err for err in errors),
                       f"Expected unknown ID error, got: {errors}")
    
    def test_missing_required_synth_style(self):
        """Test configuration missing required synth style."""
        # Empty configuration - missing synth style (would need one in practice)
        selected = {"carryover_compact", "adaptive_off"}
        is_valid, errors = validate_combo(selected, self.registry)
        
        # This is actually valid from constraint perspective (no agent requires synth_style)
        # But in practice, you'd need at least one synth style for the graph to work
        # This test demonstrates that pure constraint validation doesn't enforce
        # "at least one from group" - that would be a separate validation layer
        self.assertTrue(is_valid)
    
    def test_validate_combo_or_raise_success(self):
        """Test validate_combo_or_raise with valid configuration."""
        selected = {"synth_style_A", "carryover_compact", "adaptive_off"}
        
        # Should not raise
        try:
            validate_combo_or_raise(selected, self.registry)
        except ValueError:
            self.fail("validate_combo_or_raise raised ValueError on valid config")
    
    def test_validate_combo_or_raise_failure(self):
        """Test validate_combo_or_raise with invalid configuration."""
        selected = {"synth_style_A", "synth_style_B"}
        
        # Should raise
        with self.assertRaises(ValueError) as context:
            validate_combo_or_raise(selected, self.registry)
        
        self.assertIn("Invalid agent combination", str(context.exception))
    
    def test_get_missing_required_agents(self):
        """Test detection of missing required agents."""
        # adaptive_policy_strict requires adaptive_on
        selected = {"adaptive_policy_strict", "synth_style_A"}
        missing = get_missing_required_agents(selected, self.registry)
        
        self.assertIn("adaptive_on", missing)
    
    def test_get_conflicting_agents(self):
        """Test detection of conflicting agents."""
        selected = {"synth_style_A", "synth_style_B"}
        conflicts = get_conflicting_agents(selected, self.registry)
        
        # At least one should be in conflicts (they're mutually exclusive)
        self.assertTrue(len(conflicts) > 0)
        self.assertTrue("synth_style_A" in conflicts or "synth_style_B" in conflicts)
    
    def test_get_group_violations(self):
        """Test detection of group violations."""
        selected = {"carryover_none", "carryover_compact", "carryover_full"}
        violations = get_group_violations(selected, self.registry)
        
        self.assertIn("carryover", violations)
        self.assertEqual(len(violations["carryover"]), 3)
    
    def test_suggest_fixes(self):
        """Test fix suggestions for invalid configuration."""
        # Missing required agent
        selected = {"adaptive_policy_strict", "synth_style_A"}
        suggestions = suggest_fixes(selected, self.registry)
        
        self.assertIn("adaptive_on", suggestions['add'])
    
    def test_empty_selection(self):
        """Test that empty selection is valid (no constraints violated)."""
        selected = set()
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_complex_valid_configuration(self):
        """Test a complex but valid configuration."""
        selected = {
            "retriever",
            "risk_decompose",
            "behavior_check",
            "hitl_gate",
            "synth_style_B",
            "carryover_compact",  # Changed from carryover_full (hitl_gate mutex with carryover_full)
            "adaptive_on",
            "adaptive_policy_lenient"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertTrue(is_valid, f"Complex config should be valid, got errors: {errors}")
        self.assertEqual(len(errors), 0)
    
    def test_mutex_with_constraint(self):
        """Test explicit mutex_with constraints."""
        # synth_style_A has mutex_with: ["synth_style_B"]
        selected = {"synth_style_A", "synth_style_B"}
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertFalse(is_valid)
        # Should get mutex_with error
        self.assertTrue(any("mutually exclusive" in err for err in errors),
                       f"Expected mutex error, got: {errors}")
    
    def test_mutex_hitl_and_carryover_full(self):
        """Test that hitl_gate and carryover_full cannot coexist (new constraint)."""
        # hitl_gate has mutex_with: ["carryover_full"]
        selected = {
            "hitl_gate",
            "carryover_full",
            "synth_style_A",
            "adaptive_off"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertFalse(is_valid, "Should be invalid: hitl_gate mutex with carryover_full")
        self.assertTrue(any("hitl_gate" in err and "carryover_full" in err for err in errors),
                       f"Expected mutex error mentioning both agents, got: {errors}")
    
    def test_requires_adaptive_on_needs_risk_decompose(self):
        """Test that adaptive_on requires risk_decompose (new constraint)."""
        # Test 1: Invalid - adaptive_on without risk_decompose
        selected = {
            "adaptive_on",
            "synth_style_A",
            "carryover_none",
            "adaptive_policy_strict"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertFalse(is_valid, "Should be invalid: adaptive_on requires risk_decompose")
        self.assertTrue(any("adaptive_on" in err and "risk_decompose" in err for err in errors),
                       f"Expected requires error, got: {errors}")
        
        # Test 2: Valid - with risk_decompose added
        selected_valid = {
            "adaptive_on",
            "risk_decompose",
            "synth_style_A",
            "carryover_none",
            "adaptive_policy_strict"
        }
        is_valid_2, errors_2 = validate_combo(selected_valid, self.registry)
        
        self.assertTrue(is_valid_2, f"Should be valid with risk_decompose, got errors: {errors_2}")
        self.assertEqual(len(errors_2), 0)
    
    def test_requires_policy_needs_adaptive_on(self):
        """Test that adaptive policies require adaptive_on."""
        # Test with adaptive_off and adaptive_policy_strict
        selected = {
            "adaptive_off",
            "adaptive_policy_strict",
            "synth_style_B",
            "carryover_compact"
        }
        is_valid, errors = validate_combo(selected, self.registry)
        
        self.assertFalse(is_valid, "Should be invalid: adaptive_policy_strict requires adaptive_on")
        self.assertTrue(any("adaptive_policy_strict" in err and "adaptive_on" in err for err in errors),
                       f"Expected requires error, got: {errors}")
    
    def test_one_of_groups(self):
        """Test at_most_one_group constraints with multiple scenarios."""
        # Test 1: Multiple synth styles (invalid)
        selected_synth = {
            "synth_style_A",
            "synth_style_B",
            "carryover_none",
            "adaptive_off"
        }
        is_valid_1, errors_1 = validate_combo(selected_synth, self.registry)
        
        self.assertFalse(is_valid_1, "Should be invalid: multiple synth_style agents")
        self.assertTrue(any("synth_style" in err and "at most one" in err.lower() for err in errors_1),
                       f"Expected group error for synth_style, got: {errors_1}")
        
        # Test 2: Multiple carryover modes (invalid)
        selected_carryover = {
            "carryover_none",
            "carryover_full",
            "synth_style_A",
            "adaptive_off"
        }
        is_valid_2, errors_2 = validate_combo(selected_carryover, self.registry)
        
        self.assertFalse(is_valid_2, "Should be invalid: multiple carryover agents")
        self.assertTrue(any("carryover" in err and "at most one" in err.lower() for err in errors_2),
                       f"Expected group error for carryover, got: {errors_2}")


class TestConstraintHelpers(unittest.TestCase):
    """Test helper functions for constraint analysis."""
    
    @classmethod
    def setUpClass(cls):
        """Load registry once for all tests."""
        cls.registry = load_registry()
    
    def test_get_missing_required_agents_empty(self):
        """Test with no missing agents."""
        selected = {"risk_decompose", "adaptive_on", "adaptive_policy_strict", "synth_style_A"}
        missing = get_missing_required_agents(selected, self.registry)
        
        self.assertEqual(len(missing), 0)
    
    def test_get_conflicting_agents_empty(self):
        """Test with no conflicts."""
        selected = {"retriever", "risk_decompose", "synth_style_A"}
        conflicts = get_conflicting_agents(selected, self.registry)
        
        self.assertEqual(len(conflicts), 0)
    
    def test_get_group_violations_empty(self):
        """Test with no group violations."""
        selected = {"synth_style_A", "carryover_compact", "adaptive_off"}
        violations = get_group_violations(selected, self.registry)
        
        self.assertEqual(len(violations), 0)
    
    def test_suggest_fixes_valid_config(self):
        """Test suggestions for already-valid configuration."""
        selected = {"synth_style_A", "carryover_compact", "adaptive_off"}
        suggestions = suggest_fixes(selected, self.registry)
        
        self.assertEqual(len(suggestions['add']), 0)
        self.assertEqual(len(suggestions['remove']), 0)
        self.assertEqual(len(suggestions['group_conflicts']), 0)


def run_tests():
    """Run all tests and return exit code."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestConstraintsValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestConstraintHelpers))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return appropriate exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
