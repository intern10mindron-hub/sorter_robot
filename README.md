# Luminax Sorter — Agent Instructions

## Project Overview
**Luminax Sorter** is a PyQt5-based desktop application that controls a robotic diamond sorting system. It captures images, detects diamonds on a tray, vibrates the tray to separate clusters, picks each diamond with a robotic arm, weighs it on a scale, and sorts it into weight-categorized slots.

## Architecture

### Layered Design
- **UI Layer** (`ui/`): PyQt5 widgets with real-time telemetry, control panels, and 3D robot viewer
- **Core Layer** (`core/`): Finite state machine (Workflow), session management, slot tracking
- **Hardware Layer** (`hardware/`): Controllers for scale, ESP32, camera, and robotic arm via serial/TCP

### Key Components

| Module | Responsibility |
|--------|-----------------|
| `core/workflow.py` | State machine orchestrating the sorting pipeline (IDLE → SCANNING → VIBRATING → PICKING → WEIGHING → SORTING) |
| `core/session.py` | Tracks current sorting session state and statistics |
| `core/slot_manager.py` | Manages 66 storage slots and weight categorization |
| `hardware/robot_controller.py` | TCP client for robotic arm (IP: 192.168.0.20:10003) |
| `hardware/scale_reader.py` | Serial reader for weight scale (COM3, 9600 baud) |
| `hardware/esp32_controller.py` | Serial controller for vibration motor (COM4, 115200 baud) |
| `hardware/camera_detector.py` | OpenCV camera feed for diamond detection and clustering |
| `ui/main_window.py` | Main application window coordinating all panels |
| `ui/theme.py` | **NEW** — shared design-token module (colors, fonts, QSS helper functions) for the "Industrial Console" UI theme |
| `ui/donut_gauge.py` | **NEW** — reusable custom-painted circular donut-gauge widget used for ratio-based stats (e.g. SORTED progress) |

## UI Design System ("Industrial Console" theme)

The UI was restyled to move away from a generic dark-dashboard look toward a
premium industrial-HMI aesthetic, modeled after reference machine-control
consoles (charcoal base, lighter elevated cards, soft desaturated accent,
donut-gauge data viz).

### `ui/theme.py` — shared tokens
All UI files import shared constants from this module instead of defining
their own local palettes, so colors/fonts never drift between panels:

| Token | Value | Usage |
|---|---|---|
| `BG_BASE` | `#15171A` | Window background — true charcoal |
| `BG_CARD` | `#22252A` | Elevated card surface — deliberately **lighter** than the base (key visual trait distinguishing this from earlier flat-dark iterations) |
| `BG_CARD_HI` | `#2A2E34` | Card hover/raised state |
| `BG_DEEP` | `#0F1113` | Recessed wells — camera feed background, input fields |
| `BORDER` / `BORDER_LO` / `BORDER_HI` | grays | Hairline borders at three emphasis levels |
| `TXT_BRIGHT` / `TXT_MID` / `TXT_DIM` | off-white → dim gray | Text hierarchy |
| `BRAND` | `#8FD9B6` | Soft desaturated sage-mint — the single primary accent color, used for START button, active states, progress rings |
| `GREEN` / `AMBER` / `BLUE` / `RED` | soft/desaturated | Semantic state colors (running, caution, info, alert) — intentionally muted, not neon |
| `FONT_LABEL` | Inter / Segoe UI Semibold | Section headers, button labels |
| `FONT_MONO` | JetBrains Mono / IBM Plex Mono | Coordinate/technical readouts where monospace alignment matters |
| `FONT_DISPLAY` | Inter / Segoe UI | Large numeric values (state name, gauge numbers, stat values) — clean grotesk, not mono |

Helper functions in `theme.py`:
- `card_qss(radius, bg, border)` — standard elevated rounded-card style
- `pill_button_qss(bg, text, radius)` — solid rounded pill button (primary actions)
- `outline_button_qss(border_col, text_col, bg, radius)` — soft outline button (secondary actions like HOME/TRAY/SCALE)

