"""HTTP API server with endpoints and static file serving."""

import os
import json
import cgi
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from io import BytesIO

from .agent_service import list_agents, upsert_agents, soft_delete_agents
from .config_loader import (
    load_eval_config, save_eval_config,
    load_run_config, save_run_config,
    EvalConfig, RunConfig
)
from .optimize_service import start_optimization
from .limits import validate_upload_size


class APIHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler with API endpoints and static serving."""
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # API endpoints
        if path == "/api/agents":
            self._send_json(list_agents())
        
        elif path == "/api/config/eval":
            config = load_eval_config()
            self._send_json(config.to_dict())
        
        elif path == "/api/config/run":
            config = load_run_config()
            self._send_json(config.to_dict())
        
        # Static file serving
        elif path.startswith("/ui/") or path.startswith("/viz/") or path.startswith("/runs/"):
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
            # Multipart upload
            try:
                validate_upload_size(self.rfile.read(content_length))
                self.rfile.seek(0)
                
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST'}
                )
                
                if 'file' in form:
                    file_item = form['file']
                    yaml_text = file_item.file.read().decode('utf-8')
                    data = {"yaml_text": yaml_text}
                else:
                    data = {}
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
            self._send_json(upsert_agents(yaml_text))
        
        elif path == "/api/agents/delete":
            agent_ids = data.get("ids", [])
            self._send_json(soft_delete_agents(agent_ids))
        
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
            self._send_json(start_optimization())
        
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
    start_server()
