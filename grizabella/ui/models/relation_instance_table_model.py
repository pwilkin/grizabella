"""Qt TableModel for displaying RelationInstance data."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any  # Moved typing import first

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal

if TYPE_CHECKING:
    from grizabella.core.models import RelationInstance


class RelationInstanceTableModel(QAbstractTableModel):
    """A table model for displaying RelationInstance objects."""

    data_updated = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._headers = [
            "ID",
            "Source Object ID",
            "Target Object ID",
            "Weight",
            "Upsert Date",
            # Custom properties will be added dynamically
        ]
        self._relation_instances: list[RelationInstance] = []
        self._custom_property_keys: list[str] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._relation_instances)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._headers)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole and section < len(self._headers):
            return self._headers[section]
        return None

    def data(self, index: QModelIndex | QPersistentModelIndex,
             role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        relation_instance = self._relation_instances[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(relation_instance.id)
            if col == 1:
                return str(relation_instance.source_object_instance_id)
            if col == 2:
                return str(relation_instance.target_object_instance_id)
            if col == 3:
                return str(relation_instance.weight)
            if col == 4:
                return (relation_instance.upsert_date.strftime("%Y-%m-%d %H:%M:%S")
                        if relation_instance.upsert_date else "N/A")
            if col >= 5:
                custom_prop_index = col - 5
                if custom_prop_index < len(self._custom_property_keys):
                    key = self._custom_property_keys[custom_prop_index]
                    return str(relation_instance.properties.get(key, "N/A"))
                return "N/A" # Should not happen if headers are synced

        elif role == Qt.ItemDataRole.UserRole: # For sorting or filtering if needed
            return relation_instance

        return None

    def set_relation_instances(self, instances: list[RelationInstance],
                               relation_type_definition: dict[str, Any] | None = None) -> None:
        self.beginResetModel()
        self._relation_instances = instances if instances else []

        # Update headers with custom properties
        self._custom_property_keys = []
        if relation_type_definition and relation_type_definition.get("property_schema"):
            self._custom_property_keys = sorted(
                relation_type_definition["property_schema"].keys(),
            )

        self._headers = [
            "ID",
            "Source Object ID",
            "Target Object ID",
            "Weight",
            "Upsert Date",
        ] + [f"Prop: {key}" for key in self._custom_property_keys]

        self.endResetModel()
        self.data_updated.emit()

    def get_relation_instance_at_row(self, row: int) -> RelationInstance | None:
        if 0 <= row < len(self._relation_instances):
            return self._relation_instances[row]
        return None

    def clear(self) -> None:
        self.beginResetModel()
        self._relation_instances = []
        self._custom_property_keys = []
        self._headers = [
            "ID",
            "Source Object ID",
            "Target Object ID",
            "Weight",
            "Upsert Date",
        ]
        self.endResetModel()
        self.data_updated.emit()