### `ui/donut_gauge.py` — circular progress widget
A custom `QWidget` subclass with a hand-painted `paintEvent` (dim background
arc + colored progress arc + centered big value + small label below), used
to replace flat numeric stat boxes with ratio-based gauges where a ratio
actually exists (e.g. `SORTED / 66 slots`). Numeric-but-non-ratio values
(total carats, average carats, current slot) remain as plain inline stat
rows beside the gauge — a gauge would be meaningless for an open-ended
running total.

Public API: `set_value(value_text, fraction=None, color=None)`,
`set_fraction(fraction)`, `set_label(label)`.

### Restyled files (visual only — no logic/signal changes)
- `ui/control_panel.py` — workflow tab now leads with a `DonutGauge` for
  SORTED progress; toggle switches repainted as soft rounded pills; all
  cards use `card_qss()` (lighter, rounded, generously padded) instead of
  the earlier flat boxed-stat-grid layout
- `ui/camera_panel.py` — Pick & Place / Quick Positions / Vacuum & Vibration
  / Emergency sections rebuilt as elevated rounded cards with quiet
  (non-decorated) section labels, matching the reference's restrained header
  style
- `ui/telemetry_bar.py` — bottom strip changed from plain text columns with
  vertical dividers to individual rounded telemetry chips (`TelemetryItem`
  as a `QFrame` card), echoing the reference's bottom command-bar rhythm
- `ui/main_window.py` — header bar and START/PAUSE/STOP buttons changed to
  rounded-pill chrome; the file's local `_T` token class values were
  repointed to match `theme.py` exactly (kept as a local class rather than
  migrated to avoid touching every `_T.XXX` call site — values are now
  identical to the shared tokens)

No signal connections, sequence steps, thresholds, or hardware logic were
modified in this pass — every change is QSS/paint-only.

## Key Conventions

### Hardware Communication
- **Async pattern**: All hardware controllers run in `QThread` to avoid blocking UI
- **Signals/Slots**: PyQt5 signals communicate between threads (`pyqtSignal`, `pyqtSlot`)
- **Configuration-first**: All ports, baud rates, IP addresses, and machine parameters in `config.py`
- **Serial ports**: Scale (COM3, 9600) and ESP32 (COM4, 115200) initialized at startup
- **TCP robot**: Non-blocking socket communication; coordinate transforms between image (pixels) and machine (mm)

### State Machine
- Workflow emits `state_changed` signals for UI updates
- Each state has associated metadata in `STATE_INFO` dict (display name, description, status code)
- Transitions validate preconditions before proceeding to next state

### UI Layer
- All dialogs in `ui/dialogs/` (modular, non-blocking)
- Telemetry bar (`telemetry_bar.py`) displays live scale readings and pressure sensors, now rendered as rounded chip cards (see UI Design System above)
- Robot viewer (`robot_viewer.py`) uses Three.js for 3D visualization via QWebEngineView
- Control panel (`control_panel.py`) provides start/stop, preset management, manual overrides, and the SORTED donut gauge
- **Shared styling**: `ui/theme.py` is the single source of truth for colors/fonts — any new UI file should import from it (`from ui.theme import ...`) rather than hardcoding hex values, to keep the Industrial Console theme consistent
- **Donut gauges**: for any new ratio-based stat (e.g. "X of Y"), prefer `ui/donut_gauge.py`'s `DonutGauge` widget over a flat number box

### Asset Serving
- Local HTTP server (127.0.0.1:18642) serves HTML/JS assets for 3D viewer
- Started in daemon thread before creating QApplication
- Suppresses logging to avoid console noise

## Common Development Tasks

### Adding a Hardware Controller
1. Create new file in `hardware/`
2. Subclass `QThread` for non-blocking I/O
3. Emit PyQt5 signals for state changes
4. Connect signal in `MainWindow.__init__()` and emit signals during operation

### Adding a New Workflow State
1. Add enum value to `State` in `core/workflow.py`
2. Add entry to `STATE_INFO` dict (display name, description, status code)
3. Add entry to `STEP_MAP` for progress indicator (array of 0s and 1s/2s)
4. Implement transition logic in `Workflow` class
5. Update UI panels to handle new state

