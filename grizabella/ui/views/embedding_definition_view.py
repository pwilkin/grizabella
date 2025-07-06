"""QWidget for managing Embedding Definitions in Grizabella."""
# Standard library imports
import logging  # Add logging
from typing import TYPE_CHECKING, Any, Optional  # Added TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget

# First-party imports
from grizabella.api.client import Grizabella
from grizabella.core.models import EmbeddingDefinition
from grizabella.ui.dialogs.embedding_definition_dialog import EmbeddingDefinitionDialog
from grizabella.ui.threads.api_client_thread import ApiClientThread  # Import the new thread

# from grizabella.ui.main_window import MainWindow # For connecting signals <- REMOVED FOR CIRCULAR IMPORT

if TYPE_CHECKING:
    from grizabella.ui.main_window import MainWindow


class EmbeddingDefinitionView(QWidget):
    """View for managing Embedding Definitions."""

    # Signal to indicate a busy state, could be used by MainWindow
    busy_signal = Signal(bool)

    def __init__(self, client: Optional[Grizabella], # Allow Optional client
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.client: Optional[Grizabella] = client # Store client
        self._logger = logging.getLogger(__name__) # Add logger
        self.current_definitions: list[EmbeddingDefinition] = []
        self.active_list_thread: Optional[ApiClientThread] = None
        self.active_delete_thread: Optional[ApiClientThread] = None
        self._definition_name_for_delete: Optional[str] = None # Store name for delete success handling

        self.setWindowTitle("Embedding Definitions")
        main_layout = QVBoxLayout(self)

        # Actions Toolbar
        actions_layout = QHBoxLayout()
        self.new_button = QPushButton("New Embedding Definition")
        self.edit_button = QPushButton("Edit Selected")
        self.delete_button = QPushButton("Delete Selected")
        actions_layout.addWidget(self.new_button)
        actions_layout.addWidget(self.edit_button)
        actions_layout.addWidget(self.delete_button)
        actions_layout.addStretch()
        main_layout.addLayout(actions_layout)

        # Splitter for list and details
        splitter = QSplitter(Qt.Orientation.Horizontal) # Corrected enum
        main_layout.addWidget(splitter)

        # Left side: List of Embedding Definitions
        list_groupbox = QGroupBox("Available Embedding Definitions")
        list_layout = QVBoxLayout()
        self.definitions_list_widget = QListWidget()
        self.definitions_list_widget.setAlternatingRowColors(True)
        list_layout.addWidget(self.definitions_list_widget)
        list_groupbox.setLayout(list_layout)
        splitter.addWidget(list_groupbox)

        # Right side: Details of selected Embedding Definition
        details_groupbox = QGroupBox("Definition Details")
        details_layout = QVBoxLayout()
        self.details_text_edit = QTextEdit()
        self.details_text_edit.setReadOnly(True)
        details_layout.addWidget(self.details_text_edit)
        details_groupbox.setLayout(details_layout)
        splitter.addWidget(details_groupbox)

        splitter.setSizes([200, 400]) # Initial sizes for list and details

        # Connect signals
        self.new_button.clicked.connect(self._on_new_definition)
        self.edit_button.clicked.connect(self._on_edit_definition) # Placeholder
        self.delete_button.clicked.connect(self._on_delete_definition) # Placeholder
        self.definitions_list_widget.currentItemChanged.connect(
            self._on_selection_changed,
        )

        self.edit_button.setEnabled(False) # Disabled until full edit is implemented
        self.delete_button.setEnabled(False) # Disabled until selection

        if self.client:
            self._load_definitions()
        else:
            self.definitions_list_widget.addItem("Client not connected.")
            self.details_text_edit.setText("Client not connected.")
            self.new_button.setEnabled(False)

    def set_grizabella_client(self, client: Optional[Grizabella]) -> None:
        """Sets or updates the Grizabella client and refreshes the view."""
        self.client = client
        if self.client:
            self.new_button.setEnabled(True)
            self._load_definitions()
        else:
            self.definitions_list_widget.clear()
            self.definitions_list_widget.addItem("Client not connected.")
            self.details_text_edit.clear()
            self.details_text_edit.setText("Client not connected.")
            self.current_definitions = []
            self.delete_button.setEnabled(False)
            self.edit_button.setEnabled(False)
            self.new_button.setEnabled(False)

    def refresh_definitions(self) -> None:
        """Public method to refresh the list of definitions."""
        if self.client:
            self._load_definitions()
        else:
            self._show_error_message(
                "Cannot refresh: Grizabella client not available.",
            )

    def _load_definitions(self) -> None:
        """Loads embedding definitions from the client."""
        if not self.client: # Guard against no client
            self.definitions_list_widget.clear()
            self.definitions_list_widget.addItem("Client not available.")
            self.details_text_edit.setText("Client not available.")
            return

        self.definitions_list_widget.clear()
        self.definitions_list_widget.addItem("Loading definitions...")
        self.details_text_edit.clear()
        self.busy_signal.emit(True)

        if self.active_list_thread and self.active_list_thread.isRunning():
            self._logger.warning("List definitions already in progress.")
            # Optionally, do not start a new one, or manage queueing
            self.busy_signal.emit(False) # Reset busy if we don't proceed
            return

        if not self.client or not self.client._is_connected:
            self._show_error_message("Client not available or not connected.")
            self.busy_signal.emit(False)
            return

        self.active_list_thread = ApiClientThread(
            operation_name="list_embedding_definitions",
            parent=self, # Parent for Qt object tree management
        )

        # Connect to MainWindow's API request handler
        # This assumes MainWindow is accessible, e.g., as a grandparent or via app instance
        main_win = self._find_main_window()
        if main_win:
            self.active_list_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._logger.error("Could not find MainWindow to connect ApiClientThread. API calls will fail.")
            self._show_error_message("Internal error: Cannot connect to API handler.")
            self.active_list_thread.deleteLater()
            self.active_list_thread = None
            self.busy_signal.emit(False)
            return

        self.active_list_thread.result_ready.connect(self._on_definitions_loaded_success)
        self.active_list_thread.error_occurred.connect(self._on_list_definitions_error)
        self.active_list_thread.finished.connect(self._cleanup_list_thread) # QThread's finished
        self.active_list_thread.start()

    def _cleanup_list_thread(self) -> None:
        self.busy_signal.emit(False)
        if self.active_list_thread:
            # Ensure signals are disconnected if the thread is being reused or if errors occurred
            # For one-shot threads, deleteLater is usually sufficient.
            self.active_list_thread.deleteLater()
            self.active_list_thread = None
            self._logger.debug("ListEmbeddingDefinitions ApiClientThread cleaned up.")

    def _on_list_definitions_error(self, error_message: str) -> None:
        self._show_error_message(error_message)
        # self._cleanup_list_thread() # Cleanup is handled by 'finished' signal

    def _on_definitions_loaded_success(self, result: Any) -> None: # Result is from ApiClientThread
        self.definitions_list_widget.clear()
        if not isinstance(result, list):
            self._logger.error(f"Unexpected result type from list_embedding_definitions: {type(result)}")
            self._show_error_message("Error: Invalid data received for embedding definitions.")
            self.current_definitions = []
            return

        definitions: list[EmbeddingDefinition] = result
        self.current_definitions = definitions
        if not definitions:
            self.definitions_list_widget.addItem("No embedding definitions found.")
            self.delete_button.setEnabled(False)
            return

        for ed_def in definitions:
            item = QListWidgetItem(ed_def.name)
            item.setData(Qt.ItemDataRole.UserRole, ed_def) # Corrected enum
            self.definitions_list_widget.addItem(item)

        if self.definitions_list_widget.count() > 0:
            self.definitions_list_widget.setCurrentRow(0)

    def _on_selection_changed(self, current: Optional[QListWidgetItem],
                              previous: Optional[QListWidgetItem]) -> None:
        # Suppress unused argument warnings
        _ = previous
        self.details_text_edit.clear()
        if current:
            ed_def: Optional[EmbeddingDefinition] = current.data(
                Qt.ItemDataRole.UserRole, # Corrected enum
            )
            if ed_def:
                dimensions_str = (str(ed_def.dimensions)
                                  if ed_def.dimensions is not None
                                  else "N/A (Inferred)")
                description_str = ed_def.description if ed_def.description else "N/A"
                details_html = f"""
                <b>Name:</b> {ed_def.name}<br>
                <b>Object Type:</b> {ed_def.object_type_name}<br>
                <b>Source Property:</b> {ed_def.source_property_name}<br>
                <b>Embedding Model:</b> {ed_def.embedding_model}<br>
                <b>Dimensions:</b> {dimensions_str}<br>
                <b>Description:</b><br>
                <pre>{description_str}</pre>
                """
                self.details_text_edit.setHtml(details_html)
                self.delete_button.setEnabled(True)
                # self.edit_button.setEnabled(True) # Enable when edit is implemented
            else:
                self.delete_button.setEnabled(False)
                # self.edit_button.setEnabled(False)
        else:
            self.delete_button.setEnabled(False)
            # self.edit_button.setEnabled(False)

    def _on_new_definition(self) -> None:
        """Opens the dialog to create a new embedding definition."""
        if not self.client:
            self._show_error_message(
                "Cannot create new definition: Client not connected.",
            )
            return
        dialog = EmbeddingDefinitionDialog(client=self.client, parent=self)
        if dialog.exec():
            # Dialog was accepted, refresh the list
            self._load_definitions()

    def _on_edit_definition(self) -> None:
        """Placeholder for editing an existing definition."""
        # current_item = self.definitions_list_widget.currentItem()
        # if not current_item:
        #     QMessageBox.warning(self, "Edit Error", "No embedding definition selected.")
        #     return
        # ed_to_edit: Optional[EmbeddingDefinition] = current_item.data(Qt.UserRole)
        # if not ed_to_edit:
        #     return

        # dialog = EmbeddingDefinitionDialog(client=self.client,
        #                                    embedding_definition=ed_to_edit, parent=self)
        # if dialog.exec():
        #     self._load_definitions()
        QMessageBox.information(self, "Not Implemented",
                                "Editing embedding definitions is not yet implemented.")

    def _on_delete_definition(self) -> None:
        """Deletes the selected embedding definition."""
        current_item = self.definitions_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Delete Error", "No embedding definition selected.")
            return

        ed_to_delete: Optional[EmbeddingDefinition] = current_item.data(
            Qt.ItemDataRole.UserRole, # Corrected enum
        )
        if not ed_to_delete:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the embedding definition "
            f"'{ed_to_delete.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, # Corrected enum
            QMessageBox.StandardButton.No, # Corrected enum
        )

        if reply == QMessageBox.StandardButton.Yes: # Corrected enum
            if not self.client:
                self._show_error_message(
                    "Cannot delete definition: Client not connected.",
                )
                return

            self.busy_signal.emit(True)
            self._definition_name_for_delete = ed_to_delete.name # Store for success message

            if self.active_delete_thread and self.active_delete_thread.isRunning():
                self._logger.warning("Delete definition already in progress.")
                self.busy_signal.emit(False)
                return

            if not self.client or not self.client._is_connected: # Should be caught by main_window, but good check
                self._show_error_message("Client not available or not connected.")
                self.busy_signal.emit(False)
                return

            self.active_delete_thread = ApiClientThread(
                "delete_embedding_definition", # operation_name passed positionally
                ed_to_delete.name, # Pass name as arg for *args
                parent=self,
            )

            main_win = self._find_main_window()
            if main_win:
                self.active_delete_thread.apiRequestReady.connect(main_win.handleApiRequest)
            else:
                self._logger.error("Could not find MainWindow to connect ApiClientThread for delete. API call will fail.")
                self._show_error_message("Internal error: Cannot connect to API handler for delete.")
                self.active_delete_thread.deleteLater()
                self.active_delete_thread = None
                self.busy_signal.emit(False)
                return

            self.active_delete_thread.result_ready.connect(self._on_definition_deleted_success)
            self.active_delete_thread.error_occurred.connect(self._on_delete_definition_error)
            self.active_delete_thread.finished.connect(self._cleanup_delete_thread)
            self.active_delete_thread.start()

    def _cleanup_delete_thread(self) -> None:
        self.busy_signal.emit(False)
        if self.active_delete_thread:
            self.active_delete_thread.deleteLater()
            self.active_delete_thread = None
            self._logger.debug("DeleteEmbeddingDefinition ApiClientThread cleaned up.")
        self._definition_name_for_delete = None # Clear stored name

    def _on_delete_definition_error(self, error_message: str) -> None:
        self._show_error_message(error_message)
        # self._cleanup_delete_thread() # Cleanup is handled by 'finished' signal

    def _on_definition_deleted_success(self, result: Any) -> None:
        if isinstance(result, bool) and result:
            deleted_name = self._definition_name_for_delete if self._definition_name_for_delete else "Selected"
            QMessageBox.information(
                self, "Success",
                f"Embedding definition '{deleted_name}' deleted successfully.",
            )
            self._load_definitions()  # Refresh the list
        elif isinstance(result, bool) and not result:
            deleted_name = self._definition_name_for_delete if self._definition_name_for_delete else "Selected"
            self._show_error_message(
                 f"Failed to delete embedding definition '{deleted_name}' (not found or error during deletion).",
            )
        else:
            self._show_error_message(f"Unexpected result from delete operation: {result}")
        # self._cleanup_delete_thread() # Cleanup is handled by 'finished' signal

    def _show_error_message(self, message: str) -> None:
        self.busy_signal.emit(False) # Ensure busy indicator is turned off on error
        QMessageBox.warning(self, "Error", message)

    def _find_main_window(self) -> Optional["MainWindow"]:
        """Helper to find the MainWindow instance."""
        # Import MainWindow locally to break circular dependency
        from grizabella.ui.main_window import MainWindow
        # This is a common pattern, but can be fragile.
        # A more robust way is to pass MainWindow explicitly or use a global app context.
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, MainWindow):
                return parent
            parent = parent.parent()

        # Fallback: Try to get it from QApplication if it's the top-level active window
        app_instance = QApplication.instance()
        if isinstance(app_instance, QApplication): # Ensure it's a QApplication
            active_window = app_instance.activeWindow()
            if isinstance(active_window, MainWindow):
                return active_window
        self._logger.warning("Could not find MainWindow instance via parent hierarchy or active window.")
        return None

    def closeEvent(self, event: Any) -> None:
        """Ensure threads are stopped if the widget is closed."""
        self._logger.debug(f"EmbeddingDefinitionView closeEvent triggered for {self}.")
        threads_to_manage = [
            ("active_list_thread", self.active_list_thread),
            ("active_delete_thread", self.active_delete_thread),
        ]
        for name, thread_instance in threads_to_manage:
            if thread_instance and thread_instance.isRunning():
                self._logger.info(f"EmbeddingDefinitionView: Worker thread '{name}' ({thread_instance}) is running. Attempting to quit and wait.")
                # ApiClientThread is designed to finish quickly after emitting apiRequestReady.
                # If it's stuck, it's likely waiting for main thread, which is a deeper issue.
                # Forcing quit might be okay here as the actual API call is main-thread.
                thread_instance.quit() # Request termination
                if not thread_instance.wait(500):  # Wait for 0.5 second
                    self._logger.warning(f"EmbeddingDefinitionView: Worker thread '{name}' ({thread_instance}) did not finish in time during closeEvent. Terminating.")
                    thread_instance.terminate() # Force terminate if quit fails
                    thread_instance.wait() # Wait for termination
                else:
                    self._logger.info(f"EmbeddingDefinitionView: Worker thread '{name}' ({thread_instance}) finished during closeEvent.")
            elif thread_instance:
                self._logger.debug(f"EmbeddingDefinitionView: Worker thread '{name}' ({thread_instance}) was not running. Will be deleted if pending.")
                thread_instance.deleteLater() # Ensure it's cleaned up if not running but exists
            else:
                self._logger.debug(f"EmbeddingDefinitionView: Worker thread '{name}' was None.")

        self.active_list_thread = None # Clear references
        self.active_delete_thread = None
        super().closeEvent(event)

