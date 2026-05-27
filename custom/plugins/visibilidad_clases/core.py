# =============================================================================
# custom/plugins/class_visibility_manager/core.py
# =============================================================================

__version__ = "1.3.0"
__description__ = "Visibilidad por clase (optimizado para muchas etiquetas)."

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QPushButton

from custom.plugins.visibilidad_clases.ui.panel import ClassVisibilityDialog

_dialog = None
_main_window = None
_estado_clases = {}
_sync_timer = None
_pending_load = False


def setup(main_window):
    global _main_window, _dialog, _sync_timer
    _main_window = main_window

    if hasattr(main_window, "register_plugin_tool"):
        main_window.register_plugin_tool(
            "class_tools", "👁 Gestionar Visibilidad por Clase", _abrir_gestor
        )
    else:
        dock_widget = main_window.dock.widget()
        dock_layout = dock_widget.layout()
        btn_gestor = QPushButton("👁 Gestionar Visibilidad por Clase")
        btn_gestor.setStyleSheet("""
            QPushButton {
                background-color: #2a2a3e;
                color: #cba6f7;
                border: 1px solid #3d3d5c;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                margin-bottom: 5px;
            }
            QPushButton:hover { background-color: #3d3d5c; color: #ffffff; }
        """)
        btn_gestor.clicked.connect(_abrir_gestor)
        dock_layout.insertWidget(0, btn_gestor)

    _sync_timer = QTimer()
    _sync_timer.setSingleShot(True)
    _sync_timer.timeout.connect(_sync_after_load)

    _parchear_metodo(main_window, "load_file", _on_load_file_scheduled)
    _parchear_metodo(main_window, "new_shape", _hook_post_new_shape)


def _abrir_gestor():
    global _dialog, _main_window, _estado_clases
    if _dialog is None:
        _dialog = ClassVisibilityDialog(_main_window)
        _dialog.visibilidad_cambiada.connect(
            lambda c, v: _aplicar_visibilidad_clase(_main_window, c, v)
        )
        _dialog.mostrar_todo.connect(lambda: _aplicar_visibilidad_todas(_main_window, True))
        _dialog.ocultar_todo.connect(lambda: _aplicar_visibilidad_todas(_main_window, False))

    clases = list(dict.fromkeys(s.label for s in _main_window.canvas.shapes if s.label))
    _dialog.actualizar_clases(clases, _estado_clases)
    _dialog.show()


def _aplicar_visibilidad_clase(main_window, clase, visible):
    global _estado_clases
    _estado_clases[clase] = visible
    canvas = main_window.canvas
    label_list = main_window.label_list
    label_list.blockSignals(True)
    try:
        for shape in canvas.shapes:
            if shape.label == clase:
                canvas.set_shape_visible(shape, visible)
        _sincronizar_list_widget_fast(main_window)
    finally:
        label_list.blockSignals(False)
    canvas.update()


def _aplicar_visibilidad_todas(main_window, visible):
    global _estado_clases
    canvas = main_window.canvas
    label_list = main_window.label_list
    label_list.blockSignals(True)
    try:
        for shape in canvas.shapes:
            canvas.set_shape_visible(shape, visible)
            if shape.label:
                _estado_clases[shape.label] = visible
        _sincronizar_list_widget_fast(main_window)
    finally:
        label_list.blockSignals(False)
    canvas.update()


def _on_load_file_scheduled(main_window):
    global _pending_load
    _pending_load = True
    _sync_timer.start(0)


def _sync_after_load():
    global _pending_load
    if not _pending_load or _main_window is None:
        return
    _pending_load = False
    _hook_post_load(_main_window)


def _hook_post_load(main_window):
    global _estado_clases
    canvas = main_window.canvas
    shapes = canvas.shapes

    if not shapes:
        return

    if not _estado_clases:
        for shape in shapes:
            if shape.label:
                _estado_clases[shape.label] = canvas.isVisible(shape)
        return

    label_list = main_window.label_list
    label_list.blockSignals(True)
    try:
        needs_repaint = False
        for shape in shapes:
            if not shape.label or shape.label not in _estado_clases:
                continue
            target = _estado_clases[shape.label]
            if canvas.isVisible(shape) != target:
                canvas.set_shape_visible(shape, target)
                needs_repaint = True

        items_to_shapes = getattr(main_window, "items_to_shapes", {})
        for item, shape in items_to_shapes.items():
            visible = canvas.isVisible(shape)
            state = Qt.Checked if visible else Qt.Unchecked
            if item.checkState() != state:
                item.setCheckState(state)
    finally:
        label_list.blockSignals(False)

    if needs_repaint:
        canvas.update()


def _hook_post_new_shape(main_window):
    global _estado_clases
    shape = main_window.canvas.selected_shape
    if shape and shape.label and shape.label not in _estado_clases:
        _estado_clases[shape.label] = main_window.canvas.isVisible(shape)


def _sincronizar_list_widget_fast(main_window):
    items_to_shapes = getattr(main_window, "items_to_shapes", {})
    canvas = main_window.canvas
    color_visible = QColor("#000000")
    color_oculto = QColor("#999999")

    for item, shape in items_to_shapes.items():
        visible = canvas.isVisible(shape)
        state = Qt.Checked if visible else Qt.Unchecked
        if item.checkState() != state:
            item.setCheckState(state)
        fg = color_visible if visible else color_oculto
        if item.foreground().color() != fg:
            item.setForeground(fg)


def _parchear_metodo(main_window, nombre_metodo, hook_post):
    metodo_original = getattr(main_window, nombre_metodo, None)
    if metodo_original is None:
        return
    tag = f"_visibilidad_patched_{nombre_metodo}"
    if getattr(metodo_original, tag, False):
        return

    def wrapper(*args, **kwargs):
        resultado = metodo_original(*args, **kwargs)
        if nombre_metodo == "load_file":
            if resultado:
                hook_post(main_window)
        else:
            hook_post(main_window)
        return resultado

    setattr(wrapper, tag, True)
    setattr(main_window, nombre_metodo, wrapper)
