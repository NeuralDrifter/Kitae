<div align="center">

<img src="splash.png" width="400" />

# Kitae

Multi-agent orchestrator for AI coding assistants.
Forge tasks across Claude Code, Gemini CLI, DeepSeek, and LM Studio.

<img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/CustomTkinter-0d1117?style=flat-square" />
<img src="https://img.shields.io/badge/MCP-0d1117?style=flat-square&logo=anthropic&logoColor=white" />
<img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" />

</div>

---

## What It Does

Kitae runs multiple AI agents on the same task in a continuous loop. Each agent works in sequence or in parallel, building on previous iterations until the task is complete. A flat-file memory system (`AGENT_MEMORY.md`) tracks progress across iterations so each agent knows what was already done.

## Agents

| Agent | Type | How It Connects |
|-------|------|-----------------|
| **Claude Code** | CLI | `claude` binary, streaming JSON |
| **Gemini CLI** | CLI | `gemini` binary, streaming JSON |
| **DeepSeek** | API | OpenAI-compatible, with MCP tools and shell execution |
| **LM Studio** | Local API | Auto-detects loaded model, MCP tools and shell execution |

API-only agents (DeepSeek, LM Studio) get filesystem access through a shell bridge that parses code blocks from their responses and executes them in the project directory.

## Modes

| Mode | Behavior |
|------|----------|
| **Single** | One agent loops alone, refining each pass |
| **Round-Robin** | Agents rotate A -> B -> C -> A, each builds on previous work |
| **Parallel** | All agents work simultaneously on separate copies of the project |
| **Reviewer** | First agent generates, second agent critiques |

Parallel mode creates timestamped backups before copying the project to each agent's workspace. Compare results by diffing agent folders.

## Installation

```bash
git clone https://github.com/NeuralDrifter/Kitae.git
cd Kitae
pip install -r requirements.txt
```

Dependencies: `customtkinter`, `openai`, `mcp`, `keyring`

## Setup

**Claude Code and Gemini CLI** are detected automatically if they're on your PATH.

**DeepSeek API key** — set via environment variable or the system keyring:
```bash
export DEEPSEEK_API_KEY="sk-..."
```
On first run, if a key exists in `~/.config/prism-relay/settings.json`, it's automatically migrated to the system keyring and removed from the file.

**LM Studio** — start LM Studio with a model loaded. Kitae auto-detects it at `localhost:1234`.

**MCP Servers** — configure in `~/.config/agent-loop/settings.json`:
```json
{
  "mcpServers": {
    "my-server": {
      "command": "python3",
      "args": ["/path/to/server.py"],
      "env": {}
    }
  }
}
```
MCP tools are exposed to DeepSeek and LM Studio agents in OpenAI function-calling format.

## Usage

```bash
python main.py
```

1. Select which agents to use (checkboxes, green dot = available)
2. Choose a mode
3. Write or load a prompt
4. Optionally set a working directory
5. Set limits (iterations, cost, duration) or leave at defaults
6. Click **FORGE** to start, **QUENCH** to stop

Output streams in real-time to per-agent tabs plus an aggregated "All" tab.

## Limits

| Limit | Default | Description |
|-------|---------|-------------|
| Iterations | 10 | Max loop cycles before stopping |
| Cost | $0 (unlimited) | Cumulative API spend cap |
| Duration | 0 (unlimited) | Wall-clock time in minutes |
| Completion signal | `TASK_COMPLETE` | Agent writes this to stop the loop |

## How the Loop Works

1. **Build prompt** — original task + iteration context + memory instructions
2. **Execute** — run the current agent(s) according to the selected mode
3. **Stream output** — tokens appear in real-time in the GUI
4. **Check limits** — stop if iterations, cost, or duration exceeded
5. **Repeat** — next iteration picks up where the last left off

Each agent is instructed to read and append to `AGENT_MEMORY.md` in the working directory, recording what was done, what files were modified, and what's left to do.

## Project Structure

```
Kitae/
├── main.py                  # Entry point (splash -> app)
├── config.py                # Settings loader (env, keyring, JSON)
├── requirements.txt
├── splash.png
├── agents/
│   ├── base.py              # AgentBase interface + event types
│   ├── claude.py            # Claude Code CLI agent
│   ├── gemini.py            # Gemini CLI agent
│   ├── deepseek.py          # DeepSeek API agent
│   ├── lmstudio.py          # LM Studio local agent
│   ├── file_bridge.py       # Shell execution for API agents
│   └── mcp_manager.py       # MCP server connections + tool routing
├── gui/
│   ├── app.py               # Main application window
│   ├── config_panel.py      # Left sidebar (agents, mode, prompt, limits)
│   ├── output_panel.py      # Tabbed output display
│   ├── splash.py            # Splash screen
│   ├── status_bar.py        # Bottom metrics bar
│   └── theme.py             # Kitae color palette
└── orchestrator/
    ├── loop.py              # Background loop manager
    ├── modes.py             # Single / round-robin / parallel / reviewer
    └── context.py           # Iteration context + memory instructions
```

## Cross-Platform

Kitae runs on Linux and Windows:
- Config files: `~/.config/` on Linux, `%APPDATA%` on Windows
- Shell bridge: bash on Linux, PowerShell on Windows
- Process management: cross-platform termination
- API keys: stored in system keyring (GNOME Keyring / Windows Credential Manager)

## License

[MIT](LICENSE) — Copyright (c) 2026 Michael Burgus
