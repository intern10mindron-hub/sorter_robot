from __future__ import annotations
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QTabWidget, QTableWidget,
                              QTableWidgetItem, QScrollArea, QGridLayout,
                              QFrame, QHeaderView)
from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from config import TOTAL_SLOTS, WEIGHT_COLORS, PANEL_WIDTH
from core.slot_manager import SlotManager
from core.session import Session
from core.workflow import State, STATE_INFO
from ui.setup_panel import SetupPanel
from ui.donut_gauge import DonutGauge

# ── Industrial Console palette (shared with camera_panel / telemetry_bar) ─────
from ui.theme import (
    BG_BASE, BG_CARD, BG_CARD_HI, BG_DEEP, BG_RAISED,
    BORDER, BORDER_LO, BORDER_HI,
    TXT_DIM as C_DIM, TXT_MID as C_MID, TXT_BRIGHT as C_BRIGHT,
    GREEN as C_GREEN, GREEN_D as C_GREEN_D,
    BLUE as C_BLUE, AMBER as C_AMBER, RED as C_RED,
    BRAND, BRAND_HI, BRAND_DIM, BRAND_TRACK,
    FONT_LABEL, FONT_MONO, FONT_DISPLAY,
    card_qss, outline_button_qss, pill_button_qss,
)
C_PURPLE = "#B8A8E0"   # unused-but-kept palette slot for parity with original


# ── Slot name mapping ─────────────────────────────────────────────────────────

SLOT_LAYOUT = [
    ["A1","A2","A3","A4","A5"],
    ["B1","B2","B3","B4","B5","B6"],
    ["C1","C2","C3","C4","C5"],
    ["D1","D2","D3","D4","D5","D6"],
    ["E1","E2","E3","E4","E5","E6"],
    ["F1","F2","F3","F4","F5"],
    ["F6","F7","F8","F9","F10"],
    ["G1","G2","G3","G4","G5"],
    ["G6","G7","G8","G9","G10"],
    ["H1","H2","H3","H4"],
    ["H5","H6","H7","H8"],
    ["I1","I2","I3","I4","I5","I6"],
    ["J1","J2","J3","J4"],
]

SLOT_NAMES = [name for row in SLOT_LAYOUT for name in row]
SUBROW2_FIRST = {"F6", "G6", "H5"}
_TOTAL_SLOT_COUNT = len(SLOT_NAMES)

def _pill_label(text: str, color: str = C_DIM) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size: 10px; letter-spacing: 1.5px; color: {color};"
        f"font-family: {FONT_LABEL};"
        "font-weight: 600; border: none; background: transparent;"
        "text-transform: uppercase;"
    )
    return lbl

