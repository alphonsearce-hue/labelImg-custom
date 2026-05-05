# =============================================================================
# custom/plugins/label_list_contrast/core.py
# =============================================================================

from PyQt5.QtCore import Qt, QTimer, QModelIndex, QRect
from PyQt5.QtGui import QColor, QFont, QBrush, QPalette
from PyQt5.QtWidgets import QListWidget, QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyle

__version__ = "2.1.3"
__description__ = "Contraste conservador (Solo blanco en fondos casi negros)."


# ----------------------------------------------------------------------
# Utilidad: luminancia WCAG 2.1
# ----------------------------------------------------------------------

def _luminance(color: QColor) -> float:
    def ch(c):
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(color.red()) + 0.7152 * ch(color.green()) + 0.0722 * ch(color.blue())


def _text_color_for(bg: QColor, palette: QPalette = None) -> QColor:
    """Blanco si el fondo es oscuro, negro si es claro. Maneja transparencia."""
    if not bg.isValid() or bg.alpha() < 30:
        if palette:
            bg = palette.color(QPalette.Base)
        else:
            return QColor("#ffffff")

    # Umbral de luminancia muy bajo: solo colores casi negros activan texto blanco
    return QColor("#ffffff") if _luminance(bg) < 0.15 else QColor("#111111")


# ----------------------------------------------------------------------
# Delegate: Fuerza el contraste sin duplicar texto ni desalinearlo
# ----------------------------------------------------------------------

class ContrastDelegate(QStyledItemDelegate):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.FONT_BOLD = QFont("Segoe UI", 9)
        self.FONT_BOLD.setBold(True)

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex):
        """Prepara las propiedades básicas (fuente, alineación)."""
        super().initStyleOption(option, index)
        option.font = self.FONT_BOLD
        option.displayAlignment = Qt.AlignVCenter | Qt.AlignLeft

    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex):
        # 1. Determinar el color de fondo para el cálculo de contraste
        # Priorizamos el color de la clase (BackgroundRole) sobre el de selección
        # porque visualmente el color de clase suele dominar o mezclarse.
        bg = index.data(Qt.BackgroundRole)
        if isinstance(bg, QBrush):
            bg_color = bg.color()
        elif isinstance(bg, QColor):
            bg_color = bg
        else:
            bg_color = QColor(0, 0, 0, 0)

        # Si el ítem no tiene color de fondo propio, usamos el de selección o el base
        if bg_color.alpha() < 40:
            if option.state & QStyle.State_Selected:
                bg_color = option.palette.color(QPalette.Highlight)
            else:
                bg_color = option.palette.color(QPalette.Base)

        text_color = _text_color_for(bg_color, option.palette)

        # 2. Dibujar BASE (Fondo y Checkbox) SIN TEXTO
        # Copiamos la opción y le quitamos la bandera de mostrar texto
        draw_option = QStyleOptionViewItem(option)
        
        # Intentamos ocultar el texto original de varias formas para máxima compatibilidad
        draw_option.text = "" 
        # HasDisplay = 1. Si lo quitamos, Qt no debería dibujar texto.
        draw_option.features &= ~QStyleOptionViewItem.HasDisplay
        # Por si acaso el estilo ignora HasDisplay, hacemos el texto transparente
        draw_option.palette.setColor(QPalette.Text, Qt.transparent)
        draw_option.palette.setColor(QPalette.HighlightedText, Qt.transparent)

        # Llamamos al paint original para que dibuje el fondo, el checkbox y el foco
        super().paint(painter, draw_option, index)

        # 3. Dibujar TEXTO manualmente con el color y posición correcta
        text = index.data(Qt.DisplayRole) or ""
        if text:
            painter.save()
            painter.setFont(self.FONT_BOLD)
            painter.setPen(text_color)
            
            # Calculamos el rect del texto. Si el estilo falla, usamos un offset seguro.
            style = option.widget.style() if option.widget else QApplication.style()
            
            # Intentamos obtener el rect oficial del texto
            text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, option, option.widget)
            
            # Si el rect oficial parece erróneo (muy a la izquierda o vacío), 
            # forzamos un offset para que no choque con el checkbox.
            check_rect = style.subElementRect(QStyle.SE_ItemViewItemCheckIndicator, option, option.widget)
            
            # El texto debe empezar al menos después del checkbox + margen
            min_x = option.rect.left() + 26
            if check_rect.isValid():
                min_x = max(min_x, check_rect.right() + 6)
            
            if text_rect.left() < min_x:
                # Corregimos el rect para que no se encime
                text_rect.setLeft(min_x)
                text_rect.setRight(option.rect.right() - 4)

            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)
            painter.restore()


# ----------------------------------------------------------------------
# Plugin principal
# ----------------------------------------------------------------------

class LabelListContrastPlugin:

    def __init__(self, main_window):
        self.main_window = main_window
        self._label_list: QListWidget = main_window.label_list

        self._delegate = ContrastDelegate(self._label_list)
        self._label_list.setItemDelegate(self._delegate)

        self._patch_hooks()

        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_all)
        self._timer.start(1000) 

        print("[LabelContrast] Plugin v2.1.1 iniciado.")

    def _patch_hooks(self):
        tag = "_label_contrast_v2_patched"
        plugin = self
        for method_name in ("add_label", "load_labels", "edit_label", "label_item_changed", "new_shape"):
            orig = getattr(self.main_window, method_name, None)
            if orig is None or getattr(orig, tag, False): continue
            def make_wrapper(o, name):
                def wrapper(*args, **kwargs):
                    result = o(*args, **kwargs)
                    QTimer.singleShot(100, plugin._refresh_all)
                    return result
                setattr(wrapper, tag, True)
                return wrapper
            setattr(self.main_window, method_name, make_wrapper(orig, method_name))

    def _refresh_all(self):
        lw = self._label_list
        for i in range(lw.count()):
            item = lw.item(i)
            if item:
                bg = item.background().color() if item.background() else QColor(0,0,0,0)
                item.setForeground(QBrush(_text_color_for(bg)))
        lw.viewport().update()


# ----------------------------------------------------------------------
# Punto de entrada
# ----------------------------------------------------------------------

def setup(main_window):
    plugin = LabelListContrastPlugin(main_window)
    main_window._label_list_contrast_plugin = plugin
    return plugin
