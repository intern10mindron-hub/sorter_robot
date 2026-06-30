"""
tray_camera_tester.py  — MANUAL ROI VERSION  (Premium UI v2)
Robot pick / connect logic removed. UI-only.
"""
import sys, os, json, time, math, copy
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QLabel, QPushButton, QSlider, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QStatusBar, QMessageBox, QFileDialog,
    QFrame, QScrollArea, QSizePolicy, QComboBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt5.QtGui import QImage, QPixmap, QColor, QFont

try:
    import cv2
    HAS_CV = True
except ImportError:
    HAS_CV = False
    print("WARNING: opencv-python not installed. Run: pip install opencv-python")

import socket
import threading

# ── Robot Config ────────────────────────────────────────
ROBOT_IP   = "192.168.0.20"
ROBOT_PORT = 10003
TIMEOUT    = 30.0
FL1 = 0
FL2 = 0
C   = -5.0

SPEED_MM   = 70.0
SPEED_SLOW = 20.0
OVERRIDE   = 70

Z_TRAVEL   = 144.5
Z_PICK     = 22.5
Z_PICK_UP  = 144.5

PICK_X  = 400.0
PICK_Y  = 0.0
PICK_C  = 0.0

# ═══════════════════════════════════════════════════════════════════════════════
# STYLESHEET  — Premium UI v2
# ═══════════════════════════════════════════════════════════════════════════════
QSS = """
/* ---------- base ---------- */
QWidget {
    background: #080c10;
    color: #c5cfd8;
    font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
    font-size: 14px;
    border: none;
}
QMainWindow { background: #050709; }

/* ---------- tabs ---------- */
QTabWidget::pane {
    border: none;
    background: #080c10;
    border-top: 1px solid #0e1a24;
}
QTabBar::tab {
    background: transparent;
    color: #4a6880;
    font-size: 13px;
    letter-spacing: 1px;
    padding: 10px 16px;
    border-bottom: 2px solid transparent;
    margin-right: 1px;
    min-width: 100px;
}
QTabBar::tab:selected {
    color: #00E5B0;
    border-bottom: 2px solid #00E5B0;
    background: rgba(0, 229, 176, 0.04);
}
QTabBar::tab:hover:!selected {
    color: #5a8fa8;
    background: rgba(0, 229, 176, 0.02);
}

/* ---------- buttons (base) ---------- */
QPushButton {
    background: rgba(14, 26, 36, 0.7);
    border: 1px solid #162230;
    border-radius: 5px;
    color: #8aabb8;
    font-size: 13px;
    letter-spacing: 2px;
    padding: 8px 18px;
}
QPushButton:hover {
    border-color: #2a4a62;
    color: #a8c8db;
    background: rgba(0, 229, 176, 0.05);
}
QPushButton:pressed {
    background: rgba(0, 229, 176, 0.1);
    border-color: #00E5B0;
}
QPushButton:disabled {
    color: #1e3040;
    border-color: #0e1a24;
}

/* ── accent variants ── */
QPushButton#btnGreen {
    border-color: rgba(0, 229, 176, 0.40);
    color: #00E5B0;
    background: rgba(0, 229, 176, 0.06);
}
QPushButton#btnGreen:hover  { background: rgba(0, 229, 176, 0.14); border-color: #00E5B0; }

QPushButton#btnBlue  {
    border-color: rgba(82, 160, 255, 0.40);
    color: #52a0ff;
    background: rgba(82, 160, 255, 0.05);
}
QPushButton#btnBlue:hover   { background: rgba(82, 160, 255, 0.12); border-color: #52a0ff; }

QPushButton#btnRed   {
    border-color: rgba(255, 82, 82, 0.40);
    color: #ff6b6b;
    background: rgba(255, 82, 82, 0.05);
}
QPushButton#btnRed:hover    { background: rgba(255, 82, 82, 0.12); border-color: #ff5252; }

QPushButton#btnAmber {
    border-color: rgba(255, 183, 77, 0.40);
    color: #ffb74d;
    background: rgba(255, 183, 77, 0.05);
}
QPushButton#btnAmber:hover  { background: rgba(255, 183, 77, 0.12); border-color: #ffb74d; }

/* ---------- sliders ---------- */
QSlider::groove:horizontal {
    background: #0e1a24;
    height: 3px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #00E5B0;
    width: 12px;
    height: 12px;
    border-radius: 6px;
    margin: -5px 0;
    border: 2px solid #080c10;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #005566, stop:1 #00E5B0);
    border-radius: 2px;
}
QSlider::handle:horizontal:hover { background: #40e0ff; }

/* ---------- group boxes ---------- */
QGroupBox {
    border: 1px solid #0e1a24;
    border-radius: 7px;
    margin-top: 14px;
    font-size: 11px;
    letter-spacing: 2px;
    color: #4a6a7e;
    padding: 4px;
    background: rgba(5, 10, 16, 0.5);
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    top: -1px;
    background: transparent;
    padding: 0 4px;
}

/* ---------- named labels ---------- */
QLabel#sectionLabel { font-size: 11px; letter-spacing: 2px; color: #4a6a7e; }
QLabel#value        { color: #00E5B0; }
QLabel#valueBlue    { color: #52a0ff; }
QLabel#valueAmber   { color: #ffb74d; }
QLabel#valueRed     { color: #ff6b6b; }

/* ---------- table ---------- */
QTableWidget {
    background: transparent;
    gridline-color: #0e1a24;
    alternate-background-color: #0b1218;
    font-size: 13px;
    color: #8aabb8;
    border: 1px solid #0e1a24;
    border-radius: 5px;
}
QTableWidget::item:selected { background: #0e1a24; color: #c5cfd8; }
QHeaderView::section {
    background: #0b1218;
    color: #4a6a7e;
    font-size: 11px;
    letter-spacing: 2px;
    border: none;
    border-bottom: 1px solid #0e1a24;
    padding: 5px 8px;
}

/* ---------- scrollbar ---------- */
QScrollBar:vertical   { background: transparent; width: 4px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 4px; margin: 0; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #162230;
    border-radius: 2px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { height: 0; width: 0; }

/* ---------- spinboxes ---------- */
QDoubleSpinBox, QSpinBox {
    background: #0b1218;
    border: 1px solid #162230;
    border-radius: 4px;
    color: #c5cfd8;
    padding: 4px 8px;
}
QDoubleSpinBox:focus, QSpinBox:focus { border-color: #00E5B0; background: #0e1a24; }

/* ---------- checkbox ---------- */
QCheckBox { spacing: 8px; color: #8aabb8; }
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #162230;
    border-radius: 3px;
    background: #0b1218;
}
QCheckBox::indicator:checked { background: #00E5B0; border-color: #00E5B0; }
QCheckBox::indicator:hover   { border-color: #2a6888; }

/* ---------- combobox ---------- */
QComboBox {
    background: #0b1218;
    border: 1px solid #162230;
    border-radius: 4px;
    color: #c5cfd8;
    padding: 4px 10px;
}
QComboBox:focus { border-color: #00E5B0; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #0b1218;
    border: 1px solid #162230;
    selection-background-color: #0e1a24;
    selection-color: #00E5B0;
    outline: none;
}

/* ---------- status bar ---------- */
QStatusBar {
    background: #050709;
    border-top: 1px solid #0e1a24;
    font-size: 13px;
    color: #4a6a7e;
    padding: 0 8px;
}

/* ---------- scroll area ---------- */
QScrollArea { border: none; background: transparent; }
"""

# ═══════════════════════════════════════════════════════════════════════════════
# COORDINATE MAPPER
# ═══════════════════════════════════════════════════════════════════════════════

CALIB_FILE = "tray_calibration.json"

