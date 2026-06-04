import os
from PyQt5.QtCore import Qt

__version__ = "1.1.0"
__description__ = "Correcciones de UX como permitir edición de etiquetas en cualquier modo y correcciones de selección."

class MejorasUXPlugin:
    def __init__(self, main_window):
        self.mw = main_window
        self.canvas = main_window.canvas
        self._patch_methods()

    def _update_action_states(self):
        items_seleccionados = len(self.mw.label_list.selectedItems()) > 0
        if hasattr(self.mw, 'actions'):
            for act_name in ['delete', 'copy', 'edit', 'shapeLineColor', 'shapeFillColor']:
                if hasattr(self.mw.actions, act_name):
                    getattr(self.mw.actions, act_name).setEnabled(items_seleccionados)

    def _patch_methods(self):
        self.original_edit_label = self.mw.edit_label

        def wrapped_edit_label(*args, **kwargs):
            # Ignorar la restricción de canvas.editing()
            # que causaba que el botón gris estuviera disponible pero no hiciera nada
            item = self.mw.current_item()
            if not item:
                return

            text = self.mw.label_dialog.pop_up(item.text())
            if text is not None:
                if hasattr(self.mw, "_history_manager"):
                    self.mw._history_manager._priority_desc = "Editar etiqueta"
                    self.mw._history_manager._last_action_desc = "Editar etiqueta"
                from libs.utils import generate_color_by_text
                for selected_item in self.mw.label_list.selectedItems():
                    selected_item.setText(text)
                    selected_item.setBackground(generate_color_by_text(text))
                    
                    shape = self.mw.items_to_shapes.get(selected_item)
                    if shape:
                        shape.label = text
                        shape.line_color = generate_color_by_text(text)
                        shape.fill_color = generate_color_by_text(text)
                
                self.mw.set_dirty()
                self.mw.update_combo_box()

        self.mw.edit_label = wrapped_edit_label
        
        # Re-conectar la accion del menú para que apunte a nuestro metodo
        if hasattr(self.mw, 'actions') and hasattr(self.mw.actions, 'edit'):
            try:
                self.mw.actions.edit.triggered.disconnect()
                self.mw.actions.edit.triggered.connect(wrapped_edit_label)
            except Exception:
                pass

        # Asegurar actualización de botones al cambiar selección
        self.original_label_selection_changed = self.mw.label_selection_changed
        self.original_shape_selection_changed = self.mw.shape_selection_changed

        def wrapped_label_selection_changed(*args, **kwargs):
            self.original_label_selection_changed(*args, **kwargs)
            self._update_action_states()

        def wrapped_shape_selection_changed(*args, **kwargs):
            self.original_shape_selection_changed(*args, **kwargs)
            self._update_action_states()

        self.mw.label_selection_changed = wrapped_label_selection_changed
        self.mw.shape_selection_changed = wrapped_shape_selection_changed

        # Seleccionar automáticamente la figura al hacer clic derecho para habilitar acciones
        self.original_mouse_release_event = self.canvas.mouseReleaseEvent

        def wrapped_mouse_release_event(ev):
            if ev.button() == Qt.RightButton:
                if self.canvas.h_shape and self.canvas.h_shape not in self.canvas.selected_shapes:
                    self.canvas.select_shape(self.canvas.h_shape)
                    self._update_action_states()
            self.original_mouse_release_event(ev)

        self.canvas.mouseReleaseEvent = wrapped_mouse_release_event


def setup(main_window):
    plugin = MejorasUXPlugin(main_window)
    main_window._mejoras_ux = plugin
    return plugin
