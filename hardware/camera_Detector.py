from __future__ import annotations
import json
import math
import os
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt5.QtGui import QImage

try:
    import cv2
    HAS_CV = True
except ImportError:
    HAS_CV = False

from config import CAMERA_INDEX, CAMERA_POLL_MS, CLUSTER_DISTANCE_PX

# ── Calibration file (same as tray_camera_tester.py) ─────────────────────────
CALIB_FILE = "tray_calibration.json"


class CoordinateMapper:
    """
    Loads tray_calibration.json and converts pixel coords → robot mm.
    Identical logic to tray_camera_tester.py — kept in sync manually.
    """
    def __init__(self):
        self.H     = None
        self.H_inv = None
        self.corners_px    = []
        self.corners_robot = []
        self._load()

    def pixel_to_robot(self, px, py):
        if self.H is None or not HAS_CV:
            return None
        pt = np.float32([[[px, py]]])
        r  = cv2.perspectiveTransform(pt, self.H)
        return float(r[0][0][0]), float(r[0][0][1])

    def pixels_to_robot(self, points):
        if self.H is None or not points or not HAS_CV:
            return []
        pts = np.float32([[p] for p in points])
        r   = cv2.perspectiveTransform(pts, self.H)
        return [(float(v[0][0]), float(v[0][1])) for v in r]

    @property
    def is_calibrated(self):
        return self.H is not None

    def _load(self):
        if not os.path.exists(CALIB_FILE):
            print(f"[Camera] WARNING: {CALIB_FILE} not found — "
                  f"emitting raw pixel coords until calibration is done")
            return
        try:
            with open(CALIB_FILE) as f:
                d = json.load(f)
            self.H             = np.float32(d["H"])
            self.H_inv         = np.float32(d["H_inv"]) if d.get("H_inv") else None
            self.corners_px    = d.get("corners_px", [])
            self.corners_robot = d.get("corners_robot", [])
            print(f"[Camera] Calibration loaded from {CALIB_FILE} ✓")
        except Exception as e:
            print(f"[Camera] WARNING: Calibration load failed: {e} — "
                  f"emitting raw pixel coords")

# ── Diamond dataclass ─────────────────────────────────────────────────────────

class Diamond:
    def __init__(self, x: float, y: float, radius: float):
        self.x = x
        self.y = y
        self.radius = radius
        self.is_cluster = False

    def distance_to(self, other: "Diamond") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

# ── Main detector thread ──────────────────────────────────────────────────────

