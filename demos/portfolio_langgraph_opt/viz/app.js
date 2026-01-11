// Global state
let resultsData = null;
let candidatesManifest = null;
let chartInstance = null;
let selectedCandidate = null;
let paretoSet = new Set();
let allCandidatesData = []; // Store for re-rendering
let xAxisMode = 'tokens'; // 'tokens' or 'cost'
let tokenPrice = 0.01; // USD per 1k tokens

// Load results data
async function loadResultsData() {
    // Check for URL query parameter first
    const params = new URLSearchParams(window.location.search);
    const resultsParam = params.get('results');
    
    if (resultsParam) {
        // Use the results path from query parameter
        try {
            // Add cache-busting timestamp to force fresh load
            const cacheBuster = `?t=${Date.now()}`;
            const response = await fetch(resultsParam + cacheBuster);
            if (response.ok) {
                const data = await response.json();
                console.log('Loaded data from query param:', resultsParam);
                return data;
            } else {
                console.error('Failed to load from query param:', resultsParam, 'Status:', response.status);
                throw new Error(`Failed to load results from ${resultsParam}: ${response.status}`);
            }
        } catch (e) {
            console.error('Error loading from query param:', e);
            throw new Error(`Could not load results from ${resultsParam}: ${e.message}`);
        }
    }
    
    // Try to get latest result from API (dynamic, no hardcoding)
    try {
        const apiResponse = await fetch('/api/results/latest');
        if (apiResponse.ok) {
            const apiData = await apiResponse.json();
            if (apiData.success && apiData.path) {
                console.log('API returned latest result path:', apiData.path);
                const cacheBuster = `?t=${Date.now()}`;
                const response = await fetch(apiData.path + cacheBuster);
                if (response.ok) {
                    const data = await response.json();
                    console.log('Loaded latest result data from:', apiData.path);
                    return data;
                }
            }
        }
    } catch (e) {
        console.log('Could not fetch from API /api/results/latest:', e);
    }
    
    // Fallback to legacy static paths if API fails
    const paths = [
        '../outputs/results_v11_pareto_smoke.json',
        './outputs/results_v11_pareto_smoke.json',
        'outputs/results_v11_pareto_smoke.json'
    ];
    
    for (const path of paths) {
        try {
            // Add cache-busting timestamp to force fresh load
            const cacheBuster = `?t=${Date.now()}`;
            const response = await fetch(path + cacheBuster);
            if (response.ok) {
                const data = await response.json();
                console.log('Loaded data from:', path);
                return data;
            }
        } catch (e) {
            console.log('Failed to load from:', path);
        }
    }
    
    throw new Error('Could not load results JSON from any known path');
}

// Load candidates manifest
async function loadCandidatesManifest() {
    // Try multiple paths
    const paths = [
        '../artifacts/candidates_manifest.json',
        './artifacts/candidates_manifest.json',
        'artifacts/candidates_manifest.json'
    ];
    
    for (const path of paths) {
        try {
            const response = await fetch(path);
            if (response.ok) {
                const data = await response.json();
                console.log('Loaded manifest from:', path);
                return data;
            }
        } catch (e) {
            console.log('Failed to load manifest from:', path);
        }
    }
    
    console.warn('Could not load candidates manifest - will parse names instead');
    return null;
}

// Compute Pareto frontier
function computeParetoFrontier(candidates) {
    const pareto = [];
    
    for (const candidate of candidates) {
        let isDominated = false;
        
        for (const other of candidates) {
            if (candidate === other) continue;
            
            const tokens_a = candidate.metrics.avg_total_tokens || 0;
            const coverage_a = candidate.metrics.avg_coverage || 0;
            const tokens_b = other.metrics.avg_total_tokens || 0;
            const coverage_b = other.metrics.avg_coverage || 0;
            
            // Check if 'other' dominates 'candidate'
            const coverageBetter = coverage_b >= coverage_a;
            const tokensBetter = tokens_b <= tokens_a;
            const strictlyBetter = coverage_b > coverage_a || tokens_b < tokens_a;
            
            if (coverageBetter && tokensBetter && strictlyBetter) {
                isDominated = true;
                break;
            }
        }
        
        if (!isDominated) {
            pareto.push(candidate);
        }
    }
    
    return pareto;
}

