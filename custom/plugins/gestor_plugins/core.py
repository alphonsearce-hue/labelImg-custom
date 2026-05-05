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
    QTableWidget, QTableWidgetItem, QCheckBox, QHeaderView, QMessageBox, QAction, QMenu
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
        # Ruta absoluta al archivo config.json (subiendo dos niveles desde core.py)
        # core.py -> plugin_manager -> plugins -> custom
        base_custom = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = os.path.join(base_custom, "config.json")
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
        # Ruta absoluta a la carpeta de plugins (subiendo un nivel desde core.py -> plugin_manager)
        plugins_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if not os.path.exists(plugins_dir):
            print(f"[PluginManager] No se encontró la carpeta: {plugins_dir}")
            return

        folders = [f for f in os.listdir(plugins_dir) if os.path.isdir(os.path.join(plugins_dir, f))]
        
        self.tabla.setRowCount(len(folders))
        for i, folder in enumerate(folders):
            # Checkbox
            chk = QCheckBox()
            is_enabled = self.plugins_config.get(folder, True)
            if folder == "gestor_plugins":
                is_enabled = True
            chk.setChecked(is_enabled)
            if folder == "gestor_plugins":
                chk.setEnabled(False)
                chk.setToolTip("Plugin crítico del sistema. Siempre activo.")
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
            nueva_config[folder] = True if folder == "gestor_plugins" else chk.isChecked()
        
        with open(self.config_path, 'w') as f:
            json.dump(nueva_config, f, indent=4)
        
        QMessageBox.information(self, "Plugins", "Configuración guardada.\nPor favor, reinicia LabelImg para aplicar los cambios.")
        self.accept()

def setup(main_window):
    # Menú raíz único para el ecosistema de plugins.
    if not hasattr(main_window, 'menu_plugins') or main_window.menu_plugins is None:
        main_window.menu_plugins = main_window.menuBar().addMenu("&Plugins")

    if not hasattr(main_window, "_plugin_submenus"):
        main_window._plugin_submenus = {}
    if not hasattr(main_window, "_plugin_tool_groups"):
        main_window._plugin_tool_groups = {}

    def _get_or_create_plugin_submenu(section_name):
        section = (section_name or "").strip()
        if not section:
            return main_window.menu_plugins

        if section not in main_window._plugin_submenus:
            submenu = QMenu(section, main_window)
            main_window.menu_plugins.addMenu(submenu)
            main_window._plugin_submenus[section] = submenu

        return main_window._plugin_submenus[section]

    def register_plugin_action(section_name, action):
        """API para que los plugins registren acciones bajo &Plugins."""
        submenu = _get_or_create_plugin_submenu(section_name)
        submenu.addAction(action)
        return action

    def register_plugin_submenu(section_name):
        """API para crear/reutilizar submenús bajo &Plugins."""
        return _get_or_create_plugin_submenu(section_name)

    def _ensure_dock_tool_groups():
        if main_window._plugin_tool_groups:
            return

        dock_widget = main_window.dock.widget()
        dock_layout = dock_widget.layout()

        groups = [
            ("label_mods", "🎨 Modificación de Etiquetas"),
            ("class_tools", "🏷 Herramientas de Clases"),
        ]

        for idx, (group_id, title) in enumerate(groups):
            button = QPushButton(title)
            button.setStyleSheet(
                """
                QPushButton {
                    background-color: #1e1e2e;
                    color: #cba6f7;
                    border: 1px solid #3d3d5c;
                    border-radius: 6px;
                    padding: 10px;
                    font-weight: bold;
                    margin-top: 8px;
                }
                QPushButton:hover {
                    background-color: #3d3d5c;
                    color: #ffffff;
                }
                """
            )

            menu = QMenu(main_window)
            menu.setStyleSheet(
                """
                QMenu { background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #45475a; }
                QMenu::item { padding: 8px 16px; }
                QMenu::item:selected { background-color: #313244; color: #a6e3a1; }
                """
            )
            button.clicked.connect(lambda checked=False, b=button, m=menu: m.exec_(b.mapToGlobal(b.rect().bottomLeft())))

            dock_layout.insertWidget(idx, button)
            main_window._plugin_tool_groups[group_id] = {"button": button, "menu": menu}

    def register_plugin_tool(group_id, title, callback):
        """Registra una herramienta en los botones agrupados del dock."""
        _ensure_dock_tool_groups()
        if group_id not in main_window._plugin_tool_groups:
            return None

        action = QAction(title, main_window)
        action.triggered.connect(lambda checked=False, cb=callback: cb())
        main_window._plugin_tool_groups[group_id]["menu"].addAction(action)
        return action

    main_window.register_plugin_action = register_plugin_action
    main_window.register_plugin_submenu = register_plugin_submenu
    main_window.register_plugin_tool = register_plugin_tool

    action = QAction("⚙️ Gestionar Plugins", main_window)
    action.triggered.connect(lambda: PluginManagerDialog(main_window).exec_())
    main_window.register_plugin_action("Administración", action)
