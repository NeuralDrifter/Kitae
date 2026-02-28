# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Base class for agents that run a CLI binary and parse stream-json output."""

import json
import subprocess
from abc import abstractmethod
from typing import Optional

from .base import AgentBase, Event, EventType


class CLIAgent(AgentBase):
    """Base for agents that run a CLI binary and parse stream-json output.

    Subclasses must implement:
        _build_cmd(prompt)   — return the CLI command list
        _parse_message(msg, callback, full_text) — parse one JSON message,
            return cost extracted (or 0.0)
    """

    def __init__(self, bin_path: str):
        super().__init__()
        self._bin = bin_path
        self._proc: Optional[subprocess.Popen] = None

    @abstractmethod
    def _build_cmd(self, prompt: str) -> list[str]:
        """Return the CLI command list."""
        ...

    @abstractmethod
    def _parse_message(self, msg: dict, callback: callable,
                       full_text: list[str]) -> float:
        """Parse one JSON message. Return cost extracted (or 0.0)."""
        ...

    def _init_parse_state(self):
        """Override to initialize per-run parse state."""
        pass

    def run(self, prompt: str, callback: callable, cwd: str = "") -> float:
        self.reset()
        cost = 0.0
        cmd = self._build_cmd(prompt)

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=cwd or None,
        )

        full_text: list[str] = []
        self._init_parse_state()

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

                msg_cost = self._parse_message(msg, callback, full_text)
                if msg_cost > cost:
                    cost = msg_cost
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
