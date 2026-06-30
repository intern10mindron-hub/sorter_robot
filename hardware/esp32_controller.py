from __future__ import annotations
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

from config import ESP32_PORT, ESP32_BAUD, PRESSURE_POLL_MS, PRESSURE_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────────
# Firmware command map for UPDATED_LAST_FINAL_CODE.ino
#
# Pump relay commands:
#   PON  -> pump/relay ON
#   POFF -> pump/relay OFF
#
# Vacuum solenoid commands:
#   VON  -> vacuum solenoid ON/open
#   VOFF -> vacuum solenoid OFF/closed
#
# Pressure stream:
#   PSTART / PSTOP
#   firmware sends: "P <raw_counts>" or "PRESSURE_TIMEOUT"
#
# Vibration:
#   VIB DUR <ms>
#   VIB FREQ <hz>
#   VIB AMP <0-1>
#   VIB TRIGGER
#   A is also accepted by firmware as a shortcut trigger
#
# Slot LEDs:
#   CH<n> ON / CH<n> OFF   -> channel-number based, NOT name based.
#   The firmware's LED_MAP (slot name -> channel number) is mirrored
#   below in LED_MAP so Python can translate a slot name into the
#   correct channel before sending.
# ─────────────────────────────────────────────────────────────────────────────
_WIRE_PUMP_ON        = "PON\r\n"
_WIRE_PUMP_OFF       = "POFF\r\n"
_WIRE_VACUUM_ON      = "VON\r\n"
_WIRE_VACUUM_OFF     = "VOFF\r\n"
_WIRE_PRESSURE_START = "PSTART\r\n"
_WIRE_PRESSURE_STOP  = "PSTOP\r\n"

# ── LED slot name -> channel number (mirrors firmware's LED_MAP array) ──────
LED_MAP = {
    "A1": 0,  "A2": 1,  "A3": 2,  "A4": 3,  "A5": 4,
    "B1": 5,  "B2": 6,  "B3": 7,  "B4": 8,  "B5": 9,
    "C2": 10, "C1": 11, "C3": 12, "C4": 13, "B6": 14, "C5": 15,
    "D1": 16, "D2": 17, "D4": 18, "D3": 19, "D5": 20, "D6": 21,
    "E2": 22, "E1": 23, "E3": 24, "E4": 25, "E5": 26, "E6": 27,
    "F1": 28, "F2": 29, "F3": 30, "F4": 31, "F5": 32,
    "G1": 33, "G2": 34, "G3": 35, "G4": 36, "G5": 37,
    "H2": 38, "H1": 39, "H3": 40, "H4": 41,
    "I1": 42, "I2": 43, "I3": 44, "J1": 45, "F8": 46, "F7": 47,
    "WHITE": 48, "F9": 49, "F10": 50, "I4": 51,
    "G6": 52, "G8": 53, "G7": 54, "G9": 55, "G10": 56,
    "H5": 57, "H6": 58, "H7": 59, "H8": 60,
    "I6": 61, "I5": 62, "J3": 63, "J4": 64, "J2": 65, "F6": 66,
    "RED": 71, "YELLOW": 72, "GREEN": 73, "BLUE": 74,
}

# ── Cross-wiring correction overrides ────────────────────────────────────────
# Confirmed by bench testing: these 8 slots are physically wired to a
# DIFFERENT channel than the firmware's LED_MAP assigns them. Clicking the
# slot name on the LEFT used to light the WRONG physical LED; sending the
# channel on the RIGHT instead lights the correct one.
#
# C-row cluster (closed 6-cycle, fully confirmed):
#   C1 -> was sending ch11, correct is ch13
#   C2 -> was sending ch10, correct is ch12
#   C3 -> was sending ch12, correct is ch14
#   C4 -> was sending ch13, correct is ch15
#   C5 -> was sending ch15, correct is ch11
#   B6 -> was sending ch14, correct is ch10
#
# E-row pair (simple swap, confirmed):
#   E2 -> was sending ch22, correct is ch25
#   E4 -> was sending ch25, correct is ch22
#
# Status indicator pair (simple swap, confirmed):
#   GREEN -> was sending ch73, correct is ch70
#   BLUE  -> was sending ch74, correct is ch69
#   (RED=71, YELLOW=72, WHITE=48 confirmed correct as-is — not overridden)
#
# NOT included here: D2, F6, J1, J2 — confirmed DEAD channels (nothing
# lights up on the panel at all when clicked). This is a hardware/firmware
# issue, not a mapping issue, and cannot be fixed by sending a different
# channel number. Left as a separate hardware fix.
LED_CHANNEL_OVERRIDES = {
    "C1": 13,
    "C2": 12,
    "C3": 14,
    "C4": 15,
    "C5": 11,
    "B6": 10,
    "E2": 25,
    "E4": 22,
    "GREEN": 69,
    "BLUE": 70,
}


