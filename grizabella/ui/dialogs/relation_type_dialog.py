"""Dialog for creating and editing RelationTypeDefinitions."""

# Standard library imports
import logging  # Add logging import
from typing import TYPE_CHECKING, Any, Optional

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
from grizabella.core.exceptions import SchemaError
from grizabella.core.models import (
    ObjectTypeDefinition,
    PropertyDataType,
    PropertyDefinition,
    RelationTypeDefinition,
)
from grizabella.ui.threads.api_client_thread import ApiClientThread  # Import new thread

# from grizabella.ui.main_window import MainWindow # For connecting signals <- REMOVED FOR CIRCULAR IMPORT


if TYPE_CHECKING:
    from grizabella.ui.main_window import MainWindow


class RelationTypeDialog(QDialog):
    """Dialog for creating or editing a RelationTypeDefinition."""

    relation_type_changed = Signal()
    busy_signal = Signal(bool) # To indicate busy state

    def __init__(
        self,
        grizabella_client: "Grizabella", # Retain for now
        existing_rtd: Optional[RelationTypeDefinition] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.grizabella_client_ref = grizabella_client # Store ref, API calls via MainWindow
        self.existing_rtd = existing_rtd
        self._logger = logging.getLogger(__name__)
        self._active_load_ot_thread: Optional[ApiClientThread] = None
        self._active_rtd_operation_thread: Optional[ApiClientThread] = None


        # Client connection check is less critical here as operations go via MainWindow
        # if not self.grizabella_client_ref or not self.grizabella_client_ref._is_connected:
        #     self._logger.error("Grizabella client is not available or not connected in RelationTypeDialog.")
        #     QMessageBox.critical(self, "Initialization Error", "Grizabella client is not available or not connected.")

        if self.existing_rtd:
            self.setWindowTitle(f"Edit Relation Type: {self.existing_rtd.name}")
        else:
            self.setWindowTitle("Create New Relation Type")

        self.setMinimumWidth(750)
        self.setMinimumHeight(550)

        self._init_ui()
        self._load_object_types()  # Trigger loading object types for combos

        if self.existing_rtd:
            self._load_existing_data()
        else:
            # Add a default empty property row for new relation types
            self._add_property_row()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText(
            "Optional description for the relation type.",
        )
        self.description_edit.setFixedHeight(80)

        self.source_object_type_combo = QComboBox()
        self.target_object_type_combo = QComboBox()

        form_layout.addRow("Name:", self.name_edit)
        form_layout.addRow("Description:", self.description_edit)
        form_layout.addRow("Source Object Type:", self.source_object_type_combo)
        form_layout.addRow("Target Object Type:", self.target_object_type_combo)
        layout.addLayout(form_layout)

        properties_layout = QVBoxLayout()
        properties_label = QLabel("Properties (for the relation itself):")
        properties_layout.addWidget(properties_label)

        self.properties_table = QTableWidget()
        self.properties_table.setColumnCount(
            6,
        )  # Name, Data Type, Nullable, Indexed, Unique, Description
        self.properties_table.setHorizontalHeaderLabels(
            ["Name", "Data Type", "Nullable", "Indexed", "Unique", "Description"],
        )
        header = self.properties_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents,
        )  # Data Type
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Description
        for i in range(2, 5):  # Nullable, Indexed, Unique
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

    def _load_object_types(self) -> None:
        self.busy_signal.emit(True)
        self.source_object_type_combo.setEnabled(False)
        self.target_object_type_combo.setEnabled(False)
        self.source_object_type_combo.clear()
        self.target_object_type_combo.clear()
        self.source_object_type_combo.addItem("Loading...")
        self.target_object_type_combo.addItem("Loading...")

        if self._active_load_ot_thread and self._active_load_ot_thread.isRunning():
            self._logger.warning("Load object types already in progress.")
            self.busy_signal.emit(False) # Reset if not proceeding
            return

        # Client connection check will be handled by MainWindow
        # if not self.grizabella_client_ref or not self.grizabella_client_ref._is_connected:
        #     self._handle_object_types_load_failure("Client not available or not connected.")
        #     self.busy_signal.emit(False)
        #     return

        self._active_load_ot_thread = ApiClientThread(
            operation_name="list_object_types",
            parent=self,
        )
        main_win = self._find_main_window()
        if main_win:
            self._active_load_ot_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._handle_object_types_load_failure("Internal error: Cannot connect to API handler.")
            self._active_load_ot_thread.deleteLater()
            self._active_load_ot_thread = None
            self.busy_signal.emit(False)
            return

        self._active_load_ot_thread.result_ready.connect(self._populate_object_type_combos)
        self._active_load_ot_thread.error_occurred.connect(self._handle_object_types_load_failure)
        self._active_load_ot_thread.finished.connect(self._cleanup_load_ot_thread)
        self._active_load_ot_thread.start()

    @Slot(object) # Changed from list[str]
    def _populate_object_type_combos(self, result: Any) -> None:
        if not isinstance(result, list):
            self._handle_object_types_load_failure(f"Unexpected data type for object types: {type(result)}")
            return

        object_types: list[ObjectTypeDefinition] = result # Assuming full OTDs are returned
        object_type_names = [ot.name for ot in object_types]

        self.source_object_type_combo.clear()
        self.target_object_type_combo.clear()

        if not object_type_names:
            no_types_msg = "No object types found"
            self.source_object_type_combo.addItem(no_types_msg)
            self.target_object_type_combo.addItem(no_types_msg)
            # SetEnabled handled by cleanup
            return

        for name in object_type_names:
            self.source_object_type_combo.addItem(name)
            self.target_object_type_combo.addItem(name)
        # SetEnabled handled by cleanup

        if self.existing_rtd:
            if self.existing_rtd.source_object_type_names:
                idx_s = self.source_object_type_combo.findText(self.existing_rtd.source_object_type_names[0])
                if idx_s >= 0:
                    self.source_object_type_combo.setCurrentIndex(idx_s)
            if self.existing_rtd.target_object_type_names:
                idx_t = self.target_object_type_combo.findText(self.existing_rtd.target_object_type_names[0])
                if idx_t >= 0:
                    self.target_object_type_combo.setCurrentIndex(idx_t)

    @Slot(str)
    def _handle_object_types_load_failure(self, error_message: str) -> None:
        QMessageBox.warning(self, "Load Error", f"Could not load object types: {error_message}")
        self.source_object_type_combo.clear()
        self.target_object_type_combo.clear()
        self.source_object_type_combo.addItem("Error loading")
        self.target_object_type_combo.addItem("Error loading")
        # SetEnabled handled by cleanup

    @Slot()
    def _cleanup_load_ot_thread(self) -> None:
        self.busy_signal.emit(False)
        self.source_object_type_combo.setEnabled(True)
        self.target_object_type_combo.setEnabled(True)
        if self._active_load_ot_thread:
            self._active_load_ot_thread.deleteLater()
            self._active_load_ot_thread = None

    def _load_existing_data(self) -> None:
        if not self.existing_rtd:
            return

        self.name_edit.setText(self.existing_rtd.name)
        self.name_edit.setReadOnly(
            True,
        )  # Typically, name is not editable after creation
        self.description_edit.setPlainText(self.existing_rtd.description or "")

        # Object types will be selected by _populate_object_type_combos if data is already loaded
        # Or when it finishes loading.

        self.properties_table.setRowCount(0)
        for prop_def in self.existing_rtd.properties:
            self._add_property_row(
                prop_def, read_only_name=True,
            )  # Property names also usually not editable

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

        # PK is not relevant for relation properties
        # Column indices shift: Nullable (2), Indexed (3), Unique (4), Description (5)

        nullable_check = QCheckBox()
        nullable_check.setChecked(prop_def.is_nullable if prop_def else True)
        self.properties_table.setCellWidget(
            row_position, 2, self._center_widget_in_cell(nullable_check),
        )

        indexed_check = QCheckBox()
        indexed_check.setChecked(prop_def.is_indexed if prop_def else False)
        self.properties_table.setCellWidget(
            row_position, 3, self._center_widget_in_cell(indexed_check),
        )

        unique_check = QCheckBox()
        unique_check.setChecked(prop_def.is_unique if prop_def else False)
        self.properties_table.setCellWidget(
            row_position, 4, self._center_widget_in_cell(unique_check),
        )

        desc_edit = QLineEdit(prop_def.description if prop_def else "")
        desc_edit.setPlaceholderText("Optional property description")
        self.properties_table.setCellWidget(row_position, 5, desc_edit)

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
        if self._active_rtd_operation_thread and self._active_rtd_operation_thread.isRunning():
            QMessageBox.information(self, "In Progress", "An operation is already in progress. Please wait.")
            return

        rtd_name = self.name_edit.text().strip()
        if not rtd_name:
            QMessageBox.warning(
                self, "Input Error", "Relation Type Name cannot be empty.",
            )
            self.name_edit.setFocus()
            return

        source_ot_name = self.source_object_type_combo.currentText()
        target_ot_name = self.target_object_type_combo.currentText()

        if not source_ot_name or source_ot_name in [
            "Loading...",
            "Error loading",
            "No object types found",
        ]:
            QMessageBox.warning(
                self, "Input Error", "A valid Source Object Type must be selected.",
            )
            self.source_object_type_combo.setFocus()
            return
        if not target_ot_name or target_ot_name in [
            "Loading...",
            "Error loading",
            "No object types found",
        ]:
            QMessageBox.warning(
                self, "Input Error", "A valid Target Object Type must be selected.",
            )
            self.target_object_type_combo.setFocus()
            return

        rtd_description = self.description_edit.toPlainText().strip() or None

        properties = []
        print(f"DEBUG: RelationTypeDialog._on_accept: Starting to process {self.properties_table.rowCount()} properties.")
        for row in range(self.properties_table.rowCount()):
            print(f"DEBUG: RelationTypeDialog._on_accept: Processing property row {row + 1}")
            name_edit_widget = self.properties_table.cellWidget(row, 0)
            prop_name = (
                name_edit_widget.text().strip()
                if isinstance(name_edit_widget, QLineEdit)
                else ""
            )
            print(f"DEBUG: RelationTypeDialog._on_accept: Row {row + 1}, prop_name: '{prop_name}'")
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
            current_text: Optional[str] = None # Initialize current_text
            prop_data_type_enum_member = None
            if isinstance(data_type_combo_widget, QComboBox):
                current_text = data_type_combo_widget.currentText()
                # Find the enum member corresponding to the currentText
                for enum_member in PropertyDataType:
                    if enum_member.value == current_text:
                        prop_data_type_enum_member = enum_member
                        break

            print(f"DEBUG: RelationTypeDialog._on_accept: Row {row + 1}, prop_data_type_value from combo.currentText(): '{current_text}', Found enum member: {prop_data_type_enum_member} (type: {type(prop_data_type_enum_member)})")

            if not isinstance(prop_data_type_enum_member, PropertyDataType):
                QMessageBox.warning(
                    self, "Input Error", f"Invalid data type selected in row {row + 1}. Current text: '{current_text!s}' could not be mapped to a PropertyDataType.", # Use str(current_text) for safety in f-string
                )
                # Attempt to focus the combo box if possible
                if data_type_combo_widget:
                    data_type_combo_widget.setFocus()
                return
            prop_data_type = prop_data_type_enum_member # This is now the actual enum member
            print(f"DEBUG: RelationTypeDialog._on_accept: Row {row + 1}, validated prop_data_type: {prop_data_type}")

            # Nullable (idx 2), Indexed (idx 3), Unique (idx 4)
            nullable_check_container = self.properties_table.cellWidget(row, 2)
            is_nullable = True
            if nullable_check_container:
                nullable_check = nullable_check_container.findChild(QCheckBox)
                if nullable_check:
                    is_nullable = nullable_check.isChecked()

            indexed_check_container = self.properties_table.cellWidget(row, 3)
            is_indexed = False
            if indexed_check_container:
                indexed_check = indexed_check_container.findChild(QCheckBox)
                if indexed_check:
                    is_indexed = indexed_check.isChecked()

            unique_check_container = self.properties_table.cellWidget(row, 4)
            is_unique = False
            if unique_check_container:
                unique_check = unique_check_container.findChild(QCheckBox)
                if unique_check:
                    is_unique = unique_check.isChecked()

            desc_edit_widget = self.properties_table.cellWidget(row, 5)
            prop_description = (
                desc_edit_widget.text().strip() or None
                if isinstance(desc_edit_widget, QLineEdit)
                else None
            )

            properties.append(
                PropertyDefinition(
                    name=prop_name,
                    data_type=prop_data_type,
                    is_primary_key=False,  # PK not applicable for relation properties
                    is_nullable=is_nullable,
                    is_indexed=is_indexed,
                    is_unique=is_unique,
                    description=prop_description,
                ),
            )
            print(f"DEBUG: RelationTypeDialog._on_accept: Row {row + 1}, PropertyDefinition created: {properties[-1]}")

        # Unlike Object Types, Relation Types can exist without properties.
        print(f"DEBUG: RelationTypeDialog._on_accept: All properties processed. Collected properties list: {properties}")

        try:
            print(f"DEBUG: RelationTypeDialog._on_accept: Attempting to create RelationTypeDefinition model with name='{rtd_name}', desc='{rtd_description}', src='{source_ot_name}', tgt='{target_ot_name}', props_count={len(properties)}")
            rtd_model = RelationTypeDefinition(
                name=rtd_name,
                description=rtd_description,
                source_object_type_names=[source_ot_name],  # Model expects a list
                target_object_type_names=[target_ot_name],  # Model expects a list
                properties=properties,
            )
            print(f"DEBUG: RelationTypeDialog._on_accept: RelationTypeDefinition model created successfully: {rtd_model}")
        except ValueError as e:  # Pydantic validation error
            print(f"DEBUG: RelationTypeDialog._on_accept: Pydantic ValueError during RelationTypeDefinition creation: {e!s}")
            QMessageBox.critical(
                self,
                "Validation Error",
                f"Error creating relation type definition: {e!s}",
            )
            return

        # Client connection check will be handled by MainWindow
        # if not self.grizabella_client_ref: # Check api_worker as well
        #     QMessageBox.critical(self, "Error", "Grizabella client reference not available.")
        #     self._reset_buttons_and_worker_state() # Ensure buttons are reset
        #     return

        self._set_buttons_enabled(False)
        self.busy_signal.emit(True)

        operation_name = "update_relation_type" if self.existing_rtd else "create_relation_type"
        if self.existing_rtd: # Ensure name is not changed on update
            rtd_model.name = self.existing_rtd.name

        self._active_rtd_operation_thread = ApiClientThread(
            operation_name, # operation_name variable passed positionally
            rtd_model,      # rtd_model for *args
            parent=self,
        )
        main_win = self._find_main_window()
        if main_win:
            self._active_rtd_operation_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._handle_operation_failure(operation_name, "Internal error: Cannot connect to API handler.")
            self._active_rtd_operation_thread.deleteLater()
            self._active_rtd_operation_thread = None
            self._reset_buttons_and_worker_state()
            return

        if self.existing_rtd:
            self._active_rtd_operation_thread.result_ready.connect(self._handle_update_success)
            self._active_rtd_operation_thread.error_occurred.connect(lambda err: self._handle_operation_failure("update_relation_type", err))
        else:
            self._active_rtd_operation_thread.result_ready.connect(self._handle_creation_success)
            self._active_rtd_operation_thread.error_occurred.connect(lambda err: self._handle_operation_failure("create_relation_type", err))

        self._active_rtd_operation_thread.finished.connect(self._reset_buttons_and_worker_state)
        self._active_rtd_operation_thread.start()


    def _set_buttons_enabled(self, enabled: bool) -> None:
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setEnabled(enabled)
        cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setEnabled(enabled)

    @Slot(object) # Result is Any
    def _handle_creation_success(self, result: Any) -> None:
        # create_relation_type API returns None. Success is implicit.
        # result here might be the input model if ApiClientThread passes it.
        created_rtd_name = self.name_edit.text().strip() # Get name from form
        QMessageBox.information(self, "Success", f"Relation Type '{created_rtd_name}' created successfully.")
        self.relation_type_changed.emit()
        self.accept()

    @Slot(object) # Result is Any
    def _handle_update_success(self, result: Any) -> None:
        # update_relation_type API might return the updated model or None.
        # For now, assume success means the operation completed.
        updated_rtd_name = self.name_edit.text().strip() # Name is read-only in edit mode
        QMessageBox.information(self, "Success", f"Relation Type '{updated_rtd_name}' updated successfully.")
        self.relation_type_changed.emit()
        self.accept()

    @Slot(str, str) # operation_name, error_message
    def _handle_operation_failure(self, operation_name: str, error_message: str) -> None:
        title = "Operation Failed"
        if operation_name == "create_relation_type":
            title = "Creation Failed"
        elif operation_name == "update_relation_type":
            title = "Update Failed"
        QMessageBox.critical(self, title, error_message)
        # Buttons reset by _reset_buttons_and_worker_state via 'finished'

    def _reset_buttons_and_worker_state(self) -> None:
        self._set_buttons_enabled(True)
        self.busy_signal.emit(False)
        if self._active_rtd_operation_thread:
            self._active_rtd_operation_thread.deleteLater()
            self._active_rtd_operation_thread = None
        if self._active_load_ot_thread: # Also ensure load thread is cleaned up if it was active
            self._active_load_ot_thread.deleteLater()
            self._active_load_ot_thread = None

    def _find_main_window(self) -> Optional["MainWindow"]:
        """Helper to find the MainWindow instance."""
        # Import MainWindow locally to break circular dependency
        # This import is already guarded by TYPE_CHECKING at the top for type hints
        # For runtime, it needs to be available here.
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
        self._logger.warning("Could not find MainWindow instance for RelationTypeDialog.")
        return None

    def closeEvent(self, event: Any) -> None:
        self._logger.debug(f"RelationTypeDialog closeEvent triggered for {self}.")
        threads_to_manage = [
            self._active_load_ot_thread,
            self._active_rtd_operation_thread,
        ]
        for thread_instance in threads_to_manage:
            if thread_instance and thread_instance.isRunning():
                thread_instance.quit()
                if not thread_instance.wait(500):
                    thread_instance.terminate()
                    thread_instance.wait()
        self._active_load_ot_thread = None
        self._active_rtd_operation_thread = None
        super().closeEvent(event)


