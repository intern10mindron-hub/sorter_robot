from __future__ import annotations
from enum import Enum, auto
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from config import (
    VIBRATION_DURATION, SCALE_SETTLE_MS, MIN_DIAMOND_CT,
    Z_TRAY_PICK, Z_SAFE_TRAVEL, Z_SCALE_PLACE, Z_SCALE_PICK, Z_SLOT_DROP,
)

# Poll interval used while waiting for DiamondSelector to have the next
# diamond ready (only happens if the selector hasn't caught up yet —
# normally it's already ready by the time sort completes, since it runs
# continuously in the background the whole time the robot is busy).
NEXT_PICK_POLL_MS = 150


class State(Enum):
    IDLE           = auto()
    SCANNING       = auto()
    VIBRATING      = auto()
    WAITING_CAMERA = auto()   # Manual mode: waiting for operator to click diamond
    PICKING        = auto()
    WEIGHING       = auto()
    WAITING_SLOT   = auto()
    SORTING        = auto()
    HOMING         = auto()   # Still used for manual "go home" actions and
                               # explicit STOP/emergency flows — NOT used
                               # between cycles in the continuous auto loop.
    ALERT          = auto()
    PAUSED         = auto()
    COMPLETE       = auto()

STATE_INFO = {
    State.IDLE:           ("IDLE",           "Waiting to start",               "idle"),
    State.SCANNING:       ("SCANNING",       "Detecting diamonds on tray",     "sc"),
    State.VIBRATING:      ("VIBRATING",      "Separating diamond cluster",     "vb"),
    State.WAITING_CAMERA: ("WAITING CAMERA", "Select a diamond to pick",       "wc"),
    State.PICKING:        ("PICKING",        "Robot moving to pick up",        "pk"),
    State.WEIGHING:       ("WEIGHING",       "Reading scale weight",           "wg"),
    State.WAITING_SLOT:   ("WAITING SLOT",   "Select a slot to place diamond", "ws"),
    State.SORTING:        ("SORTING",        "Placing diamond in slot",        "sr"),
    State.HOMING:         ("HOMING",         "Returning to home position",     "hm"),
    State.ALERT:          ("ALERT",          "Operator action required",       "al"),
    State.PAUSED:         ("PAUSED",         "Session paused",                 "pa"),
    State.COMPLETE:       ("COMPLETE",       "All diamonds sorted",            "ok"),
}


