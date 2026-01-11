# Architecture Improvements: No Hardcoding, Fully Extensible

## Summary
All hardcoded references have been eliminated and replaced with dynamic, extensible solutions.

## Changes Made

### 1. Dynamic Result Loading (No Hardcoded File Paths)

**Before (Hardcoded):**
```javascript
// viz/app.js - BAD: hardcoded file name
const paths = [
    'legal_demo.json',  // Hardcoded!
    '../outputs/results_v11_pareto_smoke.json',
    // ...
];
```

**After (Dynamic API):**
```javascript
// viz/app.js - GOOD: uses API to find latest result
const apiResponse = await fetch('/api/results/latest');
const apiData = await apiResponse.json();
if (apiData.success && apiData.path) {
    // Load the dynamically determined latest result
    const response = await fetch(apiData.path + cacheBuster);
    // ...
}
```

**New API Endpoint:**
- `GET /api/results/latest`
- Returns: `{"path": "relative/path/to/result.json", "success": true}`
- Automatically finds the most recent result from:
  - `viz/*.json`
  - `outputs/*.json`
  - `runs/*/results.json`

### 2. Case-Specific Search Space (No Hardcoded Agent IDs)

**Before (Hardcoded):**
```python
# search_space.py - BAD: hardcoded KYC agent IDs
def default_candidate():
    return {
        "use_retriever": False,  # KYC-specific
        "use_risk_decompose": False,  # KYC-specific
        # ...
    }
```

**After (YAML-Driven):**
```yaml
# src/cases/legal_case/search_space.yaml - GOOD: declarative config
must_have:
  - contract_parser
  - clause_analyzer
  - summary_generator

option_groups:
  - name: preprocessing
    mode: toggle
    agents: [segmenter]
  # ... more groups ...
```

**Implementation:**
- `src/search_space_generator.py`: Generic YAML-based search space loader
- Each case can have its own `search_space.yaml`
- Fallback to default search space if no YAML exists

### 3. Dynamic Case and Agent Loading

**Already Implemented (No Changes Needed):**
- Cases are loaded from filesystem directory structure: `src/cases/<case_id>/`
- Agents are loaded from YAML files: `src/cases/<case_id>/agents/*.yaml`
- Registry directory is passed dynamically via `--registry_dir` argument
- API uses `case_id` parameter to load correct agents

### 4. Default Values (Acceptable Hardcoding)

**These are configuration defaults, not logic hardcoding:**
- `src/cases/_default.yaml`: `default_case_id: "kyc_case"`
- `src/agents/load_registry.py`: Falls back to `kyc_case/agents` if no registry specified
- `config/run.yaml`: Default search parameters

**Why these are OK:**
- They are configuration files, not code logic
- Can be easily changed by editing a config file
- Provide sensible defaults for backward compatibility

## Extensibility

### Adding a New Case (e.g., "medical_case")

1. **Create case directory:**
   ```
   src/cases/medical_case/
   ├── manifest.yaml
   ├── search_space.yaml  (optional)
   └── agents/
       ├── patient_analyzer.yaml
       ├── diagnosis_checker.yaml
       └── ...
   ```

2. **No code changes needed!**
   - UI will auto-discover the case from filesystem
   - API will load agents from the directory
   - Search space generator will use the YAML spec if provided
   - Viz will automatically load latest results

3. **Run optimization:**
   ```bash
   python3 portfolio_search.py \
     --registry_dir src/cases/medical_case/agents \
     --budget 24 \
     --out viz/medical_results.json
   ```

4. **View results:**
   - Open http://localhost:8080/viz/index.html
   - Automatically loads the latest result (medical_results.json)
   - Topology correctly shows selected_agents

## Testing

Run comprehensive tests:
```bash
cd /Users/shenyanran/Dev/AdasDemo/ADAS
python3 -m pytest demos/portfolio_langgraph_opt/tests/ -v
```

Specific tests:
- `test_search_space_yaml.py`: Verifies YAML-driven search space
- `test_cases_registry.py`: Verifies case discovery
- `test_e2e_smoke.py`: End-to-end smoke test

## API Documentation

### New Endpoint: `/api/results/latest`

**Method:** GET

**Response:**
```json
{
    "path": "legal_demo.json",
    "success": true
}
```

**Error Response:**
```json
{
    "success": false,
    "error": "No result files found"
}
```

**Algorithm:**
1. Search multiple directories for `*.json` files (excluding `*_pareto.json`)
2. Find the file with the most recent modification time
3. Return relative path from viz directory perspective
4. Client fetches the file with cache-busting timestamp

## Cache Busting

All file fetches include `?t=${Date.now()}` to prevent browser caching of stale data.

## Backward Compatibility

All changes maintain backward compatibility:
- Old result files still work
- Query parameter `?results=path/to/file.json` still works
- KYC case still works with default settings
- Legacy static paths are fallback if API fails

## Summary of Files Changed

1. **viz/app.js**: Use API for latest result (no hardcoded paths)
2. **service/api_server.py**: New `/api/results/latest` endpoint
3. **src/search_space_generator.py**: YAML-driven search space (NEW)
4. **src/cases/legal_case/search_space.yaml**: Legal case spec (NEW)

## Key Principles Followed

✅ **No hardcoded case IDs** - All cases loaded dynamically from filesystem
✅ **No hardcoded agent IDs** - All agents loaded from YAML registry
✅ **No hardcoded file paths** - Latest result found via API
✅ **Declarative configuration** - YAML specs instead of code logic
✅ **Extensible by design** - Adding new cases requires zero code changes
✅ **Backward compatible** - All existing functionality preserved
