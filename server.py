import os
import sys
import json
import time
import socket
import threading
import subprocess
import re
import shutil
import tempfile
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Ensure UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import scanner

PORT = 4949
CURRENT_DIR = Path(__file__).resolve().parent

# Target skill directories
GEMINI_SKILLS_DIR = Path.home() / ".gemini" / "config" / "skills"
CLAUDE_SKILLS_DIR = Path.home() / ".claude" / "skills"

def parse_git_url(raw_url: str):
    """Parses git clone URL, branch, and subtree path with support for diverse formats."""
    trimmed = raw_url.strip()
    branch = None
    subpath = None

    # Detect 'npx skills add owner/repo --skill xyz'
    npx_match = re.match(r'^npx\s+skills\s+add\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:\s+--skill\s+([A-Za-z0-9_.-]+))?', trimmed)
    if npx_match:
        repo_slug, skill_flag = npx_match.groups()
        clone_url = f"https://github.com/{repo_slug}.git"
        return clone_url, None, skill_flag

    # Detect GitHub blob URL: https://github.com/owner/repo/blob/branch/subpath/SKILL.md
    gh_blob = re.match(r"^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/?(.*)$", trimmed)
    if gh_blob:
        owner, repo, branch, subpath = gh_blob.groups()
        if subpath.endswith('/SKILL.md') or subpath.endswith('/skill.md'):
            subpath = subpath.rsplit('/', 1)[0]
        elif subpath.lower() == 'skill.md':
            subpath = ''
        clone_url = f"https://github.com/{owner}/{repo}.git"
        return clone_url, branch, subpath or None

    # Detect GitHub tree URL: https://github.com/owner/repo/tree/branch/subpath
    gh_match = re.match(r"^https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/?(.*)$", trimmed)
    if gh_match:
        owner, repo, branch, subpath = gh_match.groups()
        clone_url = f"https://github.com/{owner}/{repo}.git"
        return clone_url, branch, subpath or None

    # Standard GitHub URL
    if trimmed.startswith("http") and "github.com" in trimmed:
        clean = trimmed.split("?")[0].rstrip("/")
        if not clean.endswith(".git"):
            clean += ".git"
        return clean, None, None

    return trimmed, None, None

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
            index_file = CURRENT_DIR / "index.html"
            if index_file.exists():
                content = index_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

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

        elif parsed.path == "/api/sync-item":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                payload = json.loads(body)
                item_name = payload.get("name")
                item_type = payload.get("type", "MCP Server")
                target = payload.get("target", "claude")

                if not item_name:
                    raise ValueError("Item name is required")

                synced_details = []

                if item_type == "MCP Server":
                    # Sync to Claude Desktop config (~/Library/Application Support/Claude/claude_desktop_config.json)
                    claude_desktop_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
                    claude_desktop_cfg = {"mcpServers": {}}
                    if claude_desktop_path.exists():
                        try:
                            claude_desktop_cfg = json.loads(claude_desktop_path.read_text(encoding="utf-8"))
                            if "mcpServers" not in claude_desktop_cfg:
                                claude_desktop_cfg["mcpServers"] = {}
                        except Exception:
                            claude_desktop_cfg = {"mcpServers": {}}
                    
                    # Also check ~/.claude.json
                    claude_cli_path = Path.home() / ".claude.json"
                    claude_cli_cfg = {}
                    if claude_cli_path.exists():
                        try:
                            claude_cli_cfg = json.loads(claude_cli_path.read_text(encoding="utf-8"))
                        except Exception:
                            pass

                    # Extract existing config from ~/.claude.json if available
                    existing_cli_mcp = claude_cli_cfg.get("mcpServers", {}).get(item_name)
                    if existing_cli_mcp:
                        mcp_conf = existing_cli_mcp
                    else:
                        mcp_conf = {
                            "command": "npx",
                            "args": ["-y", f"@{item_name}/mcp"],
                            "env": {}
                        }

                    claude_desktop_cfg["mcpServers"][item_name] = mcp_conf
                    claude_desktop_path.parent.mkdir(parents=True, exist_ok=True)
                    claude_desktop_path.write_text(json.dumps(claude_desktop_cfg, indent=2, ensure_ascii=False), encoding="utf-8")
                    synced_details.append(f"Synced to Claude Desktop config ({item_name})")

                resp = json.dumps({"status": "ok", "message": f"Successfully synced {item_name}!", "details": synced_details}, ensure_ascii=False).encode("utf-8")
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
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
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

        elif parsed.path == "/api/create-skill":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                payload = json.loads(body)

                raw_name = payload.get("name", "").strip()
                name = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_name).strip("-").lower()
                desc = payload.get("description", "").strip() or f"Custom skill for {name}"
                body_content = payload.get("body", "").strip() or "## Instructions\n\nFollow best practices for this skill."
                triggers = payload.get("triggers", [])
                if isinstance(triggers, str):
                    triggers = [t.strip().lstrip("#") for t in triggers.split(",") if t.strip()]

                targets = payload.get("targets", ["antigravity", "claude"])

                if not name:
                    raise ValueError("نام مهارت الزامی است (حروف انگلیسی و خط تیره)")

                triggers_block = ""
                if triggers:
                    triggers_block = f"\n\n## Triggers\n" + ", ".join([f"`{t}`" for t in triggers])

                skill_md_content = f"""---
name: {name}
description: {desc}
---

# {name}

{body_content}{triggers_block}
"""

                saved_paths = []
                if "antigravity" in targets:
                    dest_dir = GEMINI_SKILLS_DIR / name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    (dest_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
                    saved_paths.append(str(dest_dir))

                if "claude" in targets:
                    dest_dir = CLAUDE_SKILLS_DIR / name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    (dest_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
                    saved_paths.append(str(dest_dir))

                # Refresh ecosystem cache
                get_cached_data(force=True)

                resp = json.dumps({
                    "status": "ok",
                    "message": f"مهارت '{name}' با موفقیت ساخته شد و در دیسک ذخیره گردید.",
                    "skill_id": name,
                    "paths": saved_paths
                }, ensure_ascii=False).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return
            except Exception as e:
                err = json.dumps({"status": "error", "message": str(e)}).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return

        elif parsed.path == "/api/import-git-skill":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                payload = json.loads(body)

                raw_url = payload.get("url", "").strip()
                if not raw_url:
                    raise ValueError("آدرس مخزن گیت‌هاب الزامی است.")

                custom_name = payload.get("custom_name", "").strip()
                targets = payload.get("targets", ["antigravity", "claude"])

                clone_url, branch, subpath = parse_git_url(raw_url)

                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_clone = Path(temp_dir) / "clone"
                    cmd = ["git", "clone", "--depth", "1"]
                    if branch:
                        cmd.extend(["-b", branch])
                    cmd.extend([clone_url, str(temp_clone)])

                    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
                    if proc.returncode != 0:
                        raise RuntimeError(f"خطا در کلون مخزن: {proc.stderr.strip()}")

                    source_dir = temp_clone
                    if subpath:
                        cand = temp_clone / subpath
                        if cand.exists() and cand.is_dir():
                            source_dir = cand
                        else:
                            for root, dirs, _ in os.walk(temp_clone):
                                for d in dirs:
                                    if d.lower() == subpath.lower():
                                        source_dir = Path(root) / d
                                        break

                    if custom_name:
                        skill_name = re.sub(r"[^a-zA-Z0-9_-]", "-", custom_name).strip("-").lower()
                    elif subpath:
                        skill_name = re.sub(r"[^a-zA-Z0-9_-]", "-", Path(subpath).name).strip("-").lower()
                    else:
                        repo_name = clone_url.split("/")[-1].replace(".git", "")
                        skill_name = re.sub(r"[^a-zA-Z0-9_-]", "-", repo_name).strip("-").lower()

                    skill_md = source_dir / "SKILL.md"
                    if not skill_md.exists():
                        for f in source_dir.iterdir():
                            if f.is_file() and f.name.lower() == "skill.md":
                                skill_md = f
                                break
                    if not skill_md.exists():
                        readme = source_dir / "README.md"
                        readme_content = readme.read_text(encoding="utf-8", errors="ignore") if readme.exists() else f"# {skill_name}\n\nImported from {raw_url}"
                        (source_dir / "SKILL.md").write_text(f"---\nname: {skill_name}\ndescription: Imported skill from {clone_url}\n---\n\n{readme_content}", encoding="utf-8")

                    saved_paths = []
                    if "antigravity" in targets:
                        target_dir = GEMINI_SKILLS_DIR / skill_name
                        if target_dir.exists():
                            shutil.rmtree(target_dir)
                        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", ".github"))
                        saved_paths.append(str(target_dir))

                    if "claude" in targets:
                        target_dir = CLAUDE_SKILLS_DIR / skill_name
                        if target_dir.exists():
                            shutil.rmtree(target_dir)
                        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", ".github"))
                        saved_paths.append(str(target_dir))

                # Force reload ecosystem
                get_cached_data(force=True)

                resp = json.dumps({
                    "status": "ok",
                    "message": f"مهارت '{skill_name}' با موفقیت از گیت‌هاب ایمپورت شد.",
                    "skill_id": skill_name,
                    "paths": saved_paths
                }, ensure_ascii=False).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return
            except Exception as e:
                err = json.dumps({"status": "error", "message": str(e)}).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
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
