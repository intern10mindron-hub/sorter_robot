"""
donut_gauge.py — circular donut-gauge widget for Luminax Sorter
─────────────────────────────────────────────────────────────────
Reusable widget that paints a ring (dim track + colored progress arc)
with a centered big value + small label underneath, matching the
reference HMI's OEE / Cycle gauge style.

Place at: ui/donut_gauge.py
Import as: from ui.donut_gauge import DonutGauge

Pure visual component — no business logic. Call set_value()/set_text()
from existing update_* methods in control_panel.py to drive it.
"""
from __future__ import annotations
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QFont

from ui.theme import (
    BRAND, BRAND_TRACK, TXT_BRIGHT, TXT_DIM, FONT_DISPLAY, FONT_LABEL,
)


class DonutGauge(QWidget):
    """
    A circular progress ring with a big centered value and a small
    label underneath (e.g. "84.2" / "%", or "0" / "SORTED").

    fraction: 0.0–1.0 progress around the ring (None = indeterminate/dim ring)
    """

    def __init__(self, label: str, value_text: str = "0",
                 unit_text: str = "", color: str = BRAND,
                 diameter: int = 120, thickness: int = 10,
                 parent=None):
        super().__init__(parent)
        self._label = label
        self._value_text = value_text
        self._unit_text = unit_text
        self._color = QColor(color)
        self._fraction = 0.0
        self._thickness = thickness
        self.setFixedSize(diameter, diameter + 26)  # extra height for label below ring
        self.setStyleSheet("background: transparent;")

    # ── Public API ────────────────────────────────────────────────────
    def set_value(self, value_text: str, fraction: float = None, color: str = None):
        """Update the displayed value text and (optionally) ring fill fraction/color."""
        self._value_text = value_text
        if fraction is not None:
            self._fraction = max(0.0, min(1.0, fraction))
        if color is not None:
            self._color = QColor(color)
        self.update()

    def set_fraction(self, fraction: float):
        self._fraction = max(0.0, min(1.0, fraction))
        self.update()

    def set_label(self, label: str):
        self._label = label
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        d = min(self.width(), self.height() - 26)
        margin = self._thickness / 2 + 2
        rect = QRectF(margin, margin, d - 2 * margin, d - 2 * margin)

        # Dim background track (full circle)
        track_pen = QPen(QColor(BRAND_TRACK))
        track_pen.setWidth(self._thickness)
        track_pen.setCapStyle(Qt.RoundCap)
        p.setPen(track_pen)
        p.drawArc(rect, 0, 360 * 16)

        # Progress arc — starts at 12 o'clock, clockwise
        if self._fraction > 0:
            prog_pen = QPen(self._color)
            prog_pen.setWidth(self._thickness)
            prog_pen.setCapStyle(Qt.RoundCap)
            p.setPen(prog_pen)
            span = int(360 * 16 * self._fraction)
            p.drawArc(rect, 90 * 16, -span)

        # Centered value text
        p.setPen(QColor(TXT_BRIGHT))
        val_font = QFont()
        val_font.setFamily("Inter")
        val_font.setPixelSize(int(d * 0.22))
        val_font.setBold(True)
        p.setFont(val_font)
        val_rect = QRectF(0, d * 0.30, d, d * 0.34)
        p.drawText(val_rect, Qt.AlignCenter, self._value_text)

        if self._unit_text:
            p.setPen(QColor(TXT_DIM))
            unit_font = QFont()
            unit_font.setFamily("Inter")
            unit_font.setPixelSize(int(d * 0.09))
            p.setFont(unit_font)
            unit_rect = QRectF(0, d * 0.56, d, d * 0.14)
            p.drawText(unit_rect, Qt.AlignCenter, self._unit_text)

        # Label below the ring
        p.setPen(QColor(TXT_DIM))
        lbl_font = QFont()
        lbl_font.setFamily("Inter")
        lbl_font.setPixelSize(11)
        lbl_font.setBold(True)
        lbl_font.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
        p.setFont(lbl_font)
        lbl_rect = QRectF(0, d + 4, self.width(), 20)
        p.drawText(lbl_rect, Qt.AlignCenter, self._label.upper())

        p.end()