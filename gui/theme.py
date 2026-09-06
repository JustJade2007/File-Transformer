"""
Theme definitions for File-Transformer.
Supports: Cyber Dark, Minimalist Slate, Windows 11 Native.
"""
import json
import os
from typing import Dict, Optional

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(APP_DIR, "config.json")

THEMES = {
    "Cyber Dark": {
        "ctk_appearance": "dark",
        "ctk_color_theme": "blue",
        # Custom extension palette
        "bg_primary": "#0d1117",
        "bg_secondary": "#161b22",
        "bg_card": "#1c2333",
        "bg_hover": "#21262d",
        "accent": "#58a6ff",
        "accent_hover": "#79c0ff",
        "accent_dim": "#1f3a5f",
        "text_primary": "#e6edf3",
        "text_secondary": "#8b949e",
        "text_muted": "#484f58",
        "border": "#30363d",
        "success": "#3fb950",
        "warning": "#d29922",
        "error": "#f85149",
        "progress_track": "#21262d",
        "dropzone_border": "#388bfd",
        "dropzone_bg": "#0f2040",
        "badge_done": "#0d4429",
        "badge_error": "#3d1a18",
        "badge_converting": "#1a2e4a",
    },
    "Minimalist Slate": {
        "ctk_appearance": "dark",
        "ctk_color_theme": "blue",
        "bg_primary": "#1a1a2e",
        "bg_secondary": "#16213e",
        "bg_card": "#1e2a45",
        "bg_hover": "#252f4a",
        "accent": "#a78bfa",
        "accent_hover": "#c4b5fd",
        "accent_dim": "#312e81",
        "text_primary": "#f1f5f9",
        "text_secondary": "#94a3b8",
        "text_muted": "#64748b",
        "border": "#334155",
        "success": "#4ade80",
        "warning": "#facc15",
        "error": "#f87171",
        "progress_track": "#1e293b",
        "dropzone_border": "#a78bfa",
        "dropzone_bg": "#1e1b4b",
        "badge_done": "#14532d",
        "badge_error": "#450a0a",
        "badge_converting": "#1e3a5f",
    },
    "Windows 11 Native": {
        "ctk_appearance": "system",
        "ctk_color_theme": "blue",
        "bg_primary": "#202020",
        "bg_secondary": "#2c2c2c",
        "bg_card": "#363636",
        "bg_hover": "#404040",
        "accent": "#0078d4",
        "accent_hover": "#106ebe",
        "accent_dim": "#003366",
        "text_primary": "#ffffff",
        "text_secondary": "#aaaaaa",
        "text_muted": "#6d6d6d",
        "border": "#3d3d3d",
        "success": "#107c10",
        "warning": "#797620",
        "error": "#a4262c",
        "progress_track": "#2c2c2c",
        "dropzone_border": "#0078d4",
        "dropzone_bg": "#002a4a",
        "badge_done": "#0a3d0a",
        "badge_error": "#4a1215",
        "badge_converting": "#003060",
    },
}

DEFAULT_THEME = "Cyber Dark"

# Runtime palette reference updated on theme switch
current: Dict = dict(THEMES[DEFAULT_THEME])
current_name: str = DEFAULT_THEME


def load_settings() -> Dict:
    """Load persisted settings from config.json."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_settings(settings: Dict):
    """Persist settings to config.json."""
    existing = load_settings()
    existing.update(settings)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    except Exception:
        pass


def apply_theme(name: str):
    """Switch the active theme palette. Call before CTk window creation or after."""
    global current, current_name
    theme = THEMES.get(name, THEMES[DEFAULT_THEME])
    current.clear()
    current.update(theme)
    current_name = name
    save_settings({"theme": name})


def get_saved_theme() -> str:
    s = load_settings()
    saved = s.get("theme", DEFAULT_THEME)
    return saved if saved in THEMES else DEFAULT_THEME


def c(key: str) -> str:
    """Shorthand to get a color from the current theme palette."""
    return current.get(key, "#ffffff")
