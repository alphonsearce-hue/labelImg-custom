# =============================================================================
# custom/plugins/label_list_contrast/core.py
# =============================================================================
# El contraste se calcula solo en el delegate al pintar cada ítem (sin hooks
# ni refrescos masivos que ralentizan load_file / load_labels).

from PyQt5.QtCore import Qt, QModelIndex
from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtWidgets import QListWidget, QStyledItemDelegate, QStyleOptionViewItem, QStyle

__version__ = "2.3.0"
__description__ = "Contraste legible en la lista (solo delegate, sin hooks)."


def _luminance(color: QColor) -> float:
    def ch(c):
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * ch(color.red()) + 0.7152 * ch(color.green()) + 0.0722 * ch(color.blue())


def text_color_for_background(bg: QColor, palette: QPalette = None) -> QColor:
    """Utilidad exportable para otros plugins (p. ej. colores_etiquetas)."""
    if not bg.isValid() or bg.alpha() < 30:
        if palette:
            bg = palette.color(QPalette.Base)
        else:
            return QColor("#ffffff")
    return QColor("#ffffff") if _luminance(bg) < 0.15 else QColor("#111111")


class ContrastDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._font = QFont("Segoe UI", 9)
        self._font.setBold(True)

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex):
        super().initStyleOption(option, index)
        option.font = self._font
        option.displayAlignment = Qt.AlignVCenter | Qt.AlignLeft

        bg = index.data(Qt.BackgroundRole)
        if isinstance(bg, QColor):
            bg_color = bg
        elif hasattr(bg, "color"):
            bg_color = bg.color()
        else:
            bg_color = QColor(0, 0, 0, 0)

        if bg_color.alpha() < 40:
            if option.state & QStyle.State_Selected:
                bg_color = option.palette.color(QPalette.Highlight)
            else:
                bg_color = option.palette.color(QPalette.Base)

        text_color = text_color_for_background(bg_color, option.palette)
        option.palette.setColor(QPalette.Text, text_color)
        option.palette.setColor(QPalette.WindowText, text_color)
        option.palette.setColor(QPalette.ButtonText, text_color)
        if option.state & QStyle.State_Selected:
            option.palette.setColor(QPalette.HighlightedText, text_color)

    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        super().paint(painter, opt, index)


class LabelListContrastPlugin:
    def __init__(self, main_window):
        self._label_list: QListWidget = main_window.label_list
        self._label_list.setItemDelegate(ContrastDelegate(self._label_list))
        print("[LabelContrast] Plugin v2.3.0 (solo delegate, sin hooks).")


def setup(main_window):
    plugin = LabelListContrastPlugin(main_window)
    main_window._label_list_contrast_plugin = plugin
    return plugin