class CameraDetector(QThread):
    frame_ready    = pyqtSignal(QImage)
    diamonds_found = pyqtSignal(list)   # list of (robot_x, robot_y, is_cluster) in mm
                                        # falls back to pixel coords if not calibrated
    connected      = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._cap     = None
        self._mutex   = QMutex()
        self._detect  = False   # only detect when requested

        # Load calibration once on startup
        self._mapper = CoordinateMapper()
        self._warned_no_calib = False   # log warning only once per run

    # ── Public control methods ────────────────────────────────────────────────

    def start_detection(self):
        with QMutexLocker(self._mutex):
            self._detect = True

    def stop_detection(self):
        with QMutexLocker(self._mutex):
            self._detect = False

    # ── Thread entry point ────────────────────────────────────────────────────

    def run(self):
        self._running = True

        if not HAS_CV:
            self.connected.emit(False)
            self._running = False
            return

        self._cap = cv2.VideoCapture(CAMERA_INDEX)
        if not self._cap.isOpened():
            self.connected.emit(False)
            # Do NOT simulate — just stay idle, show black feed
            self._running = False
            return

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT,  960)
        self.connected.emit(True)

        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                self.msleep(CAMERA_POLL_MS)
                continue

            diamonds = self._detect_diamonds(frame)
            annotated = self._annotate(frame, diamonds)
            qimg = self._to_qimage(annotated)
            self.frame_ready.emit(qimg)

            with QMutexLocker(self._mutex):
                should_emit = self._detect

            if should_emit:
                coords = self._to_robot_coords(diamonds)
                self.diamonds_found.emit(coords)
                self._detect = False

            self.msleep(CAMERA_POLL_MS)

        if self._cap:
            self._cap.release()

    def stop(self):
        self._running = False
        self.wait(2000)

    # ── Coordinate conversion ─────────────────────────────────────────────────

    def _to_robot_coords(self, diamonds: list[Diamond]) -> list[tuple]:
        """
        Convert diamond pixel positions to robot mm using CoordinateMapper.
        If calibration not loaded, falls back to raw pixel coords (logged once).
        Returns list of (x, y, is_cluster).
        """
        if not self._mapper.is_calibrated:
            if not self._warned_no_calib:
                print("[Camera] WARNING: No calibration — emitting raw pixel coords. "
                      "Run tray_camera_tester.py to calibrate.")
                self._warned_no_calib = True
            return [(d.x, d.y, d.is_cluster) for d in diamonds]

        # Convert all at once (efficient batch call)
        pixel_points = [(d.x, d.y) for d in diamonds]
        robot_points = self._mapper.pixels_to_robot(pixel_points)

        if not robot_points:
            return [(d.x, d.y, d.is_cluster) for d in diamonds]

        return [(rx, ry, diamonds[i].is_cluster)
                for i, (rx, ry) in enumerate(robot_points)]

    # ── Detection ─────────────────────────────────────────────────────────────

    def _detect_diamonds(self, frame) -> list[Diamond]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (9, 9), 2)

        circles = cv2.HoughCircles(
            blur, cv2.HOUGH_GRADIENT, dp=1.2,
            minDist=20, param1=80, param2=35,
            minRadius=8, maxRadius=60
        )

        diamonds = []
        if circles is not None:
            for x, y, r in circles[0]:
                diamonds.append(Diamond(float(x), float(y), float(r)))

        # Mark clusters
        for i, a in enumerate(diamonds):
            for j, b in enumerate(diamonds):
                if i != j and a.distance_to(b) < CLUSTER_DISTANCE_PX:
                    a.is_cluster = True
                    b.is_cluster = True

        return diamonds

    # ── Annotation ────────────────────────────────────────────────────────────

    def _annotate(self, frame, diamonds: list[Diamond]):
        out = frame.copy()
        h, w = out.shape[:2]

        for d in diamonds:
            col = (40, 160, 240) if d.is_cluster else (84, 220, 61)
            cv2.circle(out, (int(d.x), int(d.y)), int(d.radius), col, 2)
            cx, cy, r = int(d.x), int(d.y), int(d.radius)
            cv2.line(out, (cx - r - 6, cy), (cx + r + 6, cy), col, 1)
            cv2.line(out, (cx, cy - r - 6), (cx, cy + r + 6), col, 1)
            if d.is_cluster:
                cv2.rectangle(out,
                    (cx - r - 4, cy - r - 4),
                    (cx + r + 4, cy + r + 4),
                    (40, 160, 240), 1)

            # Show converted mm coords if calibrated, else show pixels
            if self._mapper.is_calibrated:
                result = self._mapper.pixel_to_robot(d.x, d.y)
                if result:
                    rx, ry = result
                    label = f"({rx:.1f},{ry:.1f})mm"
                else:
                    label = f"px({cx},{cy})"
            else:
                label = f"px({cx},{cy})"

            cv2.putText(out, label,
                (cx + int(r) + 6, cy),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                (80, 220, 180), 1)

        # Calibration status overlay
        cal_str = "[calibrated]" if self._mapper.is_calibrated else "[NOT CALIBRATED]"
        cv2.putText(out, f"{len(diamonds)} detected  {cal_str}",
            (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 130, 80), 1)

        return out

    # ── QImage conversion ─────────────────────────────────────────────────────

    def _to_qimage(self, frame) -> QImage:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()

    # ── Simulation mode ───────────────────────────────────────────────────────

    def _simulate(self):
        """Generate synthetic camera frames with animated diamonds."""
        import math
        import random

        if not HAS_CV:
            print("[Camera] Running in minimal simulation mode (no OpenCV)")
            import time
            while self._running:
                with QMutexLocker(self._mutex):
                    should_emit = self._detect
                if should_emit:
                    # Even in minimal sim, attempt coordinate conversion
                    fake = [Diamond(320.0, 240.0, 18.0)]
                    coords = self._to_robot_coords(fake)
                    self.diamonds_found.emit(coords)
                    with QMutexLocker(self._mutex):
                        self._detect = False
                self.msleep(CAMERA_POLL_MS)
            return

        import cv2 as _cv2
        t = 0
        dias = [(320, 240, 18), (400, 280, 22), (260, 310, 16), (450, 200, 20)]
        print("[Camera] Running in simulation mode")

        while self._running:
            try:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                frame[:] = (6, 8, 6)
                for x in range(0, 640, 40):
                    _cv2.line(frame, (x, 0), (x, 480), (10, 14, 10), 1)
                for y in range(0, 480, 40):
                    _cv2.line(frame, (0, y), (640, y), (10, 14, 10), 1)
                _cv2.ellipse(frame, (320, 240), (200, 160), 0, 0, 360, (26, 36, 26), 2)

                all_dias = []
                for i, (bx, by, r) in enumerate(dias):
                    x = int(bx + math.sin(t * 0.03 + i) * 3)
                    y = int(by + math.cos(t * 0.04 + i) * 3)
                    d = Diamond(x, y, r)
                    all_dias.append(d)

                for i, a in enumerate(all_dias):
                    for j, b in enumerate(all_dias):
                        if i != j and a.distance_to(b) < CLUSTER_DISTANCE_PX:
                            a.is_cluster = True

                ann  = self._annotate(frame, all_dias)
                qimg = self._to_qimage(ann)
                self.frame_ready.emit(qimg)

                with QMutexLocker(self._mutex):
                    should_emit = self._detect

                if should_emit:
                    # Convert sim pixel coords → robot mm
                    coords = self._to_robot_coords(all_dias)
                    self.diamonds_found.emit(coords)
                    with QMutexLocker(self._mutex):
                        self._detect = False

                t += 1
                self.msleep(CAMERA_POLL_MS)

            except Exception as e:
                print(f"[Camera] Simulate error: {e}")
                self.msleep(100)