"""Qt TableModel for displaying ObjectInstance data."""
from __future__ import annotations

from typing import Any, Optional  # Moved typing import first, Added Optional

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)

from grizabella.core.models import ObjectInstance, PropertyDefinition


# For mock/placeholder if real models are not yet fully integrated or for testing
class MockPropertyDefinition:
    def __init__(self, name: str, data_type: str, description: str = "") -> None:
        self.name = name
        # e.g., "STRING", "INTEGER", "FLOAT", "BOOLEAN", "DATETIME", "JSON", "BLOB"
        self.data_type = data_type
        self.description = description


class MockObjectInstance:
    def __init__(self, id: str, object_type: str, properties: dict[str, Any]) -> None:
        self.id = id
        self.object_type = object_type
        self.properties = properties
        self.weight: float = 1.0
        self.upsert_date: str | None = "2024-01-01T00:00:00Z"  # Mock date


class ObjectInstanceTableModel(QAbstractTableModel):
    """A Qt TableModel for displaying ObjectInstance data.
    Columns are dynamically determined by the PropertyDefinitions of the ObjectType.
    """

    # Define roles for custom data if needed, e.g., for raw data object
    RawDataRole = Qt.ItemDataRole.UserRole + 1

    def __init__(
        self,
        property_definitions: list[PropertyDefinition],
        parent: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self._instances: list[ObjectInstance] = []
        self._property_definitions: list[PropertyDefinition] = []
        self._headers: list[str] = []
        self.update_property_definitions(property_definitions)

    def update_property_definitions(
        self, property_definitions: list[PropertyDefinition],
    ) -> None:
        self.beginResetModel()
        # Sort by name for consistent order
        self._property_definitions = sorted(
            property_definitions, key=lambda pd: pd.name,
        )

        # Ensure 'id' is always the first column if present
        id_prop = next(
            (pd for pd in self._property_definitions if pd.name == "id"), None,
        )
        if id_prop:
            self._property_definitions.remove(id_prop)
            self._property_definitions.insert(0, id_prop)

        self._headers = [pd.name for pd in self._property_definitions]
        self.endResetModel()

    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._instances)

    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._headers)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if 0 <= section < len(self._headers):
                    # Make header more readable
                    return self._headers[section].replace("_", " ").title()
            elif orientation == Qt.Orientation.Vertical:
                return str(section + 1)  # Row numbers
        return None

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._instances):
            return None

        instance = self._instances[index.row()]
        column_name = self._headers[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            # Special handling for 'id' if it's directly on instance
            if column_name == "id":
                return getattr(instance, "id", None)

            # Access property from the 'properties' dictionary
            value = instance.properties.get(column_name)

            # Basic formatting for display
            # if isinstance(value, (list, dict)): # For JSON/BLOB, show placeholder or summary
            #     prop_def = self._property_definitions[index.column()]
            #     if prop_def.data_type == PropertyDataType.JSON:
            #         return "[JSON Data]"
            #     elif prop_def.data_type == PropertyDataType.BLOB:
            #         return "[BLOB Data]"
            #     return str(value) # Fallback for other complex types
            if isinstance(value, (list, dict)):
                # Placeholder for complex types
                return f"[{type(value).__name__} Data]"

            if value is None:
                return ""  # Display empty string for None
            return str(value)

        if role == Qt.ItemDataRole.ToolTipRole:
            prop_def = self._property_definitions[index.column()]
            return f"{prop_def.description}\nType: {prop_def.data_type}"

        if role == ObjectInstanceTableModel.RawDataRole:
            return instance  # Return the whole ObjectInstance object

        return None

    def set_instances(self, instances: list[ObjectInstance]) -> None:
        self.beginResetModel()
        self._instances = instances if instances else []
        self.endResetModel()

    def clear_data(self) -> None:
        self.beginResetModel()
        self._instances = []
        self.endResetModel()

    def get_instance_at_row(
        self, row: int,
    ) -> Optional[ObjectInstance]:
        if 0 <= row < len(self._instances):
            return self._instances[row]
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Sort table by given column number."""
        if not 0 <= column < len(self._headers):
            return

        self.layoutAboutToBeChanged.emit()
        column_name = self._headers[column]

        def sort_key(instance: ObjectInstance):
            value = instance.properties.get(column_name)
            if column_name == "id":  # Special handling for 'id'
                value = getattr(instance, "id", None)

            if value is None:  # Handle None values for sorting
                return ""  # Or some other placeholder that sorts consistently
            # Attempt to convert to a comparable type if it's simple
            if isinstance(value, (int, float, bool)):
                return value
            return str(value).lower()  # Default to case-insensitive string comparison

        try:
            self._instances.sort(
                key=sort_key, reverse=order == Qt.SortOrder.DescendingOrder,
            )
        except TypeError:
            # Optionally, fall back to string comparison for all if mixed types are problematic
            self._instances.sort(
                key=lambda x: str(x.properties.get(column_name, "")).lower(),
                reverse=order == Qt.SortOrder.DescendingOrder,
            )

        self.layoutChanged.emit()
