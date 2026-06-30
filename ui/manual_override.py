from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QLabel, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal

BG_CARD   = "#212840"
BG_DEEP   = "#141824"
BORDER_LO = "#253050"
C_DIM     = "#A9B4BE"
C_GREEN   = "#00C8A0"
C_BLUE    = "#38bdf8"
C_AMBER   = "#fb923c"
C_RED     = "#f87171"

class ManualOverride(QWidget):
    home_requested = pyqtSignal()
    tray_requested = pyqtSignal()
    scale_requested = pyqtSignal()
    pump_on_requested = pyqtSignal()
    pump_off_requested = pyqtSignal()
    vibrate_requested = pyqtSignal()
    emergency_stop_requested = pyqtSignal()
    emergency_reset_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._emergency_active = False
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # QUICK POSITIONS
        quick_title = QLabel("QUICK POSITIONS")
        quick_title.setStyleSheet(f"color: {C_DIM}; font-size: 9px; letter-spacing: 2px;")
        main_layout.addWidget(quick_title)
        
        pos_layout = QHBoxLayout()
        pos_layout.setSpacing(8)
        
        self.btn_home = QPushButton("HOME")
        self.btn_tray = QPushButton("TRAY")
        self.btn_scale = QPushButton("SCALE")
        
        for btn in [self.btn_home, self.btn_tray, self.btn_scale]:
            btn.setFixedHeight(32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {BG_DEEP};
                    border: 1px solid {C_BLUE};
                    border-radius: 4px;
                    color: {C_BLUE};
                    font-size: 10px;
                }}
                QPushButton:hover {{ background: #1a2a3a; }}
                QPushButton:disabled {{ border-color: {C_DIM}; color: {C_DIM}; }}
            """)
            pos_layout.addWidget(btn)
        
        pos_layout.addStretch()
        main_layout.addLayout(pos_layout)
        
        self.btn_home.clicked.connect(self.home_requested.emit)
        self.btn_tray.clicked.connect(self.tray_requested.emit)
        self.btn_scale.clicked.connect(self.scale_requested.emit)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background: {BORDER_LO}; max-height: 1px;")
        main_layout.addWidget(line)
        
        # VACUUM & VIBRATION
        vac_title = QLabel("VACUUM & VIBRATION")
        vac_title.setStyleSheet(f"color: {C_DIM}; font-size: 9px; letter-spacing: 2px;")
        main_layout.addWidget(vac_title)
        
        pump_layout = QHBoxLayout()
        pump_layout.setSpacing(8)
        
        self.btn_pump_on = QPushButton("PUMP ON")
        self.btn_pump_off = QPushButton("PUMP OFF")
        
        self.btn_pump_on.setStyleSheet(f"""
            QPushButton {{
                background: {BG_DEEP};
                border: 1px solid {C_GREEN};
                border-radius: 4px;
                color: {C_GREEN};
                font-size: 10px;
                padding: 6px;
            }}
            QPushButton:hover {{ background: #1a2a1a; }}
        """)
        
        self.btn_pump_off.setStyleSheet(f"""
            QPushButton {{
                background: {BG_DEEP};
                border: 1px solid {C_DIM};
                border-radius: 4px;
                color: {C_DIM};
                font-size: 10px;
                padding: 6px;
            }}
            QPushButton:hover {{ border-color: {C_RED}; color: {C_RED}; }}
        """)
        
        pump_layout.addWidget(self.btn_pump_on)
        pump_layout.addWidget(self.btn_pump_off)
        pump_layout.addStretch()
        main_layout.addLayout(pump_layout)
        self.btn_vibrate = QPushButton("VIBRATE")
        self.btn_vibrate.setFixedHeight(32)
        self.btn_vibrate.setStyleSheet(f"""
            QPushButton {{
                background: {BG_DEEP};
                border: 1px solid {C_AMBER};
                border-radius: 4px;
                color: {C_AMBER};
                font-size: 10px;
            }}

            QPushButton:hover {{ background: #2a1f00; }}
        """)
        main_layout.addWidget(self.btn_vibrate)
        
        self.btn_pump_on.clicked.connect(self.pump_on_requested.emit)
        self.btn_pump_off.clicked.connect(self.pump_off_requested.emit)
        self.btn_vibrate.clicked.connect(self.vibrate_requested.emit)
        
        # Pressure display
        self.pressure_label = QLabel("Pressure: -- kPa")
        self.pressure_label.setStyleSheet(f"color: {C_DIM}; font-size: 10px;")
        main_layout.addWidget(self.pressure_label)
        
        # Separator
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet(f"background: {BORDER_LO}; max-height: 1px;")
        main_layout.addWidget(line2)
        
        # EMERGENCY
        emergency_title = QLabel("EMERGENCY")
        emergency_title.setStyleSheet(f"color: {C_DIM}; font-size: 9px; letter-spacing: 2px;")
        main_layout.addWidget(emergency_title)
        
        self.btn_estop = QPushButton("EMERGENCY STOP")
        self.btn_estop.setFixedHeight(40)
        self.btn_estop.setStyleSheet(f"""
            QPushButton {{
                background: #3a0000;
                border: 2px solid {C_RED};
                border-radius: 4px;
                color: {C_RED};
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #5a0000;
                border-color: #ff8888;
                color: #ff8888;
            }}
        """)
        main_layout.addWidget(self.btn_estop)
        
        self.btn_reset = QPushButton("RESET")
        self.btn_reset.setFixedHeight(32)
        self.btn_reset.setStyleSheet(f"""
            QPushButton {{
                background: {BG_DEEP};
                border: 1px solid {C_BLUE};
                border-radius: 4px;
                color: {C_BLUE};
                font-size: 10px;
            }}
            QPushButton:hover {{ background: #1a2a3a; }}
        """)
        main_layout.addWidget(self.btn_reset)
        
        # FIXED: Changed from emergency_stop to _on_emergency_stop
        self.btn_estop.clicked.connect(self._on_emergency_stop)
        self.btn_reset.clicked.connect(self._on_emergency_reset)
        
        # Status
        self.status_label = QLabel("● READY")
        self.status_label.setStyleSheet(f"color: {C_GREEN}; font-size: 9px; padding: 5px;")
        main_layout.addWidget(self.status_label)
        main_layout.addStretch()
    
    def _on_emergency_stop(self):
        """Emergency stop - stops all operations"""
        self._emergency_active = True
        # Disable all controls
        for widget in self.findChildren(QWidget):
            widget.setEnabled(False)
        # Re-enable only emergency related controls
        self.btn_estop.setEnabled(True)
        self.btn_reset.setEnabled(True)
        # Update status
        self.status_label.setText("● EMERGENCY STOP ACTIVE")
        self.status_label.setStyleSheet(f"color: {C_RED}; font-size: 9px; padding: 5px;")
        # Emit signal
        self.emergency_stop_requested.emit()
        print("EMERGENCY STOP ACTIVATED")
    
    def _on_emergency_reset(self):
        """Reset after emergency stop"""
        self._emergency_active = False
        # Re-enable all controls
        for widget in self.findChildren(QWidget):
            widget.setEnabled(True)
        # Update status
        self.status_label.setText("● READY")
        self.status_label.setStyleSheet(f"color: {C_GREEN}; font-size: 9px; padding: 5px;")
        # Emit signal
        self.emergency_reset_requested.emit()
        print("EMERGENCY RESET - System ready")
    
    def update_pressure(self, pressure_kpa: float):
        """Update pressure display"""
        if pressure_kpa is not None:
            self.pressure_label.setText(f"Pressure: {pressure_kpa:.1f} kPa")
            # Color code based on pressure
            if pressure_kpa < -80:
                self.pressure_label.setStyleSheet(f"color: {C_GREEN}; font-size: 10px;")
            elif pressure_kpa < -40:
                self.pressure_label.setStyleSheet(f"color: {C_AMBER}; font-size: 10px;")
            else:
                self.pressure_label.setStyleSheet(f"color: {C_DIM}; font-size: 10px;")
        else:
            self.pressure_label.setText("Pressure: -- kPa")
            self.pressure_label.setStyleSheet(f"color: {C_DIM}; font-size: 10px;")