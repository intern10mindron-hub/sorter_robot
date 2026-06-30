from __future__ import annotations

# ── HARDWARE PORTS ────────────────────────────────────────────────────────────
SCALE_PORT    = "COM13"
SCALE_BAUD    = 9600         # Scale-Tec standard baud rate
SCALE_UNIT    = "carats"    # Scale-Tec outputs carats directly  
SCALE_OFFSET  = 0.0         # tare offset in carats
ESP32_PORT    = "COM4"
ESP32_BAUD    = 115200
ROBOT_IP      = "192.168.0.20"
ROBOT_PORT    = 10003
CAMERA_INDEX  = 0         # 0 = first camera, 1 = second camera

# ── MACHINE PARAMETERS ────────────────────────────────────────────────────────
TOTAL_SLOTS         = 66    # Fixed: model has 66 slots not 67
VIBRATION_DURATION  = 1500
PICK_Z_SAFE         = 144.5
PICK_Z_DOWN         = 80
SCALE_Z             = 60
PRESSURE_THRESHOLD  = 55
SCALE_SETTLE_MS     = 8000
CLUSTER_DISTANCE_PX = 40
MIN_DIAMOND_CT = 0.05   # below this = no diamond / noise

POS_HOME  = "HOME"
POS_TRAY  = "TRAY"
POS_SCALE = "SCALE"

# ── UPDATE RATES ──────────────────────────────────────────────────────────────

SCALE_POLL_MS    = 100
PRESSURE_POLL_MS = 80
CAMERA_POLL_MS   = 33
JOINT_POLL_MS    = 50
# ── PICK TIMING ───────────────────────────────────────────────────────────────
PICK_GRIP_DELAY_MS = 500   # wait after pump/solenoid ON before lifting —
                            # gives vacuum time to seal & grip the diamond

# ── PATHS ─────────────────────────────────────────────────────────────────────

PRESETS_FILE = "presets.json"
VIEWER_HTML  = "http://127.0.0.1:18642/assets/viewer.html"
ASSETS_PORT  = 18642
EXPORTS_DIR  = "exports"

# ── PANEL WIDTH ───────────────────────────────────────────────────────────────

PANEL_WIDTH = 300

# ── WEIGHT COLOURS ────────────────────────────────────────────────────────────

WEIGHT_COLORS = [
    "#38bdf8", "#0ea5e9", "#6366f1", "#8b5cf6",
    "#a855f7", "#c084fc", "#e879f9", "#ec4899",
    "#f43f5e", "#ef4444", "#f97316", "#fb923c",
    "#facc15", "#a3e635", "#4ade80", "#00c8a0",
    "#00E5B0", "#06b6d4", "#38bdf8", "#0ea5e9",
    "#6366f1", "#8b5cf6", "#a855f7", "#c084fc",
    "#e879f9", "#ec4899", "#f43f5e", "#ef4444",
    "#f97316", "#fb923c", "#facc15", "#a3e635",
    "#4ade80", "#00c8a0", "#00E5B0", "#06b6d4",
    "#38bdf8", "#0ea5e9", "#6366f1", "#8b5cf6",
    "#a855f7", "#c084fc", "#e879f9", "#ec4899",
    "#f43f5e", "#ef4444", "#f97316", "#fb923c",
    "#facc15", "#a3e635", "#4ade80", "#00c8a0",
    "#00E5B0", "#06b6d4", "#38bdf8", "#0ea5e9",
    "#6366f1", "#8b5cf6", "#a855f7", "#c084fc",
    "#e879f9", "#ec4899", "#f43f5e", "#ef4444",
]

# ── STYLESHEET ────────────────────────────────────────────────────────────────

