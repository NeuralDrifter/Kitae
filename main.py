#!/usr/bin/env python3
# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Kitae — Forge. Fold. Refine. Repeat."""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.splash import show_splash


def main():
    show_splash()


if __name__ == "__main__":
    main()
