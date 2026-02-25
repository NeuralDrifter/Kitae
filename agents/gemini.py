"""Gemini CLI agent — runs gemini in headless stream-json mode."""

import json
import subprocess
from typing import Optional

from .base import AgentBase, Event, EventType


class GeminiAgent(AgentBase):
    name = "gemini"

    def __init__(self, bin_path: str):
        super().__init__()
        self._bin = bin_path
        self._proc: Optional[subprocess.Popen] = None

    def run(self, prompt: str, callback: callable, cwd: str = "") -> float:
        self.reset()
        cost = 0.0

        cmd = [
            self._bin,
            "-p", prompt,
            "-o", "stream-json",
            "-y",  # auto-approve (yolo mode)
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

                if msg_type in ("assistant", "response"):
                    content = msg.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")
                                callback(Event(EventType.TOKEN, self.name, text=text))
                                full_text.append(text)
                    elif isinstance(content, str):
                        callback(Event(EventType.TOKEN, self.name, text=content))
                        full_text.append(content)

                elif msg_type == "result":
                    text = msg.get("result", "")
                    if text:
                        callback(Event(EventType.TOKEN, self.name, text=text + "\n"))
                        full_text.append(text)

                elif msg_type == "error":
                    err = msg.get("error", "Unknown error")
                    err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    callback(Event(EventType.ERROR, self.name, text=err_msg))

                else:
                    # Unknown type — try to extract any text content
                    text = msg.get("content", "") or msg.get("text", "")
                    if text:
                        callback(Event(EventType.TOKEN, self.name, text=str(text)))
                        full_text.append(str(text))

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