if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    # --- Mock GrizabellaClient for testing ---
    class MockProperty: # Simplified for this test
        def __init__(self, name, data_type="TEXT") -> None:
            self.name = name
            self.data_type = data_type

    class MockObjectType: # Simplified for this test
        def __init__(self, name, properties=None) -> None:
            self.name = name
            self.properties = properties if properties else []
            self.description = f"Description for {name}"


    class MockGrizabellaClient:
        _embedding_defs = [
            EmbeddingDefinition(
                name="doc_content_v1", object_type_name="Document",
                source_property_name="content", embedding_model="model1",
                dimensions=128, description="Content embedding for docs",
            ),
            EmbeddingDefinition(
                name="user_bio_v2", object_type_name="User",
                source_property_name="biography", embedding_model="model2",
                dimensions=256, description="User bio embedding",
            ),
        ]
        _object_types = [
            MockObjectType("Document",
                           [MockProperty("content"), MockProperty("title")]),
            MockObjectType("User",
                           [MockProperty("biography"), MockProperty("username")]),
        ]

        def list_embedding_definitions(self) -> list[EmbeddingDefinition]:
            return self._embedding_defs[:]

        def delete_embedding_definition(self, name: str) -> bool:
            initial_len = len(self._embedding_defs)
            self._embedding_defs = [ed for ed in self._embedding_defs
                                    if ed.name != name]
            return len(self._embedding_defs) < initial_len

        def create_embedding_definition(self,
                                        ed_def: EmbeddingDefinition) -> EmbeddingDefinition:
            # Check for duplicates by name
            if any(existing_ed.name == ed_def.name
                   for existing_ed in self._embedding_defs):
                msg = f"Embedding definition with name '{ed_def.name}' already exists."
                raise Exception(
                    msg,
                )
            self._embedding_defs.append(ed_def)
            return ed_def

        def list_object_types(self) -> list[MockObjectType]: # Required by dialog
            return self._object_types[:]

        def get_object_type_definition(self, name: str) -> Optional[MockObjectType]: # Required by dialog
            for obj_type in self._object_types:
                if obj_type.name == name:
                    return obj_type
            return None
    # --- End Mock GrizabellaClient ---

    app = QApplication(sys.argv)
    mock_client_instance = MockGrizabellaClient()
    view = EmbeddingDefinitionView(client=mock_client_instance) # type: ignore
    view.show()
    sys.exit(app.exec())
