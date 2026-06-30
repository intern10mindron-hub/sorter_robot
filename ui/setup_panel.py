from __future__ import annotations
import json
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QGroupBox, QGridLayout,
                              QDoubleSpinBox, QMessageBox, QFrame, QScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor


POSITIONS_FILE = "positions.json"

DEFAULT_POSITIONS = {
    "home":  {"x": 100.0,  "y": -200.0, "z": 144.5, "c": -5.0},
    "tray":  {"x": 400.0,  "y":    0.0, "z":  22.5, "c": -5.0},
    "scale": {"x":   0.0,  "y":    0.0, "z":  30.0, "c": -5.0},
}

# ── Palette (matches control_panel / camera_panel) ────────────────────────────
BG_BASE   = "#0E1218"
BG_CARD   = "#151C25"
BG_DEEP   = "#0A0F15"
BORDER    = "#1F2D3D"
BORDER_LO = "#172030"
BORDER_HI = "#2A3F58"
C_DIM     = "#4A6070"
C_MID     = "#7A94A8"
C_BRIGHT  = "#D8E8F0"
C_GREEN   = "#00E5B0"
C_GREEN_D = "#00A87A"
C_BLUE    = "#38D4F8"
C_AMBER   = "#FFAB40"
C_RED     = "#FF5C6A"

AX_X = "#FF6B7A"
AX_Y = "#00E5B0"
AX_Z = "#38D4F8"


def load_positions() -> dict:
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE) as f:
                data = json.load(f)
                for key in DEFAULT_POSITIONS:
                    if key not in data:
                        data[key] = DEFAULT_POSITIONS[key]
                return data
        except Exception:
            pass
    return dict(DEFAULT_POSITIONS)


def save_positions(positions: dict):
    try:
        with open(POSITIONS_FILE, "w") as f:
            json.dump(positions, f, indent=2)
    except Exception as e:
        print(f"[Setup] Save error: {e}")


