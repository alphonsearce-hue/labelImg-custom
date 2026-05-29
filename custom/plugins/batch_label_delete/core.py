# =============================================================================
# custom/plugins/batch_label_delete/core.py
# =============================================================================
# PROPÓSITO:
#   Permite seleccionar una o varias etiquetas y borrarlas de un rango de
#   imágenes, ya sea:
#     • Desde la imagen actual hacia adelante N imágenes.
#     • Desde la imagen X hasta la imagen Y (rango libre).
#
#   El procesamiento se hace directamente sobre los archivos de anotación
#   en disco (XML / TXT / JSON) sin cargar cada imagen en la UI,
#   y corre en un hilo secundario para no bloquear la interfaz.
#
# INSTALACIÓN:
#   custom/plugins/batch_label_delete/
#       __init__.py   (vacío)
#       core.py       (este archivo)
#
# ACCESO:
#   Menú Editar → "🗑  Borrado masivo por rango..."   (Ctrl+Shift+D)
# =============================================================================

import os
import json
import xml.etree.ElementTree as ET

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QAction, QDialog, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QProgressBar, QRadioButton, QSpinBox, QVBoxLayout,
)
from PyQt5.QtGui import QColor

__version__ = "1.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# Estilo global del plugin (dark + acento verde #7ed957)
# ─────────────────────────────────────────────────────────────────────────────
_QSS = """
QDialog {
    background-color: #0d0d14;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLabel {
    color: #cdd6f4;
    font-size: 13px;
}
QLabel#lbl_title {
    color: #7ed957;
    font-size: 16px;
    font-weight: bold;
    padding: 4px 0;
}
QLabel#lbl_preview {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 12px;
    color: #a6e3a1;
    line-height: 1.6;
}
QLabel#lbl_hint {
    color: #6c7086;
    font-size: 11px;
    font-weight: normal;
}
QGroupBox {
    color: #89dceb;
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: bold;
    font-size: 13px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #89dceb;
}
QListWidget {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px;
    font-size: 13px;
    outline: none;
}
QListWidget::item {
    padding: 6px 10px;
    border-radius: 4px;
}
QListWidget::item:hover {
    background-color: #313244;
}
QListWidget::item:selected {
    background-color: #7ed957;
    color: #0d0d14;
    font-weight: bold;
}
QRadioButton {
    color: #cdd6f4;
    padding: 5px 2px;
    font-size: 13px;
}
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 2px solid #7ed957;
    border-radius: 7px;
    background-color: #1e1e2e;
}
QRadioButton::indicator:checked {
    background-color: #7ed957;
}
QSpinBox {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 6px 10px;
    font-size: 13px;
    min-width: 68px;
}
QSpinBox:disabled {
    color: #45475a;
    border-color: #313244;
}
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #313244;
    border-radius: 3px;
    width: 18px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #45475a;
}
QProgressBar {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 6px;
    text-align: center;
    color: #cdd6f4;
    height: 20px;
    font-size: 11px;
}
QProgressBar::chunk {
    background-color: #7ed957;
    border-radius: 5px;
}
QPushButton {
    background-color: #1e1e2e;
    color: #7ed957;
    border: 1px solid #7ed957;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 13px;
    min-width: 110px;
}
QPushButton:hover {
    background-color: #7ed957;
    color: #0d0d14;
}
QPushButton:disabled {
    color: #45475a;
    border-color: #313244;
    background-color: #1e1e2e;
}
QPushButton#btn_sel_all, QPushButton#btn_desel {
    min-width: 0;
    padding: 5px 10px;
    font-size: 11px;
    border-color: #45475a;
    color: #a6adc8;
}
QPushButton#btn_sel_all:hover, QPushButton#btn_desel:hover {
    background-color: #45475a;
    color: #cdd6f4;
}
QPushButton#btn_cancel {
    color: #f38ba8;
    border-color: #f38ba8;
}
QPushButton#btn_cancel:hover {
    background-color: #f38ba8;
    color: #0d0d14;
}
QPushButton#btn_exec {
    color: #fab387;
    border-color: #fab387;
}
QPushButton#btn_exec:hover {
    background-color: #fab387;
    color: #0d0d14;
}
QFrame[frameShape="4"] {
    color: #313244;
    max-height: 1px;
}
"""


