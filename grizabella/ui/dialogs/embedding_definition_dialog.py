from typing import TYPE_CHECKING, Any, Optional  # Added Any, TYPE_CHECKING

from PySide6.QtCore import Signal, Slot  # QThread removed
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QLabel, QLineEdit, QMessageBox, QSpinBox, QTextEdit, QVBoxLayout  # QApplication added

from grizabella.api.client import Grizabella
from grizabella.core.models import EmbeddingDefinition, ObjectTypeDefinition, PropertyDataType, PropertyDefinition
from grizabella.ui.threads.api_client_thread import ApiClientThread  # Import new thread

# from grizabella.ui.main_window import MainWindow # For connecting signals <- REMOVED FOR CIRCULAR IMPORT

if TYPE_CHECKING:
    from grizabella.ui.main_window import MainWindow


class EmbeddingDefinitionDialog(QDialog):
    """Dialog for creating and editing Embedding Definitions."""

    busy_signal = Signal(bool) # To indicate busy state

    def __init__(self, client: Grizabella, embedding_definition: Optional[EmbeddingDefinition] = None, parent=None) -> None:
        super().__init__(parent)
        self.client_ref = client # Store ref, but API calls go via MainWindow
        self.embedding_definition = embedding_definition
        self.is_edit_mode = embedding_definition is not None
        self.object_types_cache: list[ObjectTypeDefinition] = []

        self._active_fetch_ot_thread: Optional[ApiClientThread] = None
        # FetchObjectTypePropertiesThread is removed as properties are assumed to be part of ObjectTypeDefinition
        self._active_create_ed_thread: Optional[ApiClientThread] = None


        self.setWindowTitle(
            "Edit Embedding Definition" if self.is_edit_mode else "New Embedding Definition",
        )
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # Name
        self.name_label = QLabel("Definition Name:")
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_label)
        layout.addWidget(self.name_edit)

        # Object Type Name
        self.object_type_label = QLabel("Object Type:")
        self.object_type_combo = QComboBox()
        self.object_type_combo.setPlaceholderText("Select Object Type...")
        layout.addWidget(self.object_type_label)
        layout.addWidget(self.object_type_combo)

        # Source Property Name
        self.source_property_label = QLabel("Source Property:")
        self.source_property_combo = QComboBox()
        self.source_property_combo.setPlaceholderText("Select Source Property...")
        self.source_property_combo.setEnabled(False) # Disabled until object type is selected
        layout.addWidget(self.source_property_label)
        layout.addWidget(self.source_property_combo)

        # Embedding Model
        self.model_label = QLabel("Embedding Model:")
        self.model_edit = QLineEdit("colbert-ir/colbertv2.0") # Removed "huggingface/" prefix
        layout.addWidget(self.model_label)
        layout.addWidget(self.model_edit)

        # Dimensions
        self.dimensions_label = QLabel("Dimensions (Optional):")
        self.dimensions_spinbox = QSpinBox()
        self.dimensions_spinbox.setRange(0, 100000) # 0 means not set / infer
        self.dimensions_spinbox.setValue(0)
        layout.addWidget(self.dimensions_label)
        layout.addWidget(self.dimensions_spinbox)

        # Description
        self.description_label = QLabel("Description:")
        self.description_edit = QTextEdit()
        self.description_edit.setFixedHeight(100)
        layout.addWidget(self.description_label)
        layout.addWidget(self.description_edit)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel) # Corrected enum
        layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.object_type_combo.currentIndexChanged.connect(self._on_object_type_changed)

        self._load_object_types()

        if self.is_edit_mode and self.embedding_definition:
            self._populate_fields()

    def _load_object_types(self) -> None:
        """Fetches object types and populates the combo box."""
        self.object_type_combo.setEnabled(False)
        self.object_type_combo.clear()
        self.object_type_combo.addItem("Loading object types...")
        self.busy_signal.emit(True)


        if self._active_fetch_ot_thread and self._active_fetch_ot_thread.isRunning():
            # self._show_error_message("Already fetching object types.") # Or just ignore
            self.busy_signal.emit(False)
            return

        # Client connection check will be handled by MainWindow
        # if not self.client_ref or not self.client_ref._is_connected:
        #     self._show_error_message("Client not available or not connected.")
        #     self.object_type_combo.clear()
        #     self.object_type_combo.addItem("Error: Client not available.")
        #     self.object_type_combo.setEnabled(False)
        #     self.busy_signal.emit(False)
        #     return

        self._active_fetch_ot_thread = ApiClientThread(
            operation_name="list_object_types",
            parent=self,
        )
        main_win = self._find_main_window()
        if main_win:
            self._active_fetch_ot_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._show_error_message("Internal error: Cannot connect to API handler for object types.")
            self._active_fetch_ot_thread.deleteLater()
            self._active_fetch_ot_thread = None
            self.busy_signal.emit(False)
            self.object_type_combo.setEnabled(True) # Re-enable on error
            return

        self._active_fetch_ot_thread.result_ready.connect(self._on_object_types_loaded)
        self._active_fetch_ot_thread.error_occurred.connect(self._show_error_message) # Generic error handler
        self._active_fetch_ot_thread.finished.connect(self._cleanup_fetch_ot_thread)
        self._active_fetch_ot_thread.start()

    @Slot()
    def _cleanup_fetch_ot_thread(self) -> None:
        self.busy_signal.emit(False)
        self.object_type_combo.setEnabled(True) # Re-enable after attempt
        if self._active_fetch_ot_thread:
            self._active_fetch_ot_thread.deleteLater()
            self._active_fetch_ot_thread = None

    @Slot(object) # Changed from list
    def _on_object_types_loaded(self, result: Any) -> None:
        if not isinstance(result, list):
            self._show_error_message(f"Unexpected data type for object types: {type(result)}")
            self.object_type_combo.clear()
            self.object_type_combo.addItem("Error loading types.")
            self.object_type_combo.setEnabled(False)
            return

        object_types: list[ObjectTypeDefinition] = result
        self.object_types_cache = object_types
        self.object_type_combo.clear()
        if not object_types:
            self.object_type_combo.addItem("No object types found.")
            self.object_type_combo.setEnabled(False)
            return

        self.object_type_combo.addItem("Select Object Type...")
        for ot_def in object_types:
            self.object_type_combo.addItem(ot_def.name, userData=ot_def)
        # self.object_type_combo.setEnabled(True) # Handled by cleanup

        if self.is_edit_mode and self.embedding_definition:
            idx = self.object_type_combo.findText(self.embedding_definition.object_type_name)
            if idx != -1:
                self.object_type_combo.setCurrentIndex(idx) # This will trigger _on_object_type_changed
            else:
                self._on_object_type_changed(0)
        else:
            self.object_type_combo.setCurrentIndex(0)

    def _on_object_type_changed(self, index: int) -> None:
        self.source_property_combo.clear()
        self.source_property_combo.setEnabled(False)
        selected_ot_def = self.object_type_combo.itemData(index)

        if not selected_ot_def or not isinstance(selected_ot_def, ObjectTypeDefinition):
            self.source_property_combo.setPlaceholderText("Select Source Property...")
            return

        # Properties are now assumed to be part of the ObjectTypeDefinition from list_object_types
        self._populate_source_properties(selected_ot_def)


    def _populate_source_properties(self, ot_def: ObjectTypeDefinition) -> None:
        self.source_property_combo.clear()
        if not ot_def.properties:
            self.source_property_combo.addItem("No properties found for this type.")
            self.source_property_combo.setEnabled(False)
            return

        self.source_property_combo.addItem("Select Source Property...")
        for prop_def in ot_def.properties:
            # Typically, embeddings are created from text-like fields
            # Add filtering if necessary, e.g., if prop_def.data_type == PropertyDataType.TEXT:
            self.source_property_combo.addItem(prop_def.name, userData=prop_def)
        self.source_property_combo.setEnabled(True)

        if self.is_edit_mode and self.embedding_definition and \
           self.embedding_definition.object_type_name == ot_def.name:
            idx = self.source_property_combo.findText(self.embedding_definition.source_property_name)
            if idx != -1:
                self.source_property_combo.setCurrentIndex(idx)
        else:
             self.source_property_combo.setCurrentIndex(0) # Ensure placeholder

    def _populate_fields(self) -> None:
        """Populates fields if in edit mode."""
        if not self.embedding_definition:
            return
        self.name_edit.setText(self.embedding_definition.name)
        # Object type and source property are handled by their respective load/change signals
        model_name_to_display = self.embedding_definition.embedding_model
        if model_name_to_display.startswith("huggingface/"):
            model_name_to_display = model_name_to_display.replace("huggingface/", "", 1)
        self.model_edit.setText(model_name_to_display)
        self.dimensions_spinbox.setValue(self.embedding_definition.dimensions or 0)
        self.description_edit.setText(self.embedding_definition.description or "")

    def get_embedding_definition_data(self) -> Optional[EmbeddingDefinition]:
        """Constructs an EmbeddingDefinition model from dialog fields."""
        name = self.name_edit.text().strip()
        if not name:
            self._show_error_message("Definition Name cannot be empty.")
            return None

        object_type_index = self.object_type_combo.currentIndex()
        if object_type_index <= 0: # 0 is placeholder
            self._show_error_message("Object Type must be selected.")
            return None
        object_type_name = self.object_type_combo.currentText()

        source_property_index = self.source_property_combo.currentIndex()
        if source_property_index <= 0: # 0 is placeholder
            self._show_error_message("Source Property must be selected.")
            return None
        source_property_name = self.source_property_combo.currentText()

        embedding_model = self.model_edit.text().strip()
        if not embedding_model:
            self._show_error_message("Embedding Model cannot be empty.")
            return None

        dimensions_val = self.dimensions_spinbox.value()
        dimensions = dimensions_val if dimensions_val > 0 else None

        description = self.description_edit.toPlainText().strip() or None

        return EmbeddingDefinition(
            name=name,
            object_type_name=object_type_name,
            source_property_name=source_property_name,
            embedding_model=embedding_model,
            dimensions=dimensions,
            description=description,
        )

    def accept(self) -> None:
        """Handles the OK button click."""
        ed_data = self.get_embedding_definition_data()
        if not ed_data:
            return # Error message already shown

        if self.is_edit_mode and self.embedding_definition:
            # Placeholder for update logic
            # self.update_thread = UpdateEmbeddingDefinitionThread(self.client, ed_data)
            # self.update_thread.finished.connect(self._on_save_finished)
            # self.update_thread.error.connect(self._on_save_error)
            # self.update_thread.start()
            QMessageBox.information(self, "Not Implemented", "Editing is not yet implemented.")
            # For now, just accept if data is valid for testing
            super().accept()

        else: # Create mode
            # Client connection check will be handled by MainWindow
            # if not self.client_ref or not self.client_ref._is_connected:
            #     self._show_error_message("Client not available or not connected for create.")
            #     return

            if self._active_create_ed_thread and self._active_create_ed_thread.isRunning():
                self._show_error_message("Create operation already in progress.")
                return

            self._active_create_ed_thread = ApiClientThread(
                "create_embedding_definition", # operation_name passed positionally
                ed_data,                       # ed_data for *args
                parent=self,                    # parent as keyword argument
            )
            main_win = self._find_main_window()
            if main_win:
                self._active_create_ed_thread.apiRequestReady.connect(main_win.handleApiRequest)
            else:
                self._on_save_error("Internal error: Cannot connect to API handler.")
                self._active_create_ed_thread.deleteLater()
                self._active_create_ed_thread = None
                return

            self._active_create_ed_thread.result_ready.connect(self._on_save_finished)
            self._active_create_ed_thread.error_occurred.connect(self._on_save_error)
            self._active_create_ed_thread.finished.connect(self._cleanup_create_ed_thread)
            self._active_create_ed_thread.start()
            self.setEnabled(False) # Disable dialog while saving
            self.busy_signal.emit(True)


    @Slot(object) # Changed from EmbeddingDefinition
    def _on_save_finished(self, result: Any) -> None:
        # self.setEnabled(True) # Handled by cleanup
        # self.busy_signal.emit(False) # Handled by cleanup
        if not isinstance(result, EmbeddingDefinition):
            self._on_save_error(f"Unexpected result type from save operation: {type(result)}")
            return

        created_def: EmbeddingDefinition = result
        QMessageBox.information(
            self,
            "Success",
            f"Embedding Definition '{created_def.name}' saved successfully.",
        )
        self.embedding_definition = created_def
        super().accept()

    @Slot(str)
    def _on_save_error(self, error_message: str) -> None:
        # self.setEnabled(True) # Handled by cleanup
        # self.busy_signal.emit(False) # Handled by cleanup
        self._show_error_message(error_message)

    @Slot()
    def _cleanup_create_ed_thread(self) -> None: # Renamed
        self.setEnabled(True)
        self.busy_signal.emit(False)
        if self._active_create_ed_thread:
            self._active_create_ed_thread.deleteLater()
            self._active_create_ed_thread = None

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
        print("EmbeddingDefinitionDialog: Could not find MainWindow instance.")
        return None

    def _show_error_message(self, message: str) -> None:
        self.busy_signal.emit(False) # Ensure busy is off on error
        QMessageBox.warning(self, "Error", message)

    def closeEvent(self, event: Any) -> None: # Added type hint
        threads_to_manage = [
            self._active_fetch_ot_thread,
            self._active_create_ed_thread,
        ]
        for thread_instance in threads_to_manage:
            if thread_instance and thread_instance.isRunning():
                thread_instance.quit()
                if not thread_instance.wait(500):
                    thread_instance.terminate()
                    thread_instance.wait()
        self._active_fetch_ot_thread = None
        self._active_create_ed_thread = None
        super().closeEvent(event)

