import os
import sys
import json
import time
import glob
import subprocess
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
    """Calculates size, file count, and line count for depth/richness scoring."""
    total_bytes = 0
    file_count = 0
    line_count = 0
    try:
        for f in folder_path.rglob("*"):
            if f.is_file():
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

THIINGS_ASSETS = {
    "brain": "/assets/thiings/brain.png",
    "camera": "/assets/thiings/camera.png",
    "video": "/assets/thiings/video.png",
    "rocket": "/assets/thiings/rocket.png",
    "target": "/assets/thiings/target.png",
    "code": "/assets/thiings/code.png",
    "book": "/assets/thiings/book.png",
    "shield": "/assets/thiings/shield.png",
    "document": "/assets/thiings/document.png",
    "globe": "/assets/thiings/globe.png",
    "crown": "/assets/thiings/crown.png",
    "folder": "/assets/thiings/folder.png",
    "magic-wand": "/assets/thiings/magic-wand.png",
    "scissors": "/assets/thiings/scissors.png",
    "lightning": "/assets/thiings/lightning.png",
    "star": "/assets/thiings/star.png",
    "sparkle": "/assets/thiings/sparkle.png",
    "heart": "/assets/thiings/heart.png",
    "search": "/assets/thiings/search.png",
    "pen": "/assets/thiings/pen.png",
    "headphones": "/assets/thiings/headphones.png",
    "speaker": "/assets/thiings/speaker.png",
    "palette": "/assets/thiings/palette.png",
    "briefcase": "/assets/thiings/briefcase.png",
    "flame": "/assets/thiings/flame.png",
    "robot": "/assets/thiings/robot.png",
    "smartphone": "/assets/thiings/smartphone.png",
    "calendar": "/assets/thiings/calendar.png",
    "chat": "/assets/thiings/chat.png",
    "gear": "/assets/thiings/gear.png",
    "wrench": "/assets/thiings/wrench.png",
    "puzzle": "/assets/thiings/puzzle.png"
}

