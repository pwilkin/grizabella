"""Dialog for creating and editing ObjectTypeDefinitions."""

from typing import TYPE_CHECKING, Any, Optional  # Added TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, Slot  # QThread removed
from PySide6.QtWidgets import (
    QApplication,  # Added
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from grizabella.api.client import Grizabella
from grizabella.core.models import (
    ObjectTypeDefinition,
    PropertyDataType,
    PropertyDefinition,
)
from grizabella.ui.threads.api_client_thread import ApiClientThread  # Import new thread

# from grizabella.ui.main_window import MainWindow # For connecting signals <- REMOVED FOR CIRCULAR IMPORT

if TYPE_CHECKING:
    from grizabella.ui.main_window import MainWindow


class ObjectTypeDialog(QDialog):
    """Dialog for creating or editing an ObjectTypeDefinition."""

    object_type_changed = Signal() # Emitted when an OTD is successfully created/updated
    busy_signal = Signal(bool) # To indicate busy state to parent or MainWindow

    def __init__(
        self,
        grizabella_client: "Grizabella", # Retain for now, might be used by logic not directly calling API
        existing_otd: Optional[ObjectTypeDefinition] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.grizabella_client_ref = grizabella_client # Keep ref if needed, but API calls go via MainWindow
        self.existing_otd = existing_otd
        self._active_api_thread: Optional[ApiClientThread] = None # Renamed

        if self.existing_otd:
            self.setWindowTitle(f"Edit Object Type: {self.existing_otd.name}")
        else:
            self.setWindowTitle("Create New Object Type")

        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        self._init_ui()
        if self.existing_otd:
            self._load_existing_data()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText(
            "Optional description for the object type.",
        )
        self.description_edit.setFixedHeight(80)

        form_layout.addRow("Name:", self.name_edit)
        form_layout.addRow("Description:", self.description_edit)
        layout.addLayout(form_layout)

        properties_layout = QVBoxLayout()
        properties_label = QLabel("Properties:")
        properties_layout.addWidget(properties_label)

        self.properties_table = QTableWidget()
        self.properties_table.setColumnCount(7)
        self.properties_table.setHorizontalHeaderLabels(
            ["Name", "Data Type", "PK", "Nullable", "Indexed", "Unique", "Description"],
        )
        header = self.properties_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        for i in range(2, 6):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        properties_layout.addWidget(self.properties_table)

        prop_buttons_layout = QHBoxLayout()
        self.add_prop_button = QPushButton("Add Property")
        self.remove_prop_button = QPushButton("Remove Selected Property")
        prop_buttons_layout.addWidget(self.add_prop_button)
        prop_buttons_layout.addWidget(self.remove_prop_button)
        prop_buttons_layout.addStretch()
        properties_layout.addLayout(prop_buttons_layout)

        layout.addLayout(properties_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        layout.addWidget(self.button_box)

        self.add_prop_button.clicked.connect(self._add_property_row)
        self.remove_prop_button.clicked.connect(self._remove_property_row)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)

        if not self.existing_otd:
            self._add_property_row()

    def _load_existing_data(self) -> None:
        if not self.existing_otd:
            return

        self.name_edit.setText(self.existing_otd.name)
        self.name_edit.setReadOnly(True)
        self.description_edit.setPlainText(self.existing_otd.description or "")

        self.properties_table.setRowCount(0)
        for prop_def in self.existing_otd.properties:
            self._add_property_row(prop_def, read_only_name=True)

    def _add_property_row(
        self,
        prop_def: Optional[PropertyDefinition] = None,
        read_only_name: bool = False,
    ) -> None:
        row_position = self.properties_table.rowCount()
        self.properties_table.insertRow(row_position)

        name_edit = QLineEdit(prop_def.name if prop_def else "")
        if read_only_name:
            name_edit.setReadOnly(True)
        self.properties_table.setCellWidget(row_position, 0, name_edit)

        combo_data_type = QComboBox()
        for data_type in PropertyDataType:
            combo_data_type.addItem(data_type.value, data_type)
        if prop_def:
            index = combo_data_type.findData(prop_def.data_type)
            if index >= 0:
                combo_data_type.setCurrentIndex(index)
        self.properties_table.setCellWidget(row_position, 1, combo_data_type)

        pk_check = QCheckBox()
        pk_check.setChecked(prop_def.is_primary_key if prop_def else False)
        self.properties_table.setCellWidget(
            row_position, 2, self._center_widget_in_cell(pk_check),
        )

        nullable_check = QCheckBox()
        nullable_check.setChecked(prop_def.is_nullable if prop_def else True)
        self.properties_table.setCellWidget(
            row_position, 3, self._center_widget_in_cell(nullable_check),
        )

        indexed_check = QCheckBox()
        indexed_check.setChecked(prop_def.is_indexed if prop_def else False)
        self.properties_table.setCellWidget(
            row_position, 4, self._center_widget_in_cell(indexed_check),
        )

        unique_check = QCheckBox()
        unique_check.setChecked(prop_def.is_unique if prop_def else False)
        self.properties_table.setCellWidget(
            row_position, 5, self._center_widget_in_cell(unique_check),
        )

        desc_edit = QLineEdit(prop_def.description if prop_def else "")
        desc_edit.setPlaceholderText("Optional property description")
        self.properties_table.setCellWidget(row_position, 6, desc_edit)

    def _center_widget_in_cell(self, widget: QWidget) -> QWidget:
        cell_container_widget = QWidget()
        cell_layout = QHBoxLayout(cell_container_widget)
        cell_layout.addWidget(widget)
        cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        return cell_container_widget

    def _remove_property_row(self) -> None:
        current_row = self.properties_table.currentRow()
        if current_row >= 0:
            self.properties_table.removeRow(current_row)
        else:
            QMessageBox.warning(
                self, "Warning", "Please select a property row to remove.",
            )

    def _on_accept(self) -> None:
        otd_name = self.name_edit.text().strip()
        if not otd_name:
            QMessageBox.warning(
                self, "Input Error", "Object Type Name cannot be empty.",
            )
            self.name_edit.setFocus()
            return

        otd_description = self.description_edit.toPlainText().strip() or None

        properties = []
        primary_key_count = 0
        for row in range(self.properties_table.rowCount()):
            name_edit_widget = self.properties_table.cellWidget(row, 0)
            prop_name = ""
            if isinstance(name_edit_widget, QLineEdit):
                prop_name = name_edit_widget.text().strip()
            else:
                QMessageBox.critical(
                    self,
                    "Internal Error",
                    f"Row {row+1}: Name widget is not a QLineEdit.",
                )
                return

            if not prop_name:
                QMessageBox.warning(
                    self,
                    "Input Error",
                    f"Property name in row {row + 1} cannot be empty.",
                )
                if name_edit_widget:
                    name_edit_widget.setFocus()
                return

            data_type_combo_widget = self.properties_table.cellWidget(row, 1)
            prop_data_type = None
            if isinstance(data_type_combo_widget, QComboBox):
                prop_data_type = data_type_combo_widget.currentData()
            else:
                QMessageBox.critical(
                    self,
                    "Internal Error",
                    f"Row {row+1}: Data type widget is not a QComboBox.",
                )
                return

            pk_check_container = self.properties_table.cellWidget(row, 2)
            is_pk = False
            if pk_check_container:
                pk_check = pk_check_container.findChild(QCheckBox)
                if pk_check:
                    is_pk = pk_check.isChecked()
            if is_pk:
                primary_key_count += 1

            nullable_check_container = self.properties_table.cellWidget(row, 3)
            is_nullable = True
            if nullable_check_container:
                nullable_check = nullable_check_container.findChild(QCheckBox)
                if nullable_check:
                    is_nullable = nullable_check.isChecked()

            indexed_check_container = self.properties_table.cellWidget(row, 4)
            is_indexed = False
            if indexed_check_container:
                indexed_check = indexed_check_container.findChild(QCheckBox)
                if indexed_check:
                    is_indexed = indexed_check.isChecked()

            unique_check_container = self.properties_table.cellWidget(row, 5)
            is_unique = False
            if unique_check_container:
                unique_check = unique_check_container.findChild(QCheckBox)
                if unique_check:
                    is_unique = unique_check.isChecked()

            desc_edit_widget = self.properties_table.cellWidget(row, 6)
            prop_description = None
            if isinstance(desc_edit_widget, QLineEdit):
                prop_description = desc_edit_widget.text().strip() or None
            elif desc_edit_widget is not None:
                QMessageBox.critical(
                    self,
                    "Internal Error",
                    f"Row {row+1}: Description widget is not a QLineEdit.",
                )
                return

            properties.append(
                PropertyDefinition(
                    name=prop_name,
                    data_type=prop_data_type,
                    is_primary_key=is_pk,
                    is_nullable=is_nullable,
                    is_indexed=is_indexed,
                    is_unique=is_unique,
                    description=prop_description,
                ),
            )

        if not properties:
            QMessageBox.warning(
                self, "Input Error", "An Object Type must have at least one property.",
            )
            return

        if primary_key_count > 1:
            QMessageBox.warning(
                self,
                "Input Error",
                "An Object Type can have at most one primary key property.",
            )
            return

        try:
            otd_model = ObjectTypeDefinition(
                name=otd_name, description=otd_description, properties=properties,
            )
        except ValueError as e:
            QMessageBox.critical(
                self,
                "Validation Error",
                f"Error creating object type definition: {e!s}",
            )
            return

        if self.grizabella_client_ref:
            ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
            if ok_button:
                ok_button.setEnabled(False)
            cancel_button = self.button_box.button(
                QDialogButtonBox.StandardButton.Cancel,
            )
            if cancel_button:
                cancel_button.setEnabled(False)

            if self.existing_otd:
                QMessageBox.information(
                    self,
                    "Not Implemented",
                    "Editing object types is not yet fully implemented.",
                )
                self._reset_buttons()
                return

            # Client connection check will be handled by MainWindow's API handler
            # if not self.grizabella_client_ref or not self.grizabella_client_ref._is_connected:
            #     QMessageBox.critical(self, "Client Error", "Client not available or not connected.")
            #     self._reset_buttons() # Ensure buttons are reset
            #     return

            if self._active_api_thread and self._active_api_thread.isRunning():
                QMessageBox.information(self, "Busy", "An operation is already in progress.")
                return # Don't start a new one

            self._active_api_thread = ApiClientThread(
                "create_object_type", # Hardcoded for now as edit is not implemented
                otd_model,            # otd_model for *args
                parent=self,
            )
            main_win = self._find_main_window()
            if main_win:
                self._active_api_thread.apiRequestReady.connect(main_win.handleApiRequest)
            else:
                self._handle_creation_failure("Internal error: Cannot connect to API handler.")
                self._active_api_thread.deleteLater()
                self._active_api_thread = None
                self._reset_buttons() # Ensure buttons are reset
                return

            self._active_api_thread.result_ready.connect(self._handle_creation_success)
            self._active_api_thread.error_occurred.connect(self._handle_creation_failure)
            self._active_api_thread.finished.connect(self._reset_buttons) # Connect finished for cleanup
            self._active_api_thread.start()
            self.busy_signal.emit(True) # Indicate busy
        else:
            QMessageBox.critical(self, "Error", "Grizabella client reference not available.")
            self._reset_buttons()

    @Slot(object) # Changed from ObjectTypeDefinition
    def _handle_creation_success(self, result: Any) -> None:
        # The 'create_object_type' API returns None. The success is implicit.
        # The 'result' here will be the otd_model we sent if ApiClientThread passes it through.
        # For now, let's assume result is the original otd_model or similar.
        if isinstance(result, ObjectTypeDefinition) or hasattr(result, "name"):
            created_otd_name = result.name
        else: # If API returns None or something else unexpected
            created_otd_name = self.name_edit.text().strip() # Use name from form as fallback

        QMessageBox.information(
            self, "Success", f"Object Type '{created_otd_name}' operation successful.",
        )
        self.object_type_changed.emit()
        self.accept() # Close dialog on success

    @Slot(str)
    def _handle_creation_failure(self, error_message: str) -> None:
        QMessageBox.critical(self, "Operation Failed", error_message)
        # Buttons are reset by _reset_buttons via the 'finished' signal

    def _reset_buttons(self) -> None:
        self.busy_signal.emit(False) # Reset busy state
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setEnabled(True)
        cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setEnabled(True)

        if self._active_api_thread:
            self._active_api_thread.deleteLater()
            self._active_api_thread = None

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
        if isinstance(app_instance, QApplication):
            active_window = app_instance.activeWindow()
            if isinstance(active_window, MainWindow):
                return active_window
        # self._logger.warning("Could not find MainWindow instance.") # Logger not defined here
        print("ObjectTypeDialog: Could not find MainWindow instance.")
        return None

    def closeEvent(self, event: Any) -> None: # Added type hint
        if self._active_api_thread and self._active_api_thread.isRunning():
            # Handle active thread if dialog is closed prematurely
            self._active_api_thread.quit()
            if not self._active_api_thread.wait(500):
                self._active_api_thread.terminate()
                self._active_api_thread.wait()
        self._active_api_thread = None
        super().closeEvent(event)


# For testing the dialog independently
if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    # Import Grizabella for the mock client
    from grizabella.api.client import Grizabella

    # Define a mock for direct execution
    class MockGrizabellaClient(Grizabella):  # Renamed and inherits
        def __init__(self) -> None:
            # Call super init as Grizabella requires db_name_or_path
            super().__init__(db_name_or_path="mock_object_type_dialog_db")

        def create_object_type(
            self, object_type_def: ObjectTypeDefinition,
        ) -> None:  # Corrected signature
            # import time; time.sleep(1) # Simulate delay
            # if object_type_def.name == "ErrorTest":
            #     raise SchemaError("This is a mock schema error for ErrorTest.")
            pass
            # Base method returns None

        def list_object_types(
            self,
        ) -> list[ObjectTypeDefinition]:  # Corrected return type
            return []

        # Add other methods Grizabella might expect if the dialog calls them,
        # e.g., update_object_type if edit functionality were fully implemented.
        def update_object_type(self, object_type_def: ObjectTypeDefinition) -> None:
            pass
            # Base method likely returns None or the updated object

    app = QApplication(sys.argv)
    mock_client = MockGrizabellaClient()  # Use the renamed mock

    dialog_new = ObjectTypeDialog(grizabella_client=mock_client)
    if dialog_new.exec():
        pass
    else:
        pass

    existing_prop1 = PropertyDefinition(
        name="id",
        data_type=PropertyDataType.UUID,
        is_primary_key=True,
        is_nullable=False,
    )
    existing_prop2 = PropertyDefinition(name="content", data_type=PropertyDataType.TEXT)
    mock_otd = ObjectTypeDefinition(
        name="MyDocument",
        description="A test document type.",
        properties=[existing_prop1, existing_prop2],
    )
    dialog_edit = ObjectTypeDialog(grizabella_client=mock_client, existing_otd=mock_otd)
    if dialog_edit.exec():
        pass
    else:
        pass

    sys.exit(app.exec())
