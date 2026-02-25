"""Kitae — Forge. Fold. Refine. Repeat."""

import os
import queue
import time
import customtkinter as ctk
from tkinter import messagebox

import config
from agents import ClaudeAgent, GeminiAgent, DeepSeekAgent, LMStudioAgent
from agents.mcp_manager import MCPManager
from agents.base import AgentBase, Event, EventType
from orchestrator.loop import LoopManager, LoopConfig
from orchestrator.modes import MODES, ParallelMode, has_existing_base, backup_base, copy_base_to_agent_dir
from gui.config_panel import ConfigPanel
from gui.output_panel import OutputPanel
from gui.status_bar import StatusBar
from gui import theme as T


POLL_MS = 50


class AgentLoopApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Kitae")
        self.geometry("1100x700")
        self.minsize(800, 500)
        self.configure(fg_color=T.BG_DARK)

        self._settings = config.load()
        self._event_queue: queue.Queue[Event] = queue.Queue()
        self._loop_manager: LoopManager | None = None

        # MCP server connections (shared across all API agents)
        self._mcp: MCPManager | None = None
        if self._settings.mcp_servers:
            self._mcp = MCPManager(self._settings.mcp_servers)
            self._mcp.connect()

        # Layout — sidebar | accent divider | output
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)  # output gets all stretch

        self.config_panel = ConfigPanel(
            self, self._settings,
            on_start=self._start_loop,
            on_stop=self._stop_loop,
        )
        self.config_panel.grid(row=0, column=0, sticky="nsew")

        # Vertical accent line between sidebar and content
        divider = ctk.CTkFrame(self, width=1, fg_color=T.BORDER_MID, corner_radius=0)
        divider.grid(row=0, column=1, sticky="ns")

        self.output_panel = OutputPanel(self)
        self.output_panel.grid(row=0, column=2, sticky="nsew")

        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=0, columnspan=3, sticky="ew")

        self._poll_queue()

    def _build_agents(self, names: list[str]) -> list[AgentBase]:
        agents = []
        for name in names:
            if name == "claude" and self._settings.claude_available:
                agents.append(ClaudeAgent(self._settings.claude_bin))
            elif name == "gemini" and self._settings.gemini_available:
                agents.append(GeminiAgent(self._settings.gemini_bin))
            elif name == "deepseek" and self._settings.deepseek_available:
                agents.append(DeepSeekAgent(
                    api_key=self._settings.deepseek_api_key,
                    base_url=self._settings.deepseek_base_url,
                    model=self._settings.deepseek_model,
                    mcp_manager=self._mcp,
                ))
            elif name == "lmstudio" and self._settings.lmstudio_available:
                agents.append(LMStudioAgent(
                    base_url=self._settings.lmstudio_base_url,
                    model=self._settings.lmstudio_model,
                    mcp_manager=self._mcp,
                ))
        return agents

    def _start_loop(self):
        prompt = self.config_panel.get_prompt()
        if not prompt.strip():
            self.output_panel.append("loop", "[ERROR] Please enter a prompt.\n")
            return

        selected = self.config_panel.get_selected_agents()
        if not selected:
            self.output_panel.append("loop", "[ERROR] Select at least one agent.\n")
            return

        mode_name = self.config_panel.get_mode()
        if mode_name in ("round-robin", "parallel", "reviewer") and len(selected) < 2:
            self.output_panel.append(
                "loop",
                f"[ERROR] {mode_name} mode needs at least 2 agents selected.\n")
            return

        working_dir = self.config_panel.get_working_dir()

        if mode_name == "parallel" and not working_dir:
            self.output_panel.append(
                "loop", "[ERROR] Parallel mode requires a working directory.\n")
            return

        agents = self._build_agents(selected)
        if not agents:
            self.output_panel.append("loop", "[ERROR] No agents available.\n")
            return

        mode = MODES[mode_name]()

        # --- Parallel mode: backup base FIRST, then copy into agent folders ---
        if mode_name == "parallel" and working_dir:
            if has_existing_base(working_dir):
                do_backup = messagebox.askyesno(
                    "Existing Project Detected",
                    f"The working directory has existing files:\n{working_dir}\n\n"
                    "Create a backup zip before copying into agent folders?",
                    parent=self,
                )
                if do_backup:
                    self.output_panel.clear_all()
                    self.output_panel.append(
                        "loop", "[parallel] Backing up base project...\n")
                    self.update_idletasks()
                    try:
                        zip_path = backup_base(working_dir)
                        self.output_panel.append(
                            "loop", f"[parallel] Backup saved: {zip_path}\n\n")
                    except Exception as e:
                        self.output_panel.append(
                            "loop", f"[ERROR] Backup failed: {e}\n")
                        return
                else:
                    self.output_panel.clear_all()

                # Copy base into each agent's folder
                for a in agents:
                    self.output_panel.append(
                        "loop", f"[parallel] Copying base -> .agent-loop/{a.name}/\n")
                    self.update_idletasks()
                    try:
                        agent_dir = copy_base_to_agent_dir(working_dir, a.name)
                        mode._agent_dirs[a.name] = agent_dir
                    except Exception as e:
                        self.output_panel.append(
                            "loop", f"[ERROR] Copy failed for {a.name}: {e}\n")
                        return

                mode._setup_done = True
                self.output_panel.append("loop", "[parallel] All agent folders ready.\n\n")
            else:
                self.output_panel.clear_all()
                self.output_panel.append(
                    "loop", "[parallel] Empty working dir — agents start from scratch.\n\n")
                for a in agents:
                    d = os.path.join(working_dir, ".agent-loop", a.name)
                    os.makedirs(d, exist_ok=True)
                    mode._agent_dirs[a.name] = d
                mode._setup_done = True
        else:
            self.output_panel.clear_all()

        loop_config = LoopConfig(
            prompt=prompt,
            max_iterations=self.config_panel.get_max_iterations(),
            max_cost_usd=self.config_panel.get_max_cost(),
            max_duration_secs=self.config_panel.get_max_duration_secs(),
            completion_signal=self._settings.completion_signal,
            working_dir=working_dir,
        )

        for a in agents:
            self.output_panel.ensure_tab(a.name)

        self.status_bar.reset()
        self.config_panel.set_running(True)

        self._loop_manager = LoopManager(agents, mode, loop_config, self._event_queue)
        self._loop_manager.start()

        self.status_bar.set_status("Forging")
        self._start_time = time.time()

    def _stop_loop(self):
        if self._loop_manager:
            self._loop_manager.stop()
        self.status_bar.set_status("Quenching")

    def _poll_queue(self):
        try:
            while True:
                event = self._event_queue.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass

        if self._loop_manager and self._loop_manager.running:
            elapsed = time.time() - self._loop_manager.start_time
            self.status_bar.set_elapsed(elapsed)

        self.after(POLL_MS, self._poll_queue)

    def _handle_event(self, event: Event):
        if event.type == EventType.TOKEN:
            self.output_panel.append(event.agent, event.text)
            if event.iteration > 0 and self._loop_manager:
                max_it = self._loop_manager._config.max_iterations
                self.status_bar.set_iteration(event.iteration, max_it)

        elif event.type == EventType.ERROR:
            self.output_panel.append(event.agent, f"\n[ERROR] {event.text}\n")

        elif event.type == EventType.COST:
            self.status_bar.set_cost(event.cost)

        elif event.type == EventType.COMPLETE:
            self.output_panel.append("loop", f"\n{event.text}\n")
            self.config_panel.set_running(False)
            self.status_bar.set_status("Tempered")

    def destroy(self):
        if self._mcp:
            self._mcp.shutdown()
        super().destroy()
