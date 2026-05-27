# =============================================================================
# custom/plugins/plugin_manager/core.py
# =============================================================================
# PROPÓSITO: Gestor central de plugins con funciones masivas y recarga.
# =============================================================================

__version__ = "1.1.0"
__description__ = "Gestor avanzado: Activa/Desactiva todo y recarga el sistema."

import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAction,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

# --- Estilos ---
STYLESHEET = """
QDialog {
    background-color: #0f0f17;
    color: #ffffff;
}
QLabel {
    color: #ffffff;
}
QTableWidget {
    background-color: #1e1e2e;
    color: #e0e0e0;
    gridline-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
}
QHeaderView::section {
    background-color: #313244;
    color: #a6e3a1;
    padding: 10px;
    font-weight: bold;
    border: none;
}
QCheckBox {
    color: #ffffff;
    spacing: 10px;
    padding: 5px;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 2px solid #a6e3a1;
    border-radius: 4px;
    background: #1e1e2e;
}
QCheckBox::indicator:checked {
    background-color: #a6e3a1;
}
QTableWidget QCheckBox {
    margin-left: 20px;
}
QPushButton {
    background-color: #1e1e2e;
    color: #e0e0e0;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 10px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #313244;
    color: #ffffff;
}
QPushButton#btn_save {
    background-color: #1e1e2e;
    color: #a6e3a1;
    border: 1px solid #a6e3a1;
}
QPushButton#btn_save:hover {
    background-color: #a6e3a1;
    color: #11111b;
}
QPushButton#btn_danger {
    background-color: #f7768e;
    color: #ffffff;
    border: 1px solid #f7768e;
}
QPushButton#btn_danger:hover {
    background-color: #f7768e;
    color: #11111b;
}
"""

MENU_STYLESHEET = """
QMenu {
    background-color: #0f0f17;
    color: #e0e0e0;
    border: 1px solid #313244;
}
QMenu::item {
    padding: 8px 24px;
}
QMenu::item:selected {
    background-color: #a6e3a1;
    color: #11111b;
    font-weight: bold;
}
QMenu::separator {
    background-color: #313244;
    height: 1px;
    margin: 4px 0px;
}
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
        base_custom = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.config_path = os.path.join(base_custom, "config.json")
        self.plugins_config = self._load_config()
        self._construir_ui()

    def _load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                return json.load(f)
        return {}

    def _construir_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("🔌 Gestión de Plugins")
        header.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #a6e3a1; margin-bottom: 10px;"
        )
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
        self.tabla.setHorizontalHeaderLabels(
            ["Habilitado", "Nombre del Plugin", "Estado", "Versión"]
        )
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

        # Filtrar carpetas válidas (que tengan __init__.py o core.py y no sean __pycache__)
        folders = []
        for f in os.listdir(plugins_dir):
            full_path = os.path.join(plugins_dir, f)
            if os.path.isdir(full_path) and f != "__pycache__":
                if os.path.exists(
                    os.path.join(full_path, "__init__.py")
                ) or os.path.exists(os.path.join(full_path, "core.py")):
                    folders.append(f)

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
            # No local stylesheet to prevent overriding the main premium checkbox styles.
            self.tabla.setCellWidget(i, 0, chk)

            # Nombre
            item_name = QTableWidgetItem(folder)
            item_name.setFlags(item_name.flags() ^ Qt.ItemIsEditable)
            self.tabla.setItem(i, 1, item_name)

            # Estado (solo lectura para esta sesión)
            loaded_plugins = getattr(self.main_window, "_loaded_plugins", set())
            is_active = (
                folder in loaded_plugins
                or hasattr(self.main_window, f"_{folder}")
                or any(folder in str(p) for p in loaded_plugins)
            )

            status_text = "activo" if is_active else "inactivo"
            item_status = QTableWidgetItem(status_text)
            item_status.setFlags(item_status.flags() ^ Qt.ItemIsEditable)
            if is_active:
                item_status.setForeground(QColor("#a6e3a1"))  # Premium Green
            else:
                item_status.setForeground(QColor("#6c7086"))  # Premium Muted Gray
            self.tabla.setItem(i, 2, item_status)

            # Versión (si existe)
            self.tabla.setItem(i, 3, QTableWidgetItem("1.0.0"))

    def _set_all_states(self, state):
        for i in range(self.tabla.rowCount()):
            chk = self.tabla.cellWidget(i, 0)
            if chk:
                chk.setChecked(state)

    def _guardar_cambios(self):
        nueva_config = {}
        for i in range(self.tabla.rowCount()):
            folder = self.tabla.item(i, 1).text()
            chk = self.tabla.cellWidget(i, 0)
            nueva_config[folder] = (
                True if folder == "gestor_plugins" else chk.isChecked()
            )

        with open(self.config_path, "w") as f:
            json.dump(nueva_config, f, indent=4)

        msg = QMessageBox(self)
        msg.setWindowTitle("Plugins")
        msg.setText(
            "Configuración guardada.\nPor favor, reinicia LabelImg para aplicar los cambios."
        )
        msg.setIcon(QMessageBox.Information)
        msg.setStyleSheet(STYLESHEET)
        msg.exec_()

        self.accept()


def setup(main_window):
    # Menú raíz único para el ecosistema de plugins.
    if not hasattr(main_window, "menu_plugins") or main_window.menu_plugins is None:
        main_window.menu_plugins = main_window.menuBar().addMenu("&Plugins")
        main_window.menu_plugins.setStyleSheet(MENU_STYLESHEET)

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
            submenu.setStyleSheet(MENU_STYLESHEET)
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
                    color: #a6e3a1;
                    border: 1px solid #a6e3a1;
                    border-radius: 6px;
                    padding: 10px;
                    font-weight: bold;
                    margin-top: 8px;
                }
                QPushButton:hover {
                    background-color: #a6e3a1;
                    color: #11111b;
                }
                """
            )

            menu = QMenu(main_window)
            menu.setStyleSheet(MENU_STYLESHEET)
            button.clicked.connect(
                lambda checked=False, b=button, m=menu: m.exec_(
                    b.mapToGlobal(b.rect().bottomLeft())
                )
            )

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
