"""
diamond_selector.py
====================
Continuous background diamond selector for Luminax Sorter Auto mode.

Replaces auto_scanner.py's per-cycle open/scan/close/highlight/close flow.

Lifecycle:
    Auto START  → open_session()  → TrayDetectorDialog opens ONCE, minimized,
                                     camera thread starts and keeps running
    Auto STOP   → close_session() → dialog fully closed

While the session is open, this class watches every camera frame
(live.cam.stats_ready) continuously — regardless of what the robot is
doing (idle, picking, weighing, sorting). It always tries to keep one
"next diamond" ready to go:

    2+ isolated diamonds (excluding the one currently being picked)
        → lock the first one as the next pick target, no vibration
    exactly 1 isolated diamond AND no cluster present anywhere on the
    tray (the genuine last-diamond case)
        → lock that one as the next pick target, no vibration — there
          is nothing left to separate, so vibrating would only risk
          throwing the last diamond into a bad position for no reason
    0 isolated diamonds, OR exactly 1 isolated diamond WITH a cluster
    still present
        → CRITICAL: immediately invalidate/drop any previously-locked
          next-pick coordinates (the tray is about to physically move),
          then trigger esp32.vibrate() once and wait. A fresh frame
          after vibration finishes re-evaluates from scratch.

DEBOUNCING (prevents spurious/random vibration):
Camera frames during robot motion can be transiently noisy — the
gripper/arm passing through frame, motion blur, or partial occlusion
can cause the detector to briefly misclassify a perfectly good isolated
diamond as part of a "cluster" for a single frame, even though nothing
has actually moved on the tray. Reacting to every single frame
individually caused random/spurious vibration triggers.

To fix this, every classification (cluster-needs-vibration vs.
ready-with-N-isolated) must be seen on CONSECUTIVE_FRAMES_REQUIRED (3)
consecutive frames in a row before it's acted on. A single noisy frame
that disagrees with the streak resets the counter — it does not
immediately flip behaviour. This adds a small ~100ms confirmation
delay (at ~30fps) but eliminates false triggers from transient
misdetection.

PICKING-STATE VIBRATION GATE:
Vibration must never happen while the robot is actively in
State.PICKING (moving to grab the current diamond from the tray) —
vibrating the tray mid-grab risks disturbing the pick. Vibration is
allowed at any OTHER workflow state (WEIGHING, SORTING, IDLE, etc.).
This is tracked by connecting to workflow.state_changed directly (via
set_workflow()) rather than requiring main_window.py to push state in
explicitly. If a confirmed "vibrate" classification arrives while
PICKING is active, it is simply not acted on that frame — no signal
fires, nothing is invalidated — and the same confirmed classification
is naturally re-evaluated on the next frame once PICKING ends.

This invalidate-on-vibrate step is what fixes the original "stale
coordinate" bug: without it, a diamond's coordinates could be locked in
one frame, then the tray gets vibrated for a *different* reason (e.g.
while the robot was still busy with the previous diamond), silently
moving the already-locked diamond to a new position — so the robot
would later drive to the stale, pre-vibration coordinates and find
nothing there.

The diamond currently being picked/weighed/sorted is excluded by
position (treated like a cluster member) so it can never be
re-selected while it is still physically on the tray / in the gripper.

Public API used by main_window.py / workflow.py:
    open_session()
    close_session()
    is_ready() -> bool
    consume_next() -> (rx, ry) | None   # marks that diamond as "in progress"
    clear_in_progress()                  # called from on_sort_complete
    ready_changed   (signal, bool)       # fires True the instant a pick is ready
    vibrate_needed  (signal)             # connect to esp32.vibrate
"""
from __future__ import annotations
import math
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

EXCLUDE_RADIUS_MM   = 10.0   # treat anything within this of the in-progress
                              # diamond as unpickable, same idea as cluster_dist
VIBRATE_RESUME_MS   = 1500   # how long to wait after triggering vibration
                              # before resuming frame reads (matches
                              # VIBRATION_DURATION used elsewhere in the app)

CONSECUTIVE_FRAMES_REQUIRED = 5   # a classification must repeat this many
                                   # frames in a row before being acted on —
                                   # filters out single-frame noise caused by
                                   # robot motion/occlusion in camera view


