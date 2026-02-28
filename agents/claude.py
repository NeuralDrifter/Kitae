# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Claude Code agent — runs claude CLI in headless stream-json mode."""

from .base import Event, EventType, AGENT_CLAUDE
from .cli_agent import CLIAgent


class ClaudeAgent(CLIAgent):
    name = AGENT_CLAUDE

    def _build_cmd(self, prompt: str) -> list[str]:
        return [
            self._bin, "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "--no-session-persistence",
            "--max-turns", "50",
        ]

    def _init_parse_state(self):
        self._streamed_via_events = False

    def _parse_message(self, msg: dict, callback: callable,
                       full_text: list[str]) -> float:
        msg_type = msg.get("type", "")

        # Real-time streaming tokens (verbose mode)
        if msg_type == "stream_event":
            event = msg.get("event", {})
            delta = event.get("delta", {})
            if delta.get("type", "") == "text_delta":
                text = delta.get("text", "")
                if text:
                    callback(Event(EventType.TOKEN, self.name, text=text))
                    full_text.append(text)
                    self._streamed_via_events = True

        # Complete assistant turn
        elif msg_type == "assistant":
            if self._streamed_via_events:
                self._streamed_via_events = False
                return 0.0
            content = msg.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        callback(Event(EventType.TOKEN, self.name, text=text))
                        full_text.append(text)

        # Tool results (show what Claude did)
        elif msg_type == "user":
            content = msg.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        result_text = block.get("content", "")
                        if isinstance(result_text, str) and result_text:
                            display = result_text[:500]
                            if len(result_text) > 500:
                                display += "..."
                            callback(Event(EventType.TOKEN, self.name,
                                           text=f"\n[tool result] {display}\n"))

        # Final result with cost
        elif msg_type == "result":
            text = msg.get("result", "")
            if text:
                callback(Event(EventType.TOKEN, self.name, text=text + "\n"))
                full_text.append(text)
            cost = msg.get("cost_usd", 0.0) or 0.0
            session_cost = msg.get("total_cost_usd", 0.0) or 0.0
            return max(cost, session_cost)

        # Errors
        elif msg_type == "error":
            err = msg.get("error", {})
            err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            callback(Event(EventType.ERROR, self.name, text=err_msg))

        return 0.0