# For testing the dialog independently
if __name__ == "__main__":
    import sys  # Standard library

    from PySide6.QtWidgets import QApplication  # Third-party

    # First-party imports
    from grizabella.api.client import Grizabella
    from grizabella.core.models import RelationInstance

    # Mock GrizabellaClient for standalone testing
    class MockGrizabellaClient(Grizabella):  # Inherit from Grizabella
        """Mock Grizabella client for testing RelationTypeDialog."""

        def __init__(self) -> None:
            # Call super init as Grizabella requires db_name_or_path
            super().__init__(db_name_or_path="mock_relation_type_dialog_db")

        def create_relation_type(
            self, relation_type_def: RelationTypeDefinition,
        ) -> None:  # Corrected signature
            # import time; time.sleep(1) # Simulate delay
            if relation_type_def.name == "ErrorTest":
                msg = "This is a mock schema error for ErrorTest."
                raise SchemaError(msg)

        # update_relation_type is not in the base Grizabella client.
        # The RelationApiWorker uses getattr, so it will correctly report
        # "Client does not support 'update_relation_type'" if this mock is used for edit testing.

        def get_relation(
            self, from_object_id: str, to_object_id: str, relation_type_name: str,
        ) -> list[RelationInstance]: # Match base class signature
            """Mocked get_relation."""
            return [] # Return empty list

        def delete_relation( # Corrected signature
            self, relation_type_name: str, relation_id: str, # Match Grizabella.delete_relation
        ) -> bool:
            """Mocked delete_relation."""
            return False

        def list_object_types(self) -> list[ObjectTypeDefinition]:
            # import time; time.sleep(0.5)
            return [
                ObjectTypeDefinition(
                    name="Document",
                    properties=[
                        PropertyDefinition(
                            name="title", data_type=PropertyDataType.TEXT,
                        ),
                    ],
                ),
                ObjectTypeDefinition(
                    name="Person",
                    properties=[
                        PropertyDefinition(name="name", data_type=PropertyDataType.TEXT),
                    ],
                ),
                ObjectTypeDefinition(
                    name="Event",
                    properties=[
                        PropertyDefinition(
                            name="date", data_type=PropertyDataType.DATETIME,
                        ),
                    ],
                ),
            ]

    app = QApplication(sys.argv)
    mock_client = MockGrizabellaClient()

    dialog_new = RelationTypeDialog(grizabella_client=mock_client)
    if dialog_new.exec():
        pass
    else:
        pass

    # Test with existing data (simplified, edit not fully implemented)
    # existing_prop = PropertyDefinition(name="role", data_type=PropertyDataType.TEXT)
    # mock_rtd = RelationTypeDefinition(
    #     name="HAS_AUTHOR",
    #     description="Indicates authorship.",
    #     source_object_type_names=["Document"],
    #     target_object_type_names=["Person"],
    #     properties=[existing_prop]
    # )
    # dialog_edit = RelationTypeDialog(grizabella_client=mock_client, existing_rtd=mock_rtd)
    # if dialog_edit.exec():
    #     print("Dialog accepted (Edit RTD).")
    # else:
    #     print("Dialog cancelled (Edit RTD).")

    sys.exit(app.exec())