def _resolve_channel(slot_name: str):
    """
    Resolve a slot name to the channel number that should actually be sent.
    Override table takes priority (corrected cross-wiring); falls back to
    the firmware's own LED_MAP for everything else. Returns None if the
    name isn't recognized at all.
    """
    if slot_name in LED_CHANNEL_OVERRIDES:
        return LED_CHANNEL_OVERRIDES[slot_name]
    return LED_MAP.get(slot_name)

class ESP32Controller(QThread):
    pressure_updated = pyqtSignal(float)   # kPa
    diamond_picked   = pyqtSignal()
    diamond_released = pyqtSignal()
    connected        = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running            = False
        self._ser                = None
        self._mutex              = QMutex()
        self._had_diamond        = False
        self._simulated_pressure = 12.0

    # ── PUBLIC COMMANDS ───────────────────────────────────────────────────────

    def pump_on(self):
        """
        Start vacuum pump motor / relay, then open the solenoid so vacuum
        actually reaches the nozzle. Pump + solenoid are coupled — calling
        pump_on() always turns BOTH on together.
        """
        self._send(_WIRE_PUMP_ON)
        self.msleep(50)
        self.solenoid_open()

    def pump_off(self):
        """
        Close the solenoid first, then stop the pump relay.
        Pump + solenoid are coupled — calling pump_off() always turns
        BOTH off together.
        """
        self.solenoid_close()
        self.msleep(50)
        self._send(_WIRE_PUMP_OFF)

    def solenoid_open(self):
        """Open solenoid valve — vacuum reaches nozzle — diamond sticks."""
        self._send(_WIRE_VACUUM_ON)

    def solenoid_close(self):
        """Close solenoid valve — vacuum drops — diamond releases."""
        self._send(_WIRE_VACUUM_OFF)

    def pick(self):
        """Pick = pump_on() (pump + solenoid together)."""
        self.pump_on()

    def release(self):
        """Release = pump_off() (pump + solenoid together)."""
        self.pump_off()

    def vibrate(self, duration_ms: int = 1500):
        """
        Trigger vibration motor for duration_ms milliseconds.
        Firmware auto-stops after duration.
        """
        # Firmware clamp in updated code: 50–30000 ms
        dur = max(50, min(30000, int(duration_ms)))
        self._send(f"VIB DUR {dur}\r\n")
        self._send("VIB TRIGGER\r\n")

    def vibrate_shortcut(self):
        """Trigger vibration using firmware shortcut command A."""
        self._send("A\r\n")

    def vibration_stop(self):
        """Stop vibration immediately."""
        self._send("VIB STOP\r\n")

    def vibration_frequency(self, hz: float):
        """Set vibration sine frequency. Firmware clamps to 1–500 Hz."""
        hz = max(1.0, min(500.0, float(hz)))
        self._send(f"VIB FREQ {hz:.2f}\r\n")

    def vibration_amplitude(self, amp: float):
        """Set vibration amplitude. Firmware clamps to 0–1."""
        amp = max(0.0, min(1.0, float(amp)))
        self._send(f"VIB AMP {amp:.3f}\r\n")

    def led_on(self, slot_name: str):
        """
        Turn ON the LED for a specific slot (e.g. 'A1', 'F6').
        Resolves slot_name -> channel number (override table first, then
        firmware LED_MAP), then sends the real "CH<n> ON" protocol command.
        Unknown slot names are ignored with a console warning.
        """
        ch = _resolve_channel(slot_name)
        if ch is None:
            print(f"[ESP32] led_on: unknown slot name '{slot_name}' — ignored")
            return
        self._send(f"CH{ch} ON\r\n")

    def led_off(self, slot_name: str):
        """
        Turn OFF the LED for a specific slot.
        Same name -> channel resolution as led_on().
        """
        ch = _resolve_channel(slot_name)
        if ch is None:
            print(f"[ESP32] led_off: unknown slot name '{slot_name}' — ignored")
            return
        self._send(f"CH{ch} OFF\r\n")

    def leds_all_on(self):
        """Turn ON all slot LEDs."""
        self._send("ALL ON\r\n")

    def leds_all_off(self):
        """Turn OFF all slot LEDs."""
        self._send("ALL OFF\r\n")

    def led_brightness(self, level: int):
        """Set global LED brightness 0–65535."""
        level = max(0, min(65535, int(level)))
        self._send(f"BRIGHT {level}\r\n")

    def pressure_start(self):
        """Start continuous pressure stream from firmware."""
        self._send(_WIRE_PRESSURE_START)

    def pressure_stop(self):
        """Stop continuous pressure stream from firmware."""
        self._send(_WIRE_PRESSURE_STOP)

    def safe_off(self):
        """Force firmware safe state: pressure stream off, motor off, pump off, vacuum off, LEDs off."""
        self._send("SAFE\r\n")

    def request_pressure_once(self):
        """Request one pressure reading."""
        self._send("PRESSURE?\r\n")

    def request_status(self):
        """Request STATUS reply from firmware."""
        self._send("STATUS\r\n")

    # ── THREAD ────────────────────────────────────────────────────────────────

    def run(self):
        self._running = True
        if not HAS_SERIAL:
            self.connected.emit(False)
            self._simulate()
            return

        port = self._find_port(ESP32_PORT)
        try:
            # Open serial without holding DTR/RTS active.
            # On many ESP32 dev boards DTR/RTS toggling causes auto-reset.
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = ESP32_BAUD
            ser.bytesize = serial.EIGHTBITS
            ser.parity = serial.PARITY_NONE
            ser.stopbits = serial.STOPBITS_ONE
            ser.timeout = 0.1
            ser.write_timeout = 0.2
            ser.rtscts = False
            ser.dsrdtr = False
            ser.dtr = False
            ser.rts = False
            ser.open()
            self._ser = ser
            try:
                self._ser.setDTR(False)
                self._ser.setRTS(False)
            except Exception:
                pass

            self.connected.emit(True)
            print(f"[ESP32] Connected on {port}")

            # Give ESP32 time to finish boot once after serial open.
            self.msleep(1200)

            try:
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()
            except Exception:
                pass

            # Safe initial state for safe-boot firmware
            self.safe_off()
            self.pressure_stop()
            self.solenoid_close()
            self.pump_off()
            self.leds_all_off()
            print("[ESP32] Forced SAFE OFF after connect")

            # Start continuous pressure streaming
            self.pressure_start()
            print("[ESP32] Pressure streaming started")

            buf = ""
            while self._running:
                try:
                    raw = self._ser.read(128).decode("ascii", errors="ignore")
                    if raw:
                        buf += raw
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            self._handle_line(line.strip())
                except Exception as e:
                    print(f"[ESP32] Read error: {e}")
                self.msleep(PRESSURE_POLL_MS)

        except Exception as e:
            print(f"[ESP32] Connection failed on {port}: {e}")
            self.connected.emit(False)
            self._simulate()
        finally:
            if self._ser and self._ser.is_open:
                try:
                    self.safe_off()
                    self.pressure_stop()
                    self.vibration_stop()
                    self.solenoid_close()
                    self.pump_off()
                    self.leds_all_off()
                except Exception:
                    pass
                self._ser.close()
                print("[ESP32] Serial closed")

    def stop(self):
        self._running = False
        try:
            self.pressure_stop()
            self.vibration_stop()
            self.solenoid_close()
            self.pump_off()
        except Exception:
            pass
        self.wait(2000)

    # ── INTERNAL ──────────────────────────────────────────────────────────────

    def _find_port(self, preferred: str) -> str:
        if not HAS_SERIAL:
            return preferred
        try:
            ports = serial.tools.list_ports.comports()
            for p in ports:
                if p.device == preferred:
                    return preferred
            # Auto-detect by USB chip description
            for p in ports:
                desc = (p.description or "").lower()
                if any(k in desc for k in ["ch340", "cp210", "esp32", "uart", "prolific", "pl2303"]):
                    print(f"[ESP32] Auto-detected on {p.device}: {p.description}")
                    return p.device
            all_ports = [p.device for p in ports]
            if all_ports:
                return all_ports[0]
        except Exception:
            pass
        return preferred

    def _send(self, cmd: str):
        with QMutexLocker(self._mutex):
            if self._ser and self._ser.is_open:
                try:
                    self._ser.write(cmd.encode("ascii"))
                except Exception as e:
                    print(f"[ESP32] Send error: {e}")
            else:
                # Simulation fallback
                if cmd == _WIRE_PUMP_ON:
                    self._simulated_pressure = 68.0
                elif cmd == _WIRE_PUMP_OFF:
                    self._simulated_pressure = 12.0

    def _raw_pressure_to_kpa(self, raw_counts: float) -> float:
        """
        Convert raw pressure counts to kPa.
        Tune these two values after checking your real serial values.
        """
        HX711_SCALE  = 50000.0   # counts per kPa — tune this
        HX711_OFFSET = 800000.0  # raw value at 0 kPa — tune this
        kpa = round((raw_counts - HX711_OFFSET) / HX711_SCALE, 1)
        return max(0.0, kpa)

    def _handle_line(self, line: str):
        if not line:
            return

        # ── Pressure stream from updated firmware ─────────────────────────────
        # Firmware sends: "P 123456"
        if line.startswith("P "):
            try:
                raw_counts = float(line.split()[1])
                # print(f"[ESP32] RAW PRESSURE: {raw_counts}")   # remove after calibration
                kpa = self._raw_pressure_to_kpa(raw_counts)
                self.pressure_updated.emit(kpa)
                self._check_pick_state(kpa)
            except (ValueError, IndexError):
                pass
            return

        # One-shot pressure response from PRESSURE? command:
        # Firmware sends: "PRESSURE_RAW 123456"
        if line.startswith("PRESSURE_RAW "):
            try:
                raw_counts = float(line.split()[1])
                # print(f"[ESP32] RAW PRESSURE: {raw_counts}")
                kpa = self._raw_pressure_to_kpa(raw_counts)
                self.pressure_updated.emit(kpa)
                self._check_pick_state(kpa)
            except (ValueError, IndexError):
                pass
            return

        # STATUS line may include: ... PRESSURE_RAW=<value>
        if "PRESSURE_RAW=" in line:
            try:
                raw_text = line.split("PRESSURE_RAW=", 1)[1].split()[0]
                raw_counts = float(raw_text)
                print(f"[ESP32] STATUS: {line}")
                kpa = self._raw_pressure_to_kpa(raw_counts)
                self.pressure_updated.emit(kpa)
                self._check_pick_state(kpa)
            except (ValueError, IndexError):
                print(f"[ESP32] STATUS: {line}")
            return

        # ── Pressure timeout ─────────────────────────────────────────────────
        if line in ("PRESSURE_TIMEOUT", "ERR PRESSURE TIMEOUT", "PRESSURE_RAW TIMEOUT"):
            self.pressure_updated.emit(0.0)
            print(f"[ESP32] {line}")
            return

        # ── Firmware responses ───────────────────────────────────────────────
        if line.startswith("OK"):
            print(f"[ESP32] {line}")
            return

        if line.startswith("VAC="):
            print(f"[ESP32] STATUS: {line}")
            return

        if line.startswith("ERR"):
            print(f"[ESP32] ERROR: {line}")
            return

        if line in ("Triggered!", "TRIGGERED!", "Triggered"):
            print("[ESP32] Vibration triggered")
            return

        if line in ("Stopped", "STOPPED"):
            print("[ESP32] Vibration stopped")
            return

        # Keep unknown boot/help/debug lines visible during testing
        print(f"[ESP32] {line}")

    def _check_pick_state(self, kpa: float):
        has_diamond = kpa >= PRESSURE_THRESHOLD
        if has_diamond and not self._had_diamond:
            self.diamond_picked.emit()
        elif not has_diamond and self._had_diamond:
            self.diamond_released.emit()
        self._had_diamond = has_diamond

    def _simulate(self):
        import math
        t = 0
        print("[ESP32] Running in simulation mode")
        while self._running:
            noise = math.sin(t * 0.4) * 3.5
            kpa   = round(self._simulated_pressure + noise, 1)
            self.pressure_updated.emit(kpa)
            self._check_pick_state(kpa)
            t += 1
            self.msleep(PRESSURE_POLL_MS)