// Calculate cost per case
function calculateCost(tokens, pricePerK) {
    return (tokens / 1000) * pricePerK;
}

// Get X value based on current mode
function getXValue(candidate) {
    const tokens = candidate.metrics.avg_total_tokens || 0;
    if (xAxisMode === 'cost') {
        return calculateCost(tokens, tokenPrice);
    }
    return tokens;
}

// Get X axis label
function getXAxisLabel() {
    if (xAxisMode === 'cost') {
        return `Cost per Case (USD @ $${tokenPrice.toFixed(3)}/1k tokens)`;
    }
    return 'Average Total Tokens';
}

// Format X value for display
function formatXValue(value) {
    if (xAxisMode === 'cost') {
        return '$' + value.toFixed(4);
    }
    return value.toFixed(0);
}

// Apply deterministic jitter for visual separation (DISPLAY ONLY)
function applyDeterministicJitter(candidate) {
    // Simple deterministic hash (32-bit)
    function simpleHash(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = ((hash << 5) - hash) + str.charCodeAt(i);
            hash = hash & hash; // 32-bit
        }
        return Math.abs(hash);
    }

    const name = (candidate && candidate.name) ? candidate.name : JSON.stringify(candidate);
    const hash = simpleHash(name);

    // Magnitudes: ±1.0 token, ±0.003 coverage (0.3%)
    const jitterX = ((hash % 100) / 100 - 0.5) * 2.0;
    const jitterY = ((hash % 37) / 37 - 0.5) * 0.006;

    return { x: jitterX, y: jitterY };
}

