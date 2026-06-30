from __future__ import annotations
import serial
import serial.tools.list_ports
from PyQt5.QtCore import QThread, pyqtSignal


class PressureSensor(QThread):
    """
    Reads normalized pressure values from the HX710B ESP32 on a dedicated
    serial port (default 4). The ESP32 firmware handles baseline zeroing
    and outputs one signed integer per line at ~50 Hz.

    Signals:
        pressure_updated(int)  — emitted on every valid reading
        error(str)             — emitted on serial/parse errors
        connected(bool)        — emitted when port opens or fails

    Usage:
        self.pressure = PressureSensor(port="COM14")
        self.pressure.pressure_updated.connect(self._on_pressure)
        self.pressure.start()
        ...
        self.pressure.stop()
    """

    pressure_updated = pyqtSignal(int)
    error            = pyqtSignal(str)
    connected        = pyqtSignal(bool)

    def __init__(self, port: str = "COM14", baud: int = 115200, parent=None):
        super().__init__(parent)
        self._port    = port
        self._baud    = baud
        self._running = False

    # ── PUBLIC API ────────────────────────────────────────────────────────────

    def start(self):
        if not self.isRunning():
            super().start()

    def stop(self):
        self._running = False
        self.wait(2000)

    # ── THREAD ────────────────────────────────────────────────────────────────

    def run(self):
        self._running = True
        ser = None

        try:
            ser = serial.Serial(
                port=self._port,
                baudrate=self._baud,
                timeout=1.0,
            )
            print(f"[Pressure] Connected → {self._port} @ {self._baud}")
            self.connected.emit(True)

            # Flush any startup banner from the firmware ("HX710B READY", etc.)
            ser.reset_input_buffer()

            while self._running:
                try:
                    line = ser.readline().decode("ascii", errors="ignore").strip()
                except Exception as e:
                    self.error.emit(f"Pressure read error: {e}")
                    break

                if not line:
                    continue

                # Skip firmware status lines (non-numeric)
                if not line.lstrip("-").isdigit():
                    print(f"[Pressure] Firmware msg: {line}")
                    continue

                try:
                    value = int(line)
                    self.pressure_updated.emit(value)
                except ValueError:
                    self.error.emit(f"Pressure parse error: {line!r}")

        except serial.SerialException as e:
            print(f"[Pressure] Failed to open {self._port}: {e}")
            self.connected.emit(False)
            self.error.emit(f"Pressure sensor: {e}")

        finally:
            if ser and ser.is_open:
                try:
                    ser.close()
                except Exception:
                    pass
            print(f"[Pressure] Disconnected")