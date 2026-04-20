# =============================================================================
# custom/plugins/label_exporter/core.py
# =============================================================================
# PROPÓSITO: Exportación avanzada V3.3 con soporte de CARGA DINÁMICA.
# =============================================================================

__version__ = "3.3.0"
__description__ = "Exportación profesional con diagnóstico de archivos y soporte de carga dinámica."

import csv
import json
import os
import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QCheckBox, QFileDialog, QMessageBox, QProgressBar, QFrame,
    QTabWidget, QWidget, QSpinBox, QLineEdit, QApplication
)
from PyQt5.QtCore import Qt, QEventLoop
from libs.pascal_voc_io import PascalVocReader
from libs.yolo_io import YoloReader

# --- Estilos ---
STYLESHEET = """
QDialog { background-color: #0f0f17; color: #cdd6f4; }
QTabWidget::pane { border: 1px solid #313244; background: #0f0f17; border-radius: 5px; }
QTabBar::tab { background: #1e1e2e; color: #bac2de; padding: 12px 25px; border: 1px solid #313244; border-bottom: none; }
QTabBar::tab:selected { background: #313244; color: #a6e3a1; font-weight: bold; }
QLabel { color: #bac2de; font-size: 13px; }
QCheckBox { color: #cdd6f4; spacing: 10px; padding: 5px; }
QPushButton {
    background-color: #1e1e2e; color: #a6e3a1; border: 1px solid #a6e3a1;
    border-radius: 4px; padding: 8px; font-weight: bold;
}
QPushButton:hover { background-color: #a6e3a1; color: #11111b; }
QLineEdit { background: #1e1e2e; color: #ffffff; border: 1px solid #313244; padding: 8px; border-radius: 4px; }
QSpinBox { background: #1e1e2e; color: #ffffff; border: 1px solid #313244; padding: 6px; }
"""

class ExportDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Exportación de Etiquetas (V3.3)")
        self.setMinimumWidth(650)
        self.setStyleSheet(STYLESHEET)
        self._construir_ui()

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # --- SECCIÓN ORIGEN DE ETIQUETAS ---
        layout.addWidget(QLabel("<b>📁 Paso 1: Localizar Carpeta de Etiquetas (XML/TXT)</b>"))
        origen_layout = QHBoxLayout()
        self.txt_origen = QLineEdit()
        save_dir = getattr(self.main_window, 'default_save_dir', "")
        if save_dir: self.txt_origen.setText(save_dir)
        origen_layout.addWidget(self.txt_origen)
        btn_browse = QPushButton("Explorar...")
        btn_browse.clicked.connect(self._explorar_origen)
        origen_layout.addWidget(btn_browse)
        layout.addLayout(origen_layout)
        
        self.btn_verificar = QPushButton("🔍 Verificar si hay etiquetas aquí")
        self.btn_verificar.clicked.connect(self._verificar_etiquetas)
        layout.addWidget(self.btn_verificar)
        layout.addWidget(QFrame(frameShape=QFrame.HLine))

        # Tabs
        self.tabs = QTabWidget()
        
        # TAB LOTE
        self.tab_lote = QWidget()
        layout_lote = QVBoxLayout(self.tab_lote)
        total_imgs = len(getattr(self.main_window, 'm_img_list', []))
        layout_lote.addWidget(QLabel(f"<b>📂 Paso 2: Configurar Rango ({total_imgs} imágenes)</b>"))
        
        r_layout = QHBoxLayout()
        self.spin_desde = QSpinBox(); self.spin_desde.setRange(1, max(1, total_imgs))
        self.spin_hasta = QSpinBox(); self.spin_hasta.setRange(1, max(1, total_imgs)); self.spin_hasta.setValue(total_imgs)
        r_layout.addWidget(QLabel("Desde #:")); r_layout.addWidget(self.spin_desde)
        r_layout.addWidget(QLabel("Hasta #:")); r_layout.addWidget(self.spin_hasta)
        layout_lote.addLayout(r_layout)
        
        self.chk_lote_csv = QCheckBox("✔ CSV"); self.chk_lote_json = QCheckBox("✔ JSON")
        self.chk_lote_txt = QCheckBox("✔ TXT"); self.chk_lote_excel = QCheckBox("✔ Excel")
        for c in [self.chk_lote_csv, self.chk_lote_json, self.chk_lote_txt, self.chk_lote_excel]:
            c.setChecked(True); layout_lote.addWidget(c)
        layout_lote.addStretch()

        self.tabs.addTab(self.tab_lote, "Exportación Masiva")
        layout.addWidget(self.tabs)

        self.progress = QProgressBar(); self.progress.setVisible(False); layout.addWidget(self.progress)
        self.btn_export = QPushButton("🚀 Iniciar Proceso de Auditoría"); self.btn_export.setObjectName("btn_export")
        self.btn_export.setMinimumHeight(50)
        self.btn_export.clicked.connect(self.accept); layout.addWidget(self.btn_export)

    def _explorar_origen(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de etiquetas")
        if dir_path: self.txt_origen.setText(dir_path)

    def _verificar_etiquetas(self):
        origen = self.txt_origen.text()
        if not origen or not os.path.exists(origen):
            QMessageBox.critical(self, "Error", "La carpeta no existe.")
            return

        all_imgs = getattr(self.main_window, 'm_img_list', [])
        if not all_imgs: return
        
        # Probar con la imagen 1 y la última del rango
        img1 = all_imgs[self.spin_desde.value()-1]
        img2 = all_imgs[self.spin_hasta.value()-1]
        
        results = []
        for img in [img1, img2]:
            base = os.path.splitext(os.path.basename(img))[0]
            encontrado = any(os.path.exists(os.path.join(origen, base + ext)) for ext in [".xml", ".XML", ".txt", ".TXT"])
            results.append(encontrado)
            
        if all(results):
            QMessageBox.information(self, "Éxito", "Se detectaron etiquetas para todo el rango seleccionado.")
        elif any(results):
            QMessageBox.warning(self, "Parcial", "Se detectaron algunas etiquetas, pero faltan otras. Revisa los nombres de archivo.")
        else:
            QMessageBox.critical(self, "Falla Total", "No se encontró ninguna etiqueta en esta carpeta. Verifica la ruta.")

    def get_config(self):
        return {
            "origen_manual": self.txt_origen.text(),
            "desde": self.spin_desde.value() - 1,
            "hasta": self.spin_hasta.value(),
            "formatos": {
                "csv": self.chk_lote_csv.isChecked(),
                "json": self.chk_lote_json.isChecked(),
                "txt": self.chk_lote_txt.isChecked(),
                "excel": self.chk_lote_excel.isChecked()
            }
        }

class LabelExporterPlugin:
    def __init__(self, main_window):
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        dock_widget = self.main_window.dock.widget()
        dock_layout = dock_widget.layout()
        self.btn_main = QPushButton("📊 Exportación de Etiquetas")
        self.btn_main.setStyleSheet("background-color: #1e1e2e; color: #a6e3a1; border: 1px solid #a6e3a1; border-radius: 6px; padding: 12px; font-weight: bold; margin-top: 15px;")
        self.btn_main.clicked.connect(self._abrir_exportador)
        pos = dock_layout.indexOf(self.main_window.label_list)
        dock_layout.insertWidget(pos if pos != -1 else 3, self.btn_main)

    def _abrir_exportador(self):
        dialog = ExportDialog(self.main_window)
        if dialog.exec_():
            config = dialog.get_config()
            self._procesar_exportacion(config, dialog)

    def _procesar_exportacion(self, config, dialog):
        target_root = QFileDialog.getExistingDirectory(self.main_window, "Seleccione carpeta de destino")
        if not target_root: return
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = os.path.join(target_root, f"Auditoria_{timestamp}")
        os.makedirs(report_dir, exist_ok=True)

        all_imgs = getattr(self.main_window, 'm_img_list', [])
        img_list = all_imgs[config["desde"]:config["hasta"]]

        dialog.progress.setVisible(True); dialog.progress.setMaximum(len(img_list))
        resumen_datos = []

        for i, img_path in enumerate(img_list):
            dialog.progress.setValue(i + 1)
            QApplication.processEvents() # Mantener UI viva
            
            shapes = self._leer_anotacion_disco(img_path, config["origen_manual"])
            if not shapes: continue
            
            img_name_base = os.path.splitext(os.path.basename(img_path))[0]
            img_folder = os.path.join(report_dir, img_name_base); os.makedirs(img_folder, exist_ok=True)
            entry = self._format_entry(img_path, shapes); resumen_datos.append(entry)

            fmts = config["formatos"]
            if fmts["csv"]: self._export_csv(os.path.join(img_folder, f"data_{img_name_base}.csv"), [entry])
            if fmts["json"]: self._export_json(os.path.join(img_folder, f"data_{img_name_base}.json"), [entry])
            if fmts["txt"]: self._export_txt(os.path.join(img_folder, f"resumen_{img_name_base}.txt"), [entry])
            if fmts["excel"]: self._export_csv(os.path.join(img_folder, f"reporte_{img_name_base}.csv"), [entry], is_excel=True)

        self._generar_resumen_global(report_dir, resumen_datos)
        dialog.progress.setVisible(False)
        QMessageBox.information(self.main_window, "Completado", f"Procesadas {len(resumen_datos)} imágenes.\nUbicación: {report_dir}")

    def _leer_anotacion_disco(self, img_path, origen_manual):
        img_path = os.path.abspath(img_path); img_dir = os.path.dirname(img_path)
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        search_dirs = []
        if origen_manual and os.path.exists(origen_manual):
            search_dirs.append(os.path.abspath(origen_manual))
        
        save_dir = getattr(self.main_window, 'default_save_dir', None)
        if save_dir: search_dirs.append(os.path.abspath(save_dir))
        search_dirs.append(img_dir)

        for d in search_dirs:
            for ext in [".xml", ".XML", ".txt", ".TXT"]:
                p = os.path.join(d, base_name + ext)
                if os.path.exists(p):
                    if ext.lower() == ".xml":
                        try: return PascalVocReader(p).get_shapes()
                        except: pass
                    else:
                        cp = os.path.join(d, "classes.txt")
                        if not os.path.exists(cp): cp = os.path.join(img_dir, "classes.txt")
                        if os.path.exists(cp):
                            try:
                                with open(cp, 'r', encoding='utf-8') as f:
                                    cls = [l.strip() for l in f.readlines() if l.strip()]
                                return YoloReader(p, img_path, cls).get_shapes()
                            except: pass
        print(f"[Exporter Debug] No encontrado: {base_name} en {search_dirs}")
        return []

    def _format_entry(self, path, shapes):
        name = os.path.basename(path); counts = {} ; details = []
        for s in shapes:
            label = s['label'] if isinstance(s, dict) else s.label
            counts[label] = counts.get(label, 0) + 1
            pts = s['points'] if isinstance(s, dict) else [[p.x(), p.y()] for p in s.points]
            details.append({"label": label, "points": pts})
        return {"image": name, "counts": counts, "total": len(shapes), "details": details}

    def _generar_resumen_global(self, report_dir, data):
        with open(os.path.join(report_dir, "RESUMEN_GLOBAL.csv"), 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f, delimiter=';'); w.writerow(["Imagen", "Total", "Clases"])
            for e in data: w.writerow([e["image"], e["total"], str(e["counts"])])

    def _export_csv(self, path, data, is_excel=False):
        with open(path, 'w', newline='', encoding='utf-8-sig' if is_excel else 'utf-8') as f:
            w = csv.writer(f, delimiter=';' if is_excel else ','); w.writerow(["Imagen", "Clase", "Puntos"])
            for img in data:
                for d in img["details"]: w.writerow([img["image"], d["label"], str(d["points"])])

    def _export_json(self, path, data):
        with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

    def _export_txt(self, path, data):
        with open(path, 'w', encoding='utf-8') as f:
            for i in data: f.write(f"Imagen: {i['image']}\nTotal: {i['total']}\n{i['counts']}\n" + "="*20 + "\n")

def setup(main_window):
    main_window._label_exporter = LabelExporterPlugin(main_window)