STYLESHEET = """
QWidget {
    background-color: #0D1117;
    color: #E2E8F0;
    font-family: 'IBM Plex Mono', 'Consolas', monospace;
    font-size: 12px;
    border: none;
}
QMainWindow { background-color: #0D1117; }

QSplitter::handle { background-color: #2D3748; width: 1px; height: 1px; }

QTabWidget::pane {
    border: none;
    border-top: 1px solid #2D3748;
    background: #1C2128;
}
QTabBar {
    background: #161B22;
    border-bottom: 1px solid #2D3748;
}
QTabBar::tab {
    background: transparent;
    color: #4A5568;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 3px;
    padding: 11px 0px;
    min-width: 58px;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
}
QTabBar::tab:selected {
    color: #00C8A0;
    border-bottom: 2px solid #00C8A0;
}
QTabBar::tab:hover:!selected { color: #A0AEC0; }

QPushButton {
    background: #1C2128;
    border: 1px solid #2D3748;
    border-radius: 4px;
    color: #A0AEC0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 2px;
    padding: 7px 18px;
}
QPushButton:hover {
    border-color: #4A5568;
    color: #E2E8F0;
    background: #242C38;
}
QPushButton:pressed { background: #161B22; }

QPushButton#btnStart {
    border-color: rgba(0,200,160,0.55);
    color: #00C8A0;
    background: rgba(0,200,160,0.08);
    font-weight: 600;
}
QPushButton#btnStart:hover {
    background: rgba(0,200,160,0.18);
    border-color: #00C8A0;
}
QPushButton#btnPause {
    border-color: rgba(251,146,60,0.55);
    color: #fb923c;
    background: rgba(251,146,60,0.08);
    font-weight: 600;
}
QPushButton#btnPause:hover {
    background: rgba(251,146,60,0.18);
    border-color: #fb923c;
}
QPushButton#btnStop {
    border-color: rgba(248,113,113,0.55);
    color: #f87171;
    background: rgba(248,113,113,0.08);
    font-weight: 600;
}
QPushButton#btnStop:hover {
    background: rgba(248,113,113,0.18);
    border-color: #f87171;
}
QPushButton#btnVibrate {
    border-color: rgba(251,146,60,0.30);
    color: #A0AEC0;
}
QPushButton#btnVibrate:hover {
    border-color: #fb923c;
    color: #fb923c;
    background: rgba(251,146,60,0.09);
}
QPushButton#btnAuto {
    border-color: rgba(0,200,160,0.30);
    color: #00C8A0;
    background: rgba(0,200,160,0.05);
}
QPushButton#btnAuto:hover {
    background: rgba(0,200,160,0.15);
    border-color: #00C8A0;
}
QPushButton#btnExport {
    border-color: #2D3748;
    color: #A0AEC0;
}
QPushButton#btnExport:hover {
    border-color: #00C8A0;
    color: #00C8A0;
    background: rgba(0,200,160,0.08);
}
QPushButton#btnNewPreset {
    border-color: #2D3748;
    color: #4A5568;
}
QPushButton#btnNewPreset:hover {
    border-color: #4A5568;
    color: #E2E8F0;
    background: #1C2128;
}

QTableWidget {
    background: transparent;
    alternate-background-color: #161B22;
    gridline-color: #2D3748;
    border: none;
    font-size: 11px;
    color: #A0AEC0;
}
QTableWidget::item { padding: 7px 10px; border: none; }
QTableWidget::item:selected {
    background: #2D3748;
    color: #E2E8F0;
}
QHeaderView::section {
    background: #161B22;
    color: #4A5568;
    font-size: 9px;
    letter-spacing: 3px;
    border: none;
    border-bottom: 1px solid #2D3748;
    padding: 7px 10px;
}

QScrollBar:vertical {
    background: transparent;
    width: 3px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2D3748;
    border-radius: 2px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #4A5568; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 0; }

QLineEdit {
    background: #161B22;
    border: 1px solid #2D3748;
    border-radius: 4px;
    color: #E2E8F0;
    padding: 6px 10px;
    font-size: 12px;
}
QLineEdit:focus { border-color: #00C8A0; }

QComboBox {
    background: #161B22;
    border: 1px solid #2D3748;
    border-radius: 4px;
    color: #A0AEC0;
    padding: 6px 10px;
    font-size: 12px;
}
QComboBox QAbstractItemView {
    background: #1C2128;
    border: 1px solid #2D3748;
    selection-background-color: #2D3748;
    color: #E2E8F0;
}

QStatusBar {
    background: #161B22;
    border-top: 1px solid #2D3748;
    font-size: 11px;
    color: #4A5568;
    padding: 0 16px;
}

QToolTip {
    background: #1C2128;
    border: 1px solid #2D3748;
    color: #E2E8F0;
    font-size: 11px;
    padding: 6px 12px;
    border-radius: 4px;
}
"""

