from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from libs.utils import generate_color_by_text

__version__ = "1.0.0"
__description__ = "Buscar y reemplazar etiquetas de clase en lote."


def setup(main_window):
    plugin = ClassReplaceToolPlugin(main_window)
    main_window._class_replace_tool = plugin
    return plugin


class ClassReplaceToolPlugin:
    def __init__(self, main_window):
        self.mw = main_window
        self.canvas = main_window.canvas
        self._setup_ui()

    def _setup_ui(self):
        action = QAction("Buscar y reemplazar clase", self.mw)
        action.triggered.connect(self._open_replace_dialog)

        if hasattr(self.mw, "register_plugin_tool"):
            self.mw.register_plugin_tool(
                "class_tools",
                "🔁 Buscar y reemplazar clase",
                self._open_replace_dialog
            )
        else:
            self._create_dock_button()

        if hasattr(self.mw, "register_plugin_action"):
            self.mw.register_plugin_action("Edición", action)
        elif hasattr(self.mw, "menu_plugins"):
            self.mw.menu_plugins.addAction(action)

    def _create_dock_button(self):
        dock_widget = self.mw.dock.widget()
        dock_layout = dock_widget.layout()
        button = QPushButton("🔁 Buscar y Reemplazar Clase")
        button.setStyleSheet(
            """
            QPushButton {
                background-color: #1e1e2e;
                color: #f9e2af;
                border: 1px solid #f9e2af;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
                margin-top: 8px;
            }
            QPushButton:hover {
                background-color: #f9e2af;
                color: #11111b;
            }
            """
        )
        button.clicked.connect(self._open_replace_dialog)
        dock_layout.insertWidget(0, button)

    def _open_replace_dialog(self):
        dialog = ClassReplaceDialog(self.mw, self._collect_classes())
        if dialog.exec_():
            source_label, target_label = dialog.get_values()
            self._replace_class(source_label, target_label)

    def _collect_classes(self):
        classes = []
        classes.extend(getattr(self.mw, "label_hist", []))
        for shape in self.canvas.shapes:
            if shape.label:
                classes.append(shape.label)
        unique = sorted(set(classes))
        return unique

    def _replace_class(self, source_label, target_label):
        if not source_label or not target_label:
            return

        replaced = 0
        for shape in self.canvas.shapes:
            if shape.label == source_label:
                shape.label = target_label
                replaced += 1

        if replaced == 0:
            QMessageBox.information(
                self.mw,
                "Buscar/Reemplazar",
                f"No se encontraron cajas con la clase '{source_label}'.",
            )
            return

        items_to_shapes = getattr(self.mw, "items_to_shapes", None) or getattr(self.mw, "itemsToShapes", {})
        label_list = getattr(self.mw, "label_list", None) or getattr(self.mw, "labelList", None)

        if label_list:
            label_list.blockSignals(True)
        for item, shape in items_to_shapes.items():
            if shape.label == target_label:
                item.setText(target_label)
                item.setBackground(generate_color_by_text(target_label))
        if label_list:
            label_list.blockSignals(False)

        label_hist = getattr(self.mw, "label_hist", None)
        if isinstance(label_hist, list) and target_label not in label_hist:
            label_hist.append(target_label)

        if hasattr(self.mw, "set_dirty"):
            self.mw.set_dirty()
        if hasattr(self.mw, "update_combo_box"):
            self.mw.update_combo_box()

        self.canvas.update()
        QMessageBox.information(
            self.mw,
            "Buscar/Reemplazar",
            f"Se reemplazaron {replaced} cajas: '{source_label}' -> '{target_label}'.",
        )


class ClassReplaceDialog(QDialog):
    STYLESHEET = """
    QDialog { background-color: #0f0f17; color: #cdd6f4; }
    QLabel { color: #e6e9ef; font-size: 13px; font-weight: bold; }
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

    def __init__(self, parent, classes):
        super().__init__(parent)
        self.classes = classes or []
        self.setWindowTitle("Reemplazar Clases")
        self.setMinimumWidth(500)
        self.setStyleSheet(self.STYLESHEET)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        header = QLabel("🔁 Buscar y reemplazar clases")
        header.setStyleSheet("font-size: 18px; color: #f5c2e7; font-weight: bold;")
        layout.addWidget(header)

        layout.addWidget(QLabel("🏷 Clase origen (buscar):"))
        self.cmb_source = QComboBox()
        self.cmb_source.setEditable(False)
        self.cmb_source.addItems(self.classes)
        layout.addWidget(self.cmb_source)

        layout.addWidget(QLabel("🎯 Clase destino (reemplazar por):"))
        self.cmb_target = QComboBox()
        self.cmb_target.setEditable(True)
        self.cmb_target.addItems(self.classes)
        layout.addWidget(self.cmb_target)

        footer = QHBoxLayout()
        footer.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_apply = QPushButton("💾 Aplicar reemplazo")
        btn_apply.setObjectName("btn_apply")
        btn_apply.clicked.connect(self._on_apply)
        footer.addWidget(btn_cancel)
        footer.addWidget(btn_apply)
        layout.addLayout(footer)

    def _on_apply(self):
        source_label, target_label = self.get_values()
        if not source_label or not target_label:
            QMessageBox.warning(self, "Campos incompletos", "Debes seleccionar ambas clases.")
            return
        if source_label == target_label:
            QMessageBox.warning(self, "Sin cambios", "La clase origen y destino son iguales.")
            return
        self.accept()

    def get_values(self):
        source_label = self.cmb_source.currentText().strip()
        target_label = self.cmb_target.currentText().strip()
        return source_label, target_label

