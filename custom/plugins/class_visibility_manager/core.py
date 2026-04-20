# =============================================================================
# custom/plugins/class_visibility_manager/core.py
# =============================================================================
# PROPÓSITO: Plugin "Gestor de Visibilidad por Clase" para LabelImg.
# Permite ocultar/mostrar grupos de RectBoxes por etiqueta.
# Sincroniza bidireccionalmente con los checkboxes de la lista lateral.
# =============================================================================

__version__ = "1.2.0"
__description__ = "Gestiona la visibilidad de RectBoxes por clase. Sincroniza con los checkboxes laterales."

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor

from custom.plugins.class_visibility_manager.ui.panel import ClassVisibilityDialog

_dialog = None
_main_window = None
_estado_clases = {}  # Memoria de visibilidad por clase durante la sesión

def setup(main_window):
    """
    Configura el plugin insertando un botón de acceso en el dock derecho.
    """
    global _main_window, _dialog
    _main_window = main_window

    dock_widget = main_window.dock.widget()
    dock_layout = dock_widget.layout()

    # Creamos un botón elegante para abrir el gestor
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
        QPushButton:hover {
            background-color: #3d3d5c;
            color: #ffffff;
        }
    """)
    btn_gestor.clicked.connect(_abrir_gestor)

    # Insertamos el botón al principio del dock
    dock_layout.insertWidget(0, btn_gestor)

    # Hooks de sincronización
    _parchear_metodo(main_window, 'load_file', _hook_post_load)
    _parchear_metodo(main_window, 'new_shape', _hook_post_new_shape)
    
    # Sincronización inicial
    QTimer.singleShot(1000, lambda: _actualizar_estado_desde_canvas(main_window))

def _abrir_gestor():
    global _dialog, _main_window, _estado_clases
    if _dialog is None:
        _dialog = ClassVisibilityDialog(_main_window)
        # Importante: conectar señales
        _dialog.visibilidad_cambiada.connect(lambda c, v: _aplicar_visibilidad_clase(_main_window, c, v))
        _dialog.mostrar_todo.connect(lambda: _aplicar_visibilidad_todas(_main_window, True))
        _dialog.ocultar_todo.connect(lambda: _aplicar_visibilidad_todas(_main_window, False))

    # Actualizar la lista de clases antes de mostrar
    clases = list(dict.fromkeys(s.label for s in _main_window.canvas.shapes if s.label))
    _dialog.actualizar_clases(clases, _estado_clases)
    _dialog.show()

def _aplicar_visibilidad_clase(main_window, clase, visible):
    """Aplica visibilidad a todas las shapes de una clase específica."""
    global _estado_clases
    _estado_clases[clase] = visible
    canvas = main_window.canvas
    
    # Bloquear señales de la lista para evitar bucles si LabelImg reacciona al checkstate
    main_window.label_list.blockSignals(True)
    
    for shape in canvas.shapes:
        if shape.label == clase:
            canvas.set_shape_visible(shape, visible)
    
    canvas.update()
    _sincronizar_list_widget(main_window)
    
    main_window.label_list.blockSignals(False)

def _aplicar_visibilidad_todas(main_window, visible):
    """Aplica visibilidad a absolutamente todas las clases."""
    global _estado_clases
    canvas = main_window.canvas
    
    main_window.label_list.blockSignals(True)
    
    for shape in canvas.shapes:
        canvas.set_shape_visible(shape, visible)
        if shape.label:
            _estado_clases[shape.label] = visible
            
    canvas.update()
    _sincronizar_list_widget(main_window)
    
    main_window.label_list.blockSignals(False)

def _actualizar_estado_desde_canvas(main_window):
    """Sincroniza el diccionario interno con lo que hay en el canvas."""
    global _estado_clases
    for shape in main_window.canvas.shapes:
        if shape.label and shape.label not in _estado_clases:
            _estado_clases[shape.label] = main_window.canvas.isVisible(shape)

def _sincronizar_list_widget(main_window):
    """
    Sincroniza los checkboxes de la lista lateral (label_list).
    Visible -> CheckState = 2 (Checked)
    Invisible -> CheckState = 0 (Unchecked)
    """
    label_list = main_window.label_list
    
    # Colores para mejor visibilidad del texto atenuado
    COLOR_VISIBLE = QColor("#000000") # Negro para texto activo
    COLOR_OCULTO = QColor("#999999")  # Gris claro para texto oculto

    for i in range(label_list.count()):
        item = label_list.item(i)
        if item is None: continue
        
        shape = main_window.items_to_shapes.get(item)
        if shape:
            visible = main_window.canvas.isVisible(shape)
            
            # Sincronizar Checkbox físico de la lista
            # 2 = Qt.Checked, 0 = Qt.Unchecked
            item.setCheckState(2 if visible else 0)
            
            # Sincronizar Color del texto
            item.setForeground(COLOR_VISIBLE if visible else COLOR_OCULTO)

def _parchear_metodo(main_window, nombre_metodo, hook_post):
    metodo_original = getattr(main_window, nombre_metodo, None)
    if metodo_original is None: return

    def wrapper(*args, **kwargs):
        resultado = metodo_original(*args, **kwargs)
        # Usamos un timer para asegurar que los cambios se procesen después del original
        QTimer.singleShot(100, lambda: hook_post(main_window))
        return resultado
    
    import types
    setattr(main_window, nombre_metodo, wrapper)

def _hook_post_load(main_window):
    """Se ejecuta tras cargar una imagen."""
    _actualizar_estado_desde_canvas(main_window)
    # Re-aplicar visibilidad persistente
    global _estado_clases
    for shape in main_window.canvas.shapes:
        if shape.label in _estado_clases:
            main_window.canvas.set_shape_visible(shape, _estado_clases[shape.label])
    
    main_window.canvas.update()
    _sincronizar_list_widget(main_window)

def _hook_post_new_shape(main_window):
    """Se ejecuta tras crear una nueva etiqueta."""
    _actualizar_estado_desde_canvas(main_window)
    _sincronizar_list_widget(main_window)
