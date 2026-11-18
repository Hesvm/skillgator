import os
import sys
import json
import time
import glob
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime

# Ensure standard output can handle UTF-8 Persian text safely
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

USER_HOME = Path.home()
GEMINI_DIR = USER_HOME / ".gemini"
CLAUDE_DIR = USER_HOME / ".claude"

# Cross-platform paths for Claude Desktop & NPM
if sys.platform == "darwin":
    CLAUDE_APPDATA = USER_HOME / "Library" / "Application Support" / "Claude"
    NPM_GLOBAL_DIR = USER_HOME / ".gemini" / "antigravity" / "nodejs" / "lib"
else:
    CLAUDE_APPDATA = USER_HOME / "AppData" / "Roaming" / "Claude"
    NPM_GLOBAL_DIR = USER_HOME / "AppData" / "Roaming" / "npm"

def get_file_time(path):
    try:
        mtime = os.path.getmtime(path)
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Unknown"

def extract_triggers(text):
    """Extracts trigger phrases, activation keywords, and user intents from description or markdown."""
    if not text:
        return []
    triggers = []
    import re
    patterns = [
        r'(?:triggers?(?:\s+on)?|use\s+when(?:ever)?|when\s+the\s+user\s+says|activated\s+when)\s*[:\-]?\s*([^\n\.]+)',
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            segment = m.group(1)
            quoted = re.findall(r'[\'"`]([^\'"`]+)[\'"`]', segment)
            if quoted:
                triggers.extend(quoted)
            else:
                parts = [p.strip() for p in re.split(r'[,،;؛]+', segment) if p.strip()]
                triggers.extend(parts[:6])
    clean = []
    for t in triggers:
        t = t.strip(' \t\n\r\'"`-\\')
        if 1 < len(t) < 40 and not any(t.lower().startswith(x) for x in ['the ', 'when ', 'only ', 'this ']):
            clean.append(t)
    return list(dict.fromkeys(clean))[:10]

def parse_markdown_frontmatter(content):
    meta = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_front = parts[1]
            body = parts[2].strip()
            lines = raw_front.splitlines()
            current_key = None
            val_lines = []
            for line in lines:
                if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
                    if current_key:
                        meta[current_key] = "\n".join(val_lines).strip().strip('"\'')
                    k, v = line.split(":", 1)
                    current_key = k.strip()
                    val_lines = [v.strip()] if v.strip() else []
                elif current_key:
                    val_lines.append(line.strip())
            if current_key:
                meta[current_key] = "\n".join(val_lines).strip().strip('"\'')

    # If description is just >- or | or empty, look for text in body
    desc = meta.get("description", "").strip()
    if not desc or desc in [">-", "|", ">"]:
        # Grab first non-empty heading or paragraph from body
        for bl in body.splitlines():
            bl = bl.strip()
            if bl and not bl.startswith("#") and not bl.startswith("---"):
                desc = bl
                break
        meta["description"] = desc if desc else "No detailed description available"

    return meta, body

def calculate_folder_stats(folder_path):
    """Calculates size, file count, and line count for depth/richness scoring, excluding bloated caches and dependencies."""
    total_bytes = 0
    file_count = 0
    line_count = 0
    ignored_names = {".venv", "venv", "node_modules", ".git", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build"}
    try:
        for f in folder_path.rglob("*"):
            if f.is_file():
                # Filter out heavy dependency or cache folders
                rel_parts = f.relative_to(folder_path).parts
                if any(p in ignored_names or (p.startswith(".") and p != ".env") for p in rel_parts[:-1]):
                    continue
                file_count += 1
                try:
                    size = f.stat().st_size
                    total_bytes += size
                    # Count lines for text files
                    if f.suffix in [".md", ".py", ".json", ".js", ".ts", ".txt", ".html", ".sh"]:
                        with open(f, "r", encoding="utf-8", errors="ignore") as tf:
                            line_count += sum(1 for _ in tf)
                except Exception:
                    pass
    except Exception:
        pass
    
    score = total_bytes + (file_count * 1500) + (line_count * 8)
    return {
        "size_bytes": total_bytes,
        "size_kb": round(total_bytes / 1024, 1),
        "file_count": file_count,
        "line_count": line_count,
        "richness_score": score
    }

THIINGS_ASSETS = {} # Deprecated in favor of ICONLY_PRO_3D

# Curated high-precision 3D models from Iconly Pro Hes Edition (Retina WebP 1024x1024)
ICONLY_CURATED = {
    # Creator OS Pipeline
    "creator-intelligence": {"3d": "/assets/3d/AI/Brain_Angle_1.webp", "emoji": "🧠", "icon": "cpu-charge", "color": "text-purple-600 bg-purple-50 border-purple-200"},
    "trend-radar": {"3d": "/assets/3d/Chart & Analytics/Trend_Line.webp", "emoji": "📡", "icon": "radar-2", "color": "text-blue-600 bg-blue-50 border-blue-200"},
    "audience-positioning": {"3d": "/assets/3d/Chart & Analytics/Target_Chart.webp", "emoji": "🎯", "icon": "target", "color": "text-rose-600 bg-rose-50 border-rose-200"},
    "topic-discovery": {"3d": "/assets/3d/Technology/Desk_Lamp_Alt_10731.webp", "emoji": "💡", "icon": "lamp-on", "color": "text-amber-600 bg-amber-50 border-amber-200"},
    "idea-development": {"3d": "/assets/3d/Design/Magic.webp", "emoji": "🌱", "icon": "magic-star", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"},
    "hook-engineering": {"3d": "/assets/3d/Essential/Flash_1_10240.webp", "emoji": "🪝", "icon": "flash-circle", "color": "text-red-600 bg-red-50 border-red-200"},
    "scriptwriting": {"3d": "/assets/3d/Technology/Wacom_Pen_Alt_10788.webp", "emoji": "✍️", "icon": "edit-2", "color": "text-indigo-600 bg-indigo-50 border-indigo-200"},
    "visual-storyboarding": {"3d": "/assets/3d/Video & Movie/Movie_and_Cinema_Basic.webp", "emoji": "🎬", "icon": "video-play", "color": "text-teal-600 bg-teal-50 border-teal-200"},
    "retention-editing": {"3d": "/assets/3d/Design/Scissor.webp", "emoji": "✂️", "icon": "scissor", "color": "text-orange-600 bg-orange-50 border-orange-200"},
    "platform-packaging": {"3d": "/assets/3d/Files/Folder_1_10238.webp", "emoji": "📦", "icon": "box-1", "color": "text-sky-600 bg-sky-50 border-sky-200"},
    "publishing-operations": {"3d": "/assets/3d/Essential/Rocket_1_10210.webp", "emoji": "🚀", "icon": "send-2", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"},
    "performance-learning": {"3d": "/assets/3d/Chart & Analytics/Analytics_Dashboard.webp", "emoji": "📈", "icon": "chart-2", "color": "text-blue-600 bg-blue-50 border-blue-200"},
    "youtube-thumbnail": {"3d": "/assets/3d/Design/Color_Picker.webp", "emoji": "🖼️", "icon": "gallery-edit", "color": "text-red-600 bg-red-50 border-red-200"},
    "carousel-craft": {"3d": "/assets/3d/Technology/iPhone_14_Pro_Alt_10757.webp", "emoji": "📑", "icon": "slider-vertical", "color": "text-fuchsia-600 bg-fuchsia-50 border-fuchsia-200"},
    "client-acquisition": {"3d": "/assets/3d/Cryptocurrency/Trading_Dashboard_Monitor.webp", "emoji": "💼", "icon": "dollar-circle", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"},
    "pushe-film": {"3d": "/assets/3d/Video & Movie/Video_camera_1_10083.webp", "emoji": "🎥", "icon": "video-play", "color": "text-purple-600 bg-purple-50 border-purple-200"},
    "sound-design": {"3d": "/assets/3d/Essential/Headset_1_10038.webp", "emoji": "🎵", "icon": "music-note", "color": "text-amber-600 bg-amber-50 border-amber-200"},
    "vidiq": {"3d": "/assets/3d/Chart & Analytics/Report_Document.webp", "emoji": "📊", "icon": "chart-square", "color": "text-red-600 bg-red-50 border-red-200"},

    # Instagram Suite
    "ig-reel": {"3d": "/assets/3d/Technology/iPhone_14_Pro_Alt_10757.webp", "emoji": "📱", "icon": "video-square", "color": "text-pink-600 bg-pink-50 border-pink-200"},
    "ig-story": {"3d": "/assets/3d/Technology/Apple_Watch_Alt_10798.webp", "emoji": "⏱️", "icon": "clock", "color": "text-rose-600 bg-rose-50 border-rose-200"},
    "ig-viral": {"3d": "/assets/3d/Essential/Flash_1_10240.webp", "emoji": "🔥", "icon": "trend-up", "color": "text-orange-600 bg-orange-50 border-orange-200"},
    "ig-profile": {"3d": "/assets/3d/Heart & Love/Arrow_in_Heart_Alt_10932.webp", "emoji": "👤", "icon": "profile-circle", "color": "text-indigo-600 bg-indigo-50 border-indigo-200"},
    "ig-caption": {"3d": "/assets/3d/AI/Chatbot_Interaction_Angle_2.webp", "emoji": "💬", "icon": "message-text-1", "color": "text-cyan-600 bg-cyan-50 border-cyan-200"},
    "ig-human": {"3d": "/assets/3d/Cryptocurrency/Crypto_Security_Shield.webp", "emoji": "🛡️", "icon": "shield-tick", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"},
    "ig-plan": {"3d": "/assets/3d/Documentation/Achievement_Document_Alt.webp", "emoji": "🗓️", "icon": "calendar-tick", "color": "text-purple-600 bg-purple-50 border-purple-200"},
    "ig-audit": {"3d": "/assets/3d/Chart & Analytics/Performance_Gauge.webp", "emoji": "🔍", "icon": "scan-barcode", "color": "text-amber-600 bg-amber-50 border-amber-200"},
    "ig-repurpose": {"3d": "/assets/3d/Design/Magic_Alt.webp", "emoji": "🔄", "icon": "refresh-circle", "color": "text-indigo-600 bg-indigo-50 border-indigo-200"},
    "ig-creator-expert": {"3d": "/assets/3d/Reward/Ranking_Alt.webp", "emoji": "👑", "icon": "crown-1", "color": "text-amber-600 bg-amber-50 border-amber-200"},

    # UI / Design / Frontend
    "figma": {"3d": "/assets/3d/Design/Design.webp", "emoji": "🎨", "icon": "bezier", "color": "text-purple-600 bg-purple-50 border-purple-200"},
    "make-interfaces-feel-better": {"3d": "/assets/3d/Design/Color_Picker.webp", "emoji": "✨", "icon": "magicpen", "color": "text-fuchsia-600 bg-fuchsia-50 border-fuchsia-200"},
    "vibe-component": {"3d": "/assets/3d/Design/Design_Alt.webp", "emoji": "💎", "icon": "magicpen", "color": "text-violet-600 bg-violet-50 border-violet-200"},
    "vibe-production-hardening": {"3d": "/assets/3d/Cryptocurrency/Crypto_Security_Shield.webp", "emoji": "🔒", "icon": "security-safe", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"},

    # SEO & Search Engine
    "seo": {"3d": "/assets/3d/Chart & Analytics/Search_Analytics.webp", "emoji": "🌐", "icon": "global-search", "color": "text-blue-600 bg-blue-50 border-blue-200"},
    "search-console": {"3d": "/assets/3d/Chart & Analytics/Search_Analytics.webp", "emoji": "🔍", "icon": "scan-barcode", "color": "text-blue-600 bg-blue-50 border-blue-200"},

    # Persian & Localization
    "persian": {"3d": "/assets/3d/Documentation/Achievement_Document_Alt.webp", "emoji": "🇮🇷", "icon": "translate", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"},

    # MCP Servers & Tools
    "hooshang": {"3d": "/assets/3d/AI/Robot_Full_Body_Angle_1.webp", "emoji": "🤖", "icon": "robot", "color": "text-indigo-600 bg-indigo-50 border-indigo-200"},
    "mem0": {"3d": "/assets/3d/AI/Brain_Angle_2.webp", "emoji": "🧠", "icon": "hierarchy-3", "color": "text-purple-600 bg-purple-50 border-purple-200"},
    "notion": {"3d": "/assets/3d/Documentation/Achievement_Document_Alt.webp", "emoji": "📝", "icon": "document-text", "color": "text-slate-800 bg-slate-100 border-slate-200"},
    "posthog": {"3d": "/assets/3d/Chart & Analytics/Data_Bars.webp", "emoji": "🦔", "icon": "data-2", "color": "text-amber-600 bg-amber-50 border-amber-200"},
    "easytrader": {"3d": "/assets/3d/Cryptocurrency/Trading_Dashboard_Monitor.webp", "emoji": "📈", "icon": "trend-up", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"},
    "adplat-admin": {"3d": "/assets/3d/Chart & Analytics/Conversion_Funnel.webp", "emoji": "📣", "icon": "bullhorn", "color": "text-blue-600 bg-blue-50 border-blue-200"},
    "dastyar-serp": {"3d": "/assets/3d/Chart & Analytics/Search_Analytics.webp", "emoji": "🔎", "icon": "search-normal", "color": "text-purple-600 bg-purple-50 border-purple-200"},
    "soundcloud": {"3d": "/assets/3d/Essential/Headset_1_10038.webp", "emoji": "🎧", "icon": "music-note", "color": "text-orange-600 bg-orange-50 border-orange-200"},

    # CLIs & Runtime
    "claude": {"3d": "/assets/3d/AI/Robot_Full_Body_Angle_2.webp", "emoji": "🤖", "icon": "command", "color": "text-amber-600 bg-amber-50 border-amber-200"},
    "agy": {"3d": "/assets/3d/Essential/Rocket_1_10210.webp", "emoji": "🚀", "icon": "flash-1", "color": "text-blue-600 bg-blue-50 border-blue-200"},
    "antigravity": {"3d": "/assets/3d/Essential/Rocket_1_10210.webp", "emoji": "🚀", "icon": "flash-1", "color": "text-blue-600 bg-blue-50 border-blue-200"},
    "uv": {"3d": "/assets/3d/Essential/Flash_1_10240.webp", "emoji": "⚡", "icon": "electricity", "color": "text-violet-600 bg-violet-50 border-violet-200"},
    "python": {"3d": "/assets/3d/AI/Code_Development_Angle_1.webp", "emoji": "🐍", "icon": "code-1", "color": "text-sky-600 bg-sky-50 border-sky-200"},
    "git": {"3d": "/assets/3d/Essential/Settings_Gear_triple_Plastic.webp", "emoji": "🌿", "icon": "git-branch", "color": "text-orange-600 bg-orange-50 border-orange-200"},
    "code": {"3d": "/assets/3d/AI/Code_Development_Angle_1.webp", "emoji": "💻", "icon": "code-1", "color": "text-sky-600 bg-sky-50 border-sky-200"},
}

# Curated pool for rich deterministic hash fallback
FALLBACK_3D_POOLS = {
    "AI": [
        "/assets/3d/AI/Robot_Full_Body_Angle_1.webp",
        "/assets/3d/AI/Brain_Angle_1.webp",
        "/assets/3d/AI/Brain_Angle_2.webp",
        "/assets/3d/AI/Code_Development_Angle_1.webp",
        "/assets/3d/AI/Chatbot_Interaction_Angle_2.webp",
        "/assets/3d/AI/AI_Web_Angle_2.webp",
        "/assets/3d/AI/CPU_with_Nodes_Angle_1.webp",
        "/assets/3d/AI/AI_Cloud.webp",
    ],
    "Technology": [
        "/assets/3d/Technology/MacBook_Alt_10812.webp",
        "/assets/3d/Technology/iPhone_14_Pro_Alt_10757.webp",
        "/assets/3d/Technology/Apple_Watch_Alt_10798.webp",
        "/assets/3d/Technology/Desk_Lamp_Alt_10731.webp",
        "/assets/3d/Technology/Airpod_Alt_10794.webp",
        "/assets/3d/Technology/Wacom_Pen_Alt_10788.webp",
    ],
    "Chart": [
        "/assets/3d/Chart & Analytics/Analytics_Dashboard.webp",
        "/assets/3d/Chart & Analytics/Bar_Chart.webp",
        "/assets/3d/Chart & Analytics/Trend_Line.webp",
        "/assets/3d/Chart & Analytics/Data_Bars.webp",
        "/assets/3d/Chart & Analytics/Target_Chart.webp",
        "/assets/3d/Chart & Analytics/Search_Analytics.webp",
        "/assets/3d/Chart & Analytics/Conversion_Funnel.webp",
    ],
    "Design": [
        "/assets/3d/Design/Design.webp",
        "/assets/3d/Design/Design_Alt.webp",
        "/assets/3d/Design/Color_Picker.webp",
        "/assets/3d/Design/Magic.webp",
        "/assets/3d/Design/Scissor.webp",
    ],
    "Media": [
        "/assets/3d/Video & Movie/Video_camera_1_10083.webp",
        "/assets/3d/Video & Movie/Movie_and_Cinema_Basic.webp",
        "/assets/3d/Video & Movie/Video_Record.webp",
        "/assets/3d/Photo/360_Camera.webp",
        "/assets/3d/Essential/Headset_1_10038.webp",
    ],
    "Security": [
        "/assets/3d/Cryptocurrency/Crypto_Security_Shield.webp",
        "/assets/3d/Cryptocurrency/Blockchain_Cube_Network.webp",
        "/assets/3d/Cryptocurrency/Trading_Dashboard_Monitor.webp",
        "/assets/3d/Essential/Settings_Gear_triple_Plastic.webp",
        "/assets/3d/Essential/Rocket_1_10210.webp",
    ],
    "Essential": [
        "/assets/3d/Essential/Rocket_1_10210.webp",
        "/assets/3d/Essential/Flash_1_10240.webp",
        "/assets/3d/Essential/Settings_Gear_triple_Plastic.webp",
        "/assets/3d/Documentation/Achievement_Document_Alt.webp",
        "/assets/3d/Files/Folder_1_10238.webp",
        "/assets/3d/Essential/Discover_Globe_10619.webp",
    ]
}

def assign_icon_and_emoji(name, item_type="Skill", platform=""):
    """Assigns an ultra-rich 3D Iconly Pro WebP model, emoji, and Iconsax icon to each item."""
    n = name.lower()
    
    # 1. Direct curated match
    for key, val in ICONLY_CURATED.items():
        if key in n:
            return {
                "emoji": val["emoji"],
                "icon": val["icon"],
                "thiings": val["3d"],
                "color": val["color"]
            }

    # 2. Semantic category matching
    pool = "Essential"
    emoji = "🧩"
    icon = "category"
    color = "text-slate-600 bg-slate-100 border-slate-200"

    if any(k in n for k in ["video", "film", "movie", "camera", "clip", "editor", "reel", "short", "youtube"]):
        pool = "Media"
        emoji = "🎬"
        icon = "video-play"
        color = "text-violet-600 bg-violet-50 border-violet-200"
    elif any(k in n for k in ["audio", "sound", "music", "podcast", "earshot", "voice"]):
        pool = "Media"
        emoji = "🎵"
        icon = "music-note"
        color = "text-amber-600 bg-amber-50 border-amber-200"
    elif any(k in n for k in ["ai", "robot", "llm", "intelligence", "gpt", "agent", "prompt", "brain"]):
        pool = "AI"
        emoji = "🤖"
        icon = "cpu-charge"
        color = "text-indigo-600 bg-indigo-50 border-indigo-200"
    elif any(k in n for k in ["chart", "analytics", "stat", "trend", "seo", "audit", "metric", "ranking", "rank"]):
        pool = "Chart"
        emoji = "📈"
        icon = "chart-2"
        color = "text-blue-600 bg-blue-50 border-blue-200"
    elif any(k in n for k in ["design", "ui", "ux", "figma", "visual", "art", "style", "theme", "color"]):
        pool = "Design"
        emoji = "🎨"
        icon = "bezier"
        color = "text-fuchsia-600 bg-fuchsia-50 border-fuchsia-200"
    elif any(k in n for k in ["crypto", "finance", "money", "wallet", "trade", "dollar", "card"]):
        pool = "Security"
        emoji = "💰"
        icon = "dollar-circle"
        color = "text-emerald-600 bg-emerald-50 border-emerald-200"
    elif any(k in n for k in ["security", "shield", "protect", "auth", "token", "lock", "guard", "safe"]):
        pool = "Security"
        emoji = "🛡️"
        icon = "shield-tick"
        color = "text-emerald-600 bg-emerald-50 border-emerald-200"
    elif any(k in n for k in ["code", "dev", "git", "cli", "terminal", "script", "tool", "python", "node", "npm"]):
        pool = "Technology"
        emoji = "💻"
        icon = "command"
        color = "text-sky-600 bg-sky-50 border-sky-200"
    elif item_type == "MCP Server":
        pool = "Technology"
        emoji = "🔌"
        icon = "server"
        color = "text-emerald-600 bg-emerald-50 border-emerald-200"
    elif item_type == "Command":
        pool = "Essential"
        emoji = "⚡"
        icon = "flash-circle"
        color = "text-amber-600 bg-amber-50 border-amber-200"
    elif item_type == "Rule":
        pool = "Essential"
        emoji = "📜"
        icon = "shield-security"
        color = "text-purple-600 bg-purple-50 border-purple-200"
    elif item_type == "CLI":
        pool = "Technology"
        emoji = "💻"
        icon = "command"
        color = "text-sky-600 bg-sky-50 border-sky-200"

    # Deterministic selection from selected category pool
    target_pool = FALLBACK_3D_POOLS.get(pool, FALLBACK_3D_POOLS["Essential"])
    hash_idx = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16) % len(target_pool)
    model_3d = target_pool[hash_idx]

    return {
        "emoji": emoji,
        "icon": icon,
        "thiings": model_3d,
        "color": color
    }


def scan_antigravity_skills():
    skills = []
    # 1. Config skills
    config_skills_dir = GEMINI_DIR / "config" / "skills"
    if config_skills_dir.exists():
        for item in config_skills_dir.iterdir():
            if item.is_dir():
                skill_file = item / "SKILL.md"
                desc = "No description"
                if skill_file.exists():
                    try:
                        text = skill_file.read_text(encoding="utf-8", errors="ignore")
                        meta, _ = parse_markdown_frontmatter(text)
                        desc = meta.get("description", desc)
                    except Exception:
                        pass
                
                stats = calculate_folder_stats(item)
                visual = assign_icon_and_emoji(item.name, "Skill", "Antigravity")
                triggers = extract_triggers(desc)
                
                # Token weight estimation for skill
                skill_chars = len(text) if (skill_file.exists() and 'text' in locals() and text) else (stats["size_kb"] * 1024)
                skill_tokens = max(50, int(skill_chars / 3.8))
                
                skills.append({
                    "id": f"agy-{item.name}",
                    "name": item.name,
                    "platform": "Antigravity",
                    "scope": "User Config",
                    "origin": "user",
                    "is_user_created": True,
                    "type": "Skill",
                    "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                    "icon": visual["icon"],
                    "color": visual["color"],
                    "description": desc,
                    "triggers": triggers,
                    "token_weight": skill_tokens,
                    "path": str(item),
                    "last_modified": get_file_time(item),
                    "has_skill_md": skill_file.exists(),
                    "size_kb": stats["size_kb"],
                    "file_count": stats["file_count"],
                    "line_count": stats["line_count"],
                    "richness_score": stats["richness_score"]
                })

    # 2. Builtin skills
    builtin_skills_dir = GEMINI_DIR / "antigravity" / "builtin" / "skills"
    if builtin_skills_dir.exists():
        for item in builtin_skills_dir.iterdir():
            if item.is_dir():
                skill_file = item / "SKILL.md"
                desc = "Built-in Antigravity Skill"
                if skill_file.exists():
                    try:
                        text = skill_file.read_text(encoding="utf-8", errors="ignore")
                        meta, _ = parse_markdown_frontmatter(text)
                        desc = meta.get("description", desc)
                    except Exception:
                        pass
                
                stats = calculate_folder_stats(item)
                visual = assign_icon_and_emoji(item.name, "Skill", "Antigravity")
                triggers = extract_triggers(desc)
                
                skill_chars = len(text) if (skill_file.exists() and 'text' in locals() and text) else (stats["size_kb"] * 1024)
                skill_tokens = max(50, int(skill_chars / 3.8))
                
                skills.append({
                    "id": f"agy-builtin-{item.name}",
                    "name": item.name,
                    "platform": "Antigravity",
                    "scope": "Built-in",
                    "origin": "builtin",
                    "is_user_created": False,
                    "type": "Skill",
                    "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                    "icon": visual["icon"],
                    "color": visual["color"],
                    "description": desc,
                    "triggers": triggers,
                    "token_weight": skill_tokens,
                    "path": str(item),
                    "last_modified": get_file_time(item),
                    "has_skill_md": skill_file.exists(),
                    "size_kb": stats["size_kb"],
                    "file_count": stats["file_count"],
                    "line_count": stats["line_count"],
                    "richness_score": stats["richness_score"]
                })

    # Sort descending by richness score
    skills.sort(key=lambda s: s["richness_score"], reverse=True)
    return skills

def scan_antigravity_mcp():
    mcps = []
    mcp_dir = GEMINI_DIR / "antigravity" / "mcp"
    if mcp_dir.exists():
        for item in mcp_dir.iterdir():
            if item.is_dir():
                tool_files = list(item.glob("*.json"))
                instructions_file = item / "instructions.md"
                has_instructions = instructions_file.exists()
                tools_list = []
                tools_schema = []
                for tf in tool_files:
                    t_stem = tf.stem
                    tools_list.append(t_stem)
                    try:
                        t_data = json.loads(tf.read_text(encoding="utf-8", errors="ignore"))
                        t_desc = t_data.get("description", "").strip()
                        schema_obj = t_data.get("parameters") or t_data.get("inputSchema") or {}
                        t_params = list(schema_obj.get("properties", {}).keys())
                        tools_schema.append({
                            "name": t_data.get("name", t_stem),
                            "description": t_desc[:180] + ("..." if len(t_desc) > 180 else ""),
                            "params": t_params
                        })
                    except Exception:
                        tools_schema.append({"name": t_stem, "description": "", "params": []})

                stats = calculate_folder_stats(item)
                visual = assign_icon_and_emoji(item.name, "MCP Server", "Antigravity")
                skills_user_built = ["hooshang", "vidiq"]
                is_custom = (item.name in skills_user_built)
                
                # Token weight calculation for MCP schemas
                total_schema_chars = sum(len(tf.read_text(encoding="utf-8", errors="ignore")) for tf in tool_files)
                mcp_tokens = int(total_schema_chars / 3.8) if total_schema_chars > 0 else (len(tools_list) * 120)
                
                mcps.append({
                    "id": f"agy-mcp-{item.name}",
                    "name": item.name,
                    "platform": "Antigravity",
                    "type": "MCP Server",
                    "origin": "user" if is_custom else "system",
                    "is_user_created": is_custom,
                    "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                    "icon": visual["icon"],
                    "color": visual["color"],
                    "tools_count": len(tools_list),
                    "tools": tools_list,
                    "tools_schema": tools_schema,
                    "token_weight": mcp_tokens,
                    "status": "online",
                    "has_instructions": has_instructions,
                    "path": str(item),
                    "last_modified": get_file_time(item),
                    "size_kb": stats["size_kb"],
                    "file_count": stats["file_count"],
                    "line_count": stats["line_count"],
                    "richness_score": stats["richness_score"] + (len(tools_list) * 5000)
                })
    mcps.sort(key=lambda m: m["richness_score"], reverse=True)
    return mcps

def scan_antigravity_rules():
    rules = []
    rules_dir = GEMINI_DIR / "antigravity" / "rules"
    if rules_dir.exists():
        for item in rules_dir.glob("*.md"):
            try:
                text = item.read_text(encoding="utf-8", errors="ignore")
                meta, _ = parse_markdown_frontmatter(text)
                desc = meta.get("description", "System Rule")
            except Exception:
                desc = "System Rule"
            visual = assign_icon_and_emoji(item.name, "Rule", "Antigravity")
            rules.append({
                "id": f"agy-rule-{item.stem}",
                "name": item.name,
                "platform": "Antigravity",
                "type": "Rule",
                "origin": "user",
                "is_user_created": True,
                "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                "icon": visual["icon"],
                "color": visual["color"],
                "description": desc,
                "path": str(item),
                "last_modified": get_file_time(item)
            })
    return rules

def scan_claude_desktop():
    servers = []
    config_file = CLAUDE_APPDATA / "claude_desktop_config.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                mcp_servers = data.get("mcpServers", {})
                for name, conf in mcp_servers.items():
                    cmd = conf.get("command", "")
                    args = conf.get("args", [])
                    env = conf.get("env", {})
                    visual = assign_icon_and_emoji(name, "MCP Server", "Claude Desktop")
                    servers.append({
                        "id": f"claude-mcp-{name}",
                        "name": name,
                        "platform": "Claude Desktop",
                        "type": "MCP Server",
                        "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                        "icon": visual["icon"],
                        "color": visual["color"],
                        "command": cmd,
                        "args": args,
                        "env_vars": list(env.keys()),
                        "raw_config": conf,
                        "path": str(config_file),
                        "last_modified": get_file_time(config_file)
                    })
        except Exception as e:
            print(f"Error parsing Claude Desktop config: {e}", file=sys.stderr)
    return servers

def scan_claude_code():
    skills = []
    commands = []
    plugins = []

    # Claude Skills
    skills_dir = CLAUDE_DIR / "skills"
    if skills_dir.exists():
        for item in skills_dir.iterdir():
            if item.is_dir():
                skill_file = item / "SKILL.md"
                desc = "Claude Code Skill"
                if skill_file.exists():
                    try:
                        text = skill_file.read_text(encoding="utf-8", errors="ignore")
                        meta, _ = parse_markdown_frontmatter(text)
                        desc = meta.get("description", desc)
                    except Exception:
                        pass
                stats = calculate_folder_stats(item)
                visual = assign_icon_and_emoji(item.name, "Skill", "Claude Code")
                triggers = extract_triggers(desc)
                
                skill_chars = len(text) if (skill_file.exists() and 'text' in locals() and text) else (stats["size_kb"] * 1024)
                skill_tokens = max(50, int(skill_chars / 3.8))
                
                skills.append({
                    "id": f"claude-skill-{item.name}",
                    "name": item.name,
                    "platform": "Claude Code",
                    "type": "Skill",
                    "origin": "user",
                    "is_user_created": True,
                    "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                    "icon": visual["icon"],
                    "color": visual["color"],
                    "description": desc,
                    "triggers": triggers,
                    "token_weight": skill_tokens,
                    "path": str(item),
                    "last_modified": get_file_time(item),
                    "size_kb": stats["size_kb"],
                    "file_count": stats["file_count"],
                    "line_count": stats["line_count"],
                    "richness_score": stats["richness_score"]
                })
    skills.sort(key=lambda s: s["richness_score"], reverse=True)

    # Claude Commands
    commands_dir = CLAUDE_DIR / "commands"
    if commands_dir.exists():
        for item in commands_dir.glob("*.md"):
            desc = "Custom Slash Command"
            try:
                text = item.read_text(encoding="utf-8", errors="ignore")
                meta, _ = parse_markdown_frontmatter(text)
                desc = meta.get("description", desc)
            except Exception:
                pass
            visual = assign_icon_and_emoji(item.stem, "Command", "Claude Code")
            commands.append({
                "id": f"claude-cmd-{item.stem}",
                "name": f"/{item.stem}",
                "platform": "Claude Code",
                "type": "Command",
                "origin": "user",
                "is_user_created": True,
                "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                "icon": visual["icon"],
                "color": visual["color"],
                "description": desc,
                "path": str(item),
                "last_modified": get_file_time(item)
            })

    # Claude Plugins
    plugins_dir = CLAUDE_DIR / "plugins"
    if plugins_dir.exists():
        for item in plugins_dir.iterdir():
            if item.is_dir():
                visual = assign_icon_and_emoji(item.name, "Plugin", "Claude Code")
                plugins.append({
                    "id": f"claude-plugin-{item.name}",
                    "name": item.name,
                    "platform": "Claude Code",
                    "type": "Plugin",
                    "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                    "icon": visual["icon"],
                    "color": visual["color"],
                    "path": str(item),
                    "last_modified": get_file_time(item)
                })

    return skills, commands, plugins

def scan_cursor_windsurf():
    """Scans Cursor, Windsurf, and other modern AI agent directories."""
    items = []
    agent_paths = [
        (USER_HOME / ".cursor" / "skills", "Cursor", "Skill"),
        (USER_HOME / ".cursor" / "rules", "Cursor", "Rule"),
        (USER_HOME / ".windsurf" / "skills", "Windsurf", "Skill"),
        (USER_HOME / ".windsurf" / "rules", "Windsurf", "Rule"),
        (USER_HOME / ".continue" / "prompts", "Continue", "Prompt"),
    ]
    for folder, platform, itype in agent_paths:
        if folder.exists():
            for f in folder.iterdir():
                if f.name.startswith("."):
                    continue
                visual = assign_icon_and_emoji(f.stem, itype, platform)
                stats = calculate_folder_stats(f) if f.is_dir() else {"size_kb": round(f.stat().st_size/1024, 1), "file_count": 1, "line_count": 0, "richness_score": 500}
                desc = f"{platform} {itype}"
                if f.is_file() and f.suffix in [".md", ".txt"]:
                    try:
                        meta, _ = parse_markdown_frontmatter(f.read_text(encoding="utf-8", errors="ignore"))
                        desc = meta.get("description", desc)
                    except Exception:
                        pass
                items.append({
                    "id": f"{platform.lower()}-{f.stem}",
                    "name": f.stem,
                    "platform": platform,
                    "type": itype,
                    "origin": "user",
                    "is_user_created": True,
                    "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                    "icon": visual["icon"],
                    "color": visual["color"],
                    "description": desc,
                    "triggers": extract_triggers(desc),
                    "path": str(f),
                    "last_modified": get_file_time(f),
                    "size_kb": stats["size_kb"],
                    "file_count": stats["file_count"],
                    "line_count": stats.get("line_count", 0),
                    "richness_score": stats.get("richness_score", 500)
                })
    return items

def find_creator_os_dir():
    """Finds Creator OS directory dynamically across Mac and Windows."""
    candidates = [
        USER_HOME / "🧨 Projects" / "Hesvm (IG PAGE)" / "creator-os",
        USER_HOME / "Projects" / "Hesvm (IG PAGE)" / "creator-os",
        USER_HOME / "Desktop" / "creator-os",
        USER_HOME / "Documents" / "creator-os",
        USER_HOME / "creator-os",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

def scan_creator_os():
    return []

def scan_clis():
    clis = []

    # NPM Global Packages
    if NPM_GLOBAL_DIR.exists():
        node_modules = NPM_GLOBAL_DIR / "node_modules"
        if node_modules.exists():
            for item in node_modules.iterdir():
                if item.is_dir():
                    if item.name.startswith("@"):
                        for sub_item in item.iterdir():
                            if sub_item.is_dir():
                                pkg_json = sub_item / "package.json"
                                ver = "Unknown"
                                desc = ""
                                if pkg_json.exists():
                                    try:
                                        with open(pkg_json, "r", encoding="utf-8") as f:
                                            pdata = json.load(f)
                                            ver = pdata.get("version", ver)
                                            desc = pdata.get("description", desc)
                                    except Exception:
                                        pass
                                visual = assign_icon_and_emoji(sub_item.name, "CLI", "NPM")
                                clis.append({
                                    "id": f"npm-{item.name}/{sub_item.name}",
                                    "name": f"{item.name}/{sub_item.name}",
                                    "category": "NPM Global",
                                    "type": "CLI",
                                    "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                                    "icon": visual["icon"],
                                    "color": visual["color"],
                                    "version": ver,
                                    "description": desc,
                                    "path": str(sub_item),
                                    "last_modified": get_file_time(sub_item)
                                })
                    else:
                        pkg_json = item / "package.json"
                        ver = "Unknown"
                        desc = ""
                        if pkg_json.exists():
                            try:
                                with open(pkg_json, "r", encoding="utf-8") as f:
                                    pdata = json.load(f)
                                    ver = pdata.get("version", ver)
                                    desc = pdata.get("description", desc)
                            except Exception:
                                pass
                        visual = assign_icon_and_emoji(item.name, "CLI", "NPM")
                        clis.append({
                            "id": f"npm-{item.name}",
                            "name": item.name,
                            "category": "NPM Global",
                            "type": "CLI",
                            "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                            "icon": visual["icon"],
                            "color": visual["color"],
                            "version": ver,
                            "description": desc,
                            "path": str(item),
                            "last_modified": get_file_time(item)
                        })

    # Standard tool paths
    core_tools = [
        {"name": "claude", "desc": "Anthropic Claude Code CLI"},
        {"name": "agy", "desc": "Google Antigravity CLI"},
        {"name": "uv", "desc": "Astral UV Python Package & Tool Manager"},
        {"name": "uvx", "desc": "Astral UV Executable Tool Runner"},
        {"name": "pnpm", "desc": "Fast, disk space efficient package manager"},
        {"name": "npm", "desc": "Node Package Manager"},
        {"name": "node", "desc": "Node.js JavaScript Runtime"},
        {"name": "python", "desc": "Python Programming Language Interpreter"},
        {"name": "git", "desc": "Distributed Version Control System"},
        {"name": "code", "desc": "Visual Studio Code CLI"}
    ]

    for tool in core_tools:
        name = tool["name"]
        try:
            # Cross-platform command existence lookup
            which_cmd = "which" if sys.platform != "win32" else "where.exe"
            res = subprocess.run([which_cmd, name], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                paths = [p.strip() for p in res.stdout.strip().splitlines() if p.strip()]
                first_path = paths[0] if paths else "In PATH"
                visual = assign_icon_and_emoji(name, "CLI", "System")
                clis.append({
                    "id": f"cli-{name}",
                    "name": name,
                    "category": "System Executable",
                    "type": "CLI",
                    "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                    "icon": visual["icon"],
                    "color": visual["color"],
                    "version": "Installed",
                    "description": tool["desc"],
                    "path": first_path,
                    "last_modified": get_file_time(first_path) if os.path.exists(first_path) else "Active"
                })
        except Exception:
            pass

    return clis
    clis = []

    # NPM Global Packages
    if NPM_GLOBAL_DIR.exists():
        node_modules = NPM_GLOBAL_DIR / "node_modules"
        if node_modules.exists():
            for item in node_modules.iterdir():
                if item.is_dir():
                    if item.name.startswith("@"):
                        for sub_item in item.iterdir():
                            if sub_item.is_dir():
                                pkg_json = sub_item / "package.json"
                                ver = "Unknown"
                                desc = ""
                                if pkg_json.exists():
                                    try:
                                        with open(pkg_json, "r", encoding="utf-8") as f:
                                            pdata = json.load(f)
                                            ver = pdata.get("version", ver)
                                            desc = pdata.get("description", desc)
                                    except Exception:
                                        pass
                                visual = assign_icon_and_emoji(sub_item.name, "CLI", "NPM")
                                clis.append({
                                    "id": f"npm-{item.name}/{sub_item.name}",
                                    "name": f"{item.name}/{sub_item.name}",
                                    "category": "NPM Global",
                                    "type": "CLI",
                                    "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                                    "icon": visual["icon"],
                                    "color": visual["color"],
                                    "version": ver,
                                    "description": desc,
                                    "path": str(sub_item),
                                    "last_modified": get_file_time(sub_item)
                                })
                    else:
                        pkg_json = item / "package.json"
                        ver = "Unknown"
                        desc = ""
                        if pkg_json.exists():
                            try:
                                with open(pkg_json, "r", encoding="utf-8") as f:
                                    pdata = json.load(f)
                                    ver = pdata.get("version", ver)
                                    desc = pdata.get("description", desc)
                            except Exception:
                                pass
                        visual = assign_icon_and_emoji(item.name, "CLI", "NPM")
                        clis.append({
                            "id": f"npm-{item.name}",
                            "name": item.name,
                            "category": "NPM Global",
                            "type": "CLI",
                            "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                            "icon": visual["icon"],
                            "color": visual["color"],
                            "version": ver,
                            "description": desc,
                            "path": str(item),
                            "last_modified": get_file_time(item)
                        })

    # Standard tool paths
    core_tools = [
        {"name": "claude", "desc": "Anthropic Claude Code CLI"},
        {"name": "agy", "desc": "Google Antigravity CLI"},
        {"name": "uv", "desc": "Astral UV Python Package & Tool Manager"},
        {"name": "uvx", "desc": "Astral UV Executable Tool Runner"},
        {"name": "pnpm", "desc": "Fast, disk space efficient package manager"},
        {"name": "npm", "desc": "Node Package Manager"},
        {"name": "node", "desc": "Node.js JavaScript Runtime"},
        {"name": "python", "desc": "Python Programming Language Interpreter"},
        {"name": "git", "desc": "Distributed Version Control System"},
        {"name": "code", "desc": "Visual Studio Code CLI"}
    ]

    for tool in core_tools:
        name = tool["name"]
        try:
            # Check if command exists
            res = subprocess.run(["where.exe", name], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                paths = [p.strip() for p in res.stdout.strip().splitlines() if p.strip()]
                first_path = paths[0] if paths else "In PATH"
                visual = assign_icon_and_emoji(name, "CLI", "System")
                clis.append({
                    "id": f"cli-{name}",
                    "name": name,
                    "category": "System Executable",
                    "type": "CLI",
                    "emoji": visual["emoji"],
                    "thiings": visual.get("thiings", ""),
                    "icon": visual["icon"],
                    "color": visual["color"],
                    "version": "Installed",
                    "description": tool["desc"],
                    "path": first_path,
                    "last_modified": get_file_time(first_path) if os.path.exists(first_path) else "Active"
                })
        except Exception:
            pass

    return clis

def calculate_fingerprint():
    """Generates a fast fingerprint of watched directories to detect changes instantly."""
    watch_dirs = [
        GEMINI_DIR / "config" / "skills",
        GEMINI_DIR / "antigravity" / "mcp",
        GEMINI_DIR / "antigravity" / "rules",
        CLAUDE_APPDATA / "claude_desktop_config.json",
        CLAUDE_DIR / "skills",
        CLAUDE_DIR / "commands",
        NPM_GLOBAL_DIR / "node_modules"
    ]
    parts = []
    for p in watch_dirs:
        try:
            if p.is_file():
                parts.append(f"{p}:{p.stat().st_mtime}")
            elif p.is_dir():
                parts.append(f"{p}:{p.stat().st_mtime}")
                # Check top-level child mtimes
                for child in p.iterdir():
                    try:
                        parts.append(f"{child.name}:{child.stat().st_mtime}")
                    except Exception:
                        pass
        except Exception:
            pass
    return hash("".join(parts))

def get_complete_ecosystem():
    agy_skills = scan_antigravity_skills()
    agy_mcp = scan_antigravity_mcp()
    agy_rules = scan_antigravity_rules()
    claude_mcp = scan_claude_desktop()
    claude_skills, claude_commands, claude_plugins = scan_claude_code()
    clis = scan_clis()
    cursor_windsurf_items = scan_cursor_windsurf()

    creator_os_items = []

    # Parity Matrix
    agy_skill_names = {s["name"].lower() for s in agy_skills}
    claude_skill_names = {s["name"].lower() for s in claude_skills}
    all_skill_names = sorted(list(agy_skill_names | claude_skill_names))

    skill_parity = []
    for name in all_skill_names:
        in_agy = name in agy_skill_names
        in_claude = name in claude_skill_names
        status = "synced" if (in_agy and in_claude) else ("agy_only" if in_agy else "claude_only")
        skill_parity.append({
            "name": name,
            "in_antigravity": in_agy,
            "in_claude": in_claude,
            "status": status
        })

    agy_mcp_names = {m["name"].lower() for m in agy_mcp}
    claude_mcp_names = {m["name"].lower() for m in claude_mcp}
    all_mcp_names = sorted(list(agy_mcp_names | claude_mcp_names))

    mcp_parity = []
    for name in all_mcp_names:
        in_agy = name in agy_mcp_names
        in_claude = name in claude_mcp_names
        status = "synced" if (in_agy and in_claude) else ("agy_only" if in_agy else "claude_only")
        mcp_parity.append({
            "name": name,
            "in_antigravity": in_agy,
            "in_claude": in_claude,
            "status": status
        })

    # 1. Calculate Trigger Conflicts across all skills
    all_skills_for_conflicts = agy_skills + claude_skills
    trigger_map = {}
    for s in all_skills_for_conflicts:
        s_name = s.get("name")
        for t in s.get("triggers", []):
            t_clean = t.strip().lower().lstrip("#").lstrip("/")
            if not t_clean or len(t_clean) < 3:
                continue
            trigger_map.setdefault(t_clean, []).append(s_name)

    conflicts = []
    for t, s_list in sorted(trigger_map.items()):
        unique_skills = sorted(list(set(s_list)))
        if len(unique_skills) > 1:
            conflicts.append({
                "trigger": t,
                "count": len(unique_skills),
                "skills": unique_skills
            })

    # 2. Total Token Weight across ecosystem
    total_mcp_tokens = sum(m.get("token_weight", 0) for m in agy_mcp)
    total_skill_tokens = sum(s.get("token_weight", 0) for s in (agy_skills + claude_skills))
    total_token_weight = total_mcp_tokens + total_skill_tokens

    all_items = agy_skills + agy_mcp + agy_rules + claude_skills + claude_mcp + claude_commands + claude_plugins
    user_created_skills_count = sum(1 for s in (agy_skills + claude_skills) if s.get("is_user_created"))
    user_created_total_count = sum(1 for i in all_items if i.get("is_user_created"))

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "total_antigravity_skills": len(agy_skills),
            "total_antigravity_mcp": len(agy_mcp),
            "total_antigravity_rules": len(agy_rules),
            "total_claude_skills": len(claude_skills),
            "total_claude_commands": len(claude_commands),
            "total_claude_mcp": len(claude_mcp),
            "total_clis": len(clis),
            "total_creator_os_items": len(creator_os_items),
            "synced_skills_count": sum(1 for s in skill_parity if s["status"] == "synced"),
            "synced_mcp_count": sum(1 for m in mcp_parity if m["status"] == "synced"),
            "user_created_skills_count": user_created_skills_count,
            "user_created_total_count": user_created_total_count + len(creator_os_items),
            "total_conflicts_count": len(conflicts),
            "total_token_weight": total_token_weight,
            "total_mcp_tokens": total_mcp_tokens,
            "total_skill_tokens": total_skill_tokens
        },
        "creator_os": creator_os_items,
        "antigravity": {
            "skills": agy_skills,
            "mcp": agy_mcp,
            "rules": agy_rules
        },
        "claude": {
            "mcp": claude_mcp,
            "skills": claude_skills,
            "commands": claude_commands,
            "plugins": claude_plugins
        },
        "clis": clis,
        "cursor_windsurf": cursor_windsurf_items,
        "parity": {
            "skills": skill_parity,
            "mcp": mcp_parity
        },
        "conflicts": conflicts
    }

if __name__ == "__main__":
    data = get_complete_ecosystem()
    print(json.dumps(data, indent=2, ensure_ascii=False))