def assign_icon_and_emoji(name, item_type="Skill", platform=""):
    """Assigns a semantic 3D thiings asset, emoji, and Iconsax icon to each item."""
    n = name.lower()
    
    # Creator & Video Skills
    if "creator-intelligence" in n:
        return {"emoji": "🧠", "icon": "cpu-charge", "thiings": THIINGS_ASSETS["brain"], "color": "text-purple-600 bg-purple-50 border-purple-200"}
    elif "trend-radar" in n:
        return {"emoji": "📡", "icon": "radar-2", "thiings": THIINGS_ASSETS["globe"], "color": "text-blue-600 bg-blue-50 border-blue-200"}
    elif "audience-positioning" in n:
        return {"emoji": "🎯", "icon": "target", "thiings": THIINGS_ASSETS["target"], "color": "text-rose-600 bg-rose-50 border-rose-200"}
    elif "topic-discovery" in n:
        return {"emoji": "💡", "icon": "lamp-on", "thiings": THIINGS_ASSETS["search"], "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif "idea-development" in n:
        return {"emoji": "🌱", "icon": "magic-star", "thiings": THIINGS_ASSETS["magic-wand"], "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}
    elif "hook-engineering" in n:
        return {"emoji": "🪝", "icon": "flash-circle", "thiings": THIINGS_ASSETS["lightning"], "color": "text-red-600 bg-red-50 border-red-200"}
    elif "scriptwriting" in n:
        return {"emoji": "✍️", "icon": "edit-2", "thiings": THIINGS_ASSETS["pen"], "color": "text-indigo-600 bg-indigo-50 border-indigo-200"}
    elif "visual-storyboarding" in n:
        return {"emoji": "🎬", "icon": "video-play", "thiings": THIINGS_ASSETS["camera"], "color": "text-teal-600 bg-teal-50 border-teal-200"}
    elif "retention-editing" in n:
        return {"emoji": "✂️", "icon": "scissor", "thiings": THIINGS_ASSETS["scissors"], "color": "text-orange-600 bg-orange-50 border-orange-200"}
    elif "platform-packaging" in n:
        return {"emoji": "📦", "icon": "box-1", "thiings": THIINGS_ASSETS["folder"], "color": "text-sky-600 bg-sky-50 border-sky-200"}
    elif "publishing-operations" in n:
        return {"emoji": "🚀", "icon": "send-2", "thiings": THIINGS_ASSETS["rocket"], "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}
    elif "performance-learning" in n:
        return {"emoji": "📈", "icon": "chart-2", "thiings": THIINGS_ASSETS["sparkle"], "color": "text-blue-600 bg-blue-50 border-blue-200"}
    elif "youtube-thumbnail" in n:
        return {"emoji": "🖼️", "icon": "gallery-edit", "thiings": THIINGS_ASSETS["palette"], "color": "text-red-600 bg-red-50 border-red-200"}
    elif "carousel-craft" in n or "ig-carousel" in n or "carousel" in n:
        return {"emoji": "📑", "icon": "slider-vertical", "thiings": THIINGS_ASSETS["document"], "color": "text-fuchsia-600 bg-fuchsia-50 border-fuchsia-200"}
    elif "client-acquisition" in n:
        return {"emoji": "💼", "icon": "dollar-circle", "thiings": THIINGS_ASSETS["briefcase"], "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}
    elif "sound-design" in n or "soundcloud" in n:
        return {"emoji": "🎵", "icon": "music-note", "thiings": THIINGS_ASSETS["headphones"], "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif "watch-video" in n or "video-vision" in n or "analyze-edit" in n or "pushe-film" in n or "video-editor" in n:
        return {"emoji": "👁️", "icon": "eye", "thiings": THIINGS_ASSETS["video"], "color": "text-violet-600 bg-violet-50 border-violet-200"}
    elif "vidiq" in n:
        return {"emoji": "📊", "icon": "chart-square", "thiings": THIINGS_ASSETS["sparkle"], "color": "text-red-600 bg-red-50 border-red-200"}

    # Instagram Suite
    elif "ig-reel" in n:
        return {"emoji": "📱", "icon": "video-square", "thiings": THIINGS_ASSETS["smartphone"], "color": "text-pink-600 bg-pink-50 border-pink-200"}
    elif "ig-story" in n:
        return {"emoji": "⏱️", "icon": "clock", "thiings": THIINGS_ASSETS["calendar"], "color": "text-rose-600 bg-rose-50 border-rose-200"}
    elif "ig-viral" in n:
        return {"emoji": "🔥", "icon": "trend-up", "thiings": THIINGS_ASSETS["flame"], "color": "text-orange-600 bg-orange-50 border-orange-200"}
    elif "ig-profile" in n:
        return {"emoji": "👤", "icon": "profile-circle", "thiings": THIINGS_ASSETS["heart"], "color": "text-indigo-600 bg-indigo-50 border-indigo-200"}
    elif "ig-caption" in n or "ig-reply" in n or "ig-comment" in n or "ig-dm" in n:
        return {"emoji": "💬", "icon": "message-text-1", "thiings": THIINGS_ASSETS["chat"], "color": "text-cyan-600 bg-cyan-50 border-cyan-200"}
    elif "ig-human" in n or "security" in n:
        return {"emoji": "🛡️", "icon": "shield-tick", "thiings": THIINGS_ASSETS["shield"], "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}
    elif "ig-plan" in n:
        return {"emoji": "🗓️", "icon": "calendar-tick", "thiings": THIINGS_ASSETS["calendar"], "color": "text-purple-600 bg-purple-50 border-purple-200"}
    elif "ig-audit" in n:
        return {"emoji": "🔍", "icon": "scan-barcode", "thiings": THIINGS_ASSETS["search"], "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif "ig-repurpose" in n:
        return {"emoji": "🔄", "icon": "refresh-circle", "thiings": THIINGS_ASSETS["magic-wand"], "color": "text-indigo-600 bg-indigo-50 border-indigo-200"}
    elif "ig-creator-expert" in n or "creator-os" in n:
        return {"emoji": "👑", "icon": "crown-1", "thiings": THIINGS_ASSETS["crown"], "color": "text-amber-600 bg-amber-50 border-amber-200"}

    # UI / Design / Figma
    elif "figma" in n:
        return {"emoji": "🎨", "icon": "bezier", "thiings": THIINGS_ASSETS["palette"], "color": "text-purple-600 bg-purple-50 border-purple-200"}
    elif "make-interfaces-feel-better" in n or "vibe-component" in n:
        return {"emoji": "✨", "icon": "magicpen", "thiings": THIINGS_ASSETS["sparkle"], "color": "text-fuchsia-600 bg-fuchsia-50 border-fuchsia-200"}
    elif "vibe-production-hardening" in n:
        return {"emoji": "🔒", "icon": "security-safe", "thiings": THIINGS_ASSETS["shield"], "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}

    # SEO & Search
    elif "seo" in n or "search-console" in n:
        return {"emoji": "🌐", "icon": "global-search", "thiings": THIINGS_ASSETS["globe"], "color": "text-blue-600 bg-blue-50 border-blue-200"}

    # Persian & Localization
    elif "persian-writing" in n or "persian-rtl" in n or "persian" in n:
        return {"emoji": "🇮🇷", "icon": "translate", "thiings": THIINGS_ASSETS["book"], "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}

    # MCP Servers & Tools
    elif "hooshang" in n or "robot" in n:
        return {"emoji": "🤖", "icon": "robot", "thiings": THIINGS_ASSETS["robot"], "color": "text-indigo-600 bg-indigo-50 border-indigo-200"}
    elif "mem0" in n:
        return {"emoji": "🧠", "icon": "hierarchy-3", "thiings": THIINGS_ASSETS["brain"], "color": "text-purple-600 bg-purple-50 border-purple-200"}
    elif "notion" in n:
        return {"emoji": "📝", "icon": "document-text", "thiings": THIINGS_ASSETS["document"], "color": "text-slate-800 bg-slate-100 border-slate-200"}
    elif "posthog" in n:
        return {"emoji": "🦔", "icon": "data-2", "thiings": THIINGS_ASSETS["sparkle"], "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif "jitter" in n:
        return {"emoji": "🎬", "icon": "video-play", "thiings": THIINGS_ASSETS["video"], "color": "text-purple-600 bg-purple-50 border-purple-200"}

    # CLIs & Tools
    elif "claude" in n:
        return {"emoji": "🤖", "icon": "command", "thiings": THIINGS_ASSETS["robot"], "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif "agy" in n or "antigravity" in n:
        return {"emoji": "🚀", "icon": "flash-1", "thiings": THIINGS_ASSETS["rocket"], "color": "text-blue-600 bg-blue-50 border-blue-200"}
    elif "uv" in n or "uvx" in n:
        return {"emoji": "⚡", "icon": "electricity", "thiings": THIINGS_ASSETS["lightning"], "color": "text-violet-600 bg-violet-50 border-violet-200"}
    elif "python" in n or "code" in n:
        return {"emoji": "🐍", "icon": "code-1", "thiings": THIINGS_ASSETS["code"], "color": "text-sky-600 bg-sky-50 border-sky-200"}
    elif "git" in n or "wrench" in n:
        return {"emoji": "🌿", "icon": "git-branch", "thiings": THIINGS_ASSETS["wrench"], "color": "text-orange-600 bg-orange-50 border-orange-200"}

    # Fallbacks by Type
    if item_type == "MCP Server":
        return {"emoji": "🔌", "icon": "server", "thiings": THIINGS_ASSETS["gear"], "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}
    elif item_type == "Command":
        return {"emoji": "⚡", "icon": "slash", "thiings": THIINGS_ASSETS["lightning"], "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif item_type == "Rule":
        return {"emoji": "📜", "icon": "shield-security", "thiings": THIINGS_ASSETS["shield"], "color": "text-purple-600 bg-purple-50 border-purple-200"}
    elif item_type == "CLI":
        return {"emoji": "💻", "icon": "command", "thiings": THIINGS_ASSETS["code"], "color": "text-sky-600 bg-sky-50 border-sky-200"}

    return {"emoji": "🧩", "icon": "category", "thiings": THIINGS_ASSETS["puzzle"], "color": "text-slate-600 bg-slate-100 border-slate-200"}
    """Assigns a specialized semantic emoji and Iconsax icon to each skill/MCP/CLI."""
    n = name.lower()
    
    # Creator & Video Skills
    if "creator-intelligence" in n:
        return {"emoji": "🧠", "icon": "cpu-charge", "color": "text-purple-600 bg-purple-50 border-purple-200"}
    elif "trend-radar" in n:
        return {"emoji": "📡", "icon": "radar-2", "color": "text-blue-600 bg-blue-50 border-blue-200"}
    elif "audience-positioning" in n:
        return {"emoji": "🎯", "icon": "target", "color": "text-rose-600 bg-rose-50 border-rose-200"}
    elif "topic-discovery" in n:
        return {"emoji": "💡", "icon": "lamp-on", "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif "idea-development" in n:
        return {"emoji": "🌱", "icon": "magic-star", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}
    elif "hook-engineering" in n:
        return {"emoji": "🪝", "icon": "flash-circle", "color": "text-red-600 bg-red-50 border-red-200"}
    elif "scriptwriting" in n:
        return {"emoji": "✍️", "icon": "edit-2", "color": "text-indigo-600 bg-indigo-50 border-indigo-200"}
    elif "visual-storyboarding" in n:
        return {"emoji": "🎬", "icon": "video-play", "color": "text-teal-600 bg-teal-50 border-teal-200"}
    elif "retention-editing" in n:
        return {"emoji": "✂️", "icon": "scissor", "color": "text-orange-600 bg-orange-50 border-orange-200"}
    elif "platform-packaging" in n:
        return {"emoji": "📦", "icon": "box-1", "color": "text-sky-600 bg-sky-50 border-sky-200"}
    elif "publishing-operations" in n:
        return {"emoji": "🚀", "icon": "send-2", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}
    elif "performance-learning" in n:
        return {"emoji": "📈", "icon": "chart-2", "color": "text-blue-600 bg-blue-50 border-blue-200"}
    elif "youtube-thumbnail" in n:
        return {"emoji": "🖼️", "icon": "gallery-edit", "color": "text-red-600 bg-red-50 border-red-200"}
    elif "carousel-craft" in n or "ig-carousel" in n or "carousel" in n:
        return {"emoji": "📑", "icon": "slider-vertical", "color": "text-fuchsia-600 bg-fuchsia-50 border-fuchsia-200"}
    elif "client-acquisition" in n:
        return {"emoji": "💼", "icon": "dollar-circle", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}
    elif "sound-design" in n or "soundcloud" in n:
        return {"emoji": "🎵", "icon": "music-note", "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif "watch-video" in n or "video-vision" in n or "analyze-edit" in n:
        return {"emoji": "👁️", "icon": "eye", "color": "text-violet-600 bg-violet-50 border-violet-200"}
    elif "vidiq" in n:
        return {"emoji": "📊", "icon": "chart-square", "color": "text-red-600 bg-red-50 border-red-200"}

    # Instagram Suite
    elif "ig-reel" in n:
        return {"emoji": "📱", "icon": "video-square", "color": "text-pink-600 bg-pink-50 border-pink-200"}
    elif "ig-story" in n:
        return {"emoji": "⏱️", "icon": "clock", "color": "text-rose-600 bg-rose-50 border-rose-200"}
    elif "ig-viral" in n:
        return {"emoji": "🔥", "icon": "trend-up", "color": "text-orange-600 bg-orange-50 border-orange-200"}
    elif "ig-profile" in n:
        return {"emoji": "👤", "icon": "profile-circle", "color": "text-indigo-600 bg-indigo-50 border-indigo-200"}
    elif "ig-caption" in n:
        return {"emoji": "💬", "icon": "message-text-1", "color": "text-cyan-600 bg-cyan-50 border-cyan-200"}
    elif "ig-reply" in n or "ig-comment" in n:
        return {"emoji": "💬", "icon": "messages-3", "color": "text-teal-600 bg-teal-50 border-teal-200"}
    elif "ig-dm" in n:
        return {"emoji": "✉️", "icon": "direct-normal", "color": "text-blue-600 bg-blue-50 border-blue-200"}
    elif "ig-human" in n:
        return {"emoji": "🛡️", "icon": "shield-tick", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}
    elif "ig-plan" in n:
        return {"emoji": "🗓️", "icon": "calendar-tick", "color": "text-purple-600 bg-purple-50 border-purple-200"}
    elif "ig-audit" in n:
        return {"emoji": "🔍", "icon": "scan-barcode", "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif "ig-repurpose" in n:
        return {"emoji": "🔄", "icon": "refresh-circle", "color": "text-indigo-600 bg-indigo-50 border-indigo-200"}
    elif "ig-creator-expert" in n:
        return {"emoji": "👑", "icon": "crown-1", "color": "text-amber-600 bg-amber-50 border-amber-200"}

    # UI / Design / Figma
    elif "figma" in n:
        return {"emoji": "🎨", "icon": "bezier", "color": "text-purple-600 bg-purple-50 border-purple-200"}
    elif "make-interfaces-feel-better" in n or "vibe-component" in n:
        return {"emoji": "✨", "icon": "magicpen", "color": "text-fuchsia-600 bg-fuchsia-50 border-fuchsia-200"}
    elif "vibe-production-hardening" in n:
        return {"emoji": "🔒", "icon": "security-safe", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}

    # SEO & Search
    elif "seo" in n or "search-console" in n:
        return {"emoji": "🌐", "icon": "global-search", "color": "text-blue-600 bg-blue-50 border-blue-200"}

    # Persian & Localization
    elif "persian-writing" in n or "persian-rtl" in n or "persian" in n:
        return {"emoji": "🇮🇷", "icon": "translate", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}

    # MCP Servers
    elif "hooshang" in n:
        return {"emoji": "🤖", "icon": "robot", "color": "text-indigo-600 bg-indigo-50 border-indigo-200"}
    elif "mem0" in n:
        return {"emoji": "🧠", "icon": "hierarchy-3", "color": "text-purple-600 bg-purple-50 border-purple-200"}
    elif "notion" in n:
        return {"emoji": "📝", "icon": "document-text", "color": "text-slate-800 bg-slate-100 border-slate-200"}
    elif "posthog" in n:
        return {"emoji": "🦔", "icon": "data-2", "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif "pinterest" in n:
        return {"emoji": "📌", "icon": "bookmark", "color": "text-red-600 bg-red-50 border-red-200"}

    # CLIs & Tools
    elif "claude" in n:
        return {"emoji": "🤖", "icon": "command", "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif "agy" in n or "antigravity" in n:
        return {"emoji": "🚀", "icon": "flash-1", "color": "text-blue-600 bg-blue-50 border-blue-200"}
    elif "uv" in n or "uvx" in n:
        return {"emoji": "⚡", "icon": "electricity", "color": "text-violet-600 bg-violet-50 border-violet-200"}
    elif "pnpm" in n or "npm" in n or "node" in n:
        return {"emoji": "📦", "icon": "box-add", "color": "text-red-600 bg-red-50 border-red-200"}
    elif "python" in n:
        return {"emoji": "🐍", "icon": "code-1", "color": "text-sky-600 bg-sky-50 border-sky-200"}
    elif "git" in n:
        return {"emoji": "🌿", "icon": "git-branch", "color": "text-orange-600 bg-orange-50 border-orange-200"}
    elif "code" in n:
        return {"emoji": "💻", "icon": "code-circle", "color": "text-blue-600 bg-blue-50 border-blue-200"}

    # Fallback by Item Type
    if item_type == "MCP Server":
        return {"emoji": "🔌", "icon": "server", "color": "text-emerald-600 bg-emerald-50 border-emerald-200"}
    elif item_type == "Command":
        return {"emoji": "⚡", "icon": "slash", "color": "text-amber-600 bg-amber-50 border-amber-200"}
    elif item_type == "Rule":
        return {"emoji": "📜", "icon": "shield-security", "color": "text-purple-600 bg-purple-50 border-purple-200"}
    elif item_type == "CLI":
        return {"emoji": "💻", "icon": "command", "color": "text-sky-600 bg-sky-50 border-sky-200"}

    return {"emoji": "🧩", "icon": "category", "color": "text-slate-600 bg-slate-100 border-slate-200"}
    """Calculates size, file count, and line count for depth/richness scoring."""
    total_bytes = 0
    file_count = 0
    line_count = 0
    try:
        for f in folder_path.rglob("*"):
            if f.is_file():
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
    
    # Richness score formula: byte size + weighted bonuses for files and lines
    score = total_bytes + (file_count * 1500) + (line_count * 8)
    return {
        "size_bytes": total_bytes,
        "size_kb": round(total_bytes / 1024, 1),
        "file_count": file_count,
        "line_count": line_count,
        "richness_score": score
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
    """Scans and integrates the local Creator OS installation into the dashboard."""
    creator_os_path = find_creator_os_dir()
    items = []
    if creator_os_path.exists():
        stats = calculate_folder_stats(creator_os_path)
        items.append({
            "id": "creator-os-core",
            "name": "Creator OS (Master Suite)",
            "platform": "Creator OS",
            "type": "Suite",
            "origin": "user",
            "is_user_created": True,
            "suite": "Creator OS",
            "emoji": "👑",
            "icon": "crown-1",
            "color": "text-amber-600 bg-amber-50 border-amber-300",
            "description": "سیستم جامع و بومی مهندسی محتوا برای حسام طاهری شامل ۱۴ اسکیل اختصاصی، پایگاه دانش (Knowledge Dossiers)، دیتابیس هوک‌ها، و اسکریپت‌های اتوماسیون.",
            "path": str(creator_os_path),
            "last_modified": get_file_time(creator_os_path),
            "size_kb": stats["size_kb"],
            "file_count": stats["file_count"],
            "line_count": stats["line_count"],
            "richness_score": stats["richness_score"] + 1000000
        })

        # Scan sub-modules of Creator OS
        sub_dirs = ["knowledge", "research", "evaluations", "schemas", "scripts", "templates", "docs"]
        for sub in sub_dirs:
            sp = creator_os_path / sub
            if sp.exists():
                sstats = calculate_folder_stats(sp)
                items.append({
                    "id": f"creator-os-{sub}",
                    "name": f"Creator OS / {sub.capitalize()}",
                    "platform": "Creator OS",
                    "type": "Module",
                    "origin": "user",
                    "is_user_created": True,
                    "suite": "Creator OS",
                    "emoji": "📂",
                    "icon": "folder-favorite",
                    "color": "text-amber-600 bg-amber-50 border-amber-200",
                    "description": f"ماژول اختصاصی {sub.capitalize()} در سیستم Creator OS شامل فایل‌های مرجع، تمپلیت‌ها و کدهای اعتبارسنجی.",
                    "path": str(sp),
                    "last_modified": get_file_time(sp),
                    "size_kb": sstats["size_kb"],
                    "file_count": sstats["file_count"],
                    "line_count": sstats["line_count"],
                    "richness_score": sstats["richness_score"]
                })
    return items

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

    # Mark skills that belong to Creator OS Suite
    creator_os_prefixes = ["01-", "02-", "03-", "04-", "05-", "06-", "07-", "08-", "09-", "10-", "11-", "12-", "13-", "14-", "15-"]
    for s in agy_skills:
        if any(s["name"].startswith(p) for p in creator_os_prefixes):
            s["suite"] = "Creator OS"
    
    for s in claude_skills:
        if any(s["name"].startswith(p) for p in creator_os_prefixes):
            s["suite"] = "Creator OS"

    creator_os_items = scan_creator_os()

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
            "user_created_total_count": user_created_total_count + len(creator_os_items)
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
        }
    }

if __name__ == "__main__":
    data = get_complete_ecosystem()
    print(json.dumps(data, indent=2, ensure_ascii=False))
