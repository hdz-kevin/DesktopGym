"""Tabla generica con paginacion.

Se usa QTableView con un modelo propio en vez de QTableWidget: el modelo solo
guarda la pagina visible, asi que la memoria no crece con el historico y el
desplazamiento sigue siendo fluido con miles de registros.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from gym.ui.theme import TEXT_MUTED

T = TypeVar("T")


@dataclass
class Column(Generic[T]):
    """Definicion de una columna: como se titula y como se extrae su texto."""

    title: str
    value: Callable[[T], Any]
    width: int | None = None
    stretch: bool = False
    align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    color: Callable[[T], str | None] = field(default=lambda _: None)


class RecordTableModel(QAbstractTableModel, Generic[T]):
    def __init__(self, columns: list[Column[T]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns = columns
        self._rows: list[T] = []

    def set_rows(self, rows: list[T]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def record_at(self, row: int) -> T | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        record = self._rows[index.row()]
        column = self._columns[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            value = column.value(record)
            return "" if value is None else str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(column.align)
        if role == Qt.ItemDataRole.ForegroundRole:
            color = column.color(record)
            return QColor(color) if color else None
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        return self._columns[section].title


class PagedTable(QWidget, Generic[T]):
    """Tabla con controles de paginacion y aviso de vacio."""

    row_activated = Signal(object)
    page_changed = Signal(int)

    def __init__(
        self,
        columns: list[Column[T]],
        page_size: int = 25,
        empty_text: str = "No hay registros para mostrar.",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.page_size = page_size
        self._page = 1
        self._total = 0

        self.model = RecordTableModel(columns, self)

        self.view = QTableView(self)
        self.view.setModel(self.model)
        self.view.verticalHeader().setVisible(False)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setAlternatingRowColors(False)
        self.view.setShowGrid(False)
        self.view.verticalHeader().setDefaultSectionSize(44)
        self.view.doubleClicked.connect(self._emit_activated)

        header = self.view.horizontalHeader()
        header.setHighlightSections(False)
        for i, column in enumerate(columns):
            if column.stretch:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            elif column.width:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.view.setColumnWidth(i, column.width)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        self.empty_label = QLabel(empty_text, self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {TEXT_MUTED}; padding: 40px;")
        self.empty_label.hide()

        self.summary = QLabel("", self)
        self.summary.setObjectName("muted")
        self.prev_button = QPushButton("Anterior", self)
        self.next_button = QPushButton("Siguiente", self)
        self.prev_button.clicked.connect(lambda: self.go_to_page(self._page - 1))
        self.next_button.clicked.connect(lambda: self.go_to_page(self._page + 1))

        pager = QHBoxLayout()
        pager.setContentsMargins(2, 0, 2, 0)
        pager.addWidget(self.summary)
        pager.addStretch(1)
        pager.addWidget(self.prev_button)
        pager.addWidget(self.next_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.empty_label)
        layout.addLayout(pager)

    @property
    def page(self) -> int:
        return self._page

    @property
    def offset(self) -> int:
        return (self._page - 1) * self.page_size

    @property
    def page_count(self) -> int:
        return max(1, -(-self._total // self.page_size))

    def set_data(self, rows: list[T], total: int) -> None:
        self._total = total
        self.model.set_rows(rows)

        has_rows = bool(rows)
        self.view.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)

        first = self.offset + 1 if has_rows else 0
        last = self.offset + len(rows)
        self.summary.setText(f"{first}-{last} de {total}" if has_rows else "Sin resultados")
        self.prev_button.setEnabled(self._page > 1)
        self.next_button.setEnabled(self._page < self.page_count)

    def go_to_page(self, page: int) -> None:
        page = max(1, min(page, self.page_count))
        if page != self._page:
            self._page = page
            self.page_changed.emit(page)

    def reset_page(self) -> None:
        """Vuelve a la primera pagina, por ejemplo al cambiar un filtro."""
        self._page = 1

    def selected_record(self) -> T | None:
        indexes = self.view.selectionModel().selectedRows()
        if not indexes:
            return None
        return self.model.record_at(indexes[0].row())

    def _emit_activated(self, index: QModelIndex) -> None:
        record = self.model.record_at(index.row())
        if record is not None:
            self.row_activated.emit(record)
