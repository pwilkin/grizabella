import uuid
from typing import TYPE_CHECKING, Any, Optional  # Added TYPE_CHECKING

from PySide6.QtCore import QDateTime, QStringListModel, Qt, Signal  # Added QStringListModel
from PySide6.QtWidgets import (
    QApplication,  # Added
    QCheckBox,
    QComboBox,
    QCompleter,  # Added QCompleter
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from grizabella.api.client import Grizabella
from grizabella.core.models import (
    ObjectInstance,  # Added ObjectInstance
    PropertyDataType,
    RelationInstance,
    RelationTypeDefinition,
)
from grizabella.ui.threads.api_client_thread import ApiClientThread  # Corrected import path

# from grizabella.ui.main_window import MainWindow # For connecting signals <- REMOVED FOR CIRCULAR IMPORT

if TYPE_CHECKING:
    from grizabella.ui.main_window import MainWindow


class RelationInstanceDialog(QDialog):
    """Dialog for creating or editing a RelationInstance.

    This dialog allows users to select a relation type and then choose
    source and target object instances using filterable ComboBoxes.
    It also provides fields for standard relation properties like weight
    and any custom properties defined for the selected relation type.
    API calls for fetching object instances and saving the relation
    are handled asynchronously using ApiClientThread.
    """

    relation_saved = Signal(object)  # Emits the saved RelationInstance

    def __init__(
        self,
        grizabella_client: Grizabella,  # Corrected type hint
        relation_types: list[RelationTypeDefinition],
        parent: Optional[QWidget] = None,
        instance_to_edit: Optional[RelationInstance] = None,
        selected_relation_type_name: Optional[str] = None,  # Changed from ID to name
    ) -> None:
        super().__init__(parent)
        self.grizabella_client = grizabella_client
        self.instance_to_edit = instance_to_edit
        # Store by name, as RelationTypeDefinition doesn't have a direct 'id' field in models.py
        self.all_relation_types: dict[str, RelationTypeDefinition] = {
            rt.name: rt for rt in relation_types
        }
        self.current_relation_type: Optional[RelationTypeDefinition] = None
        self._saved_instance: Optional[RelationInstance] = (
            None  # Initialize _saved_instance
        )

        self.mode = "edit" if self.instance_to_edit else "create"
        self.setWindowTitle(
            f"{'Edit' if self.mode == 'edit' else 'Create'} Relation Instance",
        )
        self.setMinimumWidth(500) # Consider increasing width for comboboxes

        self._layout = QVBoxLayout(self)

        # Relation Type Selection
        self.relation_type_combo = QComboBox()
        for rt_def in self.all_relation_types.values():
            # Use rt_def.name as userData since id is not directly on RelationTypeDefinition
            self.relation_type_combo.addItem(f"{rt_def.name}", userData=rt_def.name)
        self.relation_type_combo.currentIndexChanged.connect(
            self._on_relation_type_changed,
        )
        self._layout.addWidget(QLabel("Relation Type:"))
        self._layout.addWidget(self.relation_type_combo)

        # Core Fields
        self.form_layout = QFormLayout()
        self.source_object_combo = self._create_filterable_combobox()
        self.target_object_combo = self._create_filterable_combobox()

        self.weight_spinbox = QDoubleSpinBox()
        self.weight_spinbox.setMinimum(0.0)
        self.weight_spinbox.setMaximum(1.0)  # Assuming weight is between 0 and 1
        self.weight_spinbox.setSingleStep(0.01)
        self.weight_spinbox.setValue(1.0)  # Default weight

        self.form_layout.addRow("Source Object:", self.source_object_combo)
        self.form_layout.addRow("Target Object:", self.target_object_combo)
        self.form_layout.addRow("Weight:", self.weight_spinbox)

        self._layout.addLayout(self.form_layout)

        # Custom Properties Area
        self.custom_props_scroll_area = QScrollArea()
        self.custom_props_scroll_area.setWidgetResizable(True)
        self.custom_props_widget = QWidget()
        self.custom_props_layout = QFormLayout(self.custom_props_widget)
        self.custom_props_scroll_area.setWidget(self.custom_props_widget)
        self._layout.addWidget(QLabel("Custom Properties:"))
        self._layout.addWidget(self.custom_props_scroll_area)
        self.property_widgets: dict[str, QWidget] = {}

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self._layout.addWidget(self.button_box)

        self._api_thread: Optional[ApiClientThread] = None

        # Populate fields if editing or pre-selected type
        if self.instance_to_edit:
            self._populate_for_edit()
        elif selected_relation_type_name:  # Now using name
            idx = self.relation_type_combo.findData(
                selected_relation_type_name,
            )  # Find by name
            if idx != -1:
                self.relation_type_combo.setCurrentIndex(idx)
            elif self.relation_type_combo.count() > 0:
                self.relation_type_combo.setCurrentIndex(0)
        elif self.relation_type_combo.count() > 0:
            self.relation_type_combo.setCurrentIndex(0)  # Select first by default

        self._on_relation_type_changed(
            self.relation_type_combo.currentIndex(),
        )  # Initial population of custom props

    def _create_filterable_combobox(self) -> QComboBox:
        """Helper to create a QComboBox with filtering enabled."""
        combobox = QComboBox()
        combobox.setEditable(True)
        combobox.setInsertPolicy(QComboBox.InsertPolicy.NoInsert) # Important for completer

        completer = QCompleter(self)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains) # Filter as user types
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        combobox.setCompleter(completer)

        # Update completer model when combobox text changes (for filtering)
        # Or, more simply, the completer will use the combobox's model directly if not set.
        # We will populate a QStringListModel for the completer.
        return combobox

    def _populate_object_instance_combobox(
        self,
        combobox: QComboBox,
        object_type_name: str,
        selected_instance_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Fetches and populates a QComboBox with ObjectInstances of a given type."""
        combobox.clear()
        completer_model = QStringListModel([], self) # Model for QCompleter

        if not self.grizabella_client or not self.grizabella_client._is_connected:
            QMessageBox.warning(self, "API Error", "Grizabella client not connected.")
            combobox.setEnabled(False)
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        try:
            # Use find_objects instead of get_object_instances_by_type_name
            instances: list[ObjectInstance] = (
                self.grizabella_client.find_objects(
                    type_name=object_type_name,
                )
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "API Error",
                f"Failed to fetch object instances for type '{object_type_name}': {e}",
            )
            instances = []
            combobox.setEnabled(False)
            # Consider disabling OK button if this is critical
            # self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)


        if not instances:
            combobox.addItem("No instances available", userData=None)
            combobox.setEnabled(False)
            # self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            combobox.setEnabled(True)
            display_texts = []
            for instance in instances:
                # Access name from properties dict, fallback to id
                instance_name = instance.properties.get("name")
                display_text = (
                    f"{instance_name} ({instance.id})"
                    if instance_name and str(instance_name).strip()
                    else str(instance.id)
                )
                combobox.addItem(display_text, userData=instance.id)
                display_texts.append(display_text)

            completer_model.setStringList(display_texts)
            active_completer = combobox.completer()
            if active_completer:
                active_completer.setModel(completer_model)
                # Optionally, ensure the completer's popup is updated if text is already in lineEdit
                # active_completer.complete()

            if selected_instance_id:
                for i in range(combobox.count()):
                    if combobox.itemData(i) == selected_instance_id:
                        combobox.setCurrentIndex(i)
                        break
        self._update_ok_button_state()


    def _populate_for_edit(self) -> None:
        if not self.instance_to_edit:
            return

        rt_name = self.instance_to_edit.relation_type_name
        idx = self.relation_type_combo.findData(rt_name)
        if idx != -1:
            self.relation_type_combo.setCurrentIndex(idx)
            self.relation_type_combo.setEnabled(False)
        else:
            QMessageBox.warning(
                self, "Error", f"Could not find relation type '{rt_name}' for editing.",
            )
            # Dialog might be unusable, consider disabling fields or closing

        # _on_relation_type_changed will be called, which populates comboboxes.
        # We need to ensure selected_instance_id is passed correctly there,
        # or call _populate_object_instance_combobox directly here after
        # current_relation_type is set.
        # For now, _on_relation_type_changed will handle initial population,
        # then we set the values if editing.

        # The actual setting of combobox values will happen after _on_relation_type_changed
        # has populated them. We can defer this or ensure _on_relation_type_changed
        # itself handles the selected_instance_id for edit mode.

        # Let's ensure _on_relation_type_changed handles this.
        # We will call _on_relation_type_changed which will then call
        # _populate_object_instance_combobox.
        # The selected IDs will be passed to _populate_object_instance_combobox
        # from _on_relation_type_changed when in edit mode.

        self.weight_spinbox.setValue(self.instance_to_edit.weight)
        # Custom properties are handled by _on_relation_type_changed.

    def _on_relation_type_changed(self, index: int) -> None:
        selected_rt_name = self.relation_type_combo.itemData(index)
        if selected_rt_name:
            self.current_relation_type = self.all_relation_types.get(selected_rt_name)
            if self.current_relation_type:
                source_id_to_select = None
                target_id_to_select = None
                if self.mode == "edit" and self.instance_to_edit:
                    # Ensure the relation type matches before trying to use instance IDs
                    if self.instance_to_edit.relation_type_name == self.current_relation_type.name:
                        source_id_to_select = self.instance_to_edit.source_object_instance_id
                        target_id_to_select = self.instance_to_edit.target_object_instance_id

                # Assuming the first type name in the list is the relevant one for the dialog
                # This might need refinement if a RelationTypeDefinition can link multiple distinct types
                # in a way that requires user selection beyond what's currently implemented.
                source_type_name = self.current_relation_type.source_object_type_names[0] if self.current_relation_type.source_object_type_names else None
                target_type_name = self.current_relation_type.target_object_type_names[0] if self.current_relation_type.target_object_type_names else None

                if source_type_name:
                    self._populate_object_instance_combobox(
                        self.source_object_combo,
                        source_type_name,
                        selected_instance_id=source_id_to_select,
                    )
                else:
                    self.source_object_combo.clear()
                    self.source_object_combo.addItem("Source type not defined", userData=None)
                    self.source_object_combo.setEnabled(False)

                if target_type_name:
                    self._populate_object_instance_combobox(
                        self.target_object_combo,
                        target_type_name,
                        selected_instance_id=target_id_to_select,
                    )
                else:
                    self.target_object_combo.clear()
                    self.target_object_combo.addItem("Target type not defined", userData=None)
                    self.target_object_combo.setEnabled(False)

            self._update_custom_properties_fields()
        else:
            self.current_relation_type = None
            self.source_object_combo.clear()
            self.target_object_combo.clear()
            self.source_object_combo.setEnabled(False)
            self.target_object_combo.setEnabled(False)
            self._clear_custom_properties_fields()
        self._update_ok_button_state()


    def _clear_custom_properties_fields(self) -> None:
        for widget in self.property_widgets.values():
            self.custom_props_layout.removeRow(widget)
            widget.deleteLater()
        self.property_widgets.clear()

    def _update_custom_properties_fields(self) -> None:
        self._clear_custom_properties_fields()
        # RelationTypeDefinition has 'properties: List[PropertyDefinition]'
        if not self.current_relation_type or not self.current_relation_type.properties:
            return

        # Iterate through the list of PropertyDefinition objects
        for prop_def in self.current_relation_type.properties:
            prop_name = prop_def.name
            label = prop_def.name
            description = prop_def.description or ""
            # prop_def.data_type is an Enum (PropertyDataType)

            editor: QWidget
            prop_type_enum = prop_def.data_type
            current_value = None
            if self.instance_to_edit and prop_name in self.instance_to_edit.properties:
                current_value = self.instance_to_edit.properties[prop_name]

            if prop_type_enum == PropertyDataType.TEXT:
                editor = QLineEdit()
                if current_value is not None:
                    editor.setText(str(current_value))
            elif prop_type_enum == PropertyDataType.INTEGER:
                editor = QSpinBox()
                editor.setRange(-2147483648, 2147483647)  # Max int range
                if current_value is not None:
                    editor.setValue(int(current_value))
            elif prop_type_enum == PropertyDataType.FLOAT:
                editor = QDoubleSpinBox()
                editor.setRange(-1.7976931348623157e308, 1.7976931348623157e308)
                editor.setDecimals(6)  # Default, can be adjusted
                if current_value is not None:
                    editor.setValue(float(current_value))
            elif prop_type_enum == PropertyDataType.BOOLEAN:
                editor = QCheckBox()
                if current_value is not None:
                    editor.setChecked(bool(current_value))
            elif prop_type_enum == PropertyDataType.DATETIME:
                editor = QDateTimeEdit()
                editor.setCalendarPopup(True)
                editor.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
                if current_value is not None:
                    # Assuming current_value is a datetime object or ISO string
                    if isinstance(current_value, str):
                        qdt = QDateTime.fromString(
                            current_value, "yyyy-MM-ddTHH:mm:ssZ",
                        )  # Example format
                        if not qdt.isValid():  # Try with timezone offset
                            qdt = QDateTime.fromString(
                                current_value, Qt.DateFormat.ISODateWithMs,
                            )
                        if not qdt.isValid():  # Try basic ISO
                            qdt = QDateTime.fromString(
                                current_value, Qt.DateFormat.ISODate,
                            )

                        editor.setDateTime(
                            qdt if qdt.isValid() else QDateTime.currentDateTime(),
                        )
                    elif isinstance(
                        current_value, QDateTime,
                    ):  # If it's already QDateTime
                        editor.setDateTime(current_value)
                    # Add handling for Python datetime objects if necessary
                else:
                    editor.setDateTime(QDateTime.currentDateTime())
            elif prop_type_enum == PropertyDataType.UUID:
                editor = QLineEdit()
                if current_value is not None:
                    editor.setText(str(current_value))
            elif prop_type_enum == PropertyDataType.JSON:
                editor = (
                    QLineEdit()
                )  # For simplicity, JSON as string. Could use QTextEdit.
                if current_value is not None:
                    editor.setText(str(current_value))  # Or json.dumps(current_value)
            elif prop_type_enum == PropertyDataType.BLOB:
                editor = (
                    QLineEdit()
                )  # BLOBs are hard to edit directly, show placeholder or path?
                editor.setPlaceholderText("BLOB data (not directly editable)")
                editor.setReadOnly(True)
                if current_value is not None:
                    editor.setText(
                        f"<BLOB data present, {len(current_value)} bytes>"
                        if isinstance(current_value, bytes)
                        else "<BLOB data>",
                    )

            else:  # Default to QLineEdit for unknown or unhandled types
                editor = QLineEdit()
                if current_value is not None:
                    editor.setText(str(current_value))

            if description:
                editor.setToolTip(description)

            self.custom_props_layout.addRow(f"{label}:", editor)
            self.property_widgets[prop_name] = editor

    def _update_ok_button_state(self) -> None:
        """Enable or disable the OK button based on selections."""
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if not ok_button:
            return

        source_selected = self.source_object_combo.currentData() is not None and self.source_object_combo.isEnabled()
        target_selected = self.target_object_combo.currentData() is not None and self.target_object_combo.isEnabled()
        relation_type_selected = self.current_relation_type is not None

        can_proceed = source_selected and target_selected and relation_type_selected

        # Further check: if combobox has only "No instances available", currentData might be None
        # but it's effectively not a valid selection.
        if self.source_object_combo.count() == 1 and self.source_object_combo.itemText(0) == "No instances available":
            can_proceed = False
        if self.target_object_combo.count() == 1 and self.target_object_combo.itemText(0) == "No instances available":
            can_proceed = False

        ok_button.setEnabled(can_proceed)


    def accept(self) -> None:
        """Validates the form data, creates/updates the RelationInstance,
        and attempts to save it via an API call.
        Source and Target object IDs are retrieved from the ComboBox selections.
        """
        if not self.current_relation_type:
            QMessageBox.warning(
                self, "Validation Error", "Please select a relation type.",
            )
            return

        source_id = self.source_object_combo.currentData()
        target_id = self.target_object_combo.currentData()

        if source_id is None:
            QMessageBox.warning(
                self, "Validation Error", "Please select a Source Object.",
            )
            self.source_object_combo.setFocus()
            return
        if target_id is None:
            QMessageBox.warning(
                self, "Validation Error", "Please select a Target Object.",
            )
            self.target_object_combo.setFocus()
            return

        # currentData should already be uuid.UUID if populated correctly
        if not isinstance(source_id, uuid.UUID):
            QMessageBox.warning(self, "Validation Error", "Invalid Source Object ID selected.")
            return
        if not isinstance(target_id, uuid.UUID):
            QMessageBox.warning(self, "Validation Error", "Invalid Target Object ID selected.")
            return

        properties = {}
        if self.current_relation_type and self.current_relation_type.properties:
            for prop_def in self.current_relation_type.properties:
                prop_name = prop_def.name
                widget = self.property_widgets.get(prop_name)

                # value_str = widget.text() # This was for QLineEdit only
                prop_type_enum = prop_def.data_type
                parsed_value: Any = None
                has_value = False

                try:
                    if isinstance(widget, QLineEdit):
                        value_str = widget.text().strip()
                        if value_str:
                            has_value = True
                            if prop_type_enum == PropertyDataType.TEXT:
                                parsed_value = value_str
                            elif prop_type_enum == PropertyDataType.UUID:
                                parsed_value = uuid.UUID(value_str)
                            elif prop_type_enum == PropertyDataType.JSON:
                                # For JSON, we might want to parse it here or send as string
                                parsed_value = value_str  # Assuming it's sent as string
                            # BLOB is read-only, so no value extraction here
                    elif isinstance(widget, QSpinBox):
                        has_value = True  # QSpinBox always has a value
                        parsed_value = widget.value()
                    elif isinstance(widget, QDoubleSpinBox):
                        has_value = True
                        parsed_value = widget.value()
                    elif isinstance(widget, QCheckBox):
                        has_value = True  # QCheckBox always has a state
                        parsed_value = widget.isChecked()
                    elif isinstance(widget, QDateTimeEdit):
                        has_value = True
                        # Convert QDateTime to Python datetime object (UTC) or ISO string
                        # For simplicity, let's use ISO string format that Pydantic can parse
                        parsed_value = (
                            widget.dateTime()
                            .toUTC()
                            .toString(Qt.DateFormat.ISODateWithMs)
                        )

                    if has_value:
                        properties[prop_name] = parsed_value
                    elif prop_def.is_nullable:
                        properties[prop_name] = None
                    else:  # Not nullable and no value (or widget type not handled for value extraction)
                        QMessageBox.warning(
                            self,
                            "Validation Error",
                            f"Property '{prop_name}' is required.",
                        )
                        if widget:
                            widget.setFocus()
                        return

                except ValueError as e:  # Catch UUID conversion errors, etc.
                    QMessageBox.warning(
                        self,
                        "Validation Error",
                        f"Invalid value for property '{prop_name}' ({prop_type_enum.value}): {e}",
                    )
                    if widget:
                        widget.setFocus()
                    return

        relation_data = {
            "relation_type_name": self.current_relation_type.name,  # Use name
            "source_object_instance_id": source_id,
            "target_object_instance_id": target_id,
            "weight": self.weight_spinbox.value(),
            "properties": properties,
        }

        if self.instance_to_edit:
            relation_data["id"] = self.instance_to_edit.id
            relation_data["upsert_date"] = (
                self.instance_to_edit.upsert_date
            )  # Preserve original if not changed by backend

        try:
            relation_instance_model = RelationInstance(**relation_data)
        except Exception as e:  # Catch Pydantic validation errors
            QMessageBox.critical(
                self, "Data Error", f"Error creating relation data model: {e}",
            )
            return

        if not self.grizabella_client or not self.grizabella_client._is_connected:
            self._handle_api_error("Client not available or not connected for saving relation.")
            return

        self.button_box.setEnabled(False) # Disable buttons during operation

        if self._api_thread and self._api_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Save operation already in progress.")
            self.button_box.setEnabled(True) # Re-enable if we don't proceed
            return

        self._api_thread = ApiClientThread(
            "add_relation", # operation_name passed positionally
            relation_instance_model, # Pass model as arg for *args
            parent=self, # Parent for Qt object tree management
        )

        main_win = self._find_main_window()
        if main_win:
            self._api_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._handle_api_error("Internal error: Cannot connect to API handler for saving relation.")
            self._api_thread.deleteLater()
            self._api_thread = None
            self.button_box.setEnabled(True)
            return

        self._api_thread.result_ready.connect(self._handle_save_result)
        self._api_thread.error_occurred.connect(self._handle_api_error)
        # Connect finished to re-enable button box and clean up thread
        self._api_thread.finished.connect(self._on_api_thread_finished)
        self._api_thread.start()

    def _on_api_thread_finished(self) -> None:
        """Called when the API thread finishes, regardless of success or error."""
        self.button_box.setEnabled(True)
        if self._api_thread:
            self._api_thread.deleteLater() # Schedule for cleanup
            self._api_thread = None

    def _handle_save_result(self, result: Any) -> None: # result type is Any from ApiClientThread
        # self.button_box.setEnabled(True) # Handled by _on_api_thread_finished
        if not isinstance(result, RelationInstance):
            self._handle_api_error(f"Unexpected result type from save operation: {type(result)}")
            return

        QMessageBox.information(
            self, "Success", f"Relation instance '{result.id}' saved successfully.",
        )
        self._saved_instance = result
        self.relation_saved.emit(result)
        super().accept()

    def _handle_api_error(self, error_message: str) -> None:
        # self.button_box.setEnabled(True) # Handled by _on_api_thread_finished
        QMessageBox.critical(
            self, "API Error", f"Failed to save relation instance: {error_message}",
        )
        # Dialog remains open for user to correct or cancel

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
        # Consider logging this if a logger is available in the dialog
        print("RelationInstanceDialog: Could not find MainWindow instance.")
        return None

    def get_relation_instance(self) -> Optional[RelationInstance]:
        if self.result() == QDialog.DialogCode.Accepted and self._saved_instance:
            return self._saved_instance
        return None

    def closeEvent(self, event: Any) -> None:
        """Ensure thread is stopped if the dialog is closed."""
        if self._api_thread and self._api_thread.isRunning():
            self._api_thread.quit()
            if not self._api_thread.wait(500): # Wait 0.5 sec
                self._api_thread.terminate()
                self._api_thread.wait()
        self._api_thread = None
        super().closeEvent(event)
