# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""DeepSeek agent — calls the DeepSeek API via openai SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openai import OpenAI

from .base import Event, EventType, AGENT_DEEPSEEK
from .openai_agent import OpenAIAgent

if TYPE_CHECKING:
    from .mcp_manager import MCPManager

# Rough pricing per 1M tokens (DeepSeek V3)
INPUT_COST_PER_M = 0.27
OUTPUT_COST_PER_M = 1.10


class DeepSeekAgent(OpenAIAgent):
    name = AGENT_DEEPSEEK

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1",
                 model: str = "deepseek-chat",
                 mcp_manager: MCPManager | None = None):
        client = OpenAI(api_key=api_key, base_url=base_url)
        super().__init__(client, model, mcp_manager)

    def _configure_stream_kwargs(self, kwargs: dict):
        kwargs["stream_options"] = {"include_usage": True}

    def _compute_cost(self, prompt_tokens: int,
                      completion_tokens: int) -> float:
        return (prompt_tokens * INPUT_COST_PER_M
                + completion_tokens * OUTPUT_COST_PER_M) / 1_000_000

    def _handle_delta_extras(self, delta, callback: callable):
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            callback(Event(EventType.TOKEN, self.name, text=reasoning))
