# =============================================================================
# custom/plugins/batch_label_edit/core.py
# =============================================================================
# PROPÓSITO:
#   El usuario selecciona cajas individuales en el canvas.
#   Esas cajas aparecen en el panel izquierdo (cada una como ítem individual).
#   Al ejecutar, SOLO esas cajas específicas se renombran en el rango de
#   imágenes, usando IoU >= 0.8 para identificarlas en cada imagen.
#   Las demás cajas de la misma clase NO se modifican.
#
# ACCESO:
#   Menú Editar → "✏  Edición masiva por rango..."  (Ctrl+Shift+E)
#   Clic derecho en el lienzo → "✏  Edición masiva..."
# =============================================================================

import os
import json
import xml.etree.ElementTree as ET

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QAction, QComboBox, QDialog, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QProgressBar, QRadioButton,
    QSpinBox, QVBoxLayout,
)

__version__ = "2.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# Estilo global (dark + acento azul #89b4fa)
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
    color: #89b4fa;
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
    padding: 5px 10px;
    border-radius: 4px;
}
QListWidget::item:hover {
    background-color: #313244;
}
QListWidget::item:selected {
    background-color: #89b4fa;
    color: #0d0d14;
    font-weight: bold;
}
QRadioButton {
    color: #cdd6f4;
    padding: 5px 2px;
    font-size: 13px;
}
QRadioButton::indicator {
    width: 14px; height: 14px;
    border: 2px solid #89b4fa;
    border-radius: 7px;
    background-color: #1e1e2e;
}
QRadioButton::indicator:checked { background-color: #89b4fa; }
QSpinBox {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 6px 10px;
    font-size: 13px;
    min-width: 68px;
}
QSpinBox:disabled { color: #45475a; border-color: #313244; }
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #313244; border-radius: 3px; width: 18px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: #45475a; }
QComboBox {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 6px 10px;
    font-size: 13px;
    min-width: 140px;
}
QComboBox:disabled { color: #45475a; border-color: #313244; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    selection-background-color: #89b4fa;
    selection-color: #0d0d14;
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
QProgressBar::chunk { background-color: #89b4fa; border-radius: 5px; }
QPushButton {
    background-color: #1e1e2e;
    color: #89b4fa;
    border: 1px solid #89b4fa;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 13px;
    min-width: 110px;
}
QPushButton:hover { background-color: #89b4fa; color: #0d0d14; }
QPushButton:disabled { color: #45475a; border-color: #313244; background-color: #1e1e2e; }
QPushButton#btn_sel_all, QPushButton#btn_desel {
    min-width: 0; padding: 5px 10px; font-size: 11px;
    border-color: #45475a; color: #a6adc8;
}
QPushButton#btn_sel_all:hover, QPushButton#btn_desel:hover {
    background-color: #45475a; color: #cdd6f4;
}
QPushButton#btn_cancel { color: #f38ba8; border-color: #f38ba8; }
QPushButton#btn_cancel:hover { background-color: #f38ba8; color: #0d0d14; }
QPushButton#btn_exec { color: #a6e3a1; border-color: #a6e3a1; }
QPushButton#btn_exec:hover { background-color: #a6e3a1; color: #0d0d14; }
QFrame[frameShape="4"] { color: #313244; max-height: 1px; }
"""


# =============================================================================
# Lógica de edición (match por IoU: solo las cajas seleccionadas)
# =============================================================================

class AnnotationRenamer:
    """Renombra únicamente las cajas que coincidan por IoU >= 0.8
    con las cajas seleccionadas por el usuario."""

    XML_EXT  = ".xml"
    TXT_EXT  = ".txt"
    JSON_EXT = ".json"

    @staticmethod
    def find_annotation(img_path: str, save_dir):
        basename = os.path.splitext(os.path.basename(img_path))[0]
        if save_dir:
            cands = [
                (os.path.join(save_dir, basename + AnnotationRenamer.XML_EXT),  "xml"),
                (os.path.join(save_dir, basename + AnnotationRenamer.TXT_EXT),  "yolo"),
                (os.path.join(save_dir, basename + AnnotationRenamer.JSON_EXT), "json"),
            ]
        else:
            base = os.path.splitext(img_path)[0]
            cands = [
                (base + AnnotationRenamer.XML_EXT,  "xml"),
                (base + AnnotationRenamer.TXT_EXT,  "yolo"),
                (base + AnnotationRenamer.JSON_EXT, "json"),
            ]
        for path, fmt in cands:
            if os.path.isfile(path):
                return path, fmt
        return None, None

    @staticmethod
    def iou(a, b):
        xA, yA = max(a[0], b[0]), max(a[1], b[1])
        xB, yB = min(a[2], b[2]), min(a[3], b[3])
        inter  = max(0.0, xB - xA) * max(0.0, yB - yA)
        aA = (a[2]-a[0]) * (a[3]-a[1])
        aB = (b[2]-b[0]) * (b[3]-b[1])
        uni = aA + aB - inter
        return inter / uni if uni > 0 else 0.0

    # ── Pascal VOC XML ────────────────────────────────────────────────────────
    @staticmethod
    def rename_xml(xml_path: str, boxes: list, new_label: str) -> int:
        """boxes = lista de dict {'label', 'pixel':(xmin,ymin,xmax,ymax)}"""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            changed = 0
            for obj in root.findall("object"):
                name_el = obj.find("name")
                label   = name_el.text if name_el is not None else ""
                bb = obj.find("bndbox")
                if bb is None:
                    continue
                try:
                    boxB = (float(bb.find("xmin").text), float(bb.find("ymin").text),
                            float(bb.find("xmax").text), float(bb.find("ymax").text))
                except (ValueError, TypeError):
                    continue
                for sel in boxes:
                    if sel["label"] == label and AnnotationRenamer.iou(sel["pixel"], boxB) >= 0.8:
                        name_el.text = new_label
                        changed += 1
                        break
            if changed:
                tree.write(xml_path, encoding="utf-8", xml_declaration=True)
            return changed
        except Exception as e:
            print(f"[batch_label_edit] XML error {xml_path}: {e}")
            return 0

    # ── YOLO TXT ──────────────────────────────────────────────────────────────
    @staticmethod
    def rename_yolo(txt_path: str, boxes: list, new_label: str, label_hist: list) -> int:
        """boxes = lista de dict {'label', 'norm':(xmin,ymin,xmax,ymax) normalizado}"""
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            lh = list(label_hist)
            if new_label in lh:
                new_id = lh.index(new_label)
            else:
                new_id = len(lh)
                lh.append(new_label)

            result, changed = [], 0
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 5:
                    try:
                        cid   = int(parts[0])
                        lbl   = lh[cid] if cid < len(lh) else ""
                        xc, yc, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                        boxB  = (xc - w/2, yc - h/2, xc + w/2, yc + h/2)
                        for sel in boxes:
                            if sel["label"] == lbl and AnnotationRenamer.iou(sel["norm"], boxB) >= 0.8:
                                rest = " ".join(parts[1:])
                                line = f"{new_id} {rest}\n"
                                changed += 1
                                break
                    except (ValueError, IndexError):
                        pass
                result.append(line)
            if changed:
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.writelines(result)
            return changed
        except Exception as e:
            print(f"[batch_label_edit] YOLO error {txt_path}: {e}")
            return 0

    # ── CreateML JSON ─────────────────────────────────────────────────────────
    @staticmethod
    def rename_json(json_path: str, img_path: str, boxes: list, new_label: str) -> int:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            img_name = os.path.basename(img_path)
            changed  = 0
            for entry in data:
                if entry.get("image") == img_name:
                    for ann in entry.get("annotations", []):
                        lbl = ann.get("label", "")
                        c   = ann.get("coordinates", {})
                        try:
                            xc, yc, w, h = float(c.get("x",0)), float(c.get("y",0)), \
                                            float(c.get("width",0)), float(c.get("height",0))
                        except (ValueError, TypeError):
                            continue
                        boxB = (xc-w/2, yc-h/2, xc+w/2, yc+h/2)
                        for sel in boxes:
                            if sel["label"] == lbl and AnnotationRenamer.iou(sel["pixel"], boxB) >= 0.8:
                                ann["label"] = new_label
                                changed += 1
                                break
            if changed:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            return changed
        except Exception as e:
            print(f"[batch_label_edit] JSON error {json_path}: {e}")
            return 0

    # ── Dispatcher ────────────────────────────────────────────────────────────
    @classmethod
    def process_image(cls, img_path, boxes, new_label, label_hist, save_dir) -> int:
        ann_path, fmt = cls.find_annotation(img_path, save_dir)
        if ann_path is None:
            return 0
        if fmt == "xml":
            return cls.rename_xml(ann_path, boxes, new_label)
        if fmt == "yolo":
            return cls.rename_yolo(ann_path, boxes, new_label, label_hist)
        if fmt == "json":
            return cls.rename_json(ann_path, img_path, boxes, new_label)
        return 0


# =============================================================================
# Hilo de trabajo
# =============================================================================

class _WorkerThread(QThread):
    sig_progress = pyqtSignal(int, str)
    sig_done     = pyqtSignal(int, int)

    def __init__(self, img_paths, boxes, new_label, label_hist, save_dir):
        super().__init__()
        self.img_paths  = img_paths
        self.boxes      = boxes
        self.new_label  = new_label
        self.label_hist = label_hist
        self.save_dir   = save_dir

    def run(self):
        total = len(self.img_paths)
        changed = 0
        for i, path in enumerate(self.img_paths):
            self.sig_progress.emit(int(i/total*100), f"({i+1}/{total})  {os.path.basename(path)}")
            changed += AnnotationRenamer.process_image(
                path, self.boxes, self.new_label, self.label_hist, self.save_dir)
        self.sig_progress.emit(100, "Finalizado")
        self.sig_done.emit(total, changed)


# =============================================================================
# Diálogo principal
# =============================================================================

class BatchEditDialog(QDialog):

    def __init__(self, parent, label_hist, save_dir):
        super().__init__(parent)
        self.mw         = parent
        self.label_hist = label_hist
        self.save_dir   = save_dir
        self._worker    = None

        # Lista interna de cajas seleccionadas en canvas:
        # cada elemento: {'label': str, 'pixel': tuple, 'norm': tuple, 'display': str}
        self._canvas_boxes = []

        self.setWindowTitle("Edición Masiva de Etiquetas")
        self.setMinimumSize(920, 640)
        self.setStyleSheet(_QSS)
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._build_ui()
        self._on_mode_changed()

        # Señales dinámicas
        self.mw.canvas.selectionChanged.connect(self._on_canvas_selection_changed)
        self.mw.file_list_widget.itemSelectionChanged.connect(self._on_image_changed)

        # Carga inicial
        self._refresh_boxes_from_canvas()

    # ─────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        lbl_title = QLabel("✏  Edición Masiva de Etiquetas")
        lbl_title.setObjectName("lbl_title")
        root.addWidget(lbl_title)
        root.addWidget(self._hline())

        cols = QHBoxLayout()
        cols.setSpacing(16)
        cols.addWidget(self._build_boxes_panel(), stretch=1)

        mid_col = QVBoxLayout()
        mid_col.setSpacing(12)
        mid_col.addWidget(self._build_existing_classes_panel(), stretch=1)
        cols.addLayout(mid_col, stretch=1)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        right_col.addWidget(self._build_range_panel(), stretch=1)
        right_col.addWidget(self._build_new_class_panel())
        cols.addLayout(right_col, stretch=1)
        root.addLayout(cols)

        root.addWidget(self._hline())

        self.lbl_preview = QLabel("Selecciona cajas en el canvas, un rango y la nueva clase.")
        self.lbl_preview.setObjectName("lbl_preview")
        self.lbl_preview.setWordWrap(True)
        self.lbl_preview.setMinimumHeight(54)
        root.addWidget(self.lbl_preview)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        self.lbl_prog_msg = QLabel("")
        self.lbl_prog_msg.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.lbl_prog_msg.setVisible(False)
        root.addWidget(self.lbl_prog_msg)

        row_btns = QHBoxLayout()
        row_btns.addStretch()
        btn_cancel = QPushButton("✕  Cancelar")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self.reject)
        self.btn_exec = QPushButton("✏  Ejecutar edición")
        self.btn_exec.setObjectName("btn_exec")
        self.btn_exec.setEnabled(False)
        self.btn_exec.clicked.connect(self._execute)
        row_btns.addWidget(btn_cancel)
        row_btns.addWidget(self.btn_exec)
        root.addLayout(row_btns)

    def _build_boxes_panel(self):
        """Panel izquierdo: cajas individuales seleccionadas en el canvas."""
        grp = QGroupBox("Etiquetas seleccionadas")
        v   = QVBoxLayout(grp)
        v.setSpacing(8)

        self.lbl_hint_boxes = QLabel("Selecciona cajas en la imagen actual")
        self.lbl_hint_boxes.setObjectName("lbl_hint")
        v.addWidget(self.lbl_hint_boxes)

        self.list_boxes = QListWidget()
        self.list_boxes.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_boxes.setMinimumHeight(220)
        self.list_boxes.itemSelectionChanged.connect(self._update_preview)
        v.addWidget(self.list_boxes)

        row = QHBoxLayout()
        btn_all = QPushButton("✔ Selec. todo")
        btn_all.setObjectName("btn_sel_all")
        btn_all.clicked.connect(self.list_boxes.selectAll)
        btn_non = QPushButton("✕ Limpiar")
        btn_non.setObjectName("btn_desel")
        btn_non.clicked.connect(self.list_boxes.clearSelection)
        row.addWidget(btn_all)
        row.addWidget(btn_non)
        row.addStretch()
        v.addLayout(row)
        return grp

    def _build_range_panel(self):
        total   = len(self.mw.m_img_list)
        cur_idx = self.mw.cur_img_idx
        grp = QGroupBox("Rango de imágenes")
        v   = QVBoxLayout(grp)
        v.setSpacing(10)

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

        self.lbl_total = QLabel(f"Total de imágenes en el directorio: {total}")
        self.lbl_total.setObjectName("lbl_hint")
        v.addWidget(self.lbl_total)

        self.rb_forward.toggled.connect(self._on_mode_changed)
        self.rb_range.toggled.connect(self._on_mode_changed)
        v.addStretch()
        return grp

    def _build_existing_classes_panel(self):
        """Panel central: lista de todas las clases existentes.
        Al hacer clic en una, las etiquetas seleccionadas se renombran a esa clase."""
        grp = QGroupBox("Clases existentes")
        v   = QVBoxLayout(grp)
        v.setSpacing(8)

        lbl_hint = QLabel("Haz clic en una clase para renombrar las etiquetas seleccionadas:")
        lbl_hint.setObjectName("lbl_hint")
        v.addWidget(lbl_hint)

        self.list_classes = QListWidget()
        self.list_classes.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_classes.setMinimumHeight(180)
        self.list_classes.itemClicked.connect(self._on_existing_class_clicked)
        v.addWidget(self.list_classes)

        self._populate_classes_list()
        return grp

    def _populate_classes_list(self):
        """Llena la lista de clases existentes desde label_hist."""
        self.list_classes.blockSignals(True)
        self.list_classes.clear()
        for cls in sorted(set(self.mw.label_hist)):
            self.list_classes.addItem(cls)
        self.list_classes.blockSignals(False)

    def _on_existing_class_clicked(self, item):
        """Al hacer clic en una clase existente, pone esa clase como destino
        en el combo de Nueva clase."""
        class_name = item.text().strip()
        if class_name:
            self.combo_class.setEditText(class_name)

    def _build_new_class_panel(self):
        grp = QGroupBox("Nueva clase")
        v   = QVBoxLayout(grp)
        v.setSpacing(8)

        lbl_hint = QLabel("Selecciona o escribe la clase destino:")
        lbl_hint.setObjectName("lbl_hint")
        v.addWidget(lbl_hint)

        self.combo_class = QComboBox()
        self.combo_class.setEditable(True)
        self.combo_class.setInsertPolicy(QComboBox.NoInsert)
        self.combo_class.lineEdit().setPlaceholderText("Escribe o selecciona una clase…")
        self._populate_combo()
        self.combo_class.setCurrentIndex(-1)  # Iniciar en blanco
        self.combo_class.currentTextChanged.connect(self._update_preview)
        v.addWidget(self.combo_class)
        return grp

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _hline(self):
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        return f

    def _populate_combo(self):
        self.combo_class.blockSignals(True)
        current = self.combo_class.currentText()
        self.combo_class.clear()
        for cls in sorted(set(self.mw.label_hist)):
            self.combo_class.addItem(cls)
        if current:
            idx = self.combo_class.findText(current)
            if idx >= 0:
                self.combo_class.setCurrentIndex(idx)
            else:
                self.combo_class.setEditText(current)
        else:
            self.combo_class.setCurrentIndex(-1)  # Mantener en blanco
        self.combo_class.blockSignals(False)

    def _refresh_boxes_from_canvas(self):
        """Lee las cajas seleccionadas del canvas y llena la lista."""
        # Obtener shapes seleccionadas
        shapes = []
        if hasattr(self.mw.canvas, 'selected_shapes') and self.mw.canvas.selected_shapes:
            shapes = list(self.mw.canvas.selected_shapes)
        elif getattr(self.mw.canvas, 'selected_shape', None):
            shapes = [self.mw.canvas.selected_shape]

        # Dimensiones imagen actual
        w = float(self.mw.image.width())  if (self.mw.image and not self.mw.image.isNull()) else 1.0
        h = float(self.mw.image.height()) if (self.mw.image and not self.mw.image.isNull()) else 1.0

        # Construir lista de cajas con coordenadas
        self._canvas_boxes = []
        label_count = {}   # para numerar duplicados: "car #1", "car #2"

        for s in shapes:
            if not s.label:
                continue
            xs = [p.x() for p in s.points]
            ys = [p.y() for p in s.points]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)

            # Número de ocurrencia de este label
            label_count[s.label] = label_count.get(s.label, 0) + 1
            n = label_count[s.label]

            display = f"{s.label}  #{n}   [{int(xmin)}, {int(ymin)}, {int(xmax)}, {int(ymax)}]"

            self._canvas_boxes.append({
                "label":   s.label,
                "pixel":   (xmin, ymin, xmax, ymax),
                "norm":    (xmin/w, ymin/h, xmax/w, ymax/h),
                "display": display,
            })

        # Refrescar QListWidget
        self.list_boxes.blockSignals(True)
        self.list_boxes.clear()

        if not self._canvas_boxes:
            placeholder = QListWidgetItem("  [Selecciona cajas en la imagen]")
            placeholder.setData(Qt.UserRole, None)
            placeholder.setFlags(Qt.NoItemFlags)
            self.list_boxes.addItem(placeholder)
            self.lbl_hint_boxes.setText("Selecciona cajas en la imagen actual")
        else:
            for i, box in enumerate(self._canvas_boxes):
                item = QListWidgetItem(f"  {box['display']}")
                item.setData(Qt.UserRole, i)   # índice en self._canvas_boxes
                self.list_boxes.addItem(item)
                item.setSelected(True)          # preseleccionar todas
            count = len(self._canvas_boxes)
            self.lbl_hint_boxes.setText(
                f"{count} caja(s) seleccionada(s) en el canvas — desmarca las que no quieras editar"
            )

        self.list_boxes.blockSignals(False)
        self._populate_combo()
        if hasattr(self, 'list_classes'):
            self._populate_classes_list()
        self._update_preview()

    def _selected_boxes(self) -> list:
        """Devuelve las cajas que el usuario tiene marcadas en la lista."""
        result = []
        for item in self.list_boxes.selectedItems():
            idx = item.data(Qt.UserRole)
            if idx is not None and idx < len(self._canvas_boxes):
                result.append(self._canvas_boxes[idx])
        return result

    def _image_range(self) -> list:
        img_list = self.mw.m_img_list
        cur_idx  = self.mw.cur_img_idx
        total    = len(img_list)
        if self.rb_forward.isChecked():
            start = cur_idx
            end   = min(cur_idx + self.spin_fwd.value(), total)
        else:
            start = max(0, self.spin_from.value() - 1)
            end   = min(self.spin_to.value(), total)
            if end <= start:
                end = start + 1
        return img_list[start:end]

    def _new_label(self) -> str:
        return self.combo_class.currentText().strip()

    # ─────────────────────────────────────────────────────────────────
    # Señales dinámicas
    # ─────────────────────────────────────────────────────────────────

    def _on_canvas_selection_changed(self, _selected=False):
        self._refresh_boxes_from_canvas()

    def _on_image_changed(self):
        total   = len(self.mw.m_img_list)
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
        if hasattr(self.mw, '_batch_label_edit') and self.mw._batch_label_edit.dialog == self:
            self.mw._batch_label_edit.dialog = None

    def accept(self):
        self.cleanup(); super().accept()

    def reject(self):
        self.cleanup(); super().reject()

    def closeEvent(self, event):
        self.cleanup(); super().closeEvent(event)

    def _on_mode_changed(self):
        fwd = self.rb_forward.isChecked()
        self.spin_fwd.setEnabled(fwd)
        self.spin_from.setEnabled(not fwd)
        self.spin_to.setEnabled(not fwd)
        self._update_preview()

    def _clamp_range(self):
        if self.spin_to.value() < self.spin_from.value():
            self.spin_to.blockSignals(True)
            self.spin_to.setValue(self.spin_from.value())
            self.spin_to.blockSignals(False)

    # ─────────────────────────────────────────────────────────────────
    # Preview
    # ─────────────────────────────────────────────────────────────────

    def _update_preview(self):
        boxes     = self._selected_boxes()
        imgs      = self._image_range()
        new_label = self._new_label()

        if not boxes:
            self.lbl_preview.setText(
                "⚠  Selecciona al menos una caja en la imagen."
            )
            self.btn_exec.setEnabled(False)
            return

        if not imgs:
            self.lbl_preview.setText("⚠  El rango no contiene imágenes válidas.")
            self.btn_exec.setEnabled(False)
            return

        if not new_label:
            self.lbl_preview.setText("⚠  Escribe o selecciona la nueva clase.")
            self.btn_exec.setEnabled(False)
            return

        # Nombre de las cajas a mostrar
        labels_str = ", ".join(
            f"<b style='color:#89b4fa'>{b['display']}</b>"
            for b in boxes[:3]
        )
        if len(boxes) > 3:
            labels_str += f" <span style='color:#6c7086'>y {len(boxes)-3} más</span>"

        first = os.path.basename(imgs[0])
        last  = os.path.basename(imgs[-1])
        range_str = (
            f"<b>{first}</b>" if len(imgs) == 1
            else f"<b>{first}</b>  →  <b>{last}</b>"
        )

        note = ""
        if self.mw.file_path and self.mw.file_path in imgs:
            note = ("<br><span style='color:#fab387; font-size:11px;'>"
                    "⚡ La imagen actual está en el rango y se recargará al terminar.</span>")

        self.lbl_preview.setText(
            f"{labels_str}"
            f"  <span style='color:#6c7086'>→</span>"
            f"  <b style='color:#a6e3a1'>{new_label}</b><br>"
            f"Imágenes afectadas: <b>{len(imgs)}</b>  —  {range_str}"
            f"{note}"
        )
        self.btn_exec.setEnabled(True)

    # ─────────────────────────────────────────────────────────────────
    # Ejecución
    # ─────────────────────────────────────────────────────────────────

    def _execute(self):
        boxes     = self._selected_boxes()
        new_label = self._new_label()
        imgs      = self._image_range()

        if not boxes or not new_label or not imgs:
            return

        detail = "\n".join(f"  • {b['display']}" for b in boxes)
        reply  = QMessageBox.warning(
            self,
            "Confirmar edición masiva",
            f"¿Cambiar la clase de las siguientes {len(boxes)} caja(s) a  '{new_label}'\n"
            f"en {len(imgs)} imagen(es)?\n\n"
            f"{detail}\n\n"
            "Solo se modificarán las cajas que coincidan en posición (IoU ≥ 0.8).\n"
            "Las demás cajas de la misma clase NO se tocarán.\n"
            "Esta acción no se puede deshacer.\n\n"
            "¿Continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_exec.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_prog_msg.setVisible(True)
        self.progress_bar.setValue(0)

        self._worker = _WorkerThread(
            img_paths  = imgs,
            boxes      = boxes,
            new_label  = new_label,
            label_hist = list(self.mw.label_hist),
            save_dir   = self.save_dir,
        )
        self._worker.sig_progress.connect(self._on_progress)
        self._worker.sig_done.connect(self._on_done)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.lbl_prog_msg.setText(msg)

    def _on_done(self, n_imgs: int, n_changed: int):
        self.progress_bar.setValue(100)
        self.lbl_prog_msg.setText(
            f"✔  Listo — {n_changed} anotación(es) editadas en {n_imgs} imagen(es)."
        )
        QMessageBox.information(
            self, "Edición completada",
            f"Proceso finalizado correctamente.\n\n"
            f"  • Imágenes procesadas  : {n_imgs}\n"
            f"  • Anotaciones editadas : {n_changed}",
        )
        if self.mw.file_path:
            self.mw.load_file(self.mw.file_path)
        self.accept()


# =============================================================================
# Plugin wrapper + punto de entrada
# =============================================================================

class BatchLabelEditPlugin:

    def __init__(self, main_window):
        self.mw     = main_window
        self.dialog = None
        self._register_menu()
        print(f"[batch_label_edit] v{__version__} cargado  (Ctrl+Shift+E)")

    def _register_menu(self):
        menu_edit = self.mw.menus.edit
        for act in menu_edit.actions():
            if getattr(act, "_ble_registered", False):
                return

        menu_edit.addSeparator()
        action = QAction("✏  Edición masiva por rango...", self.mw)
        action._ble_registered = True
        action.setShortcut("Ctrl+Shift+E")
        action.triggered.connect(self._open)
        menu_edit.addAction(action)

        has_ctx = any(
            act and getattr(act, "_ble_context_registered", False)
            for act in self.mw.actions.beginnerContext
        )
        if not has_ctx:
            self.context_action = QAction("✏  Edición masiva...", self.mw)
            self.context_action._ble_context_registered = True
            self.context_action.triggered.connect(self._open)

            beg = list(self.mw.actions.beginnerContext)
            beg.extend([None, self.context_action])
            self.mw.actions.beginnerContext = tuple(beg)

            adv = list(self.mw.actions.advancedContext)
            adv.extend([None, self.context_action])
            self.mw.actions.advancedContext = tuple(adv)

            self.mw.populate_mode_actions()

    def _open(self):
        mw = self.mw
        if not mw.m_img_list:
            QMessageBox.warning(mw, "Sin imágenes", "Abre primero un directorio con imágenes.")
            return

        if self.dialog is not None:
            self.dialog.raise_()
            self.dialog.activateWindow()
            return

        self.dialog = BatchEditDialog(
            parent     = mw,
            label_hist = list(mw.label_hist),
            save_dir   = mw.default_save_dir,
        )
        self.dialog.show()


def setup(main_window):
    plugin = BatchLabelEditPlugin(main_window)
    main_window._batch_label_edit = plugin
    return plugin