if __name__ == "__main__":
    # Example Usage (requires a running Grizabella server or mock client)
    app = QApplication([])

    # --- Mock GrizabellaClient for testing ---
    class MockProperty(PropertyDefinition): # Keep this simple for mock
        name: str
        data_type: PropertyDataType = PropertyDataType.TEXT # Corrected type
        is_primary_key: bool = False
        is_nullable: bool = True
        is_indexed: bool = False
        is_unique: bool = False
        description: Optional[str] = None


    class MockObjectType(ObjectTypeDefinition): # Keep this simple for mock
        name: str
        description: Optional[str] = None
        properties: list[PropertyDefinition] # Corrected type


    class MockGrizabellaClient: # Renamed to avoid conflict if real Grizabella is imported
        def list_object_types(self) -> list[MockObjectType]: # Use MockObjectType for return
            # Ensure properties are of type PropertyDefinition for MockObjectType
            doc_props = [
                PropertyDefinition(name="content", data_type=PropertyDataType.TEXT),
                PropertyDefinition(name="title", data_type=PropertyDataType.TEXT),
            ]
            person_props = [
                PropertyDefinition(name="bio", data_type=PropertyDataType.TEXT),
                PropertyDefinition(name="full_name", data_type=PropertyDataType.TEXT),
            ]
            return [
                MockObjectType(name="Document", properties=doc_props),
                MockObjectType(name="Person", properties=person_props),
                MockObjectType(name="Product", properties=[]), # Type with no properties
            ]

        def get_object_type_definition(self, name: str) -> Optional[MockObjectType]: # Use MockObjectType
            ots = self.list_object_types() # This now returns List[MockObjectType]
            for ot in ots:
                if ot.name == name:
                    return ot # ot is MockObjectType
            return None

        def create_embedding_definition(self, ed: EmbeddingDefinition) -> EmbeddingDefinition:
            # Simulate successful creation
            return ed
    # --- End Mock GrizabellaClient ---

    mock_client_instance = MockGrizabellaClient() # Renamed instance
    dialog = EmbeddingDefinitionDialog(client=mock_client_instance) # type: ignore

    if dialog.exec():
        new_ed = dialog.get_embedding_definition_data()
        if new_ed:
            pass
    else:
        pass

    app.exec()
