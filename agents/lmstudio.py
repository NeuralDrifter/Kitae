# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""LM Studio agent — local inference via OpenAI-compatible API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openai import OpenAI

from .base import AGENT_LMSTUDIO
from .openai_agent import OpenAIAgent

if TYPE_CHECKING:
    from .mcp_manager import MCPManager


def detect_model(base_url: str, timeout: float = 3.0) -> str:
    """Ping LM Studio /models endpoint and return the first loaded model ID.

    Returns empty string if the server is unreachable or has no models.
    """
    try:
        client = OpenAI(api_key="lm-studio", base_url=base_url, timeout=timeout)
        models = client.models.list()
        for m in models.data:
            return m.id
    except Exception:
        pass
    return ""


class LMStudioAgent(OpenAIAgent):
    name = AGENT_LMSTUDIO

    def __init__(self, base_url: str = "http://localhost:1234/v1",
                 model: str = "",
                 mcp_manager: MCPManager | None = None):
        client = OpenAI(api_key="lm-studio", base_url=base_url)
        super().__init__(client, model or detect_model(base_url), mcp_manager)
