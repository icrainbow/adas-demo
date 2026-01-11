"""Unit tests for YAML-driven search space generator."""

import unittest
from pathlib import Path

from demos.portfolio_langgraph_opt.src.search_space_generator import load_search_space_for_case
from demos.portfolio_langgraph_opt.src.agents import load_registry
from demos.portfolio_langgraph_opt.src.search_space import validate_candidate


class TestSearchSpaceYAML(unittest.TestCase):
    """Test suite for YAML search space adapter."""
    
    def test_loader_default_case(self):
        """T1: Default loader returns module with KYC candidates."""
        ss = load_search_space_for_case(case_id=None, registry_dir=None)
        
        # Check interface
        self.assertTrue(hasattr(ss, 'default_candidate'))
        self.assertTrue(hasattr(ss, 'all_candidates_small'))
        self.assertTrue(hasattr(ss, 'candidate_to_name'))
        
        # Check candidates generation
        candidates = ss.all_candidates_small()
        self.assertGreater(len(candidates), 0, "Default (KYC) must generate >0 candidates")
        
        # Check default candidate
        baseline = ss.default_candidate()
        self.assertIsInstance(baseline, dict)
        self.assertIn('selected_agents', baseline)
    
    def test_loader_legal_case(self):
        """T2: Legal loader returns adapter with bounded candidates."""
        ss = load_search_space_for_case(case_id="legal_case", registry_dir=None)
        
        # Check interface
        self.assertTrue(hasattr(ss, 'default_candidate'))
        self.assertTrue(hasattr(ss, 'all_candidates_small'))
        self.assertTrue(hasattr(ss, 'candidate_to_name'))
        
        # Check candidates bounded
        candidates = ss.all_candidates_small()
        self.assertGreater(len(candidates), 20, "Legal case must generate >20 candidates")
        self.assertLessEqual(len(candidates), 200, "Legal case must generate <=200 candidates")
        
        print(f"\nLegal case generated {len(candidates)} candidates")
    
    def test_legal_candidates_schema_valid(self):
        """T3: Legal candidates have valid schema."""
        ss = load_search_space_for_case(case_id="legal_case", registry_dir=None)
        candidates = ss.all_candidates_small()
        
        # Test first 20 candidates
        for i, candidate in enumerate(candidates[:20]):
            with self.subTest(i=i):
                # Must not raise ValueError
                validate_candidate(candidate)
                
                # Must have selected_agents
                self.assertIn('selected_agents', candidate)
                self.assertIsInstance(candidate['selected_agents'], list)
    
    def test_legal_candidates_agent_existence(self):
        """T4: All agents in legal candidates exist in registry."""
        # Load legal registry
        repo_root = Path(__file__).parent.parent.parent.parent
        legal_agents_dir = repo_root / "demos/portfolio_langgraph_opt/src/cases/legal_case/agents"
        registry = load_registry(str(legal_agents_dir))
        registry_ids = set(registry.keys())
        
        # Load legal candidates
        ss = load_search_space_for_case(case_id="legal_case", registry_dir=None)
        candidates = ss.all_candidates_small()
        
        # Check every candidate
        for i, candidate in enumerate(candidates):
            with self.subTest(i=i):
                selected_agents = candidate.get('selected_agents', [])
                for agent_id in selected_agents:
                    self.assertIn(agent_id, registry_ids, 
                                 f"Agent '{agent_id}' not in legal registry")
    
    def test_legal_default_candidate(self):
        """T5: Legal default candidate includes must_have agents."""
        ss = load_search_space_for_case(case_id="legal_case", registry_dir=None)
        baseline = ss.default_candidate()
        
        # Check structure
        self.assertIsInstance(baseline, dict)
        self.assertIn('selected_agents', baseline)
        
        # Check must_have agents present
        selected_agents = set(baseline['selected_agents'])
        must_have = {'contract_parser', 'clause_analyzer', 'summary_generator'}
        
        for agent_id in must_have:
            self.assertIn(agent_id, selected_agents, 
                         f"Must-have agent '{agent_id}' not in default candidate")
        
        # Validate candidate
        validate_candidate(baseline)
        
        print(f"\nLegal default candidate: {baseline['selected_agents']}")
    
    def test_legal_candidate_naming(self):
        """T6: Legal candidate names are stable and deterministic."""
        ss = load_search_space_for_case(case_id="legal_case", registry_dir=None)
        candidates = ss.all_candidates_small()
        
        # Get names
        names = [ss.candidate_to_name(c) for c in candidates[:10]]
        
        # Check format
        for name in names:
            self.assertTrue(name.startswith("LEGAL-"), f"Name must start with 'LEGAL-': {name}")
            self.assertRegex(name, r'^LEGAL-[A-Z-]+-\d{3}-[a-f0-9]{8}$', f"Invalid name format: {name}")
        
        # Check uniqueness
        self.assertEqual(len(names), len(set(names)), "Candidate names must be unique")
        
        print(f"\nSample legal candidate names: {names[:5]}")


if __name__ == '__main__':
    unittest.main()
