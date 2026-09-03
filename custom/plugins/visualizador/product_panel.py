# =============================================================================
# custom/plugins/visualizador/product_panel.py
# =============================================================================
# Panel dock lateral con:
#   - Buscador de productos (SKU índice / UPC / palabra clave)
#   - Miniaturas del catálogo
#   - Info del producto seleccionado
#   - Editor de etiqueta para la caja activa en el canvas
#   - Menú de opciones: activar/desactivar funciones del plugin
# =============================================================================

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPixmap
from PyQt5.QtWidgets import (
    QAction, QCheckBox, QDialog, QDockWidget, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMenu,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from libs.utils import generate_color_by_text

if TYPE_CHECKING:
    from .catalog_db import CatalogDB
    from .hover_tooltip import HoverTooltipManager

# ── Constantes de diseño ──────────────────────────────────────────────────────
_DARK_BG      = "#0f0f17"
_PANEL_BG     = "#1e1e2e"
_CARD_BG      = "#181825"
_BORDER       = "#45475a"
_TEXT_MAIN    = "#cdd6f4"
_TEXT_SUB     = "#a6adc8"
_ACCENT_GREEN = "#a6e3a1"
_ACCENT_BLUE  = "#89dceb"
_ACCENT_YELL  = "#f9e2af"
_ACCENT_RED   = "#f38ba8"
_ACCENT_PINK  = "#f5c2e7"
_ACCENT_LAVEN = "#cba6f7"

_THUMB_SMALL  = 80    # miniatura en resultados
_THUMB_LARGE  = 140   # miniatura en detalle
_MAX_RESULTS  = 60


_STYLESHEET = f"""
QDockWidget {{
    color: {_TEXT_MAIN};
    font-size: 13px;
}}
QDockWidget::title {{
    background-color: {_PANEL_BG};
    color: {_ACCENT_LAVEN};
    font-weight: bold;
    padding: 6px 10px;
}}
QWidget#panel_root {{
    background-color: {_DARK_BG};
}}
QGroupBox {{
    background-color: {_PANEL_BG};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding: 8px 6px 6px 6px;
    color: {_ACCENT_LAVEN};
    font-weight: bold;
    font-size: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}
QLineEdit {{
    background-color: {_CARD_BG};
    color: {_TEXT_MAIN};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 6px 8px;
    font-size: 12px;
}}
QLineEdit:focus {{
    border-color: {_ACCENT_BLUE};
}}
QPushButton {{
    background-color: {_PANEL_BG};
    color: {_ACCENT_BLUE};
    border: 1px solid {_ACCENT_BLUE};
    border-radius: 5px;
    padding: 6px 12px;
    font-weight: bold;
    font-size: 11px;
}}
QPushButton:hover {{
    background-color: {_ACCENT_BLUE};
    color: {_DARK_BG};
}}
QPushButton#btn_apply {{
    color: {_ACCENT_GREEN};
    border-color: {_ACCENT_GREEN};
}}
QPushButton#btn_apply:hover {{
    background-color: {_ACCENT_GREEN};
    color: {_DARK_BG};
}}
QPushButton#btn_clear {{
    color: {_ACCENT_RED};
    border-color: {_ACCENT_RED};
    font-size: 10px;
    padding: 4px 8px;
}}
QPushButton#btn_clear:hover {{
    background-color: {_ACCENT_RED};
    color: {_DARK_BG};
}}
QPushButton#btn_options {{
    color: {_ACCENT_YELL};
    border-color: {_ACCENT_YELL};
    font-size: 11px;
}}
QPushButton#btn_options:hover {{
    background-color: {_ACCENT_YELL};
    color: {_DARK_BG};
}}
QListWidget {{
    background-color: {_CARD_BG};
    color: {_TEXT_MAIN};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    font-size: 11px;
    outline: none;
}}
QListWidget::item:selected {{
    background-color: {_ACCENT_LAVEN};
    color: {_DARK_BG};
}}
QListWidget::item:hover {{
    background-color: #313244;
}}
QScrollArea {{
    background-color: {_CARD_BG};
    border: 1px solid {_BORDER};
    border-radius: 4px;
}}
QLabel#field_key {{
    color: {_ACCENT_YELL};
    font-size: 11px;
    font-weight: bold;
}}
QLabel#field_val {{
    color: {_TEXT_MAIN};
    font-size: 11px;
}}
QLabel#section_hdr {{
    color: {_ACCENT_PINK};
    font-size: 12px;
    font-weight: bold;
    padding: 4px 0;
}}
QLabel#status_bar {{
    color: {_TEXT_SUB};
    font-size: 10px;
    padding: 2px 6px;
}}
QCheckBox {{
    color: {_TEXT_MAIN};
    font-size: 11px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {_BORDER};
    border-radius: 3px;
    background: {_CARD_BG};
}}
QCheckBox::indicator:checked {{
    background: {_ACCENT_GREEN};
    border-color: {_ACCENT_GREEN};
}}
"""


# =============================================================================
class _ImageGrid(QWidget):
    """Widget interno: grilla de miniaturas, 3 columnas."""

    clicked = pyqtSignal(int)   # índice de la imagen clicada

    def __init__(self, thumb_size: int = _THUMB_LARGE, parent=None):
        super().__init__(parent)
        self._size  = thumb_size
        self._layout = QGridLayout(self)
        self._layout.setSpacing(6)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._pixmaps: list[QPixmap] = []

    def set_images(self, paths: list[str]) -> None:
        # Limpiar
        for i in reversed(range(self._layout.count())):
            item = self._layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        self._pixmaps.clear()

        for idx, path in enumerate(paths):
            btn = QPushButton()
            btn.setFixedSize(self._size, self._size)
            btn.setStyleSheet(
                f"background:{_CARD_BG}; border:1px solid {_BORDER};"
                "border-radius:4px; padding:0;"
            )
            btn.setCursor(Qt.PointingHandCursor)

            if os.path.isfile(path):
                px = QPixmap(path)
                if not px.isNull():
                    px = px.scaled(self._size, self._size,
                                   Qt.KeepAspectRatio,
                                   Qt.SmoothTransformation)
                    btn.setIcon(btn.style().standardIcon(0))  # clear
                    from PyQt5.QtGui import QIcon
                    btn.setIcon(QIcon(px))
                    btn.setIconSize(btn.size())
                    self._pixmaps.append(px)

            row, col = divmod(idx, 3)
            self._layout.addWidget(btn, row, col)
            _idx = idx
            btn.clicked.connect(lambda _, i=_idx: self.clicked.emit(i))

        self.adjustSize()


# =============================================================================
class _OptionsDialog(QDialog):
    """Diálogo con checkboxes para activar/desactivar funciones del plugin."""

    def __init__(self, options: dict[str, bool], parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Opciones del Visualizador")
        self.setMinimumWidth(400)
        self.setStyleSheet(f"""
            QDialog {{ background-color:{_DARK_BG}; color:{_TEXT_MAIN}; }}
            QLabel  {{ color:{_TEXT_MAIN}; font-size:12px; }}
        """ + _STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("⚙️  Funciones del Visualizador")
        title.setStyleSheet(f"font-size:15px; color:{_ACCENT_LAVEN}; font-weight:bold;")
        layout.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color:{_BORDER};")
        layout.addWidget(line)

        self._checks: dict[str, QCheckBox] = {}

        groups = {
            "🖼️  Tooltip": {
                "hover_tooltip":     "Tooltip al pasar el cursor (1 imagen)",
                "selection_tooltip": "Tooltip al seleccionar una caja (3 imágenes)",
            },
            "💡  Sugerencias extra": {
                "smart_label":      "Asignar etiqueta inteligente desde búsqueda",
                "highlight_match":  "Resaltar cajas del producto buscado",
                "search_history":   "Historial de búsquedas recientes",
                "label_validation": "Validar etiquetas al guardar",
            },
        }

        for group_name, items in groups.items():
            gb = QGroupBox(group_name)
            gb_layout = QVBoxLayout(gb)
            gb_layout.setSpacing(8)
            for key, desc in items.items():
                cb = QCheckBox(desc)
                cb.setChecked(options.get(key, True))
                self._checks[key] = cb
                gb_layout.addWidget(cb)
            layout.addWidget(gb)

        # Botones
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("✔ Guardar")
        btn_ok.setObjectName("btn_apply")
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        

    def get_values(self) -> dict[str, bool]:
        return {k: cb.isChecked() for k, cb in self._checks.items()}


# =============================================================================
class ProductPanel(QDockWidget):
    """
    Panel lateral (dock) completo del plugin Visualizador.
    """

    def __init__(self, main_window, db: "CatalogDB",
                 tooltip_mgr: "HoverTooltipManager"):
        super().__init__("🔍 Visualizador de Productos", main_window)

        self.setObjectName("product_panel_dock")

        self.mw          = main_window
        self.db          = db
        self.tooltip_mgr = tooltip_mgr

        # Guarda la lista estática inicial de clases predefinidas
        self._official_yolo_classes = list(getattr(self.mw, "label_hist", []))
    

        # Opciones (activas por defecto)
        self._options: dict[str, bool] = {
            "hover_tooltip":     True,
            "selection_tooltip": True,
            "smart_label":       True,
            "highlight_match":   True,
            "search_history":    True,
            "label_validation":  True,
        }

        # Historial de búsquedas
        self._history: list[str] = []

        # Caché de pixmaps de resaltado
        self._highlight_shapes: list = []

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )
        self.setMinimumWidth(180)

        self._build_ui()
        self._connect_signals()

        self._load_options()
        self._apply_options()

    # ── Construcción UI ───────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("panel_root")
        root.setStyleSheet(_STYLESHEET)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # ─── Cabecera con opciones ─────────────────────────────────────────
        hdr = QHBoxLayout()
        lbl_title = QLabel("🔍 Visualizador")
        lbl_title.setStyleSheet(
            f"color:{_ACCENT_PINK}; font-size:14px; font-weight:bold;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()

        btn_add = QPushButton("🔄 Actualizar Catálogo")
        btn_add.setObjectName("btn_apply")
        btn_add.clicked.connect(self._open_update_catalog_dialog)
        hdr.addWidget(btn_add)

        btn_opts = QPushButton("⚙️ Opciones")
        btn_opts.setObjectName("btn_options")
        btn_opts.clicked.connect(self._open_options)
        hdr.addWidget(btn_opts)
        outer.addLayout(hdr)

        # ─── Búsqueda ──────────────────────────────────────────────────────
        grp_search = QGroupBox("🔍  Búsqueda")
        sv = QVBoxLayout(grp_search)
        sv.setSpacing(6)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(
            "SKU índice, UPC o nombre del producto…")
        sv.addWidget(self._search_edit)

        row_btns = QHBoxLayout()
        self._btn_search = QPushButton("Buscar")
        self._btn_clear  = QPushButton("✕")
        self._btn_clear.setObjectName("btn_clear")
        self._btn_clear.setFixedWidth(30)
        self._btn_clear.setToolTip("Limpiar búsqueda")
        row_btns.addWidget(self._btn_search)
        row_btns.addWidget(self._btn_clear)
        sv.addLayout(row_btns)

        # Historial
        self._history_lbl = QLabel("Recientes:")
        self._history_lbl.setObjectName("status_bar")
        self._history_lbl.hide()
        sv.addWidget(self._history_lbl)

        self._history_list = QListWidget()
        self._history_list.setMaximumHeight(80)
        self._history_list.hide()
        sv.addWidget(self._history_list)

        outer.addWidget(grp_search)

        # ─── Resultados ────────────────────────────────────────────────────
        grp_results = QGroupBox("📋  Resultados")
        rv = QVBoxLayout(grp_results)

        self._results_list = QListWidget()
        self._results_list.setMinimumHeight(100)
        self._results_list.setMaximumHeight(180)
        rv.addWidget(self._results_list)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("status_bar")
        rv.addWidget(self._status_lbl)

        outer.addWidget(grp_results)

        # ─── Detalle del producto ──────────────────────────────────────────
        grp_detail = QGroupBox("🖼️  Producto")
        dv = QVBoxLayout(grp_detail)
        dv.setSpacing(6)

        # Miniaturas
        self._img_scroll = QScrollArea()
        self._img_scroll.setWidgetResizable(True)
        self._img_scroll.setFixedHeight(180)
        self._img_inner = _ImageGrid(_THUMB_LARGE)
        self._img_scroll.setWidget(self._img_inner)
        dv.addWidget(self._img_scroll)

        # Botón asignar etiqueta inteligente
        self._btn_smart = QPushButton("⚡ Asignar etiqueta al seleccionado")
        self._btn_smart.setObjectName("btn_apply")
        self._btn_smart.setToolTip(
            "Asigna automáticamente la etiqueta correcta a la caja seleccionada")
        self._btn_smart.hide()
        dv.addWidget(self._btn_smart)

        # Info del producto (scroll)
        self._info_scroll = QScrollArea()
        self._info_scroll.setWidgetResizable(True)
        self._info_scroll.setMinimumHeight(120)
        self._info_widget = QWidget()
        self._info_widget.setStyleSheet(f"background:{_CARD_BG};")
        self._info_layout = QVBoxLayout(self._info_widget)
        self._info_layout.setSpacing(3)
        self._info_layout.setContentsMargins(6, 6, 6, 6)
        self._info_scroll.setWidget(self._info_widget)
        dv.addWidget(self._info_scroll)

        outer.addWidget(grp_detail)

        # ─── Editor de etiqueta ────────────────────────────────────────────
        grp_edit = QGroupBox("✏️  Editar etiqueta de la caja activa")
        ev_layout = QVBoxLayout(grp_edit)
        ev_layout.setSpacing(6)

        self._cur_label_lbl = QLabel("Sin caja seleccionada")
        self._cur_label_lbl.setObjectName("status_bar")
        self._cur_label_lbl.setWordWrap(True)
        ev_layout.addWidget(self._cur_label_lbl)

        self._edit_label = QLineEdit()
        self._edit_label.setPlaceholderText("Nueva etiqueta…")
        self._edit_label.setEnabled(False)
        ev_layout.addWidget(self._edit_label)

        row_edit = QHBoxLayout()
        self._btn_apply_label = QPushButton("✔ Aplicar")
        self._btn_apply_label.setObjectName("btn_apply")
        self._btn_apply_label.setEnabled(False)
        self._btn_validate   = QPushButton("🔍 Validar")
        self._btn_validate.setToolTip("Verificar si la etiqueta existe en el catálogo")
        row_edit.addWidget(self._btn_apply_label)
        row_edit.addWidget(self._btn_validate)
        ev_layout.addLayout(row_edit)

        outer.addWidget(grp_edit)
        outer.addStretch()

        # ─── Barra de estado ───────────────────────────────────────────────
        self._bottom_status = QLabel("Listo")
        self._bottom_status.setObjectName("status_bar")
        self._bottom_status.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._bottom_status)

        # ─── ScrollArea contenedor principal ───────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # Aparece SOLO cuando el panel es más estrecho que la cabecera
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)    # Muestra scroll vertical si el contenido alto no cabe

        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {_DARK_BG}; }}")
        scroll.setWidget(root)

        self.setWidget(scroll)

    # ── Conexión de señales ───────────────────────────────────────────────────
    def _connect_signals(self) -> None:
        self._btn_search.clicked.connect(self._do_search)
        self._btn_clear.clicked.connect(self._clear_search)
        self._search_edit.returnPressed.connect(self._do_search)
        self._results_list.currentRowChanged.connect(self._on_result_selected)
        self._history_list.itemClicked.connect(self._on_history_item_clicked)
        self._btn_apply_label.clicked.connect(self._apply_label)
        self._btn_validate.clicked.connect(self._validate_label)
        self._btn_smart.clicked.connect(self._apply_smart_label)

        # Canvas
        try:
            self.mw.canvas.selectionChanged.connect(self._on_canvas_selection)
        except Exception:
            pass

        # Guardar: validación según formato activo
        original_save = getattr(self.mw, "save_file", None)
        if original_save:
            def patched_save(*args, **kwargs):
                if self._options.get("label_validation", True):
                    if not self._validate_before_save():
                        return False  # Cancela la acción de guardar si el usuario presiona "No"
                return original_save(*args, **kwargs)
            self.mw.save_file = patched_save

    # ── Búsqueda ──────────────────────────────────────────────────────────────
    def _do_search(self) -> None:
        query = self._search_edit.text().strip()
        if not query:
            self._status_lbl.setText("Escribe algo para buscar.")
            return

        results = self.db.search(query)
        self._results_list.clear()

        # Actualizar historial
        if self._options.get("search_history", True):
            if query not in self._history:
                self._history.insert(0, query)
                if len(self._history) > 10:
                    self._history.pop()
            self._update_history_widget()

        if results.empty:
            self._status_lbl.setText("❌ Sin resultados")
            self._clear_detail()
            return

        self._status_lbl.setText(
            f"✅ {len(results)} resultado(s) — selecciona uno")

        # Guardar para uso posterior
        self._current_results = results.reset_index(drop=False)

        for _, row in self._current_results.iterrows():
            nombre   = str(row.get("nombre_capturado", ""))[:45]
            sku_idx  = str(row.get("sku_indice", ""))
            gramaje  = str(row.get("gramaje", ""))
            text     = f"[{sku_idx}] {nombre}  {gramaje}"
            item     = QListWidgetItem(text)
            item.setToolTip(nombre)
            self._results_list.addItem(item)

    def _clear_search(self) -> None:
        self._search_edit.clear()
        self._results_list.clear()
        self._status_lbl.setText("")
        self._clear_detail()
        self._clear_highlight()
        self._btn_smart.hide()

    # ── Historial ─────────────────────────────────────────────────────────────
    def _update_history_widget(self) -> None:
        if not self._options.get("search_history", True) or not self._history:
            self._history_lbl.hide()
            self._history_list.hide()
            return
        self._history_lbl.show()
        self._history_list.show()
        self._history_list.clear()
        for h in self._history:
            self._history_list.addItem(h)

    def _on_history_item_clicked(self, item: QListWidgetItem) -> None:
        self._search_edit.setText(item.text())
        self._do_search()

    # ── Detalle del producto ──────────────────────────────────────────────────
    def _on_result_selected(self, row_idx: int) -> None:
        if row_idx < 0 or not hasattr(self, "_current_results"):
            return
        if row_idx >= len(self._current_results):
            return

        row = self._current_results.iloc[row_idx]
        upc = str(row.get("upc_version", ""))

        # Imágenes
        img_paths = self.db.get_images(upc, max_images=9)
        self._img_inner.set_images(img_paths)

        # Info
        self._show_info(row)

        # Resaltado
        if self._options.get("highlight_match", True):
            sku_idx = str(row.get("sku_indice", ""))
            self._highlight_boxes(sku_idx)

        # Botón de asignación inteligente
        if self._options.get("smart_label", True):
            self._smart_label_data = row
            self._btn_smart.show()
        else:
            self._btn_smart.hide()

    def _show_info(self, row) -> None:
        # Limpiar
        for i in reversed(range(self._info_layout.count())):
            item = self._info_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        ordered = self.db.ordered_record(row)
        for key, val in ordered:
            if not val or val == "nan":
                continue
            row_w = QWidget()
            row_w.setStyleSheet(f"background:{_CARD_BG};")
            rh = QHBoxLayout(row_w)
            rh.setContentsMargins(2, 2, 2, 2)
            rh.setSpacing(6)

            lk = QLabel(f"{key}:")
            lk.setObjectName("field_key")
            lk.setFixedWidth(120)
            lk.setAlignment(Qt.AlignRight | Qt.AlignTop)

            lv = QLabel(val)
            lv.setObjectName("field_val")
            lv.setWordWrap(True)
            lv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            rh.addWidget(lk)
            rh.addWidget(lv)
            self._info_layout.addWidget(row_w)

        self._info_layout.addStretch()

    def _clear_detail(self) -> None:
        self._img_inner.set_images([])
        for i in reversed(range(self._info_layout.count())):
            item = self._info_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

    # ── Resaltado ─────────────────────────────────────────────────────────────
    def _highlight_boxes(self, sku_indice: str) -> None:
        """Resalta con borde grueso las cajas que coinciden con el SKU índice."""
        self._clear_highlight()
        if not sku_indice:
            return
        for shape in self.mw.canvas.shapes:
            if self.db.parse_sku_indice(shape.label or "") == sku_indice:
                # Guardar color original y cambiar temporalmente
                shape._orig_lc = shape.line_color
                shape.line_color = QColor(255, 215, 0)   # dorado
                self._highlight_shapes.append(shape)
        self.mw.canvas.update()

    def _clear_highlight(self) -> None:
        for shape in self._highlight_shapes:
            if hasattr(shape, "_orig_lc"):
                shape.line_color = shape._orig_lc
        self._highlight_shapes.clear()
        try:
            self.mw.canvas.update()
        except Exception:
            pass

    # ── Selección en canvas ───────────────────────────────────────────────────
    def _on_canvas_selection(self, selected: bool) -> None:
        shape = self.mw.canvas.selected_shape
        if not selected or shape is None:
            self._cur_label_lbl.setText("Sin caja seleccionada")
            self._edit_label.setEnabled(False)
            self._edit_label.clear()
            self._btn_apply_label.setEnabled(False)
            return

        label = shape.label or ""
        self._cur_label_lbl.setText(f"Etiqueta actual:  {label}")
        self._edit_label.setText(label)
        self._edit_label.setEnabled(True)
        self._btn_apply_label.setEnabled(True)

    # ── Etiqueta inteligente ──────────────────────────────────────────────────
    def _apply_smart_label(self) -> None:
        if not hasattr(self, "_smart_label_data"):
            return
        shape = self.mw.canvas.selected_shape
        if shape is None:
            QMessageBox.warning(
                self, "Sin selección",
                "Selecciona primero una caja en el canvas.")
            return

        row      = self._smart_label_data
        sku_idx  = str(row.get("sku_indice", ""))
        upc_ver  = str(row.get("upc_version", ""))
        new_lbl  = f"{sku_idx}_{upc_ver}" if sku_idx and upc_ver else upc_ver

        reply = QMessageBox.question(
            self, "Asignar etiqueta",
            f"¿Asignar etiqueta a la caja seleccionada?\n\n"
            f"Etiqueta actual:  {shape.label}\n"
            f"Nueva etiqueta:   {new_lbl}",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return

        self._set_shape_label(shape, new_lbl)
        self._cur_label_lbl.setText(f"Etiqueta actual:  {new_lbl}")
        self._edit_label.setText(new_lbl)
        self._set_status(f"✅ Etiqueta asignada: {new_lbl}")

    # ── Editor de etiqueta manual ─────────────────────────────────────────────
    def _apply_label(self) -> None:
        shape = self.mw.canvas.selected_shape
        if shape is None:
            QMessageBox.warning(
                self, "Sin selección",
                "Selecciona una caja en el canvas primero.")
            return

        new_label = self._edit_label.text().strip()
        if not new_label:
            QMessageBox.warning(self, "Etiqueta vacía",
                                "La etiqueta no puede estar vacía.")
            return

        if new_label == shape.label:
            self._set_status("ℹ️ La etiqueta no cambió.")
            return

        reply = QMessageBox.question(
            self, "Confirmar cambio",
            f"¿Cambiar la etiqueta de la caja seleccionada?\n\n"
            f"Actual:  {shape.label}\n"
            f"Nueva:   {new_label}",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return

        self._set_shape_label(shape, new_label)
        self._cur_label_lbl.setText(f"Etiqueta actual:  {new_label}")
        self._set_status(f"✅ Etiqueta cambiada a: {new_label}")

    def _validate_label(self) -> None:
        """Verifica si el texto en el campo de edición existe en el catálogo."""
        text = self._edit_label.text().strip()
        if not text:
            return
        rows = self.db.find_by_label(text)
        if rows.empty:
            self._set_status(f"⚠️ '{text}' no encontrado en el catálogo")
            QMessageBox.warning(
                self, "No encontrado",
                f"La etiqueta '{text}' no coincide con ningún producto del catálogo.")
        else:
            nombre = rows.iloc[0].get("nombre_capturado", "")
            self._set_status(f"✅ Válido: {nombre}")
            # Mostrar el producto en el panel
            self._show_info(rows.iloc[0])
            upc = rows.iloc[0].get("upc_version", "")
            self._img_inner.set_images(self.db.get_images(upc, max_images=9))

    def _validate_before_save(self) -> bool:
        """
        Valida que las etiquetas pertenezcan estrictamente a la lista predefinida oficial.
        """
        current_format = str(getattr(self.mw, "label_file_format", "")).upper()

        if "YOLO" in current_format:
            # Usa la lista inicial respaldada o intenta leer el archivo de clases predefinidas
            official = set(getattr(self, "_official_yolo_classes", []))

            # Si el respaldo estaba vacío, intenta cargar desde predefined_classes.txt
            if not official and hasattr(self.mw, "label_hist"):
                official = set(self.mw.label_hist)

            unknown_classes = []
            for shape in self.mw.canvas.shapes:
                label = (shape.label or "").strip()
                # Detecta cualquier clase que no estuviera en la lista original
                if label and label not in official:
                    unknown_classes.append(label)

            if unknown_classes:
                unique_bads = list(set(unknown_classes))
                msg_list = "\n".join(f"  • {l}" for l in unique_bads[:5])
                if len(unique_bads) > 5:
                    msg_list += f"\n  ... y {len(unique_bads) - 5} más."

                reply = QMessageBox.warning(
                    self.mw,
                    "⚠️ Alerta YOLO: Clase no permitida",
                    f"Las siguientes etiquetas NO pertenecen a las clases oficiales:\n\n{msg_list}\n\n"
                    f"⚠️ Guardar agregará estas líneas a 'classes.txt' y desincronizará tu dataset.\n\n"
                    f"¿Deseas guardar de todas formas?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                return reply == QMessageBox.Yes

        return True

    # ── Utilidades ────────────────────────────────────────────────────────────
    def _set_shape_label(self, shape, new_label: str) -> None:
        """Cambia la etiqueta de una shape y sincroniza con LabelImg."""
        old_label = shape.label
        shape.label = new_label

        # Sincronizar colores
        try:
            shape.line_color = generate_color_by_text(new_label)
        except Exception:
            pass

        # Actualizar panel de etiquetas de LabelImg
        items_to_shapes = (
            getattr(self.mw, "items_to_shapes", None) or
            getattr(self.mw, "itemsToShapes", {})
        )
        label_list = (
            getattr(self.mw, "label_list", None) or
            getattr(self.mw, "labelList", None)
        )
        if label_list:
            label_list.blockSignals(True)
        for item, s in items_to_shapes.items():
            if s is shape:
                item.setText(new_label)
                try:
                    item.setBackground(generate_color_by_text(new_label))
                except Exception:
                    pass
        if label_list:
            label_list.blockSignals(False)

        # Agregar al historial de clases
        label_hist = getattr(self.mw, "label_hist", None)
        if isinstance(label_hist, list) and new_label not in label_hist:
            label_hist.append(new_label)

        if hasattr(self.mw, "set_dirty"):
            self.mw.set_dirty()
        if hasattr(self.mw, "update_combo_box"):
            self.mw.update_combo_box()
        self.mw.canvas.update()

    def _set_status(self, msg: str) -> None:
        self._bottom_status.setText(msg)

    # ── Opciones ──────────────────────────────────────────────────────────────
    def _open_options(self) -> None:
        dlg = _OptionsDialog(self._options, self)
        if dlg.exec_():
            new_opts = dlg.get_values()
            self._options.update(new_opts)
            self._apply_options()
            self._save_options()

    def _apply_options(self) -> None:
        # Tooltip hover
        self.tooltip_mgr.set_hover_enabled(
            self._options.get("hover_tooltip", True))
        # Tooltip selección
        self.tooltip_mgr.set_selection_enabled(
            self._options.get("selection_tooltip", True))
        # Historial
        if not self._options.get("search_history", True):
            self._history_lbl.hide()
            self._history_list.hide()
        else:
            self._update_history_widget()
        # Smart label button
        if not self._options.get("smart_label", True):
            self._btn_smart.hide()

    def _save_options(self) -> None:
        """Persiste las opciones en custom/config.json bajo la clave 'visualizador_opts'."""
        import json
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "config.json"
        )
        config_path = os.path.normpath(config_path)
        try:
            cfg = {}
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["visualizador_opts"] = self._options
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Visualizador] No se pudo guardar opciones: {e}")

    def _load_options(self) -> None:
        #Carga opciones guardadas previamente.
        import json
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "config.json"
        )
        config_path = os.path.normpath(config_path)
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                saved = cfg.get("visualizador_opts", {})
                self._options.update(saved)
        except Exception as e:
            print(f"[Visualizador] No se pudo cargar opciones: {e}")
    
    def _open_add_product_dialog(self) -> None:
        """Abre ventana para capturar nuevo producto y llamar a la BD."""
        from PyQt5.QtWidgets import QInputDialog, QFileDialog, QMessageBox

        upc, ok = QInputDialog.getText(self, "Nuevo Producto", "UPC (Código de barras):")
        if not ok or not upc.strip():
            return

        nombre, ok = QInputDialog.getText(self, "Nuevo Producto", "Nombre completo del producto:")
        if not ok or not nombre.strip():
            return

        cluster, ok = QInputDialog.getInt(self, "Nuevo Producto", "Cluster ID:", value=0, min=0)
        if not ok:
            return

        # Seleccionar hasta 3 imágenes desde el explorador
        files, _ = QFileDialog.getOpenFileNames(
            self, "Selecciona hasta 3 imágenes del producto", "", "Imágenes (*.png *.jpg *.jpeg)"
        )

        try:
            upc_ver = self.db.registrar_nuevo_producto(
                upc_capturado=upc.strip(),
                nombre=nombre.strip(),
                cluster_id=cluster,
                imagenes_paths=files
            )
            QMessageBox.information(self, "Éxito", f"Producto {upc_ver} registrado correctamente.")
            # Refrescar búsqueda actual si aplica
            self._do_search()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el producto: {e}")

    def _open_update_catalog_dialog(self) -> None:
        """Abre selectores de archivo/carpeta para actualizar el catálogo de forma masiva."""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox

        # 1. Seleccionar el nuevo archivo CSV
        csv_path, _ = QFileDialog.getOpenFileName(
            self,
            "1/2 - Selecciona el nuevo archivo CSV",
            "",
            "Archivos CSV (*.csv)"
        )
        if not csv_path:
            return  # Cancelado por el usuario

        # 2. Seleccionar la carpeta que contiene las subcarpetas de imágenes (ej. dataset_catalogo_1575_skus)
        img_dir = QFileDialog.getExistingDirectory(
            self,
            "2/2 - Selecciona la carpeta contenedora de las nuevas imágenes"
        )
        if not img_dir:
            return  # Cancelado por el usuario

        # 3. Procesar actualización
        try:
            total_skus, total_folders = self.db.actualizar_catalogo_masivo(csv_path, img_dir)
            
            QMessageBox.information(
                self,
                "Actualización Completada",
                f"✅ Catálogo actualizado con éxito.\n\n"
                f"• Total de productos en CSV: {total_skus}\n"
                f"• Carpetas de imágenes integradas: {total_folders}"
            )
            self._clear_search()
        except Exception as e:
            QMessageBox.critical(self, "Error al actualizar", f"No se pudo actualizar el catálogo:\n{e}")
