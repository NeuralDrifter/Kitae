# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Base class for agents that use the OpenAI SDK (DeepSeek, LM Studio, etc.)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openai import OpenAI

from .base import AgentBase, Event, EventType
from .file_bridge import (
    SYSTEM_INSTRUCTION,
    build_file_context,
    extract_bash_blocks,
    execute_bash_blocks,
)

if TYPE_CHECKING:
    from .mcp_manager import MCPManager

MAX_TOOL_ROUNDS = 10


class OpenAIAgent(AgentBase):
    """Base for agents that use the OpenAI SDK.

    Subclasses can override:
        _configure_stream_kwargs(kwargs) — add stream_options, etc.
        _compute_cost(prompt_tokens, completion_tokens) — return USD cost
        _handle_delta_extras(delta, callback) — handle model-specific delta
            fields (e.g. reasoning_content)
    """

    def __init__(self, client: OpenAI, model: str,
                 mcp_manager: MCPManager | None = None):
        super().__init__()
        self._client = client
        self._model = model
        self._mcp = mcp_manager

    def run(self, prompt: str, callback: callable, cwd: str = "") -> float:
        self.reset()
        cost = 0.0

        if not self._model:
            callback(Event(EventType.ERROR, self.name,
                           text="No model configured"))
            return 0.0

        # Build messages
        messages: list[dict] = []
        if cwd:
            messages.append({"role": "system", "content": SYSTEM_INSTRUCTION})
            file_ctx = build_file_context(cwd)
            if file_ctx:
                prompt = file_ctx + "\n---\n\n" + prompt

        messages.append({"role": "user", "content": prompt})

        # MCP tools in OpenAI format (if available)
        tools = self._mcp.get_openai_tools() if self._mcp else []

        # Tool-calling loop
        content_chunks: list[str] = []

        for round_idx in range(MAX_TOOL_ROUNDS):
            if self.stopped:
                break

            # On last allowed round, omit tools to force a text response
            send_tools = tools if (tools and round_idx < MAX_TOOL_ROUNDS - 1) else None

            text, tool_calls, round_cost = self._stream_completion(
                messages, send_tools, callback,
            )
            cost += round_cost

            if text:
                content_chunks.append(text)

            if not tool_calls:
                break

            # Append assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": text or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        },
                    }
                    for tc in tool_calls
                ],
            })

            # Execute each tool call and append results
            for tc in tool_calls:
                callback(Event(EventType.TOKEN, self.name,
                               text=f"\n[mcp] Calling tool: {tc['name']}\n"))
                try:
                    args = json.loads(tc["arguments"])
                    result = self._mcp.call_tool(tc["name"], args)
                except Exception as exc:
                    result = f"[mcp] Error: {exc}"

                display = result[:1500]
                if len(result) > 1500:
                    display += "\n... (truncated)"
                callback(Event(EventType.TOKEN, self.name,
                               text=f"[mcp] Result: {display}\n"))

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

        # Bash bridge: extract and execute bash blocks
        if cwd and content_chunks:
            full_output = "".join(content_chunks)
            blocks = extract_bash_blocks(full_output)
            if blocks:
                callback(Event(EventType.TOKEN, self.name,
                               text=f"\n\n[{self.name}] Executing {len(blocks)} bash block(s)...\n"))

                results = execute_bash_blocks(blocks, cwd)
                for preview, output, rc in results:
                    status = "ok" if rc == 0 else f"exit {rc}"
                    msg = f"$ {preview} [{status}]\n"
                    if output:
                        display = output[:1000]
                        if len(output) > 1000:
                            display += "\n... (truncated)"
                        msg += display + "\n"
                    callback(Event(EventType.TOKEN, self.name, text=msg))

        callback(Event(EventType.COST, self.name, cost=cost))
        return cost

    # ── Streaming helper ──────────────────────────────────────────────────

    def _stream_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        callback: callable,
    ) -> tuple[str, list[dict], float]:
        """Stream one chat completion. Returns (text, tool_calls, cost).

        tool_calls is a list of dicts: {id, name, arguments (json string)}.
        """
        content_parts: list[str] = []
        tc_accum: dict[int, dict] = {}
        cost = 0.0

        kwargs = dict(
            model=self._model,
            messages=messages,
            stream=True,
        )
        self._configure_stream_kwargs(kwargs)
        if tools:
            kwargs["tools"] = tools

        try:
            stream = self._client.chat.completions.create(**kwargs)

            for chunk in stream:
                if self.stopped:
                    break

                if chunk.choices:
                    choice = chunk.choices[0]
                    delta = choice.delta
                    if delta:
                        self._handle_delta_extras(delta, callback)

                        if delta.content:
                            callback(Event(EventType.TOKEN, self.name,
                                           text=delta.content))
                            content_parts.append(delta.content)

                        if delta.tool_calls:
                            for tc_delta in delta.tool_calls:
                                idx = tc_delta.index
                                if idx not in tc_accum:
                                    tc_accum[idx] = {
                                        "id": "", "name": "", "arguments": "",
                                    }
                                if tc_delta.id:
                                    tc_accum[idx]["id"] = tc_delta.id
                                if tc_delta.function:
                                    if tc_delta.function.name:
                                        tc_accum[idx]["name"] = tc_delta.function.name
                                    if tc_delta.function.arguments:
                                        tc_accum[idx]["arguments"] += tc_delta.function.arguments

                # Usage info comes in the final chunk
                if chunk.usage:
                    inp = chunk.usage.prompt_tokens or 0
                    out = chunk.usage.completion_tokens or 0
                    cost = self._compute_cost(inp, out)

        except Exception as e:
            callback(Event(EventType.ERROR, self.name, text=str(e)))

        text = "".join(content_parts)
        tool_calls = [tc_accum[i] for i in sorted(tc_accum)] if tc_accum else []
        return text, tool_calls, cost

    # ── Extension points ──────────────────────────────────────────────────

    def _configure_stream_kwargs(self, kwargs: dict):
        """Override to add stream_options or other kwargs."""
        pass

    def _compute_cost(self, prompt_tokens: int,
                      completion_tokens: int) -> float:
        """Override with per-model pricing. Default: 0.0 (free/local)."""
        return 0.0

    def _handle_delta_extras(self, delta, callback: callable):
        """Override to handle model-specific delta fields."""
        pass