# =============================================================================
# Lógica de edición de archivos de anotación (sin cargar imágenes)
# =============================================================================

class AnnotationEditor:
    """Lee y reescribe archivos de anotación eliminando cajas que coincidan en IoU."""

    XML_EXT  = ".xml"
    TXT_EXT  = ".txt"
    JSON_EXT = ".json"

    @staticmethod
    def find_annotation(img_path: str, save_dir: str | None):
        """
        Devuelve (ann_path, fmt_str) o (None, None).
        Replica la lógica de show_bounding_box_from_annotation_file.
        """
        basename = os.path.splitext(os.path.basename(img_path))[0]

        if save_dir:
            candidates = [
                (os.path.join(save_dir, basename + AnnotationEditor.XML_EXT),  "xml"),
                (os.path.join(save_dir, basename + AnnotationEditor.TXT_EXT),  "yolo"),
                (os.path.join(save_dir, basename + AnnotationEditor.JSON_EXT), "json"),
            ]
        else:
            base = os.path.splitext(img_path)[0]
            candidates = [
                (base + AnnotationEditor.XML_EXT,  "xml"),
                (base + AnnotationEditor.TXT_EXT,  "yolo"),
                (base + AnnotationEditor.JSON_EXT, "json"),
            ]

        for path, fmt in candidates:
            if os.path.isfile(path):
                return path, fmt
        return None, None

    @staticmethod
    def get_iou(boxA, boxB):
        # Determine the (x, y)-coordinates of the intersection rectangle
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        # Compute the area of intersection rectangle
        interWidth = max(0.0, xB - xA)
        interHeight = max(0.0, yB - yA)
        interArea = interWidth * interHeight

        # Compute the area of both the prediction and ground-truth rectangles
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

        # Compute the intersection over union
        unionArea = boxAArea + boxBArea - interArea
        if unionArea == 0:
            return 0.0
        return interArea / unionArea

    # ── Pascal VOC XML ────────────────────────────────────────────────────────
    @staticmethod
    def remove_from_xml(xml_path: str, selected_boxes: list) -> int:
        """Elimina elementos <object> si tienen alta coincidencia de IoU con alguna de las selected_boxes."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            to_remove = []
            for obj in root.findall("object"):
                name = obj.find("name")
                label = name.text if name is not None else ""
                
                bndbox = obj.find("bndbox")
                if bndbox is None:
                    continue
                
                try:
                    xmin = float(bndbox.find("xmin").text)
                    ymin = float(bndbox.find("ymin").text)
                    xmax = float(bndbox.find("xmax").text)
                    ymax = float(bndbox.find("ymax").text)
                except (ValueError, TypeError):
                    continue
                
                boxB = (xmin, ymin, xmax, ymax)
                
                # Buscar si coincide con alguna de las selected_boxes (mismo label + alto IoU)
                matched = False
                for sel in selected_boxes:
                    if sel['label'] == label:
                        iou = AnnotationEditor.get_iou(sel['pixel'], boxB)
                        if iou >= 0.8:
                            matched = True
                            break
                
                if matched:
                    to_remove.append(obj)
            
            for obj in to_remove:
                root.remove(obj)
                
            if to_remove:
                tree.write(xml_path, encoding="utf-8", xml_declaration=True)
            return len(to_remove)
        except Exception as exc:
            print(f"[batch_label_delete] XML error en {xml_path}: {exc}")
            return 0

    # ── YOLO TXT ──────────────────────────────────────────────────────────────
    @staticmethod
    def remove_from_yolo(txt_path: str, selected_boxes: list, label_hist: list) -> int:
        """
        Elimina líneas del archivo YOLO si coinciden en clase y tienen alto IoU (en espacio normalizado)
        con alguna de las selected_boxes.
        """
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            kept, removed = [], 0
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 5:
                    try:
                        class_id = int(parts[0])
                        label = label_hist[class_id] if class_id < len(label_hist) else ""
                        
                        x_center = float(parts[1])
                        y_center = float(parts[2])
                        width    = float(parts[3])
                        height   = float(parts[4])
                        
                        xmin_norm = x_center - width / 2.0
                        ymin_norm = y_center - height / 2.0
                        xmax_norm = x_center + width / 2.0
                        ymax_norm = y_center + height / 2.0
                        boxB_norm = (xmin_norm, ymin_norm, xmax_norm, ymax_norm)
                        
                        # Buscar coincidencia
                        matched = False
                        for sel in selected_boxes:
                            if sel['label'] == label:
                                iou = AnnotationEditor.get_iou(sel['norm'], boxB_norm)
                                if iou >= 0.8:
                                    matched = True
                                    break
                        
                        if matched:
                            removed += 1
                            continue
                    except (ValueError, IndexError):
                        pass
                kept.append(line)

            if removed:
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.writelines(kept)
            return removed
        except Exception as exc:
            print(f"[batch_label_delete] YOLO error en {txt_path}: {exc}")
            return 0

    # ── CreateML JSON ─────────────────────────────────────────────────────────
    @staticmethod
    def remove_from_json(json_path: str, img_path: str, selected_boxes: list) -> int:
        """Elimina anotaciones de CreateML JSON si coinciden con las selected_boxes usando IoU."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            img_name = os.path.basename(img_path)
            removed = 0

            for entry in data:
                if entry.get("image") == img_name:
                    before = entry.get("annotations", [])
                    after  = []
                    for ann in before:
                        label = ann.get("label", "")
                        coords = ann.get("coordinates", {})
                        
                        try:
                            x_center = float(coords.get("x", 0))
                            y_center = float(coords.get("y", 0))
                            width    = float(coords.get("width", 0))
                            height   = float(coords.get("height", 0))
                        except (ValueError, TypeError):
                            after.append(ann)
                            continue
                        
                        xmin = x_center - width / 2.0
                        ymin = y_center - height / 2.0
                        xmax = x_center + width / 2.0
                        ymax = y_center + height / 2.0
                        boxB = (xmin, ymin, xmax, ymax)
                        
                        # Buscar coincidencia
                        matched = False
                        for sel in selected_boxes:
                            if sel['label'] == label:
                                iou = AnnotationEditor.get_iou(sel['pixel'], boxB)
                                if iou >= 0.8:
                                    matched = True
                                    break
                        
                        if matched:
                            removed += 1
                        else:
                            after.append(ann)
                            
                    entry["annotations"] = after

            if removed:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            return removed
        except Exception as exc:
            print(f"[batch_label_delete] JSON error en {json_path}: {exc}")
            return 0

    # ── Dispatcher ────────────────────────────────────────────────────────────
    @classmethod
    def process_image(cls, img_path: str, selected_boxes: list,
                      label_hist: list, save_dir) -> int:
        ann_path, fmt = cls.find_annotation(img_path, save_dir)
        if ann_path is None:
            return 0
        if fmt == "xml":
            return cls.remove_from_xml(ann_path, selected_boxes)
        if fmt == "yolo":
            return cls.remove_from_yolo(ann_path, selected_boxes, label_hist)
        if fmt == "json":
            return cls.remove_from_json(ann_path, img_path, selected_boxes)
        return 0


