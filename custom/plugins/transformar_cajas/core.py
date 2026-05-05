from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QAction

__version__ = "1.0.0"
__description__ = "Transformación simultánea de múltiples bounding boxes (mover/redimensionar)."


def setup(main_window):
    plugin = MultiBBoxTransformerPlugin(main_window)
    main_window._multi_bbox_transformer = plugin
    return plugin


class MultiBBoxTransformerPlugin:
    def __init__(self, main_window):
        self.mw = main_window
        self.canvas = main_window.canvas
        self.enabled = True

        self._original_bounded_move_vertex = self.canvas.bounded_move_vertex
        self.canvas.bounded_move_vertex = self._bounded_move_vertex_group

        self._setup_ui()

    def _setup_ui(self):
        action = QAction("Transformación múltiple de cajas", self.mw)
        action.setCheckable(True)
        action.setChecked(True)
        action.triggered.connect(self._toggle_enabled)

        if hasattr(self.mw, "register_plugin_action"):
            self.mw.register_plugin_action("Selección", action)
        elif hasattr(self.mw, "menu_plugins"):
            self.mw.menu_plugins.addAction(action)

    def _toggle_enabled(self, enabled):
        self.enabled = bool(enabled)

    def _bounded_move_vertex_group(self, pos):
        anchor_shape = self.canvas.h_shape
        anchor_vertex = self.canvas.h_vertex
        selected_shapes = list(getattr(self.canvas, "selected_shapes", []))

        should_group_resize = (
            self.enabled
            and anchor_shape is not None
            and anchor_vertex is not None
            and len(selected_shapes) >= 2
            and anchor_shape in selected_shapes
            and len(anchor_shape.points) == 4
        )

        anchor_before = None
        if should_group_resize:
            anchor_before = QPointF(anchor_shape[anchor_vertex])

        # Ejecutar comportamiento nativo primero para la caja "ancla".
        self._original_bounded_move_vertex(pos)

        if not should_group_resize:
            return

        anchor_after = anchor_shape[anchor_vertex]
        shift_pos = anchor_after - anchor_before
        if not shift_pos:
            return

        if (
            anchor_shape is None
            or anchor_vertex is None
            or self.canvas.out_of_pixmap(anchor_after)
        ):
            return

        # Replicar el mismo delta incremental a todas las cajas seleccionadas.
        for shape in selected_shapes:
            if shape is anchor_shape:
                continue
            if len(shape.points) != 4:
                continue

            shape.move_vertex_by(anchor_vertex, shift_pos)

            left_index = (anchor_vertex + 1) % 4
            right_index = (anchor_vertex + 3) % 4
            if anchor_vertex % 2 == 0:
                right_shift = QPointF(shift_pos.x(), 0)
                left_shift = QPointF(0, shift_pos.y())
            else:
                left_shift = QPointF(shift_pos.x(), 0)
                right_shift = QPointF(0, shift_pos.y())

            shape.move_vertex_by(right_index, right_shift)
            shape.move_vertex_by(left_index, left_shift)