### Adding a New Themed UI Panel
1. Import shared tokens: `from ui.theme import BG_BASE, BG_CARD, BRAND, FONT_LABEL, FONT_MONO, FONT_DISPLAY, card_qss, pill_button_qss, outline_button_qss, ...`
2. Wrap card-like sections in a `QFrame` styled with `card_qss(radius=14-16)` rather than hand-rolled QSS
3. Use `FONT_LABEL` for section headers/buttons, `FONT_DISPLAY` for large numeric values, `FONT_MONO` only for technical/coordinate readouts
4. For any "X of Y" ratio stat, use `ui/donut_gauge.py`'s `DonutGauge` instead of a flat stat box
5. Keep the accent color (`BRAND`, soft sage-mint) restrained — reserve it for primary actions and progress indicators, not decorative everywhere

### Modifying Machine Parameters
All settings centralized in `config.py`:
- **Servo positions**: `PICK_Z_SAFE`, `PICK_Z_DOWN`, `SCALE_Z` (millimeters)
- **Timing**: `VIBRATION_DURATION`, `SCALE_SETTLE_MS`, poll rates
- **Hardware**: Serial ports, baud rates, robot IP/port, camera index
- **Detection**: `CLUSTER_DISTANCE_PX` for diamond clustering algorithm

### Coordinate Transform (Pixels ↔ Machine)
- Tray corners and dimensions hardcoded in `robot_controller.py`
- Camera detects diamonds in pixel space; must convert to machine coordinates (mm)
- Bilinear interpolation used for accurate picking

## File Structure
```
config.py                # Global configuration (ports, baud, IPs, timings)
main.py                  # Application entry point; starts HTTP server
presets.json             # Weight ranges and slot assignments
positions.json           # Calibrated tray/scale positions

ui/
  theme.py               # NEW — shared design tokens (colors, fonts, QSS helpers) for the Industrial Console theme
  donut_gauge.py         # NEW — reusable custom-painted circular donut-gauge widget
  main_window.py         # Main window layout and signal routing; header/status bar restyled
  control_panel.py       # Start/Stop buttons, preset selector; SORTED donut gauge, rounded cards
  camera_panel.py        # Live camera feed display; rounded elevated cards
  robot_viewer.py        # 3D robot visualization (Three.js)
  telemetry_bar.py       # Live sensor readings (scale, pressure); rounded chip cards
  manual_override.py     # Manual position/slot control
  setup_panel.py         # Calibration wizard
  dialogs/                # Modal dialogs (non-blocking)

core/
  workflow.py            # State machine and orchestration logic
  session.py             # Session tracking (processed diamonds, stats)
  slot_manager.py        # Weight range logic and slot assignment

hardware/
  robot_controller.py    # TCP client for ABB/KUKA robot
  scale_reader.py        # Serial weight scale reader
  esp32_controller.py    # Serial ESP32 vibration motor control
  camera_detector.py     # OpenCV diamond detection + clustering

assets/
  viewer.html            # 3D viewer HTML page
  three.min.js            # Three.js library
  GLTFLoader.js           # 3D model loader
  OrbitControls.js        # 3D camera control
  qwebchannel.js           # PyQt5 ↔ JavaScript bridge
```

## Running and Testing

### Start Application
```bash
python main.py
```
The application initializes all hardware controllers and displays the main window.

### Hardware Simulation
When hardware is not connected, controllers gracefully degrade:
- Scale reader: Returns 0.0g if COM3 disconnected
- Robot: Motion commands logged instead of sent if IP unreachable
- Camera: Fallback to blank feed if camera not available

### Common Issues
- **"Port already in use"**: Another instance running; kill process and retry
- **"Scale not responding"**: Check COM3 port and baud rate in `config.py`
- **"Robot connection refused"**: Verify robot IP/port in `config.py` and robot is powered on
- **"Camera not detected"**: Update `CAMERA_INDEX` in `config.py` (0=first camera, 1=second)
- **`ModuleNotFoundError: No module named 'theme'`**: `theme.py` (and `donut_gauge.py`) must live inside the `ui/` package, imported as `from ui.theme import ...` / `from ui.donut_gauge import DonutGauge` — not at project root

## Dependencies
- **PyQt5, PyQtWebEngine**: GUI framework and web engine
- **opencv-python**: Diamond detection via image processing
- **numpy**: Array operations and coordinate transforms
- **pyserial**: Serial communication (scale, ESP32)
- **openpyxl**: Export sorting results to Excel

See `requirements.txt` for exact versions.
