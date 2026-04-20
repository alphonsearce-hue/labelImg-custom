import os
import shutil
import json
from PyQt5.QtWidgets import (QAction, QMenu, QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QLineEdit, QCheckBox, 
                             QMessageBox, QListWidget, QTabWidget, QWidget, QFileDialog,
                             QScrollArea, QFrame)
from PyQt5.QtCore import Qt

def setup(main_window):
    if hasattr(main_window, "_propagar_labels_plugin"):
        return main_window._propagar_labels_plugin
    plugin = PropagacionPlugin(main_window)
    main_window._propagar_labels_plugin = plugin
    return plugin

class PropagacionPlugin:
    def __init__(self, main_window):
        self.mw = main_window
        self.dialog = None
        self._setup_menu()

    def _setup_menu(self):
        menubar = self.mw.menuBar()
        self.menu_prop = QMenu("Propagación", self.mw)
        menubar.addMenu(self.menu_prop)
        self.action_run = QAction("🚀 Iniciar Propagación", self.mw)
        self.action_run.triggered.connect(self.show_dialog)
        self.menu_prop.addAction(self.action_run)

    def show_dialog(self):
        if self.dialog is None:
            self.dialog = PropagacionDialog(self.mw)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

class PropagacionDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.mw = parent
        self.setWindowTitle("YOLO Dataset Assistant (Plugin Mode)")
        self.setMinimumSize(950, 650)
        self.selected_folder = ""
        self.check_vars = {} # {str(idx): QCheckBox}
        
        self._apply_styles()
        self._setup_ui()
        self._load_classes()

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #0f111a; color: #e0e0e0; font-family: 'Segoe UI'; }
            QWidget#Sidebar { background-color: #161925; border-right: 1px solid #2e3440; }
            QLabel { color: #e0e0e0; font-size: 11px; }
            QLabel#Title { font-size: 20px; font-weight: bold; color: #ffffff; margin-bottom: 10px; }
            QLabel#TabTitle { font-size: 16px; font-weight: bold; color: #ffffff; margin-bottom: 5px; }
            QLineEdit { background-color: #1a1d2b; border: 1px solid #2e3440; border-radius: 4px; color: #ffffff; padding: 6px; }
            QListWidget { background-color: #1a1d2b; border: 1px solid #2e3440; border-radius: 4px; color: #cccccc; }
            QListWidget::item:selected { background-color: #7ed957; color: #0f111a; }
            QPushButton { background-color: #1a1d2b; border: 1px solid #2e3440; color: #ffffff; border-radius: 4px; padding: 8px; font-weight: bold; }
            QPushButton:hover { border: 1px solid #7ed957; background-color: #232736; }
            QPushButton#MainAction { background-color: #1a1d2b; border: 2px solid #7ed957; border-radius: 6px; padding: 12px; font-size: 13px; }
            QPushButton#MainAction:hover { background-color: #7ed957; color: #0f111a; }
            QCheckBox { color: #e0e0e0; spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 2px solid #2e3440; background-color: #1a1d2b; }
            QCheckBox::indicator:checked { background-color: #7ed957; }
            QTabWidget::pane { border: 1px solid #2e3440; background-color: #0f111a; top: -1px; }
            QTabBar::tab { background-color: #1a1d2b; color: #888888; padding: 10px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background-color: #7ed957; color: #0f111a; font-weight: bold; }
            QScrollArea { border: 1px solid #2e3440; background-color: #1a1d2b; border-radius: 4px; }
            QWidget#ClasesContainer { background-color: #1a1d2b; }
        """)

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # PANEL IZQUIERDO
        sidebar = QWidget(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(280)
        side_layout = QVBoxLayout(sidebar)
        side_layout.addWidget(QLabel("YOLO Dataset Assistant", objectName="Title"))
        
        side_layout.addWidget(QLabel("Carpeta seleccionada:"))
        self.lbl_folder = QLabel("Ninguna carpeta seleccionada")
        self.lbl_folder.setWordWrap(True)
        side_layout.addWidget(self.lbl_folder)
        
        btn_select = QPushButton("📁 Seleccionar carpeta")
        btn_select.clicked.connect(self._select_folder)
        side_layout.addWidget(btn_select)

        side_layout.addWidget(QLabel("🔍 Buscar archivo:"))
        self.txt_search = QLineEdit()
        self.txt_search.textChanged.connect(self._filter_files)
        side_layout.addWidget(self.txt_search)

        self.list_files = QListWidget()
        side_layout.addWidget(self.list_files)

        side_layout.addWidget(QLabel("🔢 Frames a propagar:"))
        self.txt_frames = QLineEdit(); self.txt_frames.setText("15")
        side_layout.addWidget(self.txt_frames)

        self.cb_backup = QCheckBox("📦 Hacer copia de seguridad")
        self.cb_backup.setChecked(True)
        side_layout.addWidget(self.cb_backup)
        
        main_layout.addWidget(sidebar)

        # ÁREA DERECHA (TABS)
        content_area = QWidget(); content_layout = QVBoxLayout(content_area)
        self.tabs = QTabWidget()
        
        # TAB 1: Muebles/Clases
        self.tab_clases = QWidget(); clases_main_layout = QVBoxLayout(self.tab_clases)
        clases_main_layout.addWidget(QLabel("🏷️ Propagación de Clases Estáticas", objectName="TabTitle", alignment=Qt.AlignCenter))
        clases_main_layout.addWidget(QLabel("Selecciona las clases estáticas a propagar:\n(Las clases móviles están ocultas por seguridad)", alignment=Qt.AlignCenter))
        
        self.scroll_clases = QScrollArea()
        self.scroll_clases.setWidgetResizable(True)
        self.clases_container = QWidget()
        self.clases_container.setObjectName("ClasesContainer")
        self.clases_layout = QVBoxLayout(self.clases_container)
        self.clases_layout.setAlignment(Qt.AlignTop)
        self.scroll_clases.setWidget(self.clases_container)
        clases_main_layout.addWidget(self.scroll_clases)
        
        btn_prop_clases = QPushButton("🚀 Propagar Clases Seleccionadas", objectName="MainAction")
        btn_prop_clases.clicked.connect(self._propagar_muebles)
        clases_main_layout.addWidget(btn_prop_clases)
        
        # TAB 2: Personas (Inteligente)
        self.tab_personas = QWidget(); personas_layout = QVBoxLayout(self.tab_personas)
        personas_layout.addWidget(QLabel("👤 Propagación Inteligente", objectName="TabTitle", alignment=Qt.AlignCenter))
        
        instrucciones = (
            "Esta herramienta repara 'Falsos Negativos' en objetos con movimiento mínimo.\n\n"
            "Compara el frame base con los siguientes. Si el modelo falló\n"
            "en detectar a una persona, el asistente copiará automáticamente\n"
            "la caja del frame base para rescatar la etiqueta."
        )
        lbl_inst = QLabel(instrucciones, alignment=Qt.AlignCenter)
        lbl_inst.setStyleSheet("color: #888888; font-size: 12px; margin: 20px;")
        personas_layout.addWidget(lbl_inst)
        
        personas_layout.addWidget(QLabel("⚙️ Umbral interno de solapamiento (IoU): 0.02", alignment=Qt.AlignCenter))
        personas_layout.addStretch()
        
        btn_prop_pers = QPushButton("👤 Propagar Personas (Rescate)", objectName="MainAction")
        btn_prop_pers.clicked.connect(self._propagar_personas)
        personas_layout.addWidget(btn_prop_pers)
        
        self.tabs.addTab(self.tab_clases, "Propagar Clases")
        self.tabs.addTab(self.tab_personas, "Personas")
        content_layout.addWidget(self.tabs)
        main_layout.addWidget(content_area)

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if folder:
            self.selected_folder = folder
            self.lbl_folder.setText(os.path.basename(folder))
            self._load_files()

    def _load_files(self):
        self.list_files.clear()
        if self.selected_folder:
            files = sorted([f for f in os.listdir(self.selected_folder) if f.lower().endswith(('.txt'))])
            # Intentar cargar clases.txt si existe para actualizar checkboxes
            self._load_classes()
            self.list_files.addItems(files)

    def _load_classes(self):
        # Limpiar anteriores
        for i in reversed(range(self.clases_layout.count())): 
            self.clases_layout.itemAt(i).widget().setParent(None)
        self.check_vars.clear()

        classes = getattr(self.mw, "label_hist", [])
        clases_ignoradas = ["persona", "person"]
        
        for i, name in enumerate(classes):
            if name.lower() in clases_ignoradas: continue
            cb = QCheckBox(f"[{i}] {name}")
            self.check_vars[str(i)] = cb
            self.clases_layout.addWidget(cb)

    def _filter_files(self, text):
        for i in range(self.list_files.count()):
            item = self.list_files.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _calcular_iou(self, box1, box2):
        # box: [class, cx, cy, w, h]
        cx1, cy1, w1, h1 = map(float, box1[1:])
        cx2, cy2, w2, h2 = map(float, box2[1:])
        b1x1, b1y1, b1x2, b1y2 = cx1-w1/2, cy1-h1/2, cx1+w1/2, cy1+h1/2
        b2x1, b2y1, b2x2, b2y2 = cx2-w2/2, cy2-h2/2, cx2+w2/2, cy2+h2/2
        xi1, yi1 = max(b1x1, b2x1), max(b1y1, b2y1)
        xi2, yi2 = min(b1x2, b2x2), min(b1y2, b2y2)
        inter_area = max(0, xi2-xi1) * max(0, yi2-yi1)
        union_area = (w1*h1) + (w2*h2) - inter_area
        return inter_area / union_area if union_area > 0 else 0

    def _propagar_muebles(self):
        archivo_base = self.list_files.currentItem().text() if self.list_files.currentItem() else None
        if not archivo_base: return QMessageBox.warning(self, "Atención", "Selecciona un archivo base en la lista.")
        
        clases_seleccionadas = [idx for idx, cb in self.check_vars.items() if cb.isChecked()]
        if not clases_seleccionadas: return QMessageBox.warning(self, "Atención", "No hay clases seleccionadas.")
        
        try:
            frames = int(self.txt_frames.text())
            ruta_base = os.path.join(self.selected_folder, archivo_base)
            with open(ruta_base, "r") as f:
                lineas_base = [l for l in f.readlines() if l.strip() and l.strip().split()[0] in clases_seleccionadas]
            
            if not lineas_base: return QMessageBox.showinfo("Info", "El archivo base no tiene las clases seleccionadas.")
            
            all_files = [self.list_files.item(i).text() for i in range(self.list_files.count())]
            idx_base = all_files.index(archivo_base)
            targets = all_files[idx_base+1 : idx_base+1+frames]
            
            procesados = 0
            for name in targets:
                path = os.path.join(self.selected_folder, name)
                if self.cb_backup.isChecked(): shutil.copy2(path, path+".bak")
                with open(path, "r") as f:
                    finales = [l for l in f.readlines() if l.strip() and l.strip().split()[0] not in clases_seleccionadas]
                with open(path, "w") as f:
                    f.writelines(finales + lineas_base)
                procesados += 1
            QMessageBox.information(self, "Éxito", f"Clases propagadas en {procesados} archivos.")
        except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def _propagar_personas(self):
        archivo_base = self.list_files.currentItem().text() if self.list_files.currentItem() else None
        if not archivo_base: return
        CLASE_PERSONA = "0" # Estándar YOLO
        umbral_iou = 0.02
        
        try:
            frames = int(self.txt_frames.text())
            ruta_base = os.path.join(self.selected_folder, archivo_base)
            with open(ruta_base, "r") as f:
                pers_base = [l.strip().split() for l in f.readlines() if l.strip() and l.strip().split()[0] == CLASE_PERSONA]
            
            if not pers_base: return QMessageBox.showinfo("Info", "No hay personas (ID 0) en el archivo base.")
            
            all_files = [self.list_files.item(i).text() for i in range(self.list_files.count())]
            idx_base = all_files.index(archivo_base)
            targets = all_files[idx_base+1 : idx_base+1+frames]
            
            procesados = 0
            for name in targets:
                path = os.path.join(self.selected_folder, name)
                with open(path, "r") as f:
                    lineas_target = [l.strip().split() for l in f.readlines() if l.strip()]
                
                otras = [" ".join(l)+"\n" for l in lineas_target if l[0] != CLASE_PERSONA]
                pers_target = [l for l in lineas_target if l[0] == CLASE_PERSONA]
                
                finales_pers = [" ".join(l)+"\n" for l in pers_target]
                for p_b in pers_base:
                    if not any(self._calcular_iou(p_b, p_t) >= umbral_iou for p_t in pers_target):
                        finales_pers.append(" ".join(p_b)+"\n")
                
                with open(path, "w") as f: f.writelines(otras + finales_pers)
                procesados += 1
            QMessageBox.information(self, "Éxito", f"Personas propagadas en {procesados} archivos.")
        except Exception as e: QMessageBox.critical(self, "Error", str(e))