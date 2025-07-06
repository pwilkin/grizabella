"""Main window for the Grizabella application.
Handles the overall UI structure, including menus, views, and client interaction.
"""

import logging  # Add logging import
import sys
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QApplication, QMainWindow, QMenuBar, QStackedWidget, QTabWidget

from grizabella.ui.threads.api_client_thread import ApiClientThread  # Added for type hinting and sender check
from grizabella.ui.views.connection_view import ConnectionView
from grizabella.ui.views.embedding_definition_view import EmbeddingDefinitionView
from grizabella.ui.views.object_explorer_view import ObjectExplorerView
from grizabella.ui.views.object_type_view import ObjectTypeView
from grizabella.ui.views.query_view import QueryView  # Added import
from grizabella.ui.views.relation_explorer_view import RelationExplorerView
from grizabella.ui.views.relation_type_view import RelationTypeView

if TYPE_CHECKING:
    from grizabella.api.client import (
        Grizabella,
    )  # Assuming Grizabella is the client class name


class MainWindow(QMainWindow):
    """Main window for the Grizabella application.
    It will contain the menu bar, toolbar, status bar, and central widget area.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Grizabella - Tri-Layer Memory System")
        self.setGeometry(100, 100, 1200, 800)
        self.grizabella_client: Optional[Grizabella] = None
        self.connection_view: Optional[ConnectionView] = None
        self._logger = logging.getLogger(__name__) # Initialize logger

        # Schema Editor related views
        self.object_type_view: Optional[ObjectTypeView] = None
        self.embedding_definition_view: Optional[EmbeddingDefinitionView] = None
        self.relation_type_view: Optional[RelationTypeView] = None
        self.schema_editor_tabs: Optional[QTabWidget] = None

        # Object Explorer view
        self.object_explorer_view: Optional[ObjectExplorerView] = None
        # Relation Explorer view
        self.relation_explorer_view: Optional[RelationExplorerView] = None
        # Query View
        self.query_view: Optional[QueryView] = None

        # Main application tabs (to hold Schema Editor and Object Explorer)
        self.main_application_tabs: Optional[QTabWidget] = None

        self.central_stacked_widget: Optional[QStackedWidget] = None

        self._create_menu_bar()
        self._create_status_bar()
        self._setup_central_widget()

    def _create_menu_bar(self) -> None:
        """Creates the main menu bar."""
        menu_bar = self.menuBar()
        if not isinstance(menu_bar, QMenuBar):
            menu_bar = QMenuBar(self)
            self.setMenuBar(menu_bar)

        file_menu = menu_bar.addMenu("&File")
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

        # Placeholder for other menus
        # view_menu = menu_bar.addMenu("&View")
        # view_menu.addAction("Object Types", self._show_object_type_view_action) # Example

    # def _show_object_type_view_action(self):
    #     if self.grizabella_client and self.central_stacked_widget and self.object_type_view:
    #         self.central_stacked_widget.setCurrentWidget(self.object_type_view)
    #     elif not self.grizabella_client:
    #         self.show_status_message("Please connect to a Grizabella instance first.")
    #     else: # Should not happen if UI is consistent
    #         self.show_status_message("Object Type View not available.")

    def _create_status_bar(self) -> None:
        """Creates the status bar."""
        self.status_bar = self.statusBar()
        self.show_status_message("Ready")

    def _setup_central_widget(self) -> None:
        """Sets up the central widget using a QStackedWidget to switch views."""
        self.central_stacked_widget = QStackedWidget(self)

        self.connection_view = ConnectionView(self)
        self.central_stacked_widget.addWidget(self.connection_view)

        # ObjectTypeView is created when a client connects
        # self.object_type_view = ObjectTypeView(None, self) # Initialize with no client
        # self.central_stacked_widget.addWidget(self.object_type_view)

        self.setCentralWidget(self.central_stacked_widget)
        self.central_stacked_widget.setCurrentWidget(self.connection_view)

        if self.connection_view:
            self.connection_view.connection_status_updated.connect(
                self.show_status_message,
            )
            self.connection_view.grizabella_client_updated.connect(
                self.set_grizabella_client,
            )

    @Slot(str)
    def show_status_message(self, message: str) -> None:
        """Displays a message in the status bar."""
        if hasattr(self, "status_bar") and self.status_bar:
            self.status_bar.showMessage(message)
        else:
            pass

    @Slot(object)
    def set_grizabella_client(
        self, client: Optional["Grizabella"],
    ) -> None:  # Corrected type hint
        """Stores the Grizabella client instance and updates status and central view."""
        self._logger.info(f"MainWindow: set_grizabella_client called. Client is {'set' if client else 'None'}.")
        self.grizabella_client = client
        if client and self.central_stacked_widget:
            try:
                db_identifier = getattr(
                    client, "db_path", getattr(client, "db_name_or_path", "Unknown DB"),
                )
                self.show_status_message(f"Grizabella client connected: {db_identifier}")
                self._logger.info(f"MainWindow: Client connected to {db_identifier}. Setting up main tabs.")

                if not self.main_application_tabs:
                    self._logger.debug("MainWindow: Main application tabs not yet created. Creating now.")
                    self.main_application_tabs = QTabWidget()
                    self.central_stacked_widget.addWidget(self.main_application_tabs)

                    # 1. Schema Editor Tab (as a QTabWidget itself)
                    self._logger.debug("MainWindow: Creating Schema Editor tabs.")
                    self.schema_editor_tabs = QTabWidget()
                    self.main_application_tabs.addTab(
                        self.schema_editor_tabs, "Schema Editor",
                    )

                    # Populate Schema Editor Tabs
                    self._logger.debug("MainWindow: Creating ObjectTypeView.")
                    self.object_type_view = ObjectTypeView(self.grizabella_client, self)
                    self.schema_editor_tabs.addTab(self.object_type_view, "Object Types")
                    self._logger.debug("MainWindow: ObjectTypeView added to schema_editor_tabs.")

                    self._logger.debug("MainWindow: Creating EmbeddingDefinitionView.")
                    self.embedding_definition_view = EmbeddingDefinitionView(
                        self.grizabella_client, self,
                    )
                    self.schema_editor_tabs.addTab(
                        self.embedding_definition_view, "Embedding Definitions",
                    )

                    self._logger.debug("MainWindow: Creating RelationTypeView.")
                    self.relation_type_view = RelationTypeView(self.grizabella_client, self)
                    self.schema_editor_tabs.addTab(
                        self.relation_type_view, "Relation Types",
                    )
                    self._logger.debug("MainWindow: Schema Editor tabs populated with ObjectTypeView, EmbeddingDefinitionView, and RelationTypeView.")

                    # 2. Object Explorer Tab - ENABLE THIS ONE
                    self._logger.debug("MainWindow: Creating ObjectExplorerView.")
                    if self.grizabella_client:  # Ensure client is not None
                        self.object_explorer_view = ObjectExplorerView(
                            self.grizabella_client, self,
                        )
                        self.main_application_tabs.addTab(
                            self.object_explorer_view, "Object Explorer",
                        )
                        if hasattr(self.object_explorer_view, "busy_signal"):
                            self.object_explorer_view.busy_signal.connect(
                                lambda busy: self.show_status_message(
                                    "Processing..." if busy else "Ready",
                                ),
                            )
                    else: # Should not happen
                        self.object_explorer_view = ObjectExplorerView(None, self) # type: ignore
                        self.object_explorer_view.setEnabled(False)
                        self.main_application_tabs.addTab(
                            self.object_explorer_view, "Object Explorer (No Client)",
                        )
                    self._logger.debug("MainWindow: ObjectExplorerView added.")

                    # 3. Relation Explorer Tab
                    self._logger.debug("MainWindow: Creating RelationExplorerView.")
                    if self.grizabella_client:
                        self.relation_explorer_view = RelationExplorerView(
                            self.grizabella_client, self,
                        )
                        self.main_application_tabs.addTab(
                            self.relation_explorer_view, "Relation Explorer",
                        )
                    else: # Should not happen
                        self.relation_explorer_view = RelationExplorerView(None, self) # type: ignore
                        self.relation_explorer_view.setEnabled(False)
                        self.main_application_tabs.addTab(
                            self.relation_explorer_view, "Relation Explorer (No Client)",
                        )
                    self._logger.debug("MainWindow: RelationExplorerView added.")

                    # 4. Query View Tab
                    self._logger.debug("MainWindow: Creating QueryView.")
                    if self.grizabella_client:
                        self.query_view = QueryView(self.grizabella_client, self)
                        self.main_application_tabs.addTab(self.query_view, "Query Builder")
                    else: # Should not happen
                        self.query_view = QueryView(None, self) # type: ignore
                        self.query_view.setEnabled(False)
                        self.main_application_tabs.addTab(
                            self.query_view, "Query Builder (No Client)",
                        )
                    self._logger.debug("MainWindow: QueryView added.")
                    self._logger.info("MainWindow: All views initialized.")

                else:
                    self._logger.info("MainWindow: Main application tabs already exist. Refreshing views with client.")
                    # Client reconnected or already connected, ensure all views have the client
                    if self.object_type_view:
                        self.object_type_view.set_client(self.grizabella_client)
                        if self.grizabella_client:
                            self.object_type_view.refresh_object_types()
                    if self.embedding_definition_view:
                        if hasattr(self.embedding_definition_view, "set_grizabella_client"):
                            self.embedding_definition_view.set_grizabella_client(self.grizabella_client)
                        if self.grizabella_client and hasattr(self.embedding_definition_view, "refresh_definitions"):
                            self.embedding_definition_view.refresh_definitions()
                    if self.relation_type_view:
                        if hasattr(self.relation_type_view, "set_grizabella_client"):
                            self.relation_type_view.set_grizabella_client(self.grizabella_client)
                        if self.grizabella_client and hasattr(self.relation_type_view, "refresh_relation_types"):
                            self.relation_type_view.refresh_relation_types()
                    if self.object_explorer_view and hasattr(self.object_explorer_view, "set_client"):
                        self.object_explorer_view.set_client(self.grizabella_client)
                    if self.relation_explorer_view:
                        if hasattr(self.relation_explorer_view, "grizabella_client"):
                            self.relation_explorer_view.grizabella_client = self.grizabella_client
                        if self.grizabella_client and hasattr(self.relation_explorer_view, "refresh_view"):
                            self.relation_explorer_view.refresh_view()
                    if self.query_view:
                        self.query_view.set_client(self.grizabella_client)
                    self._logger.info("MainWindow: Views refreshed.")

                self._logger.debug("MainWindow: Setting current widget to main_application_tabs.")
                self.central_stacked_widget.setCurrentWidget(self.main_application_tabs)
                self._logger.debug("MainWindow: Current widget set.")

            except Exception as e:
                self._logger.error(f"MainWindow: Error during UI setup after client connection: {e}", exc_info=True)
                app_instance = QApplication.instance()
                if app_instance:
                    app_instance.quit() # Try to quit gracefully if UI setup fails critically
                else:
                    self._logger.error("MainWindow: QApplication.instance() is None, cannot quit.")
                return # Stop further processing in this slot

        elif self.central_stacked_widget:  # Client is None (disconnected)
            self.show_status_message(
                "Grizabella client disconnected or connection failed.",
            )
            # Clear client from all views
            if self.object_type_view:
                self.object_type_view.set_client(None)
            if self.embedding_definition_view and hasattr(
                self.embedding_definition_view, "set_grizabella_client",
            ):
                self.embedding_definition_view.set_grizabella_client(None)
            # Add manual clear for embedding_definition_view if no set_grizabella_client
            elif self.embedding_definition_view and hasattr(
                self.embedding_definition_view, "definitions_list_widget",
            ):
                self.embedding_definition_view.definitions_list_widget.clear()
                self.embedding_definition_view.details_text_edit.clear()
                self.embedding_definition_view.current_definitions = []

            if self.relation_type_view and hasattr(
                self.relation_type_view, "set_grizabella_client",
            ):
                self.relation_type_view.set_grizabella_client(None)
            # The set_grizabella_client(None) call in RelationTypeView already handles
            # clearing its UI elements, including calling its own _clear_details.
            # The following elif block for manual clearing is redundant and causes W0212.
            # elif self.relation_type_view and hasattr(self.relation_type_view, 'list_widget'):
            #     self.relation_type_view.list_widget.clear()
            #     self.relation_type_view.list_widget.addItem("Client disconnected.")
            #     self.relation_type_view.list_widget.setEnabled(False)
            #     if hasattr(self.relation_type_view, '_clear_details'):
            #         self.relation_type_view._clear_details()
            #     self.relation_type_view.new_button.setEnabled(False)
            #     self.relation_type_view.edit_button.setEnabled(False)
            #     self.relation_type_view.delete_button.setEnabled(False)

            if self.object_explorer_view and hasattr(self.object_explorer_view, "set_client"):
                self.object_explorer_view.set_client(
                    None,
                )  # set_client handles UI update for None
            if self.relation_explorer_view:
                if hasattr(self.relation_explorer_view, "grizabella_client"):
                    self.relation_explorer_view.grizabella_client = None
                if hasattr(
                    self.relation_explorer_view, "refresh_view",
                ):  # To clear views
                    self.relation_explorer_view.refresh_view()
                if self.relation_explorer_view:
                    self.relation_explorer_view.setEnabled(False)

            if self.query_view:
                self.query_view.set_client(None)  # Use set_client method
                # Clearing data and setEnabled is handled by set_client(None)

            if self.connection_view:
                self.central_stacked_widget.setCurrentWidget(self.connection_view)

    def get_grizabella_client(self) -> Optional["Grizabella"]:  # Corrected type hint
        """Returns the stored Grizabella client instance."""
        return self.grizabella_client

    @Slot(str, tuple, dict)
    def handleApiRequest(self, operation_name: str, op_args: tuple, op_kwargs: dict) -> None:
        """Handles API requests emitted by worker threads.
        Executes the Grizabella API call in the main thread and sends the
        result back to the originating worker thread.
        """
        actual_sender_thread: Optional[ApiClientThread] = None
        sender_obj = self.sender()

        if isinstance(sender_obj, ApiClientThread):
            actual_sender_thread = sender_obj
        elif hasattr(sender_obj, "parent") and isinstance(sender_obj.parent(), ApiClientThread):
            # This case might occur if the signal is emitted from a child QObject of the thread
            self._logger.info("MainWindow.handleApiRequest: Sender is not ApiClientThread, but its parent is. Using parent.")
            actual_sender_thread = sender_obj.parent() # type: ignore

        if not actual_sender_thread:
            self._logger.error(
                "MainWindow.handleApiRequest: Could not identify an ApiClientThread as the sender or its direct parent. Ignoring request.",
            )
            return

        # Now, actual_sender_thread is confirmed to be an ApiClientThread instance
        if not self.grizabella_client or not self.grizabella_client._is_connected:
            error_msg = "Grizabella client is not available or not connected."
            self._logger.error(f"MainWindow.handleApiRequest: {error_msg}")
            actual_sender_thread.handleApiResponse(False, error_msg)
            return

        try:
            method_to_call = getattr(self.grizabella_client, operation_name)
            if not callable(method_to_call):
                raise AttributeError(
                    f"Method '{operation_name}' not found or not callable in Grizabella client.",
                )

            self._logger.info(
                f"MainWindow: Executing API call '{operation_name}' "
                f"with args: {op_args}, kwargs: {op_kwargs} for sender: {actual_sender_thread}",
            )

            # Process events to keep UI responsive during the API call.
            app_instance = QApplication.instance()
            if app_instance:
                app_instance.processEvents()

            result = method_to_call(*op_args, **op_kwargs)
            self._logger.info(f"MainWindow: API call '{operation_name}' successful.")
            actual_sender_thread.handleApiResponse(True, result)

        except Exception as e:
            error_msg = f"Error executing API call '{operation_name}': {e}"
            self._logger.error(f"MainWindow.handleApiRequest: {error_msg}", exc_info=True)
            actual_sender_thread.handleApiResponse(False, e) # Pass the exception object

    def shutdown_threads_and_client(self) -> None:
        """Gracefully shuts down all view threads and the main Grizabella client."""
        self._logger.info("MainWindow: shutdown_threads_and_client called.")
        views_to_close = [
            self.object_type_view,
            self.embedding_definition_view,
            self.relation_type_view,
            self.object_explorer_view,
            self.relation_explorer_view,
            self.query_view,
            self.connection_view, # ConnectionView might not have threads, but good practice
        ]
        for view_widget in views_to_close:
            if view_widget:
                view_name = view_widget.__class__.__name__
                # Call close() to trigger the standard Qt close event mechanism.
                # The overridden closeEvent in each view will then be called by Qt.
                self._logger.info(f"MainWindow: Attempting to call close() for {view_name}.")
                try:
                    self._logger.debug(f"MainWindow: PRE-CALL to {view_name}.close()")
                    view_widget.close()
                    self._logger.debug(f"MainWindow: POST-CALL to {view_name}.close()")
                    self._logger.info(f"MainWindow: Successfully returned from close() for {view_name}. Its closeEvent should have handled thread cleanup.")
                except Exception as e_c:
                    self._logger.error(f"MainWindow: Error during view_widget.close() for {view_name}: {e_c}", exc_info=True)
            else:
                self._logger.debug("MainWindow: Encountered a None view_widget in views_to_close list.")
        self._logger.info("MainWindow: Finished iterating through view closeEvents/close methods.")

        if self.grizabella_client:
            self._logger.info("MainWindow: Attempting to close Grizabella client.")
            try:
                # Assuming grizabella_client.close() handles its own adapter closures.
                # We might need more granular logging within Grizabella.close() itself if problems persist here.
                self.grizabella_client.close()
                self._logger.info("MainWindow: Grizabella client close() method completed.")
            except Exception as e:
                self._logger.error(f"MainWindow: Error during Grizabella client.close(): {e}", exc_info=True)
            finally:
                self.grizabella_client = None
                self._logger.info("MainWindow: Grizabella client reference set to None.")
        else:
            self._logger.info("MainWindow: No Grizabella client instance to close.")
        self._logger.info("MainWindow: shutdown_threads_and_client finished.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
