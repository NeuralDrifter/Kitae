# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Left sidebar — session configuration with Kitae theme."""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from agents import AGENT_REGISTRY
from orchestrator.modes import MODE_SINGLE, MODE_ROUND_ROBIN, MODE_PARALLEL, MODE_REVIEWER
from gui import theme as T


class Tooltip:
    """Hover tooltip for any tkinter/CTk widget."""

    DELAY_MS = 400

    def __init__(self, widget, text: str):
        self._widget = widget
        self._text = text
        self._tip_window: tk.Toplevel | None = None
        self._after_id: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._cancel, add="+")
        widget.bind("<ButtonPress>", self._cancel, add="+")

    def _schedule(self, event=None):
        self._cancel()
        self._after_id = self._widget.after(self.DELAY_MS, self._show)

    def _cancel(self, event=None):
        if self._after_id:
            self._widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self):
        if self._tip_window:
            return
        x = self._widget.winfo_rootx() + self._widget.winfo_width() + 4
        y = self._widget.winfo_rooty()

        self._tip_window = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg=T.BORDER_MID)

        label = tk.Label(
            tw, text=self._text,
            justify="left",
            background=T.BG_CARD,
            foreground=T.TEXT,
            relief="flat",
            borderwidth=0,
            font=("JetBrains Mono", 10),
            padx=10, pady=8,
            wraplength=260,
        )
        label.pack(padx=1, pady=1)

    def _hide(self):
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


def _make_section(parent, row: int, label: str) -> tuple[ctk.CTkFrame, int]:
    """Create a section header + card frame, return (card_frame, next_row)."""
    ctk.CTkLabel(
        parent, text=label,
        font=("JetBrains Mono", 10, "bold"),
        text_color=T.GOLD_DIM,
    ).grid(row=row, column=0, padx=14, pady=(T.SECTION_GAP, 3), sticky="w")
    row += 1

    card = ctk.CTkFrame(
        parent,
        fg_color=T.BG_CARD,
        corner_radius=T.CARD_RADIUS,
        border_width=1,
        border_color=T.BORDER,
    )
    card.grid(row=row, column=0, padx=8, pady=(0, 2), sticky="ew")
    card.grid_columnconfigure(0, weight=1)
    row += 1
    return card, row


