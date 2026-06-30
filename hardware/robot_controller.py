from __future__ import annotations
import socket
import struct
import threading
import queue
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker

from config import (
    ROBOT_IP, JOINT_POLL_MS,
    Z_TRAY_PICK, Z_SAFE_TRAVEL, Z_SCALE_PLACE, Z_SCALE_PICK, Z_SLOT_DROP,
    Z_SCALE_CLEAR,
)

ROBOT_PORT    = 10003
MONITOR_PORT  = 12000
MONITOR_SPORT = 12001

C          = 0.0
FL1        = 0
FL2        = 0
SPEED_MM   = 20.0
SPEED_SLOW = 10.0
OVERRIDE   = 70

PICK_DOWN_OVRD = 5

# Dedicated, hardcoded override for scale-position movements only:
# place_on_scale, lift_clear_from_scale, lift_from_scale, pick_from_scale,
# move_xy_at_scale_pick_height.
# move_to_scale() is intentionally excluded — transit to scale uses the
# global OVERRIDE so it travels at the same speed as slot/home moves.
SCALE_OVRD = 1

FL1_RBF = 6
FL1_LBF = 7

TRAY_CORNERS = [
    (-67.19, 160.85),
    (-69.24, 365.20),
    ( 83.80, 364.71),
    ( 82.81, 160.00),
]

TRAY_X_MIN  = min(c[0] for c in TRAY_CORNERS)
TRAY_X_MAX  = max(c[0] for c in TRAY_CORNERS)
TRAY_Y_MIN  = min(c[1] for c in TRAY_CORNERS)
TRAY_Y_MAX  = max(c[1] for c in TRAY_CORNERS)
TRAY_WIDTH  = TRAY_X_MAX - TRAY_X_MIN
TRAY_HEIGHT = TRAY_Y_MAX - TRAY_Y_MIN

PICK_X = 14.483
PICK_Y = 266.042
PICK_C = 0.0

SCALE_X =  400.0
SCALE_Y =  0.0
SCALE_Z = Z_SCALE_PLACE

POSTURE_X =  400.0
POSTURE_Y =  0.0
POSTURE_Z =  144.5
POSTURE_C =  0.0

SLOT_POSITIONS = {
    "A1":  (-61.9064, -364.7666), "A2":  (-61.9064, -319.7666),
    "A3":  (-61.9064, -274.7666), "A4":  (-61.9064, -229.7666),
    "A5":  (-61.9064, -184.7666), "B1":  (-16.9064, -387.2666),
    "B2":  (-16.9064, -342.2666), "B3":  (-16.9064, -297.2666),
    "B4":  (-16.9064, -252.2666), "B5":  (-16.9064, -207.2666),
    "B6":  (-16.9064, -162.2666), "C1":  ( 28.0936, -364.7666),
    "C2":  ( 28.0936, -319.7666), "C3":  ( 28.0936, -274.7666),
    "C4":  ( 28.0936, -229.7666), "C5":  ( 28.0936, -184.7666),
    "D1":  ( 73.0936, -387.2666), "D2":  ( 73.0936, -342.2666),
    "D3":  ( 73.0936, -297.2666), "D4":  ( 73.0936, -252.2666),
    "D5":  ( 73.0936, -207.2666), "D6":  ( 73.0936, -162.2666),
    "E1":  (118.0259, -364.7666), "E2":  (118.0259, -319.7666),
    "E3":  (118.0259, -274.7666), "E4":  (118.0259, -229.7666),
    "E5":  (118.0259, -184.7666), "E6":  (118.0259, -139.7666),
    "F1":  (163.0959, -342.2666), "F2":  (163.0959, -297.2666),
    "F3":  (163.0959, -252.2666), "F4":  (163.0959, -207.2666),
    "F5":  (163.0959, -162.2666), "F6":  (163.0959,  152.7405),
    "F7":  (163.0959,  197.7405), "F8":  (163.0959,  242.7405),
    "F9":  (163.0959,  287.7405), "F10": (163.0959,  332.7405),
    "G1":  (208.0959, -319.7666), "G2":  (208.0959, -274.7666),
    "G3":  (208.0959, -229.7666), "G4":  (208.0959, -184.7666),
    "G5":  (208.0959, -139.7666), "G6":  (208.0959,  130.2405),
    "G7":  (208.0959,  175.2405), "G8":  (208.0959,  220.2405),
    "G9":  (208.0959,  265.2405), "G10": (208.0959,  310.2405),
    "H1":  (253.0959, -297.2666), "H2":  (253.0959, -252.2666),
    "H3":  (253.0959, -207.2666), "H4":  (253.0959, -162.2666),
    "H5":  (253.0959,  152.7405), "H6":  (253.0959,  197.7405),
    "H7":  (253.0959,  242.7405), "H8":  (253.0959,  287.7405),
    "I1":  (298.0913, -229.7666), "I2":  (298.0913, -184.7666),
    "I3":  (298.0913, -139.7666), "I4":  (298.0913,  175.2419),
    "I5":  (298.0913,  220.2419), "I6":  (298.0913,  265.2419),
    "J1":  (343.0913, -202.7222), "J2":  (343.0913, -162.2666),
    "J3":  (343.0913,  152.7405), "J4":  (343.0913,  197.7405),
}

