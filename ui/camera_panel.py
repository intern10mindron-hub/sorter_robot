from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QFrame, QScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QFont, QColor
from config import PANEL_WIDTH
# TOP of file — add this import
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tray_detector_dialog import TrayDetectorDialog

# ── Industrial Console palette (shared with control_panel / telemetry_bar) ────
from ui.theme import (
    BG_BASE, BG_CARD, BG_CARD_HI, BG_DEEP, BG_RAISED,
    BORDER, BORDER_LO, BORDER_HI,
    TXT_DIM as C_DIM, TXT_MID as C_MID, TXT_BRIGHT as C_BRIGHT,
    GREEN as C_GREEN, GREEN_D as C_GREEN_D,
    BLUE as C_BLUE, AMBER as C_AMBER, RED as C_RED,
    BRAND, BRAND_HI, BRAND_DIM,
    FONT_LABEL, FONT_MONO, FONT_DISPLAY,
    card_qss, outline_button_qss, pill_button_qss,
)

class CameraPanel(QWidget):
    # Camera signals
    vibrate_clicked = pyqtSignal()
    # Pick & Place signal
    pick_and_place_requested = pyqtSignal()
    pick_target_selected      = pyqtSignal(float, float) 
    pick_cancelled           = pyqtSignal() 

    # Manual override signals
    home_requested            = pyqtSignal()
    tray_requested            = pyqtSignal()
    scale_requested           = pyqtSignal()
    pump_on_requested         = pyqtSignal()
    pump_off_requested        = pyqtSignal()
    emergency_stop_requested  = pyqtSignal()
    emergency_reset_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(PANEL_WIDTH)
        self._vib_count        = 0
        self._emergency_active = False
        self._workflow_state = None
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(BG_BASE))
        self.setPalette(p)

        self.setStyleSheet(f"""
            CameraPanel, CameraPanel > QWidget {{
                background-color: {BG_BASE};
                color: {C_BRIGHT};
            }}

            QLabel {{ color: {C_BRIGHT}; background: transparent; }}
            QScrollArea {{ background: {BG_BASE}; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: {BG_BASE}; }}
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
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())
        root.addWidget(self._make_feed())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_BASE}; }}")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_inner = QWidget()
        scroll_inner.setStyleSheet(f"background: {BG_BASE};")
        inner_lay = QVBoxLayout(scroll_inner)
        inner_lay.setContentsMargins(14, 12, 14, 16)
        inner_lay.setSpacing(12)
        inner_lay.addWidget(self._make_pick_and_place())
        inner_lay.addWidget(self._make_detection_section())
        inner_lay.addWidget(self._make_quick_positions())
        inner_lay.addWidget(self._make_vacuum_vibration())
        inner_lay.addWidget(self._make_emergency())
        inner_lay.addStretch()
        scroll.setWidget(scroll_inner)
        root.addWidget(scroll)

    # ── HELPERS ───────────────────────────────────────────────────────────────
    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 11px; letter-spacing: 1.5px; color: {C_MID};"
            f"font-family: {FONT_LABEL};"
            "font-weight: 600;"
            "border: none; background: transparent;"
        )
        return lbl

    def _card_header_row(self, text: str) -> QWidget:
        """Quiet uppercase label header — no decorative accent tab,
        matching the reference's plain section headers."""
        hdr = QWidget()
        hdr.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(18, 16, 18, 6)
        lay.addWidget(self._section_label(text))
        return hdr

    def _action_btn(self, text: str, border_col: str, text_col: str,
                    bg_col: str = BG_DEEP, height: int = 38) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(height)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {BG_DEEP};
                border: 1.5px solid {border_col};
                border-radius: 10px;
                color: {border_col};
                font-size: 11px;
                font-weight: 600;
                font-family: {FONT_LABEL};
                letter-spacing: 1px;
                padding: 4px 8px;
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
                background: {BG_DEEP};
                border: 1.5px solid {BORDER};
                color: {C_DIM};
            }}
        """)
        return btn
    
    def set_robot(self, robot):
        """
        Receives the main app's RobotTCP instance.
        Call this from main_window.py after creating CameraPanel:
            self.camera_panel.set_robot(self._robot)
        """
        self._robot = robot
        
    def set_workflow(self, workflow):     # ← ADD THIS
        self._workflow = workflow
        
    def set_workflow_state(self, state):
        """Called by main_window on every state_changed to gate feed click."""
        self._workflow_state = state
    
    # Add these 2 methods to the CameraPanel class
    def _open_tray_detector(self, event=None):
        from core.workflow import State

        # Allow open in IDLE, PAUSED, or WAITING_CAMERA states
        allowed = (State.IDLE, State.PAUSED, State.WAITING_CAMERA)
        if (self._workflow_state is not None
                and self._workflow_state not in allowed):
            return

        self._tray_dlg = TrayDetectorDialog(parent=self)
        self._tray_dlg.diamond_selected.connect(self._on_diamond_from_tray)
        self._tray_dlg.diamond_selected.connect(
            lambda rx, ry: self._tray_dlg.close()   # auto-close after click
        )
        self._tray_dlg.closed.connect(self._on_tray_dialog_closed)
        if hasattr(self, '_robot') and self._robot is not None:
            self._tray_dlg.set_robot(self._robot)
        if hasattr(self, '_workflow') and self._workflow is not None:
            self._tray_dlg.set_workflow(self._workflow)
        self._tray_dlg.showMaximized()

    def _on_tray_dialog_closed(self):
        """If operator closes dialog without clicking a diamond, cancel and return to IDLE."""
        from core.workflow import State
        if self._workflow_state == State.WAITING_CAMERA:
            self.pick_cancelled.emit()          # ← tell main_window to stop workflow
            self.set_pick_place_status(
                "● Ready — Place diamond on tray first", C_DIM
            )
    
    def _on_diamond_from_tray(self, robot_x, robot_y):
        self.pick_target_selected.emit(robot_x, robot_y)

    # ── HEADER ────────────────────────────────────────────────────────────────
    def _make_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(50)
        w.setStyleSheet(
            f"background: {BG_BASE};"
            f"border-bottom: 1px solid {BORDER_LO};"
        )
        lay = QHBoxLayout(w)
        lay.setContentsMargins(18, 0, 18, 0)
        lay.setSpacing(10)

        lbl = QLabel("CAMERA FEED")
        lbl.setStyleSheet(
            f"font-size: 12px; letter-spacing: 1.5px; color: {C_BRIGHT};"
            f"font-family: {FONT_LABEL};"
            "font-weight: 600; border: none;"
        )

        self._cam_dot = QLabel("●")
        self._cam_dot.setStyleSheet(
            f"font-size: 9px; color: {C_DIM}; border: none;"
        )
        self._cam_status = QLabel("NO SIGNAL")
        self._cam_status.setStyleSheet(
            f"font-size: 9px; color: {C_DIM};"
            f"font-family: {FONT_LABEL};"
            "letter-spacing: 1px; font-weight: 700; border: none;"
        )

        status_row = QWidget()
        status_row.setStyleSheet("background: transparent; border: none;")
        sr = QHBoxLayout(status_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(5)
        sr.addWidget(self._cam_dot)
        sr.addWidget(self._cam_status)

        lay.addWidget(lbl)
        lay.addStretch()
        lay.addWidget(status_row)
        return w

    # In camera_panel.py

    def _make_feed(self) -> QWidget:
        wrapper = QWidget()
        wrapper.setStyleSheet(f"background: {BG_BASE}; border: none;")
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(14, 12, 14, 0)

        self._feed = QLabel()
        self._feed.setFixedHeight(190)
        self._feed.setAlignment(Qt.AlignCenter)
        # ── pure black feed well, rounded to match card language ──
        self._feed.setStyleSheet(
            "background: #000000;"
            f"border-radius: 14px;"
            f"border: 1px solid {BORDER_HI};"
        )
        self._feed.setText("")          # ← no "NO SIGNAL" text
        self._feed.mousePressEvent = self._open_tray_detector
        wl.addWidget(self._feed)
        return wrapper
 
    # ── PICK & PLACE ──────────────────────────────────────────────────────────
    def _make_pick_and_place(self) -> QWidget:
        outer = QFrame()
        outer.setStyleSheet(card_qss(radius=16))
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 16)
        ol.setSpacing(0)
        ol.addWidget(self._card_header_row("PICK & PLACE"))

        content = QWidget()
        content.setStyleSheet("background: transparent; border: none;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(18, 4, 18, 0)
        cl.setSpacing(10)

        self.btn_pick_place = QPushButton("⬆  PICK & PLACE")
        self.btn_pick_place.setFixedHeight(46)
        self.btn_pick_place.setStyleSheet(pill_button_qss(bg=BRAND, text=BG_BASE, radius=12))
        self.btn_pick_place.clicked.connect(self._on_pick_and_place)
        cl.addWidget(self.btn_pick_place)

        self._pick_status_lbl = QLabel("● Ready — Place diamond on tray first")
        self._pick_status_lbl.setStyleSheet(
            f"color: {C_DIM}; font-size: 10px;"
            f"font-family: {FONT_LABEL};"
            "border: none; background: transparent; padding: 2px 0;"
        )
        self._pick_status_lbl.setWordWrap(True)
        cl.addWidget(self._pick_status_lbl)
        ol.addWidget(content)
        return outer

    # ========== CHANGED METHOD ==========
    def _on_pick_and_place(self):
        """
        Manual mode — signal main_window to start the sequence.
        Robot moves to tray first, THEN camera opens automatically.
        """
        self.pick_and_place_requested.emit()

    # ── DETECTION ─────────────────────────────────────────────────────────────
    def _make_detection_section(self) -> QWidget:
        outer = QFrame()
        outer.setStyleSheet(card_qss(radius=16))
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 8)
        ol.setSpacing(2)

        ol.addWidget(self._card_header_row("DETECTION"))
        self._det_count   = self._data_row("Detected",   "0",    C_GREEN)
        self._det_cluster = self._data_row("Cluster",    "No",   C_DIM)
        self._det_vibs    = self._data_row("Vibrations", "0",    C_MID)
        self._det_mode    = self._data_row("Mode",       "AUTO", C_GREEN)

        for row in [self._det_count, self._det_cluster,
                    self._det_vibs, self._det_mode]:
            ol.addWidget(row)
        return outer

    def _data_row(self, label: str, value: str, val_color: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(18, 6, 18, 6)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size: 13px; color: {C_BRIGHT};"
            f"font-family: {FONT_LABEL};"
            "border: none;"
        )
        val = QLabel(value)
        val.setObjectName(f"val_{label}")
        val.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {val_color};"
            f"font-family: {FONT_DISPLAY};"
            "border: none;"
        )
        lay.addWidget(lbl)
        lay.addStretch()
        lay.addWidget(val)
        return w

    # ── QUICK POSITIONS ───────────────────────────────────────────────────────
    def _make_quick_positions(self) -> QWidget:
        outer = QFrame()
        outer.setStyleSheet(card_qss(radius=16))
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 16)
        ol.setSpacing(0)

        ol.addWidget(self._card_header_row("QUICK POSITIONS"))

        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent; border: none;")
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(18, 4, 18, 0)
        bl.setSpacing(8)

        self.btn_home  = self._action_btn("HOME",  C_BLUE, C_BLUE)
        self.btn_tray  = self._action_btn("TRAY",  C_BLUE, C_BLUE)
        self.btn_scale = self._action_btn("SCALE", C_BLUE, C_BLUE)

        self.btn_home.clicked.connect(self.home_requested.emit)
        self.btn_tray.clicked.connect(self.tray_requested.emit)
        self.btn_scale.clicked.connect(self.scale_requested.emit)

        bl.addWidget(self.btn_home)
        bl.addWidget(self.btn_tray)
        bl.addWidget(self.btn_scale)
        ol.addWidget(btn_row)
        return outer

    # ── VACUUM & VIBRATION ────────────────────────────────────────────────────
    def _make_vacuum_vibration(self) -> QWidget:
        outer = QFrame()
        outer.setStyleSheet(card_qss(radius=16))
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 16)
        ol.setSpacing(0)

        ol.addWidget(self._card_header_row("VACUUM & VIBRATION"))

        content = QWidget()
        content.setStyleSheet("background: transparent; border: none;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(18, 4, 18, 0)
        cl.setSpacing(10)

        pump_row = QWidget()
        pump_row.setStyleSheet("background: transparent; border: none;")
        pr = QHBoxLayout(pump_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.setSpacing(8)

        self.btn_pump_on  = self._action_btn("PUMP ON",  C_GREEN, C_GREEN)
        self.btn_pump_off = self._action_btn("PUMP OFF", C_DIM,   C_MID)
        self.btn_pump_on.clicked.connect(self.pump_on_requested.emit)
        self.btn_pump_off.clicked.connect(self.pump_off_requested.emit)
        pr.addWidget(self.btn_pump_on)
        pr.addWidget(self.btn_pump_off)
        cl.addWidget(pump_row)

        self._vib_btn = self._action_btn("VIBRATE", C_AMBER, C_AMBER, height=38)
        self._vib_btn.clicked.connect(self._on_vibrate)
        cl.addWidget(self._vib_btn)

        self._pressure_lbl = QLabel("Pressure: — kPa")
        self._pressure_lbl.setStyleSheet(
            f"color: {C_DIM}; font-size: 11px;"
            f"font-family: {FONT_LABEL};"
            "border: none; background: transparent;"
        )
        cl.addWidget(self._pressure_lbl)
        ol.addWidget(content)
        return outer

    # ── EMERGENCY ─────────────────────────────────────────────────────────────
    def _make_emergency(self) -> QWidget:
        outer = QFrame()
        outer.setStyleSheet(card_qss(radius=16))
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 18)
        ol.setSpacing(0)

        ol.addWidget(self._card_header_row("EMERGENCY"))

        content = QWidget()
        content.setStyleSheet("background: transparent; border: none;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(18, 4, 18, 0)
        cl.setSpacing(10)

        self.btn_estop = QPushButton("⬛  EMERGENCY STOP")
        self.btn_estop.setFixedHeight(46)
        self.btn_estop.setStyleSheet(pill_button_qss(bg=C_RED, text=BG_BASE, radius=12))
        self.btn_estop.clicked.connect(self._on_emergency_stop)
        cl.addWidget(self.btn_estop)

        self.btn_reset = self._action_btn("RESET SYSTEM", C_BLUE, C_BLUE, height=36)
        self.btn_reset.clicked.connect(self._on_emergency_reset)
        cl.addWidget(self.btn_reset)

        self._status_lbl = QLabel("● READY")
        self._status_lbl.setStyleSheet(
            f"color: {C_GREEN}; font-size: 11px;"
            f"font-family: {FONT_LABEL};"
            "font-weight: 700; letter-spacing: 1px;"
            "padding: 4px 0; border: none; background: transparent;"
        )
        cl.addWidget(self._status_lbl)

        ol.addWidget(content)
        return outer

    # ── INTERNAL SLOTS ────────────────────────────────────────────────────────
    def _on_vibrate(self):
        self.vibrate_clicked.emit()
        self.increment_vibrations()

    def _on_emergency_stop(self):
        self._emergency_active = True
        for btn in [self.btn_home, self.btn_tray, self.btn_scale,
                    self.btn_pump_on, self.btn_pump_off, self._vib_btn]:
            btn.setEnabled(False)
        self._status_lbl.setText("● EMERGENCY STOPPED")
        self._status_lbl.setStyleSheet(
            f"color: {C_RED}; font-size: 11px;"
            f"font-family: {FONT_LABEL};"
            "font-weight: 700; letter-spacing: 1px;"
            "padding: 4px 0; border: none; background: transparent;"
        )
        self.emergency_stop_requested.emit()

    def _on_emergency_reset(self):
        self._emergency_active = False
        for btn in [self.btn_home, self.btn_tray, self.btn_scale,
                    self.btn_pump_on, self.btn_pump_off, self._vib_btn]:
            btn.setEnabled(True)
        self._status_lbl.setText("● READY")
        self._status_lbl.setStyleSheet(
            f"color: {C_GREEN}; font-size: 11px;"
            f"font-family: {FONT_LABEL};"
            "font-weight: 700; letter-spacing: 1px;"
            "padding: 4px 0; border: none; background: transparent;"
        )
        self.emergency_reset_requested.emit()

    # ── PUBLIC API ────────────────────────────────────────────────────────────
    def update_frame(self, img: QImage):
        # Guard: don't paint frames if camera is marked disconnected
        if self._cam_status.text() == "NO SIGNAL":
            return

        self._cam_dot.setText("●")
        self._cam_dot.setStyleSheet(
            f"font-size: 9px; color: {C_GREEN}; border: none;"
        )
        self._cam_status.setText("LIVE")
        self._cam_status.setStyleSheet(
            f"font-size: 9px; color: {C_GREEN};"
            f"font-family: {FONT_LABEL};"
            "letter-spacing: 1px; font-weight: 700; border: none;"
        )
        pix = QPixmap.fromImage(img)
        self._feed.setPixmap(
            pix.scaled(self._feed.width() - 4, self._feed.height() - 4,
                       Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self._feed.setText("")

    def update_diamonds(self, diamonds: list):
        count       = len(diamonds)
        has_cluster = any(d[2] for d in diamonds)

        vals = self._det_count.findChildren(QLabel)
        if len(vals) >= 2:
            vals[-1].setText(str(count))
            vals[-1].setStyleSheet(
                f"font-size: 15px; font-weight: 700; color: {C_GREEN};"
                f"font-family: {FONT_DISPLAY}; border: none;"
            )
        c_vals = self._det_cluster.findChildren(QLabel)
        if len(c_vals) >= 2:
            c_vals[-1].setText("Yes" if has_cluster else "No")
            col = C_AMBER if has_cluster else C_DIM
            c_vals[-1].setStyleSheet(
                f"font-size: 15px; font-weight: 700; color: {col};"
                f"font-family: {FONT_DISPLAY}; border: none;"
            )

    def increment_vibrations(self):
        self._vib_count += 1
        vib_vals = self._det_vibs.findChildren(QLabel)
        if len(vib_vals) >= 2:
            vib_vals[-1].setText(str(self._vib_count))

    def update_pressure(self, kpa: float):
        self._pressure_lbl.setText(f"Pressure: {kpa:.1f} kPa")
        if kpa > 55:
            col = C_GREEN
        elif kpa > 30:
            col = C_AMBER
        else:
            col = C_DIM
        self._pressure_lbl.setStyleSheet(
            f"color: {col}; font-size: 11px;"
            f"font-family: {FONT_LABEL};"
            "border: none; background: transparent;"
        )

    def set_connected(self, ok: bool):
        col = C_GREEN if ok else C_RED
        txt = "LIVE"   if ok else "NO SIGNAL"
        self._cam_dot.setStyleSheet(
            f"font-size: 9px; color: {col}; border: none;"
        )
        self._cam_status.setText(txt)
        self._cam_status.setStyleSheet(
            f"font-size: 9px; color: {col};"
            f"font-family: {FONT_LABEL};"
            "letter-spacing: 1px; font-weight: 700; border: none;"
        )
        # ── clear feed to pure black when disconnected ──
        if not ok:
            self._feed.clear()
            self._feed.setText("")
            self._feed.setStyleSheet(
                "background: #000000;"
                f"border-radius: 14px;"
                f"border: 1px solid {BORDER_HI};"
            )
    def set_pick_place_enabled(self, enabled: bool):
        """Enable or disable the Pick & Place button."""
        self.btn_pick_place.setEnabled(enabled)

    def set_pick_place_status(self, text: str, color: str = None):
        """Update the status label below Pick & Place button."""
        self._pick_status_lbl.setText(text)
        if color:
            self._pick_status_lbl.setStyleSheet(
                f"color: {color}; font-size: 10px;"
                f"font-family: {FONT_LABEL};"
                "border: none; background: transparent; padding: 2px 0;"
            )
            
    def set_pump_button_state(self, on: bool):
        """Update PUMP ON / PUMP OFF button visuals to reflect real pump state.
        on=True  → PUMP ON glows green,  PUMP OFF goes dim
        on=False → PUMP OFF glows red,   PUMP ON goes dim
        """
        if on:
            self.btn_pump_on.setStyleSheet(f"""
                QPushButton {{
                    background: {C_GREEN};
                    border: 1.5px solid {C_GREEN};
                    border-radius: 10px;
                    color: {BG_BASE};
                    font-size: 11px;
                    font-weight: 600;
                    font-family: {FONT_LABEL};
                    letter-spacing: 1px;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    background: {C_GREEN};
                    color: {BG_BASE};
                }}
                QPushButton:disabled {{
                    background: {BG_DEEP};
                    border: 1.5px solid {BORDER};
                    color: {C_DIM};
                }}
            """)
            self.btn_pump_off.setStyleSheet(f"""
                QPushButton {{
                    background: {BG_DEEP};
                    border: 1.5px solid {BORDER};
                    border-radius: 10px;
                    color: {C_DIM};
                    font-size: 11px;
                    font-weight: 600;
                    font-family: {FONT_LABEL};
                    letter-spacing: 1px;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    background: {BORDER};
                    color: {BG_BASE};
                }}
                QPushButton:disabled {{
                    background: {BG_DEEP};
                    border: 1.5px solid {BORDER};
                    color: {C_DIM};
                }}
            """)
        else:
            self.btn_pump_on.setStyleSheet(f"""
                QPushButton {{
                    background: {BG_DEEP};
                    border: 1.5px solid {BORDER};
                    border-radius: 10px;
                    color: {C_DIM};
                    font-size: 11px;
                    font-weight: 600;
                    font-family: {FONT_LABEL};
                    letter-spacing: 1px;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    background: {BORDER};
                    color: {BG_BASE};
                }}
                QPushButton:disabled {{
                    background: {BG_DEEP};
                    border: 1.5px solid {BORDER};
                    color: {C_DIM};
                }}
            """)
            self.btn_pump_off.setStyleSheet(f"""
                QPushButton {{
                    background: {C_RED};
                    border: 1.5px solid {C_RED};
                    border-radius: 10px;
                    color: {BG_BASE};
                    font-size: 11px;
                    font-weight: 600;
                    font-family: {FONT_LABEL};
                    letter-spacing: 1px;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    background: {C_RED};
                    color: {BG_BASE};
                }}
                QPushButton:disabled {{
                    background: {BG_DEEP};
                    border: 1.5px solid {BORDER};
                    color: {C_DIM};
                }}
            """)