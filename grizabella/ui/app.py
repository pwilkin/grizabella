"""Grizabella UI Application.

This module contains the main entry point for launching the Grizabella
PySide6 user interface.
"""
import logging  # Add logging import
import sys

from PySide6.QtWidgets import QApplication
from qt_material import apply_stylesheet

from .main_window import MainWindow


def main() -> None:
    """Main function to initialize and run the Grizabella UI application.
    It sets up basic logging, applies the Material Design theme (light_blue.xml),
    creates the main window, connects signals for graceful shutdown,
    and starts the application event loop.
    """
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s") # Add basic config
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme="light_blue.xml")
    main_win = MainWindow()

    # Connect aboutToQuit signal for graceful shutdown
    app.aboutToQuit.connect(main_win.shutdown_threads_and_client)

    main_win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
