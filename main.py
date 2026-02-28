#!/usr/bin/env python3
# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Kitae — Forge. Fold. Refine. Repeat."""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    skip = os.environ.get("KITAE_NO_SPLASH", "")
    if not skip:
        try:
            from gui.splash import show_splash
            show_splash()
            return
        except ImportError:
            pass
    # Fallback: launch app directly
    from gui.app import AgentLoopApp
    app = AgentLoopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
