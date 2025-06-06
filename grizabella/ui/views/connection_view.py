"""QWidget for managing Grizabella database connections."""
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

from grizabella.api.client import Grizabella
from grizabella.core.exceptions import ConfigurationError, DatabaseError


class ConnectionView(QWidget):
    """A QWidget for managing database connections.
    Allows users to specify a database path, browse for a directory,
    and attempt to connect to a Grizabella database.
    """

    # Signals
    connection_status_updated = Signal(str)
    grizabella_client_updated = Signal(object) # Can be Grizabella client or None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.grizabella_client_internal = None # Internal reference
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Database Path Input
        path_layout = QHBoxLayout()
        path_label = QLabel("Database Path/Name:")
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText(
            "e.g., 'default', 'my_db', or /path/to/db",
        )
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_directory)

        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_button)
        layout.addLayout(path_layout)

        # Connect Button
        connect_button = QPushButton("Connect")
        connect_button.clicked.connect(self._connect_to_database)
        layout.addWidget(connect_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

    def _browse_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Database Directory",
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if directory:
            self.path_input.setText(directory)

    def _connect_to_database(self) -> None:
        db_path = self.path_input.text().strip()
        if not db_path:
            QMessageBox.warning(self, "Connection Error",
                                "Database path cannot be empty.")
            self.connection_status_updated.emit(
                "Connection Error: Database path cannot be empty.",
            )
            return

        try:
            self.grizabella_client_internal = Grizabella(db_name_or_path=db_path)
            self.grizabella_client_internal.connect()
            self.grizabella_client_updated.emit(self.grizabella_client_internal)

            status_message = f"Successfully connected to database: {db_path}"
            QMessageBox.information(self, "Connection Successful", status_message)
            self.connection_status_updated.emit(status_message)

        except ConfigurationError as e:
            error_message = f"Configuration Error: {e}"
            QMessageBox.critical(self, "Connection Failed", error_message)
            self.connection_status_updated.emit(error_message)
            self.grizabella_client_internal = None
            self.grizabella_client_updated.emit(None)
        except DatabaseError as e:
            error_message = f"Database Error: {e}"
            QMessageBox.critical(self, "Connection Failed", error_message)
            self.connection_status_updated.emit(error_message)
            self.grizabella_client_internal = None
            self.grizabella_client_updated.emit(None)
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            QMessageBox.critical(self, "Connection Failed", error_message)
            self.connection_status_updated.emit(error_message)
            self.grizabella_client_internal = None
            self.grizabella_client_updated.emit(None)

    def get_grizabella_client(self):
        """Returns the internally stored Grizabella client instance."""
        return self.grizabella_client_internal

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    class MockMainWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Mock Parent for ConnectionView")
            layout = QVBoxLayout(self)
            self.connection_view = ConnectionView(self) # Parent is self
            layout.addWidget(self.connection_view)

            self.status_label = QLabel("Status: Ready")
            layout.addWidget(self.status_label)

            self.g_client_from_signal = None

            # Connect signals from ConnectionView
            self.connection_view.connection_status_updated.connect(
                self.update_status_label,
            )
            self.connection_view.grizabella_client_updated.connect(
                self.handle_client_update,
            )

        def update_status_label(self, message) -> None:
            self.status_label.setText(f"Status: {message}")

        def handle_client_update(self, client) -> None:
            self.g_client_from_signal = client
            if client:
                pass
            else:
                pass

    main_win = MockMainWindow()
    main_win.show()
    sys.exit(app.exec())
