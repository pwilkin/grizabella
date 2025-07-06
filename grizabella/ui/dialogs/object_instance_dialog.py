# Standard library imports
import json  # For handling JSON data in QTextEdit
import logging  # For logging
import uuid  # For generating mock IDs and for UUID type
from datetime import datetime, timezone  # For mock dates and datetime type
from decimal import Decimal  # For weight
from pathlib import Path  # For MockGrizabella init
from typing import TYPE_CHECKING, Any, Optional, Union  # Added TYPE_CHECKING

from PySide6.QtCore import QDateTime, Qt, Signal, Slot  # QThread removed
from PySide6.QtWidgets import (
    QApplication,  # Added
    QCheckBox,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# First-party imports
from grizabella.api.client import Grizabella
from grizabella.core.models import (
    ObjectInstance,
    ObjectTypeDefinition,
    PropertyDataType,
    PropertyDefinition,
)
from grizabella.ui.threads.api_client_thread import ApiClientThread  # Import new thread

# from grizabella.ui.main_window import MainWindow # For connecting signals <- REMOVED FOR CIRCULAR IMPORT

if TYPE_CHECKING:
    from grizabella.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class ObjectInstanceDialog(QDialog):
    """A dialog for creating or editing an ObjectInstance.
    The form fields are dynamically generated based on the ObjectTypeDefinition.
    """

    busy_signal = Signal(bool)
    instance_upserted_signal = Signal(dict)  # Emits the upserted ObjectInstance data

    def __init__(
        self,
        grizabella_client: Grizabella, # This client is used to get db_name_or_path, but not for direct calls
        object_type: ObjectTypeDefinition,
        mode: str = "create",  # "create" or "edit"
        instance_data: Optional[ObjectInstance] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        # self.grizabella_client_ref = grizabella_client # No longer needed for direct calls
        self.object_type = object_type
        self.mode = mode
        self.instance_data = instance_data
        self.form_widgets: dict[str, QWidget] = {}
        self._active_upsert_thread: Optional[ApiClientThread] = None # Renamed

        self.setWindowTitle(
            f"{self.mode.capitalize()} {self.object_type.name} Instance",
        )
        self.setMinimumWidth(500)

        self._init_ui()
        self._populate_form()
        if self.mode == "edit" and self.instance_data:
            self._load_instance_data()

        self._connect_signals()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content_widget = QWidget()
        self.form_layout = QFormLayout(self.scroll_content_widget)
        self.form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.scroll_area.setWidget(self.scroll_content_widget)

        main_layout.addWidget(self.scroll_area)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        main_layout.addWidget(self.button_box)

    def _populate_form(self) -> None:
        if self.mode == "edit" and self.instance_data:
            self.id_display_label = QLabel(str(self.instance_data.id))
            self.form_layout.addRow("ID:", self.id_display_label)

        sorted_properties: list[PropertyDefinition] = sorted(
            self.object_type.properties, key=lambda p: p.name,
        )

        for prop_def in sorted_properties:
            prop_name = prop_def.name
            if prop_name in [
                "id",
                "upsert_date",
                "weight",
            ]:  # weight handled separately
                continue

            label_text = prop_def.name.replace("_", " ").title()
            if not prop_def.is_nullable:
                label_text += " *"

            widget = self._create_widget_for_property(prop_def)
            if widget:
                self.form_layout.addRow(label_text, widget)
                self.form_widgets[prop_name] = widget
            else:
                self.form_layout.addRow(
                    label_text,
                    QLabel(f"[Unsupported type: {prop_def.data_type.value}]"),
                )

        self.weight_spinbox = QDoubleSpinBox()
        self.weight_spinbox.setRange(0.0, 10.0)
        self.weight_spinbox.setDecimals(4)
        self.weight_spinbox.setValue(1.0)
        if self.mode == "edit" and self.instance_data:
            self.weight_spinbox.setValue(float(self.instance_data.weight))
        self.form_layout.addRow("Weight:", self.weight_spinbox)
        self.form_widgets["weight"] = self.weight_spinbox

    def _create_widget_for_property(
        self, prop_def: PropertyDefinition,
    ) -> Optional[QWidget]:
        data_type = prop_def.data_type
        widget: Optional[QWidget] = None
        description_tooltip = prop_def.description or ""

        if data_type == PropertyDataType.UUID:
            widget = QLineEdit()
            widget.setPlaceholderText(prop_def.description or "Enter UUID")
        elif data_type == PropertyDataType.TEXT:  # Changed from STRING to TEXT
            widget = (
                QLineEdit()
            )  # For single-line text, use QLineEdit. For multi-line, use QTextEdit.
            # Assuming TEXT here implies a general string that fits QLineEdit.
            # If TEXT is meant for long-form, this should be QTextEdit.
            # Based on PropertyDataType enum, TEXT is the general string type.
            widget.setPlaceholderText(prop_def.description or "Enter text")
        # If a separate "LONG_TEXT" or similar existed for QTextEdit:
        # elif data_type == PropertyDataType.LONG_TEXT:
        #     widget = QTextEdit()
        #     widget.setPlaceholderText(prop_def.description or "Enter multi-line text")
        #     widget.setAcceptRichText(False)
        #     widget.setFixedHeight(100)
        elif data_type == PropertyDataType.INTEGER:
            widget = QSpinBox()
            widget.setRange(-2147483648, 2147483647)
        elif data_type == PropertyDataType.FLOAT:
            widget = QDoubleSpinBox()
            widget.setRange(-1.79e308, 1.79e308)  # type: ignore
            widget.setDecimals(10)
        elif data_type == PropertyDataType.BOOLEAN:
            widget = QCheckBox()
        elif data_type == PropertyDataType.DATETIME:
            widget = QDateTimeEdit()
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            widget.setDateTime(QDateTime.currentDateTime())
        elif data_type == PropertyDataType.JSON:
            widget = QTextEdit()
            widget.setPlaceholderText(prop_def.description or "Enter JSON data")
            widget.setAcceptRichText(False)
            widget.setFixedHeight(150)
        elif data_type == PropertyDataType.BLOB:
            widget = QLabel("[BLOB data not directly editable in this form]")
        else:
            data_type.value if hasattr(data_type, "value") else data_type

        if widget:
            widget.setToolTip(description_tooltip)
            if not prop_def.is_nullable and isinstance(widget, QLineEdit):
                widget.setStyleSheet("border: 1px solid orange;")

        return widget

    def _load_instance_data(self) -> None:
        if not self.instance_data:
            return

        for prop_name, widget in self.form_widgets.items():
            if prop_name == "weight":
                continue

            if prop_name in self.instance_data.properties:
                value = self.instance_data.properties.get(prop_name)
                current_prop_def = next(
                    (p for p in self.object_type.properties if p.name == prop_name),
                    None,
                )

                if isinstance(widget, QLineEdit):
                    widget.setText(str(value) if value is not None else "")
                elif isinstance(widget, QTextEdit):
                    if (
                        current_prop_def
                        and current_prop_def.data_type == PropertyDataType.JSON
                    ):
                        widget.setPlainText(
                            json.dumps(value, indent=2) if value is not None else "",
                        )
                    else:
                        widget.setPlainText(str(value) if value is not None else "")
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(value) if value is not None else 0)
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value) if value is not None else 0.0)
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value) if value is not None else False)
                elif isinstance(widget, QDateTimeEdit):
                    if isinstance(value, datetime):
                        # Ensure timezone information is handled if present
                        if value.tzinfo:
                            qt_dt = QDateTime(
                                value.year,
                                value.month,
                                value.day,
                                value.hour,
                                value.minute,
                                value.second,
                                value.microsecond // 1000,
                            )
                            qt_dt = qt_dt.toTimeZone(
                                QDateTime.currentDateTime().timeZone(),
                            )  # Convert to local for display
                            widget.setDateTime(qt_dt)
                        else:  # Naive datetime
                            widget.setDateTime(
                                QDateTime(
                                    value.year,
                                    value.month,
                                    value.day,
                                    value.hour,
                                    value.minute,
                                    value.second,
                                    value.microsecond // 1000,
                                ),
                            )
                    elif isinstance(value, str):  # Attempt to parse string
                        dt_value = QDateTime.fromString(value, Qt.DateFormat.ISODate)
                        if not dt_value.isValid():
                            dt_value = QDateTime.fromString(
                                value, Qt.DateFormat.ISODateWithMs,
                            )
                        if not dt_value.isValid():
                            dt_value = QDateTime.fromString(
                                value, "yyyy-MM-dd HH:mm:ss",
                            )
                        if dt_value.isValid():
                            widget.setDateTime(dt_value)
                        else:
                            pass
                    elif value is None:
                        widget.setDateTime(QDateTime.currentDateTime())

    def _collect_data(self) -> Optional[ObjectInstance]:
        properties_data: dict[str, Any] = {}
        is_valid = True

        for prop_name_from_widget, widget in self.form_widgets.items():
            if prop_name_from_widget == "weight":
                continue

            current_prop_def = next(
                (
                    p
                    for p in self.object_type.properties
                    if p.name == prop_name_from_widget
                ),
                None,
            )
            if not current_prop_def:
                QMessageBox.critical(
                    self,
                    "Internal Error",
                    f"Definition not found for {prop_name_from_widget}",
                )
                return None

            value: Any = None

            if isinstance(widget, QLineEdit):
                text_value = widget.text()
                if current_prop_def.data_type == PropertyDataType.UUID:
                    if text_value:
                        try:
                            value = uuid.UUID(text_value)
                        except ValueError:
                            QMessageBox.warning(
                                self,
                                "Invalid UUID",
                                f"'{current_prop_def.name}': Invalid UUID format.",
                            )
                            is_valid = False
                            widget.setFocus()
                            break
                    elif not current_prop_def.is_nullable:
                        QMessageBox.warning(
                            self,
                            "Missing Value",
                            f"'{current_prop_def.name}' (UUID) is required.",
                        )
                        is_valid = False
                        widget.setFocus()
                        break
                    else:
                        value = None
                else:  # TEXT (formerly STRING)
                    value = text_value
            elif isinstance(widget, QTextEdit):
                text_content = widget.toPlainText()
                if current_prop_def.data_type == PropertyDataType.JSON:
                    if text_content.strip():
                        try:
                            value = json.loads(text_content)
                        except json.JSONDecodeError as e:
                            QMessageBox.warning(
                                self, "Invalid JSON", f"'{current_prop_def.name}': {e}",
                            )
                            is_valid = False
                            widget.setFocus()
                            break
                    elif not current_prop_def.is_nullable:
                        QMessageBox.warning(
                            self,
                            "Missing Value",
                            f"'{current_prop_def.name}' (JSON) is required.",
                        )
                        is_valid = False
                        widget.setFocus()
                        break
                    else:
                        value = None  # Nullable and empty JSON is None
                else:  # TEXT (if QTextEdit is used for TEXT type)
                    value = text_content
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                value = widget.value()
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
            elif isinstance(widget, QDateTimeEdit):
                q_dt = widget.dateTime()
                # Convert QDateTime to Python datetime, try to preserve UTC if specified
                dt_object = datetime(
                    q_dt.date().year(),
                    q_dt.date().month(),
                    q_dt.date().day(),
                    q_dt.time().hour(),
                    q_dt.time().minute(),
                    q_dt.time().second(),
                    q_dt.time().msec() * 1000,
                )  # microseconds
                if q_dt.timeSpec() == Qt.TimeSpec.UTC:
                    value = dt_object.replace(tzinfo=timezone.utc)
                else:  # Assume local, or could be naive if not explicitly set
                    value = dt_object
            elif isinstance(widget, QLabel):  # BLOB placeholder
                value = self.instance_data.properties.get(current_prop_def.name) if self.mode == "edit" and self.instance_data and current_prop_def.name in self.instance_data.properties else None

            if not current_prop_def.is_nullable and (
                value is None or (isinstance(value, str) and not value.strip())
            ):
                # Special case for JSON: null is a valid JSON value, so if it's None and nullable, it's fine.
                # If it's None and NOT nullable, it's an error.
                if not (
                    current_prop_def.data_type == PropertyDataType.JSON
                    and value is None
                    and current_prop_def.is_nullable
                ):
                    QMessageBox.warning(
                        self,
                        "Missing Value",
                        f"Property '{current_prop_def.name}' is required.",
                    )
                    if hasattr(widget, "setFocus"):
                        widget.setFocus()  # type: ignore
                    is_valid = False
                    break

            properties_data[current_prop_def.name] = value

        if not is_valid:
            return None

        weight_val = Decimal(str(self.weight_spinbox.value()))

        instance_payload: dict[str, Any] = {
            "object_type_name": self.object_type.name,
            "properties": properties_data,
            "weight": weight_val,
        }

        if self.mode == "edit" and self.instance_data:
            instance_payload["id"] = self.instance_data.id

        try:
            return ObjectInstance(**instance_payload)
        except Exception as e:
            QMessageBox.critical(
                self, "Data Error", f"Could not create object instance: {e}",
            )
            return None

    def _connect_signals(self) -> None:
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def accept(self) -> None:
        object_instance_to_upsert = self._collect_data()

        if object_instance_to_upsert:
            # Client connection check will be handled by MainWindow's API handler
            self.busy_signal.emit(True)
            self.button_box.setEnabled(False)

            if self._active_upsert_thread and self._active_upsert_thread.isRunning():
                logger.warning("Upsert operation already in progress.")
                self.busy_signal.emit(False) # Reset busy if we don't proceed
                self.button_box.setEnabled(True)
                return

            self._active_upsert_thread = ApiClientThread(
                "upsert_object", # operation_name passed positionally
                object_instance_to_upsert, # obj for *args
                parent=self,
            )
            main_win = self._find_main_window()
            if main_win:
                self._active_upsert_thread.apiRequestReady.connect(main_win.handleApiRequest)
            else:
                self._on_upsert_error("Internal error: Cannot connect to API handler.")
                self._active_upsert_thread.deleteLater()
                self._active_upsert_thread = None
                # busy_signal and button_box re-enabled by _on_upsert_error via _cleanup_upsert_thread
                return

            self._active_upsert_thread.result_ready.connect(self._on_upsert_finished)
            self._active_upsert_thread.error_occurred.connect(self._on_upsert_error)
            self._active_upsert_thread.finished.connect(self._cleanup_upsert_thread)
            self._active_upsert_thread.start()

    @Slot(object) # Changed from ObjectInstance to Any
    def _on_upsert_finished(self, result: Any) -> None:
        # self.button_box.setEnabled(True) # Handled by cleanup
        # self.busy_signal.emit(False) # Handled by cleanup
        if not isinstance(result, ObjectInstance):
            self._on_upsert_error(f"Unexpected result type from upsert operation: {type(result)}")
            return

        upserted_instance: ObjectInstance = result
        QMessageBox.information(
            self,
            "Success",
            f"Object instance '{upserted_instance.id}' saved successfully.",
        )
        self.instance_upserted_signal.emit(upserted_instance.model_dump())
        super().accept()

    @Slot(str)
    def _on_upsert_error(self, error_message: str) -> None:
        # self.button_box.setEnabled(True) # Handled by cleanup
        # self.busy_signal.emit(False) # Handled by cleanup
        QMessageBox.critical(self, "Error Saving Instance", error_message)

    @Slot()
    def _cleanup_upsert_thread(self) -> None: # Renamed
        self.button_box.setEnabled(True)
        self.busy_signal.emit(False)
        if self._active_upsert_thread:
            self._active_upsert_thread.deleteLater()
            self._active_upsert_thread = None

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
        logger.warning("Could not find MainWindow instance for ObjectInstanceDialog.")
        return None

    # _perform_upsert_object_on_main_thread is removed.

    def closeEvent(self, event: Any) -> None: # Added type hint
        if self._active_upsert_thread and self._active_upsert_thread.isRunning():
            logger.info(f"Upsert thread {self._active_upsert_thread} running during close. Quitting.")
            self._active_upsert_thread.quit()
            if not self._active_upsert_thread.wait(500):
                logger.warning(f"Upsert thread {self._active_upsert_thread} did not finish. Terminating.")
                self._active_upsert_thread.terminate()
                self._active_upsert_thread.wait()
        self._active_upsert_thread = None # Clear reference
        super().closeEvent(event)

