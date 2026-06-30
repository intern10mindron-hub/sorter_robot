import sys
import os
import threading
import http.server
import socketserver

# Set working directory to project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtGui import QFont
from ui.main_window import MainWindow
# ── Start local HTTP server for assets ────────────────────────────────────────
ASSETS_PORT = 18642

def start_asset_server():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))  # set root to project folder
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *a: None  # suppress console noise
    with http.server.HTTPServer(("127.0.0.1", 18642), handler) as httpd:
        httpd.serve_forever()

# Start BEFORE creating QApplication
t = threading.Thread(target=start_asset_server, daemon=True)
t.start()

# ── Qt App ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv)
    app.setApplicationName("Luminax Sorter")
    app.setOrganizationName("Mindron Technology")

    font = QFont("IBM Plex Mono", 10)
    app.setFont(font)

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec_())