class CoordinateMapper:
    def __init__(self):
        self.H     = None
        self.H_inv = None
        self.corners_px    = []
        self.corners_robot = []
        self._load()

    def set_corners(self, corners_px, corners_robot):
        if not HAS_CV or len(corners_px) != 4 or len(corners_robot) != 4:
            return False
        src = np.float32(corners_px)
        dst = np.float32(corners_robot)
        H, _ = cv2.findHomography(src, dst, method=0)
        if H is None:
            return False
        self.H, _ = H, None
        self.H_inv, _ = cv2.findHomography(dst, src, method=0)
        # Convert to plain Python float — numpy float32 is not JSON serializable
        self.corners_px    = [[float(v) for v in p] for p in corners_px]
        self.corners_robot = [[float(v) for v in p] for p in corners_robot]
        self._save()
        
        return True

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

    def robot_to_pixel(self, rx, ry):
        if self.H_inv is None or not HAS_CV:
            return None
        pt = np.float32([[[rx, ry]]])
        r  = cv2.perspectiveTransform(pt, self.H_inv)
        return float(r[0][0][0]), float(r[0][0][1])

    @property
    def is_calibrated(self):
        return self.H is not None

    def reprojection_error(self):
        if not self.is_calibrated:
            return float("inf")
        errs = []
        for pp, rp in zip(self.corners_px, self.corners_robot):
            m = self.pixel_to_robot(*pp)
            if m:
                errs.append(math.hypot(m[0]-rp[0], m[1]-rp[1]))
        return float(np.mean(errs)) if errs else float("inf")

    def _save(self):
        d = {
            "corners_px":    self.corners_px,
            "corners_robot": self.corners_robot,
            "H":             self.H.tolist(),
            "H_inv":         self.H_inv.tolist() if self.H_inv is not None else None,
            "saved":         time.strftime("%Y-%m-%d %H:%M:%S"),
            "error_mm":      round(self.reprojection_error(), 4),
        }
        with open(CALIB_FILE, "w") as f:
            json.dump(d, f, indent=2)

    def _load(self):
        if not os.path.exists(CALIB_FILE):
            return
        try:
            with open(CALIB_FILE) as f:
                d = json.load(f)
            self.H             = np.float32(d["H"])
            self.H_inv         = np.float32(d["H_inv"]) if d.get("H_inv") else None
            self.corners_px    = d.get("corners_px", [])
            self.corners_robot = d.get("corners_robot", [])
        except Exception as e:
            print(f"Calibration load failed: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# DETECTOR PARAMS
# ═══════════════════════════════════════════════════════════════════════════════

class DetectorParams:
    min_radius     = 2
    max_radius     = 37
    circularity    = 45
    cluster_dist   = 8
    blur           = 5
    rib_kernel_w   = 80
    rib_kernel_h   = 4
    threshold_mode = "otsu"
    threshold_val  = 160
    show_mask      = False
    show_rib_mask  = False
    edge_margin    = 0

PARAMS = DetectorParams()

# ═══════════════════════════════════════════════════════════════════════════════
# DIAMOND DATACLASS
# ═══════════════════════════════════════════════════════════════════════════════

class Diamond:
    def __init__(self, px, py, radius_px, circularity,
                 robot_x=0.0, robot_y=0.0, is_cluster=False):
        self.px          = px
        self.py          = py
        self.radius_px   = radius_px
        self.circularity = circularity
        self.robot_x     = robot_x
        self.robot_y     = robot_y
        self.is_cluster  = is_cluster

# ═══════════════════════════════════════════════════════════════════════════════
# DETECTOR CORE
# ═══════════════════════════════════════════════════════════════════════════════

def detect_diamonds(frame, mapper: CoordinateMapper, tray_poly=None):
    if not HAS_CV:
        return [], frame, frame

    H_f, W_f = frame.shape[:2]

    tray_mask = np.zeros((H_f, W_f), dtype=np.uint8)
    if tray_poly and len(tray_poly) >= 3:
        cv2.fillPoly(tray_mask, [np.array(tray_poly, dtype=np.int32)], 255)
    else:
        return [], frame, np.zeros((H_f, W_f), dtype=np.uint8)

    # Shrink the tray mask inward by edge_margin px so blobs sitting on/over
    # the ROI boundary line itself (false detections right on the green
    # outline) are excluded before thresholding/contour detection.
    if PARAMS.edge_margin > 0:
        erode_k = np.ones((PARAMS.edge_margin * 2 + 1, PARAMS.edge_margin * 2 + 1), np.uint8)
        tray_mask = cv2.erode(tray_mask, erode_k, iterations=1)

    gray     = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe    = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    if PARAMS.threshold_mode == "otsu":
        _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        _, thresh = cv2.threshold(enhanced, PARAMS.threshold_val, 255, cv2.THRESH_BINARY)

    thresh  = cv2.bitwise_and(thresh, thresh, mask=tray_mask)
    kernel  = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(thresh,  cv2.MORPH_OPEN,  kernel, iterations=1)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=1)
    debug_mask = cleaned.copy()

    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    singles  = []
    clusters = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        min_area = PARAMS.min_radius ** 2 * 2
        max_area = PARAMS.max_radius ** 2 * 8
        if not (min_area < area < max_area):
            continue

        hull      = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        solidity  = area / hull_area if hull_area > 0 else 1.0
        rect      = cv2.minAreaRect(cnt)
        box       = cv2.boxPoints(rect)
        box       = np.intp(box)
        cx, cy    = int(rect[0][0]), int(rect[0][1])
        w, h      = rect[1][0], rect[1][1]
        r         = max(w, h) / 2

        MAX_SINGLE = PARAMS.max_radius ** 2 * 2
        is_blob    = (area > MAX_SINGLE and solidity < 0.82)

        d = Diamond(float(cx), float(cy), float(r), float(solidity), is_cluster=is_blob)
        d._box = box

        if is_blob:
            clusters.append(d)
        else:
            singles.append(d)

    all_raw = singles + clusters
    if mapper.is_calibrated and all_raw:
        robot_pts = mapper.pixels_to_robot([(d.px, d.py) for d in all_raw])
        for d, (rx, ry) in zip(all_raw, robot_pts):
            d.robot_x = rx
            d.robot_y = ry

    if len(singles) > 1:
        for i, a in enumerate(singles):
            for j, b in enumerate(singles):
                if i >= j:
                    continue
                dv = (math.hypot(a.robot_x - b.robot_x, a.robot_y - b.robot_y)
                      if mapper.is_calibrated
                      else math.hypot(a.px - b.px, a.py - b.py))
                if dv < PARAMS.cluster_dist:
                    a.is_cluster = True
                    b.is_cluster = True

    isolated = [d for d in singles if not d.is_cluster]
    grouped  = [d for d in singles if d.is_cluster]
    all_d    = isolated + grouped + clusters

    out  = frame.copy()
    dark = (out * 0.3).astype(np.uint8)
    out  = np.where(tray_mask[:, :, np.newaxis] == 255, out, dark)

    if tray_poly and len(tray_poly) >= 3:
        cv2.polylines(out, [np.array(tray_poly, dtype=np.int32)], True, (0, 255, 0), 2)

    for d in clusters:
        cx, cy = int(d.px), int(d.py)
        box_s  = getattr(d, '_box', None)
        if box_s is not None:
            cv2.drawContours(out, [box_s], 0, (0, 0, 220), 2)
        est = max(2, int(d.radius_px * 2 / max(1, PARAMS.max_radius) * 5))
        cv2.putText(out, f"GROUP ~{est}", (cx-30, cy-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 60, 255), 1)

    for d in grouped:
        cx, cy = int(d.px), int(d.py)
        box_s  = getattr(d, '_box', None)
        if box_s is not None:
            cv2.drawContours(out, [box_s], 0, (0, 140, 255), 1)
        cv2.putText(out, "grp", (cx-10, cy-7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 140, 255), 1)

    for i, d in enumerate(isolated):
        cx, cy = int(d.px), int(d.py)
        box_s  = getattr(d, '_box', None)
        if box_s is not None:
            cv2.drawContours(out, [box_s], 0, (0, 255, 0), 2)
        cv2.circle(out, (cx, cy), 4, (0, 0, 255), -1)
        lbl = (f"D{i+1} ({d.robot_x:.1f},{d.robot_y:.1f})mm"
               if mapper.is_calibrated else f"D{i+1} px({cx},{cy})")
        cv2.putText(out, lbl, (cx+6, cy-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 180), 1)

    has_cluster = len(clusters) > 0 or len(grouped) > 0
    status_col  = (40, 160, 240) if has_cluster else (84, 220, 61)
    cal_str     = "[calibrated]" if mapper.is_calibrated else "[NOT CALIBRATED]"
    cv2.putText(out,
        f"{'CLUSTER' if has_cluster else 'OK'}  "
        f"Isolated:{len(isolated)} Grouped:{len(grouped)} "
        f"Clusters:{len(clusters)}  {cal_str}",
        (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_col, 1)

    return all_d, out, debug_mask

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO DETECT
# ═══════════════════════════════════════════════════════════════════════════════

def auto_detect_tray(frame):
    if not HAS_CV:
        return None
    H, W = frame.shape[:2]
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 0)
    _, dark = cv2.threshold(blurred, 75, 255, cv2.THRESH_BINARY_INV)
    kernel  = np.ones((7, 7), np.uint8)
    cleaned = cv2.morphologyEx(dark,    cv2.MORPH_CLOSE, kernel, iterations=3)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN,  kernel, iterations=2)
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < H * W * 0.08: continue
        if area > H * W * 0.88: continue
        rect = cv2.minAreaRect(cnt)
        (cx, cy), (w, h), angle = rect
        if w == 0 or h == 0: continue
        aspect = max(w, h) / min(w, h)
        if not (1.0 < aspect < 2.0): continue
        hull     = cv2.convexHull(cnt)
        solidity = area / max(1, cv2.contourArea(hull))
        if solidity < 0.85: continue
        if area > best_area:
            best_area = area
            box  = cv2.boxPoints(rect)
            box  = np.int32(box)
            best = box.tolist()
    return best

# ═══════════════════════════════════════════════════════════════════════════════
# CAMERA THREAD
# ═══════════════════════════════════════════════════════════════════════════════

