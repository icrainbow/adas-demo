"""HTTP API server with endpoints and static file serving."""

import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from io import BytesIO
from email.parser import BytesParser
from email.policy import default as email_default

from .agent_service import list_agents, upsert_agents, delete_agents
from .case_service import list_cases, load_manifest, get_default_case_id, validate_case_id
from .config_loader import (
    load_eval_config, save_eval_config,
    load_run_config, save_run_config,
    EvalConfig, RunConfig
)
from .optimize_service import start_optimization
from .limits import validate_upload_size


def _parse_multipart_form_data(headers, body: bytes):
    """
    Python 3.13-compatible multipart/form-data parser (stdlib only).
    Returns:
      fields: dict[str, list[str]]
      files: list[dict] with keys: field, filename, content_type, content (bytes)
    """
    content_type = headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        raise ValueError("Expected multipart/form-data")

    if not body:
        return {}, []

    # email parser expects a full message with headers + blank line + body
    raw = (
        f"Content-Type: {content_type}\r\n"
        f"MIME-Version: 1.0\r\n"
        f"\r\n"
    ).encode("utf-8") + body

    msg = BytesParser(policy=email_default).parsebytes(raw)
    if not msg.is_multipart():
        return {}, []

    fields = {}
    files = []

    for part in msg.iter_parts():
        cd = part.get("Content-Disposition", "")
        if not cd:
            continue

        name = part.get_param("name", header="Content-Disposition")
        filename = part.get_param("filename", header="Content-Disposition")

        payload = part.get_payload(decode=True) or b""

        if filename:
            files.append({
                "field": name or "",
                "filename": filename,
                "content_type": part.get_content_type() or "application/octet-stream",
                "content": payload,
            })
        else:
            value = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            fields.setdefault(name or "", []).append(value)

    return fields, files


class APIHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler with API endpoints and static serving."""
    
    def do_GET(self):
        """Handle GET requests."""
        print(f"[GET] {self.path}")  # Debug logging
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Case API endpoints
        if path == "/api/cases":
            cases = list_cases()
            print(f"[GET /api/cases] Returning {len(cases)} cases")  # Debug
            self._send_json({"cases": cases})
        
        elif path == "/api/cases/default":
            self._send_json({"default_case_id": get_default_case_id()})
        
        elif path.startswith("/api/cases/") and path.endswith("/agents"):
            # GET /api/cases/{case_id}/agents
            parts = path.split("/")
            if len(parts) == 5:
                case_id = parts[3]
                if validate_case_id(case_id):
                    self._send_json(list_agents(case_id))
                else:
                    self._send_error(400, "Invalid case_id format")
            else:
                self._send_error(400, "Invalid path")
        
        elif path.startswith("/api/cases/") and not path.endswith("/agents"):
            # GET /api/cases/{case_id}
            parts = path.split("/")
            if len(parts) == 4:
                case_id = parts[3]
                if validate_case_id(case_id):
                    try:
                        manifest = load_manifest(case_id)
                        if manifest:
                            self._send_json(manifest)
                        else:
                            self._send_error(404, f"Case '{case_id}' not found")
                    except Exception as e:
                        self._send_error(400, str(e))
                else:
                    self._send_error(400, "Invalid case_id format")
            else:
                self._send_error(400, "Invalid path")
        
        # Agent API endpoints (backward compatible with query param)
        elif path == "/api/agents":
            query = parse_qs(parsed.query)
            case_id = query.get('case_id', [None])[0]
            self._send_json(list_agents(case_id))
        
        elif path == "/api/config/eval":
            config = load_eval_config()
            self._send_json(config.to_dict())
        
        elif path == "/api/config/run":
            config = load_run_config()
            self._send_json(config.to_dict())
        
        elif path == "/api/results/latest":
            # Dynamically find the most recent result JSON
            result_path = self._find_latest_result()
            if result_path:
                self._send_json({"path": result_path, "success": True})
            else:
                self._send_json({"success": False, "error": "No result files found"})
        
        # Static file serving
        elif path.startswith("/ui/") or path.startswith("/viz/") or path.startswith("/runs/") or path.startswith("/outputs/") or path.startswith("/artifacts/"):
            self._serve_static_file(path)
        
        else:
            self._send_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests."""
        path = self.path
        
        # Parse content
        content_length = int(self.headers.get('Content-Length', 0))
        content_type = self.headers.get('Content-Type', '')
        
        if 'multipart/form-data' in content_type:
            # Multipart upload (Python 3.13 compatible; no cgi; read body once)
            try:
                body = self.rfile.read(content_length)
                validate_upload_size(body)

                fields, files = _parse_multipart_form_data(self.headers, body)

                # Accept either:
                # - file upload(s) (use first file)
                # - or a form field "yaml_text"
                yaml_text = ""

                if files:
                    yaml_text = files[0]["content"].decode("utf-8", errors="replace")
                else:
                    # form field fallback
                    vals = fields.get("yaml_text", [])
                    if vals:
                        yaml_text = vals[0]

                data = {"yaml_text": yaml_text} if yaml_text else {}
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})
                return
        else:
            # JSON body
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode('utf-8')) if body else {}
            except:
                data = {}
        
        # API endpoints
        if path == "/api/agents/upsert":
            yaml_text = data.get("yaml_text", "")
            case_id = data.get("case_id")
            self._send_json(upsert_agents(yaml_text, case_id))
        
        elif path == "/api/agents/delete":
            agent_ids = data.get("ids", [])
            case_id = data.get("case_id")
            self._send_json(delete_agents(agent_ids, case_id))
        
        elif path == "/api/config/eval/save":
            try:
                config = EvalConfig.from_dict(data)
                self._send_json(save_eval_config(config))
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})
        
        elif path == "/api/config/run/save":
            try:
                config = RunConfig.from_dict(data)
                self._send_json(save_run_config(config))
            except Exception as e:
                self._send_json({"success": False, "error": str(e)})
        
        elif path == "/api/optimize/start":
            case_id = data.get("case_id") if data else None
            self._send_json(start_optimization(case_id=case_id))
        
        else:
            self._send_error(404, "Not Found")
    
    def _serve_static_file(self, path):
        """Serve static files with path validation."""
        # Map URL path to filesystem
        if path.startswith("/ui/"):
            base_dir = "demos/portfolio_langgraph_opt/ui"
            rel_path = path[4:]  # Remove /ui/
        elif path.startswith("/viz/"):
            base_dir = "demos/portfolio_langgraph_opt/viz"
            rel_path = path[5:]  # Remove /viz/
        elif path.startswith("/runs/"):
            base_dir = "demos/portfolio_langgraph_opt/runs"
            rel_path = path[6:]  # Remove /runs/
        elif path.startswith("/outputs/"):
            base_dir = "demos/portfolio_langgraph_opt/outputs"
            rel_path = path[9:]  # Remove /outputs/
        elif path.startswith("/artifacts/"):
            base_dir = "demos/portfolio_langgraph_opt/artifacts"
            rel_path = path[11:]  # Remove /artifacts/
        else:
            self._send_error(403, "Forbidden")
            return
        
        # Security: reject path traversal
        if ".." in rel_path or rel_path.startswith("/"):
            self._send_error(403, "Forbidden")
            return
        
        # Build full path and verify
        full_path = os.path.join(base_dir, rel_path)
        real_path = os.path.realpath(full_path)
        real_base = os.path.realpath(base_dir)
        
        if not real_path.startswith(real_base):
            self._send_error(403, "Forbidden")
            return
        
        # Serve file
        if os.path.isfile(real_path):
            try:
                with open(real_path, 'rb') as f:
                    content = f.read()
                
                # Guess content type
                if real_path.endswith('.html'):
                    content_type = 'text/html'
                elif real_path.endswith('.js'):
                    content_type = 'application/javascript'
                elif real_path.endswith('.css'):
                    content_type = 'text/css'
                elif real_path.endswith('.json'):
                    content_type = 'application/json'
                elif real_path.endswith('.dot'):
                    content_type = 'text/plain'
                else:
                    content_type = 'application/octet-stream'
                
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", len(content))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self._send_error(500, f"Error reading file: {e}")
        else:
            self._send_error(404, "File not found")
    
    def _send_json(self, data):
        """Send JSON response."""
        content = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)
    
    def _find_latest_result(self):
        """
        Find the most recent result JSON file.
        Search in multiple locations and return the relative path from server root.
        """
        import glob
        from pathlib import Path
        
        # Search paths (relative to server root)
        search_patterns = [
            "demos/portfolio_langgraph_opt/viz/*.json",
            "demos/portfolio_langgraph_opt/outputs/*.json",
            "demos/portfolio_langgraph_opt/runs/*/results.json",
            "demos/portfolio_langgraph_opt/runs/*/results_pareto.json"
        ]
        
        latest_file = None
        latest_mtime = 0
        
        for pattern in search_patterns:
            for filepath in glob.glob(pattern):
                # Skip pareto and markdown files for primary result
                if '_pareto.json' in filepath or '_pareto.md' in filepath:
                    continue
                
                try:
                    mtime = os.path.getmtime(filepath)
                    if mtime > latest_mtime:
                        latest_mtime = mtime
                        latest_file = filepath
                except:
                    continue
        
        if latest_file:
            # Convert to relative path from viz perspective
            # e.g., "demos/portfolio_langgraph_opt/viz/legal_demo.json" -> "legal_demo.json"
            # or "demos/portfolio_langgraph_opt/outputs/foo.json" -> "../outputs/foo.json"
            path_obj = Path(latest_file)
            
            # If in viz directory, return just filename
            if "viz" in latest_file:
                return path_obj.name
            # If in outputs directory, return relative path from viz
            elif "outputs" in latest_file:
                return f"../outputs/{path_obj.name}"
            # If in runs directory, return relative path from viz
            elif "runs" in latest_file:
                # Extract run_xxx/results.json pattern
                parts = path_obj.parts
                if "runs" in parts:
                    idx = parts.index("runs")
                    relative_parts = parts[idx:]  # e.g., ('runs', 'run_20260111_xxx', 'results.json')
                    return f"../{'/'.join(relative_parts)}"
            
            # Fallback: return full relative path from demos/portfolio_langgraph_opt
            return latest_file.replace("demos/portfolio_langgraph_opt/", "../")
        
        return None
    
    def _send_error(self, code, message):
        """Send error response."""
        content = json.dumps({"error": message}).encode('utf-8')
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)
    
    def log_message(self, format, *args):
        """Override to reduce logging noise."""
        pass


def start_server(port=8080):
    """Start the API server."""
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
    
    server = HTTPServer(("localhost", port), APIHandler)
    print("=" * 70)
    print("Portfolio LangGraph Config API Server")
    print("=" * 70)
    print(f"Server running on: http://localhost:{port}")
    print(f"Config UI:         http://localhost:{port}/ui/config.html")
    print(f"Viz (existing):    http://localhost:{port}/viz/index.html")
    print("=" * 70)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    start_server(port)
