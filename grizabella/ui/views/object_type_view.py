"""View for managing ObjectTypeDefinitions."""
import logging  # Add logging
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import Qt, Signal, Slot  # Removed QThread
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,  # Added
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from grizabella.api.client import Grizabella
from grizabella.core.exceptions import SchemaError
from grizabella.core.models import ObjectTypeDefinition, PropertyDataType, PropertyDefinition
from grizabella.ui.dialogs.object_type_dialog import ObjectTypeDialog
from grizabella.ui.threads.api_client_thread import ApiClientThread  # Import new thread

# from grizabella.ui.main_window import MainWindow # For connecting signals <- REMOVED FOR CIRCULAR IMPORT

if TYPE_CHECKING:
    from grizabella.ui.main_window import MainWindow


class ObjectTypeView(QWidget):
    """QWidget for displaying and managing ObjectTypeDefinitions."""

    busy_signal = Signal(bool)

    def __init__(self, grizabella_client: Optional["Grizabella"] = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.grizabella_client = grizabella_client # Will be set by MainWindow
        self._logger = logging.getLogger(__name__)
        self.current_otds: list[ObjectTypeDefinition] = []
        self._active_list_ot_thread: Optional[ApiClientThread] = None
        self._active_delete_ot_thread: Optional[ApiClientThread] = None
        self._otd_name_for_delete_success: Optional[str] = None


        self._init_ui()
        self.set_client(self.grizabella_client) # Initial call

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        left_layout = QVBoxLayout()

        self.ot_list_widget = QListWidget()
        self.ot_list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self.ot_list_widget.currentItemChanged.connect(self._on_ot_selected)
        left_layout.addWidget(QLabel("Object Types:"))
        left_layout.addWidget(self.ot_list_widget)

        action_buttons_layout = QHBoxLayout()
        self.new_ot_button = QPushButton("New Object Type")
        self.edit_ot_button = QPushButton("Edit Selected")
        self.delete_ot_button = QPushButton("Delete Selected")
        self.refresh_button = QPushButton("Refresh List")

        self.new_ot_button.clicked.connect(self._create_new_otd)
        self.edit_ot_button.clicked.connect(self._edit_selected_otd)
        self.delete_ot_button.clicked.connect(self._delete_selected_otd)
        self.refresh_button.clicked.connect(self.refresh_object_types)

        action_buttons_layout.addWidget(self.new_ot_button)
        action_buttons_layout.addWidget(self.edit_ot_button)
        action_buttons_layout.addWidget(self.delete_ot_button)
        action_buttons_layout.addStretch()
        action_buttons_layout.addWidget(self.refresh_button)
        left_layout.addLayout(action_buttons_layout)

        details_groupbox = QGroupBox("Object Type Details")
        details_layout = QVBoxLayout()

        form_layout = QFormLayout()
        self.name_display = QLineEdit()
        self.name_display.setReadOnly(True)
        self.description_display = QTextEdit()
        self.description_display.setReadOnly(True)
        self.description_display.setFixedHeight(80)

        form_layout.addRow("Name:", self.name_display)
        form_layout.addRow("Description:", self.description_display)
        details_layout.addLayout(form_layout)

        details_layout.addWidget(QLabel("Properties:"))
        self.properties_table = QTableWidget()
        self.properties_table.setColumnCount(7)
        self.properties_table.setHorizontalHeaderLabels([
            "Name", "Data Type", "PK", "Nullable", "Indexed", "Unique",
            "Description",
        ])
        header = self.properties_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(2, 6):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.properties_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        details_layout.addWidget(self.properties_table)

        details_groupbox.setLayout(details_layout)

        main_layout.addLayout(left_layout, 1)
        main_layout.addWidget(details_groupbox, 2)

        self._clear_details()
        self._update_action_buttons_state()

    def set_client(self, client: Optional["Grizabella"]) -> None:
        self.grizabella_client = client
        if self.grizabella_client:
            self.refresh_object_types()
            self.new_ot_button.setEnabled(True)
            self.refresh_button.setEnabled(True)
        else:
            self.ot_list_widget.clear()
            self.current_otds = []
            self._clear_details()
            self.new_ot_button.setEnabled(False)
            self.refresh_button.setEnabled(False)
        self._update_action_buttons_state()

    def refresh_object_types(self) -> None:
        if not self.grizabella_client:
            QMessageBox.warning(self, "Client Not Available",
                                "Grizabella client is not connected.")
            return

        self.busy_signal.emit(True)
        self.ot_list_widget.setEnabled(False)
        self.refresh_button.setEnabled(False)

        if self._active_list_ot_thread and self._active_list_ot_thread.isRunning():
            self._logger.warning("List object types already in progress.")
            self.busy_signal.emit(False) # Reset busy if we don't proceed
            self.ot_list_widget.setEnabled(True)
            self.refresh_button.setEnabled(True)
            return

        if not self.grizabella_client or not self.grizabella_client._is_connected:
             QMessageBox.critical(self, "Client Error", "Client not available or not connected.")
             self.busy_signal.emit(False)
             self.ot_list_widget.setEnabled(True)
             self.refresh_button.setEnabled(True)
             return

        self._active_list_ot_thread = ApiClientThread(
            operation_name="list_object_types",
            parent=self,
        )
        main_win = self._find_main_window()
        if main_win:
            self._active_list_ot_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._handle_api_error("list_object_types", "Internal error: Cannot connect to API handler.")
            self._active_list_ot_thread.deleteLater()
            self._active_list_ot_thread = None
            # busy_signal and buttons re-enabled by _handle_api_error via _on_list_worker_finished
            return

        self._active_list_ot_thread.result_ready.connect(self._populate_ot_list)
        self._active_list_ot_thread.error_occurred.connect(
            lambda err_msg: self._handle_api_error("list_object_types", err_msg),
        )
        self._active_list_ot_thread.finished.connect(self._on_list_worker_finished)
        self._active_list_ot_thread.start()

    @Slot(object) # Changed from list
    def _populate_ot_list(self, result: Any) -> None:
        if not isinstance(result, list):
            self._handle_api_error("list_object_types", f"Unexpected data type for object types: {type(result)}")
            return

        otds: list[ObjectTypeDefinition] = result
        self.current_otds = sorted(otds, key=lambda otd_item: otd_item.name.lower())
        self.ot_list_widget.clear()
        if not self.current_otds:
            self.ot_list_widget.addItem(QListWidgetItem("No object types defined."))
            # self.ot_list_widget.setEnabled(False) # Handled by finished
            self._clear_details()
        else:
            for otd_item in self.current_otds:
                item = QListWidgetItem(otd_item.name)
                item.setData(Qt.ItemDataRole.UserRole, otd_item)
                self.ot_list_widget.addItem(item)
            # self.ot_list_widget.setEnabled(True) # Handled by finished
            if self.ot_list_widget.count() > 0:
                self.ot_list_widget.setCurrentRow(0)
        self._update_action_buttons_state()


    @Slot()
    def _on_list_worker_finished(self) -> None:
        self.busy_signal.emit(False)
        self.ot_list_widget.setEnabled(True if self.current_otds else False)
        self.refresh_button.setEnabled(True)
        if self._active_list_ot_thread:
            self._active_list_ot_thread.deleteLater()
            self._active_list_ot_thread = None

    def _on_ot_selected(self, current_item: Optional[QListWidgetItem],
                        _previous_item: Optional[QListWidgetItem]) -> None: # Marked unused
        if current_item:
            otd: Optional[ObjectTypeDefinition] = current_item.data(
                Qt.ItemDataRole.UserRole,
            )
            if otd and isinstance(otd, ObjectTypeDefinition):
                self._display_ot_details(otd)
            else:
                self._clear_details()
        else:
            self._clear_details()
        self._update_action_buttons_state()

    def _display_ot_details(self, otd: ObjectTypeDefinition) -> None:
        self.name_display.setText(otd.name)
        self.description_display.setPlainText(otd.description or "")

        self.properties_table.setRowCount(0)
        for prop_def in otd.properties:
            row_position = self.properties_table.rowCount()
            self.properties_table.insertRow(row_position)

            self.properties_table.setItem(row_position, 0,
                                          QTableWidgetItem(prop_def.name))
            self.properties_table.setItem(row_position, 1,
                                          QTableWidgetItem(prop_def.data_type.value))

            pk_item = QTableWidgetItem("Yes" if prop_def.is_primary_key else "No")
            pk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.properties_table.setItem(row_position, 2, pk_item)

            nullable_item = QTableWidgetItem("Yes" if prop_def.is_nullable else "No")
            nullable_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.properties_table.setItem(row_position, 3, nullable_item)

            indexed_item = QTableWidgetItem("Yes" if prop_def.is_indexed else "No")
            indexed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.properties_table.setItem(row_position, 4, indexed_item)

            unique_item = QTableWidgetItem("Yes" if prop_def.is_unique else "No")
            unique_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.properties_table.setItem(row_position, 5, unique_item)

            self.properties_table.setItem(
                row_position, 6, QTableWidgetItem(prop_def.description or ""),
            )
        self.properties_table.resizeColumnsToContents()

    def _clear_details(self) -> None:
        self.name_display.clear()
        self.description_display.clear()
        self.properties_table.setRowCount(0)

    def _update_action_buttons_state(self) -> None:
        has_client = self.grizabella_client is not None
        selected_otd_item = self.ot_list_widget.currentItem()
        is_valid_otd_selected = False
        if selected_otd_item:
            data = selected_otd_item.data(Qt.ItemDataRole.UserRole)
            is_valid_otd_selected = isinstance(data, ObjectTypeDefinition)

        self.new_ot_button.setEnabled(has_client)
        self.edit_ot_button.setEnabled(has_client and is_valid_otd_selected)
        self.delete_ot_button.setEnabled(has_client and is_valid_otd_selected)
        self.refresh_button.setEnabled(has_client)

    def _create_new_otd(self) -> None:
        if not self.grizabella_client:
            QMessageBox.critical(self, "Error", "Grizabella client not available.")
            return

        dialog = ObjectTypeDialog(self.grizabella_client, parent=self)
        dialog.object_type_changed.connect(self.refresh_object_types)
        dialog.exec()

    def _edit_selected_otd(self) -> None:
        if not self.grizabella_client:
            QMessageBox.critical(self, "Error", "Grizabella client not available.")
            return

        selected_item = self.ot_list_widget.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "No Selection",
                                "Please select an Object Type to edit.")
            return

        otd_to_edit: Optional[ObjectTypeDefinition] = selected_item.data(
            Qt.ItemDataRole.UserRole,
        )
        if not isinstance(otd_to_edit, ObjectTypeDefinition):
            QMessageBox.warning(self, "Invalid Selection",
                                "The selected item is not a valid Object Type.")
            return

        dialog = ObjectTypeDialog(self.grizabella_client,
                                  existing_otd=otd_to_edit, parent=self)
        dialog.object_type_changed.connect(self.refresh_object_types)
        if dialog.exec():
            QMessageBox.information(
                self, "Edit",
                f"Edit dialog for '{otd_to_edit.name}' was opened. "
                "Full edit functionality pending.",
            )
        else:
            QMessageBox.information(
                self, "Edit",
                f"Edit dialog for '{otd_to_edit.name}' was cancelled.",
            )

    def _delete_selected_otd(self) -> None:
        if not self.grizabella_client:
            QMessageBox.critical(self, "Error", "Grizabella client not available.")
            return

        selected_item = self.ot_list_widget.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "No Selection",
                                "Please select an Object Type to delete.")
            return

        otd_to_delete: Optional[ObjectTypeDefinition] = selected_item.data(
            Qt.ItemDataRole.UserRole,
        )
        if not isinstance(otd_to_delete, ObjectTypeDefinition):
            QMessageBox.warning(self, "Invalid Selection",
                                "The selected item is not a valid Object Type.")
            return

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle("Confirm Delete")
        msg_box.setText(
            f"Are you sure you want to delete Object Type '{otd_to_delete.name}'?",
        )
        msg_box.setInformativeText("This action cannot be undone.")
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        reply = msg_box.exec()


        if reply == QMessageBox.StandardButton.Yes:
            self.busy_signal.emit(True)
            self.delete_ot_button.setEnabled(False)
            self._otd_name_for_delete_success = otd_to_delete.name

            if self._active_delete_ot_thread and self._active_delete_ot_thread.isRunning():
                QMessageBox.information(self, "In Progress", "Another delete operation is already in progress.")
                self.busy_signal.emit(False)
                self.delete_ot_button.setEnabled(True) # Re-enable if not proceeding
                return

            if not self.grizabella_client or not self.grizabella_client._is_connected:
                QMessageBox.critical(self, "Client Error", "Client not available or not connected.")
                self.busy_signal.emit(False)
                self.delete_ot_button.setEnabled(True)
                return

            self._active_delete_ot_thread = ApiClientThread(
                "delete_object_type", # operation_name passed positionally
                otd_to_delete.name,   # type_name for *args
                parent=self,
            )
            main_win = self._find_main_window()
            if main_win:
                self._active_delete_ot_thread.apiRequestReady.connect(main_win.handleApiRequest)
            else:
                self._handle_api_error("delete_object_type", "Internal error: Cannot connect to API handler.")
                self._active_delete_ot_thread.deleteLater()
                self._active_delete_ot_thread = None
                # busy_signal and button re-enabled by _handle_api_error via _on_delete_worker_finished
                return

            self._active_delete_ot_thread.result_ready.connect(self._handle_delete_success)
            self._active_delete_ot_thread.error_occurred.connect(
                lambda err_msg: self._handle_api_error("delete_object_type", err_msg),
            )
            self._active_delete_ot_thread.finished.connect(self._on_delete_worker_finished)
            self._active_delete_ot_thread.start()

    @Slot(object) # Changed from str
    def _handle_delete_success(self, result: Any) -> None:
        # result from delete_object_type is typically None or a confirmation, not the name.
        # We use the stored name.
        otd_name = self._otd_name_for_delete_success
        if result is None or (isinstance(result, bool) and result): # Grizabella API might return None or True
            QMessageBox.information(self, "Success", f"Object Type '{otd_name}' deleted successfully.")
            self.refresh_object_types()
        else:
            self._handle_api_error("delete_object_type", f"Failed to delete '{otd_name}'. API returned: {result}")
        self._otd_name_for_delete_success = None


    @Slot(str, str) # Added operation_name to distinguish errors
    def _handle_api_error(self, operation_name: str, error_message: str) -> None:
        title = "API Error"
        if operation_name == "list_object_types":
            title = "Error Listing Object Types"
            self.ot_list_widget.clear()
            self.ot_list_widget.addItem(QListWidgetItem("Error loading object types."))
            self.current_otds = []
            self._clear_details()
        elif operation_name == "delete_object_type":
            title = "Delete Failed"

        QMessageBox.critical(self, title, error_message)
        self._update_action_buttons_state()
        # Cleanup is handled by the 'finished' signal of the respective thread.
        # Ensure busy signal is reset if it was set for this operation.
        # This might need more granular tracking if multiple operations can be "busy"
        self.busy_signal.emit(False)


    @Slot()
    def _on_delete_worker_finished(self) -> None:
        self.busy_signal.emit(False)
        self._update_action_buttons_state() # Re-enables delete button if appropriate
        if self._active_delete_ot_thread:
            self._active_delete_ot_thread.deleteLater()
            self._active_delete_ot_thread = None
        self._otd_name_for_delete_success = None

    def _find_main_window(self) -> Optional["MainWindow"]:
        """Helper to find the MainWindow instance."""
        # Import MainWindow locally to break circular dependency
        from grizabella.ui.main_window import MainWindow

        parent = self.parent()
        while parent is not None:
            if isinstance(parent, MainWindow):
                return parent
            parent = parent.parent()

        app_instance = QApplication.instance()
        if isinstance(app_instance, QApplication): # Ensure it's a QApplication
            active_window = app_instance.activeWindow()
            if isinstance(active_window, MainWindow):
                return active_window
        self._logger.warning("Could not find MainWindow instance for ObjectTypeView.")
        return None

    def closeEvent(self, event: Any) -> None:
        self._logger.debug(f"ObjectTypeView closeEvent triggered for {self}.")
        threads_to_manage = [
            ("_active_list_ot_thread", self._active_list_ot_thread),
            ("_active_delete_ot_thread", self._active_delete_ot_thread),
        ]
        for name, thread_instance in threads_to_manage:
            if thread_instance and thread_instance.isRunning():
                self._logger.info(f"ObjectTypeView: Worker thread '{name}' ({thread_instance}) is running. Attempting to quit/wait.")
                thread_instance.quit()
                if not thread_instance.wait(500):
                    self._logger.warning(f"ObjectTypeView: Worker thread '{name}' ({thread_instance}) did not finish. Terminating.")
                    thread_instance.terminate()
                    thread_instance.wait() # Wait for termination
                else:
                    self._logger.info(f"ObjectTypeView: Worker thread '{name}' ({thread_instance}) finished.")
            elif thread_instance: # Exists but not running
                thread_instance.deleteLater()

        self._active_list_ot_thread = None
        self._active_delete_ot_thread = None
        self._logger.info(f"ObjectTypeView: About to call super().closeEvent() for {self}.")
        super().closeEvent(event)
        self._logger.info(f"ObjectTypeView: Returned from super().closeEvent() for {self}.")


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    # Import the actual client here for the mock to inherit from
    from grizabella.api.client import Grizabella

    # Define MockGrizabellaClientForTest directly in the __main__ block
    class MockGrizabellaClientForTest(Grizabella): # Inherit from Grizabella
        """Mock Grizabella client for standalone testing."""

        _otds_data: dict[str, ObjectTypeDefinition] = {}
        _seq: int = 0

        def __init__(self, db_name_or_path: str = "mock", create_if_not_exists: bool = False) -> None: # Match base
            # Minimal init for mock.
            # super().__init__(db_name_or_path, create_if_not_exists) # Avoid actual DB connection
            self._is_connected = True # Pretend to be connected

            prop1 = PropertyDefinition(
                name="id", data_type=PropertyDataType.UUID, is_primary_key=True,
            )
            prop2 = PropertyDefinition(
                name="title", data_type=PropertyDataType.TEXT, is_nullable=False,
            )
            prop3 = PropertyDefinition(
                name="pages", data_type=PropertyDataType.INTEGER,
            )
            otd1 = ObjectTypeDefinition(
                name="Book", description="A literary work.",
                properties=[prop1, prop2, prop3],
            )
            self._otds_data[otd1.name] = otd1

            prop_a = PropertyDefinition(
                name="name", data_type=PropertyDataType.TEXT, is_primary_key=True,
            )
            prop_b = PropertyDefinition(
                name="age", data_type=PropertyDataType.INTEGER,
            )
            otd2 = ObjectTypeDefinition(
                name="Author", description="Writer of books.",
                properties=[prop_a, prop_b],
            )
            self._otds_data[otd2.name] = otd2

        def list_object_types(self) -> list[ObjectTypeDefinition]:
            return list(self._otds_data.values())

        def create_object_type(self, object_type_def: ObjectTypeDefinition) -> None: # Match base
            if object_type_def.name in self._otds_data:
                msg = f"Object type '{object_type_def.name}' already exists."
                raise SchemaError(
                    msg,
                )
            self._otds_data[object_type_def.name] = object_type_def
            # Original Grizabella.create_object_type returns None

        def delete_object_type(self, type_name: str) -> None: # Match base
            if type_name not in self._otds_data:
                msg = f"Object type '{type_name}' not found."
                raise SchemaError(msg)
            del self._otds_data[type_name]

        # Add other necessary overrides if ObjectTypeView calls them,
        # ensuring their signatures match Grizabella client methods.
        # For example, if connect/close are called:
        def connect(self) -> None:
            self._is_connected = True

        def close(self) -> None:
            self._is_connected = False

    app = QApplication(sys.argv)
    mock_client_instance = MockGrizabellaClientForTest()
    main_view_instance = ObjectTypeView(grizabella_client=mock_client_instance)
    main_view_instance.setWindowTitle("Grizabella Object Type Management")
    main_view_instance.resize(900, 600)
    main_view_instance.show()
    sys.exit(app.exec())