// Generate DOT from selected_agents array (TRUE TOPOLOGY)
function generateDOTFromAgents(agents, candidateName) {
    console.log(`🎯 generateDOTFromAgents called with ${agents.length} agents:`, agents);
    
    let dot = 'digraph Topology {\n';
    dot += '  rankdir=LR;\n';
    dot += '  bgcolor="white";\n';
    dot += '  labelloc="t";\n';
    dot += `  label="${candidateName} (${agents.length} agents)";\n`;
    dot += '  fontname="Arial Bold";\n';
    dot += '  fontsize=14;\n\n';
    dot += '  node [shape=box, style="rounded,filled", fontname="Arial", fontsize=11, fillcolor="#E3F2FD"];\n\n';

    dot += '  start [label="Start", shape=circle, fillcolor="#4CAF50"];\n';
    dot += '  end [label="End", shape=circle, fillcolor="#F44336"];\n\n';

    agents.forEach((agent, idx) => {
        // Escape quotes in agent names
        const safe = String(agent).replace(/"/g, '\\"');
        dot += `  agent_${idx} [label="${safe}"];\n`;
    });

    dot += '\n';

    if (!agents || agents.length === 0) {
        dot += '  start -> end;\n';
    } else {
        dot += '  start -> agent_0;\n';
        for (let i = 0; i < agents.length - 1; i++) {
            dot += `  agent_${i} -> agent_${i + 1};\n`;
        }
        dot += `  agent_${agents.length - 1} -> end;\n`;
    }

    dot += '}\n';
    console.log('🎯 Generated DOT:', dot);
    return dot;
}

// Create scatter chart
function createScatterChart(data) {
    const ctx = document.getElementById('paretoChart').getContext('2d');
    
    // Extract all candidates
    allCandidatesData = data.all_scores.map(entry => ({
        name: entry.name,
        metrics: entry.metrics,
        score: entry.score
    }));
    
    // Render the chart
    renderChart();
    
    return allCandidatesData;
}

// Render or re-render chart
function renderChart() {
    const ctx = document.getElementById('paretoChart').getContext('2d');
    
    // Destroy existing chart if present
    if (chartInstance) {
        chartInstance.destroy();
    }
    
    // Add baseline and best
    const baseline = {
        name: 'baseline',
        metrics: resultsData.baseline.metrics,
        score: resultsData.baseline.score,
        isBaseline: true
    };
    
    const best = {
        name: 'best',
        metrics: resultsData.best.metrics,
        score: resultsData.best.score,
        isBest: true
    };
    
    // Compute Pareto frontier
    const paretoFrontier = computeParetoFrontier(allCandidatesData);
    paretoSet = new Set(paretoFrontier.map(c => c.name));
    
    // Prepare datasets
    const allPoints = allCandidatesData.map(c => {
        const jitter = applyDeterministicJitter(c);
        const trueX = getXValue(c);
        const trueY = c.metrics.avg_coverage || 0;
        return {
            x: trueX + jitter.x,
            y: trueY + jitter.y,
            candidate: c,
            trueX: trueX,
            trueY: trueY
        };
    });
    
    const paretoPoints = paretoFrontier.map(c => {
        const jitter = applyDeterministicJitter(c);
        const trueX = getXValue(c);
        const trueY = c.metrics.avg_coverage || 0;
        return {
            x: trueX + jitter.x,
            y: trueY + jitter.y,
            candidate: c,
            trueX: trueX,
            trueY: trueY
        };
    });
    
    // Sort Pareto points by X for line connection
    paretoPoints.sort((a, b) => a.x - b.x);
    
    const baselinePoint = {
        x: getXValue(baseline),
        y: baseline.metrics.avg_coverage || 0,
        candidate: baseline
    };
    
    const bestPoint = {
        x: getXValue(best),
        y: best.metrics.avg_coverage || 0,
        candidate: best
    };
    
    // Create chart
    chartInstance = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'All Candidates',
                    data: allPoints,
                    backgroundColor: 'rgba(150, 150, 150, 0.6)',
                    borderColor: 'rgba(150, 150, 150, 0.8)',
                    borderWidth: 1,
                    pointRadius: 6,
                    pointHoverRadius: 8
                },
                {
                    label: 'Pareto Frontier',
                    data: paretoPoints,
                    backgroundColor: 'rgba(54, 162, 235, 0.8)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 2,
                    pointRadius: 8,
                    pointHoverRadius: 10,
                    showLine: true,
                    borderDash: [5, 5],
                    fill: false
                },
                {
                    label: 'Baseline',
                    data: [baselinePoint],
                    backgroundColor: 'rgba(75, 192, 192, 0.8)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 2,
                    pointRadius: 12,
                    pointHoverRadius: 14,
                    pointStyle: 'star'
                },
                {
                    label: 'Best (by score)',
                    data: [bestPoint],
                    backgroundColor: 'rgba(255, 99, 132, 0.8)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 2,
                    pointRadius: 12,
                    pointHoverRadius: 14,
                    pointStyle: 'star'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            onClick: (event, activeElements) => {
                if (activeElements.length > 0) {
                    const element = activeElements[0];
                    const datasetIndex = element.datasetIndex;
                    const index = element.index;
                    const point = chartInstance.data.datasets[datasetIndex].data[index];
                    selectCandidate(point.candidate);
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const point = context.raw;
                            const candidate = point.candidate;
                            
                            // Use true (unjittered) values if available
                            const displayCoverage = point.trueY !== undefined ? point.trueY : candidate.metrics.avg_coverage;
                            const displayTokens = point.trueX !== undefined ? point.trueX : candidate.metrics.avg_total_tokens;
                            
                            return [
                                `Name: ${candidate.name}`,
                                `Coverage: ${(displayCoverage * 100).toFixed(2)}%`,
                                `Tokens: ${displayTokens.toFixed(1)}`,
                                `Cost: $${calculateCost(displayTokens, tokenPrice).toFixed(4)}`,
                                `Score: ${candidate.score.toFixed(2)}`
                            ];
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: getXAxisLabel(),
                        font: {
                            size: 14,
                            weight: 'bold'
                        }
                    },
                    ticks: {
                        callback: function(value) {
                            return formatXValue(value);
                        }
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Average Coverage',
                        font: {
                            size: 14,
                            weight: 'bold'
                        }
                    },
                    ticks: {
                        callback: function(value) {
                            return (value * 100).toFixed(0) + '%';
                        }
                    },
                    min: 0,
                    max: 1
                }
            }
        }
    });
}

