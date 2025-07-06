"""Grizabella Query View.

Provides a UI for constructing and executing various types of queries
against the Grizabella backend, and displaying the results.
"""

import json
import logging  # Add logging
from typing import TYPE_CHECKING, Any, Optional  # Added TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,  # Added for __main__
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from grizabella.api.client import Grizabella
from grizabella.core.models import (
    EmbeddingDefinition as CoreEmbeddingDefinition,
)
from grizabella.core.models import (
    ObjectInstance,
    PropertyDataType,
)
from grizabella.core.models import (
    ObjectTypeDefinition as CoreObjectTypeDefinition,
)
from grizabella.core.models import (
    PropertyDefinition as CorePropertyDefinition,
)
from grizabella.ui.threads.api_client_thread import ApiClientThread

# from grizabella.ui.main_window import MainWindow # For connecting signals <- REMOVED FOR CIRCULAR IMPORT

if TYPE_CHECKING:
    from grizabella.ui.main_window import MainWindow


class QueryView(QWidget):
    """View for constructing and executing queries, and displaying their results."""

    # Signals for API calls
    fetch_object_types_signal = Signal()
    fetch_embedding_definitions_signal = Signal()
    execute_query_signal = Signal(dict)  # query_params

    # Signals for results
    query_success_signal = Signal(list)  # List of ObjectInstance or similar
    query_error_signal = Signal(str)

    def __init__(
        self, client: Optional[Grizabella], parent=None,
    ) -> None:  # Allow Optional client
        super().__init__(parent)
        self.client = client
        self._logger = logging.getLogger(__name__) # Add logger
        self.setWindowTitle("Query View")

        self.current_query_type_index = 0

        # API data
        self.object_types = []
        self.embedding_definitions = []

        self._init_ui()
        self._connect_signals()
        if self.client:  # Only load if client is present
            self._load_initial_data()
        else:
            self._update_ui_for_client_state()  # Disable UI if no client initially

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # Query Type Selection
        self.query_type_combo = QComboBox()
        self.query_type_combo.addItem("Simple Object Query")
        self.query_type_combo.addItem("Embedding Similarity Search")
        self.query_type_combo.addItem("Complex Query")
        main_layout.addWidget(self.query_type_combo)

        # Query Input Area (Stacked Widget)
        self.query_input_stack = QStackedWidget()
        self.query_input_stack.addWidget(self._create_simple_object_query_ui())
        self.query_input_stack.addWidget(self._create_embedding_similarity_search_ui())
        self.query_input_stack.addWidget(self._create_complex_query_ui())
        main_layout.addWidget(self.query_input_stack)

        # Execute Button
        self.execute_button = QPushButton("Execute Query")
        main_layout.addWidget(self.execute_button)

        # Results Display Area
        results_group = QGroupBox("Query Results")
        results_layout = QVBoxLayout()
        self.results_table_view = QTableView()
        self.results_table_view.setAlternatingRowColors(True)
        self.results_table_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.results_table_view.horizontalHeader().setStretchLastSection(True)
        self.results_model = QStandardItemModel(0, 0, self)  # Placeholder model
        self.results_table_view.setModel(self.results_model)
        results_layout.addWidget(self.results_table_view)
        results_group.setLayout(results_layout)
        main_layout.addWidget(results_group)

        self.setLayout(main_layout)
        self._update_ui_for_client_state()  # Initial UI state based on client

    def _create_simple_object_query_ui(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        self.simple_obj_type_combo = QComboBox()
        layout.addRow("Object Type:", self.simple_obj_type_combo)

        # Conditions input - starting with a simple QLineEdit for filter string
        self.simple_conditions_edit = QLineEdit()
        self.simple_conditions_edit.setPlaceholderText(
            "e.g., property_name == 'value' AND another_prop > 10",
        )
        layout.addRow("Conditions:", self.simple_conditions_edit)

        # The QTableWidget for conditions was optional and can be added later if needed.
        # Removing the TODO and commented code for now.

        widget.setLayout(layout)
        return widget

    def _create_embedding_similarity_search_ui(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        self.embed_search_embedding_name_combo = QComboBox()
        layout.addRow("Embedding Name:", self.embed_search_embedding_name_combo)

        self.embed_search_query_text_edit = QLineEdit()
        self.embed_search_query_text_edit.setPlaceholderText(
            "Enter query text or comma-separated vector components",
        )
        layout.addRow("Query Text/Vector:", self.embed_search_query_text_edit)

        self.embed_search_limit_spinbox = QSpinBox()
        self.embed_search_limit_spinbox.setRange(1, 1000)
        self.embed_search_limit_spinbox.setValue(10)
        layout.addRow("Limit:", self.embed_search_limit_spinbox)

        self.embed_search_filter_edit = QLineEdit()
        self.embed_search_filter_edit.setPlaceholderText(
            "Optional SQL-like filter (e.g., category = 'electronics')",
        )
        layout.addRow("Filter Condition:", self.embed_search_filter_edit)

        widget.setLayout(layout)
        return widget

    def _create_complex_query_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)  # Using QVBoxLayout for QTextEdit

        label = QLabel("Enter Complex Query JSON:")
        layout.addWidget(label)

        self.complex_query_json_edit = QTextEdit()
        self.complex_query_json_edit.setPlaceholderText(
            "Paste JSON representation of ComplexQuery model here.\n"
            "Example: {\n"
            '  "components": [\n'
            "    {\n"
            '      "object_type_name": "MyObject",\n'
            '      "relational_filter": {"conditions": "property_a > 10"}\n'
            "    }\n"
            "  ]\n"
            "}",
        )
        self.complex_query_json_edit.setAcceptRichText(False)
        layout.addWidget(self.complex_query_json_edit)

        widget.setLayout(layout)
        return widget

    def _connect_signals(self) -> None:
        self.query_type_combo.currentIndexChanged.connect(self._on_query_type_changed)
        self.execute_button.clicked.connect(self._on_execute_query_clicked)

        # API call signals
        self.fetch_object_types_signal.connect(self._fetch_object_types_worker)
        self.fetch_embedding_definitions_signal.connect(
            self._fetch_embedding_definitions_worker,
        )
        self.execute_query_signal.connect(self._execute_query_worker)

        # Result signals
        self.query_success_signal.connect(self._handle_query_success)
        self.query_error_signal.connect(self._handle_query_error)

    def _load_initial_data(self) -> None:
        if not self.client:
            self._update_ui_for_client_state()
            return
        self.fetch_object_types_signal.emit()
        self.fetch_embedding_definitions_signal.emit()

    def set_client(self, client: Optional[Grizabella]) -> None:
        self.client = client
        self._update_ui_for_client_state()
        if self.client:
            self._load_initial_data()
        else:
            # Clear data if client is removed
            self.simple_obj_type_combo.clear()
            self.embed_search_embedding_name_combo.clear()
            self.results_model.clear()
            self.object_types = []
            self.embedding_definitions = []

    def _update_ui_for_client_state(self) -> None:
        enabled = bool(self.client)
        self.query_type_combo.setEnabled(enabled)
        self.query_input_stack.setEnabled(enabled)
        self.execute_button.setEnabled(enabled)
        # Specific input fields might also need individual handling if they depend on client data
        if not enabled:
            self.simple_obj_type_combo.clear()
            self.embed_search_embedding_name_combo.clear()
            self.results_model.clear()
            self.results_model.setHorizontalHeaderLabels(["Client not connected"])

    @Slot()
    def _fetch_object_types_worker(self) -> None:
        if not self.client or not self.client._is_connected: # Check connection
            self._handle_api_load_error("list_object_types", "Client not available or not connected for fetching object types.")
            return

        if hasattr(self, "_active_fetch_obj_types_thread") and self._active_fetch_obj_types_thread and self._active_fetch_obj_types_thread.isRunning():
            QMessageBox.information(self, "Busy", "Already fetching object types.")
            return

        self._active_fetch_obj_types_thread = ApiClientThread(
            operation_name="list_object_types", parent=self,
        )
        main_win = self._find_main_window()
        if main_win:
            self._active_fetch_obj_types_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._handle_api_load_error("list_object_types", "Internal error: Cannot connect to API handler.")
            self._active_fetch_obj_types_thread.deleteLater()
            self._active_fetch_obj_types_thread = None
            return

        self._active_fetch_obj_types_thread.result_ready.connect(self._populate_object_types)
        self._active_fetch_obj_types_thread.error_occurred.connect(lambda err: self._handle_api_load_error("list_object_types", err))
        self._active_fetch_obj_types_thread.finished.connect(lambda: self._on_generic_thread_finished("_active_fetch_obj_types_thread"))
        self._active_fetch_obj_types_thread.start()

    @Slot(object) # Changed from list
    def _populate_object_types(self, result: Any) -> None:
        if not isinstance(result, list):
            self._handle_api_load_error("list_object_types", f"Unexpected data type for object types: {type(result)}")
            return
        otd_list: list[CoreObjectTypeDefinition] = result
        self.object_types = [otd.name for otd in otd_list]
        self.simple_obj_type_combo.clear()
        self.simple_obj_type_combo.addItems(self.object_types)
        if self.object_types:
            self.simple_obj_type_combo.setCurrentIndex(0)

    @Slot()
    def _fetch_embedding_definitions_worker(self) -> None:
        if not self.client or not self.client._is_connected:
            self._handle_api_load_error("list_embedding_definitions", "Client not available or not connected for fetching embedding definitions.")
            return

        if hasattr(self, "_active_fetch_embed_defs_thread") and self._active_fetch_embed_defs_thread and self._active_fetch_embed_defs_thread.isRunning():
            QMessageBox.information(self, "Busy", "Already fetching embedding definitions.")
            return

        self._active_fetch_embed_defs_thread = ApiClientThread(
            operation_name="list_embedding_definitions", parent=self,
        )
        main_win = self._find_main_window()
        if main_win:
            self._active_fetch_embed_defs_thread.apiRequestReady.connect(main_win.handleApiRequest)
        else:
            self._handle_api_load_error("list_embedding_definitions", "Internal error: Cannot connect to API handler.")
            self._active_fetch_embed_defs_thread.deleteLater()
            self._active_fetch_embed_defs_thread = None
            return

        self._active_fetch_embed_defs_thread.result_ready.connect(self._populate_embedding_definitions)
        self._active_fetch_embed_defs_thread.error_occurred.connect(lambda err: self._handle_api_load_error("list_embedding_definitions", err))
        self._active_fetch_embed_defs_thread.finished.connect(lambda: self._on_generic_thread_finished("_active_fetch_embed_defs_thread"))
        self._active_fetch_embed_defs_thread.start()

    @Slot(object) # Changed from list
    def _populate_embedding_definitions(self, result: Any) -> None:
        if not isinstance(result, list):
            self._handle_api_load_error("list_embedding_definitions", f"Unexpected data type for embedding definitions: {type(result)}")
            return
        ed_list: list[CoreEmbeddingDefinition] = result
        self.embedding_definitions = [ed.name for ed in ed_list]
        self.embed_search_embedding_name_combo.clear()
        self.embed_search_embedding_name_combo.addItems(self.embedding_definitions)
        if self.embedding_definitions:
            self.embed_search_embedding_name_combo.setCurrentIndex(0)

    @Slot(str, str) # Added operation_name
    def _handle_api_load_error(self, operation_name: str, error_message: str) -> None:
        QMessageBox.warning(
            self, "Data Load Error", f"Failed to load data for '{operation_name}': {error_message}",
        )

    @Slot(int)
    def _on_query_type_changed(self, index: int) -> None:
        self.current_query_type_index = index
        self.query_input_stack.setCurrentIndex(index)

    @Slot()
    def _on_execute_query_clicked(self) -> None:
        if not self.client:
            QMessageBox.warning(
                self, "Client Error", "Grizabella client is not connected.",
            )
            return

        query_params = {}
        query_type_str = self.query_type_combo.currentText()
        query_params["query_type"] = query_type_str

        try:
            if query_type_str == "Simple Object Query":
                self._prepare_simple_object_query(query_params)
            elif query_type_str == "Embedding Similarity Search":
                self._prepare_embedding_search_query(query_params)
            elif query_type_str == "Complex Query":
                self._prepare_complex_query(query_params)
            else:
                self.query_error_signal.emit(f"Unknown query type: {query_type_str}")
                return  # Important to return if query type is unknown

            if "error" not in query_params:  # Check if error occurred during prep
                self.execute_query_signal.emit(query_params)

        except Exception as e:  # Catch any other unexpected error during prep
            self.query_error_signal.emit(f"Error preparing query: {e!s}")

    def _prepare_simple_object_query(self, query_params: dict[str, Any]) -> None:
        if not self.simple_obj_type_combo.currentText():
            QMessageBox.warning(self, "Input Error", "Please select an Object Type.")
            query_params["error"] = True
            return
        query_params["object_type_name"] = self.simple_obj_type_combo.currentText()
        query_params["conditions"] = self.simple_conditions_edit.text() or None

    def _prepare_embedding_search_query(self, query_params: dict[str, Any]) -> None:
        if not self.embed_search_embedding_name_combo.currentText():
            QMessageBox.warning(self, "Input Error", "Please select an Embedding Name.")
            query_params["error"] = True
            return
        query_params["embedding_name"] = (
            self.embed_search_embedding_name_combo.currentText()
        )

        query_text_or_vector = self.embed_search_query_text_edit.text()
        if not query_text_or_vector:
            QMessageBox.warning(
                self, "Input Error", "Query Text/Vector cannot be empty.",
            )
            query_params["error"] = True
            return
        try:
            vector_parts = [float(x.strip()) for x in query_text_or_vector.split(",")]
            query_params["query_vector"] = vector_parts
            query_params["query_text"] = None
        except ValueError:
            query_params["query_text"] = query_text_or_vector
            query_params["query_vector"] = None

        query_params["limit"] = self.embed_search_limit_spinbox.value()
        query_params["filter_condition"] = self.embed_search_filter_edit.text() or None

    def _prepare_complex_query(self, query_params: dict[str, Any]) -> None:
        json_text = self.complex_query_json_edit.toPlainText()
        if not json_text:
            QMessageBox.warning(
                self, "Input Error", "Complex Query JSON cannot be empty.",
            )
            query_params["error"] = True
            return
        try:
            query_params["complex_query_json"] = json.loads(json_text)
        except json.JSONDecodeError as e:
            QMessageBox.critical(
                self, "JSON Error", f"Invalid JSON for Complex Query: {e}",
            )
            query_params["error"] = True
            return

    @Slot(dict)
    def _execute_query_worker(self, query_params: dict) -> None:
        if (
            not self.client
        ):  # Should be caught by _on_execute_query_clicked, but double check
            self.query_error_signal.emit("Client not connected. Cannot execute query.")
            return

        query_type = query_params.pop("query_type")

        api_method_name = None
        api_args = []
        api_kwargs = {}

        if query_type == "Simple Object Query":
            api_method_name = "query_objects"  # This method does not exist on Grizabella client, it's find_objects
            # Or, the spec implies grizabella_client.query_objects exists.
            # For now, assuming it should be find_objects or the spec is ahead of client.py
            # Let's assume client.py will be updated or use a placeholder.
            # The task description mentions `query_objects` for the client.
            api_kwargs["object_type_name"] = query_params["object_type_name"]
            api_kwargs["conditions"] = query_params[
                "conditions"
            ]  # find_objects takes filter_criteria
            # query_objects in spec takes conditions
            # Add other params like limit, offset, retrieve_embeddings if UI supports them

        elif query_type == "Embedding Similarity Search":
            api_method_name = "find_similar"  # client.py has search_similar_objects, spec says find_similar
            api_kwargs["embedding_name"] = query_params["embedding_name"]
            if query_params.get("query_text"):
                api_kwargs["query_text"] = query_params["query_text"]
            elif query_params.get("query_vector"):
                api_kwargs["query_vector"] = query_params["query_vector"]
            api_kwargs["limit"] = query_params["limit"]
            api_kwargs["filter_condition"] = query_params["filter_condition"]
            api_kwargs["retrieve_full_objects"] = True  # As per spec

        elif query_type == "Complex Query":
            api_method_name = "execute_complex_query"
            try:
                complex_query_data = query_params["complex_query_json"]
                api_kwargs["query"] = complex_query_data
            except Exception as e:
                self.query_error_signal.emit(
                    f"Error creating ComplexQuery model: {e!s}",
                )
                return

        if not self.client or not self.client._is_connected: # Check connection
            self.query_error_signal.emit("Client not available or not connected for query execution.")
            return

        if api_method_name: # Check if api_method_name was set
            # hasattr check for the method on the Grizabella class itself, not the instance,
            # as the instance will be created in the thread.
            if hasattr(self, "_active_execute_query_thread") and self._active_execute_query_thread and self._active_execute_query_thread.isRunning():
                QMessageBox.information(self, "Busy", "A query is already executing.")
                return

            self._active_execute_query_thread = ApiClientThread(
                api_method_name, # operation_name passed positionally
                *api_args,       # Spread positional arguments
                parent=self,     # Keyword argument for ApiClientThread
                **api_kwargs,     # Spread keyword arguments for the API call
            )
            main_win = self._find_main_window()
            if main_win:
                self._active_execute_query_thread.apiRequestReady.connect(main_win.handleApiRequest)
            else:
                self.query_error_signal.emit("Internal error: Cannot connect to API handler for query execution.")
                self._active_execute_query_thread.deleteLater()
                self._active_execute_query_thread = None
                return

            self._active_execute_query_thread.result_ready.connect(self._handle_query_success_raw)
            self._active_execute_query_thread.error_occurred.connect(self.query_error_signal) # Keep existing error signal for query execution
            self._active_execute_query_thread.finished.connect(lambda: self._on_generic_thread_finished("_active_execute_query_thread"))
            self._active_execute_query_thread.start()
        # elif api_method_name: # This check is now less relevant as ApiClientThread would fail if method_name is bad
        #     self.query_error_signal.emit(
        #         f"API method '{api_method_name}' not found on client.",
        #     )
        else:
            self.query_error_signal.emit(
                f"Unknown query type for execution: {query_type}",
            )

    @Slot(object)  # Can be List[ObjectInstance] or QueryResult
    def _handle_query_success_raw(self, result_data) -> None:
        """Handles raw data from API and emits a list of ObjectInstance."""
        if isinstance(result_data, list):  # From query_objects or find_similar
            self.query_success_signal.emit(result_data)
        # From execute_complex_query (QueryResult)
        elif hasattr(result_data, "objects") and isinstance(
            result_data.objects, list,
        ):
            self.query_success_signal.emit(result_data.objects)
        else:
            self.query_error_signal.emit(
                f"Received unexpected result format: {type(result_data)}",
            )

    @Slot(list)
    def _handle_query_success(self, results: list[ObjectInstance]) -> None:
        self.results_model.clear()
        if not results:
            QMessageBox.information(
                self,
                "Query Executed",
                "Query executed successfully, but returned no results.",
            )
            self.results_model.setHorizontalHeaderLabels(["Info"])
            item = QStandardItem("No results found.")
            item.setEditable(False)
            self.results_model.setItem(0, 0, item)
            return

        first_object = results[0]
        headers: list[str] = []
        if isinstance(first_object, ObjectInstance):
            headers = ["id", "object_type_name", *sorted(first_object.properties.keys())]
        else:
            headers = ["Result Data"]
            self.results_model.setHorizontalHeaderLabels(headers)
            for i, item_data in enumerate(results):
                item = QStandardItem(str(item_data))
                item.setEditable(False)
                self.results_model.setItem(i, 0, item)
            return

        self.results_model.setHorizontalHeaderLabels(headers)
        self.results_model.setRowCount(len(results))
        col_map = {header: idx for idx, header in enumerate(headers)}

        for row, obj_instance in enumerate(results):
            if not isinstance(obj_instance, ObjectInstance):
                self._set_unexpected_result_item(row, obj_instance)
                continue

            self._set_table_item(row, col_map.get("id"), str(obj_instance.id))
            self._set_table_item(
                row, col_map.get("object_type_name"), obj_instance.object_type_name,
            )

            for prop_name, prop_value in obj_instance.properties.items():
                if prop_name in col_map:
                    self._set_table_item(row, col_map[prop_name], str(prop_value))

            for header_name in headers:
                if (
                    header_name not in ["id", "object_type_name"]
                    and header_name not in obj_instance.properties
                ) and header_name in col_map and not self.results_model.item(
                    row, col_map[header_name],
                ):
                    self._set_table_item(row, col_map[header_name], "")

        self.results_table_view.resizeColumnsToContents()
        QMessageBox.information(
            self,
            "Query Success",
            f"Query executed successfully. {len(results)} results found.",
        )

    def _set_table_item(self, row: int, col: Optional[int], text: str) -> None:
        if col is not None:
            item = QStandardItem(text)
            item.setEditable(False)
            self.results_model.setItem(row, col, item)

    def _set_unexpected_result_item(self, row: int, data: Any) -> None:
        item = QStandardItem(f"Unexpected item: {data!s}")
        item.setEditable(False)
        self.results_model.setItem(row, 0, item)
        if self.results_model.columnCount() > 1:
            for col_idx in range(1, self.results_model.columnCount()):
                self._set_table_item(row, col_idx, "")

    @Slot(str)
    def _handle_query_error(self, error_message: str) -> None:
        QMessageBox.critical(
            self, "Query Execution Error", f"An error occurred: {error_message}",
        )
        self.results_model.clear()  # Clear previous results on error
        self.results_model.setHorizontalHeaderLabels(["Error"])
        item = QStandardItem(error_message)
        item.setEditable(False)
        self.results_model.setItem(0, 0, item)

    @Slot(str)
    def _on_generic_thread_finished(self, thread_attr_name: str) -> None:
        thread_instance = getattr(self, thread_attr_name, None)
        if thread_instance:
            # print(f"QueryView: Thread {thread_attr_name} ({thread_instance}) finished. Scheduling for deletion.")
            thread_instance.deleteLater()
            setattr(self, thread_attr_name, None)
        # Re-enable UI elements if necessary, e.g., execute_button
        self.execute_button.setEnabled(True)


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
        self._logger.warning("Could not find MainWindow instance for QueryView.")
        return None

    def closeEvent(self, event: Any) -> None:
        """Ensure threads are stopped if the widget is closed."""
        self._logger.debug(f"QueryView closeEvent triggered for {self}.")
        threads_to_manage = [
            ("_active_fetch_obj_types_thread", getattr(self, "_active_fetch_obj_types_thread", None)),
            ("_active_fetch_embed_defs_thread", getattr(self, "_active_fetch_embed_defs_thread", None)),
            ("_active_execute_query_thread", getattr(self, "_active_execute_query_thread", None)),
        ]
        for name, thread_instance in threads_to_manage:
            if thread_instance and thread_instance.isRunning():
                self._logger.info(f"QueryView: Worker thread '{name}' ({thread_instance}) is running. Attempting to quit/wait.")
                thread_instance.quit()
                if not thread_instance.wait(500):
                    self._logger.warning(f"QueryView: Worker thread '{name}' ({thread_instance}) did not finish. Terminating.")
                    thread_instance.terminate()
                    thread_instance.wait()
                else:
                    self._logger.info(f"QueryView: Worker thread '{name}' ({thread_instance}) finished.")
            elif thread_instance: # Exists but not running
                thread_instance.deleteLater()

        # Clear references
        self._active_fetch_obj_types_thread = None
        self._active_fetch_embed_defs_thread = None
        self._active_execute_query_thread = None
        super().closeEvent(event)


if __name__ == "__main__":
    import sys
    import uuid  # Added for mock ObjectInstance IDs

    # Mock Grizabella for standalone testing
    class MockGrizabella:  # Changed GrizabellaClient to Grizabella
        def list_object_types(self):  # Corrected method name
            return [
                CoreObjectTypeDefinition(
                    name="Person",
                    properties=[
                        CorePropertyDefinition(
                            name="name", data_type=PropertyDataType.TEXT,
                        ),
                        CorePropertyDefinition(
                            name="age", data_type=PropertyDataType.INTEGER,
                        ),
                    ],
                ),
                CoreObjectTypeDefinition(
                    name="Product",
                    properties=[
                        CorePropertyDefinition(
                            name="product_name", data_type=PropertyDataType.TEXT,
                        ),
                        CorePropertyDefinition(
                            name="price", data_type=PropertyDataType.FLOAT,
                        ),
                    ],
                ),
            ]

        def list_embedding_definitions(self):
            return [
                CoreEmbeddingDefinition(
                    name="text_embedding_ada_002",
                    object_type_name="Document",
                    source_property_name="content",
                    dimensions=1536,
                    description="OpenAI Ada v2",
                ),
                CoreEmbeddingDefinition(
                    name="clip_vit_b_32",
                    object_type_name="Image",
                    source_property_name="image_blob",
                    dimensions=512,
                    description="CLIP ViT-B/32",
                ),
            ]

        def query_objects(
            self,
            object_type_name: str,
            conditions=None,  # pylint: disable=unused-argument
            limit=100,
            offset=0,  # pylint: disable=unused-argument
            retrieve_embeddings=False,
        ):  # pylint: disable=unused-argument
            if object_type_name == "Person":
                return [
                    ObjectInstance(
                        id=uuid.uuid4(),
                        object_type_name="Person",
                        properties={"name": "Alice", "age": 30},
                    ),
                    ObjectInstance(
                        id=uuid.uuid4(),
                        object_type_name="Person",
                        properties={"name": "Bob", "age": 25, "city": "New York"},
                    ),
                ]
            return []

        def find_similar(
            self,
            embedding_name: str,
            query_text=None,  # pylint: disable=unused-argument
            query_vector=None,
            limit=10,  # pylint: disable=unused-argument
            filter_condition=None,  # pylint: disable=unused-argument
            retrieve_full_objects=True,
        ):  # pylint: disable=unused-argument
            return [
                ObjectInstance(
                    id=uuid.uuid4(),
                    object_type_name="Document",
                    properties={"title": "Similar Doc 1", "content": "abc"},
                ),
                ObjectInstance(
                    id=uuid.uuid4(),
                    object_type_name="Document",
                    properties={"title": "Similar Doc 2", "content": "def"},
                ),
            ]

        def execute_complex_query(self, query: dict[str, Any]):
            if query and query.get("components"):
                from grizabella.core.query_models import QueryResult as CoreQueryResult

                return CoreQueryResult(
                    object_instances=[
                        ObjectInstance(
                            id=uuid.uuid4(),
                            object_type_name="ComplexResult",
                            properties={"data": "Result A"},
                        ),
                        ObjectInstance(
                            id=uuid.uuid4(),
                            object_type_name="ComplexResult",
                            properties={"data": "Result B", "extra": "Field"},
                        ),
                    ],
                )
            msg = "Mock Complex Query Failed: Invalid query structure"
            raise ValueError(msg)

    app = QApplication(sys.argv)
    mock_client = MockGrizabella()
    main_view = QueryView(client=mock_client)  # type: ignore
    main_view.show()
    sys.exit(app.exec())
