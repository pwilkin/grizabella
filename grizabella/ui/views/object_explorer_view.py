"""QWidget for exploring Object Instances in Grizabella."""
# Standard library imports
import logging  # Added
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union  # Added TYPE_CHECKING

from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from grizabella.api.client import Grizabella
from grizabella.core.models import (
    ObjectInstance,
    ObjectTypeDefinition,
    PropertyDataType,
    PropertyDefinition,
    RelationInstance,
)
from grizabella.ui.dialogs.object_instance_dialog import ObjectInstanceDialog

# First-party imports
from grizabella.ui.models.object_instance_table_model import ObjectInstanceTableModel
from grizabella.ui.threads.api_client_thread import ApiClientThread  # Import new thread

# from grizabella.ui.main_window import MainWindow # For connecting signals <- REMOVED FOR CIRCULAR IMPORT

if TYPE_CHECKING:
    from grizabella.ui.main_window import MainWindow


class ObjectExplorerView(QWidget):
    """View for exploring and managing Object Instances."""

    busy_signal = Signal(bool)
    # refresh_instances_signal = Signal(str) # This can be handled internally now

    def __init__(
        self,
        grizabella_client: Optional[Grizabella],  # Allow None
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._logger = logging.getLogger(__name__)
        self.grizabella_client = grizabella_client # Will be set by MainWindow
        self.current_object_type: Optional[ObjectTypeDefinition] = None
        self.object_instance_model: Optional[ObjectInstanceTableModel] = None

        self._active_list_types_thread: Optional[ApiClientThread] = None
        self._active_list_instances_thread: Optional[ApiClientThread] = None
        self._active_delete_object_thread: Optional[ApiClientThread] = None
        self._object_id_for_delete_success: Optional[str] = None
        self._object_type_name_for_delete_success: Optional[str] = None


        self.setWindowTitle("Object Explorer")
        self._init_ui()
        self._connect_signals()
        if self.grizabella_client:
            self.refresh_view_data()
        else:
            self._handle_no_client()

    def set_client(self, client: Optional[Grizabella]) -> None:
        """Sets or updates the Grizabella client for the view."""
        self.grizabella_client = client
        if client:
            self.refresh_view_data()
        else:
            self._handle_no_client()

    def _handle_no_client(self) -> None:
        """Handles UI state when no client is available."""
        self.object_type_combo.clear()
        self.object_type_combo.setEnabled(False)
        if self.object_instance_model:
            self.object_instance_model.clear_data()
        self.current_object_type = None
        self.setWindowTitle("Object Explorer (No Client)")
        self._update_action_buttons_state()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        selection_layout = QHBoxLayout()
        self.object_type_label = QLabel("Object Type:")
        self.object_type_combo = QComboBox()
        self.object_type_combo.setPlaceholderText("Select Object Type")
        selection_layout.addWidget(self.object_type_label)
        selection_layout.addWidget(self.object_type_combo)
        selection_layout.addStretch()
        layout.addLayout(selection_layout)

        self.instances_table_view = QTableView()
        self.instances_table_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.instances_table_view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self.instances_table_view.horizontalHeader().setStretchLastSection(True)
        self.instances_table_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive,
        )
        self.instances_table_view.setSortingEnabled(True)

        # Initialize the model here and set it to the view
        # Pass an empty list of property definitions initially
        self.object_instance_model = ObjectInstanceTableModel(property_definitions=[], parent=self)
        self.instances_table_view.setModel(self.object_instance_model)

        layout.addWidget(self.instances_table_view)

        buttons_layout = QHBoxLayout()
        self.new_object_button = QPushButton("New Object")
        self.view_edit_button = QPushButton("View/Edit Selected")
        self.delete_button = QPushButton("Delete Selected")
        self.refresh_button = QPushButton("Refresh List")
        buttons_layout.addWidget(self.new_object_button)
        buttons_layout.addWidget(self.view_edit_button)
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.refresh_button)
        layout.addLayout(buttons_layout)
        self._update_action_buttons_state()

    def _connect_signals(self) -> None:
        self.object_type_combo.currentIndexChanged.connect(
            self._on_object_type_selected,
        )
        self.new_object_button.clicked.connect(self._on_new_object)
        self.view_edit_button.clicked.connect(self._on_view_edit_object)
        self.delete_button.clicked.connect(self._on_delete_object)
        self.refresh_button.clicked.connect(self._on_refresh_list)
        selection_model = self.instances_table_view.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(
                self._on_instance_selection_changed,
            )
        # self.refresh_instances_signal.connect(self._load_object_instances) # Direct call now
        self.busy_signal.connect(self._handle_busy_state)

    @Slot(bool)
    def _handle_busy_state(self, busy: bool) -> None:
        self.setEnabled(not busy)

    @Slot()
    def _cleanup_list_types_thread(self) -> None:
        self.busy_signal.emit(False)
        self.object_type_combo.setEnabled(True)
        if self._active_list_types_thread:
            self._active_list_types_thread.deleteLater()
            self._active_list_types_thread = None

    @Slot(object) # Changed from list
    def _on_object_types_loaded_success(self, result: Any) -> None:
        # self.busy_signal.emit(False) # Handled by cleanup
        # self.object_type_combo.setEnabled(True) # Handled by cleanup
        if not isinstance(result, list):
            self._on_object_types_load_error(f"Unexpected data type for object types: {type(result)}")
            return

        object_types: list[ObjectTypeDefinition] = result
        self.object_type_combo.clear()
        if object_types:
            self.object_type_combo.addItem("Select Object Type", userData=None)
            for obj_type in sorted(object_types, key=lambda x: x.name):
                self.object_type_combo.addItem(obj_type.name, userData=obj_type)
            # self.object_type_combo.setEnabled(True) # Done in cleanup
        else:
            self.object_type_combo.addItem("No object types found", userData=None)
            # self.object_type_combo.setEnabled(False) # Done in cleanup
            QMessageBox.information(
                self, "Object Types", "No object types found in the database.",
            )
        self._update_action_buttons_state()

    @Slot(str)
    def _on_object_types_load_error(self, error_message: str) -> None:
        # self.busy_signal.emit(False) # Handled by cleanup
        # self.object_type_combo.setEnabled(False) # Handled by cleanup
        QMessageBox.critical(self, "Error Loading Object Types", error_message)
        self._update_action_buttons_state()

    def _load_object_types(self) -> None:
        if not self.grizabella_client:
            self._on_object_types_load_error("Client not available.")
            return

        self.busy_signal.emit(True)
        self.object_type_combo.setEnabled(False)

        if self._active_list_types_thread and self._active_list_types_thread.isRunning():
            self._logger.warning("Load object types already in progress.")
            self.busy_signal.emit(False) # Reset busy if we don't proceed
            self.object_type_combo.setEnabled(True)
            return

        if not self.grizabella_client._is_connected: # Check after client existence
            self._on_object_types_load_error("Client not connected.")
            self.busy_signal.emit(False)
            self.object_type_combo.setEnabled(True)
            return

        self._active_list_types_thread = ApiClientThread(
            operation_name="list_object_types",
            parent=self,
        )
        main_win = self._find_main_window()
        if main_win:
            self._active_list_types_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._on_object_types_load_error("Internal error: Cannot connect to API handler.")
            self._active_list_types_thread.deleteLater()
            self._active_list_types_thread = None
            return # busy_signal and combo enabled by error handler via cleanup

        self._active_list_types_thread.result_ready.connect(self._on_object_types_loaded_success)
        self._active_list_types_thread.error_occurred.connect(self._on_object_types_load_error)
        self._active_list_types_thread.finished.connect(self._cleanup_list_types_thread)
        self._active_list_types_thread.start()

    @Slot(int)
    def _on_object_type_selected(self, index: int) -> None:
        selected_data = self.object_type_combo.itemData(index)
        if isinstance(selected_data, ObjectTypeDefinition):
            self.current_object_type = selected_data
            self.setWindowTitle(f"Object Explorer - {self.current_object_type.name}")
            self._load_object_instances(self.current_object_type.name) # Pass name
        else:
            self.current_object_type = None
            if self.object_instance_model:
                self.object_instance_model.clear_data()
            self.setWindowTitle("Object Explorer")
        self._update_action_buttons_state()

    # @Slot(str) # No longer a slot, direct call
    def _load_object_instances(self, object_type_name: str) -> None:
        if not self.current_object_type or not self.grizabella_client:
            self._on_object_instances_load_error(
                "Cannot load instances: No object type selected or client not available.",
            )
            return
        self.busy_signal.emit(True)
        self.instances_table_view.setEnabled(False)

        property_defs_for_table = self._get_properties_for_table(
            self.current_object_type.properties,
        )

        # Model is already set in _init_ui, just update its definitions and data
        if self.object_instance_model:
            self.object_instance_model.update_property_definitions(
                property_defs_for_table,
            )
        else:
            # This case should ideally not happen if _init_ui always creates the model
            self._logger.error("ObjectInstanceTableModel is None in _load_object_instances. This should not happen.")
            self.object_instance_model = ObjectInstanceTableModel(property_defs_for_table, parent=self)
            self.instances_table_view.setModel(self.object_instance_model)

        if self._active_list_instances_thread and self._active_list_instances_thread.isRunning():
            self._logger.warning("Load object instances already in progress.")
            self.busy_signal.emit(False)
            self.instances_table_view.setEnabled(True)
            return

        if not self.grizabella_client._is_connected: # Check after client existence
            self._on_object_instances_load_error("Client not connected.")
            self.busy_signal.emit(False)
            self.instances_table_view.setEnabled(True)
            return

        self._active_list_instances_thread = ApiClientThread(
            operation_name="find_objects",
            type_name=object_type_name,
            filter_criteria={},
            parent=self,
        )
        main_win = self._find_main_window()
        if main_win:
            self._active_list_instances_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._on_object_instances_load_error("Internal error: Cannot connect to API handler.")
            self._active_list_instances_thread.deleteLater()
            self._active_list_instances_thread = None
            return

        self._active_list_instances_thread.result_ready.connect(self._on_object_instances_loaded_success)
        self._active_list_instances_thread.error_occurred.connect(self._on_object_instances_load_error)
        self._active_list_instances_thread.finished.connect(self._cleanup_list_instances_thread)
        self._active_list_instances_thread.start()


    def _get_properties_for_table(
        self, all_properties: list[PropertyDefinition],
    ) -> list[PropertyDefinition]:
        props_to_display: list[PropertyDefinition] = []
        # 'id' is not in properties list, it's on MemoryInstance
        id_prop = next((p for p in all_properties if p.name == "id"), None)

        # Create a mock PropertyDefinition for 'id' for table display
        if not id_prop:  # If 'id' is not explicitly in properties, add a representation
            # This assumes 'id' is always a UUID string for display purposes.
            # The actual 'id' comes from ObjectInstance.id
            mock_id_prop = PropertyDefinition(
                name="id",
                data_type=PropertyDataType.UUID,
                is_nullable=False,
                description="Instance ID",
            )
            props_to_display.append(mock_id_prop)

        count = 0
        simple_types = [
            PropertyDataType.TEXT,
            PropertyDataType.INTEGER,
            PropertyDataType.FLOAT,
            PropertyDataType.BOOLEAN,
            PropertyDataType.UUID,
            PropertyDataType.DATETIME,
        ]
        for prop_def in sorted(all_properties, key=lambda p: p.name):
            if prop_def.name == "id":  # Already handled or will be by mock
                continue
            if prop_def.data_type in simple_types and prop_def not in props_to_display:
                props_to_display.append(prop_def)
                count += 1
            if count >= 4:  # Show id + up to 4 other simple properties
                break
        return props_to_display

    @Slot(object) # Changed from list
    def _on_object_instances_loaded_success(self, result: Any) -> None:
        # self.busy_signal.emit(False) # Handled by cleanup
        # self.instances_table_view.setEnabled(True) # Handled by cleanup
        if not isinstance(result, list):
            self._on_object_instances_load_error(f"Unexpected data type for object instances: {type(result)}")
            return

        instances: list[ObjectInstance] = result
        if self.object_instance_model:
            self.object_instance_model.set_instances(instances)
        self._update_action_buttons_state()
        if not instances and self.current_object_type:
            QMessageBox.information(
                self,
                "Object Instances",
                f"No instances found for type '{self.current_object_type.name}'.",
            )

    @Slot(str)
    def _on_object_instances_load_error(self, error_message: str) -> None:
        # self.busy_signal.emit(False) # Handled by cleanup
        # self.instances_table_view.setEnabled(True) # Handled by cleanup
        if self.object_instance_model:
            self.object_instance_model.clear_data()
        QMessageBox.critical(self, "Error Loading Object Instances", error_message)
        self._update_action_buttons_state()

    @Slot()
    def _cleanup_list_instances_thread(self) -> None:
        self.busy_signal.emit(False)
        self.instances_table_view.setEnabled(True)
        if self._active_list_instances_thread:
            self._active_list_instances_thread.deleteLater()
            self._active_list_instances_thread = None

    # _perform_load_object_instances is removed as ApiClientThread handles the request to main thread.

    @Slot()
    def _on_instance_selection_changed(self) -> None:
        self._update_action_buttons_state()

    def _update_action_buttons_state(self) -> None:
        has_type_selected = self.current_object_type is not None
        has_instance_selected = False
        selection_model = self.instances_table_view.selectionModel()

        selected_rows_count = 0
        has_current_selection = False
        if selection_model:  # Check if selection model exists
            selected_rows = selection_model.selectedRows()
            selected_rows_count = len(selected_rows)
            has_instance_selected = bool(selected_rows_count > 0)
            has_current_selection = selection_model.hasSelection() # Another way to check

        self._logger.debug(
            f"_update_action_buttons_state: current_object_type: {self.current_object_type.name if self.current_object_type else 'None'}, "
            f"has_type_selected: {has_type_selected}, "
            f"selection_model exists: {selection_model is not None}, "
            f"selectedRows_count: {selected_rows_count}, "
            f"hasSelection(): {has_current_selection}, "
            f"has_instance_selected (derived): {has_instance_selected}",
        )

        self.new_object_button.setEnabled(has_type_selected)
        self.view_edit_button.setEnabled(has_type_selected and has_instance_selected)
        self.delete_button.setEnabled(has_type_selected and has_instance_selected)
        self.refresh_button.setEnabled(has_type_selected)

    def _on_new_object(self) -> None:
        if not self.current_object_type:
            QMessageBox.warning(
                self, "New Object", "Please select an object type first.",
            )
            return
        if not self.grizabella_client:
            QMessageBox.critical(
                self, "Client Error", "Grizabella client is not available.",
            )
            return

        dialog = ObjectInstanceDialog(
            grizabella_client=self.grizabella_client,
            object_type=self.current_object_type,
            mode="create",
            parent=self,
        )
        # Connect to a lambda that calls _load_object_instances directly
        dialog.instance_upserted_signal.connect(
            lambda _obj_id: self._load_object_instances(
                self.current_object_type.name if self.current_object_type else "",
            ) if self.current_object_type else None,
        )
        dialog.exec()

    def _on_view_edit_object(self) -> None:
        if not self.current_object_type or not self.object_instance_model:
            return
        if not self.grizabella_client:
            QMessageBox.critical(
                self, "Client Error", "Grizabella client is not available.",
            )
            return

        selected_indexes = self.instances_table_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.information(
                self, "View/Edit Object", "Please select an object instance.",
            )
            return

        instance_to_edit = self.object_instance_model.get_instance_at_row(
            selected_indexes[0].row(),
        )
        if not instance_to_edit:
            QMessageBox.critical(
                self, "Error", "Could not retrieve selected instance data.",
            )
            return

        dialog = ObjectInstanceDialog(
            grizabella_client=self.grizabella_client,
            object_type=self.current_object_type,
            instance_data=instance_to_edit,
            mode="edit",
            parent=self,
        )
        dialog.instance_upserted_signal.connect(
            lambda _obj_id: self._load_object_instances(
                self.current_object_type.name if self.current_object_type else "",
            ) if self.current_object_type else None,
        )
        dialog.exec()

    def _on_delete_object(self) -> None:
        if not self.current_object_type or not self.object_instance_model:
            return
        if not self.grizabella_client:
            QMessageBox.critical(
                self, "Client Error", "Grizabella client is not available.",
            )
            return

        selected_indexes = self.instances_table_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.information(
                self, "Delete Object", "Please select an object instance to delete.",
            )
            return

        instance_to_delete = self.object_instance_model.get_instance_at_row(
            selected_indexes[0].row(),
        )
        if not instance_to_delete:
            QMessageBox.critical(
                self, "Error", "Could not retrieve instance data for deletion.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete object '{instance_to_delete.id}' of type "
            f"'{self.current_object_type.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.busy_signal.emit(True)
            self._object_id_for_delete_success = str(instance_to_delete.id)
            self._object_type_name_for_delete_success = self.current_object_type.name

            if self._active_delete_object_thread and self._active_delete_object_thread.isRunning():
                self._logger.warning("Delete object already in progress.")
                self.busy_signal.emit(False)
                return

            if not self.grizabella_client._is_connected:
                self._on_object_delete_error("Client not connected.")
                # busy_signal is handled by _on_object_delete_error via _cleanup_delete_thread
                return

            self._active_delete_object_thread = ApiClientThread(
                operation_name="delete_object",
                object_id=str(instance_to_delete.id),
                type_name=self.current_object_type.name,
                parent=self,
            )
            main_win = self._find_main_window()
            if main_win:
                self._active_delete_object_thread.apiRequestReady.connect(main_win.handleApiRequest)
            else:
                self._on_object_delete_error("Internal error: Cannot connect to API handler.")
                self._active_delete_object_thread.deleteLater()
                self._active_delete_object_thread = None
                return

            self._active_delete_object_thread.result_ready.connect(self._on_object_deleted_success)
            self._active_delete_object_thread.error_occurred.connect(self._on_object_delete_error)
            self._active_delete_object_thread.finished.connect(self._cleanup_delete_object_thread)
            self._active_delete_object_thread.start()

    @Slot(object) # Changed from (str, str)
    def _on_object_deleted_success(self, result: Any) -> None:
        # self.busy_signal.emit(False) # Handled by cleanup
        object_id = self._object_id_for_delete_success
        object_type_name = self._object_type_name_for_delete_success

        if isinstance(result, bool) and result:
            QMessageBox.information(
                self, "Success", f"Object '{object_id}' deleted successfully.",
            )
            if object_type_name:
                 self._load_object_instances(object_type_name)
        elif isinstance(result, bool) and not result:
             self._on_object_delete_error(f"Failed to delete object '{object_id}' (not found or error during deletion).")
        else:
            self._on_object_delete_error(f"Unexpected result from delete operation for object '{object_id}': {result}")

        self._object_id_for_delete_success = None # Clear stored ids
        self._object_type_name_for_delete_success = None


    @Slot(str)
    def _on_object_delete_error(self, error_message: str) -> None:
        # self.busy_signal.emit(False) # Handled by cleanup
        QMessageBox.critical(self, "Error Deleting Object", error_message)
        self._object_id_for_delete_success = None # Clear stored ids
        self._object_type_name_for_delete_success = None


    @Slot()
    def _cleanup_delete_object_thread(self) -> None: # Renamed
        self.busy_signal.emit(False)
        if self._active_delete_object_thread:
            self._active_delete_object_thread.deleteLater()
            self._active_delete_object_thread = None

    def _on_refresh_list(self) -> None:
        if self.current_object_type:
            self._load_object_instances(self.current_object_type.name)
        else:
            QMessageBox.information(
                self, "Refresh", "Please select an object type first.",
            )

    def refresh_view_data(self) -> None:
        self._load_object_types()
        if self.object_instance_model:
            self.object_instance_model.clear_data()
        self._update_action_buttons_state()

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
        self._logger.warning("Could not find MainWindow instance for ObjectExplorerView.")
        return None

    def closeEvent(self, event: Any) -> None:
        self._logger.debug(f"ObjectExplorerView closeEvent triggered for {self}.")
        threads_to_manage = [
            ("_active_list_types_thread", self._active_list_types_thread),
            ("_active_list_instances_thread", self._active_list_instances_thread),
            ("_active_delete_object_thread", self._active_delete_object_thread),
        ]
        for name, thread_instance in threads_to_manage:
            if thread_instance and thread_instance.isRunning():
                self._logger.info(f"ObjectExplorerView: Worker thread '{name}' ({thread_instance}) is running. Attempting to quit and wait.")
                thread_instance.quit()
                if not thread_instance.wait(500):
                    self._logger.warning(f"ObjectExplorerView: Worker thread '{name}' ({thread_instance}) did not finish in time. Terminating.")
                    thread_instance.terminate()
                    thread_instance.wait()
                else:
                    self._logger.info(f"ObjectExplorerView: Worker thread '{name}' ({thread_instance}) finished.")
            elif thread_instance: # Exists but not running
                thread_instance.deleteLater() # Schedule for cleanup
            # else: thread is None

        self._active_list_types_thread = None
        self._active_list_instances_thread = None
        self._active_delete_object_thread = None
        super().closeEvent(event)


# --- Mocking for standalone testing ---
class MockGrizabella(Grizabella):
    """Mock Grizabella client for standalone testing."""

    def __init__(
        self,
        db_name_or_path: Union[str, Path] = ":memory:",
        create_if_not_exists: bool = True,
    ) -> None:  # pylint: disable=unused-argument
        super().__init__(db_name_or_path=db_name_or_path, create_if_not_exists=create_if_not_exists)  # type: ignore[misc]
        self._is_connected = (
            True  # super() might set this, but ensure it's True for mock
        )
        # self.db_path is set by super()
        self._object_types: list[ObjectTypeDefinition] = []
        self._object_instances: dict[str, list[ObjectInstance]] = {}
        self._setup_mock_data()

    def _setup_mock_data(self) -> None:
        props_doc = [
            PropertyDefinition(
                name="title", data_type=PropertyDataType.TEXT, is_nullable=False,
            ),
            PropertyDefinition(
                name="pages", data_type=PropertyDataType.INTEGER, is_nullable=True,
            ),
        ]
        doc_type = ObjectTypeDefinition(
            name="Document", properties=props_doc, description="A document type",
        )
        self._object_types.append(doc_type)

        props_person = [
            PropertyDefinition(
                name="name", data_type=PropertyDataType.TEXT, is_nullable=False,
            ),
            PropertyDefinition(
                name="age", data_type=PropertyDataType.INTEGER, is_nullable=True,
            ),
        ]
        person_type = ObjectTypeDefinition(
            name="Person", properties=props_person, description="A person type",
        )
        self._object_types.append(person_type)

        self._object_instances["Document"] = [
            ObjectInstance(
                id=uuid.uuid4(),
                object_type_name="Document",
                properties={"title": "The Great Gatsby", "pages": 180},
                weight=Decimal("1.0"),
            ),
            ObjectInstance(
                id=uuid.uuid4(),
                object_type_name="Document",
                properties={"title": "Moby Dick", "pages": 600},
                weight=Decimal("1.0"),
            ),
        ]
        self._object_instances["Person"] = [
            ObjectInstance(
                id=uuid.uuid4(),
                object_type_name="Person",
                properties={"name": "Alice", "age": 30},
                weight=Decimal("1.0"),
            ),
            ObjectInstance(
                id=uuid.uuid4(),
                object_type_name="Person",
                properties={"name": "Bob", "age": 25},
                weight=Decimal("1.0"),
            ),
        ]

    def list_object_types(self) -> list[ObjectTypeDefinition]:
        QThread.msleep(100)  # Simulate delay
        return self._object_types

    def find_objects(
        self,
        type_name: str,
        filter_criteria: Optional[
            dict[str, Any]
        ] = None,  # pylint: disable=unused-argument
        limit: Optional[int] = None,
    ) -> list[ObjectInstance]:  # pylint: disable=unused-argument
        QThread.msleep(100)
        return self._object_instances.get(type_name, [])

    def get_object_type_definition(
        self, type_name: str,
    ) -> Optional[ObjectTypeDefinition]:
        return next((ot for ot in self._object_types if ot.name == type_name), None)

    def upsert_object(self, obj: ObjectInstance) -> ObjectInstance:
        QThread.msleep(100)
        if not obj.id or str(obj.id) == "00000000-0000-0000-0000-000000000000":
            obj.id = uuid.uuid4()
        obj.upsert_date = datetime.now(timezone.utc)

        type_instances = self._object_instances.setdefault(obj.object_type_name, [])
        # Remove existing if it's an update
        type_instances[:] = [inst for inst in type_instances if inst.id != obj.id]
        type_instances.append(obj)
        return obj

    def delete_object(self, object_id: str, type_name: str) -> bool:
        QThread.msleep(100)
        obj_id_uuid = uuid.UUID(object_id)
        if type_name in self._object_instances:
            initial_len = len(self._object_instances[type_name])
            self._object_instances[type_name][:] = [
                inst
                for inst in self._object_instances[type_name]
                if inst.id != obj_id_uuid
            ]
            return len(self._object_instances[type_name]) < initial_len
        return False

    # Add missing methods from Grizabella base class that Pylint might consider abstract
    def get_relation(
        self, from_object_id: str, to_object_id: str, relation_type_name: str,
    ) -> list[RelationInstance]:  # Corrected return type to match base
        # The base class Grizabella.get_relation returns list[RelationInstance].
        # For a mock, we can return an empty list.
        return []

    def delete_relation(
        self, relation_type_name: str, relation_id: str, # Corrected signature
    ) -> bool:
        # Base class Grizabella.delete_relation returns bool.
        return False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mock_client_instance = MockGrizabella()

    main_window_container = QWidget()  # Use a simple QWidget as a container
    layout = QVBoxLayout(main_window_container)
    explorer_view_instance = ObjectExplorerView(
        grizabella_client=mock_client_instance,  # type: ignore
    )
    layout.addWidget(explorer_view_instance)

    main_window_container.setWindowTitle("Object Explorer Test")
    main_window_container.setGeometry(100, 100, 900, 700)
    main_window_container.show()

    sys.exit(app.exec())