class CameraThread(QThread):
    frame_ready = pyqtSignal(QImage, QImage)
    stats_ready = pyqtSignal(list)

    def __init__(self, mapper: CoordinateMapper):
        super().__init__()
        self.mapper     = mapper
        self._running   = False
        self._cam_index = 0
        self._tray_poly = None
        self._mutex     = QMutex()

    def set_camera(self, idx):
        with QMutexLocker(self._mutex):
            self._cam_index = idx

    def set_tray_poly(self, poly):
        with QMutexLocker(self._mutex):
            self._tray_poly = copy.deepcopy(poly) if poly else None

    def run(self):
        self._running = True

        if not HAS_CV:
            self._running = False
            return

        cap = None
        while self._running:
            # ── Try to open camera if not already open ────────────────────
            if cap is None or not cap.isOpened():
                with QMutexLocker(self._mutex):
                    idx = self._cam_index
                cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,  960)
                else:
                    # Camera not found — do NOT simulate, just wait
                    cap = None
                    self.msleep(500)
                    continue

            # ── Read real frame ───────────────────────────────────────────
            ret, frame = cap.read()
            if not ret:
                cap.release()
                cap = None
                continue

            with QMutexLocker(self._mutex):
                poly = copy.deepcopy(self._tray_poly)

            if not poly:
                detected = auto_detect_tray(frame)
                if detected:
                    poly = self._order_detected(detected, frame)

            diamonds, ann, dbg = detect_diamonds(frame, self.mapper, poly)
            self.frame_ready.emit(self._to_q(ann), self._to_q(dbg, gray=True))
            self.stats_ready.emit(diamonds)
            self.msleep(33)

        if cap:
            cap.release()

    def _order_detected(self, detected, frame):
        pts  = np.array(detected, dtype="float32")
        s    = pts.sum(axis=1)
        diff = np.diff(pts, axis=1).flatten()
        ordered = [
            pts[np.argmin(s)].tolist(),
            pts[np.argmin(diff)].tolist(),
            pts[np.argmax(s)].tolist(),
            pts[np.argmax(diff)].tolist(),
        ]
        
        with QMutexLocker(self._mutex):
            self._tray_poly = copy.deepcopy(ordered)
        return ordered

    def stop(self):
        self._running = False
        self.wait(2000)

    def _to_q(self, frame, gray=False):
        if gray:
            if len(frame.shape) == 2:
                h, w = frame.shape
                return QImage(frame.data, w, h, w, QImage.Format_Grayscale8).copy()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        return QImage(frame.data, w, h, ch * w, QImage.Format_RGB888).copy()

    _sim_t = 0
    def _sim_frame(self):
        self._sim_t += 1
        t = self._sim_t
        if not HAS_CV:
            return np.zeros((480, 640, 3), dtype=np.uint8)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (10, 12, 10)
        for y in range(30, 450, 35):
            cv2.line(frame, (60, y), (580, y), (200, 200, 200), 3)
        cv2.ellipse(frame, (320, 240), (260, 200), 0, 0, 360, (40, 50, 40), 2)
        for i, (bx, by, r) in enumerate([(200,180,20),(350,260,18),(480,310,22),(250,380,16)]):
            cx = int(bx + math.sin(t * 0.04 + i * 1.2) * 5)
            cy = int(by + math.cos(t * 0.05 + i * 0.9) * 5)
            cv2.circle(frame, (cx, cy), r, (240, 240, 240), -1)
            cv2.circle(frame, (cx, cy), r, (200, 200, 200),  1)
        return frame

# ═══════════════════════════════════════════════════════════════════════════════
# CAMERA VIEW WIDGET
# ═══════════════════════════════════════════════════════════════════════════════