SLOT_ORDER = [
    "A1","A2","A3","A4","A5",
    "B1","B2","B3","B4","B5","B6",
    "C1","C2","C3","C4","C5",
    "D1","D2","D3","D4","D5","D6",
    "E1","E2","E3","E4","E5","E6",
    "F1","F2","F3","F4","F5",
    "G1","G2","G3","G4","G5",
    "H1","H2","H3","H4",
    "I1","I2","I3",
    "J1","J2",
    "F6","F7","F8","F9","F10",
    "G6","G7","G8","G9","G10",
    "H5","H6","H7","H8",
    "I4","I5","I6",
    "J3","J4",
]

def _build_monitor_start() -> bytes:
    pkt = bytearray(196)
    struct.pack_into('<H', pkt,  0, 1)
    struct.pack_into('<H', pkt,  4, 7)
    struct.pack_into('<H', pkt, 64, 8)
    return bytes(pkt)

def _build_monitor_stop() -> bytes:
    pkt = bytearray(196)
    struct.pack_into('<H', pkt, 0, 255)
    return bytes(pkt)

class _UDPMonitor:
    def __init__(self):
        self._sock    = None
        self._running = False
        self._thread  = None
        self.latest   = {}

    def start(self):
        if self._running:
            return
        self._running = True
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("", MONITOR_SPORT))
        self._sock.settimeout(1.0)
        self._sock.sendto(_build_monitor_start(), (ROBOT_IP, MONITOR_PORT))
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.sendto(_build_monitor_stop(), (ROBOT_IP, MONITOR_PORT))
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None
        self.latest.clear()

    def _loop(self):
        while self._running:
            try:
                data, _ = self._sock.recvfrom(512)
                if len(data) < 196:
                    continue
                type1 = struct.unpack_from('<H', data, 4)[0]
                if type1 in (1, 7, 1001, 1007):
                    x, y, z, a, b, c, l1, l2 = struct.unpack_from('<8f', data, 8)
                    fl1, fl2 = struct.unpack_from('<2i', data, 40)
                    self.latest.update(X=x, Y=y, Z=z, C=c, FL1=fl1, FL2=fl2)
                type2 = struct.unpack_from('<H', data, 64)[0]
                if type2 in (2, 8, 1002, 1008):
                    joints = struct.unpack_from('<8f', data, 68)
                    self.latest['J1'] = round(joints[0] * 57.2958, 2)
                    self.latest['J2'] = round(joints[1] * 57.2958, 2)
                    self.latest['J3'] = round(self.latest.get('Z', 0.0), 2)
                    self.latest['J4'] = round(joints[3] * 57.2958, 2)
            except (socket.timeout, TimeoutError):
                pass
            except OSError:
                break
            except Exception:
                pass