// Populate candidate dropdown
function populateCandidateDropdown(candidates) {
    const select = document.getElementById('candidateSelect');
    
    // Sort candidates by score descending
    const sorted = [...candidates].sort((a, b) => b.score - a.score);
    
    sorted.forEach(candidate => {
        const option = document.createElement('option');
        option.value = candidate.name;
        option.textContent = `${candidate.name} (score: ${candidate.score.toFixed(2)})`;
        if (paretoSet.has(candidate.name)) {
            option.textContent += ' [Pareto]';
        }
        select.appendChild(option);
    });
    
    // Add event listener
    select.addEventListener('change', (e) => {
        const name = e.target.value;
        if (name) {
            const candidate = candidates.find(c => c.name === name);
            if (candidate) {
                selectCandidate(candidate);
            }
        }
    });
}

// Select candidate and update UI
function selectCandidate(candidate) {
    selectedCandidate = candidate;
    
    // Update dropdown
    const select = document.getElementById('candidateSelect');
    select.value = candidate.name || '';
    
    // Update metrics
    updateMetricsPanel(candidate);
    
    // Generate and render topology
    generateTopology(candidate);
}

// Update metrics panel
function updateMetricsPanel(candidate) {
    document.getElementById('candidateName').textContent = candidate.name || 'Unknown';
    document.getElementById('metricCoverage').textContent = 
        (candidate.metrics.avg_coverage * 100).toFixed(1) + '%';
    document.getElementById('metricTokens').textContent = 
        candidate.metrics.avg_total_tokens.toFixed(1);
    document.getElementById('metricSteps').textContent = 
        candidate.metrics.avg_steps.toFixed(2);
    document.getElementById('metricHitl').textContent = 
        (candidate.metrics.hitl_rate * 100).toFixed(1) + '%';
    document.getElementById('metricScore').textContent = 
        candidate.score.toFixed(2);
    document.getElementById('metricViolation').textContent = 
        (candidate.metrics.violation_rate * 100).toFixed(1) + '%';
    
    // Update derived costs
    updateDerivedCosts(candidate);
}

// Update derived cost displays
function updateDerivedCosts(candidate) {
    const tokens = candidate.metrics.avg_total_tokens;
    const costPerCase = calculateCost(tokens, tokenPrice);
    const costPer1kCases = costPerCase * 1000;
    
    document.getElementById('costPerCase').textContent = '$' + costPerCase.toFixed(4);
    document.getElementById('costPer1kCases').textContent = '$' + costPer1kCases.toFixed(2);
}

// Parse candidate name to extract configuration
function parseCandidateName(name) {
    // Format: R{0/1}-D{0/1}-B{0/1}-H{0/1}-S{A/B}-M{n}-AD{0/1}-AP{S/L}-CO{0/1/2}
    const parts = name.split('-');
    const config = {};
    
    parts.forEach(part => {
        if (part.startsWith('R')) config.retriever = part.substring(1) === '1';
        else if (part.startsWith('D')) config.risk_decompose = part.substring(1) === '1';
        else if (part.startsWith('B')) config.behavior_check = part.substring(1) === '1';
        else if (part.startsWith('H')) config.hitl_gate = part.substring(1) === '1';
        else if (part.startsWith('S')) config.synth_style = part.substring(1);
        else if (part.startsWith('M')) config.max_steps = parseInt(part.substring(1));
        else if (part.startsWith('AD')) config.adaptive = part.substring(2) === '1';
        else if (part.startsWith('AP')) config.adaptive_policy = part.substring(2);
        else if (part.startsWith('CO')) config.carryover = part.substring(2);
    });
    
    return config;
}

