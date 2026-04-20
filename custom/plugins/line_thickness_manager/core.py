# =============================================================================
# custom/plugins/line_thickness_manager/core.py
# =============================================================================
# PROPÓSITO: Editor visual avanzado de anotaciones.
# Controla transparencia, grosor, saturación, nitidez y dimensiones.
# =============================================================================

__version__ = "2.2.0"
__description__ = "Editor visual profesional: Saturación vibrante, bordes nítidos y transparencia."

import os
import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QFrame, 
    QDialog, QPushButton, QCheckBox, QComboBox
)
from PyQt5.QtCore import Qt
from libs.shape import Shape

# --- Estilos Mejorados (Look Premium) ---
STYLESHEET = """
QDialog {
    background-color: #0f0f17;
    color: #ffffff;
}
QLabel { color: #e0e0e0; font-size: 13px; font-weight: bold; }
QCheckBox { color: #ffffff; spacing: 10px; padding: 5px; }
QCheckBox::indicator { width: 20px; height: 20px; border: 2px solid #a6e3a1; border-radius: 4px; background: #1e1e2e; }
QCheckBox::indicator:checked { background-color: #a6e3a1; }
QSlider::handle:horizontal { background: #a6e3a1; width: 18px; height: 18px; border-radius: 9px; }
QPushButton {
    background-color: #1e1e2e;
    color: #a6e3a1;
    border: 1px solid #a6e3a1;
    border-radius: 6px;
    padding: 12px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover { background-color: #a6e3a1; color: #11111b; }
QComboBox { background-color: #1e1e2e; color: #ffffff; border: 1px solid #45475a; padding: 6px; border-radius: 4px; }
"""

class VisualEditorDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Estilo Visual")
        self.setMinimumWidth(480)
        self.setStyleSheet(STYLESHEET)
        self.config = config or {}
        self._construir_ui()

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        # 1. Grosor
        layout.addWidget(QLabel("📏 Grosor de Borde (px)"))
        self.slider_thickness = self._crear_slider(1, 15, self.config.get("thickness", 2))
        layout.addWidget(self.slider_thickness)

        # 2. Transparencia
        layout.addWidget(QLabel("🌫️ Intensidad del Relleno (Alpha)"))
        self.slider_alpha = self._crear_slider(0, 255, self.config.get("alpha", 128))
        layout.addWidget(self.slider_alpha)

        # 3. Saturación (NUEVO)
        layout.addWidget(QLabel("🌈 Saturación de Color (Vibrancia)"))
        self.slider_sat = self._crear_slider(10, 30, int(self.config.get("saturation", 1.0) * 10))
        layout.addWidget(self.slider_sat)

        # 4. Estilo de Trazo
        layout.addWidget(QLabel("🧵 Estilo de Trazo"))
        self.combo_style = QComboBox()
        self.combo_style.addItems(["Sólida", "Discontinua (Dash)", "Punteada (Dot)"])
        styles_map = {Qt.SolidLine: 0, Qt.DashLine: 1, Qt.DotLine: 2}
        self.combo_style.setCurrentIndex(styles_map.get(self.config.get("dash_style", Qt.SolidLine), 0))
        layout.addWidget(self.combo_style)

        layout.addWidget(QFrame(frameShape=QFrame.HLine))

        # Checkboxes
        self.chk_sharp = QCheckBox("🎯 Bordes Nítidos (Sharp Edges / No AA)")
        self.chk_sharp.setChecked(self.config.get("sharp", False))
        layout.addWidget(self.chk_sharp)

        self.chk_adaptive = QCheckBox("🔍 Grosor adaptativo al zoom")
        self.chk_adaptive.setChecked(self.config.get("adaptive", False))
        layout.addWidget(self.chk_adaptive)

        self.chk_highlight = QCheckBox("✨ Resaltar caja seleccionada")
        self.chk_highlight.setChecked(self.config.get("highlight", True))
        layout.addWidget(self.chk_highlight)

        self.chk_focus = QCheckBox("🎚️ Modo Enfoque (Atenuar no seleccionadas)")
        self.chk_focus.setChecked(self.config.get("focus", False))
        layout.addWidget(self.chk_focus)

        self.chk_dims = QCheckBox("📏 Mostrar Dimensiones (WxH)")
        self.chk_dims.setChecked(self.config.get("dims", False))
        layout.addWidget(self.chk_dims)

        layout.addStretch()

        # Botón Aplicar
        btn_aplicar = QPushButton("💾 Guardar y Aplicar Estilo")
        btn_aplicar.clicked.connect(self.accept)
        layout.addWidget(btn_aplicar)

    def _crear_slider(self, min_v, max_v, current):
        s = QSlider(Qt.Horizontal)
        s.setRange(min_v, max_v)
        s.setValue(current)
        return s

    def get_values(self):
        style_map = [Qt.SolidLine, Qt.DashLine, Qt.DotLine]
        return {
            "thickness": self.slider_thickness.value(),
            "alpha": self.slider_alpha.value(),
            "saturation": self.slider_sat.value() / 10.0,
            "dash_style": style_map[self.combo_style.currentIndex()],
            "sharp": self.chk_sharp.isChecked(),
            "adaptive": self.chk_adaptive.isChecked(),
            "highlight": self.chk_highlight.isChecked(),
            "focus": self.chk_focus.isChecked(),
            "dims": self.chk_dims.isChecked()
        }

