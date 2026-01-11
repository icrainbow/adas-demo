// Global state for case selection
let currentCaseId = null;

// Helper: Show toast message
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

// ========== Case Selection ==========

function renderCaseSelector() {
    console.log('renderCaseSelector called');
    
    // Avoid duplicate insertion
    if (document.getElementById('caseSelect')) {
        console.log('Case selector already exists, skipping');
        return;
    }
    
    // Find main container - try multiple strategies
    let targetContainer = document.querySelector('.container') || 
                         document.querySelector('main') || 
                         document.body;
    
    console.log('Target container:', targetContainer);
    
    // Create wrapper
    const wrapper = document.createElement('div');
    wrapper.className = 'section';
    wrapper.style.marginBottom = '20px';
    wrapper.innerHTML = `
        <h2>Use Case Selection</h2>
        <div class="form-group">
            <label for="caseSelect">Select Use Case:</label>
            <select id="caseSelect" style="width: 300px; padding: 8px; font-size: 14px;">
                <option value="">-- Loading cases --</option>
            </select>
            <p class="help-text">Each use case defines its own agent pool context.</p>
        </div>
    `;
    
    // Insert at the very beginning
    if (targetContainer.firstChild) {
        targetContainer.insertBefore(wrapper, targetContainer.firstChild);
    } else {
        targetContainer.appendChild(wrapper);
    }
    
    console.log('Case selector inserted, element:', document.getElementById('caseSelect'));
    
    // Add change event listener
    const selector = document.getElementById('caseSelect');
    if (selector) {
        selector.addEventListener('change', async () => {
            currentCaseId = selector.value || null;
            console.log('Case changed to:', currentCaseId);
            if (currentCaseId) {
                await loadAgents();
            }
        });
    }
}

async function loadCases() {
    try {
        const selector = document.getElementById('caseSelect');
        if (!selector) {
            console.error('Case selector not found in DOM');
            showToast('Case selector not found in DOM');
            return;
        }
        
        console.log('Fetching /api/cases...');
        const res = await fetch('/api/cases');
        const data = await res.json();
        console.log('Received data:', data);
        
        selector.innerHTML = '';
        
        if (!data.cases || data.cases.length === 0) {
            console.warn('No cases found in response:', data);
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'No cases available';
            selector.appendChild(opt);
            currentCaseId = null;
            await loadAgents();
            return;
        }
        
        console.log(`Loading ${data.cases.length} cases...`);
        
        data.cases.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.case_id;
            opt.textContent = `${c.display_name} (v${c.version || '1.0.0'})`;
            selector.appendChild(opt);
        });
        
        // Default selection
        let defaultCaseId = null;
        try {
            const dres = await fetch('/api/cases/default');
            const d = await dres.json();
            defaultCaseId = d.default_case_id || null;
        } catch (e) {
            defaultCaseId = null;
        }
        
        currentCaseId = defaultCaseId || data.cases[0].case_id;
        selector.value = currentCaseId;
        
        await loadAgents();
    } catch (e) {
        showToast('Error loading cases: ' + e.message);
    }
}

// ========== Agent Registry ==========

async function loadAgents() {
    try {
        const url = currentCaseId
            ? `/api/agents?case_id=${encodeURIComponent(currentCaseId)}`
            : '/api/agents';
        
        const res = await fetch(url);
        const data = await res.json();
        populateAgentTable(data.agents || []);
    } catch (e) {
        showToast('Error loading agents: ' + e.message);
    }
}

