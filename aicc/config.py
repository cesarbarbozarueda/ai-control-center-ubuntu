"""Per-user settings stored in ~/.config/ai-control-center/config.json."""
import copy
import json
import os
import threading
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "ai-control-center"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_UI = {
    "theme": "auto",          # auto | light | dark
    "accent": "#5de4ef",
    "font_size": 14,
    "radius": 15,
    "density": "normal",      # compact | normal | comfortable
    "columns": "auto",        # auto | 1 | 2 | 3
    "gradient": True,
    "animations": True,
    "refresh_seconds": 5,
    "auto_update_check": True,
}

DEFAULT_CONFIG = {
    "version": 2,
    # service id -> location dict produced by detection or set manually
    "services": {},
    # user-added AI tools: id -> {label, description, port, command}
    "custom": {},
    "ui": DEFAULT_UI,
}

_lock = threading.RLock()


def load():
    with _lock:
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        try:
            with open(str(CONFIG_FILE), encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if isinstance(data.get("services"), dict):
                    cfg["services"] = data["services"]
                if isinstance(data.get("custom"), dict):
                    cfg["custom"] = data["custom"]
                if isinstance(data.get("ui"), dict):
                    cfg["ui"].update(data["ui"])
        except (OSError, ValueError):
            pass
        return cfg


def save(cfg):
    with _lock:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_FILE.with_suffix(".tmp")
        with open(str(tmp), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(str(tmp), str(CONFIG_FILE))


def update(fn):
    """Load, apply fn(cfg) and save atomically. Returns the new config."""
    with _lock:
        cfg = load()
        fn(cfg)
        save(cfg)
        return cfg


def clean_ui(values):
    """Validate UI settings coming from the browser."""
    out = {}
    if not isinstance(values, dict):
        return out
    if values.get("theme") in ("auto", "light", "dark"):
        out["theme"] = values["theme"]
    accent = values.get("accent")
    if isinstance(accent, str) and len(accent) == 7 and accent[0] == "#":
        try:
            int(accent[1:], 16)
            out["accent"] = accent.lower()
        except ValueError:
            pass
    for key, lo, hi in (("font_size", 12, 20), ("radius", 0, 28), ("refresh_seconds", 2, 60)):
        try:
            v = int(values.get(key))
            if lo <= v <= hi:
                out[key] = v
        except (TypeError, ValueError):
            pass
    if values.get("density") in ("compact", "normal", "comfortable"):
        out["density"] = values["density"]
    if str(values.get("columns")) in ("auto", "1", "2", "3"):
        out["columns"] = str(values["columns"])
    for key in ("gradient", "animations", "auto_update_check"):
        if isinstance(values.get(key), bool):
            out[key] = values[key]
    return out
