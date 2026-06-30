from __future__ import annotations
import os
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                              QSplitter, QPushButton, QLabel, QMessageBox,
                              QStatusBar, QFrame, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QColor, QPalette
from core.workflow import Workflow, State, STATE_INFO
from core.session import Session
from core.slot_manager import SlotManager
from ui.control_panel import ControlPanel
from ui.robot_viewer import RobotViewer
from ui.camera_panel import CameraPanel
from ui.telemetry_bar import TelemetryBar
from hardware.scale_reader import ScaleReader
from hardware.esp32_controller import ESP32Controller
from hardware.camera_Detector import CameraDetector
from hardware.robot_controller import RobotController
from pressure_sensor import PressureSensor

from PyQt5.QtWebEngineWidgets import QWebEnginePage
from config import STYLESHEET, SCALE_SETTLE_MS, PICK_GRIP_DELAY_MS, SCALE_PLACE_DWELL_MS

class ConsolePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        print(f'[JS] {message}')


# ── Pick sequence steps ───────────────────────────────────────────────────────
_PICK_STEP_TRAY    = 0
_PICK_STEP_DOWN    = 1
_PICK_STEP_UP      = 2

PICK_DOWN_DWELL_MS = 150

# ── Weigh sequence steps ──────────────────────────────────────────────────────
_WEIGH_STEP_TRAVEL  = 0
_WEIGH_STEP_PLACE   = 1
_WEIGH_STEP_CLEAR   = 2
_WEIGH_STEP_PICK    = 3
_WEIGH_STEP_LIFT    = 4

_SORT_STEP_TRAVEL  = 0
_SORT_STEP_DROP    = 1
_SORT_STEP_RELEASE = 2

# ── Design tokens ─────────────────────────────────────────────────────────────
# Repointed to match the reference "Industrial Console" theme (see ui/theme.py):
# true charcoal base, lighter elevated cards, soft sage-mint accent.
class _T:
    BG_BASE    = "#15171A"
    BG_SURFACE = "#22252A"
    BG_RAISED  = "#1C1F23"
    BG_BORDER  = "#262932"
    GREEN_HI   = "#8FD9B6"
    GREEN_MID  = "#5FA888"
    GREEN_DIM  = "#3A4540"
    AMBER      = "#E8C170"
    RED        = "#E08585"
    BLUE       = "#7FB8DE"
    ORANGE     = "#8FD9B6"   # kept as alias — brand accent now sage, not orange
    BRAND      = "#8FD9B6"
    TXT_HI     = "#F4F6F5"
    TXT_MID    = "#9DA5A8"
    TXT_DIM    = "#5E6569"
    HDR_H      = 64
    FONT_LABEL = "'Inter', 'Segoe UI Semibold', sans-serif"
    FONT_MONO  = "'JetBrains Mono', 'IBM Plex Mono', monospace"
    FONT_DISPLAY = "'Inter', 'Segoe UI', sans-serif"

_HEADER_QSS = f"""
QWidget#header {{
    background: {_T.BG_RAISED};
    border-bottom: 1px solid {_T.BG_BORDER};
}}
QLabel#logoMain {{
    font-family: {_T.FONT_LABEL};
    font-size: 16px;
    font-weight: 700;
    color: {_T.TXT_HI};
    letter-spacing: 4px;
    border: none;
    background: transparent;
}}
QLabel#logoSub {{
    font-family: {_T.FONT_LABEL};
    font-size: 16px;
    font-weight: 400;
    color: {_T.BRAND};
    letter-spacing: 4px;
    border: none;
    background: transparent;
}}
QLabel#logoSep {{
    color: {_T.TXT_DIM};
    font-size: 13px;
    border: none;
    background: transparent;
    letter-spacing: 0px;
    padding: 0 4px;
}}
QLabel#connDot {{
    font-size: 9px;
    color: {_T.TXT_DIM};
    border: none;
    background: transparent;
}}
QLabel#connLabel {{
    font-family: {_T.FONT_LABEL};
    font-size: 10px;
    color: {_T.TXT_MID};
    letter-spacing: 1px;
    border: none;
    background: transparent;
}}
QLabel#sessionLabel {{
    font-family: {_T.FONT_MONO};
    font-size: 10px;
    color: {_T.TXT_DIM};
    letter-spacing: 1px;
    border: none;
    background: transparent;
}}
QFrame#vSep {{
    background: {_T.BG_BORDER};
    border: none;
}}
QPushButton#btnStart {{
    font-family: {_T.FONT_LABEL};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
    color: {_T.BG_BASE};
    background: {_T.BRAND};
    border: none;
    border-radius: 10px;
    padding: 0 16px;
    min-width: 90px;
    min-height: 34px;
}}
QPushButton#btnStart:hover {{
    background: #A8E6C8;
}}
QPushButton#btnStart:pressed {{
    background: #5FA888;
}}
QPushButton#btnPause {{
    font-family: {_T.FONT_LABEL};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
    color: {_T.AMBER};
    background: {_T.BG_SURFACE};
    border: 1.5px solid {_T.AMBER};
    border-radius: 10px;
    padding: 0 16px;
    min-width: 84px;
    min-height: 34px;
}}
QPushButton#btnPause:hover {{
    background: rgba(232, 193, 112, 0.12);
}}
QPushButton#btnPause:pressed {{
    background: rgba(232, 193, 112, 0.22);
}}
QPushButton#btnStop {{
    font-family: {_T.FONT_LABEL};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
    color: {_T.RED};
    background: {_T.BG_SURFACE};
    border: 1.5px solid {_T.RED};
    border-radius: 10px;
    padding: 0 16px;
    min-width: 78px;
    min-height: 34px;
}}
QPushButton#btnStop:hover {{
    background: rgba(224, 133, 133, 0.12);
}}
QPushButton#btnStop:pressed {{
    background: rgba(224, 133, 133, 0.22);
}}
"""

