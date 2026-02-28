# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

from .base import (
    AgentBase, Event, EventType,
    AGENT_CLAUDE, AGENT_GEMINI, AGENT_DEEPSEEK, AGENT_LMSTUDIO,
    SOURCE_LOOP,
)
from .claude import ClaudeAgent
from .gemini import GeminiAgent
from .deepseek import DeepSeekAgent
from .lmstudio import LMStudioAgent
from .mcp_manager import MCPManager

# Data-driven agent registry — maps agent name to its class, settings
# availability attribute, and factory function.
AGENT_REGISTRY = {
    AGENT_CLAUDE: {
        "class": ClaudeAgent,
        "available_attr": "claude_available",
        "label": "Claude Code",
        "factory": lambda s, mcp: ClaudeAgent(s.claude_bin),
    },
    AGENT_GEMINI: {
        "class": GeminiAgent,
        "available_attr": "gemini_available",
        "label": "Gemini CLI",
        "factory": lambda s, mcp: GeminiAgent(s.gemini_bin),
    },
    AGENT_DEEPSEEK: {
        "class": DeepSeekAgent,
        "available_attr": "deepseek_available",
        "label": "DeepSeek API",
        "factory": lambda s, mcp: DeepSeekAgent(
            api_key=s.deepseek_api_key,
            base_url=s.deepseek_base_url,
            model=s.deepseek_model,
            mcp_manager=mcp,
        ),
    },
    AGENT_LMSTUDIO: {
        "class": LMStudioAgent,
        "available_attr": "lmstudio_available",
        "label": "LM Studio",
        "factory": lambda s, mcp: LMStudioAgent(
            base_url=s.lmstudio_base_url,
            model=s.lmstudio_model,
            mcp_manager=mcp,
        ),
    },
}
