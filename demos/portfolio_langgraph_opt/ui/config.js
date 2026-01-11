// Page initialization
async function init() {
    await loadAgents();
    await loadEvalConfig();
    await loadRunConfig();
}

// Helper: Show toast message
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

// ========== Agent Registry ==========

async function loadAgents() {
    try {
        const res = await fetch('/api/agents');
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
    
    for (const file of files) {
        try {
            const yaml_text = await file.text();
            const res = await fetch('/api/agents/upsert', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({yaml_text})
            });
            const data = await res.json();
            
            if (data.success) {
                showToast(`Uploaded: ${data.updated.join(', ')}`);
            } else {
                showToast(`Errors: ${data.errors.join(', ')}`);
            }
        } catch (e) {
            showToast('Upload error: ' + e.message);
        }
    }
    
    await loadAgents();
    document.getElementById('agentFileInput').value = '';
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
            body: JSON.stringify({ids: selected})
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
            max_budget: 64,
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
        const res = await fetch('/api/optimize/start', {method: 'POST'});
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
document.addEventListener('DOMContentLoaded', init);