_STATUSBAR_QSS = f"""
QStatusBar {{
    background: {_T.BG_BASE};
    border-top: 1px solid {_T.BG_BORDER};
    font-family: {_T.FONT_MONO};
    font-size: 10px;
    color: {_T.TXT_DIM};
    padding: 0 20px;
    letter-spacing: 1px;
}}
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Luminax Sorter — Mindron Technology")
        self.setMinimumSize(1280, 720)
        self.setStyleSheet(STYLESHEET)

        self.slot_manager = SlotManager()
        self.session      = Session()
        self.workflow     = Workflow(self.session, self.slot_manager, self)

        self.scale    = ScaleReader(self)
        self.esp32    = ESP32Controller(self)
        self.camera   = CameraDetector(self)
        self.robot    = RobotController(self)
        self.pressure_sensor = PressureSensor(port="COM14", parent=self)

        from diamond_selector import DiamondSelector
        self.diamond_selector = DiamondSelector(self)
        self.diamond_selector.set_robot(self.robot)
        self.diamond_selector.set_workflow(self.workflow)
        self.workflow.set_diamond_selector(self.diamond_selector)

        self._pick_step    = -1
        self._weigh_step   = -1
        self._sort_step    = -1
        self._pending_slot = 0
        self._manual_move_slot = None
        self._seq_busy         = False
        self._last_pressure    = 0

        self._build_ui()
        self._connect_signals()
        self.scale.start()
        self.esp32.start()
        self.camera.start()
        self.robot.start()
        self.pressure_sensor.start()

    # ── UI BUILD ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {_T.BG_BORDER}; }}"
        )

        self.ctrl_panel   = ControlPanel(self.slot_manager, self.session, self)
        self.robot_viewer = RobotViewer(self)
        self.cam_panel    = CameraPanel(self)
        self.cam_panel.set_robot(self.robot)

        self.ctrl_panel.setAutoFillBackground(True)
        self.cam_panel.setAutoFillBackground(True)

        splitter.addWidget(self.ctrl_panel)
        splitter.addWidget(self.robot_viewer)
        splitter.addWidget(self.cam_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        root.addWidget(splitter)
        self.tele = TelemetryBar(self)
        root.addWidget(self.tele)
        self._init_status_bar()

    def _build_header(self) -> QWidget:
        hdr = QWidget()
        hdr.setObjectName("header")
        hdr.setFixedHeight(_T.HDR_H)
        hdr.setStyleSheet(_HEADER_QSS)
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(0)

        logo_block = QWidget()
        logo_block.setStyleSheet("background: transparent;")
        lb = QHBoxLayout(logo_block)
        lb.setContentsMargins(0, 0, 0, 0)
        lb.setSpacing(0)

        logo = QLabel("LUMINAX")
        logo.setObjectName("logoMain")
        sep_lbl = QLabel("·")
        sep_lbl.setObjectName("logoSep")
        sorter = QLabel("SORTER")
        sorter.setObjectName("logoSub")

        lb.addWidget(logo)
        lb.addWidget(sep_lbl)
        lb.addWidget(sorter)

        def vsep(h: int = 26) -> QFrame:
            f = QFrame()
            f.setObjectName("vSep")
            f.setFrameShape(QFrame.VLine)
            f.setFixedSize(1, h)
            return f

        self._conn_dots   = {}
        self._conn_labels = {}
        conn_block = QWidget()
        conn_block.setStyleSheet("background: transparent;")
        cb = QHBoxLayout(conn_block)
        cb.setContentsMargins(0, 0, 0, 0)
        cb.setSpacing(20)

        for name in ["Robot", "Scale", "Camera", "ESP32", "Pressure"]:
            item = QWidget()
            item.setStyleSheet("background: transparent;")
            il = QHBoxLayout(item)
            il.setContentsMargins(0, 0, 0, 0)
            il.setSpacing(7)
            dot = QLabel("●")
            dot.setObjectName("connDot")
            lbl = QLabel(name.upper())
            lbl.setObjectName("connLabel")
            il.addWidget(dot)
            il.addWidget(lbl)
            cb.addWidget(item)
            self._conn_dots[name]   = dot
            self._conn_labels[name] = lbl

        self._session_lbl = QLabel(
            f"SESSION {self.session.session_id}"
            f"   {datetime.now().strftime('%Y-%m-%d')}"
        )
        self._session_lbl.setObjectName("sessionLabel")

        self._btn_start = QPushButton("▶  START")
        self._btn_start.setObjectName("btnStart")
        self._btn_start.setCursor(Qt.PointingHandCursor)

        self._btn_pause = QPushButton("⏸  PAUSE")
        self._btn_pause.setObjectName("btnPause")
        self._btn_pause.setCursor(Qt.PointingHandCursor)

        self._btn_stop = QPushButton("■  STOP")
        self._btn_stop.setObjectName("btnStop")
        self._btn_stop.setCursor(Qt.PointingHandCursor)

        lay.addWidget(logo_block)
        lay.addSpacing(28)
        lay.addWidget(vsep())
        lay.addSpacing(28)
        lay.addWidget(conn_block)
        lay.addStretch()
        lay.addWidget(self._session_lbl)
        lay.addSpacing(28)
        lay.addWidget(vsep())
        lay.addSpacing(20)
        lay.addWidget(self._btn_start)
        lay.addSpacing(8)
        lay.addWidget(self._btn_pause)
        lay.addSpacing(8)
        lay.addWidget(self._btn_stop)
        return hdr

    def _init_status_bar(self):
        bar = QStatusBar()
        bar.setStyleSheet(_STATUSBAR_QSS)
        self.setStatusBar(bar)
        bar.showMessage("READY  ·  All systems initialising")

    # ── SIGNALS ───────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self._btn_start.clicked.connect(self._on_start)
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_stop.clicked.connect(self._on_stop)

        self.ctrl_panel.slot_panel_selected.connect(self._on_panel_slot_move)
        self.ctrl_panel.export_clicked.connect(self._on_export)

        self.cam_panel.pick_cancelled.connect(self._on_pick_cancelled)

        self.ctrl_panel.viewer_slot_mode_changed.connect(
            lambda on: self.robot_viewer.toggle_slot_mode(on)
        )
        self.ctrl_panel.viewer_grid_changed.connect(
            lambda on: self.robot_viewer.toggle_grid(on)
        )
        self.ctrl_panel.viewer_autorot_changed.connect(
            lambda on: self.robot_viewer.toggle_autorot(on)
        )
        self.cam_panel.pick_target_selected.connect(
            lambda rx, ry: self.workflow.set_pick_target(rx, ry)
        )

        self.diamond_selector.vibrate_needed.connect(self.esp32.vibrate)
        self.diamond_selector.vibrate_needed.connect(
            self.cam_panel.increment_vibrations
        )
        self.diamond_selector.scan_failed.connect(
            lambda msg: self.statusBar().showMessage(f"SCAN  ·  {msg}")
        )
        self.diamond_selector.ready_changed.connect(self._on_next_pick_ready_changed)

        self.ctrl_panel.manual_mode_changed.connect(self._on_manual_mode_changed)
        self.ctrl_panel.speed_override_changed.connect(self.robot.set_speed_override)

        self.workflow.state_changed.connect(self._on_state_changed)
        self.workflow.alert_raised.connect(self._on_alert)
        self.workflow.cycle_complete.connect(self._on_cycle_complete)
        self.workflow.pick_failed.connect(
            lambda: self.statusBar().showMessage(
                "PICK FAILED  ·  No diamond held — rescanning"
            )
        )
        self.workflow.tray_pick_failed.connect(self._on_tray_pick_failed)
        self.workflow.scale_pick_failed.connect(
            lambda: self.statusBar().showMessage(
                "SCALE PICK FAILED  ·  3 attempts exhausted — operator required"
            )
        )
        self.workflow.scale_retry_pick.connect(self._on_scale_retry_pick)
        self.workflow.vibrate_requested.connect(self._on_workflow_vibrate_requested)
        self.workflow.scan_requested.connect(self._on_scan_requested)
        self.workflow.pick_requested.connect(self._on_pick_requested)
        self.workflow.weigh_requested.connect(self._on_weigh_requested)
        self.workflow.sort_requested.connect(self._on_sort_requested)
        self.workflow.home_requested.connect(self._on_home_requested)

        self.scale.weight_updated.connect(self._on_scale_weight)
        self.scale.connected.connect(lambda ok: self._set_conn("Scale", ok))

        self.pressure_sensor.pressure_updated.connect(self.tele.update_pressure)
        self.pressure_sensor.pressure_updated.connect(self._on_pressure_updated)
        self.pressure_sensor.pressure_updated.connect(self.cam_panel.update_pressure)
        self.pressure_sensor.connected.connect(
            lambda ok: self._set_conn("Pressure", ok)
        )
        self.pressure_sensor.error.connect(
            lambda msg: self.statusBar().showMessage(f"PRESSURE  ·  {msg}")
        )

        self.esp32.diamond_picked.connect(self._on_diamond_picked)
        self.esp32.connected.connect(lambda ok: self._set_conn("ESP32", ok))
        self.esp32.connected.connect(self._on_esp32_connected)

        self.camera.frame_ready.connect(self.cam_panel.update_frame)
        self.camera.diamonds_found.connect(self._on_diamonds_detected)
        self.camera.connected.connect(lambda ok: self._set_conn("Camera", ok))

        self.robot.joints_updated.connect(self._on_joints_updated)
        self.robot.move_complete.connect(self._on_robot_move_complete)
        self.robot.connected.connect(lambda ok: self._set_conn("Robot", ok))
        self.robot.error.connect(
            lambda msg: self.statusBar().showMessage(f"ROBOT  ·  {msg}")
        )

        self.cam_panel.vibrate_clicked.connect(self.workflow.trigger_manual_vibrate)
        self.cam_panel.home_requested.connect(
            lambda: QTimer.singleShot(0, self.robot.move_home)
        )
        self.cam_panel.tray_requested.connect(
            lambda: QTimer.singleShot(0, lambda: self.robot.move_to_tray_xy(0, 0))
        )
        self.cam_panel.scale_requested.connect(
            lambda: QTimer.singleShot(0, self.robot.move_to_scale)
        )
        self.cam_panel.pump_on_requested.connect(self._on_pump_on_requested)
        self.cam_panel.pump_off_requested.connect(self._on_pump_off_requested)
        self.cam_panel.emergency_stop_requested.connect(self._on_emergency_stop)
        self.cam_panel.emergency_reset_requested.connect(self._on_emergency_reset)
        self.cam_panel.pick_and_place_requested.connect(self._on_pick_and_place)
        self.ctrl_panel.slot_selected_for_sort.connect(self._on_slot_selected_for_sort)
        self.robot_viewer.slot_selected.connect(self._on_viewer_slot_selected)
        self.robot_viewer.slot_selected.connect(self.ctrl_panel.highlight_panel_slot)
        self.ctrl_panel.setup_tab.position_saved.connect(self.robot.update_position)

    # ── SEQUENCE RESET ────────────────────────────────────────────────────────
    def _reset_sequence_flags(self):
        self._pick_step  = -1
        self._weigh_step = -1
        self._sort_step  = -1
        self._seq_busy   = False

    # ── ACTION HANDLERS ───────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_start(self):
        if self.workflow.state == State.PAUSED:
            self.workflow.resume()
        else:
            if not self.diamond_selector.is_session_open():
                self.diamond_selector.open_session()
            self.workflow.start()

    @pyqtSlot()
    def _on_pause(self):
        if self.workflow.is_running:
            self.workflow.pause()

    @pyqtSlot()
    def _on_stop(self):
        self.workflow.stop()
        self.diamond_selector.close_session()
        self._reset_sequence_flags()
        self._restore_idle_ui()
        self.ctrl_panel.refresh_slot_colors()

    def _on_emergency_stop(self):
        self.workflow.stop()
        self.diamond_selector.close_session()
        self._reset_sequence_flags()
        self.esp32.pump_off()
        self.robot.servo_off()
        self.tele.update_pump(False)
        self.tele.update_robot("STOPPED", _T.RED)
        self.cam_panel.set_pick_place_enabled(False)
        self.cam_panel.set_pick_place_status("● Emergency Stop Active", _T.RED)
        self.ctrl_panel.set_waiting_for_slot(False)
        self.statusBar().showMessage("⚠  EMERGENCY STOP  ·  Pump off, servo off")

    def _on_emergency_reset(self):
        self._reset_sequence_flags()
        self.robot.servo_on()
        self.tele.update_robot("IDLE", _T.TXT_DIM)
        self.cam_panel.set_pick_place_enabled(True)
        self.cam_panel.set_pick_place_status(
            "● Ready — Place diamond on tray first", _T.TXT_DIM
        )
        self.statusBar().showMessage("READY  ·  System reset — press START to begin")

    @pyqtSlot()
    def _on_pick_and_place(self):
        if self.workflow.state != State.IDLE:
            return
        self._reset_sequence_flags()
        self.workflow._running   = True
        self.workflow._auto_mode = False
        self.workflow._set_state(State.WAITING_CAMERA)
        self.cam_panel.set_pick_place_status(
            "● Click a diamond in the camera to pick it", _T.BLUE
        )
        self.statusBar().showMessage(
            "WAITING CAMERA  ·  Click a diamond to pick it"
        )
        self.cam_panel.set_workflow(self.workflow)
        self.cam_panel._open_tray_detector()

    @pyqtSlot(int)
    def _on_slot_selected_for_sort(self, slot_index: int):
        if self.workflow.state != State.WAITING_SLOT:
            return
        from hardware.robot_controller import SLOT_ORDER
        label = SLOT_ORDER[slot_index] if slot_index < len(SLOT_ORDER) else str(slot_index)
        self.ctrl_panel.update_current_slot(label)
        self.workflow.trigger_slot_selected(slot_index)
        self.statusBar().showMessage(
            f"SORTING  ·  Moving to slot {label}…"
        )

    @pyqtSlot()
    def _on_export(self):
        try:
            path = self.session.export_xlsx()
            QMessageBox.information(
                self, "Export Complete",
                f"Saved to:\n{os.path.abspath(path)}"
            )
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    # ── ROBOT MOVE COMPLETE ───────────────────────────────────────────────────

    @pyqtSlot()
    def _on_robot_move_complete(self):
        if self._seq_busy:
            print("[Seq] move_complete ignored — seq_busy")
            return
        self._seq_busy = True

        state = self.workflow.state

        if state == State.PICKING:
            self._pick_step += 1
            print(f"[Seq] PICKING step {self._pick_step}")

            if self._pick_step == _PICK_STEP_TRAY:
                QTimer.singleShot(0, self._do_pick_down)

            elif self._pick_step == _PICK_STEP_DOWN:
                self.statusBar().showMessage("PICKING  ·  Gripping diamond…")
                QTimer.singleShot(PICK_DOWN_DWELL_MS, self._do_pick_up)

            elif self._pick_step == _PICK_STEP_UP:
                self._seq_busy = False
                from config import PICK_PRESSURE_SETTLE_MS
                QTimer.singleShot(PICK_PRESSURE_SETTLE_MS, self._do_tray_pick_pressure_check)

        elif state == State.WEIGHING:
            self._weigh_step += 1
            print(f"[Seq] WEIGHING step {self._weigh_step}")

            if self._weigh_step == _WEIGH_STEP_TRAVEL:
                QTimer.singleShot(0, self._do_place_on_scale)

            elif self._weigh_step == _WEIGH_STEP_PLACE:
                self.statusBar().showMessage("WEIGHING  ·  Settling diamond on scale…")
                QTimer.singleShot(SCALE_PLACE_DWELL_MS, self._do_release_on_scale)

            elif self._weigh_step == _WEIGH_STEP_CLEAR:
                self.statusBar().showMessage(
                    "WEIGHING  ·  Measuring weight — robot clear of scale…"
                )
                QTimer.singleShot(
                    SCALE_SETTLE_MS // 4,
                    self.workflow.arm_weight_capture
                )
                QTimer.singleShot(SCALE_SETTLE_MS, self._do_pump_on_then_pick_from_scale)

            elif self._weigh_step == _WEIGH_STEP_PICK:
                self.statusBar().showMessage(
                    "WEIGHING  ·  Re-gripping diamond — lifting to travel height…"
                )
                QTimer.singleShot(0, self._do_lift_from_scale)

            elif self._weigh_step == _WEIGH_STEP_LIFT:
                from config import PRESSURE_DIAMOND_THRESHOLD, PRESSURE_WEAK_THRESHOLD
                pressure = self._get_pressure()
                diamond_held = pressure >= PRESSURE_DIAMOND_THRESHOLD
                diamond_weak = (not diamond_held) and (pressure >= PRESSURE_WEAK_THRESHOLD)
                print(f"[Seq] Scale pick lift — pressure={pressure} held={diamond_held} weak={diamond_weak}")
                self._seq_busy = False
                if diamond_held:
                    self.workflow.on_scale_pick_confirmed(success=True)
                elif diamond_weak:
                    self.workflow.on_scale_pick_confirmed(success=False, weak=True)
                else:
                    self.workflow.on_scale_pick_confirmed(success=False, weak=False)

        elif state == State.SORTING:
            self._sort_step += 1
            slot = self._pending_slot
            print(f"[Seq] SORTING step {self._sort_step} slot={slot}")

            if self._sort_step == _SORT_STEP_TRAVEL:
                QTimer.singleShot(0, lambda: self._do_drop_in_slot(slot))
            elif self._sort_step == _SORT_STEP_DROP:
                self.esp32.release()
                self.tele.update_pump(False)
                self.cam_panel.set_pump_button_state(False)
                QTimer.singleShot(300, lambda: self._do_lift_from_slot(slot))
            elif self._sort_step == _SORT_STEP_RELEASE:
                self._seq_busy = False
                self.workflow.on_sort_complete()

        elif state == State.HOMING:
            self._seq_busy = False
            self.workflow.on_home_complete()

        else:
            self._seq_busy = False
            self.statusBar().showMessage("READY  ·  Move complete")
            if self._manual_move_slot:
                self.esp32.led_off(self._manual_move_slot)
                self._manual_move_slot = None

    @pyqtSlot()
    def _on_scan_requested(self):
        if not self.workflow._auto_mode:
            self.camera.start_detection()

    # ── DIAMOND SELECTOR UI FEEDBACK ──────────────────────────────────────────

    @pyqtSlot()
    def _on_workflow_vibrate_requested(self):
        if not self.workflow._auto_mode:
            self.esp32.vibrate()

    @pyqtSlot(bool)
    def _on_next_pick_ready_changed(self, ready: bool):
        if self.workflow._auto_mode and self.workflow.is_running:
            if ready:
                self.statusBar().showMessage("AUTO  ·  Next diamond ready")
            else:
                self.statusBar().showMessage("AUTO  ·  Scanning for next diamond…")

    # ── WORKFLOW SIGNAL HANDLERS ──────────────────────────────────────────────

    @pyqtSlot(float, float)
    def _on_pick_requested(self, x: float, y: float):
        self._pick_step = -1
        if self.workflow.state == State.WAITING_CAMERA and not self.workflow._auto_mode:
            return
        self.esp32.pick()
        self.tele.update_pump(True)
        self.cam_panel.set_pump_button_state(True)
        QTimer.singleShot(0, lambda: self.robot.move_to_tray_xy(x, y))

    @pyqtSlot()
    def _on_weigh_requested(self):
        self._weigh_step = -1
        QTimer.singleShot(0, self.robot.move_to_scale)

    @pyqtSlot(int)
    def _on_sort_requested(self, slot_index: int):
        self._sort_step    = -1
        self._pending_slot = slot_index
        from hardware.robot_controller import SLOT_ORDER
        label = SLOT_ORDER[slot_index] if slot_index < len(SLOT_ORDER) else str(slot_index)
        self.esp32.led_on(label)
        self.ctrl_panel.update_current_slot(label)
        QTimer.singleShot(0, lambda: self.robot.move_to_slot(slot_index))

    @pyqtSlot()
    def _on_home_requested(self):
        self.statusBar().showMessage("HOMING  ·  Returning to home position…")
        QTimer.singleShot(0, self.robot.move_home)

    # ── WORKFLOW STATE CHANGE ─────────────────────────────────────────────────

    @pyqtSlot(bool)
    def _on_esp32_connected(self, ok: bool):
        if ok:
            QTimer.singleShot(
                2000, lambda: self._update_status_indicator(self.workflow.state)
            )

    @pyqtSlot(object)
    def _on_state_changed(self, state: State):
        name, sub, code = STATE_INFO[state]
        self.cam_panel.set_workflow_state(state)
        self.ctrl_panel.update_workflow_state(state)
        self.robot_viewer.set_state(code, name)
        self._update_status_indicator(state)

        robot_status = {
            State.IDLE:           ("IDLE",           _T.TXT_DIM),
            State.SCANNING:       ("SCANNING",       _T.BLUE),
            State.VIBRATING:      ("VIBRATING",      _T.AMBER),
            State.WAITING_CAMERA: ("AT TRAY",        _T.BLUE),
            State.PICKING:        ("MOVING",         _T.GREEN_HI),
            State.WEIGHING:       ("HOLD",           _T.BLUE),
            State.WAITING_SLOT:   ("WAITING SLOT",   _T.AMBER),
            State.SORTING:        ("MOVING",         _T.GREEN_HI),
            State.HOMING:         ("HOMING",         _T.GREEN_MID),
            State.ALERT:          ("STOPPED",        _T.RED),
            State.COMPLETE:       ("COMPLETE",       _T.GREEN_HI),
        }.get(state, ("IDLE", _T.TXT_DIM))

        self.tele.update_robot(*robot_status)
        pump_on = state in (State.PICKING, State.WEIGHING, State.SORTING)
        self.tele.update_pump(pump_on)
        self.cam_panel.set_pump_button_state(pump_on)
        self.statusBar().showMessage(f"{name.upper()}  ·  {sub}")

        if state == State.IDLE:
            self._restore_idle_ui()

        elif state == State.HOMING:
            self.cam_panel.set_pick_place_enabled(False)
            self.cam_panel.set_pick_place_status(
                "● Cycle complete — returning home…", _T.GREEN_MID
            )
            self.ctrl_panel.set_waiting_for_slot(False)

        elif state == State.WAITING_CAMERA:
            self.cam_panel.set_pick_place_enabled(False)
            self.cam_panel.set_pick_place_status(
                "● Robot moving to tray…", _T.BLUE
            )
            self.ctrl_panel.set_waiting_for_slot(False)

        if state == State.PICKING:
            self.cam_panel.set_pick_place_enabled(False)
            self.cam_panel.set_pick_place_status(
                "● Picking diamond from tray…", _T.GREEN_HI
            )
            self.ctrl_panel.set_waiting_for_slot(False)

        elif state == State.WEIGHING:
            self.cam_panel.set_pick_place_enabled(False)
            self.cam_panel.set_pick_place_status(
                "● Measuring weight on scale…", _T.BLUE
            )
            self.ctrl_panel.set_waiting_for_slot(False)

        elif state == State.WAITING_SLOT:
            self.cam_panel.set_pick_place_enabled(False)
            self.cam_panel.set_pick_place_status(
                f"● Weight: {self.workflow._current_weight:.4f} ct  —  Select a slot",
                _T.AMBER
            )
            self.ctrl_panel.set_waiting_for_slot(True)
            self.ctrl_panel.show_weight_on_slots(self.workflow._current_weight)
            self.ctrl_panel._tabs.setCurrentIndex(1)

        elif state == State.SORTING:
            self.cam_panel.set_pick_place_enabled(False)
            self.cam_panel.set_pick_place_status(
                "● Placing diamond in slot…", _T.GREEN_HI
            )
            self.ctrl_panel.set_waiting_for_slot(False)

    def _update_status_indicator(self, state: State):
        if state == State.PICKING:
            active = "GREEN"
        elif state in (State.WEIGHING, State.VIBRATING):
            active = "YELLOW"
        elif state == State.SORTING:
            active = "BLUE"
        elif state == State.ALERT:
            active = "RED"
        else:
            active = "WHITE"

        for name in ("RED", "YELLOW", "GREEN", "BLUE", "WHITE"):
            if name == active:
                self.esp32.led_on(name)
            else:
                self.esp32.led_off(name)

    def _restore_idle_ui(self):
        self.cam_panel.set_pick_place_enabled(True)
        self.cam_panel.set_pick_place_status(
            "● Ready — Press START for auto or PICK & PLACE for manual", _T.TXT_DIM
        )
        self.ctrl_panel.set_waiting_for_slot(False)
        self.ctrl_panel.update_current_slot("—")

    def _on_pump_on_requested(self):
        blocked_states = (
            State.PICKING, State.WEIGHING, State.SORTING,
            State.SCANNING, State.VIBRATING, State.HOMING,
        )
        if self.workflow.state in blocked_states:
            self.statusBar().showMessage(
                "PUMP  ·  Cannot turn ON during active robot motion"
            )
            return
        self.esp32.pump_on()
        self.tele.update_pump(True)
        self.cam_panel.set_pump_button_state(True)
        self.statusBar().showMessage("PUMP  ·  ON — manual activation")

    def _on_pump_off_requested(self):
        self.esp32.pump_off()
        self.tele.update_pump(False)
        self.cam_panel.set_pump_button_state(False)
        self.statusBar().showMessage("PUMP  ·  OFF — manual release")

    @pyqtSlot(bool)
    def _on_manual_mode_changed(self, manual_on: bool):
        if manual_on:
            if self.workflow.is_running:
                self.workflow.stop()
                self.diamond_selector.close_session()
                self._reset_sequence_flags()

            det_mode = self.cam_panel._det_mode.findChildren(QLabel)
            if len(det_mode) >= 2:
                det_mode[-1].setText("MANUAL")
                det_mode[-1].setStyleSheet(
                    f"font-size: 15px; font-weight: 700; color: {_T.AMBER};"
                    f"font-family: {_T.FONT_DISPLAY}; border: none;"
                )

            self.cam_panel.set_pick_place_enabled(True)
            self.cam_panel.set_pick_place_status(
                "● Manual mode — click PICK & PLACE to start", _T.AMBER
            )
            self._btn_start.setEnabled(False)
            self.statusBar().showMessage(
                "MANUAL OVERRIDE  ·  Auto mode stopped — use PICK & PLACE"
            )
        else:
            det_mode = self.cam_panel._det_mode.findChildren(QLabel)
            if len(det_mode) >= 2:
                det_mode[-1].setText("AUTO")
                det_mode[-1].setStyleSheet(
                    f"font-size: 15px; font-weight: 700; color: {_T.GREEN_HI};"
                    f"font-family: {_T.FONT_DISPLAY}; border: none;"
                )

            self._btn_start.setEnabled(True)
            self._restore_idle_ui()
            self.statusBar().showMessage(
                "AUTO MODE  ·  Press START to begin automatic sorting"
            )

    @pyqtSlot(str)
    def _on_alert(self, msg: str):
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                    QDoubleSpinBox, QComboBox, QLabel,
                                    QPushButton, QFrame)
        from hardware.robot_controller import SLOT_ORDER

        if self.workflow.state != State.ALERT:
            QMessageBox.warning(self, "⚠  ALERT", msg)
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("⚠  No Slot Matched — Manual Override")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(f"""
            QDialog {{ background: {_T.BG_BASE}; color: {_T.TXT_HI}; }}
            QLabel {{ color: {_T.TXT_HI}; background: transparent;
                      font-family: {_T.FONT_LABEL}; }}
            QDoubleSpinBox, QComboBox {{
                background: {_T.BG_SURFACE}; border: 1px solid {_T.BG_BORDER};
                border-radius: 8px; color: {_T.TXT_HI};
                padding: 5px 8px; font-family: {_T.FONT_MONO};
                font-size: 12px; }}
            QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {_T.BRAND}; }}
            QPushButton {{
                background: {_T.BG_SURFACE}; border: 1px solid {_T.BG_BORDER};
                border-radius: 8px; color: {_T.TXT_MID};
                font-family: {_T.FONT_LABEL};
                font-size: 10px; letter-spacing: 1px; padding: 7px 16px; }}
            QPushButton:hover {{
                border-color: {_T.BRAND}; color: {_T.BRAND};
                background: rgba(143,217,182,0.10); }}
        """)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        msg_lbl = QLabel(msg)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"color: {_T.RED}; font-size: 12px; padding: 10px;"
            f"border: 1px solid rgba(224,133,133,0.30); border-radius: 8px;"
            f"background: rgba(224,133,133,0.08); font-family: {_T.FONT_LABEL};"
        )
        lay.addWidget(msg_lbl)

        meas_row = QHBoxLayout()
        meas_row.addWidget(QLabel("Measured weight:"))
        meas_val = QLabel(f"{self.workflow._current_weight:.4f} ct")
        meas_val.setStyleSheet(f"color: {_T.BRAND}; font-size: 14px; font-weight: 700;")
        meas_row.addWidget(meas_val)
        meas_row.addStretch()
        lay.addLayout(meas_row)

        w_row = QHBoxLayout()
        w_row.addWidget(QLabel("Override weight (ct):"))
        w_spin = QDoubleSpinBox()
        w_spin.setRange(0.01, 9.99)
        w_spin.setDecimals(4)
        w_spin.setSingleStep(0.01)
        w_spin.setValue(
            self.workflow._current_weight if self.workflow._current_weight > 0 else 0.01
        )
        w_spin.setFixedWidth(120)
        w_row.addWidget(w_spin)
        w_row.addStretch()
        lay.addLayout(w_row)

        s_row = QHBoxLayout()
        s_row.addWidget(QLabel("Select slot:"))
        slot_combo = QComboBox()
        for i, name in enumerate(SLOT_ORDER):
            slot_combo.addItem(name, i)
        slot_combo.setFixedWidth(120)
        s_row.addWidget(slot_combo)
        s_row.addStretch()
        lay.addLayout(s_row)

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"background: {_T.BG_BORDER}; border: none;")
        lay.addWidget(div)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn  = QPushButton("CANCEL — STOP AUTO")
        confirm_btn = QPushButton("CONFIRM — PLACE DIAMOND")
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(143,217,182,0.10); color: {_T.BRAND};
                border: 1.5px solid {_T.BRAND}; border-radius: 8px;
                font-family: {_T.FONT_LABEL}; font-size: 10px;
                font-weight: 700; letter-spacing: 1px; padding: 7px 16px; }}
            QPushButton:hover {{
                background: rgba(143,217,182,0.20); }}
        """)

        def do_cancel():
            self.workflow.stop()
            self.diamond_selector.close_session()
            self._restore_idle_ui()
            dlg.reject()

        def do_confirm():
            weight   = round(w_spin.value(), 4)
            slot_idx = slot_combo.currentData()
            self.workflow.trigger_manual_weight_and_slot(weight, slot_idx)
            dlg.accept()

        cancel_btn.clicked.connect(do_cancel)
        confirm_btn.clicked.connect(do_confirm)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(confirm_btn)
        lay.addLayout(btn_row)

        dlg.exec_()

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _set_conn(self, name: str, ok: bool):
        dot = self._conn_dots.get(name)
        lbl = self._conn_labels.get(name)
        if dot:
            color = _T.GREEN_HI if ok else _T.RED
            dot.setStyleSheet(
                f"font-size: 9px; color: {color}; border: none; background: transparent;"
            )
        if lbl:
            color = _T.TXT_MID if ok else "#8A5050"
            lbl.setStyleSheet(
                f"font-family: {_T.FONT_LABEL}; font-size: 10px;"
                f"color: {color}; letter-spacing: 1px; border: none; background: transparent;"
            )
        if name == "Camera":
            self.cam_panel.set_connected(ok)

    @pyqtSlot(object)
    def _on_cycle_complete(self, record):
        from hardware.robot_controller import SLOT_ORDER
        self.ctrl_panel.add_log_entry(
            record.diamond_id, record.weight_ct,
            record.slot_index, record.timestamp
        )
        self.ctrl_panel.update_progress(self.session.sorted_count, 66)
        self.ctrl_panel.update_session_stats(
            self.session.total_weight_ct, self.session.avg_weight_ct
        )
        slot_name = (
            SLOT_ORDER[record.slot_index]
            if record.slot_index < len(SLOT_ORDER)
            else str(record.slot_index)
        )
        self.ctrl_panel.mark_slot_sorted(slot_name, record.weight_ct)
        self.esp32.led_off(slot_name)

    @pyqtSlot()
    def _on_diamond_picked(self):
        if (self.workflow.state == State.PICKING
                and self._pick_step == _PICK_STEP_UP):
            self.workflow.on_pick_complete()

    @pyqtSlot(list)
    def _on_diamonds_detected(self, diamonds: list):
        self.cam_panel.update_diamonds(diamonds)
        if not self.workflow._auto_mode:
            self.workflow.on_diamonds_detected(diamonds)

    @pyqtSlot(float)
    def _on_scale_weight(self, ct: float):
        self.workflow.on_scale_reading(ct)
        self.tele.update_scale(ct)
        self.robot_viewer.update_scale(ct)

    @pyqtSlot(float, float, float, float)
    def _on_joints_updated(self, j1, j2, j3, j4):
        self.tele.update_joints(j1, j2, j3, j4)
        self.robot_viewer.update_joints(j1, j2, j3, j4)

    @pyqtSlot(int)
    def _on_viewer_slot_selected(self, slot_index: int):
        if self.workflow.state in (State.IDLE, State.PAUSED):
            self.robot.move_to_slot(slot_index)
            self.statusBar().showMessage(
                f"MANUAL  ·  Moving to slot S-{slot_index + 1:02d}"
            )
        else:
            self.statusBar().showMessage(
                "BUSY  ·  Cannot select slot — pause the workflow first"
            )

    @pyqtSlot(int)
    def _on_panel_slot_move(self, slot_index: int):
        if self.workflow.state not in (State.IDLE, State.PAUSED):
            self.statusBar().showMessage(
                "BUSY  ·  Cannot move — stop the workflow first"
            )
            return
        self.robot.move_to_slot(slot_index)
        self.robot_viewer.select_slot_in_viewer(slot_index)
        from hardware.robot_controller import SLOT_ORDER
        label = SLOT_ORDER[slot_index] if slot_index < len(SLOT_ORDER) else str(slot_index)
        self.statusBar().showMessage(
            f"MOVING TO SLOT  {label}  ·  Z = 144.5 mm"
        )
        self._manual_move_slot = label
        self.esp32.led_on(label)
        self.ctrl_panel.update_current_slot(label)

    # ── Sequence helpers ──────────────────────────────────────────────────────

    def _do_tray_pick_pressure_check(self):
        from config import PRESSURE_DIAMOND_THRESHOLD
        pressure = self._get_pressure()
        diamond_held = pressure > PRESSURE_DIAMOND_THRESHOLD
        print(f"[Seq] Tray pick settle check — pressure={pressure} held={diamond_held}")
        self.workflow.on_tray_pick_confirmed(diamond_held)

    def _on_tray_pick_failed(self):
        self.esp32.pump_off()
        self.tele.update_pump(False)
        self.cam_panel.set_pump_button_state(False)
        self.diamond_selector.on_pick_failed()
        self.statusBar().showMessage(
            "PICK FAILED  ·  Releasing pump — returning home to rescan…"
        )
        QTimer.singleShot(200, self._do_safe_home_after_pick_fail)

    def _do_safe_home_after_pick_fail(self):
        """Called 200ms after pump off — diamond has settled, safe to home."""
        if self.workflow._auto_mode and self.workflow._running:
            self.workflow._set_state(State.HOMING)
            self.workflow.home_requested.emit()
        else:
            self.workflow._running = False
            self.workflow._set_state(State.IDLE)

    def _do_pick_down(self):
        self._seq_busy = False
        self.robot.pick_down(pressure_getter=self._get_pressure)

    def _do_pick_up(self):
        self._seq_busy = False
        self.robot.pick_up()

    def _do_place_on_scale(self):
        self._seq_busy = False
        self.robot.place_on_scale()

    def _do_pick_from_scale(self):
        self._seq_busy = False
        self.robot.pick_from_scale(pressure_getter=self._get_pressure)
        
    def _on_scale_retry_pick(self):
        """
        Retry scale pick directly — weight already locked, no re-weigh.
        Robot goes straight back down to pick from scale again.
        """
        self.statusBar().showMessage(
            f"SCALE RETRY  ·  Attempt {self.workflow._scale_pick_retries}/3 — re-gripping…"
        )
        self._weigh_step = _WEIGH_STEP_PICK - 1
        QTimer.singleShot(0, self._do_pump_on_then_pick_from_scale)

    def _do_pump_on_then_pick_from_scale(self):
        """Pump ON first, wait PICK_GRIP_DELAY_MS, then shaft descends."""
        self.esp32.pick()
        self.tele.update_pump(True)
        self.cam_panel.set_pump_button_state(True)
        self.statusBar().showMessage(
            "WEIGHING  ·  Pump ON — descending to grip diamond on scale…"
        )
        QTimer.singleShot(PICK_GRIP_DELAY_MS, self._do_pick_from_scale)

    def _do_lift_from_scale(self):
        self._seq_busy = False
        self.robot.lift_from_scale()

    def _do_drop_in_slot(self, slot: int):
        self._seq_busy = False
        self.robot.drop_in_slot(slot)

    def _do_lift_from_slot(self, slot: int):
        self._seq_busy = False
        self.robot.lift_from_slot(slot)

    def _do_lift_clear_from_scale(self):
        self._seq_busy = False
        self.robot.lift_clear_from_scale()

    def _do_release_on_scale(self):
        self.esp32.release()
        self.tele.update_pump(False)
        self.cam_panel.set_pump_button_state(False)
        self.statusBar().showMessage(
            "WEIGHING  ·  Diamond placed — lifting clear to measure…"
        )
        self._seq_busy = False
        self.robot.lift_clear_from_scale()
        
    @pyqtSlot(int)
    def _on_pressure_updated(self, value: int):
        self._last_pressure = value

    def _get_pressure(self) -> int:
        return self._last_pressure

    def _on_pick_cancelled(self):
        if self.workflow.state == State.WAITING_CAMERA:
            self.workflow.stop()
            self._reset_sequence_flags()
            self.robot.move_home()
            self.statusBar().showMessage("PICK CANCELLED  ·  Returned to IDLE")

    def closeEvent(self, event):
        self.workflow.stop()
        self.diamond_selector.close_session()
        for hw in [self.scale, self.esp32, self.camera, self.robot,
                   self.pressure_sensor]:
            hw.stop()
        event.accept()