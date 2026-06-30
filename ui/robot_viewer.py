from __future__ import annotations
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QUrl, QObject, pyqtSlot, pyqtSignal
from config import VIEWER_HTML

class ConsolePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        print(f'[JS] {message}')

class _JSBridge(QObject):
    slot_selected    = pyqtSignal(int)
    slot_cleared  = pyqtSignal(int)      
    all_slots_cleared = pyqtSignal()    
    slot_highlighted = pyqtSignal(int)

    @pyqtSlot(int)
    def onSlotSelected(self, slot_index: int):
        self.slot_selected.emit(slot_index)
        self.slot_highlighted.emit(slot_index)

class RobotViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #0D1117;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._build_header())

        self._view = QWebEngineView()
        self._view.setPage(ConsolePage(self._view))
        self._view.setStyleSheet("background: #0D1117;")

        settings = self._view.settings()
        settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(
            QWebEngineSettings.AllowRunningInsecureContent, True)
        settings.setAttribute(
            QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebGLEnabled, True)

        self._bridge  = _JSBridge()
        self._channel = QWebChannel()
        self._channel.registerObject("qtBridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        lay.addWidget(self._view)

        self._loaded = False
        self._view.loadFinished.connect(self._on_loaded)
        
        self._view.load(QUrl(VIEWER_HTML))

    # ── Public signals ────────────────────────────────────────────────────
    @property
    def slot_selected(self):
        return self._bridge.slot_selected

    @property
    def slot_highlighted(self):
        return self._bridge.slot_highlighted

    def _build_header(self) -> QWidget:
        hdr = QWidget()
        hdr.setFixedHeight(34)
        hdr.setStyleSheet(
            "border-bottom: 1px solid #2D3748; background: #161B22;"
        )

        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(12, 0, 12, 0)
        title = QLabel("ROBOT MODEL")
        title.setStyleSheet(
            "font-size: 10px; letter-spacing: 3px; color: #A9B4BE;"
            "font-family: 'IBM Plex Mono';"
        )

        self._dot = QLabel("●")
        self._dot.setStyleSheet("font-size: 7px; color: #00C8A0;")
        self._chip = QLabel("IDLE")
        self._chip.setStyleSheet(
            "font-size: 8px; letter-spacing: 2px; padding: 3px 9px;"
            "border-radius: 3px; color: #4A5568; background: #1C2128;"
            "border: 1px solid #2D3748;"
        )

        lay.addWidget(title)
        lay.addStretch()
        lay.addWidget(self._chip)
        lay.addSpacing(8)
        lay.addWidget(self._dot)
        return hdr

    def _on_loaded(self, ok: bool):
        self._loaded = ok
        if ok:
            print("[RobotViewer] Page loaded successfully")
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(4000, self._print_glb_info)
        else:
            print("[RobotViewer] Page load FAILED")


    def _print_glb_info(self):
        self._view.page().runJavaScript("""
            (function() {
                if (!robotModel) return 'model not loaded yet';
                var box = new THREE.Box3().setFromObject(robotModel);
                var s = box.getSize(new THREE.Vector3());
                return 'SIZE x=' + s.x.toFixed(2) +
                       ' y=' + s.y.toFixed(2) +
                       ' z=' + s.z.toFixed(2);
            })()
        """, lambda r: print("[GLB]", r))

    def _js(self, script: str):
        if self._loaded:
            self._view.page().runJavaScript(script)

    # ── Poll JS for slot assignment ───────────────────────────────────────
    def poll_slot_assignments(self, callback):
        """Poll JS for latest slot assignment every 100ms."""
        if self._loaded:
            self._view.page().runJavaScript(
                "window._lastAssignment || null",
                callback
            )

    def clear_last_assignment(self):
        """Clear JS assignment after Python processed it."""
        self._js("window._lastAssignment = null;")

    # ── PUBLIC API ────────────────────────────────────────────────────────
    def update_joints(self, j1, j2, j3, j4):
        self._js(f"updateRobot({j1:.2f},{j2:.2f},{j3:.2f},{j4:.2f})")

    def update_scale(self, ct: float):
        self._js(f"updateScale({ct:.4f})")

    def select_slot_in_viewer(self, slot_index: int):
        self._js(f"selectSlotFromPanel({slot_index})")

    def set_state(self, state_code: str, label: str):
        colors = {
            "sc": ("#38bdf8", "#001525", "#003060"),
            "pk": ("#00C8A0", "#001a0a", "#003015"),
            "vb": ("#fb923c", "#1a0f00", "#3a2500"),
            "wg": ("#38bdf8", "#001525", "#003060"),
            "sr": ("#00C8A0", "#001a0a", "#003015"),
            "al": ("#f87171", "#1a0000", "#500000"),
            "id": ("#4A5568", "#1C2128", "#2D3748"),
            "ok": ("#00C8A0", "#001a0a", "#003015"),
        }
        
        col, bg, border = colors.get(state_code, colors["id"])
        self._chip.setText(label)
        self._chip.setStyleSheet(
            f"font-size: 8px; letter-spacing: 2px; padding: 3px 9px;"
            f"border-radius: 3px; color: {col}; background: {bg};"
            f"border: 1px solid {border};"
        )

    def update_slot_color(self, slot_index: int, hex_color: str):
        self._js(f"setSlotColor({slot_index}, '{hex_color}')")

    def toggle_slot_mode(self, on: bool):
        self._js(f"setSlotMode({'true' if on else 'false'})")

    def toggle_grid(self, on: bool):
        self._js(f"toggleGridVisibility({'true' if on else 'false'})")

    def toggle_autorot(self, on: bool):
        self._js(f"setAutoRotate({'true' if on else 'false'})")