// Get candidate configuration
function getCandidateConfig(candidateName) {
    // Try to get from manifest first
    if (candidatesManifest && candidatesManifest.by_name && candidatesManifest.by_name[candidateName]) {
        return candidatesManifest.by_name[candidateName];
    }
    
    // Fallback to parsing name
    return parseCandidateName(candidateName);
}

// Generate Graphviz DOT for topology (beautified)
function generateDOT(candidate) {
    // Try to get config from multiple sources
    let config;
    
    // First: try candidate_spec.derived (new format)
    if (candidate.candidate_spec && candidate.candidate_spec.derived) {
        config = candidate.candidate_spec.derived;
        console.log('Using candidate_spec.derived for DOT generation');
    }
    // Second: try candidate.candidate (old format)
    else if (candidate.candidate) {
        config = candidate.candidate;
        console.log('Using candidate.candidate for DOT generation');
    }
    // Third: try parsing from name
    else if (candidate.name) {
        config = getCandidateConfig(candidate.name);
        console.log('Parsing candidate name for DOT generation');
    }
    // Fallback: use minimal default
    else {
        console.warn('No candidate config found, using defaults');
        config = {
            use_retriever: false,
            use_risk_decompose: false,
            use_behavior_check: false,
            use_hitl_gate: false,
            synth_style: 'A',
            max_steps: 4,
            adaptive: false,
            carryover: 'compact'
        };
    }
    
    const candidateName = candidate.name || 'Unknown';
    
    let dot = 'digraph Topology {\n';
    dot += '  // Graph settings\n';
    dot += '  rankdir=LR;\n';
    dot += '  bgcolor="white";\n';
    dot += '  labelloc="t";\n';
    dot += `  label="${candidateName}";\n`;
    dot += '  fontname="Arial Bold";\n';
    dot += '  fontsize=14;\n\n';
    
    dot += '  // Default node style\n';
    dot += '  node [shape=box, style="rounded,filled", fontname="Arial", fontsize=11];\n';
    dot += '  edge [fontname="Arial", fontsize=9, color="#666666"];\n\n';
    
    // Start node
    dot += '  // Start/End nodes\n';
    dot += '  start [label="Start", shape=ellipse, fillcolor="#90EE90", color="#4CAF50", penwidth=2];\n';
    dot += '  end [label="End", shape=ellipse, fillcolor="#90EE90", color="#4CAF50", penwidth=2];\n\n';
    
    // Build processing pipeline
    dot += '  // Processing pipeline\n';
    const nodes = [];
    let firstNode = null;
    
    if (config.use_risk_decompose) {
        dot += '  risk_decompose [label="Risk\\nDecompose", fillcolor="#B3E5FC", color="#0288D1", penwidth=2];\n';
        nodes.push('risk_decompose');
        if (!firstNode) firstNode = 'risk_decompose';
    }
    
    if (config.use_behavior_check) {
        dot += '  behavior_check [label="Behavior\\nCheck", fillcolor="#B3E5FC", color="#0288D1", penwidth=2];\n';
        nodes.push('behavior_check');
        if (!firstNode) firstNode = 'behavior_check';
    }
    
    if (config.use_retriever) {
        dot += '  retriever [label="Policy\\nRetriever", fillcolor="#FFF9C4", color="#F57C00", penwidth=2];\n';
        nodes.push('retriever');
        if (!firstNode) firstNode = 'retriever';
    }
    
    // Synth node (always present)
    dot += '  synth [label="Synthesis\\n(Style ' + config.synth_style + ')", fillcolor="#FFCDD2", color="#C62828", penwidth=2];\n';
    
    // HITL gate (optional)
    if (config.use_hitl_gate) {
        dot += '  hitl_gate [label="HITL\\nGate", shape=diamond, fillcolor="#FFF59D", color="#F57F17", penwidth=2];\n';
    }
    
    // Adaptive routing (if enabled)
    if (config.adaptive) {
        dot += '\n  // Adaptive routing\n';
        dot += '  adaptive [label="Adaptive\\nRouting", shape=diamond, fillcolor="#FFE0B2", color="#E65100", penwidth=2, style="filled,dashed"];\n';
    }
    
    // Configuration note
    dot += '\n  // Configuration note\n';
    const carryoverMap = {'0': 'none', '1': 'compact', '2': 'full', 'none': 'none', 'compact': 'compact', 'full': 'full'};
    const carryoverText = carryoverMap[config.carryover] || config.carryover;
    dot += `  config_note [label="Max Steps: ${config.max_steps}\\nCarryover: ${carryoverText}", shape=note, fillcolor="#E1BEE7", color="#7B1FA2", style=filled];\n`;
    
    // Build edges
    dot += '\n  // Main flow\n';
    let prev = 'start';
    
    // Connect to first node
    if (firstNode) {
        dot += `  ${prev} -> ${firstNode};\n`;
        prev = firstNode;
    } else {
        // Direct to synth if no processing nodes
        dot += `  ${prev} -> synth;\n`;
        prev = 'synth';
    }
    
    // Connect processing nodes in order
    for (let i = 1; i < nodes.length; i++) {
        dot += `  ${nodes[i-1]} -> ${nodes[i]};\n`;
        prev = nodes[i];
    }
    
    // Connect adaptive routing if enabled
    if (config.adaptive) {
        dot += `  ${prev} -> adaptive [style=dashed, color="#FF6F00"];\n`;
        dot += `  adaptive -> synth [label="route"];\n`;
    } else {
        // Connect last node to synth
        if (nodes.length > 0) {
            dot += `  ${prev} -> synth;\n`;
        }
    }
    
    // Connect HITL gate if present
    if (config.use_hitl_gate) {
        dot += '  synth -> hitl_gate;\n';
        dot += '  hitl_gate -> end [label="approve", color="#4CAF50"];\n';
        dot += '  hitl_gate -> end [label="escalate", style=dashed, color="#F44336"];\n';
    } else {
        dot += '  synth -> end;\n';
    }
    
    // Connect config note to synth
    dot += '\n  // Configuration metadata\n';
    dot += '  config_note -> synth [style=dotted, color="#9C27B0", arrowhead=none];\n';
    
    dot += '}\n';
    
    return dot;
}

