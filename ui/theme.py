"""
theme.py — Luminax Sorter shared design tokens ("Industrial Console" theme v2)
─────────────────────────────────────────────────────────────────────────────
Restyled to match a reference HMI: true charcoal base with LIGHTER elevated
cards (not "card slightly darker than bg"), soft desaturated sage-mint accent,
donut-gauge data viz instead of flat stat boxes, rounded icon chips.

Place at: ui/theme.py
Import from ui/* files as: from ui.theme import (...)

No logic changes anywhere — pure styling/token module.
"""

# ── Base surfaces — true charcoal, NOT blue/green tinted ──────────────────
BG_BASE   = "#1D1C1C"   # window background
BG_CARD   = "#060607"   # elevated card — LIGHTER than base (key reference trait)
BG_CARD_HI = "#07090C"  # hover/raised state of a card
BG_DEEP   = "#0F1113"   # recessed wells (inputs, feed, sunken chrome)
BG_RAISED = "#1C1F23"   # header bar — between base and card

# ── Borders ─────────────────────────────────────────────────────────────
BORDER    = "#34383E"
BORDER_LO = "#262932"
BORDER_HI = "#454A52"

# ── Text ────────────────────────────────────────────────────────────────
TXT_BRIGHT = "#F4F6F5"
TXT_MID    = "#9DA5A8"
TXT_DIM    = "#5E6569"

# ── Brand / accent — soft desaturated sage-mint (reference accent) ────────
BRAND      = "#59DA9E"   # soft sage-mint — primary accent, used with restraint
BRAND_HI   = "#5CB389"
BRAND_DIM  = "#57AA86"
BRAND_TRACK = "#3A4540"  # the dim background arc of a donut gauge

# ── Semantic state colors ──────────────────────────────────────────────
GREEN     = "#5AB98D"   # running / healthy — same family as brand for cohesion
GREEN_D   = "#51A781"
AMBER     = "#CAA356"   # caution / weighing — soft, not neon
BLUE      = "#629DC5"   # info / sorting / transit — soft sky
RED       = "#CF6A6A"   # alert / stop — soft coral, not fire-engine
GREY      = "#95A1A5"

# ── Fonts ───────────────────────────────────────────────────────────────
FONT_LABEL   = "'Inter', 'Segoe UI Semibold', 'Oswald', sans-serif"
FONT_MONO    = "'JetBrains Mono', 'IBM Plex Mono', monospace"
FONT_DISPLAY = "'Inter', 'Segoe UI', sans-serif"   # big numbers — clean grotesk, not mono


def card_qss(radius: int = 14, bg: str = BG_CARD, border: str = BORDER) -> str:
    """Standard elevated-card style — lighter than base, generously rounded."""
    return (
        f"QFrame {{"
        f"  background: {bg};"
        f"  border: 1px solid {border};"
        f"  border-radius: {radius}px;"
        f"}}"
    )


def pill_button_qss(bg: str = BRAND, text: str = BG_BASE, radius: int = 10) -> str:
    """Solid rounded pill button — bottom command-bar style."""
    hover = BRAND_HI if bg == BRAND else bg
    press = BRAND_DIM if bg == BRAND else bg
    return f"""
        QPushButton {{
            background: {bg};
            color: {text};
            border: none;
            border-radius: {radius}px;
            font-family: {FONT_LABEL};
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 1px;
            padding: 8px 16px;
        }}
        QPushButton:hover {{
            background: {hover};
        }}
        QPushButton:pressed {{
            background: {press};
        }}
        QPushButton:disabled {{
            background: {BG_CARD_HI};
            color: {TXT_DIM};
        }}
    """


def outline_button_qss(border_col: str, text_col: str = None,
                        bg: str = BG_CARD, radius: int = 10) -> str:
    """Soft outline button — secondary actions (HOME/TRAY/SCALE etc)."""
    text_col = text_col or border_col
    return f"""
        QPushButton {{
            background: {bg};
            border: 1.5px solid {border_col};
            border-radius: {radius}px;
            color: {text_col};
            font-size: 11px;
            font-weight: 600;
            font-family: {FONT_LABEL};
            letter-spacing: 1px;
            padding: 6px 10px;
        }}
        QPushButton:hover {{
            background: {border_col};
            color: {BG_BASE};
        }}
        QPushButton:pressed {{
            background: {border_col}CC;
            color: {BG_BASE};
        }}
        QPushButton:disabled {{
            background: {BG_CARD};
            border: 1.5px solid {BORDER};
            color: {TXT_DIM};
        }}
    """