class CameraView(QLabel):
    clicked     = pyqtSignal(float, float)
    mouse_moved = pyqtSignal(float, float)

    def __init__(self, placeholder="No signal"):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background:#04080c;border:1px solid #0e1a24;"
            "border-radius:6px;color:#4a6a7e;")
        self.setText(placeholder)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._scale  = 1.0
        self._offset = (0, 0)
        self._fw = 640
        self._fh = 480

        # ── Zoom & pan state ──────────────────────────────────────────
        self._zoom       = 1.0          # current zoom level
        self._zoom_min   = 1.0          # fully zoomed out = fit to widget
        self._zoom_max   = 8.0          # max 8× zoom
        self._pan_x      = 0.0          # pan offset in frame pixels
        self._pan_y      = 0.0
        self._panning    = False
        self._pan_start  = None         # QPoint where pan drag started
        self._last_qimg  = None         # last QImage received

    def set_frame(self, qimg: QImage):
        self._fw      = qimg.width()
        self._fh      = qimg.height()
        self._last_qimg = qimg
        self._repaint_zoom()

    def _repaint_zoom(self):
        if self._last_qimg is None:
            return
        lw = max(1, self.width()  - 2)
        lh = max(1, self.height() - 2)

        # Base scale — fit whole frame in widget
        base_sx = lw / max(1, self._fw)
        base_sy = lh / max(1, self._fh)
        base_s  = min(base_sx, base_sy)

        # Effective scale with zoom applied
        eff_s = base_s * self._zoom

        # Clamp pan so we never show black outside frame
        vis_w = lw / eff_s          # visible width in frame pixels
        vis_h = lh / eff_s          # visible height in frame pixels
        max_px = max(0.0, self._fw - vis_w)
        max_py = max(0.0, self._fh - vis_h)
        self._pan_x = max(0.0, min(self._pan_x, max_px))
        self._pan_y = max(0.0, min(self._pan_y, max_py))

        # Crop the source QImage to visible region
        src_x = int(self._pan_x)
        src_y = int(self._pan_y)
        src_w = min(self._fw - src_x, int(math.ceil(vis_w)))
        src_h = min(self._fh - src_y, int(math.ceil(vis_h)))
        src_w = max(1, src_w)
        src_h = max(1, src_h)

        cropped = self._last_qimg.copy(src_x, src_y, src_w, src_h)
        pix     = QPixmap.fromImage(cropped)
        scaled  = pix.scaled(lw, lh, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Store mapping for click→frame conversion
        self._scale  = src_w / max(1, scaled.width())
        self._offset = (
            (lw - scaled.width())  // 2,
            (lh - scaled.height()) // 2,
        )
        self._vis_src = (src_x, src_y, src_w, src_h)
        self.setPixmap(scaled)

    def _to_frame(self, e):
        """Convert widget mouse position to full-frame pixel coordinates."""
        lx = e.x() - self._offset[0]
        ly = e.y() - self._offset[1]
        if self._scale > 0 and hasattr(self, '_vis_src'):
            src_x, src_y, src_w, src_h = self._vis_src
            fx = src_x + lx * self._scale
            fy = src_y + ly * self._scale
            if 0 <= fx < self._fw and 0 <= fy < self._fh:
                return fx, fy
        return None, None

    def wheelEvent(self, e):
        """Scroll wheel — zoom in/out centred on mouse position."""
        if self._last_qimg is None:
            return

        # Mouse position in frame coords before zoom change
        before = self._to_frame(e)

        delta    = e.angleDelta().y()
        factor   = 1.15 if delta > 0 else (1.0 / 1.15)
        new_zoom = max(self._zoom_min, min(self._zoom_max, self._zoom * factor))

        if new_zoom == self._zoom:
            return

        self._zoom = new_zoom

        # After zoom, re-anchor so mouse stays over same frame pixel
        if before is not None:
            fx, fy   = before
            lw = max(1, self.width()  - 2)
            lh = max(1, self.height() - 2)
            base_sx  = lw / max(1, self._fw)
            base_sy  = lh / max(1, self._fh)
            base_s   = min(base_sx, base_sy)
            eff_s    = base_s * self._zoom
            vis_w    = lw / eff_s
            vis_h    = lh / eff_s
            lx = e.x() - self._offset[0]
            ly = e.y() - self._offset[1]
            self._pan_x = fx - lx * (vis_w / max(1, lw))
            self._pan_y = fy - ly * (vis_h / max(1, lh))

        self._repaint_zoom()

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            # Right click = start pan drag
            self._panning   = True
            self._pan_start = e.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return
        # Left click = pick diamond
        fx, fy = self._to_frame(e)
        if fx is not None:
            self.clicked.emit(fx, fy)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.RightButton:
            self._panning = False
            self.setCursor(Qt.CrossCursor)

    def mouseMoveEvent(self, e):
        if self._panning and self._pan_start is not None:
            # Pan by dragging with right mouse button
            dx = e.x() - self._pan_start.x()
            dy = e.y() - self._pan_start.y()
            self._pan_start = e.pos()
            if hasattr(self, '_vis_src'):
                lw = max(1, self.width()  - 2)
                lh = max(1, self.height() - 2)
                _, _, src_w, src_h = self._vis_src
                self._pan_x -= dx * (src_w / max(1, lw))
                self._pan_y -= dy * (src_h / max(1, lh))
            self._repaint_zoom()
            return
        fx, fy = self._to_frame(e)
        if fx is not None:
            self.mouse_moved.emit(fx, fy)

    def resizeEvent(self, e):
        """Re-render when widget is resized."""
        self._repaint_zoom()
        super().resizeEvent(e)

# ── helpers ──────────────────────────────────────────────────────────────────

def sec(text):
    l = QLabel(text)
    l.setObjectName("sectionLabel")
    return l

def val_label(color="#00E5B0"):
    l = QLabel("—")
    l.setStyleSheet(
        f"color:{color};font-size:14px;"
        f"font-family:'JetBrains Mono','Consolas',monospace;")
    return l

def hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color:#0e1a24;")
    return f

ROI_LABELS     = ["Top-Left", "Top-Right", "Bot-Right", "Bot-Left"]
ROI_COLS       = [(0,212,255),(82,160,255),(255,183,77),(232,121,249)]
ROI_LINES      = [(0,1),(1,2),(2,3),(3,0)]
ROI_LINE_NAMES = ["TOP","RIGHT","BOTTOM","LEFT"]

TRAY_W_MM = 203
TRAY_H_MM = 155

def draw_roi_overlay(frame, corners, mouse_pos=None):
    out = frame.copy()
    n   = len(corners)
    for seg_i, (a_i, b_i) in enumerate(ROI_LINES):
        if a_i < n and b_i < n:
            col = ROI_COLS[a_i]
            cv2.line(out,
                     (int(corners[a_i][0]), int(corners[a_i][1])),
                     (int(corners[b_i][0]), int(corners[b_i][1])),
                     col, 2, cv2.LINE_AA)
            mx = int((corners[a_i][0]+corners[b_i][0])/2)
            my = int((corners[a_i][1]+corners[b_i][1])/2)
            cv2.putText(out, ROI_LINE_NAMES[seg_i], (mx-20, my-6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1)
    if n > 0 and n < 4 and mouse_pos:
        cv2.line(out,
                 (int(corners[n-1][0]), int(corners[n-1][1])),
                 (int(mouse_pos[0]),    int(mouse_pos[1])),
                 (40,60,80), 1, cv2.LINE_AA)
    if n == 3 and mouse_pos:
        cv2.line(out,
                 (int(mouse_pos[0]),  int(mouse_pos[1])),
                 (int(corners[0][0]), int(corners[0][1])),
                 (30,50,70), 1, cv2.LINE_AA)
    for i, (cx, cy) in enumerate(corners):
        col = ROI_COLS[i]
        cv2.circle(out, (int(cx), int(cy)),  7, col, -1)
        cv2.circle(out, (int(cx), int(cy)), 10, col,  2)
        cv2.putText(out, ROI_LABELS[i], (int(cx)+13, int(cy)+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, col, 1)
    if n < 4:
        cv2.putText(out, f"Click {ROI_LABELS[n]} corner  ({n}/4)",
                    (10, out.shape[0]-12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, ROI_COLS[n], 1)
    else:
        cv2.putText(out, f"ROI SET  203x155 mm tray",
                    (10, out.shape[0]-12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,212,255), 1)
    return out

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — LIVE DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

class LiveTab(QWidget):
    def __init__(self, cam_thread: CameraThread, mapper: CoordinateMapper):
        super().__init__()
        self.cam    = cam_thread
        self.mapper = mapper

        self._roi_corners   = []
        self._drawing_roi   = False
        self._mouse_pos     = None
        self._last_raw_img  = None
        self._last_diamonds = []

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── Left: video area ─────────────────────────────────────────────

        views = QWidget()
        views.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vl = QVBoxLayout(views)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)

        top_views = QHBoxLayout()
        top_views.setSpacing(6)

        self._main_view = CameraView("Waiting for camera…")
        self._main_view.setCursor(Qt.CrossCursor)
        self._main_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._main_view.setMaximumHeight(600)

        self._mask_view = CameraView("Debug mask")
        self._mask_view.setFixedWidth(160)
        self._mask_view.setMaximumHeight(600)
        self._mask_view.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        top_views.addWidget(self._main_view, stretch=6)
        top_views.addWidget(self._mask_view, stretch=0)
        vl.addLayout(top_views, stretch=1)

        # ROI toolbar
        roi_row = QHBoxLayout()

        self._btn_draw_roi = QPushButton("✎  Draw ROI  (4 corners)")
        self._btn_draw_roi.setObjectName("btnBlue")
        self._btn_draw_roi.setCheckable(True)
        self._btn_draw_roi.toggled.connect(self._toggle_roi_draw)

        self._btn_undo_pt = QPushButton("↩  Undo Point")
        self._btn_undo_pt.clicked.connect(self._undo_point)

        self._btn_clear_roi = QPushButton("✕  Clear ROI")
        self._btn_clear_roi.setObjectName("btnRed")
        self._btn_clear_roi.clicked.connect(self._clear_roi)

        self._roi_status = QLabel("No ROI — draw 4 corners to start detection")
        self._roi_status.setStyleSheet(
            "font-size:13px;color:#4a6a7e;"
            "font-family:'JetBrains Mono','Consolas',monospace;")

        roi_row.addWidget(self._btn_draw_roi)
        roi_row.addWidget(self._btn_undo_pt)
        roi_row.addWidget(self._btn_clear_roi)
        roi_row.addWidget(self._roi_status, stretch=1)

        tray_badge = QLabel(f"Tray: {TRAY_W_MM}×{TRAY_H_MM} mm")
        tray_badge.setStyleSheet(
            "font-size:13px;color:#ffb74d;"
            "border:1px solid rgba(255,183,77,0.30);"
            "border-radius:4px;padding:2px 9px;"
            "font-family:'JetBrains Mono','Consolas',monospace;")
        roi_row.addWidget(tray_badge)

        # ← ADD zoom hint
        zoom_hint = QLabel("🔍 Scroll to zoom  |  Right-drag to pan")
        zoom_hint.setStyleSheet(
            "font-size:12px;color:#2a5060;"
            "font-family:'JetBrains Mono','Consolas',monospace;")
        roi_row.addWidget(zoom_hint)

        vl.addLayout(roi_row, stretch=0)
        root.addWidget(views, stretch=3)

        self._main_view.clicked.connect(self._on_view_click)
        self._main_view.mouse_moved.connect(self._on_mouse_move)

        # ── Right panel ──────────────────────────────────────────────────

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setMinimumWidth(300)
        right_scroll.setMaximumWidth(360)
        right_scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        right_w = QWidget()
        rl = QVBoxLayout(right_w)
        rl.setContentsMargins(4, 0, 6, 0)
        rl.setSpacing(10)
        right_scroll.setWidget(right_w)
        root.addWidget(right_scroll, stretch=1)

        # State label
        self._state_lbl = QLabel("DRAW ROI FIRST")
        self._state_lbl.setStyleSheet(
            "color:#52a0ff;font-size:13px;"
            "font-family:'JetBrains Mono','Consolas',monospace;"
            "padding:7px;border:1px solid rgba(82,160,255,0.25);"
            "border-radius:5px;background:rgba(82,160,255,0.04);")
        self._state_lbl.setAlignment(Qt.AlignCenter)
        rl.addWidget(self._state_lbl)

        # Robot connection indicator (read-only)
        self._robot_indicator = QLabel("● ROBOT DISCONNECTED")
        self._robot_indicator.setStyleSheet(
            "color:#ff6b6b;font-size:12px;"
            "font-family:'JetBrains Mono','Consolas',monospace;"
            "padding:6px 10px;border:1px solid rgba(255,82,82,0.30);"
            "border-radius:5px;background:rgba(255,82,82,0.05);")
        self._robot_indicator.setAlignment(Qt.AlignCenter)
        rl.addWidget(self._robot_indicator)

        # Robot status polling — reads real connected flag, no TCP guessing
        self._robot_connected = False
        self._ext_robot       = None
        self._ext_workflow    = None
        self._robot_poll = QTimer()
        self._robot_poll.timeout.connect(self._poll_robot_status)
        self._robot_poll.start(1000)   # check every second

        # ROI corners
        roi_grp = QGroupBox("ROI CORNERS  (frame px)")
        rgl = QGridLayout(roi_grp)
        rgl.setContentsMargins(10, 16, 10, 10)
        rgl.setSpacing(4)
        self._corner_labels = []
        corner_hex = ["#00E5B0","#52a0ff","#ffb74d","#e879f9"]
        for i, (lbl, hx) in enumerate(zip(ROI_LABELS, corner_hex)):
            name = QLabel(lbl)
            name.setStyleSheet(f"color:{hx};font-size:13px;")
            val  = QLabel("—")
            val.setStyleSheet(f"color:{hx};font-size:13px;")
            rgl.addWidget(name, i, 0)
            rgl.addWidget(val,  i, 1)
            self._corner_labels.append(val)
        rl.addWidget(roi_grp)

        # Detection stats
        stats_grp = QGroupBox("DETECTION")
        sgl = QGridLayout(stats_grp)
        sgl.setContentsMargins(10, 16, 10, 10)
        sgl.setSpacing(6)
        self._lbl_count   = val_label("#00E5B0")
        self._lbl_cluster = val_label("#ffb74d")
        self._lbl_fps     = val_label("#52a0ff")
        for row, (txt, w) in enumerate([("Diamonds", self._lbl_count),
                                         ("Cluster",  self._lbl_cluster),
                                         ("FPS",      self._lbl_fps)]):
            sgl.addWidget(QLabel(txt), row, 0)
            sgl.addWidget(w,           row, 1)
        rl.addWidget(stats_grp)

        # Detection params
        det_grp = QGroupBox("DETECTION PARAMS")
        dl = QVBoxLayout(det_grp)
        dl.setContentsMargins(10, 16, 10, 10)
        dl.setSpacing(8)

        self._min_r,  min_r_lbl  = self._slider("Min radius (px)",  1,  40, PARAMS.min_radius)
        self._max_r,  max_r_lbl  = self._slider("Max radius (px)", 10, 150, PARAMS.max_radius)
        self._circ,   circ_lbl   = self._slider("Circularity (%)", 10,  95, PARAMS.circularity)
        self._clust,  clust_lbl  = self._slider("Cluster dist",     1,  80, PARAMS.cluster_dist)
        self._margin, margin_lbl = self._slider("Edge margin (px)", 0,  50, PARAMS.edge_margin)

        for name, slider, lbl in [
            ("Min radius",   self._min_r,  min_r_lbl),
            ("Max radius",   self._max_r,  max_r_lbl),
            ("Circularity",  self._circ,   circ_lbl),
            ("Cluster dist", self._clust,  clust_lbl),
            ("Edge margin",  self._margin, margin_lbl),
        ]:
            rw = QWidget()
            rwl = QVBoxLayout(rw)
            rwl.setContentsMargins(0,0,0,0); rwl.setSpacing(2)
            tr = QHBoxLayout()
            tr.addWidget(QLabel(name)); tr.addStretch(); tr.addWidget(lbl)
            rwl.addLayout(tr); rwl.addWidget(slider)
            dl.addWidget(rw)
        rl.addWidget(det_grp)

        # Threshold
        thr_grp = QGroupBox("THRESHOLD")
        thrl = QVBoxLayout(thr_grp)
        thrl.setContentsMargins(10,16,10,10); thrl.setSpacing(6)
        self._otsu_cb = QCheckBox("Auto (Otsu)")
        self._otsu_cb.setChecked(True)
        self._otsu_cb.stateChanged.connect(self._on_otsu)
        self._thresh_slider, thr_lbl = self._slider("Value", 0, 255, PARAMS.threshold_val)
        self._thresh_slider.setEnabled(False)
        self._thr_lbl = thr_lbl
        thrl.addWidget(self._otsu_cb)
        tr2 = QHBoxLayout()
        tr2.addWidget(QLabel("Value")); tr2.addStretch(); tr2.addWidget(thr_lbl)
        thrl.addLayout(tr2); thrl.addWidget(self._thresh_slider)
        rl.addWidget(thr_grp)

        # Display
        dbg_grp = QGroupBox("DISPLAY")
        dbgl = QVBoxLayout(dbg_grp)
        dbgl.setContentsMargins(10,14,10,10)
        self._show_mask_cb = QCheckBox("Show debug mask")
        self._show_mask_cb.setChecked(True)
        dbgl.addWidget(self._show_mask_cb)
        rl.addWidget(dbg_grp)
        rl.addStretch()

        # slider → param bindings
        self._min_r.valueChanged.connect(  lambda v: setattr(PARAMS,'min_radius',  v) or min_r_lbl.setText(str(v)))
        self._max_r.valueChanged.connect(  lambda v: setattr(PARAMS,'max_radius',  v) or max_r_lbl.setText(str(v)))
        self._circ.valueChanged.connect(   lambda v: setattr(PARAMS,'circularity', v) or circ_lbl.setText(f"{v}%"))
        self._clust.valueChanged.connect(  lambda v: setattr(PARAMS,'cluster_dist',v) or clust_lbl.setText(str(v)))
        self._margin.valueChanged.connect( lambda v: setattr(PARAMS,'edge_margin', v) or margin_lbl.setText(str(v)))
        self._thresh_slider.valueChanged.connect(
            lambda v: setattr(PARAMS,'threshold_val',v) or thr_lbl.setText(str(v)))

        self._frame_times  = []
        self._last_frame_t = time.time()
        self.cam.frame_ready.connect(self._on_frame)
        self.cam.stats_ready.connect(self._on_stats)

        # Vibration motor (serial)
        self._motor_serial  = None
        self._system_state  = "SCAN"
        self._vibrate_start = 0
        self._vibrate_secs  = 2.0
        self._pickup_target = 0

        # Auto-mode suppression flag — when True, _state_machine() and
        # _motor_cmd() become no-ops so this dialog's own internal
        # SCAN/VIBRATE/WAIT_PICKUP logic and motor serial never run.
        # Used by DiamondSelector during Auto mode, which drives
        # vibration through ESP32 instead. Manual mode never sets this,
        # so its behavior is completely unchanged.
        self._suppress_internal = False

        try:
            import serial
            self._motor_serial = serial.Serial('COM4', 115200, timeout=1)
            time.sleep(2)
            print("✅ Motor on COM4")
        except Exception:
            pass  # Motor not connected — vibration commands will be silently skipped

        self._sm_timer = QTimer()
        self._sm_timer.timeout.connect(self._state_machine)
        self._sm_timer.start(200)

    # ── ROI drawing ──────────────────────────────────────────────────────────

    def _toggle_roi_draw(self, checked):
        self._drawing_roi = checked
        if checked:
            self._roi_corners = []
            self._mouse_pos   = None
            self.cam.set_tray_poly(None)
            self._update_corner_labels()
            self._roi_status.setText("Click Draw ROI to set region manually")
            self._main_view.setCursor(Qt.CrossCursor)
            self._system_state = "NO_ROI"
        else:
            self._drawing_roi = False
            self._main_view.setCursor(Qt.ArrowCursor)
            if len(self._roi_corners) == 4:
                corners_px = self._order_points(self._roi_corners)
                self.cam.set_tray_poly(corners_px)

                self._roi_status.setText(f"ROI active — {TRAY_W_MM}×{TRAY_H_MM} mm tray")
                self._system_state = "SCAN"
            else:
                self._roi_status.setText(f"Need 4 corners — only {len(self._roi_corners)} set")

    def _order_points(self, pts):
        pts  = np.array(pts, dtype="float32")
        s    = pts.sum(axis=1)
        diff = np.diff(pts, axis=1)
        return [pts[np.argmin(s)], pts[np.argmin(diff)],
                pts[np.argmax(s)], pts[np.argmax(diff)]]

    def _on_view_click(self, fx, fy):
        if self._drawing_roi:
            if len(self._roi_corners) >= 4:
                return
            self._roi_corners.append((int(fx), int(fy)))
            idx = len(self._roi_corners) - 1
            self._update_corner_labels()
            if len(self._roi_corners) < 4:
                msg_parts = [f"Corner {len(self._roi_corners)}/4 set"]
                if idx > 0:
                    msg_parts.append(f"— {ROI_LINE_NAMES[idx-1]} edge drawn")
                msg_parts.append(f"→ click {ROI_LABELS[len(self._roi_corners)]}")
                self._roi_status.setText("  ".join(msg_parts))
            else:
                ordered = self._order_points(self._roi_corners)
                self._roi_corners = [[float(p[0]), float(p[1])] for p in ordered]
                self.cam.set_tray_poly(self._roi_corners)
                
                self._update_corner_labels()
                self._roi_status.setText(
                    f"✓ ROI complete — {TRAY_W_MM}×{TRAY_H_MM} mm  |  detection active")
                self._btn_draw_roi.setChecked(False)
                self._drawing_roi = False
                self._main_view.setCursor(Qt.ArrowCursor)
                self._system_state = "SCAN"
        else:
            # ← NEW: not drawing ROI — try to pick diamond at click position
            self._try_pick_at(fx, fy)

    def _try_pick_at(self, fx, fy):
        """
        Pick diamond at click position.
        Finds nearest isolated diamond within CLICK_RADIUS pixels,
        converts to robot mm, then:
        - calls workflow.set_pick_target(rx, ry)  → advances WAITING_CAMERA → PICKING
        - calls robot.move_to_tray_xy(rx, ry)     → physical move (fallback if no workflow)
        """
        CLICK_RADIUS = 30   # px — how close to diamond centre you need to click

        best_d    = None
        best_dist = float("inf")
        for d in self._last_diamonds:
            if d.is_cluster:
                continue
            dist = math.hypot(d.px - fx, d.py - fy)
            if dist < CLICK_RADIUS and dist < best_dist:
                best_dist = dist
                best_d    = d

        if best_d is None:
            # No diamond close enough — show hint
            self._roi_status.setText("⚠  Click closer to a detected diamond (green dot)")
            return

        robot_x, robot_y = best_d.robot_x, best_d.robot_y

        # Sanity check — reject if coordinates are out of robot range
        if not (-500 < robot_x < 500 and -500 < robot_y < 500):
            self._roi_status.setText(f"⚠  Invalid robot coords: ({robot_x:.1f}, {robot_y:.1f})")
            return

        self._roi_status.setText(
            f"✓  Diamond selected → Robot ({robot_x:.1f}, {robot_y:.1f}) mm")

        # ── Primary path: advance workflow state machine ──────────────────────
        if self._ext_workflow is not None:
            self._ext_workflow.set_pick_target(robot_x, robot_y)

        # ── Fallback: direct robot move (tester standalone mode) ─────────────
        elif self._ext_robot is not None and self._ext_robot.is_connected:
            self._ext_robot.move_to_tray_xy(robot_x, robot_y)

    def set_robot(self, robot):
        """Inject the main app's RobotController instance.
        The indicator reflects robot.is_connected in real time every second.
        Clicking an isolated diamond enqueues a move on the real robot."""
        self._ext_robot = robot
        # Force immediate update without waiting for next poll tick
        self._update_robot_indicator(bool(robot.is_connected) if robot else False)
        
    def set_workflow(self, workflow):
        """Inject the main app's Workflow instance so diamond clicks advance the state."""
        self._ext_workflow = workflow

    def suppress_internal_statemachine(self, on: bool):
        """
        Auto mode entry point: disables this dialog's own SCAN/VIBRATE/
        WAIT_PICKUP state machine and its motor-serial vibration commands.
        Used so DiamondSelector can drive vibration through ESP32 instead
        without the dialog's internal logic fighting it.

        Manual mode never calls this (stays False), so nothing here
        changes Manual mode's behavior.
        """
        self._suppress_internal = on
        if on:
            # Make sure we don't leave the motor mid-vibration and don't
            # leave the internal state machine stuck on VIBRATE/WAIT_PICKUP.
            try:
                if self._motor_serial:
                    self._motor_serial.write(b'S0\n')
                    self._motor_serial.flush()
            except Exception:
                pass
            self._system_state = "SCAN"

    def _poll_robot_status(self):
        """Read is_connected directly from the injected RobotController.
        If no robot has been injected, always shows DISCONNECTED."""
        if self._ext_robot is not None:
            connected = bool(self._ext_robot.is_connected)
        else:
            connected = False
        self._update_robot_indicator(connected)

    def set_robot_connected(self, connected: bool):
        """Manual override — forces indicator to a specific state."""
        self._update_robot_indicator(connected)

    def _update_robot_indicator(self, connected):
        if connected == self._robot_connected:
            return  # no change, skip redraw
        self._robot_connected = connected
        if connected:
            style = (
                "color:#00E5B0;font-size:12px;"
                "font-family:'JetBrains Mono','Consolas',monospace;"
                "padding:6px 10px;border:1px solid rgba(0,229,176,0.30);"
                "border-radius:5px;background:rgba(0,229,176,0.05);")
            text  = "● ROBOT CONNECTED"
            hdr_style = (
                "font-size:13px;font-family:'JetBrains Mono','Consolas',monospace;"
                "color:#00E5B0;border:1px solid rgba(0,229,176,0.22);"
                "border-radius:4px;padding:2px 9px;background:rgba(0,229,176,0.04);")
        else:
            style = (
                "color:#ff6b6b;font-size:12px;"
                "font-family:'JetBrains Mono','Consolas',monospace;"
                "padding:6px 10px;border:1px solid rgba(255,82,82,0.30);"
                "border-radius:5px;background:rgba(255,82,82,0.05);")
            text  = "● ROBOT DISCONNECTED"
            hdr_style = (
                "font-size:13px;font-family:'JetBrains Mono','Consolas',monospace;"
                "color:#ff6b6b;border:1px solid rgba(255,82,82,0.22);"
                "border-radius:4px;padding:2px 9px;background:rgba(255,82,82,0.04);")
        self._robot_indicator.setText(text)
        self._robot_indicator.setStyleSheet(style)
        try:
            self.window()._hdr_robot_status.setText(text)
            self.window()._hdr_robot_status.setStyleSheet(hdr_style)
        except Exception:
            pass

    def _on_mouse_move(self, fx, fy):
        self._mouse_pos = (fx, fy)
        if self._drawing_roi:
            self._repaint_roi_overlay()

    def _repaint_roi_overlay(self):
        if self._last_raw_img is None:
            # No camera frame yet — draw overlay on a blank black canvas
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            overlay = draw_roi_overlay(blank, self._roi_corners, self._mouse_pos)
            rgb  = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0],
                          rgb.shape[1] * 3, QImage.Format_RGB888).copy()
            self._main_view.set_frame(qimg)
            return
        img = self._last_raw_img
        w, h = img.width(), img.height()
        bpl = img.bytesPerLine()
        ptr = img.bits()
        ptr.setsize(h * bpl)
        frame_rgb = np.array(ptr, dtype=np.uint8).reshape((h, bpl // 3, 3))[:, :w, :].copy()
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        overlay   = draw_roi_overlay(frame_bgr, self._roi_corners, self._mouse_pos)
        rgb  = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0],
                      rgb.shape[1] * 3, QImage.Format_RGB888).copy()
        self._main_view.set_frame(qimg)

    def _undo_point(self):
        if not self._roi_corners:
            return
        self._roi_corners.pop()
        self._update_corner_labels()
        self.cam.set_tray_poly(
            self._roi_corners if len(self._roi_corners) == 4 else None)
        n = len(self._roi_corners)
        if n < 4:
            self._system_state = "NO_ROI"
            if not self._drawing_roi:
                self._btn_draw_roi.setChecked(True)
        self._roi_status.setText(
            f"Undone — {n} corner(s) → click {ROI_LABELS[n]} next" if n < 4
            else f"ROI active ({TRAY_W_MM}×{TRAY_H_MM} mm)")
        self._repaint_roi_overlay()

    def _clear_roi(self):
        self._roi_corners = []
        self._mouse_pos   = None
        self._drawing_roi = False
        self._btn_draw_roi.setChecked(False)
        self.cam.set_tray_poly(None)
        self._update_corner_labels()
        self._main_view.setCursor(Qt.ArrowCursor)
        self._roi_status.setText("ROI cleared — auto-detecting tray...")
        self._system_state = "SCAN"
        self._repaint_roi_overlay()

    def _update_corner_labels(self):
        for i, lbl in enumerate(self._corner_labels):
            if i < len(self._roi_corners):
                cx, cy = self._roi_corners[i]
                lbl.setText(f"({cx}, {cy})")
            else:
                lbl.setText("—")

    # ── State machine ─────────────────────────────────────────────────────────

    def _state_machine(self):
        # Auto mode (DiamondSelector) has taken over scanning/vibrating —
        # this dialog's own internal state machine must not run at all.
        if self._suppress_internal:
            return

        diamonds    = self._last_diamonds
        isolated    = [d for d in diamonds if not d.is_cluster]
        has_cluster = any(d.is_cluster for d in diamonds)
        now         = time.time()

        if self._system_state == "SCAN":
            self._state_lbl.setText("SCANNING…")
            self._state_lbl.setStyleSheet(
                "color:#00E5B0;font-size:13px;"
                "font-family:'JetBrains Mono','Consolas',monospace;"
                "padding:7px;border:1px solid rgba(0,229,176,0.20);"
                "border-radius:5px;background:rgba(0,229,176,0.04);")
            if has_cluster and len(isolated) < 2:
                self._motor_cmd(b'A\n')
                self._vibrate_start = now
                self._system_state  = "VIBRATE"

        elif self._system_state == "VIBRATE":
            remaining = self._vibrate_secs - (now - self._vibrate_start)
            self._state_lbl.setText(f"VIBRATING {max(0, remaining):.1f}s")
            self._state_lbl.setStyleSheet(
                "color:#52a0ff;font-size:13px;"
                "font-family:'JetBrains Mono','Consolas',monospace;"
                "padding:7px;border:1px solid rgba(82,160,255,0.20);"
                "border-radius:5px;background:rgba(82,160,255,0.04);")
            if remaining <= 0:
                self._motor_cmd(b'S0\n')
                self._system_state = "WAIT_PICKUP" if len(isolated) >= 2 else "SCAN"

        elif self._system_state == "WAIT_PICKUP":
            remaining_pick = len(isolated)
            self._state_lbl.setText(f"PICK {remaining_pick} remaining")
            self._state_lbl.setStyleSheet(
                "color:#ffb74d;font-size:13px;"
                "font-family:'JetBrains Mono','Consolas',monospace;"
                "padding:7px;border:1px solid rgba(255,183,77,0.20);"
                "border-radius:5px;background:rgba(255,183,77,0.04);")
            if remaining_pick == 0:
                self._system_state = "SCAN"

    def _motor_cmd(self, cmd):
        # Auto mode suppression — never touch the physical motor from
        # this dialog while DiamondSelector/ESP32 is driving vibration.
        if self._suppress_internal:
            return
        try:
            if self._motor_serial:
                self._motor_serial.write(cmd)
                self._motor_serial.flush()
        except Exception as e:
            print(f"Motor error: {e}")

    def _slider(self, name, lo, hi, val):
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi); s.setValue(val)
        l = QLabel(str(val))
        l.setStyleSheet(
            "color:#00E5B0;min-width:36px;text-align:right;"
            "font-family:'JetBrains Mono','Consolas',monospace;")
        l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return s, l

    def _on_otsu(self, state):
        on = (state == Qt.Checked)
        PARAMS.threshold_mode = "otsu" if on else "manual"
        self._thresh_slider.setEnabled(not on)

    def _on_frame(self, ann_img, mask_img):
        self._last_raw_img = ann_img
        if self._drawing_roi or len(self._roi_corners) > 0:
            self._repaint_roi_overlay()
        else:
            self._main_view.set_frame(ann_img)
        if self._show_mask_cb.isChecked():
            self._mask_view.set_frame(mask_img)
        now = time.time()
        self._frame_times.append(now)
        self._frame_times = [t for t in self._frame_times if now - t < 2.0]
        self._lbl_fps.setText(f"{len(self._frame_times) / 2.0:.1f}")

    def _on_stats(self, diamonds):
        self._last_diamonds = diamonds
        self._lbl_count.setText(str(len(diamonds)))
        has_c = any(d.is_cluster for d in diamonds)
        self._lbl_cluster.setText("YES" if has_c else "no")
        self._lbl_cluster.setStyleSheet(
            f"color:{'#ffb74d' if has_c else '#00E5B0'};font-size:14px;"
            f"font-family:'JetBrains Mono','Consolas',monospace;")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — CALIBRATION