# ── Small toggle switch widget — soft rounded pill (reference style) ──────────
class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, initial: bool = False, parent=None):
        super().__init__(parent)
        self._on = initial
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, _):
        self._on = not self._on
        self.toggled.emit(self._on)
        self.update()

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QColor, QPainterPath
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        track = self._track_path()
        if self._on:
            p.fillPath(track, QColor(BRAND))
        else:
            p.fillPath(track, QColor(BG_DEEP))
        p.setPen(QColor(BRAND) if self._on else QColor(BORDER_HI))
        p.drawPath(track)

        knob_x = 22 if self._on else 2
        knob_color = QColor(BG_BASE) if self._on else QColor(C_DIM)
        p.setBrush(knob_color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(knob_x, 2, 20, 20)
        p.end()

    def _track_path(self):
        from PyQt5.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(0, 0, 44, 24, 12, 12)
        return path

    def is_on(self) -> bool:
        return self._on

    def set_state(self, on: bool):
        if self._on != on:
            self._on = on
            self.update()

class ControlPanel(QWidget):
    slot_panel_selected      = pyqtSignal(int)
    export_clicked           = pyqtSignal()
    slot_selected_for_sort   = pyqtSignal(int)
    viewer_slot_mode_changed = pyqtSignal(bool)
    viewer_grid_changed      = pyqtSignal(bool)
    viewer_autorot_changed   = pyqtSignal(bool)
    manual_mode_changed      = pyqtSignal(bool)   # ← ADDED
    speed_override_changed   = pyqtSignal(int)

    def __init__(self, slot_manager: SlotManager, session: Session, parent=None):
        super().__init__(parent)
        self.slot_manager = slot_manager
        self.session = session
        self._waiting_for_slot = False
        self._sorted_count = 0
        self.setFixedWidth(PANEL_WIDTH + 75)  # +75px ≈ 2cm extra width
        self.setAutoFillBackground(True)
        p = self.palette()
        from PyQt5.QtGui import QColor
        p.setColor(self.backgroundRole(), QColor(BG_BASE))
        self.setPalette(p)

        self.setStyleSheet(f"""
            ControlPanel, ControlPanel > QWidget {{
                background-color: {BG_BASE};
                color: {C_BRIGHT};
            }}
            QScrollArea {{
                background: {BG_BASE};
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: {BG_BASE};
            }}
            QScrollBar:vertical {{
                background: {BG_BASE};
                width: 5px;
                border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_HI};
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {BRAND};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QTabWidget::pane {{
                background: {BG_BASE};
                border: none;
                border-top: 1px solid {BORDER_LO};
            }}
            QTabBar {{
                background: {BG_BASE};
            }}
            QTabBar::tab {{
                background: {BG_BASE};
                color: {C_DIM};
                font-family: {FONT_LABEL};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1px;
                padding: 12px 16px;
                border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {BRAND};
                background: {BG_BASE};
                border-bottom: 2px solid {BRAND};
            }}
            QTabBar::tab:hover:!selected {{
                color: {C_MID};
            }}
            QLabel {{
                color: {C_BRIGHT};
                background: transparent;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        lay.addWidget(self._tabs)

        self._tabs.addTab(self._make_workflow_tab(), "FLOW")
        self._tabs.addTab(self._make_slots_tab(),    "SLOTS PRESET")
        self._tabs.addTab(self._make_log_tab(),      "LOG")
        self.setup_tab = SetupPanel(parent.robot)
        self._tabs.addTab(self.setup_tab,     "SETUP")

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 11px; letter-spacing: 1.5px; color: {C_MID};"
            f"font-family: {FONT_LABEL};"
            "font-weight: 600; border: none; background: transparent;"
        )
        return lbl

    def _divider(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setFixedHeight(1)
        f.setStyleSheet(f"background: {BORDER_LO}; border: none;")
        return f

    def _card_header_row(self, text: str, extra_widget: QWidget = None) -> QWidget:
        """Plain text-label header row (no accent tab) — matches reference's
        quiet uppercase section labels with no decorative left bar."""
        hdr = QWidget()
        hdr.setStyleSheet("background: transparent; border: none;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(18, 16, 18, 4)
        hl.setSpacing(10)
        hl.addWidget(self._section_label(text))
        hl.addStretch()
        if extra_widget is not None:
            hl.addWidget(extra_widget)
        return hdr

    # ── WORKFLOW TAB ──────────────────────────────────────────────────────────
    def _make_workflow_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_BASE}; }}")

        inner = QWidget()
        inner.setStyleSheet(f"background: {BG_BASE};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(14, 16, 14, 16)
        lay.setSpacing(12)

        # ── State card — light elevated card, no accent stripe ────────────────
        state_card = QFrame()
        state_card.setStyleSheet(card_qss(radius=16))
        sc_lay = QVBoxLayout(state_card)
        sc_lay.setContentsMargins(20, 16, 20, 18)
        sc_lay.setSpacing(6)

        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 0, 0, 0)
        hdr_row.addWidget(self._section_label("CURRENT STATE"))

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(
            f"font-size: 10px; color: {C_GREEN}; border: none; background: transparent;"
        )
        hdr_row.addStretch()
        hdr_row.addWidget(self._status_dot)
        sc_lay.addLayout(hdr_row)

        self._state_name = QLabel("IDLE")
        self._state_name.setStyleSheet(
            f"font-size: 28px; color: {C_BRIGHT};"
            f"font-family: {FONT_DISPLAY};"
            "font-weight: 700; letter-spacing: 0.5px; border: none; background: transparent;"
        )
        self._state_sub = QLabel("Waiting to start")
        self._state_sub.setStyleSheet(
            f"font-size: 12px; color: {C_DIM};"
            f"font-family: {FONT_LABEL};"
            "border: none; background: transparent; line-height: 1.5;"
        )
        self._state_sub.setWordWrap(True)
        sc_lay.addSpacing(2)
        sc_lay.addWidget(self._state_name)
        sc_lay.addWidget(self._state_sub)
        lay.addWidget(state_card)

        # ── Hero progress card — donut gauges (reference's OEE/Cycle moment) ──
        lay.addWidget(self._make_gauge_card())

        # ── Operating Mode card ───────────────────────────────────────────────
        lay.addWidget(self._make_mode_card())

        # ── Viewer Controls card ──────────────────────────────────────────────
        lay.addWidget(self._make_viewer_controls())

        lay.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _make_gauge_card(self) -> QFrame:
        """
        Donut-gauge card — SORTED progress (sorted/66) as a ring, like the
        reference's OEE gauge, plus small numeric readouts for TOTAL/AVG ct
        beside it (kept as text since those aren't ratios — a gauge would
        be meaningless for an open-ended weight total).
        """
        card = QFrame()
        card.setStyleSheet(card_qss(radius=16))
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 16)
        cl.setSpacing(0)

        cl.addWidget(self._card_header_row("PROGRESS"))

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        bl = QHBoxLayout(body)
        bl.setContentsMargins(18, 8, 18, 0)
        bl.setSpacing(18)

        self._gauge_sorted = DonutGauge(
            "Sorted", value_text="0",color=BRAND, diameter=110, thickness=10
        )
        bl.addWidget(self._gauge_sorted)

        # Slot / Total ct / Avg ct as quiet inline stat rows beside the ring —
        # generous spacing instead of boxed cards, matching reference rhythm
        side = QWidget()
        side.setStyleSheet("background: transparent;")
        sv = QVBoxLayout(side)
        sv.setContentsMargins(4, 6, 0, 6)
        sv.setSpacing(10)

        self._stat_left  = self._inline_stat("Current slot", "—",  C_BLUE)
        self._stat_total = self._inline_stat("Total carats", "0.00",  C_BRIGHT)
        self._stat_avg   = self._inline_stat("Average ct",   "0.000", C_BRIGHT)
        for row in (self._stat_left, self._stat_total, self._stat_avg):
            sv.addWidget(row)
        sv.addStretch()

        bl.addWidget(side, stretch=1)
        cl.addWidget(body)
        return card

    def _inline_stat(self, label: str, value: str, val_col: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size: 11px; color: {C_DIM};"
            f"font-family: {FONT_LABEL}; border: none; background: transparent;"
        )
        val = QLabel(value)
        val.setObjectName("statval")
        val.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {val_col};"
            f"font-family: {FONT_DISPLAY}; border: none; background: transparent;"
        )
        rl.addWidget(lbl)
        rl.addStretch()
        rl.addWidget(val)
        return row

    # ========== NEW METHOD ==========
    def _make_mode_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(card_qss(radius=16))
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 4)
        cl.setSpacing(2)

        # ── AUTO MODE row ──────────────────────────────────────────────────────
        self._auto_indicator = QLabel("● AUTO")
        self._auto_indicator.setStyleSheet(
            f"font-size: 10px; color: {C_GREEN}; font-weight: 700;"
            f"font-family: {FONT_LABEL};"
            "border: none; background: transparent; letter-spacing: 1px;"
        )
        cl.addWidget(self._card_header_row("OPERATING MODE", extra_widget=self._auto_indicator))

        # ── MANUAL OVERRIDE row ───────────────────────────────────────────────
        manual_row = QWidget()
        manual_row.setStyleSheet("background: transparent; border: none;")
        ml = QHBoxLayout(manual_row)
        ml.setContentsMargins(18, 8, 18, 4)
        ml.setSpacing(10)

        manual_lbl = QLabel("Manual override")
        manual_lbl.setStyleSheet(
            f"font-size: 13px; color: {C_BRIGHT};"
            f"font-family: {FONT_LABEL};"
            "border: none; background: transparent;"
        )
        self._manual_mode_lbl = QLabel("OFF")
        self._manual_mode_lbl.setStyleSheet(
            f"font-size: 10px; color: {C_DIM}; font-weight: 700;"
            f"font-family: {FONT_LABEL};"
            "border: none; background: transparent; letter-spacing: 1px;"
        )
        self._tog_manual = ToggleSwitch(initial=False)
        self._tog_manual.toggled.connect(self._on_manual_override)

        ml.addWidget(manual_lbl)
        ml.addStretch()
        ml.addWidget(self._manual_mode_lbl)
        ml.addSpacing(8)
        ml.addWidget(self._tog_manual)
        cl.addWidget(manual_row)

        # ── Hint text ─────────────────────────────────────────────────────────
        hint_row = QWidget()
        hint_row.setStyleSheet("background: transparent; border: none;")
        hl = QHBoxLayout(hint_row)
        hl.setContentsMargins(18, 0, 18, 14)
        self._mode_hint = QLabel("Auto mode active — robot sorts automatically")
        self._mode_hint.setStyleSheet(
            f"font-size: 10px; color: {C_DIM};"
            f"font-family: {FONT_LABEL};"
            "border: none; background: transparent;"
        )
        hl.addWidget(self._mode_hint)
        cl.addWidget(hint_row)

        return card

    # ========== NEW METHOD ==========
    def _on_manual_override(self, on: bool):
        """Toggle manual override — emits signal to main_window."""
        self._manual_mode_lbl.setText("ON" if on else "OFF")

        if on:
            self._manual_mode_lbl.setStyleSheet(
                f"font-size: 10px; color: {C_AMBER}; font-weight: 700;"
                f"font-family: {FONT_LABEL};"
                "border: none; background: transparent; letter-spacing: 1px;"
            )
            self._auto_indicator.setText("○ AUTO")
            self._auto_indicator.setStyleSheet(
                f"font-size: 10px; color: {C_DIM}; font-weight: 700;"
                f"font-family: {FONT_LABEL};"
                "border: none; background: transparent; letter-spacing: 1px;"
            )
            self._mode_hint.setText("Manual override — operator controls each pick")
        else:
            self._manual_mode_lbl.setStyleSheet(
                f"font-size: 10px; color: {C_DIM}; font-weight: 700;"
                f"font-family: {FONT_LABEL};"
                "border: none; background: transparent; letter-spacing: 1px;"
            )
            self._auto_indicator.setText("● AUTO")
            self._auto_indicator.setStyleSheet(
                f"font-size: 10px; color: {C_GREEN}; font-weight: 700;"
                f"font-family: {FONT_LABEL};"
                "border: none; background: transparent; letter-spacing: 1px;"
            )
            self._mode_hint.setText("Auto mode active — robot sorts automatically")

        self.manual_mode_changed.emit(on)

    def _make_viewer_controls(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(card_qss(radius=16))
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 4)
        cl.setSpacing(2)

        # Header row — Slot Select Mode
        self._tog_slot = ToggleSwitch(initial=False)
        self._tog_slot.toggled.connect(self._on_slot_mode)
        self._slot_mode_lbl = QLabel("OFF")
        self._slot_mode_lbl.setStyleSheet(
            f"font-size: 10px; color: {C_DIM};"
            f"font-family: {FONT_LABEL};"
            "font-weight: 700; border: none; background: transparent; letter-spacing: 1px;"
        )
        slot_mode_extra = QWidget()
        sme = QHBoxLayout(slot_mode_extra)
        sme.setContentsMargins(0, 0, 0, 0)
        sme.setSpacing(8)
        sme.addWidget(self._slot_mode_lbl)
        sme.addWidget(self._tog_slot)
        cl.addWidget(self._card_header_row("SLOT SELECT MODE", extra_widget=slot_mode_extra))

        cl.addSpacing(6)

        # Display options sub-header
        disp_lbl = QLabel("DISPLAY OPTIONS")
        disp_lbl.setStyleSheet(
            f"font-size: 9px; letter-spacing: 1.5px; color: {C_DIM};"
            f"font-family: {FONT_LABEL};"
            "font-weight: 600; border: none; background: transparent;"
        )
        disp_wrap = QWidget()
        disp_wrap.setStyleSheet("background: transparent;")
        dwl = QHBoxLayout(disp_wrap)
        dwl.setContentsMargins(18, 6, 18, 6)
        dwl.addWidget(disp_lbl)
        cl.addWidget(disp_wrap)

        # Grid row
        grid_row = self._toggle_row("Grid", initial=True)
        self._tog_grid, _ = grid_row
        self._tog_grid.toggled.connect(self._on_grid)
        cl.addWidget(self._toggle_row_widget("Grid", self._tog_grid))

        # Auto-rotate row
        self._tog_autorot = ToggleSwitch(initial=False)
        self._tog_autorot.toggled.connect(self._on_autorot)
        cl.addWidget(self._toggle_row_widget("Auto-rotate", self._tog_autorot))

        # Robot speed row
        cl.addWidget(self._speed_row_widget())
        cl.addSpacing(8)

        return card

    def _toggle_row(self, label: str, initial: bool = False):
        tog = ToggleSwitch(initial=initial)
        return tog, label

    def _toggle_row_widget(self, label: str, toggle: ToggleSwitch) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent; border: none;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(18, 6, 18, 6)
        rl.setSpacing(0)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size: 13px; color: {C_BRIGHT};"
            f"font-family: {FONT_LABEL};"
            "border: none; background: transparent;"
        )
        rl.addWidget(lbl)
        rl.addStretch()
        rl.addWidget(toggle)
        return row

    def _speed_row_widget(self) -> QWidget:
        from PyQt5.QtWidgets import QComboBox
        row = QWidget()
        row.setStyleSheet("background: transparent; border: none;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(18, 6, 18, 6)
        rl.setSpacing(0)

        lbl = QLabel("Robot speed")
        lbl.setStyleSheet(
            f"font-size: 13px; color: {C_BRIGHT};"
            f"font-family: {FONT_LABEL};"
            "border: none; background: transparent;"
        )

        self._speed_combo = QComboBox()
        self._speed_combo.setFixedWidth(84)
        for v in range(10, 110, 10):
            self._speed_combo.addItem(f"{v}%", v)

        self._speed_combo.setCurrentIndex(5)  # 60% default

        self._speed_combo.setStyleSheet(f"""
            QComboBox {{
                background: {BG_DEEP};
                border: 1px solid {BORDER_HI};
                border-radius: 8px;
                color: {BRAND};
                font-family: {FONT_LABEL};
                font-size: 11px;
                font-weight: 700;
                padding: 4px 8px;
            }}
            QComboBox:hover {{
                border-color: {BRAND};
            }}
            QComboBox QAbstractItemView {{
                background: {BG_CARD_HI};
                border: 1px solid {BORDER_HI};
                color: {C_BRIGHT};
                selection-background-color: rgba(143,217,182,0.18);
                selection-color: {BRAND};
                font-family: {FONT_LABEL};
                font-size: 11px;
            }}
        """)

        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        rl.addWidget(lbl)
        rl.addStretch()
        rl.addWidget(self._speed_combo)
        return row

    def _on_speed_changed(self, index: int):
        value = self._speed_combo.itemData(index)
        if value is not None:
            self.speed_override_changed.emit(int(value))

    # ── Viewer control slots ──────────────────────────────────────────────────

    def _on_slot_mode(self, on: bool):
        self._slot_mode_lbl.setText("ON" if on else "OFF")
        color = C_GREEN if on else C_DIM
        self._slot_mode_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {color};"
            f"font-family: {FONT_LABEL};"
            "border: none; background: transparent; letter-spacing: 1px;"
        )
        self.viewer_slot_mode_changed.emit(on)

    def _on_grid(self, on: bool):
        self.viewer_grid_changed.emit(on)

    def _on_autorot(self, on: bool):
        self.viewer_autorot_changed.emit(on)

    def _open_weight_range_editor(self):
        """Open dialog to let operator edit weight ranges."""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                    QDoubleSpinBox, QLabel, QPushButton,
                                    QScrollArea, QWidget, QFrame)
        from config import DEFAULT_WEIGHT_RANGES, WEIGHT_RANGES_FILE
        import json

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Weight Ranges")
        dlg.setMinimumSize(420, 520)
        dlg.setStyleSheet(f"""
            QDialog {{
                background: {BG_BASE};
                color: {C_BRIGHT};
            }}
            QLabel {{
                color: {C_BRIGHT};
                background: transparent;
            }}
            QDoubleSpinBox {{
                background: {BG_CARD};
                border: 1px solid {BORDER_HI};
                border-radius: 8px;
                color: {C_BRIGHT};
                padding: 3px 6px;
                font-family: {FONT_MONO};
                font-size: 11px;
            }}
            QDoubleSpinBox:focus {{ border-color: {BRAND}; }}
            QPushButton {{
                background: {BG_CARD};
                border: 1px solid {BORDER_HI};
                border-radius: 8px;
                color: {C_MID};
                font-family: {FONT_LABEL};
                font-size: 10px;
                letter-spacing: 1px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                border-color: {BRAND};
                color: {BRAND};
                background: rgba(143,217,182,0.08);
            }}
        """)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        title = QLabel("WEIGHT RANGES  —  66 SLOTS")
        title.setStyleSheet(
            f"font-size: 11px; letter-spacing: 1.5px; color: {C_DIM};"
            f"font-family: {FONT_LABEL}; font-weight: 600;"
        )
        lay.addWidget(title)

        hint = QLabel("Each slot sorts diamonds within its min–max range.")
        hint.setStyleSheet(f"font-size: 11px; color: {C_MID};")
        lay.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        inner = QWidget()
        inner.setStyleSheet(f"background: {BG_BASE};")
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 4, 0)
        il.setSpacing(4)

        current_ranges = list(DEFAULT_WEIGHT_RANGES)
        if os.path.exists(WEIGHT_RANGES_FILE):
            try:
                with open(WEIGHT_RANGES_FILE) as f:
                    current_ranges = json.load(f)
            except Exception:
                pass

        spin_pairs = []

        for i, r in enumerate(current_ranges):
            name = SLOT_NAMES[i] if i < len(SLOT_NAMES) else f"S{i+1}"
            col  = WEIGHT_COLORS[i % len(WEIGHT_COLORS)]

            row_w = QWidget()
            row_w.setFixedHeight(34)
            row_w.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)

            slot_lbl = QLabel(name)
            slot_lbl.setFixedWidth(30)
            slot_lbl.setStyleSheet(
                f"font-size: 10px; color: {col}; font-weight: 700;"
                f"font-family: {FONT_MONO};"
            )

            min_spin = QDoubleSpinBox()
            min_spin.setRange(0.00, 9.99)
            min_spin.setDecimals(2)
            min_spin.setSingleStep(0.01)
            min_spin.setValue(r["min_ct"])
            min_spin.setFixedWidth(80)

            dash = QLabel("–")
            dash.setFixedWidth(12)
            dash.setStyleSheet(f"color: {C_DIM}; font-size: 12px;")

            max_spin = QDoubleSpinBox()
            max_spin.setRange(0.00, 9.99)
            max_spin.setDecimals(2)
            max_spin.setSingleStep(0.01)
            max_spin.setValue(r["max_ct"])
            max_spin.setFixedWidth(80)

            ct_lbl = QLabel("ct")
            ct_lbl.setStyleSheet(f"color: {C_DIM}; font-size: 10px;")

            rl.addWidget(slot_lbl)
            rl.addWidget(min_spin)
            rl.addWidget(dash)
            rl.addWidget(max_spin)
            rl.addWidget(ct_lbl)
            rl.addStretch()
            il.addWidget(row_w)
            spin_pairs.append((min_spin, max_spin))

        il.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        reset_btn = QPushButton("RESET DEFAULTS")
        save_btn  = QPushButton("SAVE")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(143,217,182,0.10);
                color: {BRAND};
                border: 1.5px solid {BRAND};
                border-radius: 8px;
                font-family: {FONT_LABEL};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background: rgba(143,217,182,0.20);
            }}
        """)

        def do_reset():
            from config import _build_default_ranges
            defaults = _build_default_ranges()
            for i, (mn, mx) in enumerate(spin_pairs):
                if i < len(defaults):
                    mn.setValue(defaults[i]["min_ct"])
                    mx.setValue(defaults[i]["max_ct"])

        def do_save():
            import os
            new_ranges = []
            for i, (mn, mx) in enumerate(spin_pairs):
                new_ranges.append({
                    "min_ct": round(mn.value(), 4),
                    "max_ct": round(mx.value(), 4),
                    "slot":   None
                })
            try:
                with open(WEIGHT_RANGES_FILE, "w") as f:
                    json.dump(new_ranges, f, indent=2)
            except Exception as e:
                print(f"[WeightRanges] Save failed: {e}")
                return
            for i, r in enumerate(new_ranges):
                self.slot_manager.configure_slot(i, r["min_ct"], r["max_ct"])
            self.refresh_slot_colors()
            dlg.accept()

        reset_btn.clicked.connect(do_reset)
        save_btn.clicked.connect(do_save)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)

        dlg.exec_()

    # ── SLOTS TAB ─────────────────────────────────────────────────────────────

    def _make_slots_tab(self) -> QWidget:
        from hardware.robot_controller import SLOT_ORDER as _ROBOT_ORDER
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_BASE}; }}")
        inner = QWidget()
        inner.setStyleSheet(f"background: {BG_BASE};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        lay.addWidget(self._section_label("SORTING BINS"))
        lay.addSpacing(6)

        grid_frame = QFrame()
        grid_frame.setStyleSheet(card_qss(radius=14))
        gf_lay = QVBoxLayout(grid_frame)
        gf_lay.setContentsMargins(12, 12, 12, 12)
        gf_lay.setSpacing(0)
        self._slot_cells = {}
        self._slot_index_to_name = {}
        self._selected_slot_name = None

        for idx, name in enumerate(SLOT_NAMES):
            self._slot_index_to_name[idx] = name

        prev_letter = None

        for row_names in SLOT_LAYOUT:
            if not row_names:
                continue

            current_letter = row_names[0][0]
            is_subrow2     = row_names[0] in SUBROW2_FIRST

            if prev_letter is not None and not is_subrow2:
                gap = QWidget()
                gap.setFixedHeight(6)
                gap.setStyleSheet("background: transparent;")
                gf_lay.addWidget(gap)

            if is_subrow2:
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setFixedHeight(1)
                sep.setStyleSheet(
                    f"background: {BORDER_LO}; border: none;"
                    "margin-left: 2px; margin-right: 2px;"
                )
                gf_lay.addWidget(sep)

            if not is_subrow2:
                row_hdr = QWidget()
                row_hdr.setFixedHeight(20)
                row_hdr.setStyleSheet("background: transparent;")
                rhl = QHBoxLayout(row_hdr)
                rhl.setContentsMargins(2, 2, 0, 0)
                rhl.setSpacing(0)
                lbl = QLabel(current_letter)
                lbl.setStyleSheet(
                    f"font-size: 9px; color: {C_DIM}; font-weight: 700;"
                    f"font-family: {FONT_MONO};"
                    "letter-spacing: 2px; border: none; background: transparent;"
                )
                rhl.addWidget(lbl)
                rhl.addStretch()
                gf_lay.addWidget(row_hdr)

            btn_row = QWidget()
            btn_row.setStyleSheet("background: transparent;")
            brl = QHBoxLayout(btn_row)
            brl.setContentsMargins(0, 1, 0, 3)
            brl.setSpacing(4)

            for name in row_names:
                idx       = SLOT_NAMES.index(name)
                robot_idx = _ROBOT_ORDER.index(name) if name in _ROBOT_ORDER else idx
                slot = self.slot_manager.slots[idx]
                btn  = QPushButton()
                btn.setFixedSize(42, 42)
                self._update_slot_btn_text(btn, name, slot)
                self._apply_slot_btn_style(btn, slot, selected=False)
                btn.clicked.connect(
                    lambda _, n=name, i=robot_idx: self._slot_panel_clicked(n, i)
                )
                brl.addWidget(btn)
                self._slot_cells[name] = btn
            brl.addStretch()
            gf_lay.addWidget(btn_row)
            prev_letter = current_letter

        lay.addWidget(grid_frame)

        # ── Weight ranges legend ──────────────────────────────────────────────

        legend = QFrame()
        legend.setStyleSheet(card_qss(radius=14))
        lg_lay = QVBoxLayout(legend)
        lg_lay.setContentsMargins(0, 0, 0, 12)
        lg_lay.setSpacing(0)

        edit_ranges_btn = QPushButton("EDIT")
        edit_ranges_btn.setFixedSize(52, 24)
        edit_ranges_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(143,217,182,0.10);
                color: {BRAND};
                border: 1.5px solid {BRAND};
                border-radius: 8px;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 1px;
                font-family: {FONT_LABEL};
            }}
            QPushButton:hover {{
                background: rgba(143,217,182,0.20);
            }}
        """)
        edit_ranges_btn.clicked.connect(self._open_weight_range_editor)
        lg_lay.addWidget(self._card_header_row("WEIGHT RANGES", extra_widget=edit_ranges_btn))
        lg_lay.addSpacing(6)

        ranges_scroll = QScrollArea()
        ranges_scroll.setWidgetResizable(True)
        ranges_scroll.setFixedHeight(180)
        ranges_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        ranges_inner = QWidget()
        ranges_inner.setStyleSheet("background: transparent;")
        ril = QVBoxLayout(ranges_inner)
        ril.setContentsMargins(18, 0, 12, 0)
        ril.setSpacing(2)

        from config import DEFAULT_WEIGHT_RANGES
        for i, r in enumerate(DEFAULT_WEIGHT_RANGES):
            lo   = r["min_ct"]
            hi   = r["max_ct"]
            name = SLOT_NAMES[i] if i < len(SLOT_NAMES) else f"S{i+1}"
            col  = WEIGHT_COLORS[i % len(WEIGHT_COLORS)]

            row = QWidget()
            row.setFixedHeight(22)
            row.setStyleSheet("background: transparent; border: none;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)

            swatch = QFrame()
            swatch.setFixedSize(10, 10)
            swatch.setStyleSheet(
                f"background: {col}; border-radius: 5px; border: none;"
            )
            slot_lbl = QLabel(name)
            slot_lbl.setFixedWidth(28)
            slot_lbl.setStyleSheet(
                f"font-size: 9px; color: {col}; font-weight: 700;"
                f"font-family: {FONT_MONO}; border: none;"
            )
            range_lbl = QLabel(f"{lo:.2f} – {hi:.2f} ct")
            range_lbl.setStyleSheet(
                f"font-size: 10px; color: {C_MID};"
                f"font-family: {FONT_MONO}; border: none;"
            )
            rl.addWidget(swatch)
            rl.addWidget(slot_lbl)
            rl.addWidget(range_lbl)
            rl.addStretch()
            ril.addWidget(row)

        ril.addStretch()
        ranges_scroll.setWidget(ranges_inner)
        lg_lay.addWidget(ranges_scroll)
        lay.addWidget(legend)
        
        lay.addStretch()
        scroll.setWidget(inner)
        return scroll

    # ── LOG TAB ───────────────────────────────────────────────────────────────

    def _make_log_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {BG_BASE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(10)

        table_card = QFrame()
        table_card.setStyleSheet(card_qss(radius=14))
        tc_lay = QVBoxLayout(table_card)
        tc_lay.setContentsMargins(4, 4, 4, 4)

        self._log_table = QTableWidget(0, 4)
        self._log_table.setHorizontalHeaderLabels(["#", "WEIGHT ct", "SLOT", "TIME"])
        self._log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._log_table.verticalHeader().setVisible(False)
        self._log_table.setAlternatingRowColors(True)
        self._log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._log_table.setShowGrid(False)
        self._log_table.verticalHeader().setDefaultSectionSize(36)
        self._log_table.setStyleSheet(f"""
            QTableWidget {{
                background: {BG_CARD};
                alternate-background-color: {BG_CARD_HI};
                color: {C_MID};
                border: none;
                border-radius: 14px;
                font-family: {FONT_MONO};
                font-size: 10px;
            }}
            QTableWidget::item:selected {{
                background: rgba(143,217,182,0.12);
                color: {BRAND};
            }}
            QHeaderView::section {{
                background: {BG_CARD};
                color: {C_DIM};
                border: none;
                border-bottom: 1px solid {BORDER_LO};
                padding: 8px 4px;
                font-family: {FONT_LABEL};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1.5px;
            }}
        """)
        tc_lay.addWidget(self._log_table)
        lay.addWidget(table_card)

        export_btn = QPushButton("↓  EXPORT XLSX")
        export_btn.setObjectName("btnExport")
        export_btn.setFixedHeight(40)
        export_btn.setStyleSheet(pill_button_qss(bg=BRAND, text=BG_BASE, radius=10))
        export_btn.clicked.connect(self.export_clicked.emit)
        lay.addWidget(export_btn)
        return w

    def add_log_entry(self, diamond_id: str, weight_ct: float,
                  slot_index: int, timestamp: str):
        from hardware.robot_controller import SLOT_ORDER as _SLOT_ORDER
        slot_name = _SLOT_ORDER[slot_index] if slot_index < len(_SLOT_ORDER) else str(slot_index)
        row = self._log_table.rowCount()
        self._log_table.insertRow(row)
        for col, text in enumerate([
            str(row + 1), f"{weight_ct:.4f}", slot_name, timestamp
        ]):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            self._log_table.setItem(row, col, item)
        self._log_table.scrollToBottom()

    # ── PUBLIC UPDATE SLOTS ───────────────────────────────────────────────────
    def update_workflow_state(self, state: State):
        name, sub, code = STATE_INFO[state]
        state_cols = {
            "sc": C_BLUE,  "pk": C_GREEN,  "vb": C_AMBER,
            "wg": C_BLUE,  "sr": C_GREEN,  "al": C_RED,
            "id": C_DIM,   "ok": C_GREEN,  "pa": C_AMBER,
            "ws": C_AMBER,
        }

        col = state_cols.get(code, C_DIM)
        self._state_name.setText(name)
        self._state_name.setStyleSheet(
            f"font-size: 28px; color: {C_BRIGHT};"
            f"font-family: {FONT_DISPLAY};"
            "font-weight: 700; letter-spacing: 0.5px; border: none; background: transparent;"
        )
        self._state_sub.setText(sub)
        self._status_dot.setStyleSheet(
            f"font-size: 10px; color: {col}; border: none; background: transparent;"
        )

    def update_progress(self, sorted_count: int, total: int):
        self._sorted_count = sorted_count
        fraction = sorted_count / total if total else 0.0
        self._gauge_sorted.set_value(str(sorted_count), fraction=fraction)

    def update_current_slot(self, slot_name: str):
        """Update the inline 'Current slot' stat with destination slot (e.g. 'C1') or '—' when idle."""
        lbl = self._stat_left.findChild(QLabel, "statval")
        if lbl:
            is_active = slot_name != "—"
            col = C_BLUE if is_active else C_DIM
            lbl.setText(slot_name)
            lbl.setStyleSheet(
                f"font-size: 15px; font-weight: 700; color: {col};"
                f"font-family: {FONT_DISPLAY};"
                "border: none; background: transparent;"
            )

    def update_session_stats(self, total_ct: float, avg_ct: float):
        for card, val in [
            (self._stat_total, f"{total_ct:.2f}"),
            (self._stat_avg,   f"{avg_ct:.3f}")
        ]:
            lbl = card.findChild(QLabel, "statval")
            if lbl: lbl.setText(val)

    def refresh_slot_colors(self):
        for name, btn in self._slot_cells.items():
            idx  = SLOT_NAMES.index(name)
            slot = self.slot_manager.slots[idx]
            self._update_slot_btn_text(btn, name, slot)
            selected = (name == self._selected_slot_name)
            self._apply_slot_btn_style(btn, slot, selected=selected)

    def update_slot_from_viewer(self, slot_index: int, weight_val: float):
        """Update left side slot button color and text when weight assigned from 3D viewer"""
        name = self._slot_index_to_name.get(slot_index)
        if not name or name not in self._slot_cells:
            return

        btn = self._slot_cells[name]
        btn.setText(f"{name}\n{weight_val:.2f}")
        btn.setFont(QFont("IBM Plex Mono", 6))

        slot = self.slot_manager.slots[slot_index]
        selected = (name == self._selected_slot_name)
        self._apply_slot_btn_style(btn, slot, selected=selected)

    def _update_slot_btn_text(self, btn: QPushButton, name: str, slot):
        btn.setText(name)
        btn.setFont(QFont("IBM Plex Mono", 9))

    def _apply_slot_btn_style(self, btn: QPushButton, slot, selected: bool):
        if selected:
            border = f"2px solid {BRAND}"
        else:
            border = f"1px solid {BORDER_HI}"

        if slot.has_been_sorted:
            bg = slot.sorted_color
            fg = BG_BASE
        else:
            bg = BG_DEEP
            fg = C_DIM

        btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {fg};
                border-radius: 8px;
                border: {border};
                font-size: 9px;
                font-weight: 700;
                font-family: {FONT_MONO};
                padding: 2px 1px;
                text-align: center;
                line-height: 1.4;
            }}
            QPushButton:hover {{
                border: 1px solid {BRAND};
                background: rgba(143,217,182,0.12);
                color: {BRAND};
            }}
            QPushButton:pressed {{
                background: rgba(143,217,182,0.20);
            }}
        """)
    def _slot_panel_clicked(self, name: str, idx: int):
        if self._waiting_for_slot:
            self.slot_selected_for_sort.emit(idx)
        else:
            self.slot_panel_selected.emit(idx)

    def highlight_panel_slot(self, slot_index: int):
        """Called from MainWindow when 3D slot is clicked — highlights panel box."""
        name = self._slot_index_to_name.get(slot_index)
        if not name:
            return

        if self._selected_slot_name and self._selected_slot_name in self._slot_cells:
            prev_idx  = SLOT_NAMES.index(self._selected_slot_name)
            prev_slot = self.slot_manager.slots[prev_idx]
            self._apply_slot_btn_style(
                self._slot_cells[self._selected_slot_name],
                prev_slot, selected=False
            )

        self._selected_slot_name = name
        slot = self.slot_manager.slots[slot_index]
        self._apply_slot_btn_style(self._slot_cells[name], slot, selected=True)

        if name in self._slot_cells:
            self._slot_cells[name].setFocus()

    def set_waiting_for_slot(self, waiting: bool):
        """Enable slot selection mode — buttons glow accent-mint when waiting."""
        self._waiting_for_slot = waiting
        for name, btn in self._slot_cells.items():
            idx  = SLOT_NAMES.index(name)
            slot = self.slot_manager.slots[idx]
            if waiting:
                idx  = SLOT_NAMES.index(name)
                slot = self.slot_manager.slots[idx]
                self._update_slot_btn_text(btn, name, slot)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(143,217,182,0.08);
                        color: {BRAND};
                        border-radius: 8px;
                        border: 1px solid {BRAND};
                        font-size: 9px;
                        font-weight: 700;
                        font-family: {FONT_MONO};
                        padding: 2px 1px;
                        text-align: center;
                    }}
                    QPushButton:hover {{
                        border: 1px solid {BRAND};
                        background: rgba(143,217,182,0.20);
                        color: {BRAND};
                    }}
                """)
            else:
                self._apply_slot_btn_style(btn, slot, selected=False)

    def show_weight_on_slots(self, weight_ct: float):
        """Show measured weight on all slot buttons."""
        for name, btn in self._slot_cells.items():
            idx  = SLOT_NAMES.index(name)
            slot = self.slot_manager.slots[idx]
            self._update_slot_btn_text(btn, name, slot)
            
    def mark_slot_sorted(self, slot_name: str, weight_ct: float):
        """After a sort: show diamond count, weight and color on that slot."""
        from config import WEIGHT_COLORS, DEFAULT_WEIGHT_RANGES
        btn = self._slot_cells.get(slot_name)
        if not btn:
            return

        bg = BORDER_LO
        for i, r in enumerate(DEFAULT_WEIGHT_RANGES):
            lo, hi = r["min_ct"], r["max_ct"]
            if lo <= weight_ct < hi:
                bg = WEIGHT_COLORS[i % len(WEIGHT_COLORS)]
                break

        idx = SLOT_NAMES.index(slot_name) if slot_name in SLOT_NAMES else -1
        if idx >= 0:
            self.slot_manager.slots[idx].sorted_color = bg

        count = self.slot_manager.slots[idx].count if idx >= 0 else 1

        btn.setText(f"{slot_name}-{count}\n{weight_ct:.3f}")
        btn.setFont(QFont("IBM Plex Mono", 7))
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {BG_BASE};
                border-radius: 8px;
                border: 1px solid {bg};
                font-size: 7px;
                font-weight: 700;
                font-family: {FONT_MONO};
                padding: 2px 1px;
                text-align: center;
                line-height: 1.4;
            }}
            QPushButton:hover {{
                border: 1px solid {BRAND};
                background: {bg};
                color: {BG_BASE};
            }}
            QPushButton:pressed {{
                background: {bg};
            }}
        """)