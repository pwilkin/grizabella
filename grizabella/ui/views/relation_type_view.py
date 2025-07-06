"""View for managing RelationTypeDefinitions."""
import logging  # Added
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import Qt, Signal, Slot  # Removed QThread
from PySide6.QtWidgets import (  # Added QApplication
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from grizabella.api.client import Grizabella
from grizabella.core.models import PropertyDataType, PropertyDefinition, RelationTypeDefinition
from grizabella.ui.dialogs.relation_type_dialog import RelationTypeDialog
from grizabella.ui.threads.api_client_thread import ApiClientThread  # Import new thread

# from grizabella.ui.main_window import MainWindow # For connecting signals <- REMOVED FOR CIRCULAR IMPORT


if TYPE_CHECKING:
    from grizabella.ui.main_window import MainWindow


class RelationTypeView(QWidget):
    """Widget for displaying and managing RelationTypeDefinitions."""

    busy_signal = Signal(bool)

    def __init__(self, grizabella_client: Optional[Grizabella] = None, parent=None) -> None:
        super().__init__(parent)
        self.grizabella_client = grizabella_client # Will be set by MainWindow
        self._logger = logging.getLogger(__name__)
        self._active_list_rt_thread: Optional[ApiClientThread] = None
        self._active_delete_rt_thread: Optional[ApiClientThread] = None
        self._rtd_name_for_delete_success: Optional[str] = None
        self.current_relation_types: list[RelationTypeDefinition] = []

        self._init_ui()
        # _connect_signals is not needed as connections are made when threads are created

        if self.grizabella_client:
            self.refresh_relation_types()
        else:
            self.list_widget.addItem("Grizabella client not available.") # Show message in list
            self.list_widget.setEnabled(False)
            self.new_button.setEnabled(False)
            self.edit_button.setEnabled(False)
            self.delete_button.setEnabled(False)


    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # Action Buttons
        actions_layout = QHBoxLayout()
        self.new_button = QPushButton("New Relation Type")
        self.edit_button = QPushButton("Edit Selected")
        self.delete_button = QPushButton("Delete Selected")
        self.refresh_button = QPushButton("Refresh List")

        actions_layout.addWidget(self.new_button)
        actions_layout.addWidget(self.edit_button)
        actions_layout.addWidget(self.delete_button)
        actions_layout.addStretch()
        actions_layout.addWidget(self.refresh_button)
        main_layout.addLayout(actions_layout)

        # Splitter for List and Details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: List of Relation Types
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(250)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        splitter.addWidget(self.list_widget)

        # Right side: Details of selected Relation Type
        details_container = QWidget()
        details_layout = QVBoxLayout(details_container)

        self.details_area_label = QLabel("Selected Relation Type Details:")
        details_layout.addWidget(self.details_area_label)

        self.details_name_label = QLabel("<b>Name:</b>")
        self.details_name_value = QLabel()
        details_layout.addWidget(self.details_name_label)
        details_layout.addWidget(self.details_name_value)

        self.details_desc_label = QLabel("<b>Description:</b>")
        self.details_desc_value = QTextBrowser()
        self.details_desc_value.setFixedHeight(80)
        self.details_desc_value.setReadOnly(True)
        details_layout.addWidget(self.details_desc_label)
        details_layout.addWidget(self.details_desc_value)

        self.details_source_label = QLabel("<b>Source Object Type(s):</b>")
        self.details_source_value = QLabel()
        details_layout.addWidget(self.details_source_label)
        details_layout.addWidget(self.details_source_value)

        self.details_target_label = QLabel("<b>Target Object Type(s):</b>")
        self.details_target_value = QLabel()
        details_layout.addWidget(self.details_target_label)
        details_layout.addWidget(self.details_target_value)

        self.properties_label = QLabel("<b>Properties:</b>")
        details_layout.addWidget(self.properties_label)
        self.properties_table = QTableWidget()
        self.properties_table.setColumnCount(6) # Name, Data Type, Nullable, Indexed, Unique, Description
        self.properties_table.setHorizontalHeaderLabels([
            "Name", "Data Type", "Nullable", "Indexed", "Unique", "Description",
        ])
        self.properties_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.properties_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.properties_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.properties_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # Read-only
        self.properties_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        details_layout.addWidget(self.properties_table)

        details_layout.addStretch()
        splitter.addWidget(details_container)
        splitter.setStretchFactor(0, 1) # List widget
        splitter.setStretchFactor(1, 3) # Details area

        main_layout.addWidget(splitter)

        self.edit_button.setEnabled(False) # Disabled until selection
        self.delete_button.setEnabled(False) # Disabled until selection
        self._clear_details()

    def _connect_signals(self) -> None:
        self.new_button.clicked.connect(self._on_new_relation_type)
        self.edit_button.clicked.connect(self._on_edit_relation_type) # Placeholder
        self.delete_button.clicked.connect(self._on_delete_relation_type)
        self.refresh_button.clicked.connect(self.refresh_relation_types)
        self.list_widget.currentItemChanged.connect(self._on_list_selection_changed)

    def set_grizabella_client(self, client: Optional["Grizabella"]) -> None:
        self.grizabella_client = client
        if self.grizabella_client and self.grizabella_client._is_connected:
            self.new_button.setEnabled(True)
            self.refresh_button.setEnabled(True) # Enable refresh button
            self.refresh_relation_types()
        else:
            self.new_button.setEnabled(False)
            self.edit_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.refresh_button.setEnabled(False) # Disable refresh button
            self.list_widget.clear()
            self.list_widget.addItem("Grizabella client not available.")
            self.list_widget.setEnabled(False)
            self._clear_details()
            # No active threads should exist if client is not set or disconnected
            if self._active_list_rt_thread:
                self._active_list_rt_thread.deleteLater()
                self._active_list_rt_thread = None
            if self._active_delete_rt_thread:
                self._active_delete_rt_thread.deleteLater()
                self._active_delete_rt_thread = None


    @Slot()
    def refresh_relation_types(self) -> None:
        self.busy_signal.emit(True)
        self.list_widget.setEnabled(False)
        self.refresh_button.setEnabled(False) # Disable while refreshing
        self._clear_details()
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)

        if self._active_list_rt_thread and self._active_list_rt_thread.isRunning():
            self._logger.warning("List relation types already in progress.")
            self.busy_signal.emit(False)
            self.list_widget.setEnabled(True) # Re-enable if we don't proceed
            self.refresh_button.setEnabled(True)
            return

        if not self.grizabella_client or not self.grizabella_client._is_connected:
            QMessageBox.warning(self, "Client Error", "Grizabella client not available or not connected.")
            self.list_widget.clear()
            self.list_widget.addItem("Client not available or not connected.")
            self.busy_signal.emit(False)
            self.list_widget.setEnabled(True) # Re-enable
            self.refresh_button.setEnabled(True)
            return

        self.list_widget.clear() # Clear before showing "Loading..."
        self.list_widget.addItem("Loading relation types...")

        self._active_list_rt_thread = ApiClientThread(
            operation_name="list_relation_types",
            parent=self,
        )
        main_win = self._find_main_window()
        if main_win:
            self._active_list_rt_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._handle_api_error("list_relation_types", "Internal error: Cannot connect to API handler.")
            self._active_list_rt_thread.deleteLater()
            self._active_list_rt_thread = None
            # busy_signal and buttons re-enabled by _handle_api_error via _on_list_rt_finished
            return

        self._active_list_rt_thread.result_ready.connect(self._handle_relation_types_loaded)
        self._active_list_rt_thread.error_occurred.connect(
            lambda err_msg: self._handle_api_error("list_relation_types", err_msg),
        )
        self._active_list_rt_thread.finished.connect(self._on_list_rt_finished)
        self._active_list_rt_thread.start()


    @Slot(object) # Changed from list
    def _handle_relation_types_loaded(self, result: Any) -> None:
        # self.list_widget.setEnabled(True) # Handled by finished
        if not isinstance(result, list):
            self._handle_api_error("list_relation_types", f"Unexpected data type for relation types: {type(result)}")
            return

        rtds: list[RelationTypeDefinition] = result
        self.list_widget.clear() # Clear "Loading..." message
        self.current_relation_types = sorted(rtds, key=lambda r: r.name)
        if not self.current_relation_types:
            self.list_widget.addItem("No relation types found.")
            self._clear_details()
        else:
            for rtd_item in self.current_relation_types:
                item = QListWidgetItem(rtd_item.name)
                item.setData(Qt.ItemDataRole.UserRole, rtd_item)
                self.list_widget.addItem(item)
            if self.list_widget.count() > 0: # Select first item if list is populated
                self.list_widget.setCurrentRow(0)
        self._on_list_selection_changed(self.list_widget.currentItem(), None) # Update details for selection
        # self._update_action_buttons_state() # Called by _on_list_selection_changed

    @Slot()
    def _on_list_rt_finished(self) -> None:
        self.busy_signal.emit(False)
        self.list_widget.setEnabled(True)
        self.refresh_button.setEnabled(True)
        if self._active_list_rt_thread:
            self._active_list_rt_thread.deleteLater()
            self._active_list_rt_thread = None
        # Ensure selection state of buttons is correct after load
        self._on_list_selection_changed(self.list_widget.currentItem(), None)

    def _clear_details(self) -> None:
        self.details_name_value.setText("<i>N/A</i>")
        self.details_desc_value.setPlainText("<i>N/A</i>")
        self.details_source_value.setText("<i>N/A</i>")
        self.details_target_value.setText("<i>N/A</i>")
        self.properties_table.setRowCount(0)

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_list_selection_changed(self, current: Optional[QListWidgetItem],
                                   _previous: Optional[QListWidgetItem]) -> None: # Mark unused
        if current:
            rtd: Optional[RelationTypeDefinition] = current.data(Qt.ItemDataRole.UserRole)
            if rtd:
                self.details_name_value.setText(rtd.name)
                self.details_desc_value.setPlainText(
                    rtd.description or "<i>No description.</i>",
                )
                self.details_source_value.setText(
                    ", ".join(rtd.source_object_type_names) or "<i>Any</i>",
                )
                self.details_target_value.setText(
                    ", ".join(rtd.target_object_type_names) or "<i>Any</i>",
                )

                self.properties_table.setRowCount(0)
                for prop_def in rtd.properties:
                    row_pos = self.properties_table.rowCount()
                    self.properties_table.insertRow(row_pos)
                    self.properties_table.setItem(row_pos, 0,
                                                  QTableWidgetItem(prop_def.name))
                    self.properties_table.setItem(row_pos, 1,
                                                  QTableWidgetItem(prop_def.data_type.value))

                    nullable_item = QTableWidgetItem(
                        "Yes" if prop_def.is_nullable else "No",
                    )
                    indexed_item = QTableWidgetItem(
                        "Yes" if prop_def.is_indexed else "No",
                    )
                    unique_item = QTableWidgetItem(
                        "Yes" if prop_def.is_unique else "No",
                    )

                    # Center align boolean-like columns
                    for item_widget in [nullable_item, indexed_item, unique_item]:
                        item_widget.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                    self.properties_table.setItem(row_pos, 2, nullable_item)
                    self.properties_table.setItem(row_pos, 3, indexed_item)
                    self.properties_table.setItem(row_pos, 4, unique_item)
                    self.properties_table.setItem(
                        row_pos, 5, QTableWidgetItem(prop_def.description or ""),
                    )

                self.edit_button.setEnabled(True)
                self.delete_button.setEnabled(True)
                return

        self._clear_details()
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    @Slot()
    def _on_new_relation_type(self) -> None:
        if not self.grizabella_client:
            QMessageBox.warning(self, "Client Error", "Grizabella client not available.")
            return

        dialog = RelationTypeDialog(self.grizabella_client, parent=self)
        dialog.relation_type_changed.connect(self.refresh_relation_types)
        dialog.exec()

    @Slot()
    def _on_edit_relation_type(self) -> None:
        # Placeholder for edit functionality
        current_item = self.list_widget.currentItem()
        if not current_item or not self.grizabella_client:
            QMessageBox.warning(self, "Selection Error", "Please select a relation type to edit.")
            return

        rtd_to_edit: Optional[RelationTypeDefinition] = current_item.data(Qt.ItemDataRole.UserRole)
        if not rtd_to_edit:
            return

        # For now, just show a message. Full edit dialog would be similar to new but pre-filled.
        QMessageBox.information(self, "Not Implemented", f"Editing '{rtd_to_edit.name}' is not yet fully implemented. "
                                                        "Please delete and re-create if changes are needed.")
        # dialog = RelationTypeDialog(self.grizabella_client, existing_rtd=rtd_to_edit, parent=self)
        # dialog.relation_type_changed.connect(self.refresh_relation_types)
        # dialog.exec()


    @Slot()
    def _on_delete_relation_type(self) -> None:
        current_item = self.list_widget.currentItem()
        if not current_item or not self.grizabella_client: # Removed api_worker check
            QMessageBox.warning(self, "Selection Error", "Please select a relation type to delete or client not available.")
            return

        rtd_to_delete: Optional[RelationTypeDefinition] = current_item.data(Qt.ItemDataRole.UserRole)
        if not rtd_to_delete:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the relation type '{rtd_to_delete.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.busy_signal.emit(True)
            self.delete_button.setEnabled(False)
            self._rtd_name_for_delete_success = rtd_to_delete.name

            if self._active_delete_rt_thread and self._active_delete_rt_thread.isRunning():
                QMessageBox.information(self, "In Progress", "Another delete operation is already in progress.")
                self.busy_signal.emit(False)
                self.delete_button.setEnabled(True) # Re-enable if not proceeding
                return

            if not self.grizabella_client._is_connected:
                self._handle_api_error("delete_relation_type", "Client not connected.")
                # busy_signal and button re-enabled by _handle_api_error via _on_delete_rt_finished
                return

            self._active_delete_rt_thread = ApiClientThread(
                "delete_relation_type", # operation_name passed positionally
                rtd_to_delete.name,     # type_name for *args
                parent=self,
            )
            main_win = self._find_main_window()
            if main_win:
                self._active_delete_rt_thread.apiRequestReady.connect(main_win.handleApiRequest)
            else:
                self._handle_api_error("delete_relation_type", "Internal error: Cannot connect to API handler.")
                self._active_delete_rt_thread.deleteLater()
                self._active_delete_rt_thread = None
                return

            self._active_delete_rt_thread.result_ready.connect(self._handle_delete_success)
            self._active_delete_rt_thread.error_occurred.connect(
                lambda err_msg: self._handle_api_error("delete_relation_type", err_msg),
            )
            self._active_delete_rt_thread.finished.connect(self._on_delete_rt_finished)
            self._active_delete_rt_thread.start()

    @Slot(object) # Changed from str
    def _handle_delete_success(self, result: Any) -> None:
        rtd_name = self._rtd_name_for_delete_success
        if result is None or (isinstance(result, bool) and result): # API might return None or True
            QMessageBox.information(self, "Delete Successful", f"Relation type '{rtd_name}' deleted successfully.")
            self.refresh_relation_types()
        else:
            self._handle_api_error("delete_relation_type", f"Failed to delete '{rtd_name}'. API returned: {result}")
        self._rtd_name_for_delete_success = None


    @Slot(str, str) # Added operation_name
    def _handle_api_error(self, operation_name: str, error_message: str) -> None:
        title = "API Error"
        if operation_name == "list_relation_types":
            title = "Load Failed"
            self.list_widget.clear()
            self.list_widget.addItem("Error loading relation types.")
            self._clear_details()
        elif operation_name == "delete_relation_type":
            title = "Delete Failed"

        QMessageBox.critical(self, title, error_message)
        # Ensure UI is re-enabled by the finished signal of the thread
        self.busy_signal.emit(False) # Ensure busy is off

    @Slot()
    def _on_delete_rt_finished(self) -> None:
        self.busy_signal.emit(False)
        # Re-enable delete button based on current selection
        current_item = self.list_widget.currentItem()
        self.delete_button.setEnabled(bool(current_item and current_item.data(Qt.ItemDataRole.UserRole)))
        if self._active_delete_rt_thread:
            self._active_delete_rt_thread.deleteLater()
            self._active_delete_rt_thread = None
        self._rtd_name_for_delete_success = None

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
        self._logger.warning("Could not find MainWindow instance for RelationTypeView.")
        return None

    def closeEvent(self, event: Any) -> None:
        self._logger.debug(f"RelationTypeView closeEvent triggered for {self}.")
        threads_to_manage = [
            ("_active_list_rt_thread", self._active_list_rt_thread),
            ("_active_delete_rt_thread", self._active_delete_rt_thread),
        ]
        for name, thread_instance in threads_to_manage:
            if thread_instance and thread_instance.isRunning():
                self._logger.info(f"RelationTypeView: Worker thread '{name}' ({thread_instance}) is running. Attempting to quit/wait.")
                thread_instance.quit()
                if not thread_instance.wait(500):
                    self._logger.warning(f"RelationTypeView: Worker thread '{name}' ({thread_instance}) did not finish. Terminating.")
                    thread_instance.terminate()
                    thread_instance.wait()
                else:
                    self._logger.info(f"RelationTypeView: Worker thread '{name}' ({thread_instance}) finished.")
            elif thread_instance: # Exists but not running
                thread_instance.deleteLater()

        self._active_list_rt_thread = None
        self._active_delete_rt_thread = None
        super().closeEvent(event)


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    # For mock client in __main__
    from grizabella.core.models import ObjectTypeDefinition

    class MockGrizabella: # Renamed to match Grizabella type hint
        def __init__(self) -> None:
            self._rtds = [
                RelationTypeDefinition(name="RELATES_TO", source_object_type_names=["Doc"],
                                       target_object_type_names=["Doc"],
                                       properties=[PropertyDefinition(name="strength",
                                                                     data_type=PropertyDataType.FLOAT)]),
                RelationTypeDefinition(name="HAS_CHAPTER",
                                       description="A book has chapters",
                                       source_object_type_names=["Book"],
                                       target_object_type_names=["Chapter"],
                                       properties=[]),
                RelationTypeDefinition(name="CITES",
                                       source_object_type_names=["Paper"],
                                       target_object_type_names=["Paper"],
                                       properties=[PropertyDefinition(name="context",
                                                                     data_type=PropertyDataType.TEXT,
                                                                     is_nullable=True)]),
            ]
        def list_relation_types(self) -> list[RelationTypeDefinition]:
            return self._rtds

        def delete_relation_type(self, rtd_name: str) -> None:
            self._rtds = [rtd for rtd in self._rtds if rtd.name != rtd_name]

        def list_object_types(self) -> list: # For the dialog
            return [
                ObjectTypeDefinition(name="Doc", properties=[]),
                ObjectTypeDefinition(name="Book", properties=[]),
                ObjectTypeDefinition(name="Chapter", properties=[]),
                ObjectTypeDefinition(name="Paper", properties=[]),
            ]

        def create_relation_type(self,
                                 rtd_model: RelationTypeDefinition,
                                ) -> RelationTypeDefinition:
            self._rtds.append(rtd_model)
            return rtd_model


    app = QApplication(sys.argv)
    mock_client_instance = MockGrizabella() # type: ignore

    main_view = RelationTypeView(grizabella_client=mock_client_instance) # type: ignore
    main_view.setWindowTitle("Relation Types Management (Test)")
    main_view.setGeometry(100, 100, 900, 600)
    main_view.show()

    sys.exit(app.exec())
