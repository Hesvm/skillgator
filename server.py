import os
import sys
import json
import time
import socket
import threading
import subprocess
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Ensure UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import scanner

PORT = 4949
CURRENT_DIR = Path(__file__).resolve().parent

# Global cache & change tracking
CACHE_DATA = None
LAST_FINGERPRINT = None
CACHE_LOCK = threading.Lock()

def get_cached_data(force=False):
    global CACHE_DATA, LAST_FINGERPRINT
    with CACHE_LOCK:
        current_fp = scanner.calculate_fingerprint()
        if force or CACHE_DATA is None or current_fp != LAST_FINGERPRINT:
            LAST_FINGERPRINT = current_fp
            CACHE_DATA = scanner.get_complete_ecosystem()
        return CACHE_DATA

class EcosystemMonitorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(CURRENT_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/data":
            data = get_cached_data()
            content = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        elif path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            local_fp = None
            try:
                # Send initial data immediately
                data = get_cached_data()
                local_fp = LAST_FINGERPRINT
                payload = json.dumps(data, ensure_ascii=False)
                self.wfile.write(f"event: init\ndata: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()

                while True:
                    time.sleep(1.5)
                    new_fp = scanner.calculate_fingerprint()
                    if new_fp != local_fp:
                        local_fp = new_fp
                        data = get_cached_data(force=True)
                        payload = json.dumps(data, ensure_ascii=False)
                        self.wfile.write(f"event: update\ndata: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    else:
                        # Heartbeat ping
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        elif path == "/api/export":
            data = get_cached_data()
            content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="agent-ecosystem.json"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        elif path == "/api/skill-tree":
            try:
                qs = parse_qs(parsed.query)
                folder_path = qs.get("path", [""])[0]
                def get_tree(folder, max_depth=3, current_depth=0):
                    fpath = Path(folder)
                    if not fpath.exists() or not fpath.is_dir() or current_depth > max_depth:
                        return []
                    res = []
                    for p in sorted(fpath.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                        if p.name.startswith(".") or p.name in ["__pycache__", "node_modules", ".venv", ".git"]:
                            continue
                        if p.is_dir():
                            res.append({
                                "name": p.name,
                                "type": "dir",
                                "path": str(p),
                                "children": get_tree(p, max_depth, current_depth + 1)
                            })
                        else:
                            res.append({
                                "name": p.name,
                                "type": "file",
                                "path": str(p),
                                "size_kb": round(p.stat().st_size / 1024, 1),
                                "ext": p.suffix.lower()
                            })
                    return res

                if folder_path and os.path.exists(folder_path):
                    tree_data = get_tree(folder_path)
                    resp = json.dumps({"status": "ok", "tree": tree_data}, ensure_ascii=False).encode("utf-8")
                else:
                    resp = json.dumps({"status": "error", "message": "Directory not found"}).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return
            except Exception as e:
                err = json.dumps({"status": "error", "message": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return

        elif path == "/api/read-file":
            try:
                qs = parse_qs(parsed.query)
                file_path = qs.get("path", [""])[0]
                if file_path and os.path.exists(file_path):
                    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
                    resp = json.dumps({"status": "ok", "content": content}).encode("utf-8")
                else:
                    resp = json.dumps({"status": "error", "message": "File not found"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return
            except Exception as e:
                err = json.dumps({"status": "error", "message": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return

        elif path == "/" or path == "/index.html":
            self.path = "/index.html"
            return super().do_GET()

        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/rescan":
            data = get_cached_data(force=True)
            content = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        elif parsed.path == "/api/open-editor":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                payload = json.loads(body)
                file_path = payload.get("path")
                if file_path and os.path.exists(file_path):
                    # Try opening in Antigravity or system default editor
                    if sys.platform == "darwin":
                        subprocess.run(["open", "-a", "Antigravity", file_path], check=False)
                    else:
                        os.system(f'code "{file_path}"')
                    resp = json.dumps({"status": "ok", "opened": file_path}).encode("utf-8")
                else:
                    resp = json.dumps({"status": "error", "message": "File not found"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return
            except Exception as e:
                err = json.dumps({"status": "error", "message": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return
        
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        # Silence routine static & ping requests from log spam
        first_arg = str(args[0]) if args else ""
        if "GET /api/stream" in first_arg or "GET /api/data" in first_arg or "favicon.ico" in first_arg:
            return
        super().log_message(format, *args)

def run_server():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), EcosystemMonitorHandler)
    server.daemon_threads = True
    print(f"=====================================================")
    print(f"🚀 AI Ecosystem Live Monitor is running!")
    print(f"🌐 Dashboard URL: http://localhost:{PORT}")
    print(f"📡 Real-time SSE Stream: http://localhost:{PORT}/api/stream")
    print(f"🔄 Auto-monitoring: Antigravity, Claude, CLIs & MCPs")
    print(f"=====================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()

if __name__ == "__main__":
    run_server()