function populateAgentTable(agents) {
    const tbody = document.getElementById('agentTableBody');
    tbody.innerHTML = '';
    
    if (agents.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5">No agents found. Upload agent YAML files to get started.</td></tr>';
        return;
    }
    
    agents.forEach(agent => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><input type="checkbox" class="agent-checkbox" value="${agent.id}" /></td>
            <td>${agent.id}</td>
            <td>${agent.name || agent.id}</td>
            <td>${agent.purpose || ''}</td>
            <td>${agent.role || ''}</td>
        `;
        tbody.appendChild(row);
    });
}

function toggleSelectAll() {
    const checked = document.getElementById('selectAll').checked;
    document.querySelectorAll('.agent-checkbox').forEach(cb => cb.checked = checked);
}

async function uploadAgents() {
    const files = document.getElementById('agentFileInput').files;
    if (files.length === 0) {
        showToast('Please select YAML file(s) to upload');
        return;
    }
    
    const allUpdated = [];
    const allErrors = [];
    
    for (const file of files) {
        // Check file size limit (100KB)
        if (file.size > 100 * 1024) {
            allErrors.push(`${file.name}: exceeds 100KB limit`);
            continue;
        }
        
        try {
            const yaml_text = await file.text();
            const res = await fetch('/api/agents/upsert', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    yaml_text,
                    case_id: currentCaseId
                })
            });
            const data = await res.json();
            
            if (data.success) {
                allUpdated.push(...(data.updated || []));
            } else {
                allErrors.push(...(data.errors || [`${file.name}: upload failed`]));
            }
        } catch (e) {
            allErrors.push(`${file.name}: ${e.message}`);
        }
    }
    
    // Refresh agent list once
    await loadAgents();
    document.getElementById('agentFileInput').value = '';
    
    // Show single summary toast
    const summary = [];
    if (allUpdated.length > 0) {
        summary.push(`Uploaded: ${allUpdated.length} agent(s) (${allUpdated.join(', ')})`);
    }
    if (allErrors.length > 0) {
        summary.push(`Errors: ${allErrors.length}`);
        if (allErrors.length <= 3) {
            summary.push(`(${allErrors.join('; ')})`);
        }
    }
    showToast(summary.join(' | ') || 'No agents uploaded');
}

async function deleteSelected() {
    const selected = Array.from(document.querySelectorAll('.agent-checkbox:checked'))
        .map(cb => cb.value);
    
    if (selected.length === 0) {
        showToast('No agents selected');
        return;
    }
    
    if (!confirm(`Delete ${selected.length} agent(s)?`)) {
        return;
    }
    
    try {
        const res = await fetch('/api/agents/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                ids: selected,
                case_id: currentCaseId
            })
        });
        const data = await res.json();
        
        if (data.success) {
            showToast(`Deleted: ${data.deleted.join(', ')}`);
            await loadAgents();
        } else {
            showToast(`Errors: ${data.errors.join(', ')}`);
        }
    } catch (e) {
        showToast('Delete error: ' + e.message);
    }
}

// ========== Evaluation Config ==========

async function loadEvalConfig() {
    try {
        const res = await fetch('/api/config/eval');
        const data = await res.json();
        
        if (data.weights) {
            document.getElementById('coverageWeight').value = data.weights.coverage_weight || 100.0;
            document.getElementById('violationPenalty').value = data.weights.violation_penalty || 200.0;
            document.getElementById('hitlPenalty').value = data.weights.hitl_penalty || 10.0;
            document.getElementById('stepPenalty').value = data.weights.step_penalty || 1.0;
            document.getElementById('tokenPenalty').value = data.weights.token_penalty || 0.01;
        }
    } catch (e) {
        showToast('Error loading eval config: ' + e.message);
    }
}

async function saveEvalConfig() {
    const config = {
        weights: {
            coverage_weight: parseFloat(document.getElementById('coverageWeight').value),
            violation_penalty: parseFloat(document.getElementById('violationPenalty').value),
            hitl_penalty: parseFloat(document.getElementById('hitlPenalty').value),
            step_penalty: parseFloat(document.getElementById('stepPenalty').value),
            token_penalty: parseFloat(document.getElementById('tokenPenalty').value)
        },
        sampling: {
            k_low: 2,
            k_high: 2,
            k_mid: 2
        }
    };
    
    try {
        const res = await fetch('/api/config/eval/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        const data = await res.json();
        
        if (data.success) {
            showToast('Evaluation config saved');
        } else {
            showToast('Save error: ' + data.error);
        }
    } catch (e) {
        showToast('Save error: ' + e.message);
    }
}

// ========== Run Config ==========

async function loadRunConfig() {
    try {
        const res = await fetch('/api/config/run');
        const data = await res.json();
        
        if (data.dataset) {
            document.getElementById('casesPath').value = data.dataset.cases_path || '';
            document.getElementById('policyPath').value = data.dataset.policy_path || '';
        }
        if (data.search) {
            document.getElementById('mode').value = data.search.mode || 'grid';
            document.getElementById('budget').value = data.search.budget || 16;
            document.getElementById('seed').value = data.search.seed || 7;
        }
    } catch (e) {
        showToast('Error loading run config: ' + e.message);
    }
}

async function saveRunConfig() {
    const config = {
        dataset: {
            cases_path: document.getElementById('casesPath').value,
            policy_path: document.getElementById('policyPath').value
        },
        search: {
            mode: document.getElementById('mode').value,
            budget: parseInt(document.getElementById('budget').value),
            seed: parseInt(document.getElementById('seed').value)
        },
        output: {
            output_dir: "demos/portfolio_langgraph_opt/runs",
            emit_dot: true,
            lite_mode: true
        },
        safety: {
            // aligned with CLI/service cap to avoid failing runs
            max_budget: 32,
            max_file_upload_mb: 1,
            max_concurrency: 1,
            timeout_seconds: 3600
        }
    };
    
    try {
        const res = await fetch('/api/config/run/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        const data = await res.json();
        
        if (data.success) {
            showToast('Run config saved');
        } else {
            showToast('Save error: ' + data.error);
        }
    } catch (e) {
        showToast('Save error: ' + e.message);
    }
}

// ========== Optimization ==========

async function startOptimization() {
    document.getElementById('progressPanel').style.display = 'block';
    document.getElementById('statusText').textContent = 'Running...';
    document.getElementById('warningText').textContent = '';
    document.getElementById('viewResultsBtn').disabled = true;
    
    try {
        const res = await fetch('/api/optimize/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                case_id: currentCaseId
            })
        });
        const data = await res.json();
        
        if (data.success) {
            document.getElementById('runId').textContent = data.run_id;
            document.getElementById('statusText').textContent = 'Complete';
            if (data.warning) {
                document.getElementById('warningText').textContent = 'Warning: ' + data.warning;
            }
            document.getElementById('viewResultsBtn').disabled = false;
            window.lastRunId = data.run_id;
            showToast('Optimization complete!');
        } else {
            document.getElementById('statusText').textContent = 'Error';
            document.getElementById('warningText').textContent = 'Error: ' + data.error;
            showToast('Optimization failed: ' + data.error);
        }
    } catch (e) {
        document.getElementById('statusText').textContent = 'Error';
        document.getElementById('warningText').textContent = 'Error: ' + e.message;
        showToast('Error: ' + e.message);
    }
}

function viewResults() {
    const runId = window.lastRunId;
    if (!runId) {
        showToast('No run ID available');
        return;
    }
    const url = `/viz/index.html?results=/runs/${runId}/results.json`;
    window.open(url, '_blank');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    console.log('=== DOMContentLoaded fired ===');
    console.log('Body:', document.body);
    console.log('First element:', document.body.firstChild);
    
    renderCaseSelector();
    
    console.log('After renderCaseSelector, element:', document.getElementById('caseSelect'));
    
    await loadCases();
    await loadEvalConfig();
    await loadRunConfig();
    
    console.log('=== Initialization complete ===');
});
