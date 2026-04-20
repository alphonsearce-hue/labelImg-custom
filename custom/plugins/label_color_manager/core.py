import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)
from PyQt5.QtGui import QColor, QBrush

from libs.shape import Shape
from .utils import (
    ALL_MODES,
    COLOR_THEMES,
    THEME_LABELS,
    MODE_CLASS,
    MODE_INSTANCE,
    MODE_UNIFIED,
    color_from_hex,
    stable_index,
)

__version__ = "1.0.0"
__description__ = "Gestor visual de color por instancia, clase o modo unificado."


class LabelColorManagerPlugin:
    def __init__(self, main_window):
        self.main_window = main_window
        self.canvas = main_window.canvas
        self.config_path = os.path.join(os.path.dirname(__file__), "color_config.json")

        self.mode = MODE_CLASS
        self.theme = "neon"
        self.unified_hex = "#39FF14"
        self.custom_unified_enabled = False
        self._instance_color_map = {}

        self._original_shape_paint = None

        self._load_config()
        self._inject_paint_logic()
        self._setup_ui()
        self._patch_main_window_hooks()
        self._refresh_visuals()

    def _setup_ui(self):
        if hasattr(self.main_window, "register_plugin_tool"):
            self.main_window.register_plugin_tool(
                "label_mods",
                "🎨 Configuración de Colores",
                self._open_config_dialog
            )
            return

        dock_widget = self.main_window.dock.widget()
        dock_layout = dock_widget.layout()

        self.btn_color_mode = QPushButton("🎨 Configuración de Colores")
        self.btn_color_mode.setStyleSheet(
            """
            QPushButton {
                background-color: #1e1e2e;
                color: #89dceb;
                border: 1px solid #89dceb;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
                margin-top: 8px;
            }
            QPushButton:hover {
                background-color: #89dceb;
                color: #11111b;
            }
            """
        )
        self.btn_color_mode.clicked.connect(self._open_config_dialog)
        dock_layout.insertWidget(2, self.btn_color_mode)

        if hasattr(self.main_window, "register_plugin_action"):
            action = QAction("Colores de Etiquetas", self.main_window)
            action.triggered.connect(self._open_config_dialog)
            self.main_window.register_plugin_action("Visualización", action)

    def _open_config_dialog(self, checked=False):
        dialog = ColorManagerDialog(
            self.main_window,
            self.mode,
            self.theme,
            self.unified_hex,
            self.custom_unified_enabled,
        )
        if dialog.exec_():
            selected_mode, selected_theme, selected_unified, custom_unified_enabled = dialog.get_values()

            self.mode = selected_mode
            self.theme = selected_theme
            self.unified_hex = selected_unified
            self.custom_unified_enabled = custom_unified_enabled
            self._save_config()
            self._refresh_visuals()

    def _patch_main_window_hooks(self):
        for method_name in ("load_labels", "add_label", "new_shape", "edit_label", "label_item_changed"):
            self._wrap_main_window_method(method_name)

    def _wrap_main_window_method(self, method_name):
        original = getattr(self.main_window, method_name, None)
        if original is None or getattr(original, "_label_color_wrapped", False):
            return

        def wrapped(*args, **kwargs):
            result = original(*args, **kwargs)
            self._refresh_visuals()
            return result

        wrapped._label_color_wrapped = True
        setattr(self.main_window, method_name, wrapped)

    def _inject_paint_logic(self):
        if self._original_shape_paint is None:
            self._original_shape_paint = Shape.paint

        plugin = self
        original_paint = self._original_shape_paint

        def patched_paint(shape_instance, painter):
            original_line = shape_instance.line_color
            original_fill = shape_instance.fill_color
            line_color, fill_color = plugin._resolve_shape_colors(shape_instance)

            shape_instance.line_color = line_color
            shape_instance.fill_color = fill_color
            try:
                return original_paint(shape_instance, painter)
            finally:
                shape_instance.line_color = original_line
                shape_instance.fill_color = original_fill

        Shape.paint = patched_paint

    def _resolve_shape_colors(self, shape):
        palette = COLOR_THEMES.get(self.theme) or COLOR_THEMES["neon"]
        if not palette:
            return shape.line_color, shape.fill_color

        if self.custom_unified_enabled:
            hex_color = self.unified_hex
        elif self.mode == MODE_INSTANCE:
            key = id(shape)
            if key not in self._instance_color_map:
                next_idx = len(self._instance_color_map) % len(palette)
                self._instance_color_map[key] = palette[next_idx]
            hex_color = self._instance_color_map[key]
        elif self.mode == MODE_UNIFIED:
            hex_color = self.unified_hex if self.unified_hex in palette else palette[0]
        else:
            idx = stable_index(shape.label or "", len(palette))
            hex_color = palette[idx]

        line_color = color_from_hex(hex_color, alpha=255)
        fill_color = color_from_hex(hex_color, alpha=120)
        return line_color, fill_color

    def _refresh_visuals(self):
        self._refresh_label_list_colors()
        self.canvas.update()

    def _refresh_label_list_colors(self):
        items_to_shapes = getattr(self.main_window, "itemsToShapes", None) or getattr(self.main_window, "items_to_shapes", {})
        for item, shape in items_to_shapes.items():
            line_color, _ = self._resolve_shape_colors(shape)
            item.setBackground(QBrush(QColor(line_color)))

    def _load_config(self):
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        mode = data.get("mode", MODE_CLASS)
        theme = data.get("theme", "neon")
        unified_hex = data.get("unified_hex", "#39FF14")
        custom_unified_enabled = data.get("custom_unified_enabled", False)

        if mode in ALL_MODES:
            self.mode = mode
        if theme in COLOR_THEMES:
            self.theme = theme
        self.unified_hex = unified_hex
        self.custom_unified_enabled = bool(custom_unified_enabled)

    def _save_config(self):
        data = {
            "mode": self.mode,
            "theme": self.theme,
            "unified_hex": self.unified_hex,
            "custom_unified_enabled": self.custom_unified_enabled,
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass


def setup(main_window):
    plugin = LabelColorManagerPlugin(main_window)
    main_window._label_color_manager = plugin
    return plugin


class ColorManagerDialog(QDialog):
    STYLESHEET = """
    QDialog { background-color: #0f0f17; color: #cdd6f4; }
    QLabel { color: #e6e9ef; font-size: 13px; font-weight: bold; }
    QRadioButton { color: #e6e9ef; padding: 4px; }
    QComboBox {
        background-color: #1e1e2e; color: #ffffff; border: 1px solid #45475a;
        padding: 8px; border-radius: 4px;
    }
    QPushButton {
        background-color: #1e1e2e; color: #89dceb; border: 1px solid #89dceb;
        border-radius: 6px; padding: 10px; font-weight: bold;
    }
    QPushButton:hover { background-color: #89dceb; color: #11111b; }
    QPushButton#btn_apply { color: #a6e3a1; border-color: #a6e3a1; }
    """

    def __init__(self, parent, mode, theme, unified_hex, custom_unified_enabled):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Color de Etiquetas")
        self.setMinimumWidth(540)
        self.setStyleSheet(self.STYLESHEET)
        self.mode = mode
        self.theme = theme
        self.unified_hex = unified_hex
        self.custom_unified_enabled = custom_unified_enabled
        self._build_ui()
        self._sync_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        layout.addWidget(QLabel("🎯 Modo de Coloreado"))
        self.mode_group = QButtonGroup(self)
        self.rb_instance = QRadioButton("Modo Instancia (cada box con color único)")
        self.rb_class = QRadioButton("Modo Clase (mismo color por categoría)")
        self.rb_unified = QRadioButton("Modo Unificado (todas con un color)")
        self.mode_group.addButton(self.rb_instance)
        self.mode_group.addButton(self.rb_class)
        self.mode_group.addButton(self.rb_unified)
        layout.addWidget(self.rb_instance)
        layout.addWidget(self.rb_class)
        layout.addWidget(self.rb_unified)

        layout.addWidget(QFrame(frameShape=QFrame.HLine))

        layout.addWidget(QLabel("🌈 Tema de Paleta"))
        self.theme_combo = QComboBox()
        for theme_id, label in THEME_LABELS.items():
            self.theme_combo.addItem(label, theme_id)
        layout.addWidget(self.theme_combo)

        row_unified = QHBoxLayout()
        row_unified.addWidget(QLabel("🎨 Color unificado personalizado"))
        self.btn_color_wheel = QPushButton("Abrir ruleta de color")
        self.btn_color_wheel.clicked.connect(self._pick_color_with_wheel)
        row_unified.addWidget(self.btn_color_wheel)
        layout.addLayout(row_unified)

        self.chk_custom_unified = QCheckBox("Activar color unificado personalizado (prioridad sobre tema)")
        self.chk_custom_unified.setChecked(self.custom_unified_enabled)
        self.chk_custom_unified.stateChanged.connect(self._on_custom_unified_toggled)
        layout.addWidget(self.chk_custom_unified)

        self.color_preview = QLabel("      ")
        self.color_preview.setFixedHeight(28)
        self.color_preview.setStyleSheet("border: 1px solid #45475a; border-radius: 4px;")
        layout.addWidget(self.color_preview)

        footer = QHBoxLayout()
        footer.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_apply = QPushButton("💾 Guardar y Aplicar")
        btn_apply.setObjectName("btn_apply")
        btn_apply.clicked.connect(self.accept)
        footer.addWidget(btn_cancel)
        footer.addWidget(btn_apply)
        layout.addLayout(footer)

    def _sync_ui(self):
        self.rb_instance.setChecked(self.mode == MODE_INSTANCE)
        self.rb_class.setChecked(self.mode == MODE_CLASS)
        self.rb_unified.setChecked(self.mode == MODE_UNIFIED)

        theme_index = self.theme_combo.findData(self.theme)
        self.theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        self._on_custom_unified_toggled(Qt.Checked if self.custom_unified_enabled else Qt.Unchecked)
        self._refresh_preview()

    def _on_custom_unified_toggled(self, state):
        enabled = state == Qt.Checked
        self.btn_color_wheel.setEnabled(enabled)
        self.color_preview.setEnabled(enabled)

    def _refresh_preview(self):
        self.color_preview.setStyleSheet(
            "background-color: {0}; border: 1px solid #45475a; border-radius: 4px;".format(self.unified_hex)
        )

    def _pick_color_with_wheel(self):
        color = QColorDialog.getColor(
            QColor(self.unified_hex),
            self,
            "Selecciona cualquier tonalidad (ruleta)",
            QColorDialog.DontUseNativeDialog | QColorDialog.ShowAlphaChannel,
        )
        if color.isValid():
            self.unified_hex = color.name(QColor.HexRgb)
            self.rb_unified.setChecked(True)
            self._refresh_preview()

    def get_values(self):
        if self.rb_instance.isChecked():
            mode = MODE_INSTANCE
        elif self.rb_unified.isChecked():
            mode = MODE_UNIFIED
        else:
            mode = MODE_CLASS

        theme = self.theme_combo.currentData()
        if theme not in COLOR_THEMES:
            theme = "neon"
        return mode, theme, self.unified_hex, self.chk_custom_unified.isChecked()

