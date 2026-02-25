# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Execution modes — how agents coordinate within the loop."""

import os
import shutil
import zipfile
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base import AgentBase, Event, EventType

# Directories to skip when copying the base into agent folders
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
             ".agent-loop", "backups"}


class Mode(ABC):
    """Base class for execution modes."""

    name: str = "unknown"
    working_dir: str = ""  # Set by LoopManager before execute()

    @abstractmethod
    def pick_agents(self, agents: List[AgentBase], iteration: int) -> List[AgentBase]:
        """Return which agent(s) should run this iteration."""
        ...

    @abstractmethod
    def execute(self, agents: List[AgentBase], iteration: int,
                prompt: str, callback: callable) -> float:
        """Run the iteration. Returns total cost."""
        ...


class SingleMode(Mode):
    """One agent runs every iteration."""
    name = "single"

    def pick_agents(self, agents, iteration):
        return [agents[0]]

    def execute(self, agents, iteration, prompt, callback):
        agent = agents[0]
        agent.reset()
        return agent.run(prompt, callback, cwd=self.working_dir)


class RoundRobinMode(Mode):
    """Cycles through agents each iteration."""
    name = "round-robin"

    def pick_agents(self, agents, iteration):
        idx = (iteration - 1) % len(agents)
        return [agents[idx]]

    def execute(self, agents, iteration, prompt, callback):
        idx = (iteration - 1) % len(agents)
        agent = agents[idx]
        agent.reset()
        return agent.run(prompt, callback, cwd=self.working_dir)


def backup_base(working_dir: str) -> str:
    """Zip the base project into backups/. Returns the zip path."""
    backups_dir = os.path.join(working_dir, "backups")
    os.makedirs(backups_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    zip_path = os.path.join(backups_dir, f"base_backup_{stamp}.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(working_dir):
            # Prune dirs we don't want in the backup
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS
                       and not d.startswith(".agent-loop")]
            for f in files:
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, working_dir)
                zf.write(full, arcname)

    return zip_path


def copy_base_to_agent_dir(working_dir: str, agent_name: str) -> str:
    """Copy the base project into .agent-loop/<agent_name>/. Returns the path."""
    agent_dir = os.path.join(working_dir, ".agent-loop", agent_name)

    # Wipe old copy if it exists
    if os.path.exists(agent_dir):
        shutil.rmtree(agent_dir)
    os.makedirs(agent_dir)

    for item in os.listdir(working_dir):
        if item in SKIP_DIRS or item.startswith(".agent-loop"):
            continue
        src = os.path.join(working_dir, item)
        dst = os.path.join(agent_dir, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
                *SKIP_DIRS, ".agent-loop*"))
        else:
            shutil.copy2(src, dst)

    return agent_dir


def has_existing_base(working_dir: str) -> bool:
    """Check if the working directory has files (i.e. an existing project)."""
    if not working_dir or not os.path.isdir(working_dir):
        return False
    for item in os.listdir(working_dir):
        if item not in SKIP_DIRS and not item.startswith("."):
            return True
    return False


class ParallelMode(Mode):
    """Each agent gets its own copy of the codebase in a named folder.

    Layout:
        working_dir/
        ├── backups/
        │   └── base_backup_2026-02-24_143000.zip
        ├── .agent-loop/
        │   ├── claude/    ← full copy, claude works here
        │   ├── gemini/    ← full copy, gemini works here
        │   └── deepseek/  ← full copy, deepseek works here
        └── (original base files)

    The user compares results by diffing the agent folders.
    """
    name = "parallel"
    _agent_dirs: dict[str, str] = {}  # agent_name -> folder path
    _setup_done: bool = False
    backup_requested: bool = False  # Set by GUI before loop starts

    def __init__(self):
        self._agent_dirs: dict[str, str] = {}
        self._setup_done: bool = False

    def pick_agents(self, agents, iteration):
        return list(agents)

    def execute(self, agents, iteration, prompt, callback):
        total_cost = 0.0
        for a in agents:
            a.reset()

        with ThreadPoolExecutor(max_workers=len(agents)) as pool:
            futures = {
                pool.submit(
                    a.run, prompt, callback,
                    self._agent_dirs.get(a.name, self.working_dir)
                ): a
                for a in agents
            }
            for future in as_completed(futures):
                try:
                    cost = future.result()
                    total_cost += cost or 0.0
                except Exception as e:
                    agent = futures[future]
                    callback(Event(EventType.ERROR, agent.name, text=str(e)))

        return total_cost


class ReviewerMode(Mode):
    """First agent generates, second agent reviews."""
    name = "reviewer"

    def pick_agents(self, agents, iteration):
        return agents[:2]

    def execute(self, agents, iteration, prompt, callback):
        primary = agents[0]
        reviewer = agents[1] if len(agents) > 1 else agents[0]
        total_cost = 0.0

        # Phase 1: Primary generates
        primary.reset()
        collected = []

        def collect_and_forward(event: Event):
            if event.type == EventType.TOKEN:
                collected.append(event.text)
            callback(event)

        cost = primary.run(prompt, collect_and_forward, cwd=self.working_dir)
        total_cost += cost or 0.0

        # Phase 2: Reviewer critiques
        primary_output = "".join(collected)
        review_prompt = (
            f"Review the following output from {primary.name} and provide feedback. "
            f"Point out any issues, improvements, or errors.\n\n"
            f"--- Original Prompt ---\n{prompt}\n\n"
            f"--- {primary.name}'s Output ---\n{primary_output}"
        )
        reviewer.reset()
        cost = reviewer.run(review_prompt, callback, cwd=self.working_dir)
        total_cost += cost or 0.0

        return total_cost


MODES = {
    "single": SingleMode,
    "round-robin": RoundRobinMode,
    "parallel": ParallelMode,
    "reviewer": ReviewerMode,
}