class ConfigPanel(ctk.CTkScrollableFrame):
    def __init__(self, parent, settings, on_start, on_stop):
        super().__init__(
            parent, width=T.SIDEBAR_WIDTH, fg_color=T.BG_PANEL,
            scrollbar_button_color=T.SAKURA_DIM,
            scrollbar_button_hover_color=T.SAKURA,
        )
        self._settings = settings
        self._on_start = on_start
        self._on_stop = on_stop
        self.grid_columnconfigure(0, weight=1)

        r = 0  # running row counter

        # ── Brand Header ──────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=r, column=0, padx=10, pady=(12, 4), sticky="ew")
        r += 1

        ctk.CTkLabel(
            header_frame, text="KITAE",
            font=("JetBrains Mono", 22, "bold"),
            text_color=T.GOLD,
        ).pack(anchor="w")

        ctk.CTkLabel(
            header_frame, text="Forge. Fold. Refine. Repeat.",
            font=("JetBrains Mono", 9),
            text_color=T.TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 2))

        # Thin gold accent line under header
        ctk.CTkFrame(
            self, height=1, fg_color=T.GOLD_DIM,
        ).grid(row=r, column=0, padx=14, pady=(0, 4), sticky="ew")
        r += 1

        # ── Agents Section ────────────────────────────
        card, r = _make_section(self, r, "AGENTS")

        # Build agent checkbox vars from the registry
        self._agent_vars: dict[str, ctk.BooleanVar] = {}
        agents_info = []
        for name, entry in AGENT_REGISTRY.items():
            available = getattr(settings, entry["available_attr"])
            var = ctk.BooleanVar(value=available)
            self._agent_vars[name] = var
            agents_info.append((entry["label"], var, available))

        for i, (label, var, available) in enumerate(agents_info):
            row_frame = ctk.CTkFrame(card, fg_color="transparent")
            row_frame.grid(row=i, column=0, padx=T.CARD_PAD_X, pady=(6 if i == 0 else 2, 6 if i == len(agents_info) - 1 else 2), sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)

            # Status dot
            dot_color = T.GREEN if available else T.RED_DIM
            dot = ctk.CTkLabel(
                row_frame, text="\u25CF", width=14,
                font=("", 10),
                text_color=dot_color,
            )
            dot.grid(row=0, column=0, padx=(0, 2))

            cb = ctk.CTkCheckBox(
                row_frame, text=label, variable=var,
                fg_color=T.SAKURA, hover_color=T.SAKURA_BRIGHT,
                border_color=T.BORDER_MID, text_color=T.TEXT,
                font=("JetBrains Mono", 11),
                checkbox_width=18, checkbox_height=18,
                corner_radius=4,
                state="normal" if available else "disabled",
            )
            cb.grid(row=0, column=1, sticky="w")


        # ── Mode Section ──────────────────────────────
        card, r = _make_section(self, r, "MODE")

        self.mode_var = ctk.StringVar(value=MODE_SINGLE)
        mode_tips = {
            MODE_SINGLE: "One smith, one blade.\nA single agent loops alone,\nrefining each pass.",
            MODE_ROUND_ROBIN: "The blade passes between smiths.\nAgent A \u2192 B \u2192 C \u2192 A ...\nEach folds in the previous work.",
            MODE_PARALLEL: "Multiple smiths, separate anvils.\nEach agent gets its own copy of the\nproject and works independently.\nCompare results after.",
            MODE_REVIEWER: "One forges, one inspects.\nThe first agent works, the second\ncritiques. Needs 2+ agents.",
        }

        for i, (label, value) in enumerate([
            ("Single", MODE_SINGLE),
            ("Round-Robin", MODE_ROUND_ROBIN),
            ("Parallel", MODE_PARALLEL),
            ("Reviewer", MODE_REVIEWER),
        ]):
            rb = ctk.CTkRadioButton(
                card, text=label, variable=self.mode_var, value=value,
                fg_color=T.SAKURA, hover_color=T.SAKURA_DIM,
                border_color=T.BORDER_MID, text_color=T.TEXT,
                font=("JetBrains Mono", 11),
                radiobutton_width=18, radiobutton_height=18,
            )
            rb.grid(
                row=i, column=0, padx=T.CARD_PAD_X,
                pady=(8 if i == 0 else 3, 8 if i == 3 else 3),
                sticky="w",
            )
            Tooltip(rb, mode_tips[value])

        # ── Prompt Section ────────────────────────────
        card, r = _make_section(self, r, "PROMPT")

        self.prompt_box = ctk.CTkTextbox(
            card, height=110, font=("JetBrains Mono", 11), wrap="word",
            fg_color=T.BG_INPUT, text_color=T.TEXT,
            border_color=T.BORDER, border_width=1,
            corner_radius=6,
            scrollbar_button_color=T.SAKURA_DIM,
        )
        self.prompt_box.grid(row=0, column=0, padx=T.CARD_PAD_X, pady=(T.CARD_PAD_Y, 4), sticky="ew")

        self.load_btn = ctk.CTkButton(
            card, text="Load from File", width=110, height=24,
            fg_color="transparent", hover_color=T.BG_HOVER,
            border_color=T.BORDER_MID, border_width=1,
            text_color=T.TEXT_DIM, font=("JetBrains Mono", 10),
            corner_radius=4,
            command=self._load_file,
        )
        self.load_btn.grid(row=1, column=0, padx=T.CARD_PAD_X, pady=(0, T.CARD_PAD_Y), sticky="w")

        # ── Working Directory ─────────────────────────
        card, r = _make_section(self, r, "WORKING DIRECTORY")

        self.workdir_entry = ctk.CTkEntry(
            card, placeholder_text="/path/to/project (optional)",
            fg_color=T.BG_INPUT, text_color=T.TEXT,
            border_color=T.BORDER, border_width=1,
            corner_radius=6,
            font=("JetBrains Mono", 11),
        )
        self.workdir_entry.grid(row=0, column=0, padx=T.CARD_PAD_X, pady=(T.CARD_PAD_Y, 4), sticky="ew")

        self.workdir_btn = ctk.CTkButton(
            card, text="Browse", width=70, height=24,
            fg_color="transparent", hover_color=T.BG_HOVER,
            border_color=T.BORDER_MID, border_width=1,
            text_color=T.TEXT_DIM, font=("JetBrains Mono", 10),
            corner_radius=4,
            command=self._browse_dir,
        )
        self.workdir_btn.grid(row=1, column=0, padx=T.CARD_PAD_X, pady=(0, T.CARD_PAD_Y), sticky="w")

        # ── Limits Section ────────────────────────────
        card, r = _make_section(self, r, "LIMITS")

        limits = [
            ("Iterations", "iter_entry", str(settings.max_iterations), "10"),
            ("Max Cost ($)", "cost_entry",
             str(settings.max_cost_usd) if settings.max_cost_usd else "", "0 = no limit"),
            ("Duration (min)", "duration_entry",
             str(settings.max_duration_secs // 60) if settings.max_duration_secs else "", "0 = no limit"),
        ]

        for i, (label, attr, default_val, placeholder) in enumerate(limits):
            row_frame = ctk.CTkFrame(card, fg_color="transparent")
            row_frame.grid(row=i, column=0, padx=T.CARD_PAD_X,
                           pady=(T.CARD_PAD_Y if i == 0 else 2,
                                 T.CARD_PAD_Y if i == len(limits) - 1 else 2),
                           sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row_frame, text=label, width=100, anchor="w",
                text_color=T.TEXT_DIM, font=("JetBrains Mono", 10),
            ).grid(row=0, column=0, sticky="w")

            entry = ctk.CTkEntry(
                row_frame, width=80, placeholder_text=placeholder,
                fg_color=T.BG_INPUT, text_color=T.TEXT,
                border_color=T.BORDER, border_width=1,
                corner_radius=4,
                font=("JetBrains Mono", 11),
            )
            if default_val:
                entry.insert(0, default_val)
            entry.grid(row=0, column=1, sticky="w")
            setattr(self, attr, entry)

        # ── Control Buttons ───────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=r, column=0, padx=10, pady=(T.SECTION_GAP + 4, 14), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)
        r += 1

        self.start_btn = ctk.CTkButton(
            btn_frame, text="\u2692  FORGE", height=40,
            fg_color=T.GOLD, hover_color=T.GOLD_BRIGHT,
            text_color=T.BG_DARK,
            font=("JetBrains Mono", 13, "bold"),
            corner_radius=6,
            command=self._on_start_click,
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="\u2587  QUENCH", height=40,
            fg_color=T.RED_DIM, hover_color=T.RED,
            text_color=T.TEXT_DIM,
            font=("JetBrains Mono", 13, "bold"),
            corner_radius=6,
            state="disabled",
            command=self._on_stop_click,
        )
        self.stop_btn.grid(row=0, column=1, padx=(4, 0), sticky="ew")

    # ── Public API ────────────────────────────────────

    def get_selected_agents(self) -> list[str]:
        return [name for name, var in self._agent_vars.items() if var.get()]

    def get_prompt(self) -> str:
        return self.prompt_box.get("1.0", "end").strip()

    def get_mode(self) -> str:
        return self.mode_var.get()

    def get_max_iterations(self) -> int:
        try:
            return int(self.iter_entry.get())
        except ValueError:
            return 10

    def get_max_cost(self) -> float:
        try:
            return float(self.cost_entry.get())
        except ValueError:
            return 0.0

    def get_max_duration_secs(self) -> int:
        try:
            return int(self.duration_entry.get()) * 60
        except ValueError:
            return 0

    def get_working_dir(self) -> str:
        return self.workdir_entry.get().strip()

    def set_running(self, running: bool):
        if running:
            self.start_btn.configure(state="disabled", fg_color=T.GOLD_DIM)
            self.stop_btn.configure(state="normal", fg_color=T.RED, text_color="#FFFFFF")
        else:
            self.start_btn.configure(state="normal", fg_color=T.GOLD)
            self.stop_btn.configure(state="disabled", fg_color=T.RED_DIM, text_color=T.TEXT_DIM)

    # ── Private ───────────────────────────────────────

    def _on_start_click(self):
        self._on_start()

    def _on_stop_click(self):
        self._on_stop()

    def _load_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text/Markdown", "*.txt *.md"), ("All", "*.*")])
        if path:
            try:
                with open(path) as f:
                    content = f.read()
                self.prompt_box.delete("1.0", "end")
                self.prompt_box.insert("1.0", content)
            except OSError:
                pass

    def _browse_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.workdir_entry.delete(0, "end")
            self.workdir_entry.insert(0, d)

    # ── Setter API (for session save/restore) ────────

    def set_agents(self, agents: list[str]):
        for name, var in self._agent_vars.items():
            var.set(name in agents)

    def set_mode(self, mode: str):
        self.mode_var.set(mode)

    def set_prompt(self, text: str):
        self.prompt_box.delete("1.0", "end")
        if text:
            self.prompt_box.insert("1.0", text)

    def set_working_dir(self, path: str):
        self.workdir_entry.delete(0, "end")
        if path:
            self.workdir_entry.insert(0, path)

    def set_limits(self, iterations: int, cost: float, duration_secs: int):
        self.iter_entry.delete(0, "end")
        self.iter_entry.insert(0, str(iterations))
        self.cost_entry.delete(0, "end")
        if cost:
            self.cost_entry.insert(0, str(cost))
        self.duration_entry.delete(0, "end")
        if duration_secs:
            self.duration_entry.insert(0, str(duration_secs // 60))