// Render topology using Viz.js
async function generateTopology(candidate) {
    const container = document.getElementById('topologyContainer');
    container.innerHTML = '<div class="loading-message">Rendering topology...</div>';
    
    try {
        let dot;
        let isRealDot = false;
        
        console.log('🔍 generateTopology called for candidate:', candidate.name);
        console.log('🔍 candidate_spec:', candidate.candidate_spec);
        
        // Priority 1: Real DOT from backend
        if (candidate.candidate_spec && candidate.candidate_spec.dot) {
            dot = candidate.candidate_spec.dot;
            isRealDot = true;
            console.log('✅ Using real DOT from candidate_spec.dot');
        }
        // Priority 2: Generate from selected_agents array (NEW!)
        else if (candidate.candidate_spec && candidate.candidate_spec.selected_agents) {
            const agents = candidate.candidate_spec.selected_agents;
            console.log(`✅ Using selected_agents (${agents.length} agents):`, agents);
            dot = generateDOTFromAgents(agents, candidate.name);
            isRealDot = true;
        }
        // Priority 3: Fallback to inferred DOT (backward compatibility)
        else {
            console.log('⚠️ Using inferred DOT (no candidate_spec data found)');
            console.log('⚠️ Full candidate object:', candidate);
            dot = generateDOT(candidate);
            isRealDot = false;
        }
        
        // Use Viz.js to render (v3+ API)
        if (typeof Viz === 'undefined') {
            throw new Error('Viz.js library not loaded');
        }
        
        // Viz.js v3+ uses Viz.instance() to get a renderer instance
        let svg;
        try {
            if (typeof Viz.instance === 'function') {
                // v3+ standalone: await Viz.instance() then renderSVGElement
                const instance = await Viz.instance();
                svg = await instance.renderSVGElement(dot);
            } else if (typeof Viz.renderSVGElement === 'function') {
                // v3+ direct method (some builds)
                svg = await Viz.renderSVGElement(dot);
            } else if (typeof Viz === 'function') {
                // v3+ calling Viz as function
                const instance = await Viz();
                svg = await instance.renderSVGElement(dot);
            } else {
                // Debug info for unsupported version
                console.error('Viz object methods:', Object.keys(Viz));
                throw new Error('Unsupported Viz.js API - no known render method found');
            }
        } catch (renderError) {
            console.error('Viz.js render error:', renderError);
            throw renderError;
        }
        
        container.innerHTML = '';
        container.appendChild(svg);
        
        // Update DOT source badge
        updateDotSourceBadge(isRealDot);
    } catch (error) {
        console.error('Error rendering topology:', error);
        container.innerHTML = `<div class="loading-message" style="color: red;">Error rendering topology: ${error.message}</div>`;
        updateDotSourceBadge(false);
    }
}

