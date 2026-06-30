# """
# tray_detector_dialog.py
# =======================
# Wraps tray_camera_tester.MainWindow as a floating child window.
# Zero changes to tray_camera_tester.py.

# Place in project root (same folder as tray_camera_tester.py).
# """
# import math
# from PyQt5.QtWidgets import QMainWindow
# from PyQt5.QtCore import pyqtSignal, Qt

# from tray_camera_tester import MainWindow as _TrayMainWindow


# class TrayDetectorDialog(_TrayMainWindow):
#     """
#     Subclasses the tray tester MainWindow directly.
#     Adds diamond_selected signal — emitted when operator clicks an isolated diamond.
#     Everything else (UI, camera, calibration) works exactly as in tray_camera_tester.
#     """
#     diamond_selected = pyqtSignal(float, float)

#     def __init__(self, parent=None):
#         super().__init__()   # builds full tray tester UI unchanged

#         # Make it a proper child window — stays on top of Luminax, not in taskbar
#         if parent is not None:
#             self.setParent(parent, Qt.Window)

#         self.setWindowTitle("Tray Diamond Detector — Mindron Technology")
#         self.setWindowFlags(
#             Qt.Window |
#             Qt.WindowMinimizeButtonHint |
#             Qt.WindowMaximizeButtonHint |
#             Qt.WindowCloseButtonHint
#         )

#         # Patch LiveTab._try_pick_at to also emit diamond_selected
#         live = self.live_tab
#         original_try_pick = live._try_pick_at

#         def patched_try_pick(fx, fy):
#             CLICK_RADIUS = 25
#             best_d    = None
#             best_dist = float("inf")
#             for d in live._last_diamonds:
#                 if d.is_cluster:
#                     continue
#                 dist = math.hypot(d.px - fx, d.py - fy)
#                 if dist < CLICK_RADIUS and dist < best_dist:
#                     best_dist = dist
#                     best_d    = d
#             if best_d is not None:
#                 # ← Send robot coordinates back to Luminax workflow
#                 self.diamond_selected.emit(best_d.robot_x, best_d.robot_y)
#             # Also run original (moves robot inside tray tester if connected)
#             original_try_pick(fx, fy)

#         live._try_pick_at = patched_try_pick

#     def closeEvent(self, event):
#         try:
#             self.cam_thread.stop()
#         except Exception:
#             pass
#         event.accept()


"""
tray_detector_dialog.py
=======================
Wraps tray_camera_tester.MainWindow as a floating child window.
Accepts the main app's RobotTCP instance so clicking a diamond
moves the real robot and the status indicator reflects the real
connection state — no separate connect/disconnect UI needed.
"""
import math
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import pyqtSignal, Qt

from tray_camera_tester import MainWindow as _TrayMainWindow


class TrayDetectorDialog(_TrayMainWindow):
    """
    Subclasses the tray tester MainWindow directly.
    Adds diamond_selected signal — emitted when operator clicks an isolated diamond.
    Pass the main app robot via set_robot(robot) after construction.
    """
    diamond_selected = pyqtSignal(float, float)
    closed           = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__()   # builds full tray tester UI unchanged

        # Make it a proper child window
        if parent is not None:
            self.setParent(parent, Qt.Window)

        self.setWindowTitle("Tray Diamond Detector — Mindron Technology")
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )

        # Patch LiveTab._try_pick_at to also emit diamond_selected to Luminax
        live = self.live_tab
        original_try_pick = live._try_pick_at

        def patched_try_pick(fx, fy):
            """
            Calls the fixed _try_pick_at (which now handles the click properly),
            then also emits diamond_selected so camera_panel gets the signal.
            """
            # Find the diamond first (same logic, to get coordinates for the signal)
            CLICK_RADIUS = 30
            best_d    = None
            best_dist = float("inf")
            for d in live._last_diamonds:
                if d.is_cluster:
                    continue
                dist = math.hypot(d.px - fx, d.py - fy)
                if dist < CLICK_RADIUS and dist < best_dist:
                    best_dist = dist
                    best_d    = d

            if best_d is not None:
                # Emit to camera_panel → main_window → workflow
                self.diamond_selected.emit(best_d.robot_x, best_d.robot_y)
                # Also run real pick logic (standalone robot move if no workflow)
                original_try_pick(fx, fy)

        live._try_pick_at = patched_try_pick

    def set_robot(self, robot):
        """
        Pass the main app's connected RobotTCP instance here.
        Call this right after opening the dialog:

            self._tray_dlg = TrayDetectorDialog(parent=self)
            self._tray_dlg.set_robot(self._robot)   # ← add this line
            self._tray_dlg.show()

        After this:
        - Status indicator shows real connection state immediately
        - Clicking an isolated diamond moves the real robot
        - Internal TCP poll is stopped (no conflict with main app)
        """
        self.live_tab.set_robot(robot)
        
    def set_workflow(self, workflow):     # ← ADD THIS
        self.live_tab.set_workflow(workflow)

    def closeEvent(self, event):
        try:
            self.cam_thread.stop()
        except Exception:
            pass
        event.accept()
        self.closed.emit()          # ← notify camera_panel regardless of how dialog closes