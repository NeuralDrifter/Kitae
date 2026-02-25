# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Kitae color theme — Japanese swordsmith aesthetic.

Palette pulled from the splash art:
  - Cherry blossom pink accents
  - Warm gold for headers/titles
  - Soft charcoal-slate backgrounds
  - Ember orange for forge glow
  - Muted sage green undertones
"""

# Backgrounds — warm slate, not pure black
BG_DARK = "#131316"          # Main background (deep)
BG_PANEL = "#1A1A20"         # Side panel, status bar
BG_CARD = "#1F1F27"          # Card/section containers
BG_INPUT = "#262630"         # Text inputs, text boxes
BG_HOVER = "#2E2E3A"         # Hover states
BG_ELEVATED = "#343440"      # Elevated elements (active tabs, highlights)

# Cherry blossom pink (primary accent)
SAKURA = "#D4A0A0"           # Muted cherry blossom
SAKURA_BRIGHT = "#E8B4B4"    # Lighter pink for hover/active
SAKURA_DIM = "#8B6B6B"       # Desaturated for borders/scrollbars
SAKURA_GLOW = "#D4A0A030"    # Translucent for subtle glows

# Warm gold (headers, titles)
GOLD = "#C9A84C"
GOLD_BRIGHT = "#DEC06A"
GOLD_DIM = "#8B7A3A"
GOLD_SUBTLE = "#C9A84C18"    # Very faint gold tint

# Ember orange (forge fire)
EMBER = "#D4743A"
EMBER_HOVER = "#C0652E"
EMBER_DIM = "#8B5228"

# Text
TEXT = "#D8D4CF"             # Warm off-white (parchment tone)
TEXT_DIM = "#8A8680"         # Muted warm gray
TEXT_MUTED = "#5A5753"       # Very muted
TEXT_FAINT = "#3E3C3A"       # Barely visible (decorative)

# Status
GREEN = "#7BA87B"            # Sage green (garden) — available
GREEN_DIM = "#4A6B4A"       # Dim green — indicator dot bg
RED = "#C45B5B"              # Muted red — stop/error
RED_DIM = "#7B3A3A"

# Borders — warm gray
BORDER = "#2A2A34"           # Subtle
BORDER_MID = "#3A3A44"       # Medium
BORDER_BRIGHT = "#4A4A56"   # Prominent

# Spacing constants (px)
CARD_PAD_X = 10
CARD_PAD_Y = 8
CARD_RADIUS = 8
SECTION_GAP = 12
SIDEBAR_WIDTH = 270
