# Portfolio LangGraph Interactive Visualization

Interactive web-based visualization for exploring Pareto frontier analysis and LangGraph topology diagrams.

## Quick Start

### 1. Start HTTP Server

From the **project root** directory:

```bash
cd /Users/shenyanran/Dev/AdasDemo/ADAS
python -m http.server 8000
```

Or using Python 3 explicitly:
```bash
python3 -m http.server 8000
```

### 2. Open in Browser

Navigate to:
```
http://localhost:8000/demos/portfolio_langgraph_opt/viz/
```

Or if serving from the viz directory:
```bash
cd demos/portfolio_langgraph_opt/viz
python3 -m http.server 8000
```
Then open: `http://localhost:8000/`

## Prerequisites

### Required Files

The visualization requires these files to be accessible via relative paths:

1. **Results JSON** (must exist):
   ```
   demos/portfolio_langgraph_opt/outputs/results_v11_pareto_smoke.json
   ```

2. **Candidates Manifest** (recommended):
   ```
   demos/portfolio_langgraph_opt/artifacts/candidates_manifest.json
   ```

### Generate Required Files

If files are missing, generate them:

```bash
# Run search to generate results JSON
python demos/portfolio_langgraph_opt/portfolio_search.py \
  --budget 16 \
  --out demos/portfolio_langgraph_opt/outputs/results_v11_pareto_smoke.json

# Generate artifacts including manifest
python demos/portfolio_langgraph_opt/scripts/make_pareto_viz.py
```

## Features

### Interactive Scatter Plot
- **Chart.js** scatter plot showing coverage vs. token cost
- Click any point to view detailed topology
- Hover for metrics tooltip
- Color-coded points:
  - Gray: All candidates
  - Blue: Pareto frontier
  - Green star: Baseline
  - Red star: Best by score
  - Yellow: Currently selected

### Dynamic Topology Diagrams
- **Graphviz/Viz.js** rendering of LangGraph configurations
- Beautified DOT graphs with:
  - Color-coded nodes by function
  - Styled edges (solid, dashed, dotted)
  - Configuration metadata note
  - Candidate name as title
- Real-time re-rendering on selection

### Metrics Panel
Displays for selected candidate:
- Average coverage
- Total tokens
- Average steps
- HITL rate
- Score
- Violation rate

## File Structure

```
viz/
├── index.html          # Main HTML page
├── style.css           # Responsive styling
├── app.js              # Application logic
└── README.md           # This file

Required data (relative paths):
../outputs/results_v11_pareto_smoke.json     # Required
../artifacts/candidates_manifest.json        # Optional (fallback to name parsing)
```

## Dependencies

All dependencies loaded from CDN (no npm install required):

- **Chart.js v4.4.0**: Interactive scatter plot
- **Viz.js v3.4.0**: Graphviz DOT to SVG rendering

## Troubleshooting

### "Failed to load data"

**Cause**: Results JSON not found or incorrect path.

**Solution**:
1. Ensure you're running the server from the correct directory
2. Check that `results_v11_pareto_smoke.json` exists at:
   ```
   demos/portfolio_langgraph_opt/outputs/results_v11_pareto_smoke.json
   ```
3. Verify file permissions (should be readable)
4. Check browser console for exact error path

### "Could not load candidates manifest"

**Cause**: Manifest JSON not found (non-fatal warning).

**Impact**: Falls back to parsing candidate names (still works).

**Solution** (optional):
```bash
python demos/portfolio_langgraph_opt/scripts/make_pareto_viz.py
```

### Charts not displaying

**Cause**: Chart.js not loaded from CDN.

**Solution**:
1. Check internet connection
2. Open browser DevTools → Network tab
3. Verify CDN resources load successfully
4. Try alternative CDN or download Chart.js locally

### Topology rendering error

**Cause**: Viz.js error or invalid DOT syntax.

**Solution**:
1. Check browser console for detailed error
2. Try selecting a different candidate
3. Verify candidate name format matches expected pattern
4. Check that manifest JSON has valid configuration

### Port already in use

**Error**: `OSError: [Errno 48] Address already in use`

**Solution**: Use a different port
```bash
python3 -m http.server 8001
# Then open: http://localhost:8001/demos/portfolio_langgraph_opt/viz/
```

Or kill the existing process:
```bash
lsof -ti:8000 | xargs kill -9
```

## Browser Compatibility

**Tested on:**
- Chrome 90+ ✓
- Firefox 88+ ✓
- Safari 14+ ✓
- Edge 90+ ✓

**Requirements:**
- ES6+ support (async/await, fetch API)
- Canvas API
- SVG support
- WebAssembly (for Viz.js)

## Configuration

### Using Different Results Files

Edit `app.js` lines 11-14:

```javascript
const paths = [
    '../outputs/your_custom_results.json',
    './outputs/your_custom_results.json',
    'outputs/your_custom_results.json'
];
```

### Customizing Appearance

**Colors**: Edit `style.css`
- Chart colors: `.legend-dot` styles
- Layout: `.main-content` grid

**Topology**: Edit `app.js` `generateDOT()` function
- Node colors: `fillcolor` attributes
- Edge styles: `style`, `color` attributes
- Layout: `rankdir=LR` (left-right) or `TB` (top-bottom)

## Data Flow

```
1. Load results_v11_pareto_smoke.json
   ↓
2. Load candidates_manifest.json (optional)
   ↓
3. Parse candidates and compute Pareto frontier
   ↓
4. Render Chart.js scatter plot
   ↓
5. User clicks point or selects from dropdown
   ↓
6. Get config from manifest (or parse name)
   ↓
7. Generate DOT graph
   ↓
8. Render with Viz.js → SVG
   ↓
9. Display in topology panel
```

## Advanced Usage

### Serving Over Network

Allow access from other devices on your network:

```bash
python3 -m http.server 8000 --bind 0.0.0.0
```

Then access from other devices:
```
http://<your-ip-address>:8000/demos/portfolio_langgraph_opt/viz/
```

### CORS Issues

If loading from `file://` protocol:
- Won't work due to CORS restrictions
- Must use HTTP server (any of the methods above)

### Performance

**Large Result Sets**: If you have 100+ candidates:
- Chart may become crowded
- Consider filtering or aggregating
- Topology rendering remains fast (per-candidate)

## Development

### Local Testing

```bash
# From viz directory
cd demos/portfolio_langgraph_opt/viz

# Start server
python3 -m http.server 8000

# Open in browser with auto-reload extension
# Or manually refresh after changes
```

### Debugging

1. Open browser DevTools (F12)
2. Check Console tab for errors
3. Check Network tab for failed requests
4. Use Sources tab to set breakpoints in app.js

## Related Files

- **Search Script**: `demos/portfolio_langgraph_opt/portfolio_search.py`
- **Visualization Script**: `demos/portfolio_langgraph_opt/scripts/make_pareto_viz.py`
- **Evaluation Module**: `demos/portfolio_langgraph_opt/src/evaluate.py`
- **Pareto Module**: `demos/portfolio_langgraph_opt/src/pareto.py`

## License

Part of the ADAS project.

## Support

For issues or questions:
1. Check this README's Troubleshooting section
2. Review browser console errors
3. Verify all required files exist with correct paths
4. Ensure HTTP server is running correctly

---

**Enjoy exploring the Pareto frontier!** 🚀
