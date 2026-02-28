# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Kitae — Forge. Fold. Refine. Repeat."""

import os
import queue
import time
import customtkinter as ctk
from tkinter import messagebox

import config
from agents import AGENT_REGISTRY
from agents.mcp_manager import MCPManager
from agents.base import AgentBase, Event, EventType, SOURCE_LOOP
from orchestrator.loop import LoopManager, LoopConfig
from orchestrator.modes import (
    MODES, AGENT_LOOP_DIR,
    MODE_ROUND_ROBIN, MODE_PARALLEL, MODE_REVIEWER, MODE_SINGLE,
    has_existing_base, backup_base, copy_base_to_agent_dir,
)
from gui.config_panel import ConfigPanel
from gui.output_panel import OutputPanel
from gui.status_bar import StatusBar
from gui.session import Session, SessionConfig, SessionStatus, SessionPhase
from gui.session_tab_bar import SessionTabBar
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

        # MCP server connections (shared across all API agents)
        self._mcp: MCPManager | None = None
        if self._settings.mcp_servers:
            self._mcp = MCPManager(self._settings.mcp_servers)
            self._mcp.connect()

        # Session state
        self._sessions: dict[str, Session] = {}
        self._active_session_id: str = ""
        self._session_counter: int = 0

        # Layout — row 0: tab bar, row 1: content, row 2: status bar
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)  # output gets all stretch

        # ── Row 0: Session tab bar (spans full width) ──
        self.tab_bar = SessionTabBar(
            self,
            on_switch=self._switch_session,
            on_new=self._new_session,
            on_close=self._close_session,
        )
        self.tab_bar.grid(row=0, column=0, columnspan=3, sticky="ew")

        # ── Row 1: Sidebar | divider | output container ──
        self.config_panel = ConfigPanel(
            self, self._settings,
            on_start=self._start_loop,
            on_stop=self._stop_loop,
        )
        self.config_panel.grid(row=1, column=0, sticky="nsew")

        divider = ctk.CTkFrame(self, width=1, fg_color=T.BORDER_MID, corner_radius=0)
        divider.grid(row=1, column=1, sticky="ns")

        # Container frame that holds the active session's OutputPanel
        self._output_container = ctk.CTkFrame(self, fg_color=T.BG_DARK, corner_radius=0)
        self._output_container.grid(row=1, column=2, sticky="nsew")
        self._output_container.grid_rowconfigure(0, weight=1)
        self._output_container.grid_columnconfigure(0, weight=1)

        # ── Row 2: Status bar ──
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=2, column=0, columnspan=3, sticky="ew")

        # Create the first session
        self._new_session()

        # Keyboard shortcuts
        self.bind_all("<Control-t>", lambda e: self._new_session())
        self.bind_all("<Control-w>", lambda e: self._close_session(self._active_session_id))
        self.bind_all("<Control-Tab>", lambda e: self._cycle_session(forward=True))
        self.bind_all("<Control-Shift-Tab>", lambda e: self._cycle_session(forward=False))
        # Ctrl+ISO_Left_Tab is what some Linux WMs send for Ctrl+Shift+Tab
        self.bind_all("<Control-ISO_Left_Tab>", lambda e: self._cycle_session(forward=False))
        for n in range(1, 10):
            self.bind_all(f"<Control-Key-{n}>", lambda e, idx=n: self._jump_to_session(idx))

        self._poll_queue()

    # ── Session management ────────────────────────────

    def _new_session(self):
        if len(self._sessions) >= 12:
            return

        self._session_counter += 1
        session = Session(name=f"Session {self._session_counter}")
        session.output_panel = OutputPanel(self._output_container)
        session.config = SessionConfig(
            agents=self.config_panel.get_selected_agents() if self._sessions else [],
            mode=MODE_SINGLE,
            prompt="",
            working_dir="",
            max_iterations=self._settings.max_iterations,
            max_cost_usd=self._settings.max_cost_usd or 0.0,
            max_duration_secs=self._settings.max_duration_secs or 0,
        )

        self._sessions[session.id] = session
        self.tab_bar.add_tab(session.id, session.name, session.status)
        self._switch_session(session.id)

    def _switch_session(self, session_id: str):
        if session_id not in self._sessions:
            return
        if session_id == self._active_session_id:
            return

        # Save current config to outgoing session
        if self._active_session_id and self._active_session_id in self._sessions:
            self._save_config_to_session(self._active_session_id)
            old_session = self._sessions[self._active_session_id]
            old_session.output_panel.grid_forget()

        # Activate new session
        self._active_session_id = session_id
        session = self._sessions[session_id]

        # Show its output panel
        session.output_panel.grid(row=0, column=0, sticky="nsew")

        # Restore config into sidebar
        self._load_config_from_session(session_id)

        # Update button states based on session status
        running = session.status in (SessionStatus.RUNNING, SessionStatus.STOPPING)
        self.config_panel.set_running(running)

        # Update status bar
        self._update_status_bar_for_session(session)

        # Visual tab highlight
        self.tab_bar.set_active(session_id)

    def _close_session(self, session_id: str):
        if len(self._sessions) <= 1:
            return
        session = self._sessions.get(session_id)
        if not session:
            return

        if session.status == SessionStatus.RUNNING:
            ok = messagebox.askyesno(
                "Close Running Session",
                f'"{session.name}" is still running.\nStop agents and close?',
                parent=self,
            )
            if not ok:
                return
            if session.loop_manager:
                session.loop_manager.stop()

        # Switch away if this is the active tab
        if session_id == self._active_session_id:
            ids = self.tab_bar.tab_ids()
            idx = ids.index(session_id)
            next_id = ids[idx - 1] if idx > 0 else ids[idx + 1]
            self._switch_session(next_id)

        # Tear down
        session.output_panel.destroy()
        self.tab_bar.remove_tab(session_id)
        del self._sessions[session_id]

    def _save_config_to_session(self, session_id: str):
        session = self._sessions.get(session_id)
        if not session:
            return
        session.config.agents = self.config_panel.get_selected_agents()
        session.config.mode = self.config_panel.get_mode()
        session.config.prompt = self.config_panel.get_prompt()
        session.config.working_dir = self.config_panel.get_working_dir()
        session.config.max_iterations = self.config_panel.get_max_iterations()
        session.config.max_cost_usd = self.config_panel.get_max_cost()
        session.config.max_duration_secs = self.config_panel.get_max_duration_secs()

    def _load_config_from_session(self, session_id: str):
        session = self._sessions.get(session_id)
        if not session:
            return
        c = session.config
        self.config_panel.set_agents(c.agents)
        self.config_panel.set_mode(c.mode)
        self.config_panel.set_prompt(c.prompt)
        self.config_panel.set_working_dir(c.working_dir)
        self.config_panel.set_limits(c.max_iterations, c.max_cost_usd, c.max_duration_secs)

    def _update_status_bar_for_session(self, session: Session):
        if session.status == SessionStatus.IDLE:
            self.status_bar.reset()
        else:
            self.status_bar.set_status(session.status_text)
            self.status_bar.set_cost(session.total_cost)
            self.status_bar.set_elapsed(session.elapsed)
            if session.iteration > 0:
                self.status_bar.set_iteration(session.iteration, session.max_iterations)

    def _cycle_session(self, forward: bool):
        ids = self.tab_bar.tab_ids()
        if len(ids) < 2:
            return
        try:
            idx = ids.index(self._active_session_id)
        except ValueError:
            return
        idx = (idx + (1 if forward else -1)) % len(ids)
        self._switch_session(ids[idx])

    def _jump_to_session(self, n: int):
        ids = self.tab_bar.tab_ids()
        if 0 < n <= len(ids):
            self._switch_session(ids[n - 1])

    # ── Agent building ────────────────────────────────

    def _build_agents(self, names: list[str]) -> list[AgentBase]:
        agents = []
        for name in names:
            entry = AGENT_REGISTRY.get(name)
            if entry and getattr(self._settings, entry["available_attr"]):
                agents.append(entry["factory"](self._settings, self._mcp))
        return agents

    # ── Loop start/stop (targets active session) ──────

    def _start_loop(self):
        session = self._sessions.get(self._active_session_id)
        if not session:
            return

        prompt = self.config_panel.get_prompt()
        if not prompt.strip():
            session.output_panel.append(SOURCE_LOOP, "[ERROR] Please enter a prompt.\n")
            return

        selected = self.config_panel.get_selected_agents()
        if not selected:
            session.output_panel.append(SOURCE_LOOP, "[ERROR] Select at least one agent.\n")
            return

        mode_name = self.config_panel.get_mode()
        if mode_name in (MODE_ROUND_ROBIN, MODE_PARALLEL, MODE_REVIEWER) and len(selected) < 2:
            session.output_panel.append(
                SOURCE_LOOP,
                f"[ERROR] {mode_name} mode needs at least 2 agents selected.\n")
            return

        working_dir = self.config_panel.get_working_dir()

        if mode_name == MODE_PARALLEL and not working_dir:
            session.output_panel.append(
                SOURCE_LOOP, "[ERROR] Parallel mode requires a working directory.\n")
            return

        agents = self._build_agents(selected)
        if not agents:
            session.output_panel.append(SOURCE_LOOP, "[ERROR] No agents available.\n")
            return

        mode = MODES[mode_name]()

        # --- Parallel mode: backup base FIRST, then copy into agent folders ---
        if mode_name == MODE_PARALLEL and working_dir:
            if has_existing_base(working_dir):
                do_backup = messagebox.askyesno(
                    "Existing Project Detected",
                    f"The working directory has existing files:\n{working_dir}\n\n"
                    "Create a backup zip before copying into agent folders?",
                    parent=self,
                )
                if do_backup:
                    session.output_panel.clear_all()
                    session.output_panel.append(
                        SOURCE_LOOP, "[parallel] Backing up base project...\n")
                    self.update_idletasks()
                    try:
                        zip_path = backup_base(working_dir)
                        session.output_panel.append(
                            SOURCE_LOOP, f"[parallel] Backup saved: {zip_path}\n\n")
                    except Exception as e:
                        session.output_panel.append(
                            SOURCE_LOOP, f"[ERROR] Backup failed: {e}\n")
                        return
                else:
                    session.output_panel.clear_all()

                # Copy base into each agent's folder
                for a in agents:
                    session.output_panel.append(
                        SOURCE_LOOP, f"[parallel] Copying base -> {AGENT_LOOP_DIR}/{a.name}/\n")
                    self.update_idletasks()
                    try:
                        agent_dir = copy_base_to_agent_dir(working_dir, a.name)
                        mode._agent_dirs[a.name] = agent_dir
                    except Exception as e:
                        session.output_panel.append(
                            SOURCE_LOOP, f"[ERROR] Copy failed for {a.name}: {e}\n")
                        return

                mode._setup_done = True
                session.output_panel.append(SOURCE_LOOP, "[parallel] All agent folders ready.\n\n")
            else:
                session.output_panel.clear_all()
                session.output_panel.append(
                    SOURCE_LOOP, "[parallel] Empty working dir — agents start from scratch.\n\n")
                for a in agents:
                    d = os.path.join(working_dir, AGENT_LOOP_DIR, a.name)
                    os.makedirs(d, exist_ok=True)
                    mode._agent_dirs[a.name] = d
                mode._setup_done = True
        else:
            session.output_panel.clear_all()

        loop_config = LoopConfig(
            prompt=prompt,
            max_iterations=self.config_panel.get_max_iterations(),
            max_cost_usd=self.config_panel.get_max_cost(),
            max_duration_secs=self.config_panel.get_max_duration_secs(),
            completion_signal=self._settings.completion_signal,
            working_dir=working_dir,
        )

        for a in agents:
            session.output_panel.ensure_tab(a.name)

        self.status_bar.reset()
        self.config_panel.set_running(True)

        session.loop_manager = LoopManager(agents, mode, loop_config, session.event_queue)
        session.loop_manager.start()

        session.status = SessionStatus.RUNNING
        session.status_text = SessionPhase.FORGING
        session.total_cost = 0.0
        session.elapsed = 0.0
        session.iteration = 0
        session.max_iterations = loop_config.max_iterations

        self.status_bar.set_status(SessionPhase.FORGING)
        self.tab_bar.update_tab(session.id, status=session.status)

    def _stop_loop(self):
        session = self._sessions.get(self._active_session_id)
        if not session:
            return
        if session.loop_manager:
            session.loop_manager.stop()
        session.status = SessionStatus.STOPPING
        session.status_text = SessionPhase.QUENCHING
        self.status_bar.set_status(SessionPhase.QUENCHING)
        self.tab_bar.update_tab(session.id, status=session.status)

    # ── Polling — drains ALL session queues ───────────

    def _poll_queue(self):
        for session in self._sessions.values():
            try:
                while True:
                    event = session.event_queue.get_nowait()
                    self._handle_event(session, event)
            except queue.Empty:
                pass

            # Update elapsed for running sessions
            if session.loop_manager and session.loop_manager.running:
                session.elapsed = time.time() - session.loop_manager.start_time
                if session.id == self._active_session_id:
                    self.status_bar.set_elapsed(session.elapsed)

        self.after(POLL_MS, self._poll_queue)

    def _handle_event(self, session: Session, event: Event):
        is_active = (session.id == self._active_session_id)

        if event.type == EventType.TOKEN:
            session.output_panel.append(event.agent, event.text)
            if event.iteration > 0 and session.loop_manager:
                max_it = session.loop_manager._config.max_iterations
                session.iteration = event.iteration
                session.max_iterations = max_it
                if is_active:
                    self.status_bar.set_iteration(event.iteration, max_it)

        elif event.type == EventType.ERROR:
            session.output_panel.append(event.agent, f"\n[ERROR] {event.text}\n")

        elif event.type == EventType.COST:
            session.total_cost = event.cost
            if is_active:
                self.status_bar.set_cost(event.cost)

        elif event.type == EventType.COMPLETE:
            session.output_panel.append(SOURCE_LOOP, f"\n{event.text}\n")
            session.status = SessionStatus.COMPLETE
            session.status_text = SessionPhase.TEMPERED
            self.tab_bar.update_tab(session.id, status=session.status)
            if is_active:
                self.config_panel.set_running(False)
                self.status_bar.set_status(SessionPhase.TEMPERED)

    # ── Shutdown ──────────────────────────────────────

    def destroy(self):
        for session in self._sessions.values():
            if session.loop_manager and session.loop_manager.running:
                session.loop_manager.stop()
        if self._mcp:
            self._mcp.shutdown()
        super().destroy()
