import json
import os

from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QColor, QBrush, QPolygonF
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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

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

__version__ = "1.2.0"
__description__ = (
    "Colores por clase/instancia, colores personalizados por clase, "
    "resaltado al pasar el cursor."
)

_original_shape_paint = None


class LabelColorManagerPlugin:
    def __init__(self, main_window):
        self.main_window = main_window
        self.canvas = main_window.canvas
        self.config_path = os.path.join(os.path.dirname(__file__), "color_config.json")

        self.mode = MODE_CLASS
        self.theme = "neon"
        self.unified_hex = "#39FF14"
        self.custom_unified_enabled = False
        self.custom_class_colors_enabled = False
        self.class_colors = {}
        self.hover_highlight_enabled = True
        self.hover_alpha = 90

        self._instance_color_map = {}
        self._color_cache = {}
        self._batch_depth = 0
        self._hover_shape = None

        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_visuals)

        self._load_config()
        self._setup_ui()
        self._patch_main_window_hooks()
        self._install_hover_highlight()
        self._refresh_visuals()

    def _setup_ui(self):
        if hasattr(self.main_window, "register_plugin_tool"):
            self.main_window.register_plugin_tool(
                "label_mods",
                "🎨 Configuración de Colores",
                self._open_config_dialog,
            )
            return

        dock_widget = self.main_window.dock.widget()
        dock_layout = dock_widget.layout()
        self.btn_color_mode = QPushButton("🎨 Configuración de Colores")
        self.btn_color_mode.setStyleSheet(
            """
            QPushButton {
                background-color: #1e1e2e; color: #a6e3a1;
                border: 1px solid #a6e3a1; border-radius: 6px;
                padding: 10px; font-weight: bold; margin-top: 8px;
            }
            QPushButton:hover { background-color: #a6e3a1; color: #11111b; }
            """
        )
        self.btn_color_mode.clicked.connect(self._open_config_dialog)
        dock_layout.insertWidget(2, self.btn_color_mode)

        if hasattr(self.main_window, "register_plugin_action"):
            action = QAction("Colores de Etiquetas", self.main_window)
            action.triggered.connect(self._open_config_dialog)
            self.main_window.register_plugin_action("Visualización", action)

    def _open_config_dialog(self, checked=False):
        original_config = {
            "mode": self.mode,
            "theme": self.theme,
            "unified_hex": self.unified_hex,
            "custom_unified_enabled": self.custom_unified_enabled,
            "custom_class_colors_enabled": self.custom_class_colors_enabled,
            "class_colors": self.class_colors.copy(),
            "hover_highlight_enabled": self.hover_highlight_enabled,
            "hover_alpha": self.hover_alpha,
        }

        def on_change():
            dialog.apply_to_plugin(self)
            self._invalidate_caches()
            self._refresh_visuals()

        dialog = ColorManagerDialog(self.main_window, self, on_change=on_change)
        if dialog.exec_():
            dialog.apply_to_plugin(self)
            self._save_config()
            self._invalidate_caches()
            self._refresh_visuals()
        else:
            self.mode = original_config["mode"]
            self.theme = original_config["theme"]
            self.unified_hex = original_config["unified_hex"]
            self.custom_unified_enabled = original_config["custom_unified_enabled"]
            self.custom_class_colors_enabled = original_config["custom_class_colors_enabled"]
            self.class_colors = original_config["class_colors"].copy()
            self.hover_highlight_enabled = original_config["hover_highlight_enabled"]
            self.hover_alpha = original_config["hover_alpha"]
            self._invalidate_caches()
            self._refresh_visuals()

    def _patch_main_window_hooks(self):
        for method_name in ("load_labels", "add_label", "new_shape", "edit_label"):
            self._wrap_main_window_method(method_name)

    def _wrap_main_window_method(self, method_name):
        original = getattr(self.main_window, method_name, None)
        if original is None or getattr(original, "_label_color_wrapped", False):
            return

        plugin = self

        def wrapped(*args, **kwargs):
            is_load_labels = method_name == "load_labels"
            if is_load_labels:
                plugin._batch_depth += 1
                if plugin._batch_depth == 1:
                    plugin._invalidate_caches()

            result = original(*args, **kwargs)

            if is_load_labels:
                plugin._batch_depth -= 1
                if plugin._batch_depth <= 0:
                    plugin._batch_depth = 0
                    plugin._refresh_visuals()
            elif method_name == "add_label":
                shape = args[0] if args else None
                if shape is not None:
                    in_bulk = plugin._batch_depth > 0 or getattr(
                        plugin.main_window, "_bulk_loading_labels", False
                    )
                    if not in_bulk:
                        plugin._refresh_single(shape)
            elif method_name == "new_shape":
                plugin._on_new_shape_created()
                if plugin._batch_depth <= 0:
                    plugin._schedule_refresh()
            elif plugin._batch_depth <= 0 and not getattr(
                plugin.main_window, "_bulk_loading_labels", False
            ):
                plugin._schedule_refresh()

            return result

        wrapped._label_color_wrapped = True
        setattr(self.main_window, method_name, wrapped)

    def _install_hover_highlight(self):
        canvas = self.canvas
        if getattr(canvas, "_color_hover_move_patched", False):
            return

        plugin = self
        original_move = canvas.mouseMoveEvent

        def wrapped_move(ev):
            prev = plugin._hover_shape
            original_move(ev)
            candidate = canvas.h_shape
            if (
                plugin.hover_highlight_enabled
                and candidate
                and canvas.isVisible(candidate)
                and not canvas.drawing()
            ):
                new_hover = candidate
            else:
                new_hover = None

            if prev is not new_hover:
                if prev is not None:
                    prev._hover_highlight = False
                plugin._hover_shape = new_hover
                if new_hover is not None:
                    new_hover._hover_highlight = True

        wrapped_move._color_hover_move_patched = True
        canvas.mouseMoveEvent = wrapped_move

        global _original_shape_paint
        if _original_shape_paint is None:
            _original_shape_paint = Shape.paint

        orig_paint = _original_shape_paint
        if getattr(Shape.paint, "_color_hover_paint", False):
            return

        def patched_paint(shape, painter):
            orig_paint(shape, painter)
            if plugin.hover_highlight_enabled and getattr(shape, "_hover_highlight", False):
                plugin._draw_hover_overlay(shape, painter)

        patched_paint._color_hover_paint = True
        Shape.paint = patched_paint
        canvas._color_hover_move_patched = True

    def _draw_hover_overlay(self, shape, painter):
        if len(shape.points) < 3:
            return
        poly = QPolygonF([QPointF(p.x(), p.y()) for p in shape.points])
        base = QColor(shape.line_color)
        base.setAlpha(self.hover_alpha)
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(base)
        painter.drawPolygon(poly)
        painter.restore()

    def _on_new_shape_created(self):
        if not self.custom_class_colors_enabled:
            return
        shapes = self.canvas.shapes
        if not shapes:
            return
        label = shapes[-1].label
        if label and label not in self.class_colors:
            self._prompt_color_for_class(label, parent=self.main_window)

    def _prompt_color_for_class(self, label, parent=None):
        initial = QColor(self.class_colors.get(label, "#39FF14"))
        color = QColorDialog.getColor(
            initial,
            parent or self.main_window,
            f"Color para la clase '{label}'",
            QColorDialog.DontUseNativeDialog,
        )
        if color.isValid():
            self.class_colors[label] = color.name(QColor.HexRgb)
            self._color_cache.clear()
            return True
        idx = stable_index(label, len(COLOR_THEMES.get(self.theme, COLOR_THEMES["neon"])))
        palette = COLOR_THEMES.get(self.theme) or COLOR_THEMES["neon"]
        self.class_colors[label] = palette[idx % len(palette)]
        return False

    def _known_class_names(self):
        names = set(self.class_colors.keys())
        names.update(getattr(self.main_window, "label_hist", []) or [])
        for shape in self.canvas.shapes:
            if shape.label:
                names.add(shape.label)
        return sorted(names)

    def _invalidate_caches(self):
        self._color_cache.clear()
        self._instance_color_map.clear()

    def _config_key(self):
        return (
            self.mode,
            self.theme,
            self.unified_hex,
            self.custom_unified_enabled,
            self.custom_class_colors_enabled,
            tuple(sorted(self.class_colors.items())),
        )

    def _resolve_shape_colors(self, shape):
        label = shape.label or ""

        if self.custom_class_colors_enabled and label in self.class_colors:
            cache_key = ("custom_class", label, self.class_colors[label])
            if cache_key in self._color_cache:
                return self._color_cache[cache_key]
            hex_color = self.class_colors[label]
            line = color_from_hex(hex_color, alpha=255)
            fill = color_from_hex(hex_color, alpha=120)
            self._color_cache[cache_key] = (line, fill)
            return line, fill

        palette = COLOR_THEMES.get(self.theme) or COLOR_THEMES["neon"]
        if not palette:
            return shape.line_color, shape.fill_color

        cfg = self._config_key()

        if self.custom_unified_enabled:
            cache_key = (cfg, "__custom_unified__")
            if cache_key in self._color_cache:
                return self._color_cache[cache_key]
            line = color_from_hex(self.unified_hex, alpha=255)
            fill = color_from_hex(self.unified_hex, alpha=120)
            self._color_cache[cache_key] = (line, fill)
            return line, fill

        if self.mode == MODE_INSTANCE:
            key = id(shape)
            if key not in self._instance_color_map:
                next_idx = len(self._instance_color_map) % len(palette)
                self._instance_color_map[key] = palette[next_idx]
            hex_color = self._instance_color_map[key]
            line = color_from_hex(hex_color, alpha=255)
            fill = color_from_hex(hex_color, alpha=120)
            return line, fill

        if self.mode == MODE_UNIFIED:
            cache_key = (cfg, "__unified__")
            if cache_key in self._color_cache:
                return self._color_cache[cache_key]
            hex_color = self.unified_hex if self.unified_hex in palette else palette[0]
            line = color_from_hex(hex_color, alpha=255)
            fill = color_from_hex(hex_color, alpha=120)
            self._color_cache[cache_key] = (line, fill)
            return line, fill

        cache_key = (cfg, label)
        if cache_key in self._color_cache:
            return self._color_cache[cache_key]
        idx = stable_index(label, len(palette))
        hex_color = palette[idx]
        line = color_from_hex(hex_color, alpha=255)
        fill = color_from_hex(hex_color, alpha=120)
        self._color_cache[cache_key] = (line, fill)
        return line, fill

    def _apply_colors_to_shape(self, shape):
        line_color, fill_color = self._resolve_shape_colors(shape)
        shape.line_color = line_color
        shape.fill_color = fill_color

    def _refresh_single(self, shape):
        self._apply_colors_to_shape(shape)
        item = self.main_window.shapes_to_items.get(shape)
        if item:
            item.setBackground(QBrush(QColor(shape.line_color)))
        self.canvas.update()

    def _schedule_refresh(self):
        self._refresh_timer.start(50)

    def _refresh_visuals(self):
        shapes = self.canvas.shapes
        items_to_shapes = getattr(self.main_window, "items_to_shapes", {})
        label_list = self.main_window.label_list

        label_list.blockSignals(True)
        try:
            for shape in shapes:
                self._apply_colors_to_shape(shape)
            for item, shape in items_to_shapes.items():
                item.setBackground(QBrush(QColor(shape.line_color)))
        finally:
            label_list.blockSignals(False)

        self.canvas.update()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        mode = data.get("mode", MODE_CLASS)
        if mode in ALL_MODES:
            self.mode = mode
        theme = data.get("theme", "neon")
        if theme in COLOR_THEMES:
            self.theme = theme
        self.unified_hex = data.get("unified_hex", "#39FF14")
        self.custom_unified_enabled = bool(data.get("custom_unified_enabled", False))
        self.custom_class_colors_enabled = bool(data.get("custom_class_colors_enabled", False))
        self.hover_highlight_enabled = bool(data.get("hover_highlight_enabled", True))
        self.hover_alpha = int(data.get("hover_alpha", 90))
        self.class_colors = dict(data.get("class_colors", {}))

    def _save_config(self):
        data = {
            "mode": self.mode,
            "theme": self.theme,
            "unified_hex": self.unified_hex,
            "custom_unified_enabled": self.custom_unified_enabled,
            "custom_class_colors_enabled": self.custom_class_colors_enabled,
            "hover_highlight_enabled": self.hover_highlight_enabled,
            "hover_alpha": self.hover_alpha,
            "class_colors": self.class_colors,
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass


def setup(main_window):
    plugin = LabelColorManagerPlugin(main_window)
    main_window._label_color_manager = plugin
    return plugin


class ColorManagerDialog(QDialog):
    STYLESHEET = """
    QDialog {
        background-color: #0f0f17;
        color: #ffffff;
    }
    QScrollArea {
        border: none;
        background-color: #0f0f17;
    }
    QWidget#body_widget {
        background-color: #0f0f17;
    }
    QScrollBar:vertical {
        background-color: #0f0f17;
        width: 12px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background-color: #313244;
        min-height: 20px;
        border-radius: 6px;
        margin: 2px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #a6e3a1;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QLabel { color: #e0e0e0; font-size: 13px; font-weight: bold; }
    QRadioButton, QCheckBox { color: #ffffff; spacing: 10px; padding: 5px; }
    QCheckBox::indicator, QRadioButton::indicator {
        width: 20px; height: 20px; border: 2px solid #a6e3a1; border-radius: 4px; background: #1e1e2e;
    }
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {
        background-color: #a6e3a1;
    }
    QRadioButton::indicator {
        border-radius: 11px;
    }
    QPushButton {
        background-color: #1e1e2e;
        color: #e0e0e0;
        border: 1px solid #45475a;
        border-radius: 6px;
        padding: 12px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover { background-color: #313244; color: #ffffff; }
    QPushButton#btn_apply {
        background-color: #1e1e2e;
        color: #a6e3a1;
        border: 1px solid #a6e3a1;
    }
    QPushButton#btn_apply:hover {
        background-color: #a6e3a1;
        color: #11111b;
    }
    QComboBox { background-color: #1e1e2e; color: #ffffff; border: 1px solid #45475a; padding: 8px; border-radius: 4px; }
    """

    def __init__(self, parent, plugin: LabelColorManagerPlugin, on_change=None):
        super().__init__(parent)
        self.plugin = plugin
        self.on_change = on_change
        self.setWindowTitle("Configuración de Colores")
        self.setMinimumWidth(560)
        self.setMinimumHeight(520)
        self.setStyleSheet(self.STYLESHEET)
        self._class_color_buttons = {}
        self._build_ui()
        self._sync_ui()
        self._connect_signals()

    def _connect_signals(self):
        self.rb_instance.toggled.connect(self._trigger_change)
        self.rb_class.toggled.connect(self._trigger_change)
        self.rb_unified.toggled.connect(self._trigger_change)
        self.theme_combo.currentIndexChanged.connect(self._trigger_change)
        self.chk_custom_unified.stateChanged.connect(self._trigger_change)
        self.chk_custom_class.stateChanged.connect(self._trigger_change)
        self.chk_hover.stateChanged.connect(self._trigger_change)

    def _trigger_change(self):
        if self.on_change:
            self.on_change()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("body_widget")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel("🎯 Modo de coloreado"))
        self.mode_group = QButtonGroup(self)
        self.rb_instance = QRadioButton("Instancia (cada caja distinta)")
        self.rb_class = QRadioButton("Clase (mismo color por categoría)")
        self.rb_unified = QRadioButton("Unificado (un solo color)")
        for rb in (self.rb_instance, self.rb_class, self.rb_unified):
            self.mode_group.addButton(rb)
            layout.addWidget(rb)

        layout.addWidget(QFrame(frameShape=QFrame.HLine))

        layout.addWidget(QLabel("🌈 Tema de paleta"))
        self.theme_combo = QComboBox()
        for theme_id, label in THEME_LABELS.items():
            self.theme_combo.addItem(label, theme_id)
        layout.addWidget(self.theme_combo)

        self.chk_custom_unified = QCheckBox("Color unificado personalizado (prioridad sobre tema)")
        layout.addWidget(self.chk_custom_unified)
        row_u = QHBoxLayout()
        self.btn_unified = QPushButton("Elegir color unificado")
        self.btn_unified.clicked.connect(self._pick_unified)
        self.color_preview = QLabel("      ")
        self.color_preview.setFixedHeight(24)
        row_u.addWidget(self.btn_unified)
        row_u.addWidget(self.color_preview)
        layout.addLayout(row_u)

        layout.addWidget(QFrame(frameShape=QFrame.HLine))

        self.chk_custom_class = QCheckBox(
            "Colores personalizados por clase (elige color de cada categoría)"
        )
        self.chk_custom_class.stateChanged.connect(self._toggle_class_panel)
        layout.addWidget(self.chk_custom_class)

        self.class_panel = QWidget()
        class_layout = QVBoxLayout(self.class_panel)
        class_layout.setContentsMargins(0, 0, 0, 0)
        self.class_list_host = QVBoxLayout()
        class_layout.addLayout(self.class_list_host)
        layout.addWidget(self.class_panel)

        layout.addWidget(QFrame(frameShape=QFrame.HLine))

        self.chk_hover = QCheckBox("Resaltar caja bajo el cursor (relleno semitransparente)")
        layout.addWidget(self.chk_hover)

        scroll.setWidget(body)
        outer.addWidget(scroll)

        foot = QHBoxLayout()
        foot.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_apply = QPushButton("💾 Guardar y Aplicar")
        btn_apply.setObjectName("btn_apply")
        btn_apply.clicked.connect(self.accept)
        foot.addWidget(btn_cancel)
        foot.addWidget(btn_apply)
        outer.addLayout(foot)

    def _sync_ui(self):
        p = self.plugin
        self.rb_instance.setChecked(p.mode == MODE_INSTANCE)
        self.rb_class.setChecked(p.mode == MODE_CLASS)
        self.rb_unified.setChecked(p.mode == MODE_UNIFIED)
        idx = self.theme_combo.findData(p.theme)
        self.theme_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.chk_custom_unified.setChecked(p.custom_unified_enabled)
        self.chk_custom_class.setChecked(p.custom_class_colors_enabled)
        self.chk_hover.setChecked(p.hover_highlight_enabled)
        self._refresh_unified_preview()
        self._rebuild_class_color_rows()
        self._toggle_class_panel()

    def _toggle_class_panel(self):
        self.class_panel.setEnabled(self.chk_custom_class.isChecked())

    def _rebuild_class_color_rows(self):
        while self.class_list_host.count():
            item = self.class_list_host.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._class_color_buttons.clear()

        for label in self.plugin._known_class_names():
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setMinimumWidth(180)
            btn = QPushButton("Cambiar color")
            hex_color = self.plugin.class_colors.get(label, "#888888")
            btn.setStyleSheet(f"background-color: {hex_color}; color: #111111; border: none; border-radius: 6px; padding: 8px; font-weight: bold;")
            btn.clicked.connect(lambda _=False, l=label, b=btn: self._pick_class_color(l, b))
            row.addWidget(lbl)
            row.addWidget(btn)
            host = QWidget()
            host.setLayout(row)
            self.class_list_host.addWidget(host)
            self._class_color_buttons[label] = btn

    def _pick_class_color(self, label, button):
        initial = QColor(self.plugin.class_colors.get(label, "#39FF14"))
        color = QColorDialog.getColor(initial, self, f"Color para '{label}'")
        if color.isValid():
            hex_c = color.name(QColor.HexRgb)
            self.plugin.class_colors[label] = hex_c
            button.setStyleSheet(f"background-color: {hex_c}; color: #111111; border: none; border-radius: 6px; padding: 8px; font-weight: bold;")
            self._trigger_change()

    def _pick_unified(self):
        color = QColorDialog.getColor(QColor(self.plugin.unified_hex), self, "Color unificado")
        if color.isValid():
            self.plugin.unified_hex = color.name(QColor.HexRgb)
            self.rb_unified.setChecked(True)
            self._refresh_unified_preview()
            self._trigger_change()

    def _refresh_unified_preview(self):
        self.color_preview.setStyleSheet(
            f"background-color: {self.plugin.unified_hex}; border: 1px solid #45475a; border-radius: 4px;"
        )

    def apply_to_plugin(self, plugin: LabelColorManagerPlugin):
        if self.rb_instance.isChecked():
            plugin.mode = MODE_INSTANCE
        elif self.rb_unified.isChecked():
            plugin.mode = MODE_UNIFIED
        else:
            plugin.mode = MODE_CLASS

        theme = self.theme_combo.currentData()
        plugin.theme = theme if theme in COLOR_THEMES else "neon"
        plugin.custom_unified_enabled = self.chk_custom_unified.isChecked()
        plugin.custom_class_colors_enabled = self.chk_custom_class.isChecked()
        plugin.hover_highlight_enabled = self.chk_hover.isChecked()

    def get_values(self):
        return None