# =============================================================================
# Hilo de trabajo (no bloquea la UI)
# =============================================================================

class _WorkerThread(QThread):
    sig_progress = pyqtSignal(int, str)    # (porcentaje, mensaje)
    sig_done     = pyqtSignal(int, int)    # (imágenes procesadas, total removidos)

    def __init__(self, img_paths, selected_boxes, label_hist, save_dir):
        super().__init__()
        self.img_paths      = img_paths
        self.selected_boxes = selected_boxes
        self.label_hist     = label_hist
        self.save_dir       = save_dir

    def run(self):
        total   = len(self.img_paths)
        removed = 0
        for i, path in enumerate(self.img_paths):
            self.sig_progress.emit(
                int(i / total * 100),
                f"({i + 1}/{total})  {os.path.basename(path)}"
            )
            removed += AnnotationEditor.process_image(
                path, self.selected_boxes, self.label_hist, self.save_dir
            )
        self.sig_progress.emit(100, "Finalizado")
        self.sig_done.emit(total, removed)


# =============================================================================
# Diálogo principal
# =============================================================================

class BatchDeleteDialog(QDialog):

    def __init__(self, parent, img_list, cur_idx, label_hist, save_dir):
        super().__init__(parent)
        self.mw         = parent
        self.label_hist = label_hist
        self.save_dir   = save_dir
        self._worker    = None

        self.setWindowTitle("Borrado Masivo de Etiquetas")
        self.setMinimumSize(660, 600)
        self.setStyleSheet(_QSS)
        
        # Comportamiento No Modal
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self._build_ui()
        self._on_mode_changed()   # estado inicial de spinboxes
        
        # Conectar señales dinámicas del lienzo y de cambio de imagen
        self.mw.canvas.selectionChanged.connect(self._on_canvas_selection_changed)
        self.mw.file_list_widget.itemSelectionChanged.connect(self._on_image_changed)
        
        # Cargar etiquetas de la selección actual de forma dinámica
        self._update_labels_list()

    # ─────────────────────────────────────────────────────────────────
    # Construcción de la UI
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        # Título
        lbl_title = QLabel("🗑  Borrado Masivo de Etiquetas")
        lbl_title.setObjectName("lbl_title")
        root.addWidget(lbl_title)

        root.addWidget(self._hline())

        # ── Cuerpo: dos columnas ──────────────────────────────────────
        cols = QHBoxLayout()
        cols.setSpacing(16)
        cols.addWidget(self._build_labels_panel(), stretch=1)
        cols.addWidget(self._build_range_panel(),  stretch=1)
        root.addLayout(cols)

        root.addWidget(self._hline())

        # Preview
        self.lbl_preview = QLabel("Selecciona etiquetas y un rango.")
        self.lbl_preview.setObjectName("lbl_preview")
        self.lbl_preview.setWordWrap(True)
        self.lbl_preview.setMinimumHeight(54)
        root.addWidget(self.lbl_preview)

        # Barra de progreso (oculta hasta ejecutar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        self.lbl_prog_msg = QLabel("")
        self.lbl_prog_msg.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.lbl_prog_msg.setVisible(False)
        root.addWidget(self.lbl_prog_msg)

        # Botones
        row_btns = QHBoxLayout()
        row_btns.addStretch()

        btn_cancel = QPushButton("✕  Cancelar")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self.reject)

        self.btn_exec = QPushButton("🗑  Ejecutar borrado")
        self.btn_exec.setObjectName("btn_exec")
        self.btn_exec.setEnabled(False)
        self.btn_exec.clicked.connect(self._execute)

        row_btns.addWidget(btn_cancel)
        row_btns.addWidget(self.btn_exec)
        root.addLayout(row_btns)

    def _build_labels_panel(self):
        grp = QGroupBox("Etiquetas a eliminar")
        v   = QVBoxLayout(grp)
        v.setSpacing(8)

        self.lbl_hint = QLabel("Etiquetas detectadas de la selección actual")
        self.lbl_hint.setObjectName("lbl_hint")
        v.addWidget(self.lbl_hint)

        # Lista de etiquetas
        self.list_labels = QListWidget()
        self.list_labels.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_labels.setMinimumHeight(220)
        self.list_labels.itemSelectionChanged.connect(self._update_preview)
        v.addWidget(self.list_labels)

        # Mini-botones selección
        row = QHBoxLayout()
        btn_all = QPushButton("✔ Selec. todo")
        btn_all.setObjectName("btn_sel_all")
        btn_all.clicked.connect(self.list_labels.selectAll)
        btn_non = QPushButton("✕ Limpiar")
        btn_non.setObjectName("btn_desel")
        btn_non.clicked.connect(self.list_labels.clearSelection)
        row.addWidget(btn_all)
        row.addWidget(btn_non)
        row.addStretch()
        v.addLayout(row)
        return grp

    def _build_range_panel(self):
        total = len(self.mw.m_img_list)
        cur_idx = self.mw.cur_img_idx
        grp   = QGroupBox("Rango de imágenes")
        v     = QVBoxLayout(grp)
        v.setSpacing(10)

        # ── Opción A: desde actual hacia adelante ─────────────────────
        self.rb_forward = QRadioButton("Desde imagen actual  →  N imágenes adelante")
        self.rb_forward.setChecked(True)
        v.addWidget(self.rb_forward)

        row_a = QHBoxLayout()
        row_a.setContentsMargins(20, 0, 0, 0)
        lbl_cant = QLabel("Cantidad:")
        lbl_cant.setStyleSheet("color:#a6adc8;")
        self.spin_fwd = QSpinBox()
        self.spin_fwd.setMinimum(1)
        self.spin_fwd.setMaximum(max(1, total - cur_idx))
        self.spin_fwd.setValue(min(10, max(1, total - cur_idx)))
        self.spin_fwd.setSuffix("  img")
        self.spin_fwd.valueChanged.connect(self._update_preview)
        row_a.addWidget(lbl_cant)
        row_a.addWidget(self.spin_fwd)
        row_a.addStretch()
        v.addLayout(row_a)

        v.addWidget(self._hline())

        # ── Opción B: rango libre ─────────────────────────────────────
        self.rb_range = QRadioButton("Rango personalizado  (imagen # a imagen #)")
        v.addWidget(self.rb_range)

        row_b1 = QHBoxLayout()
        row_b1.setContentsMargins(20, 0, 0, 0)
        lbl_desde = QLabel("Desde:")
        lbl_desde.setStyleSheet("color:#a6adc8;")
        self.spin_from = QSpinBox()
        self.spin_from.setMinimum(1)
        self.spin_from.setMaximum(total)
        self.spin_from.setValue(cur_idx + 1)
        self.spin_from.valueChanged.connect(self._clamp_range)
        self.spin_from.valueChanged.connect(self._update_preview)
        row_b1.addWidget(lbl_desde)
        row_b1.addWidget(self.spin_from)
        row_b1.addStretch()
        v.addLayout(row_b1)

        row_b2 = QHBoxLayout()
        row_b2.setContentsMargins(20, 0, 0, 0)
        lbl_hasta = QLabel("Hasta:")
        lbl_hasta.setStyleSheet("color:#a6adc8;")
        self.spin_to = QSpinBox()
        self.spin_to.setMinimum(1)
        self.spin_to.setMaximum(total)
        self.spin_to.setValue(min(cur_idx + 10, total))
        self.spin_to.valueChanged.connect(self._clamp_range)
        self.spin_to.valueChanged.connect(self._update_preview)
        row_b2.addWidget(lbl_hasta)
        row_b2.addWidget(self.spin_to)
        row_b2.addStretch()
        v.addLayout(row_b2)

        # Indicador de total
        self.lbl_total = QLabel(f"Total de imágenes en el directorio: {total}")
        self.lbl_total.setObjectName("lbl_hint")
        v.addWidget(self.lbl_total)

        # Conectar radios
        self.rb_forward.toggled.connect(self._on_mode_changed)
        self.rb_range.toggled.connect(self._on_mode_changed)

        v.addStretch()
        return grp

    # ─────────────────────────────────────────────────────────────────
    # Lógica de estado y actualización dinámica
    # ─────────────────────────────────────────────────────────────────

    def get_selected_labels(self) -> list:
        labels = []
        shapes = []
        if hasattr(self.mw.canvas, 'selected_shapes') and self.mw.canvas.selected_shapes:
            shapes = self.mw.canvas.selected_shapes
        elif getattr(self.mw.canvas, 'selected_shape', None):
            shapes = [self.mw.canvas.selected_shape]
        
        for s in shapes:
            if s.label and s.label not in labels:
                labels.append(s.label)
        return labels

    def _update_labels_list(self):
        self.list_labels.blockSignals(True)
        self.list_labels.clear()
        selected_labels = self.get_selected_labels()
        
        if not selected_labels:
            item = QListWidgetItem("  [Ninguna etiqueta seleccionada]")
            item.setData(Qt.UserRole, None)
            item.setFlags(Qt.NoItemFlags) # Deshabilitado
            self.list_labels.addItem(item)
        else:
            for lbl in selected_labels:
                item = QListWidgetItem(f"  {lbl}")
                item.setData(Qt.UserRole, lbl)
                self.list_labels.addItem(item)
                item.setSelected(True)
        
        self.list_labels.blockSignals(False)
        self._update_preview()

    def _on_canvas_selection_changed(self, selected=False):
        self._update_labels_list()

    def _on_image_changed(self):
        total = len(self.mw.m_img_list)
        cur_idx = self.mw.cur_img_idx
        
        self.spin_fwd.blockSignals(True)
        self.spin_fwd.setMaximum(max(1, total - cur_idx))
        self.spin_fwd.setValue(min(self.spin_fwd.value(), max(1, total - cur_idx)))
        self.spin_fwd.blockSignals(False)
        
        self.spin_from.blockSignals(True)
        self.spin_from.setMaximum(total)
        self.spin_from.setValue(cur_idx + 1)
        self.spin_from.blockSignals(False)
        
        self.spin_to.blockSignals(True)
        self.spin_to.setMaximum(total)
        self.spin_to.setValue(min(cur_idx + 10, total))
        self.spin_to.blockSignals(False)
        
        self.lbl_total.setText(f"Total de imágenes en el directorio: {total}")
        self._update_preview()

    def cleanup(self):
        try:
            self.mw.canvas.selectionChanged.disconnect(self._on_canvas_selection_changed)
        except Exception:
            pass
        try:
            self.mw.file_list_widget.itemSelectionChanged.disconnect(self._on_image_changed)
        except Exception:
            pass
        if hasattr(self.mw, '_batch_label_delete') and self.mw._batch_label_delete.dialog == self:
            self.mw._batch_label_delete.dialog = None

    def accept(self):
        self.cleanup()
        super().accept()

    def reject(self):
        self.cleanup()
        super().reject()

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

    def _hline(self):
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        return f

    def _on_mode_changed(self):
        fwd = self.rb_forward.isChecked()
        self.spin_fwd.setEnabled(fwd)
        self.spin_from.setEnabled(not fwd)
        self.spin_to.setEnabled(not fwd)
        self._update_preview()

    def _clamp_range(self):
        """spin_to siempre >= spin_from."""
        if self.spin_to.value() < self.spin_from.value():
            self.spin_to.blockSignals(True)
            self.spin_to.setValue(self.spin_from.value())
            self.spin_to.blockSignals(False)

    def _selected_labels(self) -> list:
        return [item.data(Qt.UserRole) for item in self.list_labels.selectedItems() if item.data(Qt.UserRole) is not None]

    def _image_range(self) -> list:
        img_list = self.mw.m_img_list
        cur_idx = self.mw.cur_img_idx
        total = len(img_list)
        if self.rb_forward.isChecked():
            start = cur_idx
            end   = min(cur_idx + self.spin_fwd.value(), total)
        else:
            start = max(0, self.spin_from.value() - 1)
            end   = min(self.spin_to.value(), total)
            if end <= start:
                end = start + 1
        return img_list[start:end]

    # ─────────────────────────────────────────────────────────────────
    # Preview dinámico
    # ─────────────────────────────────────────────────────────────────

    def _update_preview(self):
        labels = self._selected_labels()
        imgs   = self._image_range()

        if not labels:
            self.lbl_preview.setText(
                "⚠  Selecciona al menos una etiqueta en la imagen."
            )
            self.btn_exec.setEnabled(False)
            return

        if not imgs:
            self.lbl_preview.setText(
                "⚠  El rango no contiene imágenes válidas."
            )
            self.btn_exec.setEnabled(False)
            return

        # Etiquetas visibles (máx. 4 + "y N más")
        visible = [f"<b style='color:#7ed957'>{l}</b>" for l in labels[:4]]
        if len(labels) > 4:
            visible.append(f"<span style='color:#6c7086'>y {len(labels)-4} más</span>")
        labels_html = ", ".join(visible)

        # Rango de nombres
        first = os.path.basename(imgs[0])
        last  = os.path.basename(imgs[-1])
        range_str = (
            f"<b>{first}</b>"
            if len(imgs) == 1
            else f"<b>{first}</b>  →  <b>{last}</b>"
        )

        # ¿Afecta imagen actual?
        current_affected = (
            self.mw.file_path in imgs
        ) if self.mw.file_path else False

        note = (
            "<br><span style='color:#fab387; font-size:11px;'>"
            "⚡ La imagen actual está en el rango y se recargará al terminar."
            "</span>"
            if current_affected else ""
        )

        self.lbl_preview.setText(
            f"Etiquetas: {labels_html}<br>"
            f"Imágenes afectadas: <b>{len(imgs)}</b>  —  {range_str}"
            f"{note}"
        )
        self.btn_exec.setEnabled(True)

    # ─────────────────────────────────────────────────────────────────
    # Ejecución
    # ─────────────────────────────────────────────────────────────────

    def _execute(self):
        # 1. Obtener shapes seleccionadas en el lienzo
        selected_shapes = []
        if hasattr(self.mw.canvas, 'selected_shapes') and self.mw.canvas.selected_shapes:
            selected_shapes = self.mw.canvas.selected_shapes
        elif getattr(self.mw.canvas, 'selected_shape', None):
            selected_shapes = [self.mw.canvas.selected_shape]

        if not selected_shapes:
            QMessageBox.warning(self, "Sin selección", "No hay ninguna caja seleccionada en el lienzo.")
            return

        # 2. Calcular coordenadas (píxeles y normalizadas) para cada shape seleccionada
        # Obtener dimensiones de la imagen actual
        w = float(self.mw.image.width()) if (self.mw.image and not self.mw.image.isNull()) else 1.0
        h = float(self.mw.image.height()) if (self.mw.image and not self.mw.image.isNull()) else 1.0

        # Filtrar seleccionadas basándose en las que están seleccionadas en list_labels
        active_labels = set(self._selected_labels())

        selected_boxes = []
        for s in selected_shapes:
            if not s.label or s.label not in active_labels:
                continue
            xs = [p.x() for p in s.points]
            ys = [p.y() for p in s.points]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            
            selected_boxes.append({
                'label': s.label,
                'pixel': (xmin, ymin, xmax, ymax),
                'norm': (xmin / w, ymin / h, xmax / w, ymax / h)
            })

        imgs = self._image_range()
        if not selected_boxes or not imgs:
            return

        # Confirmación clara antes de modificar disco
        detail = "\n".join(f"  • {sel['label']} {[int(c) for c in sel['pixel']]}" for sel in selected_boxes)
        reply  = QMessageBox.warning(
            self,
            "Confirmar borrado masivo por coordenadas",
            f"¿Eliminar las siguientes {len(selected_boxes)} caja(s) de {len(imgs)} imagen(es) basado en sus coordenadas?\n\n"
            f"{detail}\n\n"
            "Solo se eliminarán las cajas en las otras imágenes que coincidan en posición y clase con las seleccionadas.\n"
            "Esta acción no se puede deshacer.\n\n"
            "¿Continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Bloquear UI
        self.btn_exec.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_prog_msg.setVisible(True)
        self.progress_bar.setValue(0)

        # Worker en hilo secundario
        self._worker = _WorkerThread(
            img_paths      = imgs,
            selected_boxes = selected_boxes,
            label_hist     = list(self.mw.label_hist),
            save_dir       = self.save_dir,
        )
        self._worker.sig_progress.connect(self._on_progress)
        self._worker.sig_done.connect(self._on_done)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.lbl_prog_msg.setText(msg)

    def _on_done(self, n_imgs: int, n_removed: int):
        self.progress_bar.setValue(100)
        self.lbl_prog_msg.setText(
            f"✔  Listo — {n_removed} anotación(es) eliminadas en {n_imgs} imagen(es)."
        )

        QMessageBox.information(
            self,
            "Borrado completado",
            f"Proceso finalizado correctamente.\n\n"
            f"  • Imágenes procesadas : {n_imgs}\n"
            f"  • Anotaciones borradas : {n_removed}",
        )

        # Recargar imagen actual si el archivo cambió
        if self.mw.file_path:
            self.mw.load_file(self.mw.file_path)

        self.accept()


# =============================================================================
# Plugin wrapper + punto de entrada
# =============================================================================

class BatchLabelDeletePlugin:

    def __init__(self, main_window):
        self.mw = main_window
        self.dialog = None
        self._register_menu()
        print(f"[batch_label_delete] v{__version__} cargado  (Ctrl+Shift+D)")

    def _register_menu(self):
        menu_edit = self.mw.menus.edit
        # Evitar duplicados en recargas en caliente
        for act in menu_edit.actions():
            if getattr(act, "_bld_registered", False):
                return

        menu_edit.addSeparator()
        action = QAction("🗑  Borrado masivo por rango...", self.mw)
        action._bld_registered = True
        action.setShortcut("Ctrl+Shift+D")
        action.triggered.connect(self._open)
        menu_edit.addAction(action)

        # También registramos en el menú contextual del lienzo (click derecho)
        # Evitar duplicados en context menus en recargas en caliente
        has_context_action = False
        for act in self.mw.actions.beginnerContext:
            if act and getattr(act, "_bld_context_registered", False):
                has_context_action = True
                break

        if not has_context_action:
            self.context_action = QAction("🗑  Borrado masivo...", self.mw)
            self.context_action._bld_context_registered = True
            self.context_action.triggered.connect(self._open)

            # Añadir al beginnerContext
            beg_list = list(self.mw.actions.beginnerContext)
            beg_list.append(None) # Separador
            beg_list.append(self.context_action)
            self.mw.actions.beginnerContext = tuple(beg_list)

            # Añadir al advancedContext
            adv_list = list(self.mw.actions.advancedContext)
            adv_list.append(None) # Separador
            adv_list.append(self.context_action)
            self.mw.actions.advancedContext = tuple(adv_list)

            # Repopular para que surta efecto inmediato
            self.mw.populate_mode_actions()

    def _open(self):
        mw = self.mw
        if not mw.m_img_list:
            QMessageBox.warning(
                mw, "Sin imágenes",
                "Abre primero un directorio con imágenes."
            )
            return

        if self.dialog is not None:
            self.dialog.raise_()
            self.dialog.activateWindow()
            return

        self.dialog = BatchDeleteDialog(
            parent     = mw,
            img_list   = mw.m_img_list,
            cur_idx    = mw.cur_img_idx,
            label_hist = list(mw.label_hist),
            save_dir   = mw.default_save_dir,
        )
        self.dialog.show()


def setup(main_window):
    plugin = BatchLabelDeletePlugin(main_window)
    main_window._batch_label_delete = plugin
    return plugin