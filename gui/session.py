# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Session data model — one session per tab."""

import queue
import uuid
from dataclasses import dataclass, field

from agents.base import Event
from orchestrator.modes import MODE_SINGLE


class SessionPhase:
    """UI status display text for forging phases."""
    IDLE = "Idle"
    FORGING = "Forging"
    QUENCHING = "Quenching"
    TEMPERED = "Tempered"


class SessionStatus:
    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    STOPPING = "stopping"


@dataclass
class SessionConfig:
    """Snapshot of ConfigPanel widget values."""
    agents: list[str] = field(default_factory=list)
    mode: str = MODE_SINGLE
    prompt: str = ""
    working_dir: str = ""
    max_iterations: int = 10
    max_cost_usd: float = 0.0
    max_duration_secs: int = 0


@dataclass
class Session:
    """One independent session — owns its own queue, loop, and output."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    config: SessionConfig = field(default_factory=SessionConfig)
    event_queue: queue.Queue = field(default_factory=queue.Queue)
    loop_manager: object = None       # LoopManager | None
    output_panel: object = None       # OutputPanel | None
    status: str = SessionStatus.IDLE

    # Cached metrics for status bar restore on tab switch
    total_cost: float = 0.0
    elapsed: float = 0.0
    iteration: int = 0
    max_iterations: int = 0
    status_text: str = "\u2014"