if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    from grizabella.core.models import RelationInstance  # Added import for mock methods

    app = QApplication(sys.argv)

    class MockGrizabella(Grizabella):
        def __init__( # pylint: disable=super-init-not-called
            self,
            db_name_or_path: Union[str, Path] = ":memory:",
            create_if_not_exists: bool = True,
        ) -> None:
            # For mock, we don't call super().__init__ to avoid actual DB setup
            self._is_connected = True
            # Add any other attributes Grizabella expects if not calling super
            self.db_path = (
                db_name_or_path  # Example if needed by other parts of Grizabella
            )

        def upsert_object(
            self, obj: ObjectInstance,
        ) -> ObjectInstance:  # Match base class signature
            # Simulate Pydantic default factory behavior if ID is not set or is default
            # The ObjectInstance model itself handles default_factory for id and upsert_date
            # This mock just ensures upsert_date is fresh, mimicking a DB update.
            obj.upsert_date = datetime.now(timezone.utc)
            if (
                not obj.id or str(obj.id) == "00000000-0000-0000-0000-000000000000"
            ):  # Check if default UUID
                obj.id = uuid.uuid4()  # Assign new if it was default (create case)
            return obj

        def get_relation(
            self, from_object_id: str, to_object_id: str, relation_type_name: str,
        ) -> list[RelationInstance]: # Match base class signature
            # Base class raises NotImplementedError, mock can do the same or return empty list
            # raise NotImplementedError("Mocked get_relation")
            return [] # Return empty list to match list[RelationInstance]

        def delete_relation( # Corrected signature
            self, relation_type_name: str, relation_id: str, # Match Grizabella.delete_relation
        ) -> bool:
            # Base class raises NotImplementedError, mock can do the same or return False
            # raise NotImplementedError("Mocked delete_relation")
            return False

    mock_client = MockGrizabella()

    person_properties = [
        PropertyDefinition(
            name="name",
            data_type=PropertyDataType.TEXT,
            is_nullable=False,
            description="Name of the person",
        ),
        PropertyDefinition(
            name="age",
            data_type=PropertyDataType.INTEGER,
            is_nullable=True,
            description="Age of the person",
        ),
        PropertyDefinition(
            name="email", data_type=PropertyDataType.TEXT, is_nullable=True,
        ),  # Changed STRING to TEXT
        PropertyDefinition(
            name="is_active", data_type=PropertyDataType.BOOLEAN, is_nullable=True,
        ),
        PropertyDefinition(
            name="bio",
            data_type=PropertyDataType.TEXT,
            is_nullable=True,
            description="Short biography",
        ),
        PropertyDefinition(
            name="preferences",
            data_type=PropertyDataType.JSON,
            is_nullable=True,
            description="User preferences in JSON format",
        ),
        PropertyDefinition(
            name="last_login", data_type=PropertyDataType.DATETIME, is_nullable=True,
        ),
        PropertyDefinition(
            name="avatar",
            data_type=PropertyDataType.BLOB,
            is_nullable=True,
            description="User avatar image data",
        ),
        PropertyDefinition(
            name="salary",
            data_type=PropertyDataType.FLOAT,
            is_nullable=True,
            description="Salary",
        ),
        PropertyDefinition(
            name="custom_uuid",
            data_type=PropertyDataType.UUID,
            is_nullable=True,
            description="A custom UUID field",
        ),
    ]
    person_object_type_def = ObjectTypeDefinition(
        name="Person", properties=person_properties, description="A person object type",
    )

    # Test Create Mode
    dialog_create = ObjectInstanceDialog(
        grizabella_client=mock_client, object_type=person_object_type_def, mode="create",
    )
    dialog_create.setWindowTitle("Create Person Test")

    @Slot(dict)
    def on_created(data: dict) -> None:
        pass

    dialog_create.instance_upserted_signal.connect(on_created)

    if dialog_create.exec():
        pass
    else:
        pass

    # Test Edit Mode
    existing_person_data = ObjectInstance(
        id=uuid.uuid4(),
        object_type_name="Person",
        properties={
            "name": "Jane Doe",
            "age": 30,
            "email": "jane.doe@example.com",
            "is_active": True,
            "bio": "Software developer.",
            "preferences": {"theme": "dark"},
            "last_login": datetime(2023, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            "avatar": None,
            "salary": 75000.50,
            "custom_uuid": uuid.uuid4(),
        },
        weight=Decimal("1.5"),
    )

    dialog_edit = ObjectInstanceDialog(
        grizabella_client=mock_client,
        object_type=person_object_type_def,
        mode="edit",
        instance_data=existing_person_data,
    )
    dialog_edit.setWindowTitle("Edit Person Test")

    @Slot(dict)
    def on_edited(data: dict) -> None:
        pass

    dialog_edit.instance_upserted_signal.connect(on_edited)  # type: ignore

    if dialog_edit.exec():  # type: ignore
        pass
    else:
        pass

    sys.exit(app.exec())
