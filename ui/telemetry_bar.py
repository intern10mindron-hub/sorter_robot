from __future__ import annotations
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame

from ui.theme import (
    BG_BASE, BG_CARD, BG_RAISED, BORDER, BORDER_LO, BORDER_HI,
    TXT_DIM as C_DIM, TXT_MID as C_MID, TXT_BRIGHT as C_BRIGHT,
    GREEN as C_GREEN, BLUE as C_BLUE, AMBER as C_AMBER, RED as C_RED,
    BRAND, FONT_LABEL, FONT_MONO, FONT_DISPLAY,
)

# Threshold above which the pressure reading indicates a diamond is held
# on the nozzle. Raw normalized value from HX710B firmware.
# TODO: calibrate after physical testing — set in config.py as PRESSURE_PICK_THRESHOLD
_PICK_THRESHOLD = 7_000_000


class TelemetryItem(QFrame):
    """A single rounded telemetry chip — matches reference's pill-card rhythm
    instead of plain column-with-vertical-divider."""

    def __init__(self, label: str, initial: str = "—", color: str = C_BRIGHT):
        super().__init__()
        self.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER_LO};"
            f"border-radius: 12px; }}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 8, 18, 8)

        inner = QWidget()
        inner.setStyleSheet("background: transparent; border: none;")
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(2)

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            f"font-size: 10px; letter-spacing: 1.5px; color: {C_DIM};"
            f"font-family: {FONT_LABEL}; font-weight: 600; border: none;"
        )
        self._val = QLabel(initial)
        self._val.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {color};"
            f"font-family: {FONT_DISPLAY}; border: none;"
        )
        il.addWidget(self._lbl)
        il.addWidget(self._val)
        lay.addWidget(inner)

    def set_value(self, text: str, color: str = None):
        self._val.setText(text)
        if color:
            self._val.setStyleSheet(
                f"font-size: 15px; font-weight: 700; color: {color};"
                f"font-family: {FONT_DISPLAY}; border: none;"
            )


class _JointsItem(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER_LO};"
            f"border-radius: 12px; }}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 8, 18, 8)
        outer.setSpacing(2)

        lbl = QLabel("JOINTS")
        lbl.setStyleSheet(
            f"font-size: 10px; letter-spacing: 1.5px; color: {C_DIM};"
            f"font-family: {FONT_LABEL}; font-weight: 600; border: none;"
        )
        row = QWidget()
        row.setStyleSheet("background: transparent; border: none;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(16)

        self._j = []
        for name in ["J1", "J2", "J3", "J4"]:
            l = QLabel(f"{name} —")
            l.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {C_DIM};"
                f"font-family: {FONT_DISPLAY}; border: none;"
            )
            rl.addWidget(l)
            self._j.append(l)

        outer.addWidget(lbl)
        outer.addWidget(row)

    def set_joints(self, j1, j2, j3, j4):
        vals = [f"J1 {j1:.0f}°", f"J2 {j2:.0f}°",
                f"J3 {j3:.0f}mm", f"J4 {j4:.0f}°"]
        for label, text in zip(self._j, vals):
            label.setText(text)
            label.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {C_MID};"
                f"font-family: {FONT_DISPLAY}; border: none;"
            )


class TelemetryBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(68)
        self.setAutoFillBackground(True)
        p = self.palette()
        from PyQt5.QtGui import QColor
        p.setColor(self.backgroundRole(), QColor(BG_BASE))
        self.setPalette(p)
        self.setStyleSheet(f"""
            TelemetryBar {{
                background-color: {BG_BASE};
                border-top: 1px solid {BORDER_LO};
            }}
            QLabel {{ color: {C_BRIGHT}; background: transparent; }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(10)

        self.scale    = TelemetryItem("SCALE",    "— ct",  C_GREEN)
        self.pressure = TelemetryItem("PRESSURE", "0 kPa", C_BLUE)
        self.pump     = TelemetryItem("PUMP",     "OFF",   C_DIM)
        self.joints   = _JointsItem()
        self.robot    = TelemetryItem("ROBOT",    "IDLE",  C_DIM)

        for w in [self.scale, self.pressure, self.pump, self.joints, self.robot]:
            lay.addWidget(w)
        lay.addStretch()

    def update_scale(self, ct: float):
        self.scale.set_value(f"{ct:.4f} ct", C_GREEN)

    def update_pressure(self, raw: int):
        """
        Accepts the raw normalized integer from the HX710B pressure sensor.
        Displays a compact human-readable value and colors green when a
        diamond is detected on the nozzle (raw > _PICK_THRESHOLD).
        """
        if raw >= _PICK_THRESHOLD:
            # Diamond held — show compact value in green
            display = f"{raw // 1_000_000}M"
            color   = C_GREEN
        elif raw >= 1_000_000:
            # Pump on, no diamond — amber
            display = f"{raw // 1_000_000}M"
            color   = C_AMBER
        else:
            # Pump off / idle noise — dim blue, show as-is
            display = str(raw)
            color   = C_BLUE
        self.pressure.set_value(display, color)

    def update_pump(self, on: bool):
        self.pump.set_value("ON" if on else "OFF", C_GREEN if on else C_DIM)

    def update_joints(self, j1, j2, j3, j4):
        self.joints.set_joints(j1, j2, j3, j4)

    def update_robot(self, status: str, color: str = C_BLUE):
        self.robot.set_value(status, color)