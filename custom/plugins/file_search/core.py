# =============================================================================
# custom/plugins/file_search/core.py
# =============================================================================
# PROPÓSITO : Búsqueda rápida de imágenes por nombre (estilo VS Code).
#             Shortcut: Ctrl+F → diálogo flotante con filtrado en tiempo real.
# =============================================================================

import os
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtWidgets import (
    QAction, QDialog, QVBoxLayout, QHBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QShortcut, QApplication,
)
from PyQt5.QtGui import QKeySequence, QColor, QFont

__version__ = "1.0.0"
__description__ = "Búsqueda rápida de imágenes por nombre de archivo (Ctrl+F)."

# ─── Paleta visual ────────────────────────────────────────────────────────────

_QSS = """
/* ── Contenedor principal ── */
QDialog {
    background-color: #0d0d16;
    border: 1px solid #7ed957;
    border-radius: 14px;
}

/* ── Input de búsqueda ── */
QLineEdit#search_input {
    background-color: #1a1a2e;
    color: #e0e0f0;
    border: 2px solid #7ed957;
    border-radius: 9px;
    padding: 11px 16px;
    font-size: 15px;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    selection-background-color: #7ed957;
    selection-color: #0d0d16;
}
QLineEdit#search_input:focus {
    border-color: #a6f57d;
    background-color: #1e1e38;
}

/* ── Lista de resultados ── */
QListWidget#result_list {
    background-color: #111120;
    color: #cdd6f4;
    border: 1px solid #2a2a45;
    border-radius: 9px;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
    outline: none;
    padding: 4px;
}
QListWidget#result_list::item {
    padding: 9px 14px;
    border-radius: 6px;
    margin: 2px 3px;
    color: #cdd6f4;
}
QListWidget#result_list::item:selected {
    background-color: #7ed957;
    color: #0d0d16;
    font-weight: bold;
}
QListWidget#result_list::item:hover:!selected {
    background-color: #1c2e1c;
    color: #a6f57d;
}

/* ── Etiquetas auxiliares ── */
QLabel#lbl_title {
    color: #7ed957;
    font-size: 14px;
    font-weight: bold;
    font-family: 'Segoe UI', 'Arial', sans-serif;
}
QLabel#lbl_counter {
    color: #555570;
    font-size: 11px;
    font-family: 'Segoe UI', 'Arial', sans-serif;
}
QLabel#lbl_hint {
    color: #3a3a55;
    font-size: 11px;
    font-family: 'Segoe UI', 'Arial', sans-serif;
}
QLabel#lbl_empty {
    color: #444460;
    font-size: 13px;
    font-family: 'Segoe UI', 'Arial', sans-serif;
}
"""

# ─── Utilidades de búsqueda ───────────────────────────────────────────────────

def _score_match(filename: str, query: str) -> int:
    """
    Devuelve una puntuación de relevancia (mayor = más relevante).
    0 = sin coincidencia.
    """
    name_lower = filename.lower()
    q = query.lower()

    if not q:
        return 1                          # Sin query → todo pasa con score mínimo

    if name_lower == q:
        return 100                        # Coincidencia exacta
    if name_lower.startswith(q):
        return 80                         # Empieza con la query
    if q in name_lower:
        return 60                         # Contiene la query

    # Coincidencia difusa: todos los caracteres de q aparecen en orden
    idx = 0
    for ch in q:
        found = name_lower.find(ch, idx)
        if found == -1:
            return 0                      # Carácter no encontrado → descartado
        idx = found + 1
    return 30                             # Fuzzy match

def _highlight_text(filename: str, query: str) -> str:
    """
    Devuelve el nombre con la parte coincidente envuelta en indicadores visuales.
    Usamos texto plano; el resaltado se simula con mayúsculas de la porción matched.
    (QListWidget no soporta HTML fácilmente sin delegate, así que usamos ► como prefijo.)
    """
    if not query:
        return filename
    idx = filename.lower().find(query.lower())
    if idx == -1:
        return filename
    # Rodear la coincidencia con corchetes visuales sutiles
    return (
        filename[:idx]
        + "【" + filename[idx: idx + len(query)] + "】"
        + filename[idx + len(query):]
    )


# ─── Diálogo de búsqueda ─────────────────────────────────────────────────────