class RobotController(QThread):
    """
    All blocking robot moves run inside this thread via a command queue.
    The UI thread only puts commands into the queue — it never blocks.
    """

    joints_updated = pyqtSignal(float, float, float, float)
    move_complete  = pyqtSignal()
    connected      = pyqtSignal(bool)
    error          = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running     = False
        self._sock        = None
        self._mutex       = QMutex()
        self._monitor     = _UDPMonitor()
        self.is_connected = False
        self._cmd_queue: queue.Queue = queue.Queue()
        self._last_tray_x = PICK_X
        self._last_tray_y = PICK_Y

    # ── PUBLIC API — safe to call from any thread ─────────────────────────────

    def servo_on(self):
        self._enqueue(lambda: self._send_cmd("SVON"))

    def servo_off(self):
        self._enqueue(lambda: self._send_cmd("SVOFF"))

    def reset_error(self):
        self._enqueue(lambda: self._send_cmd("RST"))

    def set_speed_override(self, percent: int):
        """Called by UI speed dropdown. Updates OVERRIDE for all travel moves."""
        global OVERRIDE
        OVERRIDE = max(10, min(100, percent))
        print(f"[Robot] Speed override → {OVERRIDE}%")

    def move_home(self):
        self._enqueue(lambda: self._move_xyz(
            POSTURE_X, POSTURE_Y, POSTURE_Z, c=POSTURE_C, fl1=FL1_RBF, spd=SPEED_MM, use_spd=False
        ))

    def move_to_tray_xy(self, x_mm: float = None, y_mm: float = None):
        if x_mm is None or (x_mm == 0.0 and y_mm == 0.0):
            rx, ry = PICK_X, PICK_Y
        elif x_mm > 200:
            rx, ry = self._pixel_to_robot(x_mm, y_mm, 1280, 960)
        else:
            rx, ry = x_mm, y_mm
        self._last_tray_x = rx
        self._last_tray_y = ry
        self._enqueue(lambda: self._move_xyz(rx, ry, Z_SAFE_TRAVEL, fl1=FL1_RBF, spd=SPEED_MM, use_spd=False))

    def move_to_tray_xy_at_pick_height(self, x_mm: float, y_mm: float):
        """
        Move XY only while staying at Z_TRAY_PICK (pick height).
        Used during circle sweep — robot is already at Z_TRAY_PICK,
        this just slides it to the next sweep point without changing Z.
        NOTE: Does NOT update _last_tray_x/y — those stay as the diamond centre.
        Forces FL1_RBF to guarantee consistent RBF posture at tray height.
        """
        self._enqueue(lambda: self._move_xyz(
            x_mm, y_mm, Z_TRAY_PICK, spd=SPEED_SLOW, fl1=FL1_RBF
        ))

    def pick_down(self, pressure_getter=None):
        """
        Pressure-guided descent onto tray.
        Descends in PICK_DESCEND_STEP_MM steps from current Z down to
        Z_TRAY_FLOOR. Stops immediately when pressure crosses
        PRESSURE_DIAMOND_THRESHOLD — diamond contacted.
        pressure_getter: callable that returns latest pressure int.
        """
        from config import (
            Z_TRAY_FLOOR, STAGED_DESCENT_STEPS,
            PRESSURE_DIAMOND_THRESHOLD,
        )
        x, y = self._last_tray_x, self._last_tray_y

        def _sequence():
            current_z = self._monitor.latest.get('Z', Z_TRAY_PICK)
            start_z   = current_z
            step_mm   = (start_z - Z_TRAY_FLOOR) / STAGED_DESCENT_STEPS

            for i in range(1, STAGED_DESCENT_STEPS + 1):
                z = max(start_z - step_mm * i, Z_TRAY_FLOOR)
                self._move_xyz_silent(
                    x, y, z,
                    fl1=FL1_RBF, spd=SPEED_SLOW,
                    ovrd=PICK_DOWN_OVRD
                )
                # Check pressure after each step
                if pressure_getter is not None:
                    pressure = pressure_getter()
                    if pressure > PRESSURE_DIAMOND_THRESHOLD:
                        print(f"[Robot] Diamond contacted at Z={z:.3f} pressure={pressure}")
                        break

            # Emit move_complete once — descent done
            self.move_complete.emit()

        self._enqueue(_sequence)
        
    def pick_up(self):
        x, y = self._last_tray_x, self._last_tray_y
        self._enqueue(lambda: self._move_xyz(
            x, y, Z_SAFE_TRAVEL, spd=SPEED_SLOW, fl1=FL1_RBF
        ))

    def move_to_scale(self):
        # Transit to scale at travel height — uses global OVERRIDE (same
        # speed as slot/home travel). Only the actual scale-position moves
        # below are locked at SCALE_OVRD=20.
        self._enqueue(lambda: self._move_xyz(
            SCALE_X, SCALE_Y, Z_SAFE_TRAVEL, fl1=FL1_RBF, spd=SPEED_MM, use_spd=False
        ))

    def place_on_scale(self):
        # Force RBF. Hardcoded SCALE_OVRD=20.
        self._enqueue(lambda: self._move_xyz(
            SCALE_X, SCALE_Y, Z_SCALE_PLACE, spd=SPEED_SLOW, fl1=FL1_RBF,
            ovrd=SCALE_OVRD
        ))

    def lift_clear_from_scale(self):
        """Lift nozzle clear of scale pan so scale reads free weight."""
        # Force RBF. Hardcoded SCALE_OVRD=20.
        self._enqueue(lambda: self._move_xyz(
            SCALE_X, SCALE_Y, Z_SCALE_CLEAR, spd=SPEED_SLOW, fl1=FL1_RBF,
            ovrd=SCALE_OVRD
        ))

    def lift_from_scale(self):
        # Hardcoded SCALE_OVRD=20.
        self._enqueue(lambda: self._move_xyz(
            SCALE_X, SCALE_Y, Z_SAFE_TRAVEL, fl1=FL1_RBF, spd=SPEED_SLOW,
            ovrd=SCALE_OVRD, use_spd=False
        ))

    def pick_from_scale(self, pressure_getter=None):
        """
        Pressure-guided descent onto scale to pick diamond.
        Descends in STAGED_DESCENT_STEPS steps from current Z down to
        Z_SCALE_FLOOR. The moment pressure crosses PRESSURE_WEAK_THRESHOLD,
        descent stops and robot immediately lifts to Z_SCALE_CLEAR —
        diamond never sits pressed hard against the scale surface.
        This prevents false scale readings and diamond damage.
        pressure_getter: callable that returns latest pressure int.
        """
        from config import (
            Z_SCALE_FLOOR, STAGED_DESCENT_STEPS,
            PRESSURE_WEAK_THRESHOLD,
        )

        def _sequence():
            current_z = self._monitor.latest.get('Z', Z_SCALE_CLEAR)
            start_z   = current_z
            step_mm   = (start_z - Z_SCALE_FLOOR) / STAGED_DESCENT_STEPS
            contacted = False

            for i in range(1, STAGED_DESCENT_STEPS + 1):
                z = max(start_z - step_mm * i, Z_SCALE_FLOOR)
                self._move_xyz_silent(
                    SCALE_X, SCALE_Y, z,
                    fl1=FL1_RBF, spd=SPEED_SLOW,
                    ovrd=SCALE_OVRD
                )
                if pressure_getter is not None:
                    pressure = pressure_getter()
                    if pressure >= PRESSURE_WEAK_THRESHOLD:
                        print(f"[Robot] Scale contact at Z={z:.3f} "
                            f"pressure={pressure} — lifting immediately")
                        contacted = True
                        break

            if not contacted:
                print("[Robot] Scale pick — no pressure contact detected at floor")

            # Immediately lift to Z_SCALE_CLEAR — diamond never presses
            # hard against scale surface regardless of contact result.
            self._move_xyz_silent(
                SCALE_X, SCALE_Y, Z_SCALE_CLEAR,
                fl1=FL1_RBF, spd=SPEED_SLOW,
                ovrd=SCALE_OVRD
            )

            # move_complete fires once — triggers _WEIGH_STEP_LIFT
            # pressure check in main_window.py
            self.move_complete.emit()

        self._enqueue(_sequence)

    def move_xy_at_scale_pick_height(self, x_mm: float, y_mm: float):
        """
        Move XY only while staying at Z_SCALE_PICK.
        Forces FL1_RBF. Hardcoded SCALE_OVRD=20.
        """
        self._enqueue(lambda: self._move_xyz(
            x_mm, y_mm, Z_SCALE_PICK, spd=SPEED_SLOW, fl1=FL1_RBF,
            ovrd=SCALE_OVRD
        ))

    @staticmethod
    def _fl1_for_slot(y: float) -> int:
        return FL1_LBF if y < 0.0 else FL1_RBF

    def move_home_for_slot_transition(self, slot_index: int):
        if slot_index < 0 or slot_index >= len(SLOT_ORDER):
            self.error.emit(f"Invalid slot index: {slot_index}")
            return
        label = SLOT_ORDER[slot_index]
        if label not in SLOT_POSITIONS:
            self.error.emit(f"No XYZ for slot {label}")
            return
        x, y = SLOT_POSITIONS[label]
        fl1 = self._fl1_for_slot(y)

        def _sequence():
            self._move_xyz_silent(
                POSTURE_X, POSTURE_Y, POSTURE_Z,
                fl1=FL1_RBF, spd=SPEED_MM, use_spd=False
            )
            self.msleep(500)
            self._move_xyz_silent(
                POSTURE_X, POSTURE_Y, POSTURE_Z,
                fl1=fl1, spd=SPEED_SLOW, use_spd=False
            )
            self.msleep(500)
            self._move_xyz(
                x, y, Z_SAFE_TRAVEL,
                fl1=fl1, spd=SPEED_MM, use_spd=False
            )

        self._enqueue(_sequence)

    def move_to_slot(self, slot_index: int):
        if slot_index < 0 or slot_index >= len(SLOT_ORDER):
            self.error.emit(f"Invalid slot index: {slot_index}")
            return
        label = SLOT_ORDER[slot_index]
        if label not in SLOT_POSITIONS:
            self.error.emit(f"No XYZ for slot {label}")
            return
        x, y = SLOT_POSITIONS[label]
        fl1 = self._fl1_for_slot(y)

        def _sequence():
            if y < 0.0:
                self._move_xyz_silent(
                    POSTURE_X, POSTURE_Y, POSTURE_Z, fl1=FL1_LBF, spd=SPEED_MM, use_spd=False
                )
            self._move_xyz(x, y, Z_SAFE_TRAVEL, fl1=fl1, spd=SPEED_MM, use_spd=False)

        self._enqueue(_sequence)

    def drop_in_slot(self, slot_index: int):
        if slot_index < 0 or slot_index >= len(SLOT_ORDER):
            return
        label = SLOT_ORDER[slot_index]
        x, y = SLOT_POSITIONS[label]
        fl1 = self._fl1_for_slot(y)
        self._enqueue(lambda: self._move_xyz(x, y, Z_SLOT_DROP, fl1=fl1, spd=SPEED_SLOW))

    def lift_from_slot(self, slot_index: int):
        if slot_index < 0 or slot_index >= len(SLOT_ORDER):
            return
        label = SLOT_ORDER[slot_index]
        x, y = SLOT_POSITIONS[label]
        fl1 = self._fl1_for_slot(y)

        def _sequence():
            self._move_xyz(x, y, Z_SAFE_TRAVEL, fl1=fl1, spd=SPEED_MM, use_spd=False)
            self._move_xyz_silent(
                POSTURE_X, POSTURE_Y, POSTURE_Z, fl1=FL1_RBF, spd=SPEED_MM, use_spd=False
            )

        self._enqueue(_sequence)

    def update_position(self, name: str, x: float, y: float, z: float):
        global SCALE_X, SCALE_Y, SCALE_Z
        global PICK_X, PICK_Y
        global POSTURE_X, POSTURE_Y, POSTURE_Z
        if name == "scale":
            SCALE_X = x; SCALE_Y = y; SCALE_Z = z
            print(f"[Robot] Scale → X:{x:.3f} Y:{y:.3f} Z:{z:.3f}")
        elif name == "tray":
            PICK_X = x; PICK_Y = y
            print(f"[Robot] Tray  → X:{x:.3f} Y:{y:.3f} Z:{z:.3f}")
        elif name == "home":
            POSTURE_X = x; POSTURE_Y = y; POSTURE_Z = z
            print(f"[Robot] Home  → X:{x:.3f} Y:{y:.3f} Z:{z:.3f}")

    # ── THREAD ────────────────────────────────────────────────────────────────

    def run(self):
        self._running = True
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect((ROBOT_IP, ROBOT_PORT))

            self._sock.settimeout(2.0)
            while True:
                try:
                    msg = self._sock.recv(1024).decode("ascii", errors="ignore").strip()
                    if not msg:
                        break
                    print(f"[Robot] Startup: {msg}")
                except (socket.timeout, TimeoutError):
                    break

            self._sock.settimeout(30.0)
            self.is_connected = True
            self.connected.emit(True)
            print(f"[Robot] Connected → {ROBOT_IP}:{ROBOT_PORT}")

            try:
                self._monitor.start()
                print(f"[Robot] UDP monitor started :{MONITOR_SPORT}")
            except Exception as e:
                print(f"[Robot] UDP monitor failed: {e}")

            import threading
            def _joint_poll_loop():
                import time
                while self._running:
                    lat = self._monitor.latest
                    if lat:
                        j1 = lat.get('J1', 0.0)
                        j2 = lat.get('J2', 0.0)
                        j3 = lat.get('Z',  0.0)
                        j4 = lat.get('J4', 0.0)
                        self.joints_updated.emit(j1, j2, j3, j4)
                    time.sleep(JOINT_POLL_MS / 1000.0)

            _poll_thread = threading.Thread(target=_joint_poll_loop, daemon=True)
            _poll_thread.start()

            while self._running:
                while not self._cmd_queue.empty():
                    try:
                        cmd = self._cmd_queue.get_nowait()
                        cmd()
                    except queue.Empty:
                        break
                    except Exception as e:
                        self.error.emit(f"Robot command error: {e}")
                self.msleep(10)

        except Exception as e:
            print(f"[Robot] Connection failed: {e}")
            self.is_connected = False
            self.connected.emit(False)
            while self._running:
                while not self._cmd_queue.empty():
                    try:
                        cmd = self._cmd_queue.get_nowait()
                        cmd()
                    except queue.Empty:
                        break
                    except Exception as e:
                        self.error.emit(f"[Sim] Command error: {e}")
                self.msleep(JOINT_POLL_MS)

        finally:
            self.is_connected = False
            self._monitor.stop()
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass

    def start(self):
        if not self.isRunning():
            super().start()

    def stop(self):
        self._running = False
        while not self._cmd_queue.empty():
            try:
                self._cmd_queue.get_nowait()
            except queue.Empty:
                break
        self._monitor.stop()
        self.wait(3000)

    # ── INTERNAL ──────────────────────────────────────────────────────────────

    def _enqueue(self, cmd):
        self._cmd_queue.put(cmd)

    def _pixel_to_robot(self, px: float, py: float,
                        frame_w: float = 1280, frame_h: float = 960):
        nx = px / frame_w
        ny = py / frame_h
        return (TRAY_X_MIN + nx * TRAY_WIDTH,
                TRAY_Y_MIN + ny * TRAY_HEIGHT)

    def _move_xyz(self, x, y, z, c=None, fl1=None, fl2=None,
            spd=SPEED_MM, ovrd=None, use_spd=True):
        """
        Blocking move — must only be called from inside the robot thread
        via the command queue. Never call directly from UI thread.

        ovrd defaults to None → resolves to module-level OVERRIDE at call
        time, so set_speed_override() changes take effect immediately.
        Scale position and tray pick methods pass an explicit ovrd
        (SCALE_OVRD=20, PICK_DOWN_OVRD=15) which always takes precedence
        over OVERRIDE and the RT ToolBox3 panel setting.
        move_to_scale() passes no ovrd → uses OVERRIDE like slot/home moves.
        """
        if not self._sock:
            self.msleep(600)
            self.move_complete.emit()
            return

        if ovrd is None:
            ovrd = OVERRIDE
        live = self._monitor.latest
        if fl1 is None:
            fl1 = live.get('FL1', 0)
        if fl2 is None:
            fl2 = live.get('FL2', 0)
        if c is None:
            c = live.get('C', 0.0)

        with QMutexLocker(self._mutex):
            try:
                self._raw_send("OVRD")
                self._raw_send(str(max(10, min(100, ovrd))))
                if use_spd:
                    self._raw_send("SPD")
                    self._raw_send(str(max(1.0, spd)))

                self._raw_send("MOV")
                self._raw_send(str(x))
                self._raw_send(str(y))
                self._raw_send(str(z))
                self._raw_send(str(c))
                self._raw_send(str(fl1))
                self._raw_send(str(fl2))

                self._sock.settimeout(10.0)
                raw = self._sock.recv(1024).decode("ascii", errors="ignore")
                parts = [
                    p.strip()
                    for p in raw.replace("\r", "\n").split("\n")
                    if p.strip()
                ]

                if not parts:
                    raise Exception("No response after MOV")
                if parts[0] == "ERR":
                    raise Exception("Robot ERR — check controller panel")
                if parts[0] != "OK":
                    raise Exception(f"Expected OK, got: {raw!r}")

                if len(parts) >= 2 and parts[1] == "DONE":
                    self.move_complete.emit()
                    return

                self._sock.settimeout(60.0)
                done_raw = self._sock.recv(1024).decode(
                    "ascii", errors="ignore"
                ).strip()

                if done_raw == "ERR":
                    raise Exception("Robot ERR during move")
                if done_raw != "DONE":
                    raise Exception(f"Expected DONE, got: {done_raw!r}")

                self.move_complete.emit()

            except Exception as e:
                self.error.emit(f"Robot move error: {e}")

    def _move_xyz_silent(self, x, y, z, c=None, fl1=None, fl2=None,
             spd=SPEED_MM, ovrd=None, use_spd=True):
        """
        Identical to _move_xyz but does NOT emit move_complete.
        Used for intermediate waypoint steps so the state machine only
        fires move_complete once — on the move that genuinely represents
        the sequencer's expected step.
        """
        if not self._sock:
            self.msleep(600)
            return

        if ovrd is None:
            ovrd = OVERRIDE
        live = self._monitor.latest
        if fl1 is None:
            fl1 = live.get('FL1', 0)
        if fl2 is None:
            fl2 = live.get('FL2', 0)
        if c is None:
            c = live.get('C', 0.0)

        with QMutexLocker(self._mutex):
            try:
                self._raw_send("OVRD")
                self._raw_send(str(max(10, min(100, ovrd))))
                if use_spd:
                    self._raw_send("SPD")
                    self._raw_send(str(max(1.0, spd)))

                self._raw_send("MOV")
                self._raw_send(str(x))
                self._raw_send(str(y))
                self._raw_send(str(z))
                self._raw_send(str(c))
                self._raw_send(str(fl1))
                self._raw_send(str(fl2))

                self._sock.settimeout(10.0)
                raw = self._sock.recv(1024).decode("ascii", errors="ignore")
                parts = [
                    p.strip()
                    for p in raw.replace("\r", "\n").split("\n")
                    if p.strip()
                ]

                if not parts:
                    raise Exception("No response after MOV")
                if parts[0] == "ERR":
                    raise Exception("Robot ERR — check controller panel")
                if parts[0] != "OK":
                    raise Exception(f"Expected OK, got: {raw!r}")

                if len(parts) >= 2 and parts[1] == "DONE":
                    return

                self._sock.settimeout(60.0)
                done_raw = self._sock.recv(1024).decode(
                    "ascii", errors="ignore"
                ).strip()

                if done_raw == "ERR":
                    raise Exception("Robot ERR during move")
                if done_raw != "DONE":
                    raise Exception(f"Expected DONE, got: {done_raw!r}")

                # intentionally no move_complete.emit()

            except Exception as e:
                self.error.emit(f"Robot move error: {e}")

    def _send_cmd(self, cmd: str) -> str:
        with QMutexLocker(self._mutex):
            if self._sock:
                try:
                    self._raw_send(cmd)
                    self._sock.settimeout(5.0)
                    resp = self._sock.recv(256).decode(
                        "ascii", errors="ignore"
                    ).strip()
                    print(f"[Robot] {cmd} → {resp}")
                    return resp
                except Exception as e:
                    self.error.emit(f"Robot cmd {cmd} error: {e}")
            return ""

    def _raw_send(self, text: str):
        self._sock.sendall((text + "\r\n").encode("ascii"))