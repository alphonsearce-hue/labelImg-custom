from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from libs.utils import generate_color_by_text

__version__ = "1.1.0"
__description__ = "Buscar y reemplazar etiquetas de clase en lote con soporte de rangos."

# ─── Constantes de modo ────────────────────────────────────────────────────────
MODE_CURRENT = "current"
MODE_FORWARD = "forward"
MODE_RANGE   = "range"


def setup(main_window):
    plugin = ClassReplaceToolPlugin(main_window)
    main_window._class_replace_tool = plugin
    return plugin


# ══════════════════════════════════════════════════════════════════════════════
#  Plugin principal
# ══════════════════════════════════════════════════════════════════════════════
class ClassReplaceToolPlugin:
    def __init__(self, main_window):
        self.mw = main_window
        self.canvas = main_window.canvas
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        action = QAction("Buscar y reemplazar clase", self.mw)
        action.triggered.connect(self._open_replace_dialog)

        if hasattr(self.mw, "register_plugin_tool"):
            self.mw.register_plugin_tool(
                "class_tools",
                "🔁 Buscar y reemplazar clase",
                self._open_replace_dialog,
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

    # ── Abrir diálogo ─────────────────────────────────────────────────────────
    def _open_replace_dialog(self, _checked=False):
        cur_idx   = getattr(self.mw, "cur_img_idx", 0)
        img_count = len(getattr(self.mw, "m_img_list", []))
        classes   = self._collect_classes()

        dialog = ClassReplaceDialog(self.mw, classes, cur_idx, img_count)
        if not dialog.exec_():
            return

        source_label, target_label, mode, range_data = dialog.get_values()

        if mode == MODE_CURRENT:
            self._replace_current_image(source_label, target_label, show_result=True)

        elif mode == MODE_FORWARD:
            # range_data = N (cantidad de imágenes, incluye la actual)
            start = cur_idx
            end   = min(cur_idx + range_data - 1, img_count - 1)
            self._replace_in_range(source_label, target_label, start, end)

        elif mode == MODE_RANGE:
            # range_data = (start_1based, end_1based)
            start_1, end_1 = range_data
            start = max(0, start_1 - 1)
            end   = min(end_1 - 1, img_count - 1)
            self._replace_in_range(source_label, target_label, start, end)

    # ── Reemplazo imagen actual ───────────────────────────────────────────────
    def _replace_current_image(self, source_label, target_label, show_result=False):
        """Reemplaza en el canvas activo y guarda. Devuelve nº de reemplazos."""
        replaced = 0
        for shape in self.canvas.shapes:
            if shape.label == source_label:
                shape.label = target_label
                replaced += 1

        if replaced == 0:
            if show_result:
                QMessageBox.information(
                    self.mw,
                    "Sin resultados",
                    f"No se encontraron cajas con la clase '{source_label}'.",
                )
            return 0

        # Sincronizar lista de etiquetas del panel derecho
        items_to_shapes = (
            getattr(self.mw, "items_to_shapes", None)
            or getattr(self.mw, "itemsToShapes", {})
        )
        label_list = (
            getattr(self.mw, "label_list", None)
            or getattr(self.mw, "labelList", None)
        )

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

        if show_result:
            QMessageBox.information(
                self.mw,
                "Reemplazo completado",
                f"Se reemplazaron {replaced} caja(s):\n'{source_label}'  →  '{target_label}'.",
            )
        return replaced

    # ── Reemplazo en rango ────────────────────────────────────────────────────
    def _replace_in_range(self, source_label, target_label, start_idx, end_idx):
        """Carga cada imagen del rango, aplica el reemplazo y guarda."""
        img_list = getattr(self.mw, "m_img_list", [])
        if not img_list:
            QMessageBox.warning(self.mw, "Sin imágenes", "No hay imágenes cargadas.")
            return

        # Normalizar orden e índices
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx
        start_idx = max(0, min(start_idx, len(img_list) - 1))
        end_idx   = max(0, min(end_idx,   len(img_list) - 1))

        # Guardar imagen actual si tiene cambios pendientes
        original_path = getattr(self.mw, "file_path", None)
        if getattr(self.mw, "dirty", False):
            self.mw.save_file()

        total           = end_idx - start_idx + 1
        total_replaced  = 0
        images_affected = 0

        progress = QProgressDialog(
            "Iniciando…", "Cancelar", 0, total, self.mw
        )
        progress.setWindowTitle("🔁 Reemplazo en rango")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumWidth(440)
        progress.setStyleSheet(
            """
            QProgressDialog { background-color: #0f0f17; color: #cdd6f4; }
            QLabel           { color: #cdd6f4; font-size: 12px; }
            QPushButton {
                background-color: #1e1e2e; color: #f38ba8;
                border: 1px solid #f38ba8; border-radius: 6px; padding: 6px 14px;
            }
            QProgressBar {
                background: #1e1e2e; border: 1px solid #45475a;
                border-radius: 4px; text-align: center; color: #cdd6f4;
            }
            QProgressBar::chunk { background-color: #7ed957; border-radius: 4px; }
            """
        )
        progress.show()

        for step, idx in enumerate(range(start_idx, end_idx + 1)):
            if progress.wasCanceled():
                break

            filepath = img_list[idx]
            progress.setValue(step)
            progress.setLabelText(
                f"[{step + 1} / {total}]  Imagen {idx + 1}:  {_short_name(filepath)}"
            )
            QApplication.processEvents()

            if not self.mw.load_file(filepath):
                continue

            replaced = self._replace_current_image(
                source_label, target_label, show_result=False
            )

            if replaced > 0:
                self.mw.save_file()
                total_replaced  += replaced
                images_affected += 1

        progress.setValue(total)
        progress.close()

        # Restaurar imagen original
        if original_path:
            self.mw.load_file(original_path)

        QMessageBox.information(
            self.mw,
            "✅ Reemplazo en rango completado",
            (
                f"<b>Resultado:</b><br>"
                f"• <b>{total_replaced}</b> etiqueta(s) reemplazada(s)<br>"
                f"• <b>{images_affected}</b> imagen(es) modificada(s)<br>"
                f"• Rango procesado: imagen <b>{start_idx + 1}</b>"
                f" → <b>{end_idx + 1}</b><br><br>"
                f"<code>{source_label}</code>  →  <code>{target_label}</code>"
            ),
        )

    # ── Utilidades ────────────────────────────────────────────────────────────
    def _collect_classes(self):
        classes = list(getattr(self.mw, "label_hist", []))
        for shape in self.canvas.shapes:
            if shape.label:
                classes.append(shape.label)
        return sorted(set(classes))


# ══════════════════════════════════════════════════════════════════════════════
#  Diálogo
# ══════════════════════════════════════════════════════════════════════════════
class ClassReplaceDialog(QDialog):
    STYLESHEET = """
    QDialog          { background-color: #0f0f17; color: #cdd6f4; }
    QLabel           { color: #e6e9ef; font-size: 13px; font-weight: bold; }
    QRadioButton     { color: #cdd6f4; padding: 4px 2px; font-size: 12px; }
    QComboBox {
        background-color: #1e1e2e; color: #ffffff;
        border: 1px solid #45475a; padding: 8px; border-radius: 4px;
    }
    QSpinBox {
        background-color: #1e1e2e; color: #ffffff;
        border: 1px solid #45475a; padding: 6px; border-radius: 4px;
        min-width: 72px;
    }
    QSpinBox::up-button, QSpinBox::down-button { width: 20px; }
    QPushButton {
        background-color: #1e1e2e; color: #89dceb;
        border: 1px solid #89dceb; border-radius: 6px;
        padding: 10px 18px; font-weight: bold;
    }
    QPushButton:hover  { background-color: #89dceb; color: #11111b; }
    QPushButton#btn_apply { color: #a6e3a1; border-color: #a6e3a1; }
    QPushButton#btn_apply:hover { background-color: #a6e3a1; color: #11111b; }
    """

    def __init__(self, parent, classes, cur_idx, img_count):
        super().__init__(parent)
        self._classes   = classes or []
        self._cur_idx   = cur_idx          # 0-based
        self._img_count = img_count
        self._cur_num   = cur_idx + 1      # 1-based para el usuario

        self.setWindowTitle("Reemplazar Clases")
        self.setMinimumWidth(530)
        self.setStyleSheet(self.STYLESHEET)
        self._build_ui()
        self._refresh_preview()

    # ── Construcción UI ───────────────────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(11)

        # Título
        title = QLabel("🔁 Buscar y reemplazar clases")
        title.setStyleSheet("font-size: 17px; color: #f5c2e7; font-weight: bold;")
        layout.addWidget(title)

        layout.addWidget(_hline())

        # ─ Clase origen / destino
        layout.addWidget(QLabel("🏷️  Clase origen (buscar):"))
        self.cmb_source = QComboBox()
        self.cmb_source.addItems(self._classes)
        layout.addWidget(self.cmb_source)

        layout.addWidget(QLabel("🎯  Clase destino (reemplazar por):"))
        self.cmb_target = QComboBox()
        self.cmb_target.setEditable(True)
        self.cmb_target.addItems(self._classes)
        layout.addWidget(self.cmb_target)

        layout.addWidget(_hline())

        # ─ Sección de rango
        lbl_range = QLabel("📐  Rango de aplicación:")
        lbl_range.setStyleSheet("color: #cba6f7; font-size: 13px; font-weight: bold;")
        layout.addWidget(lbl_range)

        self._mode_group = QButtonGroup(self)

        # Opción 1 — Solo imagen actual
        self.rb_current = QRadioButton(
            f"Solo imagen actual  (imagen {self._cur_num} de {self._img_count})"
        )
        self.rb_current.setChecked(True)
        self._mode_group.addButton(self.rb_current, 0)
        layout.addWidget(self.rb_current)

        # Opción 2 — Imagen actual + N hacia adelante
        row_fwd = QHBoxLayout()
        self.rb_forward = QRadioButton("Imagen actual  +")
        self._mode_group.addButton(self.rb_forward, 1)
        row_fwd.addWidget(self.rb_forward)

        self.spn_forward = QSpinBox()
        self.spn_forward.setMinimum(1)
        self.spn_forward.setMaximum(max(1, self._img_count - self._cur_idx))
        self.spn_forward.setValue(min(10, max(1, self._img_count - self._cur_idx)))
        self.spn_forward.setEnabled(False)
        row_fwd.addWidget(self.spn_forward)

        lbl_fwd_s = QLabel("  imágenes hacia adelante")
        lbl_fwd_s.setStyleSheet("font-weight: normal; color: #a6adc8;")
        row_fwd.addWidget(lbl_fwd_s)
        row_fwd.addStretch()
        layout.addLayout(row_fwd)

        # Opción 3 — Rango X a Y
        row_rng = QHBoxLayout()
        self.rb_range = QRadioButton("Rango  desde")
        self._mode_group.addButton(self.rb_range, 2)
        row_rng.addWidget(self.rb_range)

        self.spn_start = QSpinBox()
        self.spn_start.setMinimum(1)
        self.spn_start.setMaximum(self._img_count)
        self.spn_start.setValue(self._cur_num)
        self.spn_start.setEnabled(False)
        row_rng.addWidget(self.spn_start)

        lbl_to = QLabel("  hasta")
        lbl_to.setStyleSheet("font-weight: normal; color: #a6adc8;")
        row_rng.addWidget(lbl_to)

        self.spn_end = QSpinBox()
        self.spn_end.setMinimum(1)
        self.spn_end.setMaximum(self._img_count)
        self.spn_end.setValue(min(self._cur_num + 9, self._img_count))
        self.spn_end.setEnabled(False)
        row_rng.addWidget(self.spn_end)

        lbl_total = QLabel(f"  (total: {self._img_count})")
        lbl_total.setStyleSheet("font-weight: normal; color: #585b70;")
        row_rng.addWidget(lbl_total)
        row_rng.addStretch()
        layout.addLayout(row_rng)

        # ─ Preview dinámico
        self.lbl_preview = QLabel("")
        self.lbl_preview.setStyleSheet(
            "color: #7ed957; font-size: 12px; font-weight: normal;"
            "padding: 7px 12px; background: #1e1e2e; border-radius: 6px;"
        )
        layout.addWidget(self.lbl_preview)

        layout.addWidget(_hline())

        # ─ Footer
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

        # ─ Señales
        self.rb_current.toggled.connect(self._on_mode_changed)
        self.rb_forward.toggled.connect(self._on_mode_changed)
        self.rb_range.toggled.connect(self._on_mode_changed)
        self.spn_forward.valueChanged.connect(self._refresh_preview)
        self.spn_start.valueChanged.connect(self._refresh_preview)
        self.spn_end.valueChanged.connect(self._refresh_preview)

    # ── Lógica de modo ────────────────────────────────────────────────────────
    def _on_mode_changed(self):
        is_fwd   = self.rb_forward.isChecked()
        is_range = self.rb_range.isChecked()
        self.spn_forward.setEnabled(is_fwd)
        self.spn_start.setEnabled(is_range)
        self.spn_end.setEnabled(is_range)
        self._refresh_preview()

    def _refresh_preview(self):
        if self.rb_current.isChecked():
            txt = f"✦ Aplicará solo a la imagen actual  ({self._cur_num} / {self._img_count})"

        elif self.rb_forward.isChecked():
            n   = self.spn_forward.value()
            end = min(self._cur_num + n - 1, self._img_count)
            real_n = end - self._cur_num + 1
            txt = (
                f"✦ Aplicará desde imagen {self._cur_num} "
                f"hasta imagen {end}  ({real_n} imagen(es))"
            )

        else:
            s = self.spn_start.value()
            e = self.spn_end.value()
            if s > e:
                s, e = e, s
            txt = (
                f"✦ Aplicará desde imagen {s} "
                f"hasta imagen {e}  ({e - s + 1} imagen(es))"
            )

        self.lbl_preview.setText(txt)

    # ── Validación y aceptación ───────────────────────────────────────────────
    def _on_apply(self):
        source, target = self.get_values()[:2]
        if not source or not target:
            QMessageBox.warning(self, "Campos incompletos", "Debes seleccionar ambas clases.")
            return
        if source == target:
            QMessageBox.warning(self, "Sin cambios", "La clase origen y destino son iguales.")
            return

        # Confirmación extra para rangos grandes (> 50 imágenes)
        if not self.rb_current.isChecked():
            _, _, _, range_data = self.get_values()
            if self.rb_forward.isChecked():
                count = min(range_data, self._img_count - self._cur_idx)
            else:
                s, e = range_data
                count = abs(e - s) + 1

            if count > 50:
                reply = QMessageBox.question(
                    self,
                    "Confirmar operación masiva",
                    f"Estás a punto de modificar <b>{count}</b> archivos de anotación.<br>"
                    f"Esta operación no puede deshacerse fácilmente.<br><br>"
                    f"¿Deseas continuar?",
                    QMessageBox.Yes | QMessageBox.Cancel,
                )
                if reply != QMessageBox.Yes:
                    return

        self.accept()

    def get_values(self):
        """Devuelve (source_label, target_label, mode, range_data)."""
        source = self.cmb_source.currentText().strip()
        target = self.cmb_target.currentText().strip()

        if self.rb_current.isChecked():
            return source, target, MODE_CURRENT, None

        if self.rb_forward.isChecked():
            return source, target, MODE_FORWARD, self.spn_forward.value()

        s = self.spn_start.value()
        e = self.spn_end.value()
        if s > e:
            s, e = e, s
        return source, target, MODE_RANGE, (s, e)


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers internos
# ══════════════════════════════════════════════════════════════════════════════
def _hline():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    return line


def _short_name(path, max_len=55):
    import os
    name = os.path.basename(path)
    return name if len(name) <= max_len else "…" + name[-(max_len - 1):]