class VisualEditorPlugin:
    def __init__(self, main_window):
        self.main_window = main_window
        self.config_file = os.path.join(os.path.dirname(__file__), "visual_config.json")
        self.config = self.load_config()
        
        self._aplicar_config(self.config)
        self._setup_ui()
        self._setup_hooks()

    def _setup_ui(self):
        if hasattr(self.main_window, "register_plugin_tool"):
            self.main_window.register_plugin_tool(
                "label_mods",
                "🎨 Personalizar Estilo Visual",
                self._abrir_editor
            )
            return

        dock_widget = self.main_window.dock.widget()
        dock_layout = dock_widget.layout()

        self.btn_editor = QPushButton("🎨 Personalizar Estilo Visual")
        self.btn_editor.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e;
                color: #cba6f7;
                border: 1px solid #cba6f7;
                border-radius: 6px;
                padding: 12px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover { background-color: #cba6f7; color: #11111b; }
        """)
        self.btn_editor.clicked.connect(self._abrir_editor)

        dock_layout.insertWidget(1, self.btn_editor)

    def _setup_hooks(self):
        if hasattr(self.main_window, 'zoom_widget'):
            self.main_window.zoom_widget.valueChanged.connect(self.main_window.canvas.update)

    def _abrir_editor(self):
        dialog = VisualEditorDialog(self.main_window, self.config)
        if dialog.exec_():
            self.config = dialog.get_values()
            self._aplicar_config(self.config)
            self.save_config()
            self.main_window.canvas.update()

    def _aplicar_config(self, cfg):
        Shape.line_thickness = float(cfg.get("thickness", 2))
        Shape.fill_alpha = int(cfg.get("alpha", 128))
        Shape.saturation_factor = float(cfg.get("saturation", 1.0))
        Shape.dash_style = cfg.get("dash_style", Qt.SolidLine)
        Shape.sharp_edges = cfg.get("sharp", False)
        Shape.adaptive_thickness = cfg.get("adaptive", False)
        Shape.highlight_selected = cfg.get("highlight", True)
        Shape.focus_mode = cfg.get("focus", False)
        Shape.show_dimensions = cfg.get("dims", False)

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except: pass
        return {"thickness": 2, "alpha": 128, "saturation": 1.0, "dash_style": Qt.SolidLine, 
                "sharp": False, "adaptive": False, "highlight": True, "focus": False, "dims": False}

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f)
        except: pass

def setup(main_window):
    main_window._visual_editor = VisualEditorPlugin(main_window)