// Update DOT source badge
function updateDotSourceBadge(isRealDot) {
    const badgeContainer = document.getElementById('dotSourceBadge');
    if (!badgeContainer) {
        console.warn('DOT source badge container not found');
        return;
    }
    
    if (isRealDot) {
        badgeContainer.innerHTML = '<span class="badge badge-real">DOT: real</span>';
        badgeContainer.title = 'Using actual graph topology from search results';
    } else {
        badgeContainer.innerHTML = '<span class="badge badge-inferred">DOT: inferred</span>';
        badgeContainer.title = 'Inferred topology from candidate name (backward compatibility)';
    }
}

// Initialize application
async function init() {
    try {
        console.log('Loading results data...');
        resultsData = await loadResultsData();
        
        console.log('Loading candidates manifest...');
        candidatesManifest = await loadCandidatesManifest();
        
        console.log('Creating chart...');
        const candidates = createScatterChart(resultsData);
        
        console.log('Populating dropdown...');
        populateCandidateDropdown(candidates);
        
        // Setup cost control event listeners
        setupCostControls();
        
        console.log('Initialization complete!');
        
        // Auto-select first Pareto candidate
        const paretoCandidate = candidates.find(c => paretoSet.has(c.name));
        if (paretoCandidate) {
            selectCandidate(paretoCandidate);
        }
    } catch (error) {
        console.error('Initialization error:', error);
        alert('Failed to load data: ' + error.message);
    }
}

// Setup cost control event listeners
function setupCostControls() {
    // X-axis mode toggle
    const xAxisModeSelect = document.getElementById('xAxisMode');
    xAxisModeSelect.addEventListener('change', (e) => {
        xAxisMode = e.target.value;
        renderChart();
        // Update selected candidate display
        if (selectedCandidate) {
            updateDerivedCosts(selectedCandidate);
        }
    });
    
    // Token price input
    const tokenPriceInput = document.getElementById('tokenPrice');
    tokenPriceInput.addEventListener('input', (e) => {
        const newPrice = parseFloat(e.target.value);
        if (!isNaN(newPrice) && newPrice >= 0) {
            tokenPrice = newPrice;
            if (xAxisMode === 'cost') {
                renderChart();
            }
            // Update selected candidate display
            if (selectedCandidate) {
                updateDerivedCosts(selectedCandidate);
            }
        }
    });
}

// Start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
