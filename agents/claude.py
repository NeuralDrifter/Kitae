"""Claude Code agent — runs claude CLI in headless stream-json mode."""

import json
import subprocess
from typing import Optional

from .base import AgentBase, Event, EventType


class ClaudeAgent(AgentBase):
    name = "claude"

    def __init__(self, bin_path: str):
        super().__init__()
        self._bin = bin_path
        self._proc: Optional[subprocess.Popen] = None

    def run(self, prompt: str, callback: callable, cwd: str = "") -> float:
        self.reset()
        cost = 0.0

        cmd = [
            self._bin, "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "--no-session-persistence",
            "--max-turns", "50",
        ]

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=cwd or None,
        )

        full_text = []
        # Track whether we've seen stream_event tokens so we don't
        # double-emit the same text from the complete assistant message.
        streamed_via_events = False

        try:
            for line in self._proc.stdout:
                if self.stopped:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    callback(Event(EventType.TOKEN, self.name, text=line + "\n"))
                    full_text.append(line)
                    continue

                msg_type = msg.get("type", "")

                # ── Real-time streaming tokens (verbose mode) ────────
                if msg_type == "stream_event":
                    event = msg.get("event", {})
                    delta = event.get("delta", {})
                    delta_type = delta.get("type", "")

                    if delta_type == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            callback(Event(EventType.TOKEN, self.name, text=text))
                            full_text.append(text)
                            streamed_via_events = True

                # ── Complete assistant turn ───────────────────────────
                elif msg_type == "assistant":
                    # If we already streamed tokens via stream_event,
                    # skip to avoid double-emitting the same text.
                    if streamed_via_events:
                        streamed_via_events = False  # reset for next turn
                        continue
                    content = msg.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")
                                callback(Event(EventType.TOKEN, self.name, text=text))
                                full_text.append(text)

                # ── Tool results (show what Claude did) ──────────────
                elif msg_type == "user":
                    content = msg.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "tool_result":
                                # Show a brief note that a tool ran
                                tool_id = block.get("tool_use_id", "")
                                result_text = block.get("content", "")
                                if isinstance(result_text, str) and result_text:
                                    # Truncate very long tool results for display
                                    display = result_text[:500]
                                    if len(result_text) > 500:
                                        display += "..."
                                    callback(Event(EventType.TOKEN, self.name,
                                                   text=f"\n[tool result] {display}\n"))

                # ── Final result with cost ────────────────────────────
                elif msg_type == "result":
                    text = msg.get("result", "")
                    if text:
                        callback(Event(EventType.TOKEN, self.name, text=text + "\n"))
                        full_text.append(text)
                    cost = msg.get("cost_usd", 0.0) or 0.0
                    session_cost = msg.get("total_cost_usd", 0.0) or 0.0
                    if session_cost > cost:
                        cost = session_cost

                # ── Errors ────────────────────────────────────────────
                elif msg_type == "error":
                    err = msg.get("error", {})
                    err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    callback(Event(EventType.ERROR, self.name, text=err_msg))

                # ── System init (ignore gracefully) ───────────────────
                elif msg_type == "system":
                    pass  # session init, nothing to display

        finally:
            self._cleanup()

        callback(Event(EventType.COST, self.name, cost=cost))
        return cost

    def stop(self):
        super().stop()
        self._cleanup()

    def _cleanup(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    self._proc.kill()
                except ProcessLookupError:
                    pass
        self._proc = None
