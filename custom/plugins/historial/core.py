import json
import os
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QAction, QShortcut, QDockWidget, QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QLabel


__version__ = "2.0.0"
__description__ = "Historial visual de movimientos con soporte para deshacer/rehacer y navegación."


def setup(main_window):
    plugin = HistoryManagerPlugin(main_window)
    main_window._history_manager = plugin
    return plugin


class HistoryManagerPlugin:
    MAX_HISTORY = 120

    def __init__(self, main_window):
        self.mw = main_window
        self.canvas = main_window.canvas

        self.undo_stack = []
        self.redo_stack = []
        self._restoring = False
        self._last_snapshot_key = None
        self._last_action_desc = "Inicio de sesión"
        self._shape_moved_connected = False

        self.capture_timer = QTimer()
        self.capture_timer.setSingleShot(True)
        self.capture_timer.timeout.connect(self._capture_snapshot)

        self._setup_ui()
        self._patch_methods()

    def _setup_ui(self):
        # Acciones de menú
        self.action_undo = QAction("↩ Deshacer", self.mw)
        self.action_redo = QAction("↪ Rehacer", self.mw)
        self.action_undo.triggered.connect(self.undo)
        self.action_redo.triggered.connect(self.redo)
        self.action_undo.setEnabled(False)
        self.action_redo.setEnabled(False)

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+Z"), self.mw, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self.mw, activated=self.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self.mw, activated=self.redo)

        # Registro en el MainWindow (si existe el sistema de registro)
        if hasattr(self.mw, "register_plugin_action"):
            self.mw.register_plugin_action("Edición", self.action_undo)
            self.mw.register_plugin_action("Edición", self.action_redo)

        # Panel de Historial (DockWidget)
        self.dock = QDockWidget("Historial de Movimientos", self.mw)
        self.dock.setObjectName("HistoryDock")
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self._on_history_item_clicked)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Pasos realizados:"))
        layout.addWidget(self.history_list)
        
        container = QWidget()
        container.setLayout(layout)
        self.dock.setWidget(container)
        
        # Añadir al área de docks de la derecha
        self.mw.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        
        # Botón en el menú de Plugins para mostrar/ocultar el historial
        toggle_history = QAction("Ver Historial de Movimientos", self.mw)
        toggle_history.triggered.connect(lambda: self.dock.setVisible(not self.dock.isVisible()))
        if hasattr(self.mw, "register_plugin_action"):
            self.mw.register_plugin_action("Plugins", toggle_history)

    def _patch_methods(self):
        self.original_set_dirty = self.mw.set_dirty
        self.original_load_file = self.mw.load_file
        self.original_delete_selected = self.mw.delete_selected_shape
        self.original_new_shape = self.mw.new_shape

        def wrapped_set_dirty(*args, **kwargs):
            result = self.original_set_dirty(*args, **kwargs)
            if not self._restoring:
                # Si no hay una descripción pendiente, es un movimiento genérico
                if not self.capture_timer.isActive():
                    self._last_action_desc = "Cambio detectado"
                self.capture_timer.start(120)
            return result

        def wrapped_load_file(*args, **kwargs):
            result = self.original_load_file(*args, **kwargs)
            if result:
                self._reset_history()
                self._last_action_desc = "Carga de imagen"
                # Diferir el snapshot pesado al siguiente tick: la UI puede pintar antes.
                QTimer.singleShot(0, self._capture_snapshot)
            return result

        def wrapped_delete_selected(*args, **kwargs):
            self._last_action_desc = "Eliminar cuadro"
            self.original_delete_selected(*args, **kwargs)
            self.mw.set_dirty() # Asegurar que se dispare el snapshot

        def wrapped_new_shape(*args, **kwargs):
            self._last_action_desc = "Crear cuadro"
            self.original_new_shape(*args, **kwargs)
            # set_dirty ya es llamado dentro de new_shape

        # Inyectar parches
        self.mw.set_dirty = wrapped_set_dirty
        self.mw.load_file = wrapped_load_file
        self.mw.delete_selected_shape = wrapped_delete_selected
        self.mw.new_shape = wrapped_new_shape

        # Respaldo explícito: si hay movimiento/redimensión de caja,
        # marcamos acción específica y programamos captura.
        if not self._shape_moved_connected and hasattr(self.canvas, "shapeMoved"):
            self.canvas.shapeMoved.connect(self._on_shape_moved)
            self._shape_moved_connected = True

    def _on_shape_moved(self):
        if self._restoring:
            return
        self._last_action_desc = "Mover/redimensionar cuadro"
        self.capture_timer.start(120)

    def _reset_history(self):
        self.undo_stack = []
        self.redo_stack = []
        self._last_snapshot_key = None
        self.history_list.clear()
        self._refresh_actions()

    def _snapshot(self):
        shapes = []
        for shape in self.canvas.shapes:
            shapes.append(
                {
                    "label": shape.label or "",
                    "points": [[float(p.x()), float(p.y())] for p in shape.points],
                    "line_color": list(shape.line_color.getRgb()),
                    "fill_color": list(shape.fill_color.getRgb()),
                    "difficult": bool(getattr(shape, "difficult", False)),
                    "visible": bool(self.canvas.isVisible(shape)),
                }
            )

        return {
            "file_path": self.mw.file_path,
            "shapes": shapes,
            "desc": self._last_action_desc
        }

    @staticmethod
    def _bbox_from_points(points):
        if not points:
            return 0.0, 0.0, 0.0, 0.0
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return min_x, min_y, max_x - min_x, max_y - min_y

    def _infer_action_desc(self, prev_shapes, curr_shapes):
        # Sin cambios estructurales, solo geometría: detectar movimiento / tamaño.
        if len(prev_shapes) != len(curr_shapes):
            return self._last_action_desc

        moved = False
        resized = False

        for prev, curr in zip(prev_shapes, curr_shapes):
            if (prev.get("label", "") != curr.get("label", "") or
                    bool(prev.get("visible", True)) != bool(curr.get("visible", True))):
                return self._last_action_desc

            px, py, pw, ph = self._bbox_from_points(prev.get("points", []))
            cx, cy, cw, ch = self._bbox_from_points(curr.get("points", []))

            prev_center = (px + pw / 2.0, py + ph / 2.0)
            curr_center = (cx + cw / 2.0, cy + ch / 2.0)

            if abs(prev_center[0] - curr_center[0]) > 0.01 or abs(prev_center[1] - curr_center[1]) > 0.01:
                moved = True
            if abs(pw - cw) > 0.01 or abs(ph - ch) > 0.01:
                resized = True

        if moved and resized:
            return "Mover y redimensionar cuadro"
        if resized:
            return "Redimensionar cuadro"
        if moved:
            return "Mover cuadro"
        return self._last_action_desc

    def _capture_snapshot(self):
        if not self.mw.file_path or self._restoring:
            return

        state = self._snapshot()
        if self.undo_stack and self._last_action_desc in ("Cambio detectado", "Mover/redimensionar cuadro"):
            prev_shapes = self.undo_stack[-1].get("shapes", [])
            state["desc"] = self._infer_action_desc(prev_shapes, state["shapes"])

        # El key no incluye la descripción para detectar si realmente cambiaron las formas
        data_only = {"f": state["file_path"], "s": state["shapes"]}
        key = json.dumps(data_only, sort_keys=True, separators=(",", ":"))
        
        if key == self._last_snapshot_key:
            return

        self.undo_stack.append(state)
        if len(self.undo_stack) > self.MAX_HISTORY:
            self.undo_stack.pop(0)
            
        self.redo_stack = []
        self._last_snapshot_key = key
        self._refresh_history_ui()
        self._refresh_actions()

    def _restore_state(self, state):
        if not state or state.get("file_path") != self.mw.file_path:
            return

        self._restoring = True
        try:
            self.mw.items_to_shapes.clear()
            self.mw.shapes_to_items.clear()
            self.mw.label_list.clear()
            self.canvas.shapes = []
            self.canvas.visible = {}
            self.canvas.clear_selection()

            tuples_for_load = []
            visibility = []
            for entry in state.get("shapes", []):
                tuples_for_load.append(
                    (
                        entry.get("label", ""),
                        entry.get("points", []),
                        entry.get("line_color"),
                        entry.get("fill_color"),
                        entry.get("difficult", False),
                    )
                )
                visibility.append(bool(entry.get("visible", True)))

            self.mw.load_labels(tuples_for_load)
            for index, shape in enumerate(self.canvas.shapes):
                visible = visibility[index] if index < len(visibility) else True
                self.canvas.set_shape_visible(shape, visible)
                item = self.mw.shapes_to_items.get(shape)
                if item:
                    item.setCheckState(Qt.Checked if visible else Qt.Unchecked)

            self.canvas.update()
            self.original_set_dirty() # Usamos el original para no disparar otro snapshot
        finally:
            self._restoring = False

    def undo(self):
        # Si hay un snapshot pendiente (timer activo), capturarlo antes de deshacer
        if self.capture_timer.isActive():
            self.capture_timer.stop()
            self._capture_snapshot()

        if len(self.undo_stack) <= 1:
            return
        
        current = self.undo_stack.pop()
        self.redo_stack.append(current)
        
        previous = self.undo_stack[-1]
        data_only = {"f": previous["file_path"], "s": previous["shapes"]}
        self._last_snapshot_key = json.dumps(data_only, sort_keys=True, separators=(",", ":"))
        
        self._restore_state(previous)
        self._refresh_history_ui()
        self._refresh_actions()

    def redo(self):
        if not self.redo_stack:
            return
            
        next_state = self.redo_stack.pop()
        self.undo_stack.append(next_state)
        
        data_only = {"f": next_state["file_path"], "s": next_state["shapes"]}
        self._last_snapshot_key = json.dumps(data_only, sort_keys=True, separators=(",", ":"))
        
        self._restore_state(next_state)
        self._refresh_history_ui()
        self._refresh_actions()

    def _on_history_item_clicked(self, item):
        target_index = self.history_list.row(item)
        current_index = len(self.undo_stack) - 1
        
        if target_index == current_index:
            return
            
        # Navegación rápida saltando pasos
        if target_index < current_index:
            # Deshacer múltiples
            for _ in range(current_index - target_index):
                state = self.undo_stack.pop()
                self.redo_stack.append(state)
        else:
            # Rehacer múltiples
            for _ in range(target_index - current_index):
                state = self.redo_stack.pop()
                self.undo_stack.append(state)
        
        target_state = self.undo_stack[-1]
        data_only = {"f": target_state["file_path"], "s": target_state["shapes"]}
        self._last_snapshot_key = json.dumps(data_only, sort_keys=True, separators=(",", ":"))
        
        self._restore_state(target_state)
        self._refresh_history_ui()
        self._refresh_actions()

    def _refresh_history_ui(self):
        self.history_list.blockSignals(True)
        self.history_list.clear()
        
        # Mostrar todo el stack (undo + redo)
        for i, state in enumerate(self.undo_stack):
            item = QListWidgetItem(f"{i+1}. {state['desc']}")
            self.history_list.addItem(item)
            if i == len(self.undo_stack) - 1:
                item.setSelected(True)
                item.setBackground(Qt.lightGray)
        
        for i, state in enumerate(reversed(self.redo_stack)):
            item = QListWidgetItem(f"(Rehacer) {state['desc']}")
            item.setForeground(Qt.gray)
            self.history_list.addItem(item)
            
        self.history_list.scrollToBottom()
        self.history_list.blockSignals(False)

    def _refresh_actions(self):
        self.action_undo.setEnabled(len(self.undo_stack) > 1)
        self.action_redo.setEnabled(bool(self.redo_stack))

