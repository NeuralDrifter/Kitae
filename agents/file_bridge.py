"""Shell bridge for API-only agents (DeepSeek, etc.).

Gives models that can't touch the filesystem the ability to execute shell
commands by parsing code blocks from their responses and running them.
Cross-platform: uses bash on Linux/macOS, powershell on Windows.
"""

import os
import platform
import re
import subprocess
from pathlib import Path
from typing import List, Tuple

IS_WINDOWS = platform.system() == "Windows"

# ── System instruction injected as the system message ───────────────────────

def _build_system_instruction() -> str:
    if IS_WINDOWS:
        return """\
You have access to the project's file tree and contents below.

You can execute commands by writing ```powershell blocks in your response.
Every ```powershell block will be executed in order after your response finishes.
You will NOT see the output until the next iteration, so write defensively.

Examples:

```powershell
Set-Content -Path hello.py -Value 'print("hello world")'
```

```powershell
python hello.py
```

```powershell
New-Item -ItemType Directory -Force -Path src
Set-Content -Path src/utils.py -Value @'
def add(a, b):
    return a + b
'@
```

Rules:
- Each ```powershell block is executed as a separate command in the project directory.
- Use Set-Content or Out-File to write files.
- You can run any command: python, pip, dir, mkdir, etc.
- Do NOT use interactive commands (notepad, etc.).
- If you don't need to run commands, just respond normally without code blocks.
"""
    else:
        return """\
You have access to the project's file tree and contents below.

You can execute commands by writing ```bash blocks in your response.
Every ```bash block will be executed in order after your response finishes.
You will NOT see the output until the next iteration, so write defensively.

Examples:

```bash
cat > hello.py << 'EOF'
print("hello world")
EOF
```

```bash
python hello.py
```

```bash
mkdir -p src && cat > src/utils.py << 'EOF'
def add(a, b):
    return a + b
EOF
```

Rules:
- Each ```bash block is executed as a separate shell command in the project directory.
- Use heredocs (cat > file << 'EOF' ... EOF) to write files.
- You can run any command: python, pip, ls, mkdir, etc.
- Do NOT use interactive commands (vim, nano, less, etc.).
- If you don't need to run commands, just respond normally without bash blocks.
"""


SYSTEM_INSTRUCTION = _build_system_instruction()

# ── Directories / extensions to skip when scanning ──────────────────────────

_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".agent-loop",
    ".venv", "venv", "env", ".mypy_cache", ".pytest_cache",
    "dist", "build", ".next", ".cache", "target",
}

_BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".mp3", ".mp4", ".wav", ".ogg", ".flac",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".o", ".a",
    ".whl", ".pyc", ".pyo",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".sqlite", ".db",
}


# ── Build file context ──────────────────────────────────────────────────────

def build_file_context(cwd: str, max_chars: int = 60_000) -> str:
    """Scan *cwd* and return a string with the file tree + contents.

    Stays under *max_chars* to leave room in the context window.
    """
    root = Path(cwd).resolve()
    if not root.is_dir():
        return ""

    tree_lines: List[str] = []
    file_entries: List[tuple] = []  # (rel_path, abs_path)

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped dirs in-place
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        rel_dir = Path(dirpath).relative_to(root)

        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            rel = rel_dir / fname
            if fpath.suffix.lower() in _BINARY_EXTS:
                continue
            tree_lines.append(str(rel))
            file_entries.append((str(rel), str(fpath)))

    # Build tree section
    parts: List[str] = ["## Project File Tree\n```"]
    parts.extend(tree_lines)
    parts.append("```\n")

    # Append file contents until budget exhausted
    parts.append("## File Contents\n")
    budget = max_chars - sum(len(p) for p in parts) - 200  # leave margin

    for rel, abspath in file_entries:
        try:
            content = Path(abspath).read_text(errors="replace")
        except OSError:
            continue

        header = f"\n### `{rel}`\n```\n"
        footer = "\n```\n"
        entry_len = len(header) + len(content) + len(footer)

        if entry_len > budget:
            # Try a truncated version
            trunc = budget - len(header) - len(footer) - 40
            if trunc > 200:
                content = content[:trunc] + "\n... (truncated)"
                entry_len = len(header) + len(content) + len(footer)
            else:
                break  # no room left at all

        parts.append(header)
        parts.append(content)
        parts.append(footer)
        budget -= entry_len

        if budget <= 0:
            break

    return "".join(parts)


# ── Extract and execute bash blocks ─────────────────────────────────────────

_SHELL_RE = re.compile(r"```(?:bash|powershell|cmd|shell)\s*\n(.*?)```", re.DOTALL)


def extract_bash_blocks(output: str) -> List[str]:
    """Parse shell code blocks from model output.

    Accepts ```bash, ```powershell, ```cmd, and ```shell blocks.
    Returns list of command strings in order.
    """
    return [m.group(1).strip() for m in _SHELL_RE.finditer(output)]


def execute_bash_blocks(blocks: List[str], cwd: str,
                        timeout: int = 120) -> List[Tuple[str, str, int]]:
    """Execute shell blocks sequentially in *cwd*.

    Uses powershell on Windows, bash on Linux/macOS.
    Returns list of (command_preview, output, returncode) tuples.
    """
    results: List[Tuple[str, str, int]] = []

    if IS_WINDOWS:
        shell_cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]
    else:
        shell_cmd = ["bash", "-c"]

    for cmd in blocks:
        # Short preview for display (first line, truncated)
        preview = cmd.split("\n")[0][:80]

        try:
            proc = subprocess.run(
                shell_cmd + [cmd],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            combined = ""
            if proc.stdout:
                combined += proc.stdout
            if proc.stderr:
                combined += proc.stderr
            results.append((preview, combined.strip(), proc.returncode))

        except subprocess.TimeoutExpired:
            results.append((preview, f"[timed out after {timeout}s]", -1))
        except Exception as e:
            results.append((preview, f"[error: {e}]", -1))

    return results
