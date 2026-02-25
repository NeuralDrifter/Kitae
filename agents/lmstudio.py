# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""LM Studio agent — local inference via OpenAI-compatible API."""

from __future__ import annotations

import json
import logging
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

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10


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


class LMStudioAgent(AgentBase):
    name = "lmstudio"

    def __init__(self, base_url: str = "http://localhost:1234/v1",
                 model: str = "",
                 mcp_manager: MCPManager | None = None):
        super().__init__()
        self._client = OpenAI(api_key="lm-studio", base_url=base_url)
        self._model = model or detect_model(base_url)
        self._mcp = mcp_manager

    def run(self, prompt: str, callback: callable, cwd: str = "") -> float:
        self.reset()

        if not self._model:
            callback(Event(EventType.ERROR, self.name,
                           text="No model loaded in LM Studio"))
            return 0.0

        # ── Build messages ────────────────────────────────────────────────
        messages: list[dict] = []
        if cwd:
            messages.append({"role": "system", "content": SYSTEM_INSTRUCTION})
            file_ctx = build_file_context(cwd)
            if file_ctx:
                prompt = file_ctx + "\n---\n\n" + prompt

        messages.append({"role": "user", "content": prompt})

        # ── MCP tools in OpenAI format (if available) ─────────────────────
        tools = self._mcp.get_openai_tools() if self._mcp else []

        # ── Tool-calling loop ─────────────────────────────────────────────
        content_chunks: list[str] = []

        for round_idx in range(MAX_TOOL_ROUNDS):
            if self.stopped:
                break

            # On last allowed round, omit tools to force a text response
            send_tools = tools if (tools and round_idx < MAX_TOOL_ROUNDS - 1) else None

            text, tool_calls = self._stream_completion(
                messages, send_tools, callback,
            )

            if text:
                content_chunks.append(text)

            # If no tool calls, we're done
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

        # ── Bash bridge: extract and execute bash blocks ──────────────────
        if cwd and content_chunks:
            full_output = "".join(content_chunks)
            blocks = extract_bash_blocks(full_output)
            if blocks:
                callback(Event(EventType.TOKEN, self.name,
                               text=f"\n\n[lmstudio] Executing {len(blocks)} bash block(s)...\n"))

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

        # Local inference — no cost
        callback(Event(EventType.COST, self.name, cost=0.0))
        return 0.0

    # ── Streaming helper ──────────────────────────────────────────────────

    def _stream_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        callback: callable,
    ) -> tuple[str, list[dict]]:
        """Stream one chat completion. Returns (text, tool_calls).

        tool_calls is a list of dicts: {id, name, arguments (json string)}.
        """
        content_parts: list[str] = []
        # Accumulate tool calls: index -> {id, name, arguments}
        tc_accum: dict[int, dict] = {}

        kwargs = dict(
            model=self._model,
            messages=messages,
            stream=True,
        )
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
                        # Content tokens
                        if delta.content:
                            callback(Event(EventType.TOKEN, self.name, text=delta.content))
                            content_parts.append(delta.content)

                        # Tool call deltas
                        if delta.tool_calls:
                            for tc_delta in delta.tool_calls:
                                idx = tc_delta.index
                                if idx not in tc_accum:
                                    tc_accum[idx] = {"id": "", "name": "", "arguments": ""}
                                if tc_delta.id:
                                    tc_accum[idx]["id"] = tc_delta.id
                                if tc_delta.function:
                                    if tc_delta.function.name:
                                        tc_accum[idx]["name"] = tc_delta.function.name
                                    if tc_delta.function.arguments:
                                        tc_accum[idx]["arguments"] += tc_delta.function.arguments

        except Exception as e:
            callback(Event(EventType.ERROR, self.name, text=str(e)))

        text = "".join(content_parts)
        tool_calls = [tc_accum[i] for i in sorted(tc_accum)] if tc_accum else []
        return text, tool_calls
