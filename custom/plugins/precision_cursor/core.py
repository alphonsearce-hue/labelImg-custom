# =============================================================================
# custom/plugins/precision_cursor/core.py
# =============================================================================
# PROPÓSITO: Mejorar la selección de boxes pequeños (hit-box dinámico).
# Prioriza objetos pequeños y añade tolerancia de selección.
# =============================================================================

__version__ = "1.0.0"
__description__ = "Hit-box dinámico: Selección ultra-precisa de objetos pequeños con prioridad de área."

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

class PrecisionCursor:
    def __init__(self, main_window):
        self.main_window = main_window
        self._patch_canvas()

    def _patch_canvas(self):
        canvas = self.main_window.canvas
        # Guardar original por si acaso
        self.original_select = canvas.select_shape_point
        
        # Inyectar nuevo método
        canvas.select_shape_point = self.new_select_shape_point
        print("[Precision Cursor] Hit-test optimizado inyectado correctamente.")

    def new_select_shape_point(self, point, multi_select=False):
        """Versión mejorada con hit-box dinámico y prioridad a objetos pequeños."""
        canvas = self.main_window.canvas
        
        cajas_aptas = []
        
        for shape in reversed(canvas.shapes):
            if not canvas.isVisible(shape):
                continue
            
            # 1. Calcular hit-box con padding dinámico
            rect = shape.bounding_rect()
            width = rect.width()
            height = rect.height()
            area = width * height
            
            # Tolerancia dinámica: si es muy pequeño (<20px), expandir 5px virtuales
            padding = 5 if (width < 20 or height < 20) else 2
            
            # Verificar si el punto está dentro del rect expandido
            if (rect.x() - padding <= point.x() <= rect.x() + width + padding and
                rect.y() - padding <= point.y() <= rect.y() + height + padding):
                cajas_aptas.append((shape, area))

        if not cajas_aptas:
            if not multi_select:
                canvas.clear_selection()
            return None

        # 2. Prioridad: Elegir la caja con el ÁREA MÁS PEQUEÑA
        # Esto resuelve el problema de cajas grandes 'tapando' a las pequeñas
        cajas_aptas.sort(key=lambda x: x[1])
        mejor_shape = cajas_aptas[0][0]

        # --- Lógica de Selección Estándar ---
        if multi_select:
            if mejor_shape in canvas.selected_shapes:
                mejor_shape.selected = False
                canvas.selected_shapes.remove(mejor_shape)
            else:
                mejor_shape.selected = True
                canvas.selected_shapes.append(mejor_shape)
        else:
            canvas.clear_selection()
            mejor_shape.selected = True
            canvas.selected_shapes = [mejor_shape]

        canvas.selected_shape = mejor_shape
        canvas.calculate_offsets(mejor_shape, point)
        canvas.selectionChanged.emit(True)
        canvas.update()

        return mejor_shape

def setup(main_window):
    main_window._precision_cursor = PrecisionCursor(main_window)