class SetupPanel(QWidget):
    position_saved = pyqtSignal(str, float, float, float)

    def __init__(self, robot_controller, parent=None):
        super().__init__(parent)
        self.robot      = robot_controller
        self.positions  = load_positions()
        self._jog_step  = 5.0
        self._live_x    = 0.0
        self._live_y    = 0.0
        self._live_z    = 0.0

        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(BG_BASE))
        self.setPalette(p)

        self.setStyleSheet(f"""
            SetupPanel, SetupPanel > QWidget {{
                background-color: {BG_BASE};
                color: {C_BRIGHT};
            }}
            QLabel {{ color: {C_BRIGHT}; background: transparent; }}
            QScrollArea {{ background: {BG_BASE}; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: {BG_BASE}; }}
            QScrollBar:vertical {{
                background: {BG_DEEP}; width: 4px; border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_HI}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {C_GREEN}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QGroupBox {{
                background: {BG_CARD};
                border: 1px solid {BORDER_HI};
                border-radius: 8px;
                margin-top: 12px;
                padding: 14px 12px 12px 12px;
                font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 3px;
                color: {C_DIM};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                background: {BG_BASE};
            }}
            QDoubleSpinBox {{
                background: {BG_DEEP};
                border: 1.3px solid {BORDER_HI};
                border-radius: 6px;
                color: {C_BRIGHT};
                font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;
                font-size: 11px;
                font-weight: 700;
                padding: 5px 10px;
                min-width: 80px;
            }}
            QDoubleSpinBox:focus {{
                border: 1.3px solid {C_BLUE};
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                width: 18px;
                background: {BORDER};
                border-radius: 3px;
            }}
        """)

        self._build_ui()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_position)
        self._poll_timer.start(200)

    # ── UI BUILD ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_BASE}; }}")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setStyleSheet(f"background: {BG_BASE};")
        root = QVBoxLayout(inner)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────────────
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet(
            f"QFrame {{"
            f"  background: {BG_CARD};"
            f"  border: 1px solid {BORDER_HI};"
            f"  border-left: 3px solid {C_GREEN};"
            f"  border-radius: 8px;"
            f"}}"
        )
        hdr_lay = QVBoxLayout(hdr_frame)
        hdr_lay.setContentsMargins(16, 12, 16, 12)
        hdr_lay.setSpacing(4)

        title = QLabel("POSITION SETUP")
        title.setStyleSheet(
            f"font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;"
            f"font-size: 16px; font-weight: 700; color: {C_GREEN}; letter-spacing: 4px;"
            "border: none;"
        )
        sub = QLabel(
            "Jog robot to each position, then click Save.\n"
            "Positions are saved permanently to positions.json"
        )
        sub.setStyleSheet(
            f"font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;"
            f"font-size: 10px; color: {C_DIM}; line-height: 1.6; border: none;"
        )
        hdr_lay.addWidget(title)
        hdr_lay.addWidget(sub)
        root.addWidget(hdr_frame)

        # ── Live Position ─────────────────────────────────────────────────────
        live_box = QGroupBox("LIVE ROBOT POSITION")
        live_lay = QHBoxLayout(live_box)
        live_lay.setSpacing(0)
        live_lay.setContentsMargins(4, 4, 4, 4)

        for axis, color in [("X", AX_X), ("Y", AX_Y), ("Z", AX_Z)]:
            card = self._axis_card(axis, color)
            live_lay.addWidget(card)

        live_lay.addStretch()

        self._conn_lbl = QLabel("● NOT CONNECTED")
        self._conn_lbl.setStyleSheet(
            f"font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;"
            f"font-size: 10px; font-weight: 700; color: {C_RED};"
            "border: none; background: transparent;"
        )
        live_lay.addWidget(self._conn_lbl)
        root.addWidget(live_box)

        # ── Jog Controls ──────────────────────────────────────────────────────
        jog_box = QGroupBox("JOG CONTROLS")
        jog_lay = QVBoxLayout(jog_box)
        jog_lay.setSpacing(10)

        # Step size row
        step_row = QHBoxLayout()
        step_lbl = QLabel("Step size (mm)")
        step_lbl.setStyleSheet(
            f"font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;"
            f"font-size: 10px; color: {C_MID}; border: none;"
        )
        
        self._step_spin = QDoubleSpinBox()
        self._step_spin.setRange(0.1, 50.0)
        self._step_spin.setValue(5.0)
        self._step_spin.setSingleStep(0.5)
        self._step_spin.valueChanged.connect(
            lambda v: setattr(self, '_jog_step', v)
        )

        step_row.addWidget(step_lbl)
        step_row.addStretch()
        step_row.addWidget(self._step_spin)
        jog_lay.addLayout(step_row)

        jog_lay.addWidget(self._hsep())

        # Jog button grid
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(0, 4, 0, 0)

        jog_defs = [
            ("X+", "x", +1, 0, 1),
            ("X−", "x", -1, 1, 1),
            ("Y+", "y", +1, 0, 3),
            ("Y−", "y", -1, 1, 3),
            ("Z+", "z", +1, 0, 5),
            ("Z−", "z", -1, 1, 5),
        ]
        axis_colors = {"x": AX_X, "y": AX_Y, "z": AX_Z}

        for label, axis, direction, row, col in jog_defs:
            btn = QPushButton(label)
            color = axis_colors[axis]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {BG_DEEP};
                    border: 1.3px solid {color};
                    border-radius: 7px;
                    color: {color};
                    font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;
                    font-size: 11px;
                    font-weight: 700;
                    letter-spacing: 1px;
                    padding: 10px 14px;
                    min-width: 58px;
                }}
                QPushButton:hover {{
                    background: {color};
                    color: {BG_DEEP};
                }}
                QPushButton:pressed {{
                    background: {color}CC;
                    color: {BG_DEEP};
                }}
            """)
            btn.clicked.connect(
                lambda _, a=axis, d=direction: self._jog(a, d)
            )
            grid.addWidget(btn, row, col)

        # Axis divider labels
        for i, (axis, color) in enumerate(
            [("X", AX_X), ("Y", AX_Y), ("Z", AX_Z)]
        ):
            sep = QFrame()
            sep.setFrameShape(QFrame.VLine)
            sep.setStyleSheet(f"background: {color}40; border: none; max-width: 1px;")
            grid.addWidget(sep, 0, i * 2, 2, 1)

        jog_lay.addLayout(grid)
        root.addWidget(jog_box)

        # ── Save Positions ────────────────────────────────────────────────────
        save_box = QGroupBox("SAVE POSITIONS")
        save_lay = QVBoxLayout(save_box)
        save_lay.setSpacing(8)

        positions_def = [
            ("home",  "HOME",  C_GREEN),
            ("tray",  "TRAY",  C_BLUE),
            ("scale", "SCALE", C_AMBER),
        ]

        for key, label, color in positions_def:
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent; border: none;")
            row_l = QVBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(4)

            btn = QPushButton(f"SAVE AS {label} POSITION")
            btn.setFixedHeight(38)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {BG_DEEP};
                    border: 1.3px solid {color};
                    border-radius: 7px;
                    color: {color};
                    font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;
                    font-size: 11px;
                    font-weight: 700;
                    letter-spacing: 2px;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{
                    background: {color};
                    color: {BG_DEEP};
                }}
                QPushButton:pressed {{
                    background: {color}CC;
                    color: {BG_DEEP};
                }}
            """)
            btn.clicked.connect(lambda _, k=key: self._save_position(k))

            pos = self.positions.get(key, {})
            info = QLabel(
                f"X: {pos.get('x',0):+.2f}    "
                f"Y: {pos.get('y',0):+.2f}    "
                f"Z: {pos.get('z',0):+.2f}"
            )
            info.setStyleSheet(
                f"font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;"
                f"font-size: 10px; color: {C_DIM}; border: none; padding-left: 4px;"
            )
            setattr(self, f"_info_{key}", info)

            row_l.addWidget(btn)
            row_l.addWidget(info)
            save_lay.addWidget(row_w)

        root.addWidget(save_box)

        # ── Saved Values ──────────────────────────────────────────────────────
        saved_box = QGroupBox("CURRENTLY SAVED POSITIONS")
        saved_lay = QVBoxLayout(saved_box)
        saved_lay.setContentsMargins(8, 8, 8, 8)

        for key, color in [("home", C_GREEN), ("tray", C_BLUE), ("scale", C_AMBER)]:
            row_w = QWidget()
            row_w.setFixedHeight(36)
            row_w.setStyleSheet(
                f"background: {BG_DEEP}; border-radius: 6px; border: none;"
            )
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(12, 0, 12, 0)

            key_lbl = QLabel(key.upper())
            key_lbl.setFixedWidth(46)
            key_lbl.setStyleSheet(
                f"font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;"
                f"font-size: 10px; font-weight: 700; color: {color}; border: none;"
            )

            pos = self.positions.get(key, {})
            val_lbl = QLabel(
                f"X {pos.get('x',0):+8.2f}    "
                f"Y {pos.get('y',0):+8.2f}    "
                f"Z {pos.get('z',0):+8.2f}"
            )
            val_lbl.setStyleSheet(
                f"font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;"
                f"font-size: 10px; color: {C_MID}; border: none;"
            )
            setattr(self, f"_saved_row_{key}", val_lbl)

            rl.addWidget(key_lbl)
            rl.addWidget(val_lbl)
            rl.addStretch()
            saved_lay.addWidget(row_w)
            saved_lay.addSpacing(4)

        root.addWidget(saved_box)
        root.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    # ── HELPERS ───────────────────────────────────────────────────────────────
    def _axis_card(self, axis: str, color: str) -> QWidget:
        w = QWidget()
        w.setFixedSize(80, 64)
        w.setStyleSheet(
            f"background: {BG_DEEP}; border-radius: 7px; border: 1px solid {color}50;"
        )
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)

        name = QLabel(axis)
        name.setStyleSheet(
            f"font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;"
            f"font-size: 9px; font-weight: 700; letter-spacing: 3px; color: {color};"
            "border: none; background: transparent;"
        )
        val = QLabel("—")
        val.setStyleSheet(
            f"font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;"
            f"font-size: 17px; font-weight: 700; color: {color};"
            "border: none; background: transparent;"
        )
        lay.addWidget(name)
        lay.addWidget(val)

        setattr(self, f"_live_{axis.lower()}_lbl", val)
        return w

    def _hsep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setFixedHeight(1)
        f.setStyleSheet(f"background: {BORDER_LO}; border: none;")
        return f

    def _refresh_saved_label(self):
        for key in ["home", "tray", "scale"]:
            lbl = getattr(self, f"_saved_row_{key}", None)
            if lbl:
                pos = self.positions.get(key, {})
                lbl.setText(
                    f"X {pos.get('x',0):+8.2f}    "
                    f"Y {pos.get('y',0):+8.2f}    "
                    f"Z {pos.get('z',0):+8.2f}"
                )

    # ── ACTIONS ───────────────────────────────────────────────────────────────
    def _jog(self, axis: str, direction: int):
        step = self._jog_step * direction
        x = self._live_x + (step if axis == "x" else 0)
        y = self._live_y + (step if axis == "y" else 0)
        z = self._live_z + (step if axis == "z" else 0)
        z = max(10.0, z)
        self.robot._enqueue(lambda: self.robot._move_xyz(x, y, z, spd=20.0))

    def _do_jog(self, x: float, y: float, z: float):
        try:
            self.robot._move_xyz(x, y, z, spd=20.0)
        except Exception as e:
            print(f"[Setup] Jog error: {e}")

    def _save_position(self, key: str):
        x, y, z = self._live_x, self._live_y, self._live_z

        if x == 0.0 and y == 0.0 and z == 0.0:
            QMessageBox.warning(
                self, "No Position",
                "Live position is 0,0,0 — robot may not be connected.\n"
                "Connect robot first and jog to position."
            )
            return

        self.positions[key] = {"x": x, "y": y, "z": z, "c": -5.0}
        save_positions(self.positions)

        info_lbl = getattr(self, f"_info_{key}", None)
        if info_lbl:
            info_lbl.setText(
                f"X: {x:+.2f}    Y: {y:+.2f}    Z: {z:+.2f}"
            )
        self._refresh_saved_label()
        self.position_saved.emit(key, x, y, z)

        QMessageBox.information(
            self, "✔ Saved",
            f"{key.upper()} position saved:\n"
            f"X = {x:.3f}\n"
            f"Y = {y:.3f}\n"
            f"Z = {z:.3f}"
        )

    def _poll_position(self):
        if not hasattr(self.robot, '_monitor'):
            return
        lat = self.robot._monitor.latest
        if lat:
            self._live_x = lat.get('X', 0.0)
            self._live_y = lat.get('Y', 0.0)
            self._live_z = lat.get('Z', 0.0)
            self._live_x_lbl.setText(f"{self._live_x:+.2f}")
            self._live_y_lbl.setText(f"{self._live_y:+.2f}")
            self._live_z_lbl.setText(f"{self._live_z:+.2f}")
            self._conn_lbl.setText("● CONNECTED")
            self._conn_lbl.setStyleSheet(
                f"font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;"
                f"font-size: 10px; font-weight: 700; color: {C_GREEN};"
                "border: none; background: transparent;"
            )
        else:
            self._conn_lbl.setText("● NOT CONNECTED")
            self._conn_lbl.setStyleSheet(
                f"font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;"
                f"font-size: 10px; font-weight: 700; color: {C_RED};"
                "border: none; background: transparent;"
            )