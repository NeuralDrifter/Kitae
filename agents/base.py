"""Base agent interface and event types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import threading


class EventType(Enum):
    TOKEN = auto()           # Streaming text chunk
    COMPLETE = auto()        # Iteration finished
    ERROR = auto()           # Something went wrong
    COST = auto()            # Cost update


@dataclass
class Event:
    type: EventType
    agent: str               # "claude", "gemini", "deepseek"
    text: str = ""
    cost: float = 0.0
    iteration: int = 0


class AgentBase(ABC):
    """Abstract base for all agent adapters."""

    name: str = "unknown"

    def __init__(self):
        self._stop_event = threading.Event()

    @abstractmethod
    def run(self, prompt: str, callback: callable, cwd: str = "") -> Optional[float]:
        """Run prompt and call callback(Event) for each output chunk.

        Args:
            prompt: The prompt to send.
            callback: Called with Event objects for streaming output.
            cwd: Working directory for the agent (empty = inherit).

        Returns estimated cost in USD (or 0 if unknown).
        Should check self._stop_event periodically and bail if set.
        """
        ...

    def stop(self):
        """Signal the agent to stop."""
        self._stop_event.set()

    def reset(self):
        """Reset stop flag for next run."""
        self._stop_event = threading.Event()

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()
