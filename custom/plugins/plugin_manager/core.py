# =============================================================================
# custom/plugins/plugin_manager/core.py
# =============================================================================
# PROPÓSITO: Gestor central de plugins con funciones masivas y recarga.
# =============================================================================

__version__ = "1.1.0"
__description__ = "Gestor avanzado: Activa/Desactiva todo y recarga el sistema."

import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QCheckBox, QHeaderView, QMessageBox, QAction
)
from PyQt5.QtCore import Qt

# --- Estilos ---
STYLESHEET = """
QDialog { background-color: #1a1b26; color: #a9b1d6; }
QTableWidget { background-color: #24283b; color: #c0caf5; gridline-color: #414868; border-radius: 8px; }
QHeaderView::section { background-color: #414868; color: #7aa2f7; padding: 10px; font-weight: bold; border: none; }
QPushButton { background-color: #3d59a1; color: #ffffff; border-radius: 6px; padding: 10px; font-weight: bold; }
QPushButton:hover { background-color: #7aa2f7; }
QPushButton#btn_save { background-color: #9ece6a; color: #1a1b26; }
QPushButton#btn_danger { background-color: #f7768e; color: #ffffff; }
"""

class PluginManagerDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Plugin Manager — LabelImg")
        self.setMinimumWidth(750)
        self.setMinimumHeight(500)
        self.setStyleSheet(STYLESHEET)
        self.config_path = os.path.join("custom", "config.json")
        self.plugins_config = self._load_config()
        self._construir_ui()

    def _load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        
        header = QLabel("🔌 Gestión de Plugins")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #bb9af7; margin-bottom: 10px;")
        layout.addWidget(header)

        # Botones de Acción Masiva
        btn_layout = QHBoxLayout()
        btn_all = QPushButton("✅ Activar Todos")
        btn_all.clicked.connect(lambda: self._set_all_states(True))
        btn_none = QPushButton("❌ Desactivar Todos")
        btn_none.clicked.connect(lambda: self._set_all_states(False))
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        layout.addLayout(btn_layout)

        # Tabla
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Habilitado", "Nombre del Plugin", "Estado", "Versión"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tabla)
        
        self._cargar_tabla()

        # Footer
        footer = QHBoxLayout()
        btn_save = QPushButton("💾 Guardar y Aplicar")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._guardar_cambios)
        
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.close)
        
        footer.addStretch()
        footer.addWidget(btn_save)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

    def _cargar_tabla(self):
        plugins_dir = os.path.join("custom", "plugins")
        folders = [f for f in os.listdir(plugins_dir) if os.path.isdir(os.path.join(plugins_dir, f))]
        
        self.tabla.setRowCount(len(folders))
        for i, folder in enumerate(folders):
            # Checkbox
            chk = QCheckBox()
            chk.setChecked(self.plugins_config.get(folder, True))
            chk.setStyleSheet("margin-left: 20px;")
            self.tabla.setCellWidget(i, 0, chk)
            
            # Nombre
            self.tabla.setItem(i, 1, QTableWidgetItem(folder))
            
            # Estado (solo lectura para esta sesión)
            status = "activo" if hasattr(self.main_window, f"_{folder}") else "inactivo"
            self.tabla.setItem(i, 2, QTableWidgetItem(status))
            
            # Versión (si existe)
            self.tabla.setItem(i, 3, QTableWidgetItem("1.0.0"))

    def _set_all_states(self, state):
        for i in range(self.tabla.rowCount()):
            chk = self.tabla.cellWidget(i, 0)
            if chk: chk.setChecked(state)

    def _guardar_cambios(self):
        nueva_config = {}
        for i in range(self.tabla.rowCount()):
            folder = self.tabla.item(i, 1).text()
            chk = self.tabla.cellWidget(i, 0)
            nueva_config[folder] = chk.isChecked()
        
        with open(self.config_path, 'w') as f:
            json.dump(nueva_config, f, indent=4)
        
        QMessageBox.information(self, "Plugins", "Configuración guardada.\nPor favor, reinicia LabelImg para aplicar los cambios.")
        self.accept()

def setup(main_window):
    # Añadir al menú de Plugins de LabelImg
    if not hasattr(main_window, 'menu_plugins'):
        main_window.menu_plugins = main_window.menuBar().addMenu("&Plugins")
    
    action = QAction("⚙️ Gestionar Plugins", main_window)
    action.triggered.connect(lambda: PluginManagerDialog(main_window).exec_())
    main_window.menu_plugins.addAction(action)
