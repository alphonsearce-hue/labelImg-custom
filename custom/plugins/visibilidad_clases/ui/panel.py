# =============================================================================
# custom/plugins/class_visibility_manager/ui/panel.py
# =============================================================================
# PROPÓSITO: Diálogo de visibilidad por clase.
# Rediseñado para máximo contraste (Letras brillantes sobre fondo oscuro).
# =============================================================================

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QCheckBox, QFrame, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

# --- Paleta de Máximo Contraste (Cattppuccin Mocha / Deep Night) ---
DARK_BG        = "#11111b"  # Fondo ultra oscuro
DARK_SURFACE   = "#181825"
DARK_BORDER    = "#45475a"
ACCENT_PURPLE  = "#cba6f7"  # Púrpura brillante
ACCENT_GREEN   = "#a6e3a1"  # Verde brillante
ACCENT_RED     = "#f38ba8"  # Rojo brillante
TEXT_MAIN      = "#ffffff"  # Blanco puro para los nombres de las clases (Máxima legibilidad)
TEXT_DIM       = "#a6adc8"  # Gris claro

PANEL_STYLESHEET = f"""
QDialog {{
    background-color: {DARK_BG};
    color: {TEXT_MAIN};
    border: 1px solid {DARK_BORDER};
}}
QLabel#titulo_dialogo {{
    color: {ACCENT_PURPLE};
    font-size: 18px;
    font-weight: bold;
    padding: 10px;
    border-bottom: 1px solid {DARK_BORDER};
}}
QCheckBox {{
    color: {TEXT_MAIN};
    font-size: 13px;
    font-weight: bold;
    background: transparent;
    padding: 8px;
    spacing: 12px;
}}
QCheckBox:hover {{
    background-color: {DARK_SURFACE};
    border-radius: 6px;
    color: {ACCENT_PURPLE};
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid {DARK_BORDER};
    background-color: {DARK_BG};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT_PURPLE};
    border-color: {ACCENT_PURPLE};
    image: url(n/a); /* Forzar refresco visual si fuera necesario */
}}
QCheckBox::indicator:unchecked:hover {{
    border-color: {ACCENT_PURPLE};
}}
QPushButton {{
    background-color: {DARK_SURFACE};
    color: {TEXT_MAIN};
    border: 1px solid {DARK_BORDER};
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {ACCENT_PURPLE};
    color: {DARK_BG};
    border: 1px solid {ACCENT_PURPLE};
}}
QPushButton#btn_show_all {{
    border: 2px solid {ACCENT_GREEN};
    color: {ACCENT_GREEN};
}}
QPushButton#btn_show_all:hover {{
    background-color: {ACCENT_GREEN};
    color: {DARK_BG};
}}
QPushButton#btn_hide_all {{
    border: 2px solid {ACCENT_RED};
    color: {ACCENT_RED};
}}
QPushButton#btn_hide_all:hover {{
    background-color: {ACCENT_RED};
    color: {DARK_BG};
}}
QScrollArea {{
    background-color: {DARK_SURFACE};
    border: 1px solid {DARK_BORDER};
    border-radius: 10px;
}}
"""

class ClassVisibilityDialog(QDialog):
    """
    Diálogo modal para gestionar la visibilidad por clase.
    """
    visibilidad_cambiada = pyqtSignal(str, bool)
    mostrar_todo = pyqtSignal()
    ocultar_todo = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VisibilityDialog")
        self.setWindowTitle("Gestor de Visibilidad por Clase")
        self.setMinimumSize(450, 600)
        self.setStyleSheet(PANEL_STYLESHEET)
        self._checkboxes = {}
        self._estado_clases = {}
        self._construir_ui()

    def _construir_ui(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(25, 25, 25, 25)
        layout_principal.setSpacing(15)
        
        titulo = QLabel("👁 Visibilidad por Clase")
        titulo.setObjectName("titulo_dialogo")
        layout_principal.addWidget(titulo)

        # Botones de control global (Show/Hide All)
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(15)
        
        btn_show = QPushButton("Mostrar Todo")
        btn_show.setObjectName("btn_show_all")
        btn_show.setCursor(Qt.PointingHandCursor)
        btn_show.clicked.connect(self._on_show_all)
        
        btn_hide = QPushButton("Ocultar Todo")
        btn_hide.setObjectName("btn_hide_all")
        btn_hide.setCursor(Qt.PointingHandCursor)
        btn_hide.clicked.connect(self._on_hide_all)
        
        ctrl_layout.addWidget(btn_show)
        ctrl_layout.addWidget(btn_hide)
        layout_principal.addLayout(ctrl_layout)

        # Área de scroll para la lista de clases
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.clases_layout = QVBoxLayout(self.scroll_content)
        self.clases_layout.setContentsMargins(10, 10, 10, 10)
        self.clases_layout.setSpacing(5)
        self.scroll.setWidget(self.scroll_content)
        layout_principal.addWidget(self.scroll)

        # Botón de cierre
        btn_close = QPushButton("Cerrar")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        layout_principal.addWidget(btn_close)

    def actualizar_clases(self, clases, estado_sesion):
        """Reconstruye la lista de checkboxes basada en las clases de la imagen."""
        # Limpiar lista previa
        while self.clases_layout.count():
            item = self.clases_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self._checkboxes = {}
        # El estado de sesión tiene prioridad para mantener la persistencia
        self._estado_clases = estado_sesion

        if not clases:
            label_vacio = QLabel("No hay etiquetas en esta imagen.")
            label_vacio.setStyleSheet(f"color: {TEXT_DIM}; padding: 20px;")
            label_vacio.setAlignment(Qt.AlignCenter)
            self.clases_layout.addWidget(label_vacio)
            return

        for clase in sorted(clases):
            # Si no está en el estado de sesión, por defecto es visible (True)
            visible = self._estado_clases.get(clase, True)
            self._estado_clases[clase] = visible

            cb = QCheckBox(clase)
            cb.setChecked(visible)
            # Conexión directa del toggle individual
            cb.stateChanged.connect(lambda state, c=clase: self._on_toggled(c, state))
            
            self._checkboxes[clase] = cb
            self.clases_layout.addWidget(cb)
        
        self.clases_layout.addStretch()

    def _on_toggled(self, clase, state):
        """Manejador para el cambio de un checkbox individual."""
        visible = (state == Qt.Checked)
        self._estado_clases[clase] = visible
        self.visibilidad_cambiada.emit(clase, visible)

    def _on_show_all(self):
        """Marca todos los checkboxes."""
        for cb in self._checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self.mostrar_todo.emit()

    def _on_hide_all(self):
        """Desmarca todos los checkboxes."""
        for cb in self._checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self.ocultar_todo.emit()
