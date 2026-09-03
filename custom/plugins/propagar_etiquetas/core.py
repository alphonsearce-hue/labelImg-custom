import os
import shutil
from PyQt5.QtWidgets import (QAction, QMenu, QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QLineEdit, QCheckBox, 
                             QMessageBox, QListWidget, QTabWidget, QWidget, QFileDialog,
                             QScrollArea, QRadioButton, QButtonGroup)
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
        
        # Diccionarios para los checkboxes
        self.check_vars_estaticas = {} 
        self.check_vars_dinamicas = {} 
        
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
            QCheckBox, QRadioButton { color: #e0e0e0; spacing: 8px; }
            QCheckBox::indicator, QRadioButton::indicator { width: 18px; height: 18px; border-radius: 4px; border: 2px solid #2e3440; background-color: #1a1d2b; }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked { background-color: #7ed957; }
            QRadioButton::indicator { border-radius: 9px; }
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

        side_layout.addWidget(QLabel("🔍 Buscar archivo (#12 = índice):"))
        self.txt_search = QLineEdit()
        self.txt_search.textChanged.connect(self._filter_files)
        side_layout.addWidget(self.txt_search)

        self.list_files = QListWidget()
        side_layout.addWidget(self.list_files)

        # Opciones de propagación (Radio Buttons)
        self.modo_group = QButtonGroup(self)
        self.radio_frames = QRadioButton("Por cantidad de frames")
        self.radio_indice = QRadioButton("Hasta índice")
        self.radio_frames.setChecked(True)
        self.modo_group.addButton(self.radio_frames)
        self.modo_group.addButton(self.radio_indice)
        
        self.radio_frames.toggled.connect(self._actualizar_modo_ui)
        self.radio_indice.toggled.connect(self._actualizar_modo_ui)

        side_layout.addWidget(self.radio_frames)
        side_layout.addWidget(self.radio_indice)

        self.lbl_frames = QLabel("🔢 Frames a propagar:")
        side_layout.addWidget(self.lbl_frames)
        self.txt_frames = QLineEdit(); self.txt_frames.setText("15")
        side_layout.addWidget(self.txt_frames)

        self.cb_backup = QCheckBox("📦 Hacer copia de seguridad")
        self.cb_backup.setChecked(True)
        side_layout.addWidget(self.cb_backup)
        
        main_layout.addWidget(sidebar)

        # ÁREA DERECHA (TABS)
        content_area = QWidget(); content_layout = QVBoxLayout(content_area)
        self.tabs = QTabWidget()
        
        # TAB 1: Clases Estáticas
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
        
        # TAB 2: Clases Dinámicas
        self.tab_dinamicas = QWidget(); dinamicas_layout = QVBoxLayout(self.tab_dinamicas)
        dinamicas_layout.addWidget(QLabel("🔄 Propagación de Clases Dinámicas (IoU)", objectName="TabTitle", alignment=Qt.AlignCenter))
        dinamicas_layout.addWidget(QLabel("Selecciona clases con movimiento (personas, autos, etc.):", alignment=Qt.AlignCenter))
        
        self.scroll_dinamicas = QScrollArea()
        self.scroll_dinamicas.setWidgetResizable(True)
        self.dinamicas_container = QWidget()
        self.dinamicas_container.setObjectName("ClasesContainer")
        self.dinamicas_layout = QVBoxLayout(self.dinamicas_container)
        self.dinamicas_layout.setAlignment(Qt.AlignTop)
        self.scroll_dinamicas.setWidget(self.dinamicas_container)
        dinamicas_layout.addWidget(self.scroll_dinamicas)
        
        dinamicas_layout.addWidget(QLabel("⚙️ Umbral interno de solapamiento (IoU): 0.2", alignment=Qt.AlignCenter))
        
        btn_prop_dyn = QPushButton("🔄 Propagar Clases Dinámicas", objectName="MainAction")
        btn_prop_dyn.clicked.connect(self._propagar_dinamicos)
        dinamicas_layout.addWidget(btn_prop_dyn)
        
        self.tabs.addTab(self.tab_clases, "Propagar Estáticos")
        self.tabs.addTab(self.tab_dinamicas, "Dinámicos")
        content_layout.addWidget(self.tabs)
        main_layout.addWidget(content_area)

    def _actualizar_modo_ui(self):
        self.txt_frames.clear()
        if self.radio_frames.isChecked():
            self.lbl_frames.setText("🔢 Frames a propagar:")
        else:
            self.lbl_frames.setText("🔢 Índice destino:")

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if folder:
            self.selected_folder = folder
            self.lbl_folder.setText(os.path.basename(folder))
            self._load_files()

    def _load_files(self):
        self.list_files.clear()
        if self.selected_folder:
            files = sorted([f for f in os.listdir(self.selected_folder) if f.lower().endswith(('.txt')) and f.lower() != "classes.txt"])
            self._load_classes()
            
            # Indexar visualmente la lista
            for idx, f in enumerate(files):
                self.list_files.addItem(f"[{idx+1:04d}] {f}")

    def _load_classes(self):
        # Limpiar anteriores
        for i in reversed(range(self.clases_layout.count())): 
            self.clases_layout.itemAt(i).widget().setParent(None)
        for i in reversed(range(self.dinamicas_layout.count())): 
            self.dinamicas_layout.itemAt(i).widget().setParent(None)
            
        self.check_vars_estaticas.clear()
        self.check_vars_dinamicas.clear()

        classes = getattr(self.mw, "label_hist", [])
        clases_ignoradas = ["persona", "person"]
        
        for i, name in enumerate(classes):
            # Clases estáticas (ignorar personas)
            if name.lower() not in clases_ignoradas:
                cb_estatica = QCheckBox(f"[{i}] {name}")
                self.check_vars_estaticas[str(i)] = cb_estatica
                self.clases_layout.addWidget(cb_estatica)
            
            # Clases dinámicas (todas)
            cb_dinamica = QCheckBox(f"[{i}] {name}")
            self.check_vars_dinamicas[str(i)] = cb_dinamica
            self.dinamicas_layout.addWidget(cb_dinamica)

    def _filter_files(self, text):
        texto = text.lower().strip()
        
        # Búsqueda por índice
        if texto.startswith("#"):
            numero = texto[1:]
            if numero.isdigit():
                idx_buscar = int(numero.lstrip("0") or "1") - 1
                for i in range(self.list_files.count()):
                    item = self.list_files.item(i)
                    item.setHidden(i != idx_buscar)
            return

        # Búsqueda normal
        for i in range(self.list_files.count()):
            item = self.list_files.item(i)
            item.setHidden(texto not in item.text().lower())

    def _calcular_iou(self, box1, box2):
        cx1, cy1, w1, h1 = map(float, box1[1:])
        cx2, cy2, w2, h2 = map(float, box2[1:])
        b1x1, b1y1, b1x2, b1y2 = cx1-w1/2, cy1-h1/2, cx1+w1/2, cy1+h1/2
        b2x1, b2y1, b2x2, b2y2 = cx2-w2/2, cy2-h2/2, cx2+w2/2, cy2+h2/2
        xi1, yi1 = max(b1x1, b2x1), max(b1y1, b2y1)
        xi2, yi2 = min(b1x2, b2x2), min(b1y2, b2y2)
        inter_area = max(0, xi2-xi1) * max(0, yi2-yi1)
        union_area = (w1*h1) + (w2*h2) - inter_area
        return inter_area / union_area if union_area > 0 else 0

    def _obtener_archivo_real(self, list_item):
        # Remueve el prefijo "[0001] " del texto del list widget
        return list_item.text().split("] ", 1)[1]

    def _calcular_fin(self, valor, indice_base, total_archivos):
        if self.radio_frames.isChecked():
            if valor <= 0: return None
            return min(indice_base + valor, total_archivos - 1)
        else:
            indice_destino = valor - 1
            if indice_destino <= indice_base:
                QMessageBox.warning(self, "Atención", f"El índice destino ({valor}) debe ser mayor al actual ({indice_base + 1}).")
                return None
            return min(indice_destino, total_archivos - 1)

    def _propagar_muebles(self):
        if not self.list_files.currentItem(): 
            return QMessageBox.warning(self, "Atención", "Selecciona un archivo base en la lista.")
        
        archivo_base = self._obtener_archivo_real(self.list_files.currentItem())
        clases_seleccionadas = [idx for idx, cb in self.check_vars_estaticas.items() if cb.isChecked()]
        
        if not clases_seleccionadas: 
            return QMessageBox.warning(self, "Atención", "No hay clases estáticas seleccionadas.")
        if not self.txt_frames.text().isdigit(): 
            return QMessageBox.warning(self, "Error", "El valor debe ser numérico.")
        
        try:
            valor = int(self.txt_frames.text())
            all_files = [self._obtener_archivo_real(self.list_files.item(i)) for i in range(self.list_files.count())]
            idx_base = all_files.index(archivo_base)
            
            fin = self._calcular_fin(valor, idx_base, len(all_files))
            if fin is None: return
            
            ruta_base = os.path.join(self.selected_folder, archivo_base)
            with open(ruta_base, "r") as f:
                lineas_base = [l.strip() for l in f.readlines() if l.strip()]
                lineas_a_propagar = [l for l in lineas_base if l.split()[0] in clases_seleccionadas]
            
            if not lineas_a_propagar: 
                return QMessageBox.information(self, "Info", "El archivo base no tiene las clases seleccionadas.")
            
            targets = all_files[idx_base+1 : fin+1]
            procesados = 0
            
            # Backup Folder Logic
            if self.cb_backup.isChecked():
                carpeta_backup = os.path.join(self.selected_folder, "backup_etiquetas")
                os.makedirs(carpeta_backup, exist_ok=True)
            
            for name in targets:
                path = os.path.join(self.selected_folder, name)
                if self.cb_backup.isChecked():
                    ruta_bak = os.path.join(carpeta_backup, name)
                    if not os.path.exists(ruta_bak):
                        shutil.copy2(path, ruta_bak)
                
                with open(path, "r") as f:
                    lineas_target = [l.strip() for l in f.readlines() if l.strip()]
                    finales = [l for l in lineas_target if l.split()[0] not in clases_seleccionadas]
                
                with open(path, "w") as f:
                    contenido_final = "\n".join(finales + lineas_a_propagar)
                    if contenido_final:
                        f.write(contenido_final + "\n")
                procesados += 1
            QMessageBox.information(self, "Éxito", f"Clases estáticas propagadas en {procesados} archivos.")
        except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def _propagar_dinamicos(self):
        if not self.list_files.currentItem(): 
            return QMessageBox.warning(self, "Atención", "Selecciona un archivo base en la lista.")
        
        archivo_base = self._obtener_archivo_real(self.list_files.currentItem())
        clases_dinamicas = [idx for idx, cb in self.check_vars_dinamicas.items() if cb.isChecked()]
        clases_estaticas = [idx for idx, cb in self.check_vars_estaticas.items() if cb.isChecked()]
        
        # Validar intersección
        interseccion = set(clases_dinamicas) & set(clases_estaticas)
        if interseccion:
            return QMessageBox.warning(self, "Error", "Una clase no puede ser estática y dinámica a la vez.")
            
        if not clases_dinamicas: 
            return QMessageBox.warning(self, "Atención", "No seleccionaste clases dinámicas.")
        if not self.txt_frames.text().isdigit(): 
            return QMessageBox.warning(self, "Error", "El valor debe ser numérico.")
            
        umbral_iou = 0.2
        
        try:
            valor = int(self.txt_frames.text())
            all_files = [self._obtener_archivo_real(self.list_files.item(i)) for i in range(self.list_files.count())]
            idx_base = all_files.index(archivo_base)
            
            fin = self._calcular_fin(valor, idx_base, len(all_files))
            if fin is None: return
            
            ruta_base = os.path.join(self.selected_folder, archivo_base)
            with open(ruta_base, "r") as f:
                objetos_base = [l.strip() for l in f.readlines() if l.strip() and l.strip().split()[0] in clases_dinamicas]
            
            if not objetos_base: 
                return QMessageBox.information(self, "Info", "No hay objetos dinámicos seleccionados en el archivo base.")
            
            targets = all_files[idx_base+1 : fin+1]
            procesados = 0
            
            if self.cb_backup.isChecked():
                carpeta_backup = os.path.join(self.selected_folder, "backup_etiquetas")
                os.makedirs(carpeta_backup, exist_ok=True)
            
            for name in targets:
                path = os.path.join(self.selected_folder, name)
                
                if self.cb_backup.isChecked():
                    ruta_bak = os.path.join(carpeta_backup, name)
                    if not os.path.exists(ruta_bak):
                        shutil.copy2(path, ruta_bak)
                        
                with open(path, "r") as f:
                    lineas_actuales = [l.strip() for l in f.readlines() if l.strip()]
                
                otras = [l for l in lineas_actuales if l.split()[0] not in clases_dinamicas]
                actuales = [l for l in lineas_actuales if l.split()[0] in clases_dinamicas]
                
                finales = list(actuales)
                
                for base in objetos_base:
                    yolo_base = base.split()
                    match = False
                    for act in actuales:
                        if self._calcular_iou(yolo_base, act.split()) >= umbral_iou:
                            match = True
                            break
                    if not match:
                        finales.append(base)
                
                with open(path, "w") as f: 
                    f.writelines([f"{l}\n" for l in otras + finales])
                procesados += 1
                
            QMessageBox.information(self, "Éxito", f"Clases dinámicas propagadas en {procesados} archivos.")
        except Exception as e: QMessageBox.critical(self, "Error", str(e))