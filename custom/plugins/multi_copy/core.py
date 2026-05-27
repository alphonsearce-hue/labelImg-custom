# =============================================================================
# custom/plugins/multi_copy/core.py
# =============================================================================
# PROPÓSITO:
#   1. Corrige el bug AttributeError al duplicar cuando canvas retorna None.
#   2. Añade soporte para duplicar TODAS las cajas seleccionadas (multi-copia).
#
# INSTALACIÓN:
#   Copiar esta carpeta a: custom/plugins/multi_copy/
#   Asegurarse de que exista un __init__.py vacío junto a este archivo.
# =============================================================================

from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QAction

__version__ = "1.1.0"

# Desplazamiento visual de los duplicados (px) para que sean visibles al instante
_COPY_OFFSET = QPointF(10.0, 10.0)


class MultiCopyPlugin:
    """
    Parcha copy_selected_shape de MainWindow para:
      - No crashear si canvas devuelve None.
      - Duplicar todas las shapes en canvas.selected_shapes cuando hay
        más de una seleccionada.
    """

    def __init__(self, main_window):
        self.mw = main_window
        self._patch_copy_action()
        self._register_menu_action()
        print(f"[multi_copy] v{__version__} cargado — Ctrl+D ahora soporta multi-selección.")

    # ------------------------------------------------------------------
    # Parche principal
    # ------------------------------------------------------------------

    def _patch_copy_action(self):
        """Reemplaza main_window.copy_selected_shape con nuestra versión segura."""
        original = self.mw.copy_selected_shape
        if getattr(original, "_multi_copy_patched", False):
            return  # Ya parchado (recarga en caliente), no doblar

        plugin = self

        def safe_multi_copy():
            canvas = plugin.mw.canvas
            selected = getattr(canvas, "selected_shapes", [])

            # ── Multi-copia: 2 o más shapes seleccionadas ──────────────
            if len(selected) > 1:
                plugin._copy_multiple(selected)
                return

            # ── Copia simple con guarda contra None ─────────────────────
            # canvas.copy_selected_shape() puede devolver None si
            # selected_shape es None en ese momento; lo evitamos.
            if not canvas.selected_shape:
                return

            copied_shape = canvas.copy_selected_shape()
            if copied_shape is None:          # defensa extra
                return

            plugin.mw.add_label(copied_shape)
            plugin.mw.shape_selection_changed(True)

        safe_multi_copy._multi_copy_patched = True
        self.mw.copy_selected_shape = safe_multi_copy

    def _copy_multiple(self, shapes_to_copy):
        """
        Duplica cada shape de la lista, las agrega al canvas y al panel
        de etiquetas, y deja sólo las nuevas copias seleccionadas.
        """
        canvas = self.mw.canvas

        # Guardar referencias antes de limpiar
        originals = list(shapes_to_copy)

        # Deseleccionar todo antes de agregar copias
        canvas.clear_selection()

        new_shapes = []
        for shape in originals:
            # Clonar la shape
            new_shape = shape.copy()

            # Desplazar ligeramente para que sea visible
            new_shape.move_by(_COPY_OFFSET)

            # Clip a límites del canvas
            pw = canvas.pixmap.width()
            ph = canvas.pixmap.height()
            for i, pt in enumerate(new_shape.points):
                clipped_x = min(max(0.0, pt.x()), float(pw))
                clipped_y = min(max(0.0, pt.y()), float(ph))
                new_shape.points[i] = QPointF(clipped_x, clipped_y)

            new_shape.selected = True
            canvas.shapes.append(new_shape)
            new_shapes.append(new_shape)

        # Actualizar estado de selección múltiple en el canvas
        canvas.selected_shapes = new_shapes
        canvas.selected_shape = new_shapes[-1] if new_shapes else None

        # Registrar en el panel de etiquetas de MainWindow
        for s in new_shapes:
            self.mw.add_label(s)

        canvas.update()
        self.mw.set_dirty()

        total = len(new_shapes)
        self.mw.status(
            f"✔ {total} caja{'s' if total != 1 else ''} duplicada{'s' if total != 1 else ''} "
            f"(desplazamiento +{int(_COPY_OFFSET.x())}px)",
            delay=3000,
        )

    # ------------------------------------------------------------------
    # Menú (opcional)
    # ------------------------------------------------------------------

    def _register_menu_action(self):
        """Añade 'Duplicar selección' en el menú Editar si no existe ya."""
        menu_edit = self.mw.menus.edit
        for existing in menu_edit.actions():
            if getattr(existing, "_multi_copy_action", False):
                return  # Ya registrado

        action = QAction("Duplicar selección  (Ctrl+D)", self.mw)
        action._multi_copy_action = True
        action.triggered.connect(self.mw.copy_selected_shape)
        menu_edit.addSeparator()
        menu_edit.addAction(action)


# =============================================================================
# Punto de entrada requerido por PluginLoader
# =============================================================================

def setup(main_window):
    plugin = MultiCopyPlugin(main_window)
    main_window._multi_copy_plugin = plugin
    return plugin