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
- Telemetry bar (`telemetry_bar.py`) displays live scale readings and pressure sensors
- Robot viewer (`robot_viewer.py`) uses Three.js for 3D visualization via QWebEngineView
- Control panel (`control_panel.py`) provides start/stop, preset management, manual overrides

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
  main_window.py         # Main window layout and signal routing
  control_panel.py       # Start/Stop buttons, preset selector
  camera_panel.py        # Live camera feed display
  robot_viewer.py        # 3D robot visualization (Three.js)
  telemetry_bar.py       # Live sensor readings (scale, pressure)
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
  three.min.js           # Three.js library
  GLTFLoader.js          # 3D model loader
  OrbitControls.js       # 3D camera control
  qwebchannel.js         # PyQt5 ↔ JavaScript bridge
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

## Dependencies
- **PyQt5, PyQtWebEngine**: GUI framework and web engine
- **opencv-python**: Diamond detection via image processing
- **numpy**: Array operations and coordinate transforms
- **pyserial**: Serial communication (scale, ESP32)
- **openpyxl**: Export sorting results to Excel

See `requirements.txt` for exact versions.