# ── ROBOT Z COORDINATES (measured) ───────────────────────────────────────────
Z_TRAY_PICK    =  84.436  # descend to grip diamond from tray
Z_SAFE_TRAVEL  = 144.5     # lift height during all horizontal transfers
Z_SCALE_PLACE  = 121.141   # descend to place diamond on scale
Z_SCALE_PICK   = 119.050   # descend to pick diamond from scale (same height, separate constant)
Z_SLOT_DROP    =  65.372   # descend to release diamond into slot
Z_SCALE_CLEAR  = 125.0   # nozzle clear height during scale measurement
SCALE_PLACE_DWELL_MS = 150   # hold pump ON at Z_SCALE_PLACE for this long before
                              # releasing — lets the diamond settle gently onto the
                              # scale pan instead of being thrown off by momentum
                              # when the vacuum releases at high robot speed

Z_TRAY_FLOOR  = 82.890   # shaft never goes below this on tray
Z_SCALE_FLOOR = 114.851  # shaft never goes below this on scale

PRESSURE_DIAMOND_THRESHOLD = 7_000_000  # above this = diamond is held
PRESSURE_WEAK_THRESHOLD    = 4_000_000   # Partial pick — retry without re-weighing
PICK_PRESSURE_SETTLE_MS    = 250        # wait at Z_SAFE_TRAVEL before pressure check

STAGED_DESCENT_STEPS = 1  # number of equal sub-moves from travel height down to floor

# ── ROBOT XY POSITIONS (loaded from positions.json via setup panel) ───────────
PICK_X      = 400.0    # placeholder — overridden by positions.json
PICK_Y      =   0.0
SCALE_X     = 400.0    # placeholder — overridden by positions.json
SCALE_Y     =   0.0

# ── Weight Ranges ─────────────────────────────────────────────────────────────
# A1-A5 AND B1-B6 are intentionally blocked/empty (11 slots total) — no
# weight range, no diamonds ever sorted there. Weight ranges start fresh
# and sequential from C1 onward:
#   C1  = 0.000–0.100
#   C2  = 0.100–0.200
#   C3  = 0.200–0.300
#   ... continuing in 0.100 ct steps through every remaining slot in
#   SLOT_ORDER, in order.

def _build_default_ranges():
    from hardware.robot_controller import SLOT_ORDER

    # Slots that are now empty/unused — no weight range assigned, and
    # never selected by find_slot_for_weight().
    EMPTY_SLOTS = {
        "A1", "A2", "A3", "A4", "A5",
        "B1", "B2", "B3", "B4", "B5", "B6",
    }

    ranges = []
    sequential_index = 0   # next range = sequential_index * 0.100

    for name in SLOT_ORDER:
        if name in EMPTY_SLOTS:
            # Blocked slot: disabled, no weight range
            ranges.append({"slot": name, "min_ct": 0.0, "max_ct": 0.0})
        else:
            lo = round(sequential_index * 0.100, 3)
            hi = round(lo + 0.100, 3)
            ranges.append({"slot": name, "min_ct": lo, "max_ct": hi})
            sequential_index += 1

    return ranges

DEFAULT_WEIGHT_RANGES = _build_default_ranges()

# File where operator-edited weight ranges are saved/loaded
WEIGHT_RANGES_FILE = "weight_ranges.json"