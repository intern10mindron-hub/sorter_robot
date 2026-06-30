from __future__ import annotations
import re
from PyQt5.QtCore import QThread, pyqtSignal

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

from config import SCALE_PORT, SCALE_BAUD, SCALE_POLL_MS, SCALE_UNIT, SCALE_OFFSET


class ScaleReader(QThread):
    weight_updated = pyqtSignal(float)  # carats
    connected      = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._ser     = None
        self._last_ct = 0.0
    
    def run(self):
        self._running = True
        if not HAS_SERIAL:
            self.connected.emit(False)
            self._simulate()
            return

        port = self._find_port(SCALE_PORT)
        try:
            self._ser = serial.Serial(
                port,
                SCALE_BAUD,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
            )
            self.connected.emit(True)
            # print(f"[Scale] Connected on {port}")
            buf = ""
            while self._running:
                try:
                    # Send request
                    self._ser.write(b'W\r\n')
            
                    # 🔥 IMPORTANT: wait for response
                    self.msleep(200)
            
                    # Read full line (not 64 bytes)
                    raw = self._ser.readline().decode("ascii", errors="ignore")
            
                    if raw.strip():
                        # print("[RAW]", raw.strip())
            
                        ct = self._parse(raw)
                        if ct is not None and ct >= 0:
                            self._last_ct = ct
                            self.weight_updated.emit(ct)
            
                    else:
                        print("[DEBUG] No data from scale")
            
                    self.msleep(SCALE_POLL_MS)
            
                except Exception as e:
                    # print(f"[Scale] Read error: {e}")
                    pass
        finally:
            if self._ser and self._ser.is_open:
                self._ser.close()

    def stop(self):
        self._running = False
        self.wait(2000)

    def _find_port(self, preferred: str) -> str:
        """Try preferred port first, then auto-scan for scale."""
        if not HAS_SERIAL:
            return preferred
        try:
            # Test if preferred port exists
            ports = [p.device for p in serial.tools.list_ports.comports()]
            if preferred in ports:
                return preferred
            # Auto-scan — return first available port
            if ports:
                # print(f"[Scale] Port {preferred} not found, trying {ports[0]}")
                return ports[0]
        except Exception:
            pass
        return preferred

    def _parse(self, line: str):
        """Parse weight from Scaletec SAB-603C-CL serial output.
        SAB series outputs carats. Format examples:
            'ST,GS,+  0.3456 CT'
            'ST,GS,-  0.0000 CT'
            '+  0.3460CT'
            '  0.3456'
        """
        if not line:
            return None

        # Debug — shows exactly what the scale is sending
        # Remove this line once weight is confirmed working in UI
        # print(f"[Scale] RAW: {repr(line)}")

        # Skip unstable / error lines
        if "US," in line or "OL" in line or "----" in line:
            return None

        # Extract numeric value — works with or without sign and unit suffix
        m = re.search(r'([+\-]?\s*\d+\.\d+)', line)
        if m:
            try:
                val = float(m.group(1).replace(" ", ""))
                if val < 0:
                    return None   # negative = pan lifted / unstable
                if SCALE_UNIT == "grams":
                    carats = round(val / 0.2, 4)
                else:
                    carats = round(val, 4)   # SAB outputs carats directly
                return max(0.0, carats - SCALE_OFFSET)
            except ValueError:
                pass
        return None

    def _simulate(self):
        """No hardware connected — emit 0.0 only, no fake weights."""
        # print("[Scale] No hardware — emitting 0.0 (no simulation)")
        while self._running:
            self.weight_updated.emit(0.0)
            self.msleep(SCALE_POLL_MS)