class Workflow(QObject):
    state_changed     = pyqtSignal(object)
    alert_raised      = pyqtSignal(str)
    pick_requested    = pyqtSignal(float, float)
    weigh_requested   = pyqtSignal()
    sort_requested    = pyqtSignal(int)
    vibrate_requested = pyqtSignal()
    scan_requested    = pyqtSignal()
    home_requested    = pyqtSignal()
    cycle_complete    = pyqtSignal(object)
    pick_failed           = pyqtSignal()
    scale_pick_failed     = pyqtSignal()
    tray_pick_failed      = pyqtSignal()
    scale_retry_pick      = pyqtSignal()

    def __init__(self, session, slot_manager, parent=None):
        super().__init__(parent)
        self.session      = session
        self.slot_manager = slot_manager
        self._state       = State.IDLE
        self._running     = False
        self._paused      = False
        self._auto_mode   = False
        self._current_diamond_xy = (0.0, 0.0)
        self._current_weight     = 0.0
        self._pending_slot       = 0
        self._scale_pick_retries = 0

        # Continuous auto-loop support — set by main_window so the
        # workflow can ask "is the next diamond ready yet?" directly,
        # without going through HOMING/SCANNING states between cycles.
        self._diamond_selector = None

        # Weight capture flags:
        # Armed by main_window when robot arrives at Z_SCALE_CLEAR (144.5) after
        # placing diamond and turning pump OFF — the scale now reads free weight.
        # Locked as soon as the first valid non-zero reading arrives; all further
        # scale emissions are ignored until the next cycle resets these flags.
        self._weight_capture_armed = False
        self._weight_locked        = False

        self._vib_timer = QTimer(self)
        self._vib_timer.setSingleShot(True)
        self._vib_timer.timeout.connect(self._after_vibration)

        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._read_scale_settled)

        # Polls DiamondSelector.is_ready() in the continuous auto loop.
        # Started only when sort completes and the next diamond isn't
        # ready yet (rare — selector normally keeps up while the robot
        # is busy with pick/weigh/sort).
        self._next_pick_timer = QTimer(self)
        self._next_pick_timer.timeout.connect(self._poll_next_pick_ready)

    # ── PROPERTIES ────────────────────────────────────────────────────────────

    @property
    def state(self) -> State:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._running

    def _set_state(self, s: State):
        self._state = s
        self.state_changed.emit(s)

    # ── DIAMOND SELECTOR WIRING ───────────────────────────────────────────────

    def set_diamond_selector(self, selector):
        """
        Called once by main_window after constructing the workflow.
        The workflow uses selector.is_ready()/consume_next()/clear_in_progress()
        to drive the continuous auto loop without HOMING/SCANNING between
        cycles.
        """
        self._diamond_selector = selector

    # ── WEIGHT CAPTURE CONTROL ────────────────────────────────────────────────

    def arm_weight_capture(self):
        """
        Called by main_window when the robot arrives at Z_SCALE_CLEAR (144.5)
        after placing the diamond and turning the pump OFF. The scale now reads
        the diamond's free weight. The next valid non-zero reading is locked in.
        """
        self._weight_capture_armed = True
        self._weight_locked        = False
        print("[Workflow] Weight capture ARMED")

    def disarm_weight_capture(self):
        """
        Called to cancel weight capture (e.g. on stop/reset).
        Does NOT clear _current_weight — the locked value is kept until
        the next cycle resets it in set_pick_target / on_diamonds_detected / stop.
        """
        self._weight_capture_armed = False
        print("[Workflow] Weight capture DISARMED")

    # ── PUBLIC CONTROLS ───────────────────────────────────────────────────────

    def start(self):
        """
        Start full auto mode.

        The continuous loop: main_window opens the DiamondSelector session
        before calling this (or right after), and this just begins waiting
        for the first ready diamond — using the exact same mechanism as
        every later cycle. There is no special-cased first pick.
        """
        if self._state in (State.IDLE, State.PAUSED):
            self._running   = True
            self._paused    = False
            self._auto_mode = True
            self._begin_next_auto_pick()

    def pause(self):
        if self._running and self._state not in (State.ALERT, State.COMPLETE):
            self._paused = True
            self._next_pick_timer.stop()
            self._set_state(State.PAUSED)

    def resume(self):
        if self._paused:
            self._paused = False
            self._begin_next_auto_pick()

    def stop(self):
        self._running              = False
        self._paused               = False
        self._auto_mode            = False
        self._weight_capture_armed = False
        self._weight_locked        = False
        self._scale_pick_retries   = 0
        self._vib_timer.stop()
        self._settle_timer.stop()
        self._next_pick_timer.stop()
        self._set_state(State.IDLE)

    def set_pick_target(self, rx: float, ry: float) -> None:
        if self._state not in (State.WAITING_CAMERA, State.IDLE, State.SCANNING):
            return
        self._current_diamond_xy   = (rx, ry)
        self._weight_capture_armed = False
        self._weight_locked        = False
        self._current_weight       = 0.0
        self._auto_mode = False if self._state in (State.WAITING_CAMERA, State.IDLE) else self._auto_mode
        self._running   = True
        self._set_state(State.PICKING)
        self.pick_requested.emit(rx, ry)

    def trigger_manual_vibrate(self):
        """Manual vibrate — works from IDLE, PAUSED, SCANNING, or WAITING_CAMERA."""
        if self._state in (State.IDLE, State.PAUSED):
            self._set_state(State.VIBRATING)
            self.vibrate_requested.emit()
            self._vib_timer.start(VIBRATION_DURATION)
        elif self._state == State.SCANNING:
            self._set_state(State.VIBRATING)
            self.vibrate_requested.emit()
            self._vib_timer.start(VIBRATION_DURATION)
        elif self._state == State.WAITING_CAMERA:
            self._set_state(State.VIBRATING)
            self.vibrate_requested.emit()
            self._vib_timer.start(VIBRATION_DURATION)

    def trigger_alert_clear(self):
        """Called when operator resolves an alert."""
        if self._state == State.ALERT:
            if self._auto_mode:
                self._begin_next_auto_pick()
            else:
                self._running = False
                self._set_state(State.IDLE)

    def trigger_pick_and_place(self):
        """
        Manual Pick & Place:
        1. Robot moves to tray center (travel height)
        2. Camera dialog opens — operator clicks diamond
        3. set_pick_target() called with exact XY
        4. Robot picks that diamond
        """
        if self._state != State.IDLE:
            return
        self._running   = True
        self._auto_mode = False
        self._set_state(State.WAITING_CAMERA)
        self.pick_requested.emit(0.0, 0.0)   # moves robot to tray center, travel height only

    def trigger_slot_selected(self, slot_index: int):
        """Called when operator manually selects a slot (manual mode or alert)."""
        if self._state != State.WAITING_SLOT:
            return
        if self._current_weight <= 0:
            self.alert_raised.emit(
                "No valid weight reading — place diamond on scale first."
            )
            return
        self._pending_slot = slot_index
        self._set_state(State.SORTING)
        self.sort_requested.emit(slot_index)

    def trigger_manual_weight_and_slot(self, weight_ct: float, slot_index: int):
        """
        Called from alert dialog when operator manually enters weight
        and selects slot. Used when no slot matches the measured weight.
        """
        if self._state != State.ALERT:
            return
        self._current_weight = weight_ct
        self._pending_slot   = slot_index
        self._set_state(State.SORTING)
        self.sort_requested.emit(slot_index)

    # ── HARDWARE CALLBACKS ────────────────────────────────────────────────────

    def on_diamonds_detected(self, diamonds: list):
        """
        Retained for Manual mode compatibility (camera_Detector.py path).
        The continuous Auto loop no longer uses this — it goes through
        _begin_next_auto_pick() / DiamondSelector instead.
        """
        if not self._running or self._paused:
            return
        if self._state != State.SCANNING:
            return
        if not diamonds:
            # No diamonds found — scan again after short delay
            QTimer.singleShot(500, self.scan_requested.emit)
            return
        has_cluster = any(d[2] for d in diamonds)
        if has_cluster:
            self._set_state(State.VIBRATING)
            self.vibrate_requested.emit()
            self._vib_timer.start(VIBRATION_DURATION)
            return
        # Reset weight flags for new cycle
        self._weight_capture_armed = False
        self._weight_locked        = False
        self._current_weight       = 0.0
        # Take first isolated diamond
        x, y, _ = diamonds[0]
        self._current_diamond_xy = (x, y)
        self._set_state(State.PICKING)
        self.pick_requested.emit(x, y)

    def on_pick_complete(self):
        if self._state != State.PICKING:
            return
        self._set_state(State.WEIGHING)
        self.weigh_requested.emit()

    def on_tray_pick_confirmed(self, success: bool):
        """
        Called by main_window after tray pick lift, with pressure result.
        success=True  → diamond held → proceed to scale
        success=False → diamond not held → go home → rescan
        """
        if self._state != State.PICKING:
            return
        if success:
            self._set_state(State.WEIGHING)
            self.weigh_requested.emit()
        else:
            print("[Workflow] Tray pick FAILED — releasing pump then going home to rescan")
            self.pick_failed.emit()
            self.tray_pick_failed.emit()

    def on_scale_pick_confirmed(self, success: bool, weak: bool = False):
        """
        Called by main_window after scale pick lift, with pressure result.
        success=True  → diamond held → proceed to slot (weight already locked)
        weak=True     → partial pick (4M–7M) → retry pick directly, no re-weigh
        success=False → not picked at all (<4M) → fail after 3 attempts
        """
        if self._state != State.WEIGHING:
            return
        if success:
            self._scale_pick_retries = 0
            # Weight is already locked from first weigh cycle — go straight to slot
            self.disarm_weight_capture()
            if self._auto_mode:
                self._auto_find_slot()
            else:
                self._set_state(State.WAITING_SLOT)
        else:
            self._scale_pick_retries += 1
            print(f"[Workflow] Scale pick FAILED — attempt {self._scale_pick_retries}/3 weak={weak}")
            if self._scale_pick_retries >= 3:
                self._scale_pick_retries = 0
                self._set_state(State.ALERT)
                self.scale_pick_failed.emit()
                self.alert_raised.emit(
                    "Scale pick failed 3 times.\n"
                    "Please check diamond position on scale manually."
                )
            else:
                # Retry pick directly — weight already locked, no re-weigh needed
                self.scale_retry_pick.emit()

    def on_scale_reading(self, weight_ct: float):
        """
        Called on every scale emission. Only accepted when armed and not yet locked.
        Once a valid non-zero reading arrives while armed, it is locked in and all
        further readings are ignored until arm_weight_capture() is called again
        at the start of the next weigh cycle.
        """
        if not self._weight_capture_armed:
            return
        if self._weight_locked:
            return
        value = weight_ct if weight_ct >= MIN_DIAMOND_CT else 0.0
        if value > 0.0:
            self._current_weight = value
            self._weight_locked  = True
            print(f"[Workflow] Weight LOCKED: {value:.4f} ct")

    def on_sort_complete(self):
        if self._state != State.SORTING:
            return

        # Record the completed diamond
        slot_idx = self._pending_slot
        x, y     = self._current_diamond_xy
        rec      = self.session.add_record(slot_idx, self._current_weight, x, y)
        self.slot_manager.record_diamond(slot_idx, rec.diamond_id)
        self.cycle_complete.emit(rec)

        # The diamond that was just sorted is now physically in a slot —
        # safe to stop excluding its tray position in the selector.
        if self._diamond_selector is not None:
            self._diamond_selector.clear_in_progress()

        # Reset per-cycle state
        self._current_weight       = 0.0
        self._current_diamond_xy   = (0.0, 0.0)
        self._weight_capture_armed = False
        self._weight_locked        = False
        self._scale_pick_retries   = 0

        if self._auto_mode and self._running:
            # Small delay after homing — gives DiamondSelector time to
            # lift its _is_homing gate and lock a fresh diamond position
            # from the camera before we ask is_ready().
            self._set_state(State.SCANNING)
            QTimer.singleShot(500, self._begin_next_auto_pick)
        else:
            # Manual mode or stopped — go to IDLE
            self._running   = False
            self._auto_mode = False
            self._set_state(State.IDLE)

    def on_home_complete(self):
        """
        Still used for manual "go home" actions elsewhere in the app
        (e.g. STOP / emergency flows that explicitly request HOMING).
        No longer reached automatically between auto-loop cycles.
        """
        if self._state != State.HOMING:
            return
        if self._auto_mode and self._running:
            # Small delay after homing — gives DiamondSelector time to
            # lift its _is_homing gate and lock a fresh diamond position
            # from the camera before we ask is_ready().
            self._set_state(State.SCANNING)
            QTimer.singleShot(500, self._begin_next_auto_pick)
        else:
            # Manual mode or stopped — go to IDLE
            self._running   = False
            self._auto_mode = False
            self._set_state(State.IDLE)

    # ── CONTINUOUS AUTO LOOP ───────────────────────────────────────────────────

    def _begin_next_auto_pick(self):
        """
        Core of the continuous loop. Used for the very first pick of a
        session and for every subsequent pick after a sort completes —
        identical mechanism both times, no special-casing.

        If DiamondSelector already has a diamond ready (the normal case,
        since it runs continuously in the background while the robot is
        busy), we go straight to PICKING. If not yet ready, we keep the
        state as-is and poll every NEXT_PICK_POLL_MS until it is — no
        visible "waiting" state is shown, consistent with the requirement
        that the robot never idles at home/scale between diamonds.
        """
        if self._diamond_selector is None:
            # No selector wired in — nothing to do. Caller (main_window)
            # is responsible for wiring this before auto mode is usable.
            return

        self._next_pick_timer.stop()

        if self._diamond_selector.is_ready():
            self._dispatch_next_pick()
        else:
            self._next_pick_timer.start(NEXT_PICK_POLL_MS)

    def _poll_next_pick_ready(self):
        if not self._running or not self._auto_mode or self._paused:
            self._next_pick_timer.stop()
            return
        if self._diamond_selector is not None and self._diamond_selector.is_ready():
            self._next_pick_timer.stop()
            self._dispatch_next_pick()

    def _dispatch_next_pick(self):
        xy = self._diamond_selector.consume_next()
        if xy is None:
            # Lost readiness between the check and the consume (race) —
            # fall back to polling again immediately.
            self._next_pick_timer.start(NEXT_PICK_POLL_MS)
            return
        rx, ry = xy
        self._current_diamond_xy   = (rx, ry)
        self._weight_capture_armed = False
        self._weight_locked        = False
        self._current_weight       = 0.0
        self._set_state(State.PICKING)
        self.pick_requested.emit(rx, ry)

    # ── INTERNAL TIMERS ───────────────────────────────────────────────────────

    def _after_vibration(self):
        """After vibration timer — return to correct state based on mode."""
        if self._auto_mode and self._running:
            self._begin_next_auto_pick()
        elif self._running and not self._auto_mode:
            self._set_state(State.WAITING_CAMERA)
        else:
            self._running = False
            self._set_state(State.IDLE)

    def _read_scale_settled(self):
        """
        No longer used — weight capture and slot dispatch now happen
        directly in on_scale_pick_confirmed() after pressure check.
        Kept to avoid AttributeError from _settle_timer connection.
        """
        pass

    def _auto_find_slot(self):
        """Auto mode: find matching slot by weight and sort immediately."""
        weight   = self._current_weight
        slot_idx = self.slot_manager.find_slot_for_weight(weight)

        if slot_idx is None:
            self._set_state(State.ALERT)
            self.alert_raised.emit(
                f"No slot configured for {weight:.4f} ct\n"
                f"Please enter weight manually and select a slot."
            )
            return

        self._pending_slot = slot_idx
        self._set_state(State.SORTING)
        self.sort_requested.emit(slot_idx)