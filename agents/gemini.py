# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Gemini CLI agent — runs gemini in headless stream-json mode."""

from .base import Event, EventType, AGENT_GEMINI
from .cli_agent import CLIAgent


class GeminiAgent(CLIAgent):
    name = AGENT_GEMINI

    def _build_cmd(self, prompt: str) -> list[str]:
        return [
            self._bin,
            "-p", prompt,
            "-o", "stream-json",
            "-y",  # auto-approve (yolo mode)
        ]

    def _parse_message(self, msg: dict, callback: callable,
                       full_text: list[str]) -> float:
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
            text = msg.get("content", "") or msg.get("text", "")
            if text:
                callback(Event(EventType.TOKEN, self.name, text=str(text)))
                full_text.append(str(text))

        return 0.0
