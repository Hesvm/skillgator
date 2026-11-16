# Skillgator Architecture

## Overview
Skillgator is built as an ultra-lightweight, zero-dependency local agent cockpit.

```
┌─────────────────┐       SSE Stream       ┌──────────────────┐
│  scanner.py     │ ────────────────────>  │  browser UI      │
│  (Watchdog loop)│ <────────────────────  │  (Vanilla JS)    │
└─────────────────┘       REST API         └──────────────────┘
```

### Components
1. **Scanner Engine (`scanner.py`)**: Traverses standard local config directories (`~/.gemini`, `~/.claude`, `~/.cursor`).
2. **HTTP & SSE Server (`server.py`)**: Uses Python's built-in `http.server` to serve static assets and push live changes.
3. **Floating Canvas UI (`index.html`)**: Single-page application styled with Tailwind CSS, supporting both LTR and RTL.
