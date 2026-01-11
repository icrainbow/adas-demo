#!/usr/bin/env python3
import os
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]  # .../ADAS
LEGAL_DIR = REPO_ROOT / "demos/portfolio_langgraph_opt/src/cases/legal_case/agents"
KYC_DIR   = REPO_ROOT / "demos/portfolio_langgraph_opt/src/cases/kyc_case/agents"

PATCH_KEYS = ["role", "purpose", "inputs", "outputs", "token_budget_hint", "name"]

def load_yaml(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be dict: {path}")
    return data

def dump_yaml(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)

def patch_agent(dir_path: Path, spec: dict):
    agent_id = spec["id"]
    path = dir_path / f"{agent_id}.yaml"
    data = load_yaml(path) if path.exists() else {}
    if "id" not in data:
        data["id"] = agent_id

    # Overwrite only the intended keys (deterministic)
    for k in PATCH_KEYS:
        if k in spec and spec[k] is not None and spec[k] != "":
            data[k] = spec[k]

    # Required keys must exist and be non-empty
    for required in ["id", "name", "role", "purpose", "inputs", "outputs", "token_budget_hint"]:
        if required not in data:
            raise ValueError(f"Missing required key after patch: {required} in {path}")
        if required in ["name", "role", "purpose"] and not str(data[required]).strip():
            raise ValueError(f"Empty required string key after patch: {required} in {path}")
        if required in ["inputs", "outputs"] and not isinstance(data[required], list):
            raise ValueError(f"{required} must be a list in {path}")

    dump_yaml(path, data)
    return path

LEGAL_AGENTS = [
    # --- keep existing 4 ids (do not rename) but enrich them ---
    {
        "id": "contract_parser",
        "name": "Contract Parser",
        "role": "preprocessing",
        "purpose": "Normalize raw legal text, preserve headings, and produce a stable structured representation for downstream extraction.",
        "inputs": ["raw_document"],
        "outputs": ["normalized_document", "doc_structure"],
        "token_budget_hint": 1200,
    },
    {
        "id": "clause_analyzer",
        "name": "Clause Analyzer",
        "role": "extraction",
        "purpose": "Extract canonical clause types (termination, liability, indemnity, confidentiality, payment, governing law, dispute resolution) with citations.",
        "inputs": ["normalized_document", "doc_structure"],
        "outputs": ["clause_inventory"],
        "token_budget_hint": 1700,
    },
    {
        "id": "compliance_checker",
        "name": "Compliance Checker",
        "role": "verification",
        "purpose": "Check the extracted clauses against generic policy notes and flag missing/weak protections; ensure findings are evidence-grounded.",
        "inputs": ["clause_inventory", "policy_notes"],
        "outputs": ["compliance_findings"],
        "token_budget_hint": 1800,
    },
    {
        "id": "summary_generator",
        "name": "Summary Generator",
        "role": "synthesis",
        "purpose": "Generate an executive summary and decision-ready bullet points derived from verified findings, including key risks and next actions.",
        "inputs": ["compliance_findings", "clause_inventory"],
        "outputs": ["exec_summary"],
        "token_budget_hint": 1400,
    },

    # --- add 14 new atomic agents (total legal = 18) ---
    {
        "id": "segmenter",
        "name": "Segmenter",
        "role": "preprocessing",
        "purpose": "Split normalized document into stable chunk IDs for traceability and citation alignment.",
        "inputs": ["normalized_document"],
        "outputs": ["sections", "chunks"],
        "token_budget_hint": 1200,
    },
    {
        "id": "definition_indexer",
        "name": "Definition Indexer",
        "role": "extraction",
        "purpose": "Build a glossary of defined terms; flag missing, circular, unused, or inconsistent definitions.",
        "inputs": ["sections", "chunks"],
        "outputs": ["definitions_index", "definition_issues"],
        "token_budget_hint": 1400,
    },
    {
        "id": "obligation_extractor",
        "name": "Obligation Extractor",
        "role": "extraction",
        "purpose": "Extract obligations by party (Supplier/Customer/Mutual) and map each obligation to evidence chunks.",
        "inputs": ["sections", "chunks", "clause_inventory"],
        "outputs": ["obligations_table"],
        "token_budget_hint": 1600,
    },
    {
        "id": "ambiguity_detector",
        "name": "Ambiguity Detector",
        "role": "quality",
        "purpose": "Detect ambiguous language (e.g., 'reasonable efforts', 'material', 'substantially') and propose concrete rewrite options.",
        "inputs": ["sections", "chunks"],
        "outputs": ["ambiguities", "rewrite_suggestions"],
        "token_budget_hint": 1600,
    },
    {
        "id": "contradiction_detector",
        "name": "Contradiction Detector",
        "role": "quality",
        "purpose": "Detect internal conflicts between clauses and definitions; produce evidence-linked contradiction reports.",
        "inputs": ["clause_inventory", "sections", "chunks", "definitions_index"],
        "outputs": ["contradictions"],
        "token_budget_hint": 2000,
    },
    {
        "id": "risk_classifier",
        "name": "Risk Classifier",
        "role": "risk",
        "purpose": "Assign severity/likelihood/impact for clause-level risks with rationale; convert into a structured risk register.",
        "inputs": ["clause_inventory", "obligations_table", "policy_notes"],
        "outputs": ["risk_register"],
        "token_budget_hint": 2200,
    },
    {
        "id": "citation_verifier",
        "name": "Citation Verifier",
        "role": "verification",
        "purpose": "Verify every major finding is traceable to specific chunks; flag gaps and weak evidence.",
        "inputs": ["clause_inventory", "risk_register", "contradictions", "ambiguities"],
        "outputs": ["citation_gaps"],
        "token_budget_hint": 1400,
    },
    {
        "id": "hallucination_guard",
        "name": "Hallucination Guard",
        "role": "verification",
        "purpose": "Red-team the draft outputs; detect unsupported claims and force corrections to align strictly with document evidence.",
        "inputs": ["draft_review_pack", "normalized_document", "chunks"],
        "outputs": ["hallucination_flags", "corrected_claims"],
        "token_budget_hint": 1900,
    },
    {
        "id": "missing_clause_detector",
        "name": "Missing Clause Detector",
        "role": "quality",
        "purpose": "Identify expected clause categories that are absent or under-specified given the document type; generate targeted questions.",
        "inputs": ["clause_inventory", "doc_structure", "policy_notes"],
        "outputs": ["missing_clause_questions"],
        "token_budget_hint": 1500,
    },
    {
        "id": "jurisdiction_checker",
        "name": "Jurisdiction Checker",
        "role": "risk",
        "purpose": "Validate governing law / venue / dispute resolution consistency; flag mismatches and enforcement risks.",
        "inputs": ["clause_inventory", "doc_structure"],
        "outputs": ["jurisdiction_risks"],
        "token_budget_hint": 1500,
    },
    {
        "id": "liability_stress_tester",
        "name": "Liability Stress Tester",
        "role": "risk",
        "purpose": "Stress-test limitation of liability vs indemnity/warranty/termination; flag cap too low, carve-outs missing, or asymmetry.",
        "inputs": ["clause_inventory", "risk_register"],
        "outputs": ["liability_findings"],
        "token_budget_hint": 2100,
    },
    {
        "id": "negotiation_advisor",
        "name": "Negotiation Advisor",
        "role": "advisory",
        "purpose": "Turn risks into negotiation moves: redlines, fallback language, questions to ask, and recommended positions.",
        "inputs": ["risk_register", "clause_inventory", "obligations_table"],
        "outputs": ["negotiation_playbook"],
        "token_budget_hint": 2200,
    },
    {
        "id": "review_pack_assembler",
        "name": "Review Pack Assembler",
        "role": "synthesis",
        "purpose": "Assemble a final review pack (inventory, risks, contradictions, rewrites, negotiation playbook) with consistent structure.",
        "inputs": ["exec_summary", "clause_inventory", "obligations_table", "risk_register", "contradictions", "rewrite_suggestions", "negotiation_playbook", "citation_gaps", "missing_clause_questions", "jurisdiction_risks", "liability_findings"],
        "outputs": ["review_pack"],
        "token_budget_hint": 2600,
    },
    {
        "id": "style_enforcer",
        "name": "Style Enforcer",
        "role": "quality",
        "purpose": "Enforce concise formatting and eliminate duplication; ensure the review pack is skimmable and decision-ready.",
        "inputs": ["review_pack"],
        "outputs": ["review_pack_final"],
        "token_budget_hint": 1200,
    },
]

KYC_AGENTS = [
    {
        "id": "retriever",
        "name": "Retriever",
        "role": "retrieval",
        "purpose": "Retrieve relevant policy snippets and case context for the review, optimizing recall within the token budget.",
        "inputs": ["case_facts", "policy_corpus"],
        "outputs": ["retrieved_evidence"],
        "token_budget_hint": 1600,
    },
    {
        "id": "risk_decompose",
        "name": "Risk Decompose",
        "role": "risk",
        "purpose": "Decompose the case into risk themes and required checks; produce a structured risk checklist.",
        "inputs": ["case_facts", "retrieved_evidence"],
        "outputs": ["risk_checklist"],
        "token_budget_hint": 1700,
    },
    {
        "id": "hitl_gate",
        "name": "HITL Gate",
        "role": "verification",
        "purpose": "Gate uncertain/high-risk decisions for human-in-the-loop review; enforce safety and conservative defaults.",
        "inputs": ["risk_checklist", "draft_review"],
        "outputs": ["hitl_requests", "approved_path"],
        "token_budget_hint": 1200,
    },
    {
        "id": "behavior_check",
        "name": "Behavior Check",
        "role": "verification",
        "purpose": "Detect policy violations or unsafe behaviors in the draft output; flag and require corrections.",
        "inputs": ["draft_review"],
        "outputs": ["behavior_flags"],
        "token_budget_hint": 1200,
    },
    {
        "id": "carryover_none",
        "name": "Carryover None",
        "role": "memory",
        "purpose": "Disable carryover/memory to maximize independence and reduce contamination across runs.",
        "inputs": ["run_context"],
        "outputs": ["memory_mode"],
        "token_budget_hint": 400,
    },
    {
        "id": "carryover_compact",
        "name": "Carryover Compact",
        "role": "memory",
        "purpose": "Enable compact carryover of key facts and decisions to stabilize multi-step reasoning with limited tokens.",
        "inputs": ["run_context", "prior_steps"],
        "outputs": ["compact_state"],
        "token_budget_hint": 700,
    },
    {
        "id": "carryover_full",
        "name": "Carryover Full",
        "role": "memory",
        "purpose": "Enable full carryover for maximum continuity across steps when budget allows.",
        "inputs": ["run_context", "prior_steps"],
        "outputs": ["full_state"],
        "token_budget_hint": 1200,
    },
    {
        "id": "adaptive_off",
        "name": "Adaptive Off",
        "role": "control",
        "purpose": "Disable adaptive step selection to use fixed topology for baseline comparison.",
        "inputs": ["search_config"],
        "outputs": ["adaptive_mode"],
        "token_budget_hint": 300,
    },
    {
        "id": "adaptive_on",
        "name": "Adaptive On",
        "role": "control",
        "purpose": "Enable adaptive step selection so the optimizer can adjust which agents run based on intermediate signals.",
        "inputs": ["search_config"],
        "outputs": ["adaptive_mode"],
        "token_budget_hint": 400,
    },
    {
        "id": "adaptive_policy_lenient",
        "name": "Adaptive Policy Lenient",
        "role": "control",
        "purpose": "Use lenient adaptive policy to explore broader combinations and produce denser Pareto candidates.",
        "inputs": ["search_config"],
        "outputs": ["adaptive_policy"],
        "token_budget_hint": 450,
    },
    {
        "id": "adaptive_policy_strict",
        "name": "Adaptive Policy Strict",
        "role": "control",
        "purpose": "Use strict adaptive policy to reduce risk and keep outputs conservative; prioritizes precision and compliance.",
        "inputs": ["search_config"],
        "outputs": ["adaptive_policy"],
        "token_budget_hint": 450,
    },
    {
        "id": "synth_style_A",
        "name": "Synthesis Style A",
        "role": "synthesis",
        "purpose": "Synthesize outputs in a concise, structured, decision-ready format (variant A).",
        "inputs": ["signals", "evidence"],
        "outputs": ["draft_review"],
        "token_budget_hint": 1400,
    },
    {
        "id": "synth_style_B",
        "name": "Synthesis Style B",
        "role": "synthesis",
        "purpose": "Synthesize outputs in a more explanatory, rationale-heavy format (variant B).",
        "inputs": ["signals", "evidence"],
        "outputs": ["draft_review"],
        "token_budget_hint": 1500,
    },
]

def main():
    # pre-check dirs
    for d in [LEGAL_DIR, KYC_DIR]:
        if not d.exists():
            raise SystemExit(f"Missing directory: {d}")

    # patch legal agents
    legal_paths = []
    for spec in LEGAL_AGENTS:
        legal_paths.append(patch_agent(LEGAL_DIR, spec))

    # ensure exactly 18 legal agent yaml files exist for these ids
    legal_ids = {s["id"] for s in LEGAL_AGENTS}
    actual_legal = sorted([p.stem for p in LEGAL_DIR.glob("*.yaml") if not p.name.startswith("_")])
    # We don't delete extras automatically to avoid accidental data loss.
    # But we enforce that required 18 exist.
    missing = sorted(list(legal_ids - set(actual_legal)))
    if missing:
        raise SystemExit(f"Legal agents missing after patch: {missing}")

    # patch kyc agents
    kyc_paths = []
    for spec in KYC_AGENTS:
        kyc_paths.append(patch_agent(KYC_DIR, spec))

    print("=== PATCH SUMMARY ===")
    print(f"Legal patched/created: {len(legal_paths)} (required=18)")
    print(f"KYC patched: {len(kyc_paths)} (required=13)")
    print("Legal agent files (required ids) OK.")
    print("Done.")

if __name__ == "__main__":
    main()