# ═══════════════════════════════════════════════════════════════════════════════

CORNER_LABELS = ["Top-Left", "Top-Right", "Bottom-Right", "Bottom-Left"]
CORNER_COLS   = [(0,212,255),(82,160,255),(255,183,77),(232,121,249)]
CORNER_HEX    = ["#00E5B0","#52a0ff","#ffb74d","#e879f9"]

class CalibTab(QWidget):
    calibration_updated = pyqtSignal()

    def __init__(self, cam_thread: CameraThread, mapper: CoordinateMapper):
        super().__init__()
        self.cam    = cam_thread
        self.mapper = mapper
        self._corners_px   = []
        self._last_frame   = None
        self._frozen_frame = None

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)

        self._view = CameraView("Freeze frame to mark corners")
        self._view.setCursor(Qt.CrossCursor)
        self._view.clicked.connect(self._on_click)
        ll.addWidget(self._view)

        btn_row = QHBoxLayout()
        self._btn_freeze   = QPushButton("⏸  Freeze Frame")
        self._btn_freeze.setObjectName("btnBlue")
        self._btn_freeze.clicked.connect(self._freeze)
        self._btn_unfreeze = QPushButton("▶  Live")
        self._btn_unfreeze.clicked.connect(self._unfreeze)
        self._btn_undo     = QPushButton("↩  Undo")
        self._btn_undo.clicked.connect(self._undo)
        btn_row.addWidget(self._btn_freeze)
        btn_row.addWidget(self._btn_unfreeze)
        btn_row.addWidget(self._btn_undo)
        ll.addLayout(btn_row)
        root.addWidget(left, stretch=3)

        right = QWidget()
        right.setFixedWidth(300)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)

        instr = QLabel(
            "HOW TO CALIBRATE\n\n"
            "1. Freeze the frame\n"
            "2. Click each tray corner in order:\n"
            "   Top-Left → Top-Right →\n"
            "   Bottom-Right → Bottom-Left\n"
            "3. Enter the robot X,Y for each\n"
            "   corner (from teach pendant)\n"
            "4. Compute — aim for < 1 mm error\n\n"
            f"Tray: {TRAY_W_MM} × {TRAY_H_MM} mm"
        )
        instr.setStyleSheet(
            "font-size:13px;color:#4a6a7a;"
            "background:#050a0e;border:1px solid #0e1a24;"
            "border-radius:6px;padding:12px;"
            "font-family:'JetBrains Mono','Consolas',monospace;")
        instr.setWordWrap(True)
        rl.addWidget(instr)

        corners_grp = QGroupBox("CORNER POINTS")
        cgl = QVBoxLayout(corners_grp)
        cgl.setContentsMargins(8, 16, 8, 8)

        self._px_labels = []
        self._rx_spins  = []
        self._ry_spins  = []

        for i, (lbl, hex_c) in enumerate(zip(CORNER_LABELS, CORNER_HEX)):
            row_w = QGroupBox()
            r, g, b = int(hex_c[1:3],16), int(hex_c[3:5],16), int(hex_c[5:7],16)
            row_w.setStyleSheet(
                f"QGroupBox{{border:1px solid rgba({r},{g},{b},0.25);"
                f"border-radius:5px;margin-top:0px;padding:6px;"
                f"background:rgba({r},{g},{b},0.02);}}")
            row_l = QGridLayout(row_w)
            row_l.setContentsMargins(6,6,6,6); row_l.setSpacing(4)

            name_l = QLabel(lbl)
            name_l.setStyleSheet(f"color:{hex_c};font-size:13px;")
            px_l = QLabel("Click in image →")
            px_l.setStyleSheet("color:#4a6a7e;font-size:13px;")

            rx_spin = QDoubleSpinBox()
            ry_spin = QDoubleSpinBox()
            for spin in (rx_spin, ry_spin):
                spin.setRange(-2000, 2000)
                spin.setDecimals(2)
                spin.setSuffix(" mm")
                spin.setValue(0.0)
                spin.setFixedHeight(30)

            row_l.addWidget(name_l,             0, 0, 1, 2)
            row_l.addWidget(px_l,               1, 0, 1, 2)
            row_l.addWidget(QLabel("Robot X:"), 2, 0)
            row_l.addWidget(rx_spin,            2, 1)
            row_l.addWidget(QLabel("Robot Y:"), 3, 0)
            row_l.addWidget(ry_spin,            3, 1)
            cgl.addWidget(row_w)

            self._px_labels.append(px_l)
            self._rx_spins.append(rx_spin)
            self._ry_spins.append(ry_spin)

        rl.addWidget(corners_grp)

        self._btn_compute = QPushButton("✓  Compute Calibration")
        self._btn_compute.setObjectName("btnGreen")
        self._btn_compute.setFixedHeight(34)
        self._btn_compute.clicked.connect(self._compute)
        rl.addWidget(self._btn_compute)

        self._err_lbl = QLabel("—")
        self._err_lbl.setStyleSheet(
            "color:#4a6a7e;font-family:'JetBrains Mono','Consolas',monospace;"
            "font-size:24px;font-weight:500;padding:8px;")
        self._err_lbl.setAlignment(Qt.AlignCenter)
        self._result_lbl = QLabel("")
        self._result_lbl.setStyleSheet(
            "color:#4a6a7e;font-size:13px;"
            "font-family:'JetBrains Mono','Consolas',monospace;")
        self._result_lbl.setAlignment(Qt.AlignCenter)
        self._result_lbl.setWordWrap(True)
        rl.addWidget(self._err_lbl)
        rl.addWidget(self._result_lbl)
        rl.addStretch()
        root.addWidget(right, stretch=0)

        if mapper.is_calibrated:
            self._prefill()

        self.cam.frame_ready.connect(self._on_live_frame)

    def _on_live_frame(self, ann_img, _):
        if self._frozen_frame is None:
            self._last_frame = ann_img
            self._view.set_frame(ann_img)

    def _freeze(self):
        if self._last_frame:
            self._frozen_frame = self._last_frame
            self._view.set_frame(self._frozen_frame)
        else:
            # No camera — freeze a blank canvas so user can still click corners
            self._frozen_frame = True   # sentinel so _draw_corners knows we are frozen
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            rgb  = cv2.cvtColor(blank, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0],
                          rgb.shape[1] * 3, QImage.Format_RGB888).copy()
            self._view.set_frame(qimg)

    def _unfreeze(self):
        self._frozen_frame = None

    def _on_click(self, fx, fy):
        idx = len(self._corners_px)
        if idx >= 4:
            return
        self._corners_px.append((fx, fy))
        self._px_labels[idx].setText(f"Pixel: ({fx:.0f}, {fy:.0f})")
        self._px_labels[idx].setStyleSheet(f"color:{CORNER_HEX[idx]};font-size:13px;")
        self._draw_corners()

    def _undo(self):
        if not self._corners_px:
            return
        idx = len(self._corners_px) - 1
        self._corners_px.pop()
        self._px_labels[idx].setText("Click in image →")
        self._px_labels[idx].setStyleSheet("color:#4a6a7e;font-size:13px;")
        self._draw_corners()

    def _draw_corners(self):
        if self._frozen_frame is None:
            # Not frozen yet — nothing to draw on
            return
        if self._frozen_frame is True:
            # Frozen on blank canvas (no camera)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
        else:
            img = self._frozen_frame.copy()
            w, h = img.width(), img.height()
            bpl = img.bytesPerLine()
            ptr = img.bits()
            ptr.setsize(h * bpl)
            frame = np.array(ptr, dtype=np.uint8).reshape((h, bpl // 3, 3))[:, :w, :].copy()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        for i, (px, py) in enumerate(self._corners_px):
            col = CORNER_COLS[i]
            cv2.circle(frame, (int(px), int(py)),  9, col, -1)
            cv2.circle(frame, (int(px), int(py)), 13, col,  2)
            cv2.putText(frame, CORNER_LABELS[i], (int(px)+16, int(py)+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
        if len(self._corners_px) < 4:
            cv2.putText(frame, f"Click: {CORNER_LABELS[len(self._corners_px)]}",
                        (10, frame.shape[0]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        CORNER_COLS[len(self._corners_px)], 2)
        rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0],
                      rgb.shape[1]*3, QImage.Format_RGB888).copy()
        self._view.set_frame(qimg)

    def _compute(self):
        if len(self._corners_px) < 4:
            QMessageBox.warning(self, "Incomplete",
                "Click all 4 tray corners in the frozen frame first.")
            return
        corners_robot = [(self._rx_spins[i].value(), self._ry_spins[i].value())
                        for i in range(4)]
        if all(rx == 0 and ry == 0 for rx, ry in corners_robot):
            ret = QMessageBox.question(self, "Robot coords are all zero",
                "All robot XY values are 0,0 — continue anyway?",
                QMessageBox.Yes | QMessageBox.No)
            if ret != QMessageBox.Yes:
                return
        ok = self.mapper.set_corners(self._corners_px, corners_robot)
        if not ok:
            self._result_lbl.setText("Homography failed — check points are not collinear")
            return
        err = self.mapper.reprojection_error()
        self._err_lbl.setText(f"{err:.3f} mm")
        if err < 1.0:   col, msg = "#00E5B0", "✓ Excellent"
        elif err < 2.0: col, msg = "#ffb74d", "⚠ Acceptable"
        else:           col, msg = "#ff6b6b", "✕ High error — re-click corners"
        self._err_lbl.setStyleSheet(
            f"color:{col};font-family:'JetBrains Mono','Consolas',monospace;"
            f"font-size:24px;font-weight:500;padding:8px;")
        self._result_lbl.setText(f"{msg}\nSaved to {CALIB_FILE}")
        self._result_lbl.setStyleSheet(
            f"color:{col};font-size:13px;"
            f"font-family:'JetBrains Mono','Consolas',monospace;")
        self.cam.mapper = self.mapper
        self.calibration_updated.emit()

        # Save ROI corners from live tab into calibration json
        try:
            import json as _json
            with open(CALIB_FILE) as f:
                d = _json.load(f)
            live = self.window().live_tab
            if hasattr(live, '_roi_corners') and len(live._roi_corners) == 4:
                d["roi_corners"] = [[float(p[0]), float(p[1])]
                                    for p in live._roi_corners]
                with open(CALIB_FILE, "w") as f:
                    _json.dump(d, f, indent=2)
                print(f"[Calib] ROI corners saved to {CALIB_FILE}")
            else:
                print("[Calib] No ROI corners set in live tab — skipped")
        except Exception as e:
            print(f"[Calib] Could not save ROI corners: {e}")

    def _prefill(self):
        for i, (pp, rp) in enumerate(
                zip(self.mapper.corners_px, self.mapper.corners_robot)):
            if i >= 4: break
            self._corners_px.append(tuple(pp))
            self._px_labels[i].setText(f"Pixel: ({pp[0]:.0f}, {pp[1]:.0f})")
            self._px_labels[i].setStyleSheet(f"color:{CORNER_HEX[i]};font-size:13px;")
            self._rx_spins[i].setValue(rp[0])
            self._ry_spins[i].setValue(rp[1])
        err = self.mapper.reprojection_error()
        self._err_lbl.setText(f"{err:.3f} mm")
        self._err_lbl.setStyleSheet(
            "color:#00E5B0;font-family:'JetBrains Mono','Consolas',monospace;"
            "font-size:24px;font-weight:500;padding:8px;")
        self._result_lbl.setText("Loaded from saved calibration")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════════

class SnapshotTab(QWidget):
    def __init__(self, cam_thread: CameraThread, mapper: CoordinateMapper):
        super().__init__()
        self.cam    = cam_thread
        self.mapper = mapper
        self._last_frame = None
        self._snap_frame = None
        self._diamonds   = []

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)

        self._view = CameraView("No snapshot yet")
        ll.addWidget(self._view)

        btn_row = QHBoxLayout()
        self._btn_snap = QPushButton("📷  Capture Snapshot")
        self._btn_snap.setObjectName("btnGreen")
        self._btn_snap.setFixedHeight(38)
        self._btn_snap.clicked.connect(self._snap)
        self._btn_save = QPushButton("💾  Save Image")
        self._btn_save.clicked.connect(self._save)
        btn_row.addWidget(self._btn_snap)
        btn_row.addWidget(self._btn_save)
        ll.addLayout(btn_row)
        root.addWidget(left, stretch=3)

        right = QWidget()
        right.setFixedWidth(280)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        rl.addWidget(sec("DETECTION RESULTS"))

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["#", "px", "py", "Robot X", "Robot Y"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        rl.addWidget(self._table)

        self._summary = QLabel("Take a snapshot to analyse")
        self._summary.setStyleSheet(
            "font-size:13px;color:#4a6a7e;padding:6px;"
            "font-family:'JetBrains Mono','Consolas',monospace;")
        self._summary.setWordWrap(True)
        rl.addWidget(self._summary)
        rl.addStretch()
        root.addWidget(right, stretch=0)

        self.cam.frame_ready.connect(lambda img, _: setattr(self, '_last_frame', img))

    def _snap(self):
        if self._last_frame is None:
            return
        self._snap_frame = self._last_frame
        img = self._snap_frame
        w, h = img.width(), img.height()
        ptr = img.bits(); ptr.setsize(h * w * 3)
        frame_rgb = np.array(ptr).reshape((h, w, 3)).copy()
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        diamonds, ann, _ = detect_diamonds(frame_bgr, self.mapper)
        self._diamonds = diamonds
        ann_rgb = cv2.cvtColor(ann, cv2.COLOR_BGR2RGB)
        qimg = QImage(ann_rgb.data, ann_rgb.shape[1], ann_rgb.shape[0],
                      ann_rgb.shape[1]*3, QImage.Format_RGB888).copy()
        self._view.set_frame(qimg)
        self._table.setRowCount(0)
        for i, d in enumerate(diamonds):
            self._table.insertRow(i)
            cols = [str(i+1), f"{d.px:.0f}", f"{d.py:.0f}",
                    f"{d.robot_x:.2f}", f"{d.robot_y:.2f}"]
            for c, txt in enumerate(cols):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignCenter)
                if d.is_cluster:
                    item.setForeground(QColor("#ffb74d"))
                self._table.setItem(i, c, item)
        has_c   = any(d.is_cluster for d in diamonds)
        cal_str = "Calibrated" if self.mapper.is_calibrated else "Not calibrated"
        self._summary.setText(
            f"{len(diamonds)} diamond(s) detected\n"
            f"Cluster: {'YES ⚠' if has_c else 'No'}\n"
            f"Mode: {cal_str}")
        self._summary.setStyleSheet(
            f"font-size:13px;padding:6px;"
            f"color:{'#ffb74d' if has_c else '#00E5B0'};"
            f"font-family:'JetBrains Mono','Consolas',monospace;")

    def _save(self):
        if self._snap_frame is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save snapshot", "snapshot.png", "Images (*.png *.jpg)")
        if not path:
            return
        img = self._snap_frame
        w, h = img.width(), img.height()
        ptr = img.bits(); ptr.setsize(h * w * 3)
        frame     = np.array(ptr).reshape((h, w, 3)).copy()
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        cv2.imwrite(path, frame_bgr)
        QMessageBox.information(self, "Saved", f"Saved to {path}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tray Camera Tester — Mindron Technology")
        self.setMinimumSize(1100, 680)
        self.setStyleSheet(QSS)

        self.mapper = CoordinateMapper()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = self._build_header()
        root.addWidget(hdr)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        root.addWidget(self.tabs)

        self.cam_thread = CameraThread(self.mapper)
        self.cam_thread.start()

        self.live_tab  = LiveTab(self.cam_thread, self.mapper)
        self.calib_tab = CalibTab(self.cam_thread, self.mapper)
        self.snap_tab  = SnapshotTab(self.cam_thread, self.mapper)

        self.tabs.addTab(self.live_tab,  "LIVE")
        self.tabs.addTab(self.calib_tab, "CALIBRATE")
        self.tabs.addTab(self.snap_tab,  "SNAPSHOT")

        self.calib_tab.calibration_updated.connect(self._on_calibrated)

        sb = QStatusBar()
        sb.setStyleSheet(
            "QStatusBar{background:#050709;border-top:1px solid #0e1a24;"
            "font-size:13px;color:#4a6a7e;"
            "font-family:'JetBrains Mono','Consolas',monospace;}")
        self.setStatusBar(sb)
        sb.showMessage(
            "Calibration loaded — draw ROI to start"
            if self.mapper.is_calibrated
            else "No calibration — go to CALIBRATE tab | Draw ROI to begin")

    def _build_header(self):
        hdr = QWidget()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #060b10,stop:1 #050709);"
            "border-bottom:1px solid #0e1a24;")
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(14)

        def vsep():
            f = QFrame()
            f.setFrameShape(QFrame.VLine)
            f.setStyleSheet("color:#0e1a24;max-height:20px;")
            return f

        logo = QLabel("TRAY CAMERA TESTER")
        logo.setStyleSheet(
            "font-family:'JetBrains Mono','Cascadia Code','Consolas',monospace;"
            "font-size:14px;color:#00E5B0;letter-spacing:3px;font-weight:600;")

        sub = QLabel("Mindron Technology")
        sub.setStyleSheet(
            "font-family:'JetBrains Mono','Cascadia Code','Consolas',monospace;"
            "font-size:13px;color:#4a6a7e;")

        tray_lbl = QLabel(f"⬜  {TRAY_W_MM}×{TRAY_H_MM} mm")
        tray_lbl.setStyleSheet(
            "font-size:13px;color:#ffb74d;"
            "border:1px solid rgba(255,183,77,0.28);"
            "border-radius:4px;padding:2px 9px;"
            "font-family:'JetBrains Mono','Consolas',monospace;"
            "background:rgba(255,183,77,0.04);")

        cam_lbl = QLabel("Camera")
        cam_lbl.setStyleSheet(
            "font-size:13px;color:#4a6a7e;"
            "font-family:'JetBrains Mono','Consolas',monospace;")
        self._cam_combo = QComboBox()
        self._cam_combo.setFixedWidth(130)
        self._cam_combo.addItems(["Camera 0","Camera 1","Camera 2","Camera 3"])
        self._cam_combo.currentIndexChanged.connect(
            lambda i: self.cam_thread.set_camera(i))

        self._calib_status = QLabel(
            "✓  Calibrated" if self.mapper.is_calibrated else "⚠  Not calibrated")
        self._calib_status.setStyleSheet(
            f"font-size:13px;"
            f"font-family:'JetBrains Mono','Consolas',monospace;"
            f"color:{'#00E5B0' if self.mapper.is_calibrated else '#ffb74d'};"
            f"border:1px solid {'rgba(0,229,176,0.22)' if self.mapper.is_calibrated else 'rgba(255,183,77,0.22)'};"
            f"border-radius:4px;padding:2px 9px;"
            f"background:{'rgba(0,229,176,0.04)' if self.mapper.is_calibrated else 'rgba(255,183,77,0.04)'};")

        self._hdr_robot_status = QLabel("● ROBOT DISCONNECTED")
        self._hdr_robot_status.setStyleSheet(
            "font-size:13px;"
            "font-family:'JetBrains Mono','Consolas',monospace;"
            "color:#ff6b6b;"
            "border:1px solid rgba(255,82,82,0.22);"
            "border-radius:4px;padding:2px 9px;"
            "background:rgba(255,82,82,0.04);")

        lay.addWidget(logo)
        lay.addWidget(vsep())
        lay.addWidget(sub)
        lay.addWidget(tray_lbl)
        lay.addStretch()
        lay.addWidget(self._hdr_robot_status)
        lay.addWidget(vsep())
        lay.addWidget(self._calib_status)
        lay.addWidget(vsep())
        lay.addWidget(cam_lbl)
        lay.addWidget(self._cam_combo)
        return hdr

    def _on_calibrated(self):
        self._calib_status.setText("✓  Calibrated")
        self._calib_status.setStyleSheet(
            "font-size:13px;"
            "font-family:'JetBrains Mono','Consolas',monospace;"
            "color:#00E5B0;"
            "border:1px solid rgba(0,229,176,0.22);"
            "border-radius:4px;padding:2px 9px;"
            "background:rgba(0,229,176,0.04);")
        self.statusBar().showMessage(
            f"Calibration saved — error: {self.mapper.reprojection_error():.3f} mm")

    def closeEvent(self, event):
        self.cam_thread.stop()
        event.accept()

# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not HAS_CV:
        print("Install opencv-python first:  pip install opencv-python pyqt5")
        sys.exit(1)
    app = QApplication(sys.argv)
    app.setFont(QFont("JetBrains Mono", 12))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())