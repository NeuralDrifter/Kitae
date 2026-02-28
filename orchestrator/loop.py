# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""LoopManager — runs the continuous agent loop in a background thread."""

import queue
import threading
import time
from dataclasses import dataclass
from typing import List, Optional

from agents.base import AgentBase, Event, EventType, SOURCE_LOOP
from orchestrator.context import build_loop_prompt, has_completion_signal
from orchestrator.modes import Mode


@dataclass
class LoopConfig:
    prompt: str = ""
    max_iterations: int = 10
    max_cost_usd: float = 0.0       # 0 = no limit
    max_duration_secs: int = 0       # 0 = no limit
    completion_signal: str = "TASK_COMPLETE"
    working_dir: str = ""


class LoopManager:
    """Runs agent iterations in a daemon thread, pushes events to a queue."""

    def __init__(self, agents: List[AgentBase], mode: Mode, config: LoopConfig,
                 event_queue: queue.Queue):
        self._agents = agents
        self._mode = mode
        self._config = config
        self._queue = event_queue
        self._thread: Optional[threading.Thread] = None
        self._cancel = threading.Event()

        # Stats
        self.iteration = 0
        self.total_cost = 0.0
        self.start_time = 0.0
        self.running = False

    def start(self):
        """Start the loop in a background thread."""
        if self.running:
            return
        self._cancel.clear()
        self.iteration = 0
        self.total_cost = 0.0
        self.start_time = time.time()
        self.running = True

        # Tell the mode where to run agents
        self._mode.working_dir = self._config.working_dir

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the loop to stop."""
        self._cancel.set()
        for agent in self._agents:
            agent.stop()

    def _run_loop(self):
        try:
            while not self._cancel.is_set():
                self.iteration += 1

                # Check iteration limit
                if self._config.max_iterations > 0 and self.iteration > self._config.max_iterations:
                    self._emit(Event(EventType.COMPLETE, SOURCE_LOOP,
                                     text=f"Reached max iterations ({self._config.max_iterations})"))
                    break

                # Check duration limit
                if self._config.max_duration_secs > 0:
                    elapsed = time.time() - self.start_time
                    if elapsed >= self._config.max_duration_secs:
                        self._emit(Event(EventType.COMPLETE, SOURCE_LOOP,
                                         text=f"Reached max duration"))
                        break

                # Build prompt with loop-awareness instructions
                augmented = build_loop_prompt(
                    self._config.prompt,
                    self.iteration,
                    self._config.max_iterations,
                )

                # Notify iteration start
                active = self._mode.pick_agents(self._agents, self.iteration)
                agent_names = ", ".join(a.name for a in active)
                self._emit(Event(EventType.TOKEN, SOURCE_LOOP,
                                 text=f"\n{'='*60}\n Iteration {self.iteration} — {agent_names}\n{'='*60}\n\n",
                                 iteration=self.iteration))

                # Collect output for completion signal check
                iteration_output = []

                def _callback(event: Event):
                    event.iteration = self.iteration
                    self._emit(event)
                    if event.type == EventType.TOKEN:
                        iteration_output.append(event.text)

                # Execute
                try:
                    cost = self._mode.execute(self._agents, self.iteration, augmented, _callback)
                    self.total_cost += cost or 0.0
                except Exception as e:
                    self._emit(Event(EventType.ERROR, SOURCE_LOOP, text=str(e),
                                     iteration=self.iteration))
                    continue

                # Emit cost update
                output_text = "".join(iteration_output)
                self._emit(Event(EventType.COST, SOURCE_LOOP, cost=self.total_cost,
                                 iteration=self.iteration))

                # Check completion signal
                if has_completion_signal(output_text, self._config.completion_signal):
                    self._emit(Event(EventType.COMPLETE, SOURCE_LOOP,
                                     text="Completion signal detected"))
                    break

                # Check cost limit
                if self._config.max_cost_usd > 0 and self.total_cost >= self._config.max_cost_usd:
                    self._emit(Event(EventType.COMPLETE, SOURCE_LOOP,
                                     text=f"Reached max cost (${self.total_cost:.2f})"))
                    break

        except Exception as e:
            self._emit(Event(EventType.ERROR, SOURCE_LOOP, text=f"Loop crashed: {e}"))
        finally:
            # Clean up parallel worktrees if any
            if hasattr(self._mode, "cleanup"):
                self._mode.cleanup()
            self.running = False
            self._emit(Event(EventType.COMPLETE, SOURCE_LOOP,
                             text=f"Loop finished — {self.iteration} iterations, ${self.total_cost:.2f}"))

    def _emit(self, event: Event):
        self._queue.put_nowait(event)