class FileSearchDialog(QDialog):

    MAX_RESULTS = 150   # Límite de ítems mostrados para mantener fluidez

    def __init__(self, parent, img_list: list):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.img_list   = img_list
        self.selected_path: str = ""
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(580)
        self.setStyleSheet(_QSS)
        self._build_ui()
        self._run_filter("")           # Mostrar todos los archivos al abrir

    # ── Construcción de la UI ─────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 14)
        root.setSpacing(10)

        # ── Cabecera: título + contador ──
        header = QHBoxLayout()
        lbl_title = QLabel("🔍  Buscar imagen")
        lbl_title.setObjectName("lbl_title")
        self.lbl_counter = QLabel("")
        self.lbl_counter.setObjectName("lbl_counter")
        self.lbl_counter.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(self.lbl_counter)
        root.addLayout(header)

        # ── Input ──
        self.search_input = QLineEdit()
        self.search_input.setObjectName("search_input")
        self.search_input.setPlaceholderText("Escribe el nombre del archivo…")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.installEventFilter(self)
        root.addWidget(self.search_input)

        # ── Lista de resultados ──
        self.result_list = QListWidget()
        self.result_list.setObjectName("result_list")
        self.result_list.setMinimumHeight(320)
        self.result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.result_list.itemActivated.connect(self._confirm_selection)
        self.result_list.itemClicked.connect(self._confirm_selection)
        root.addWidget(self.result_list)

        # ── Pista de teclado ──
        lbl_hint = QLabel("↑ ↓  Navegar   ·   Enter  Abrir   ·   Esc  Cerrar")
        lbl_hint.setObjectName("lbl_hint")
        lbl_hint.setAlignment(Qt.AlignCenter)
        root.addWidget(lbl_hint)

    # ── Filtrado ──────────────────────────────────────────────────────────────

    def _on_text_changed(self, text: str):
        self._run_filter(text.strip())

    def _run_filter(self, query: str):
        self.result_list.clear()

        scored = []
        for path in self.img_list:
            filename = os.path.basename(path)
            score = _score_match(filename, query)
            if score > 0:
                scored.append((score, filename, path))

        # Ordenar: mayor score primero, luego alfabéticamente
        scored.sort(key=lambda x: (-x[0], x[1].lower()))

        total = len(scored)
        shown = min(total, self.MAX_RESULTS)

        for _, filename, path in scored[:shown]:
            display_name = _highlight_text(filename, query) if query else filename
            # Subdirectorio como contexto visual
            parent_dir = os.path.basename(os.path.dirname(path))
            full_text   = f"  {display_name}"
            if parent_dir:
                full_text += f"   ({parent_dir})"

            item = QListWidgetItem(full_text)
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            self.result_list.addItem(item)

        # Contador
        if total == 0:
            self.lbl_counter.setText("Sin resultados")
            placeholder = QListWidgetItem("  Sin coincidencias para esta búsqueda")
            placeholder.setFlags(Qt.NoItemFlags)
            placeholder.setForeground(QColor("#444460"))
            self.result_list.addItem(placeholder)
        elif total > self.MAX_RESULTS:
            self.lbl_counter.setText(f"Mostrando {shown} de {total}")
        else:
            label = "resultado" if total == 1 else "resultados"
            self.lbl_counter.setText(f"{total} {label}")

        # Pre-seleccionar el primero
        if self.result_list.count() > 0:
            self.result_list.setCurrentRow(0)

    # ── Eventos de teclado ────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self.search_input and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Down, Qt.Key_Tab):
                self._move_row(+1)
                return True
            if key in (Qt.Key_Up,):
                self._move_row(-1)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                item = self.result_list.currentItem()
                if item:
                    self._confirm_selection(item)
                return True
            if key == Qt.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, event)

    def _move_row(self, delta: int):
        count = self.result_list.count()
        if count == 0:
            return
        new_row = max(0, min(count - 1, self.result_list.currentRow() + delta))
        self.result_list.setCurrentRow(new_row)
        self.result_list.scrollToItem(self.result_list.currentItem())

    # ── Confirmación ─────────────────────────────────────────────────────────

    def _confirm_selection(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path:
            self.selected_path = path
            self.accept()

    def get_selected_path(self) -> str:
        return self.selected_path

    # ── Posicionamiento centrado ──────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parent()
        if parent:
            geo = parent.geometry()
            x = geo.x() + (geo.width()  - self.width())  // 2
            y = geo.y() + (geo.height() - self.height()) // 3
            self.move(x, y)
        self.search_input.setFocus()


# ─── Plugin principal ─────────────────────────────────────────────────────────

class FileSearchPlugin:

    def __init__(self, main_window):
        self.mw = main_window
        self._register_toolbar_button()
        self._register_menu_action()

    # ── Ítem en menú y Toolbar ───────────────────────────────────────────────

    def _register_toolbar_button(self):
        # Acción para el shortcut global y menú
        self.search_action = QAction("🔍 Buscar", self.mw)
        self.search_action.setShortcut("Ctrl+Shift+F")
        self.search_action.setToolTip("Buscar imagen (Ctrl+Shift+F)")
        self.search_action.triggered.connect(self.open_search)
        self.mw.addAction(self.search_action)
        
        def _place_button():
            # Eliminar la acción anterior de la toolbar principal si ya se había puesto
            try:
                self.mw.tools.removeAction(self.search_action)
            except:
                pass
            
            # Buscar el plugin "saltar_imagenes" (image_jumper)
            if hasattr(self.mw, "_image_jumper_plugin"):
                jumper = self.mw._image_jumper_plugin
                layout = jumper.root.layout()
                
                # Crear un QPushButton en lugar de un QAction para ese layout
                from PyQt5.QtWidgets import QPushButton
                btn = QPushButton("🔍 Buscar")
                btn.setObjectName("btn_go")  # Usa el mismo estilo verde
                btn.setFixedHeight(22)
                btn.setToolTip("Buscar imagen (Ctrl+Shift+F)")
                btn.clicked.connect(self.open_search)
                
                # Buscar el índice del botón eliminar (btn_delete) o del separador
                idx_delete = -1
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget() == jumper.btn_delete:
                        idx_delete = i
                        break
                
                if idx_delete != -1:
                    # Insertar antes de eliminar (y antes del separador si es posible)
                    # El separador está en idx_delete - 1
                    layout.insertWidget(idx_delete - 1, btn)
                else:
                    layout.insertWidget(layout.count() - 1, btn)
            else:
                # Fallback: ponerlo en la toolbar
                try:
                    if hasattr(self.mw, 'actions') and hasattr(self.mw.actions, 'delete'):
                        self.mw.tools.insertAction(self.mw.actions.delete, self.search_action)
                    else:
                        self.mw.tools.addAction(self.search_action)
                except Exception as exc:
                    print(f"[file_search] No se pudo añadir a la toolbar: {exc}")

        # Retrasar la ejecución para asegurar que saltar_imagenes ya esté cargado
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, _place_button)

    # ── Ítem en menú View ─────────────────────────────────────────────────────

    def _register_menu_action(self):
        action = QAction("🔍  Buscar imagen…\tCtrl+Shift+F", self.mw)
        action.triggered.connect(self.open_search)
        try:
            self.mw.menus.view.addSeparator()
            self.mw.menus.view.addAction(action)
        except Exception as exc:
            print(f"[file_search] No se pudo añadir al menú View: {exc}")

    # ── Apertura del diálogo ──────────────────────────────────────────────────

    def open_search(self):
        img_list = getattr(self.mw, "m_img_list", [])

        if not img_list:
            self.mw.status("⚠ No hay imágenes cargadas. Abre un directorio primero.", 4000)
            return

        dialog = FileSearchDialog(self.mw, img_list)

        if dialog.exec_() == QDialog.Accepted:
            target = dialog.get_selected_path()
            if target and target in img_list:
                idx = img_list.index(target)
                self.mw.cur_img_idx = idx
                self.mw.load_file(target)
                self.mw.status(f"📂  {os.path.basename(target)}", 3000)


# ─── Punto de entrada ─────────────────────────────────────────────────────────

def setup(main_window):
    plugin = FileSearchPlugin(main_window)
    main_window._file_search_plugin = plugin
    print(f"[file_search] Plugin cargado — shortcut: Ctrl+Shift+F")
    return plugin