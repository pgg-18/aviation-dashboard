"""Small shared persistence helpers: atomic JSON writes, safe reads.
Used by both store.py (dashboard cards + charts) and airport_store.py (airport table).
"""

from __future__ import annotations
import json
import os
import tempfile


def read_json(path: str):
    """Return the parsed JSON at path, or None if it doesn't exist / is unreadable."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def atomic_write_json(path: str, obj) -> None:
    """Write JSON atomically (temp file + rename) so a crash mid-write can't corrupt
    the saved data, and auto-create the target directory if needed."""
    target_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(target_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)  # atomic on the same filesystem
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
