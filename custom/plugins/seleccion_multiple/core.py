from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QAction, QInputDialog
from libs.utils import generate_color_by_text


__version__ = "2.0.0"
__description__ = "Selección múltiple por arrastre con clic derecho y edición masiva de clase."


def setup(main_window):
    plugin = MultiSelectAreaPlugin(main_window)
    main_window._multi_select_area = plugin
    return plugin


class MultiSelectAreaPlugin:
    DRAG_THRESHOLD = 6

    def __init__(self, main_window):
        self.mw = main_window
        self.canvas = main_window.canvas

        self.right_press_pos = None
        self.is_dragging = False
        self.selection_rect = QRect()

        self.line_color = QColor(0, 120, 215, 255)
        self.fill_color = QColor(0, 120, 215, 45)

        self._inject_canvas_events()
        self._setup_ui()

    def _setup_ui(self):
        action = QAction("Limpiar selección por área", self.mw)
        action.triggered.connect(self._clear_selection)

        if hasattr(self.mw, "register_plugin_action"):
            self.mw.register_plugin_action("Selección", action)
        elif hasattr(self.mw, "menu_plugins"):
            self.mw.menu_plugins.addAction(action)

    def _inject_canvas_events(self):
        self.old_mouse_press = self.canvas.mousePressEvent
        self.old_mouse_move = self.canvas.mouseMoveEvent
        self.old_mouse_release = self.canvas.mouseReleaseEvent
        self.old_paint_event = self.canvas.paintEvent

        self.canvas.mousePressEvent = self._canvas_mouse_press_event
        self.canvas.mouseMoveEvent = self._canvas_mouse_move_event
        self.canvas.mouseReleaseEvent = self._canvas_mouse_release_event
        self.canvas.paintEvent = self._canvas_paint_event

    def _canvas_mouse_press_event(self, ev):
        if ev.button() == Qt.RightButton:
            self.right_press_pos = ev.pos()
            self.is_dragging = False
            self.selection_rect = QRect(self.right_press_pos, self.right_press_pos).normalized()
            return

        self.old_mouse_press(ev)

    def _canvas_mouse_move_event(self, ev):
        if self.right_press_pos is not None:
            distance = (ev.pos() - self.right_press_pos).manhattanLength()
            if distance >= self.DRAG_THRESHOLD:
                self.is_dragging = True
                self.selection_rect = QRect(self.right_press_pos, ev.pos()).normalized()
                self.canvas.update()
                return

        self.old_mouse_move(ev)

    def _canvas_mouse_release_event(self, ev):
        if ev.button() != Qt.RightButton:
            self.old_mouse_release(ev)
            return

        # Sin arrastre: conservar menú contextual nativo (editar, crear, eliminar, etc).
        if self.right_press_pos is None or not self.is_dragging:
            self._reset_drag_state()
            self.old_mouse_release(ev)
            return

        self.selection_rect = QRect(self.right_press_pos, ev.pos()).normalized()
        self._process_selection()
        self._reset_drag_state()
        self.canvas.update()

    def _canvas_paint_event(self, ev):
        self.old_paint_event(ev)
        if not self.is_dragging:
            return

        painter = QPainter(self.canvas)
        painter.setPen(QPen(self.line_color, 1, Qt.DashLine))
        painter.setBrush(self.fill_color)
        painter.drawRect(self.selection_rect.normalized())
        painter.end()

    def _reset_drag_state(self):
        self.right_press_pos = None
        self.is_dragging = False
        self.selection_rect = QRect()

    def _process_selection(self):
        if self.selection_rect.isNull():
            return

        image_top_left = self.canvas.transform_pos(self.selection_rect.topLeft())
        image_bottom_right = self.canvas.transform_pos(self.selection_rect.bottomRight())
        image_selection_rect = QRect(
            int(image_top_left.x()),
            int(image_top_left.y()),
            int(image_bottom_right.x() - image_top_left.x()),
            int(image_bottom_right.y() - image_top_left.y()),
        ).normalized()

        selected_shapes = []
        for shape in self.canvas.shapes:
            shape.selected = False
            shape_rect = shape.bounding_rect().toRect().normalized()
            if image_selection_rect.intersects(shape_rect):
                shape.selected = True
                selected_shapes.append(shape)

        self.canvas.selected_shapes = selected_shapes
        self.canvas.selected_shape = selected_shapes[0] if selected_shapes else None
        self.canvas.selectionChanged.emit(bool(selected_shapes))
        self.canvas.update()

        if selected_shapes:
            self._bulk_edit_class(selected_shapes)

    def _bulk_edit_class(self, shapes):
        default_text = shapes[0].label if shapes else ""
        selected_class = None

        label_dialog = getattr(self.mw, "label_dialog", None)
        if label_dialog and hasattr(label_dialog, "pop_up"):
            selected_class = label_dialog.pop_up(default_text)

        if selected_class is None:
            labels = list(getattr(self.mw, "label_hist", []))
            if not labels:
                labels = [shape.label for shape in self.canvas.shapes if shape.label]
            labels = list(dict.fromkeys(labels))
            if not labels:
                return

            selected_class, ok = QInputDialog.getItem(
                self.mw,
                "Cambio masivo de clase",
                f"Cambiar {len(shapes)} cajas a:",
                labels,
                0,
                False,
            )
            if not ok:
                return

        if not selected_class:
            return

        items_to_shapes = getattr(self.mw, "items_to_shapes", None) or getattr(self.mw, "itemsToShapes", {})
        touched_items = []
        for shape in shapes:
            shape.label = selected_class

        for item, shape in items_to_shapes.items():
            if shape in shapes:
                item.setText(shape.label)
                item.setBackground(generate_color_by_text(shape.label))
                touched_items.append(item)

        label_list = getattr(self.mw, "label_list", None) or getattr(self.mw, "labelList", None)
        if label_list:
            label_list.blockSignals(True)
            label_list.clearSelection()
            for item in touched_items:
                item.setSelected(True)
            label_list.blockSignals(False)

        if hasattr(self.mw, "set_dirty"):
            self.mw.set_dirty()
        if hasattr(self.mw, "update_combo_box"):
            self.mw.update_combo_box()
        if hasattr(self.mw, "shape_selection_changed"):
            self.mw.shape_selection_changed(True)

        self.canvas.update()

    def _clear_selection(self):
        for shape in self.canvas.shapes:
            shape.selected = False
        self.canvas.selected_shapes = []
        self.canvas.selected_shape = None
        self.canvas.selectionChanged.emit(False)
        self.canvas.update()
