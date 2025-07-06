"""View for exploring and managing Relation Instances in Grizabella."""
import uuid
from typing import TYPE_CHECKING, Any, Optional  # Added TYPE_CHECKING

from PySide6.QtCore import QTimer, Signal, Slot  # Added Signal
from PySide6.QtWidgets import QAbstractItemView, QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTableView, QVBoxLayout, QWidget  # Added QApplication

from grizabella.api.client import Grizabella
from grizabella.core.models import RelationInstance, RelationTypeDefinition
from grizabella.ui.dialogs.relation_instance_dialog import RelationInstanceDialog
from grizabella.ui.models.relation_instance_table_model import RelationInstanceTableModel
from grizabella.ui.threads.api_client_thread import ApiClientThread  # Corrected import path

# from grizabella.ui.main_window import MainWindow # For connecting signals <- REMOVED FOR CIRCULAR IMPORT

if TYPE_CHECKING:
    from grizabella.ui.main_window import MainWindow


class RelationExplorerView(QWidget):
    """View for exploring and managing RelationInstances."""

    busy_signal = Signal(bool)

    def __init__(self, grizabella_client: Optional[Grizabella],
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.grizabella_client = grizabella_client # This will be set by MainWindow
        self.relation_types: list[RelationTypeDefinition] = []
        self.current_selected_relation_type: Optional[RelationTypeDefinition] = None
        self._active_api_thread: Optional[ApiClientThread] = None # Renamed

        self.setWindowTitle("Relation Explorer")
        self._main_layout = QVBoxLayout(self)

        # Top Controls: Relation Type Selection and Filters
        controls_layout = QHBoxLayout()

        # Relation Type ComboBox
        self.relation_type_combo = QComboBox()
        self.relation_type_combo.setPlaceholderText("Select Relation Type...")
        self.relation_type_combo.currentIndexChanged.connect(self._on_relation_type_selected)
        controls_layout.addWidget(QLabel("Relation Type:"))
        controls_layout.addWidget(self.relation_type_combo, 1)

        # Filter LineEdits
        self.source_id_filter_edit = QLineEdit()
        self.source_id_filter_edit.setPlaceholderText("Filter by Source Object ID (UUID)...")
        self.source_id_filter_edit.textChanged.connect(self._schedule_filter_relations)
        controls_layout.addWidget(QLabel("Source ID:"))
        controls_layout.addWidget(self.source_id_filter_edit, 1)

        self.target_id_filter_edit = QLineEdit()
        self.target_id_filter_edit.setPlaceholderText("Filter by Target Object ID (UUID)...")
        self.target_id_filter_edit.textChanged.connect(self._schedule_filter_relations)
        controls_layout.addWidget(QLabel("Target ID:"))
        controls_layout.addWidget(self.target_id_filter_edit, 1)

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(500) # 500ms delay
        self._filter_timer.timeout.connect(self._filter_relations)


        self._main_layout.addLayout(controls_layout)

        # Table View for Relation Instances
        self.relation_instances_table = QTableView()
        self.relation_instance_model = RelationInstanceTableModel(self)
        self.relation_instances_table.setModel(self.relation_instance_model)
        self.relation_instances_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.relation_instances_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.relation_instances_table.setSortingEnabled(True)
        self.relation_instances_table.horizontalHeader().setStretchLastSection(True)
        self.relation_instances_table.doubleClicked.connect(self._view_edit_selected_relation)
        self._main_layout.addWidget(self.relation_instances_table)

        # Action Buttons
        buttons_layout = QHBoxLayout()
        self.new_relation_button = QPushButton("New Relation")
        self.new_relation_button.clicked.connect(self._create_new_relation)
        self.view_edit_button = QPushButton("View/Edit Selected")
        self.view_edit_button.clicked.connect(self._view_edit_selected_relation)
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self._delete_selected_relation)
        self.refresh_button = QPushButton("Refresh List")
        self.refresh_button.clicked.connect(self._load_relation_instances_for_current_type)

        buttons_layout.addWidget(self.new_relation_button)
        buttons_layout.addWidget(self.view_edit_button)
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.refresh_button)
        self._main_layout.addLayout(buttons_layout)

        self._load_relation_types()

    def _schedule_filter_relations(self) -> None:
        self._filter_timer.start()

    def _filter_relations(self) -> None:
        self._load_relation_instances_for_current_type()

    def _load_relation_types(self) -> None:
        self.relation_type_combo.setEnabled(False)
        self.busy_signal.emit(True)

        if not self.grizabella_client or not self.grizabella_client._is_connected:
            self._handle_api_error("Client not available or not connected for loading relation types.")
            # self.relation_type_combo.setEnabled(True) # Handled in _on_api_thread_finished or _handle_api_error
            self.busy_signal.emit(False)
            return

        if self._active_api_thread and self._active_api_thread.isRunning():
            QMessageBox.information(self, "Busy", "An operation is already in progress. Please wait.")
            # self.relation_type_combo.setEnabled(True) # Handled by finished signal
            self.busy_signal.emit(False)
            return

        self._active_api_thread = ApiClientThread(
            operation_name="list_relation_types",
            parent=self,
        )

        main_win = self._find_main_window()
        if main_win:
            self._active_api_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._handle_api_error("Internal error: Cannot connect to API handler for list_relation_types.")
            self._active_api_thread.deleteLater()
            self._active_api_thread = None
            self.busy_signal.emit(False)
            return

        self._active_api_thread.result_ready.connect(self._handle_relation_types_loaded)
        self._active_api_thread.error_occurred.connect(self._handle_api_error)
        self._active_api_thread.finished.connect(self._on_api_thread_finished)
        self._active_api_thread.start()

    @Slot(object) # Changed from list to object
    def _handle_relation_types_loaded(self, result: Any) -> None:
        # self.relation_type_combo.setEnabled(True) # Handled by _on_api_thread_finished
        if not isinstance(result, list):
            self._handle_api_error(f"Unexpected data type for relation types: {type(result)}")
            return

        relation_types: list[RelationTypeDefinition] = result
        self.relation_types = sorted(relation_types, key=lambda rt: rt.name)
        self.relation_type_combo.clear()
        self.relation_type_combo.addItem("Select Relation Type...", userData=None)
        for rt_def in self.relation_types:
            self.relation_type_combo.addItem(f"{rt_def.name}", userData=rt_def)

        if not self.relation_types:
            QMessageBox.information(self, "No Relation Types", "No relation types found in the database.")
        elif self.relation_type_combo.count() > 1:
             self.relation_type_combo.setCurrentIndex(1)

    @Slot(int)
    def _on_relation_type_selected(self, index: int) -> None:
        selected_data = self.relation_type_combo.itemData(index)
        if isinstance(selected_data, RelationTypeDefinition):
            self.current_selected_relation_type = selected_data
            self._load_relation_instances_for_current_type()
        else:
            self.current_selected_relation_type = None
            self.relation_instance_model.clear()

    def _load_relation_instances_for_current_type(self) -> None:
        if not self.current_selected_relation_type:
            self.relation_instance_model.clear()
            return

        query_params: dict[str, Any] = {"relation_type_name": self.current_selected_relation_type.name}

        source_id_str = self.source_id_filter_edit.text().strip()
        if source_id_str:
            try:
                query_params["source_object_instance_id"] = uuid.UUID(source_id_str)
            except ValueError:
                QMessageBox.warning(self, "Filter Error", "Invalid Source Object ID UUID format.")
                self.relation_instance_model.clear() # Clear table on bad filter
                return

        target_id_str = self.target_id_filter_edit.text().strip()
        if target_id_str:
            try:
                query_params["target_object_instance_id"] = uuid.UUID(target_id_str)
            except ValueError:
                QMessageBox.warning(self, "Filter Error", "Invalid Target Object ID UUID format.")
                self.relation_instance_model.clear() # Clear table on bad filter
                return

        # Disable UI elements during load
        self.relation_instances_table.setEnabled(False)
        self.refresh_button.setEnabled(False)

        self.busy_signal.emit(True)

        if not self.grizabella_client or not self.grizabella_client._is_connected:
            self._handle_api_error("Client not available or not connected for querying relations.")
            # self.relation_instances_table.setEnabled(True) # Handled by finished
            # self.refresh_button.setEnabled(True) # Handled by finished
            self.busy_signal.emit(False)
            return

        if self._active_api_thread and self._active_api_thread.isRunning():
            QMessageBox.information(self, "Busy", "An operation is already in progress. Please wait.")
            # self.relation_instances_table.setEnabled(True) # Handled by finished
            # self.refresh_button.setEnabled(True) # Handled by finished
            self.busy_signal.emit(False)
            return

        self._active_api_thread = ApiClientThread(
            "query_relations", # operation_name passed positionally
            parent=self,       # parent as keyword argument
            **query_params,     # Spread query_params as keyword arguments
        )

        main_win = self._find_main_window()
        if main_win:
            self._active_api_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._handle_api_error("Internal error: Cannot connect to API handler for query_relations.")
            self._active_api_thread.deleteLater()
            self._active_api_thread = None
            self.busy_signal.emit(False)
            return

        self._active_api_thread.result_ready.connect(self._handle_relation_instances_loaded)
        self._active_api_thread.error_occurred.connect(self._handle_api_error)
        self._active_api_thread.finished.connect(self._on_api_thread_finished)
        self._active_api_thread.start()

    @Slot(object) # Changed from list to object
    def _handle_relation_instances_loaded(self, result: Any) -> None:
        # self.relation_instances_table.setEnabled(True) # Handled by finished
        # self.refresh_button.setEnabled(True) # Handled by finished
        if not isinstance(result, list):
            self._handle_api_error(f"Unexpected data type for relation instances: {type(result)}")
            return

        instances: list[RelationInstance] = result
        current_type_dict = (self.current_selected_relation_type.model_dump()
                             if self.current_selected_relation_type else None)
        self.relation_instance_model.set_relation_instances(instances, current_type_dict)
        # if not instances: # No need for popup

    def _create_new_relation(self) -> None:
        if not self.relation_types:
            QMessageBox.warning(self, "Cannot Create Relation", "No relation types available. Please define a relation type first.")
            return

        if not self.grizabella_client:
            QMessageBox.critical(self, "Client Error", "Grizabella client is not available.")
            return

        dialog = RelationInstanceDialog(
            self.grizabella_client,
            self.relation_types,
            parent=self,
            selected_relation_type_name=self.current_selected_relation_type.name if self.current_selected_relation_type else None,
        )
        dialog.relation_saved.connect(self._on_relation_saved)
        dialog.exec()

    def _view_edit_selected_relation(self) -> None:
        selected_indexes = self.relation_instances_table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "No Selection", "Please select a relation instance to view/edit.")
            return

        selected_row = selected_indexes[0].row()
        instance_to_edit = self.relation_instance_model.get_relation_instance_at_row(selected_row)

        if not instance_to_edit:
            QMessageBox.critical(self, "Error", "Could not retrieve selected relation instance.")
            return

        if not self.relation_types: # Should not happen if we can list instances
            QMessageBox.warning(self, "Error", "Relation types not loaded, cannot edit.")
            return

        if not self.grizabella_client:
            QMessageBox.critical(self, "Client Error", "Grizabella client is not available.")
            return

        dialog = RelationInstanceDialog(
            self.grizabella_client,
            self.relation_types, # Pass all known types
            parent=self,
            instance_to_edit=instance_to_edit,
        )
        dialog.relation_saved.connect(self._on_relation_saved)
        dialog.exec()

    @Slot(object) # RelationInstance
    def _on_relation_saved(self, saved_instance: RelationInstance) -> None:
        # Refresh the list if the saved instance's type matches the currently selected type
        if self.current_selected_relation_type and \
           saved_instance.relation_type_name == self.current_selected_relation_type.name:
            self._load_relation_instances_for_current_type()
        # Optionally, select the newly created/edited item if it's in the list

    def _delete_selected_relation(self) -> None:
        selected_indexes = self.relation_instances_table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "No Selection", "Please select a relation instance to delete.")
            return

        selected_row = selected_indexes[0].row()
        instance_to_delete = self.relation_instance_model.get_relation_instance_at_row(selected_row)

        if not instance_to_delete:
            QMessageBox.critical(self, "Error", "Could not retrieve selected relation instance for deletion.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete relation instance '{instance_to_delete.id}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            # self.setEnabled(False) # Handled by busy_signal if MainWindow connects it
            self.busy_signal.emit(True)
            if not self.grizabella_client or not self.grizabella_client._is_connected:
                self._handle_api_error("Client not available or not connected for deleting relation.")
                # self.setEnabled(True) # Handled by _handle_api_error
                self.busy_signal.emit(False)
                return

            if self._active_api_thread and self._active_api_thread.isRunning():
                QMessageBox.information(self, "Busy", "An operation is already in progress. Please wait.")
                self.busy_signal.emit(False)
                return

            self._active_api_thread = ApiClientThread(
                "delete_relation", # operation_name passed positionally
                # Pass arguments as keyword arguments for the API call
                relation_type_name=instance_to_delete.relation_type_name,
                relation_id=instance_to_delete.id,
                parent=self,
            )

            main_win = self._find_main_window()
            if main_win:
                self._active_api_thread.apiRequestReady.connect(main_win.handleApiRequest)
            else:
                self._handle_api_error("Internal error: Cannot connect to API handler for delete_relation.")
                self._active_api_thread.deleteLater()
                self._active_api_thread = None
                self.busy_signal.emit(False)
                return

            self._active_api_thread.result_ready.connect(self._handle_delete_success)
            self._active_api_thread.error_occurred.connect(self._handle_api_error)
            self._active_api_thread.finished.connect(self._on_api_thread_finished)
            self._active_api_thread.start()

    @Slot(object)
    def _handle_delete_success(self, result: Any) -> None:
        # self.setEnabled(True) # Handled by finished
        if isinstance(result, bool) and result:
            QMessageBox.information(self, "Success", "Relation instance deleted successfully.")
            self._load_relation_instances_for_current_type()
        elif isinstance(result, bool) and not result:
            self._handle_api_error("Failed to delete relation instance (not found or error during deletion).")
        else:
            self._handle_api_error(f"Unexpected result from delete operation: {result}")

    @Slot(str)
    def _handle_api_error(self, error_message: str) -> None:
        # self.setEnabled(True) # Handled by finished
        # self.relation_type_combo.setEnabled(True) # Handled by finished
        # self.relation_instances_table.setEnabled(True) # Handled by finished
        # self.refresh_button.setEnabled(True) # Handled by finished
        self.busy_signal.emit(False) # Ensure busy is off
        QMessageBox.critical(self, "API Error", f"An API error occurred: {error_message}")

    @Slot()
    def _on_api_thread_finished(self) -> None:
        """Cleans up the API thread instance and re-enables UI."""
        self.relation_type_combo.setEnabled(True)
        self.relation_instances_table.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.new_relation_button.setEnabled(True)
        self.view_edit_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.setEnabled(True) # General re-enable for the whole widget
        self.busy_signal.emit(False)

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
        print("RelationExplorerView: Could not find MainWindow instance.") # Basic print for now
        return None

    def refresh_view(self) -> None:
        """Public method to refresh the view, e.g., when tab is selected."""
        self._load_relation_types()

    def closeEvent(self, event: Any) -> None:
        """Ensure thread is stopped if the widget is closed."""
        if self._active_api_thread and self._active_api_thread.isRunning():
            self._active_api_thread.quit()
            if not self._active_api_thread.wait(500):
                self._active_api_thread.terminate()
                self._active_api_thread.wait()
        self._active_api_thread = None # Clear reference
        super().closeEvent(event)

    def set_client(self, client: Optional[Grizabella]) -> None:
        """Sets the Grizabella client and refreshes the view if client is new or changed."""
        # Check if the client instance is actually different or has changed state (e.g. connected/disconnected)
        # For simplicity, we'll refresh if the client object itself changes or becomes (un)available.
        client_changed = False
        if (self.grizabella_client is None and client is not None) or (self.grizabella_client is not None and client is None) or self.grizabella_client is not client:
            client_changed = True
        # More sophisticated check: if self.grizabella_client and client and self.grizabella_client._is_connected != client._is_connected:

        self.grizabella_client = client
        if client_changed or (client and not self.relation_types): # Refresh if client changed or types not loaded
            if self.grizabella_client and self.grizabella_client._is_connected:
                self.setEnabled(True)
                self.refresh_view()
            else:
                self.relation_type_combo.clear()
                self.relation_type_combo.addItem("Client not connected...")
                self.relation_instance_model.clear()
                self.setEnabled(False) # Disable view if no client
        elif not self.grizabella_client: # Explicitly handle client being None
             self.relation_type_combo.clear()
             self.relation_type_combo.addItem("Client not connected...")
             self.relation_instance_model.clear()
             self.setEnabled(False)
