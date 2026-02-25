# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Settings loader — pulls API keys and paths from env, keyring, prism-relay config, and defaults."""

import json
import os
import platform
import shutil
from pathlib import Path
from dataclasses import dataclass, field

try:
    import keyring as _keyring
except ImportError:
    _keyring = None


def _config_base() -> Path:
    """Return the platform-appropriate config directory."""
    if platform.system() == "Windows":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return Path.home() / ".config"


_CONFIG = _config_base()
PRISM_SETTINGS = _CONFIG / "prism-relay" / "settings.json"
APP_SETTINGS = _CONFIG / "agent-loop" / "settings.json"
KEYRING_SERVICE = "kitae-agent-loop"


def _probe_lmstudio(base_url: str, timeout: float = 2.0) -> bool:
    """Return True if LM Studio is reachable and has a model loaded."""
    import urllib.request
    import urllib.error
    # base_url is e.g. "http://localhost:1234/v1" — hit /models
    url = base_url.rstrip("/") + "/models"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return bool(data.get("data"))
    except Exception:
        return False


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _get_secret(key: str) -> str:
    """Retrieve a secret from the system keyring."""
    if _keyring is None:
        return ""
    try:
        return _keyring.get_password(KEYRING_SERVICE, key) or ""
    except Exception:
        return ""


def _set_secret(key: str, value: str):
    """Store a secret in the system keyring."""
    if _keyring is None:
        return
    try:
        if value:
            _keyring.set_password(KEYRING_SERVICE, key, value)
        else:
            try:
                _keyring.delete_password(KEYRING_SERVICE, key)
            except _keyring.errors.PasswordDeleteError:
                pass
    except Exception:
        pass


def _migrate_key_from_json():
    """One-time migration: move deepseek_api_key from prism settings.json to keyring."""
    if _keyring is None:
        return
    prism = _load_json(PRISM_SETTINGS)
    plaintext_key = prism.get("deepseek_api_key", "")
    if not plaintext_key:
        return
    # Already in keyring? Skip.
    existing = _get_secret("deepseek_api_key")
    if existing:
        # Key is in keyring — just remove from JSON
        pass
    else:
        _set_secret("deepseek_api_key", plaintext_key)
    # Remove plaintext key from JSON
    del prism["deepseek_api_key"]
    PRISM_SETTINGS.write_text(json.dumps(prism, indent=2))


@dataclass
class Settings:
    # API keys
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # LM Studio (local)
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_model: str = ""

    # CLI binary paths
    claude_bin: str = ""
    gemini_bin: str = ""

    # Defaults
    max_iterations: int = 10
    max_cost_usd: float = 0.0
    max_duration_secs: int = 0
    completion_signal: str = "TASK_COMPLETE"

    # MCP servers config: {name: {command, args, env}}
    mcp_servers: dict = field(default_factory=dict)

    # Agent availability (computed)
    claude_available: bool = False
    gemini_available: bool = False
    deepseek_available: bool = False
    lmstudio_available: bool = False

    def detect(self):
        """Load keys from env/keyring/config files and detect available agents."""
        # One-time migration from plaintext JSON to keyring
        _migrate_key_from_json()

        prism = _load_json(PRISM_SETTINGS)

        # DeepSeek — priority: env var → keyring → (JSON removed by migration)
        self.deepseek_api_key = (
            os.environ.get("DEEPSEEK_API_KEY")
            or _get_secret("deepseek_api_key")
        )
        self.deepseek_model = prism.get("deepseek_model", self.deepseek_model)
        self.deepseek_base_url = prism.get("deepseek_base_url", self.deepseek_base_url)

        # LM Studio
        self.lmstudio_base_url = prism.get("lmstudio_base_url", self.lmstudio_base_url)
        self.lmstudio_model = prism.get("lmstudio_model", self.lmstudio_model)

        # CLI binaries
        self.claude_bin = shutil.which("claude") or ""
        self.gemini_bin = shutil.which("gemini") or ""

        # Availability
        self.claude_available = bool(self.claude_bin)
        self.gemini_available = bool(self.gemini_bin)
        self.deepseek_available = bool(self.deepseek_api_key)
        self.lmstudio_available = _probe_lmstudio(self.lmstudio_base_url)

        # Load saved app prefs
        app = _load_json(APP_SETTINGS)
        self.max_iterations = app.get("max_iterations", self.max_iterations)
        self.max_cost_usd = app.get("max_cost_usd", self.max_cost_usd)
        self.max_duration_secs = app.get("max_duration_secs", self.max_duration_secs)
        self.mcp_servers = app.get("mcpServers", {})

    def save(self):
        """Persist user prefs."""
        APP_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "max_iterations": self.max_iterations,
            "max_cost_usd": self.max_cost_usd,
            "max_duration_secs": self.max_duration_secs,
        }
        APP_SETTINGS.write_text(json.dumps(data, indent=2))


def load() -> Settings:
    s = Settings()
    s.detect()
    return s