class DiamondSelector(QObject):
    ready_changed  = pyqtSignal(bool)
    vibrate_needed = pyqtSignal()
    scan_failed    = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dialog       = None
        self._robot        = None
        self._workflow     = None

        self._session_open = False
        self._vibrating     = False
        self._is_picking    = False   # True only while workflow.state == State.PICKING
        self._is_homing     = False   # True while robot is homing after a failed pick

        self._next_xy       = None    # (rx, ry) of the currently-locked next pick
        self._next_ready     = False

        self._excluded_xy    = None   # diamond currently being picked/weighed/sorted

        # ── Debounce state ──────────────────────────────────────────────────
        # Tracks the last classification seen and how many consecutive
        # frames have agreed with it. Classification is one of:
        #   ("ready", (rx, ry))   — N+ isolated diamonds, candidate pick rx,ry
        #   ("vibrate", None)     — cluster present, needs vibration
        #   ("empty", None)       — nothing pickable, no cluster either
        self._pending_classification = None
        self._pending_streak         = 0

        self._vib_resume_timer = QTimer(self)
        self._vib_resume_timer.setSingleShot(True)
        self._vib_resume_timer.timeout.connect(self._on_vibrate_resume)

    # ── PUBLIC API ────────────────────────────────────────────────────────────

    def set_robot(self, robot):
        self._robot = robot

    def set_workflow(self, workflow):
        """
        Injects the main app's Workflow instance. Also connects to its
        state_changed signal so this selector can track whether the
        robot is currently in State.PICKING — vibration is suppressed
        entirely while that's true (see _on_workflow_state_changed).
        """
        self._workflow = workflow
        try:
            workflow.state_changed.connect(self._on_workflow_state_changed)
        except Exception:
            pass
        # Pick up the current state immediately in case PICKING is
        # already active at the moment this is wired in.
        try:
            from core.workflow import State
            self._is_picking = (workflow.state == State.PICKING)
        except Exception:
            pass

    def _on_workflow_state_changed(self, state):
        try:
            from core.workflow import State
        except Exception:
            return
        self._is_picking = (state == State.PICKING)
        self._is_homing  = (state == State.HOMING)
        # When homing completes and state moves to PICKING (next auto pick
        # dispatched), make absolutely sure homing gate is cleared so
        # the camera can lock the new diamond immediately.
        if state not in (State.HOMING, State.PICKING):
            self._is_homing = False

    def is_session_open(self) -> bool:
        return self._session_open

    def is_ready(self) -> bool:
        return self._next_ready and self._next_xy is not None

    def consume_next(self):
        """
        Called by main_window/workflow when the robot is about to start
        picking the currently-ready diamond. Returns its (rx, ry) and
        marks it as the excluded/in-progress diamond so the selector
        will not re-select it while it's still on the tray.
        """
        if not self.is_ready():
            return None
        xy = self._next_xy
        self._excluded_xy = xy
        self._next_xy      = None
        self._next_ready    = False
        self.ready_changed.emit(False)
        return xy

    def clear_in_progress(self):
        """
        Called from on_sort_complete() — the diamond that was being
        tracked is now physically in a slot, not on the tray. Safe to
        stop excluding that position.
        """
        self._excluded_xy = None

    def open_session(self):
        """Called once when Auto START is pressed. Opens the dialog
        minimized and starts continuous background selection."""
        if self._session_open:
            return
        self._session_open = True
        self._next_xy    = None
        self._next_ready  = False
        self._excluded_xy = None
        self._vibrating   = False
        self._pending_classification = None
        self._pending_streak         = 0
        self._open_dialog()

    def close_session(self):
        """Called on STOP — fully closes the dialog and resets state."""
        self._session_open = False
        self._vib_resume_timer.stop()
        self._vibrating  = False
        self._next_xy    = None
        self._next_ready  = False
        self._excluded_xy = None
        self._pending_classification = None
        self._pending_streak         = 0
        self._close_dialog()

    def restore_window(self):
        """Operator wants to see the live feed — un-minimize it."""
        if self._dialog is not None:
            self._dialog.showNormal()

    # ── DIALOG MANAGEMENT ─────────────────────────────────────────────────────

    def _open_dialog(self):
        from tray_detector_dialog import TrayDetectorDialog
        self._dialog = TrayDetectorDialog(parent=None)
        self._dialog.setWindowTitle("AUTO SCAN — Tray Diamond Detector")

        if self._robot:
            self._dialog.set_robot(self._robot)
        if self._workflow:
            self._dialog.set_workflow(self._workflow)

        live = self._dialog.live_tab

        # Auto mode: operator does not click diamonds manually, and the
        # dialog's own motor-serial SCAN/VIBRATE state machine must be
        # disabled — vibration goes through ESP32 instead (see
        # suppress_internal_statemachine on LiveTab).
        live._try_pick_at = lambda fx, fy: None
        live.suppress_internal_statemachine(True)

        live.cam.stats_ready.connect(self._on_stats_ready)
        self._dialog.closed.connect(self._on_dialog_closed)

        self._dialog.showMinimized()
        print("[DiamondSelector] Session dialog opened (minimized) — scanning…")

    def _close_dialog(self):
        if self._dialog is not None:
            try:
                live = self._dialog.live_tab
                live.cam.stats_ready.disconnect(self._on_stats_ready)
            except Exception:
                pass
            try:
                self._dialog.cam_thread.stop()
                self._dialog.close()
            except Exception:
                pass
            self._dialog = None
        print("[DiamondSelector] Session dialog closed")

    def _on_dialog_closed(self):
        # Dialog was closed some other way (e.g. window manager) —
        # treat exactly like a STOP so the session state stays consistent.
        self._dialog = None
        if self._session_open:
            self.close_session()

    # ── DETECTION LOGIC ───────────────────────────────────────────────────────

    def _on_stats_ready(self, diamonds: list):
        if not self._session_open:
            return

        if self._vibrating or self._is_homing:
            # During vibration or homing after failed pick — tray/robot
            # is in motion, any coordinates would be unreliable.
            # Reset debounce streak so no stale classification carries over.
            self._pending_classification = None
            self._pending_streak         = 0
            return

        isolated    = [d for d in diamonds if not d.is_cluster]
        isolated    = self._filter_excluded(isolated)
        has_cluster = any(d.is_cluster for d in diamonds)

        # ── Classify this single frame ────────────────────────────────────
        if len(isolated) >= 2:
            classification = ("ready", (isolated[0].robot_x, isolated[0].robot_y))
        elif len(isolated) == 1 and not has_cluster:
            # Genuine last-diamond case — exactly one diamond on the
            # whole tray, nothing left to separate. Never vibrate for
            # this, regardless of workflow state.
            classification = ("ready", (isolated[0].robot_x, isolated[0].robot_y))
        elif has_cluster:
            classification = ("vibrate", None)
        else:
            classification = ("empty", None)

        # ── Debounce: require CONSECUTIVE_FRAMES_REQUIRED frames in a row
        # with the SAME kind of classification before acting. A single
        # noisy frame (motion blur, gripper occlusion) that disagrees
        # does not immediately change behaviour — it just doesn't extend
        # the streak. This is what prevents transient misdetection
        # during robot motion from triggering spurious vibration. ─────────
        same_kind = (
            self._pending_classification is not None
            and self._pending_classification[0] == classification[0]
        )
        if same_kind:
            self._pending_streak += 1
        else:
            self._pending_classification = classification
            self._pending_streak         = 1

        if self._pending_streak < CONSECUTIVE_FRAMES_REQUIRED:
            return   # not confirmed yet — wait for more matching frames

        kind, payload = classification

        if kind == "ready":
            if not self._next_ready:
                self._next_xy    = payload
                self._next_ready  = True
                self.ready_changed.emit(True)
                print(f"[DiamondSelector] Next pick ready (confirmed over "
                      f"{CONSECUTIVE_FRAMES_REQUIRED} frames) → "
                      f"({payload[0]:.1f}, {payload[1]:.1f}) mm")
            return

        if kind == "vibrate":
            # PICKING GATE: never vibrate while the robot is actively
            # moving to grab the current diamond — vibrating the tray
            # mid-grab risks disturbing the pick. Simply don't act on
            # this confirmed classification yet; it gets re-evaluated
            # fresh on the next frame, and will fire normally the
            # instant PICKING ends (state changes to WEIGHING etc.).
            # Nothing is invalidated here since vibration isn't actually
            # happening — the tray hasn't moved.
            if self._is_picking:
                return

            # CRITICAL FIX (stale coordinate bug): whatever was previously
            # locked as "next pick" is about to become stale the instant
            # the tray vibrates, even if that lock happened in an earlier
            # frame while the robot was still busy with the previous
            # diamond. Drop it immediately so the workflow can never
            # consume coordinates that are about to move.
            if self._next_ready:
                print("[DiamondSelector] Invalidating previously-locked pick — "
                      "vibration about to move the tray")
                self._next_xy    = None
                self._next_ready  = False
                self.ready_changed.emit(False)

            print(f"[DiamondSelector] Cluster confirmed over "
                  f"{CONSECUTIVE_FRAMES_REQUIRED} consecutive frames — vibrating")
            self._vibrating = True
            self._pending_classification = None
            self._pending_streak         = 0
            self.vibrate_needed.emit()
            self._vib_resume_timer.start(VIBRATE_RESUME_MS)
            return

        # kind == "empty" — genuinely nothing pickable and no cluster.
        # Nothing to do, nothing to vibrate for.
        if self._next_ready:
            self._next_xy    = None
            self._next_ready  = False
            self.ready_changed.emit(False)

    def _filter_excluded(self, isolated: list) -> list:
        if self._excluded_xy is None:
            return isolated
        ex, ey = self._excluded_xy
        out = []
        for d in isolated:
            dist = math.hypot(d.robot_x - ex, d.robot_y - ey)
            if dist >= EXCLUDE_RADIUS_MM:
                out.append(d)
        return out

    def _on_vibrate_resume(self):
        self._vibrating = False
        
    def on_pick_failed(self):
        """
        Called when tray pick fails — the diamond was never picked,
        so stop excluding its position and invalidate any stale
        next-pick coordinates locked during the failed attempt.
        """
        self._excluded_xy = None
        self._next_xy     = None
        self._next_ready  = False
        self._pending_classification = None
        self._pending_streak         = 0
        self.ready_changed.emit(False)
        print("[DiamondSelector] Pick failed — excluded XY cleared, next pick invalidated")