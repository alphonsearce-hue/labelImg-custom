import json

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QAction, QShortcut


__version__ = "1.0.0"
__description__ = "Historial global para deshacer/rehacer cambios de anotaciones."


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

        self.capture_timer = QTimer()
        self.capture_timer.setSingleShot(True)
        self.capture_timer.timeout.connect(self._capture_snapshot)

        self._setup_ui()
        self._patch_methods()

    def _setup_ui(self):
        self.action_undo = QAction("↩ Deshacer", self.mw)
        self.action_redo = QAction("↪ Rehacer", self.mw)
        self.action_undo.triggered.connect(self.undo)
        self.action_redo.triggered.connect(self.redo)
        self.action_undo.setEnabled(False)
        self.action_redo.setEnabled(False)

        QShortcut(QKeySequence("Ctrl+Z"), self.mw, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self.mw, activated=self.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self.mw, activated=self.redo)

        if hasattr(self.mw, "register_plugin_action"):
            self.mw.register_plugin_action("Edición", self.action_undo)
            self.mw.register_plugin_action("Edición", self.action_redo)

        if hasattr(self.mw, "register_plugin_tool"):
            self.mw.register_plugin_tool("label_mods", "↩ Deshacer", self.undo)
            self.mw.register_plugin_tool("label_mods", "↪ Rehacer", self.redo)

    def _patch_methods(self):
        original_set_dirty = self.mw.set_dirty
        original_load_file = self.mw.load_file

        def wrapped_set_dirty(*args, **kwargs):
            result = original_set_dirty(*args, **kwargs)
            if not self._restoring:
                self.capture_timer.start(80)
            return result

        def wrapped_load_file(*args, **kwargs):
            result = original_load_file(*args, **kwargs)
            if result:
                self._reset_history()
                self._capture_snapshot()
            return result

        self.mw.set_dirty = wrapped_set_dirty
        self.mw.load_file = wrapped_load_file

    def _reset_history(self):
        self.undo_stack = []
        self.redo_stack = []
        self._last_snapshot_key = None
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
        }

    def _capture_snapshot(self):
        if not self.mw.file_path or self._restoring:
            return

        state = self._snapshot()
        key = json.dumps(state, sort_keys=True)
        if key == self._last_snapshot_key:
            return

        self.undo_stack.append(state)
        if len(self.undo_stack) > self.MAX_HISTORY:
            self.undo_stack.pop(0)
        self.redo_stack = []
        self._last_snapshot_key = key
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
            self.mw.set_dirty()
        finally:
            self._restoring = False

    def undo(self):
        if len(self.undo_stack) <= 1:
            return
        current = self.undo_stack.pop()
        self.redo_stack.append(current)
        previous = self.undo_stack[-1]
        self._last_snapshot_key = json.dumps(previous, sort_keys=True)
        self._restore_state(previous)
        self._refresh_actions()

    def redo(self):
        if not self.redo_stack:
            return
        next_state = self.redo_stack.pop()
        self.undo_stack.append(next_state)
        self._last_snapshot_key = json.dumps(next_state, sort_keys=True)
        self._restore_state(next_state)
        self._refresh_actions()

    def _refresh_actions(self):
        self.action_undo.setEnabled(len(self.undo_stack) > 1)
        self.action_redo.setEnabled(bool(self.redo_stack))

