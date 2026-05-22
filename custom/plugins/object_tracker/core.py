# =============================================================================
# custom/plugins/object_tracker/core.py
# =============================================================================
# PROPÓSITO : Seguimiento automático de bounding-boxes entre frames usando
#             OpenCV KCF Tracker + interpolación lineal entre frame A y Z.
# VERSIÓN   : 1.0.0
# REQUIERE  : opencv-contrib-python >= 4.5  (pip install opencv-contrib-python)
# =============================================================================

from __future__ import annotations

import os
import traceback
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QBrush, QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDockWidget,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

__version__     = "1.0.0"
__description__ = "Object Tracking (KCF) + Interpolación lineal entre frames."

# ─── paleta oscura ────────────────────────────────────────────────────────────
_QSS = """
QWidget, QDialog {
    background-color: #0f0f17;
    color: #cdd6f4;
    font-family: 'Segoe UI', sans-serif;
    font-size: 12px;
}
QLabel           { color: #e6e9ef; }
QLabel#title     { color: #cba6f7; font-size: 16px; font-weight: bold; }
QLabel#subtitle  { color: #7ed957; font-size: 12px; font-weight: bold; }
QLabel#info      { color: #a6adc8; font-size: 11px; font-weight: normal; }
QLabel#preview   {
    color: #7ed957; font-size: 11px;
    padding: 6px 10px;
    background: #1e1e2e;
    border-radius: 6px;
}
QFrame[frameShape="4"]  { color: #313244; }

QSpinBox, QComboBox {
    background-color: #1e1e2e; color: #ffffff;
    border: 1px solid #45475a; padding: 5px 8px;
    border-radius: 4px; min-width: 70px;
}
QSpinBox::up-button, QSpinBox::down-button { width: 20px; }

QRadioButton { color: #cdd6f4; padding: 3px; }
QCheckBox    { color: #cdd6f4; padding: 3px; }

QPushButton {
    background-color: #1e1e2e; color: #89dceb;
    border: 1px solid #89dceb;
    border-radius: 6px; padding: 9px 16px; font-weight: bold;
}
QPushButton:hover   { background-color: #89dceb; color: #11111b; }
QPushButton#green   { color: #a6e3a1; border-color: #a6e3a1; }
QPushButton#green:hover  { background-color: #a6e3a1; color: #11111b; }
QPushButton#red     { color: #f38ba8; border-color: #f38ba8; }
QPushButton#red:hover    { background-color: #f38ba8; color: #11111b; }
QPushButton#yellow  { color: #f9e2af; border-color: #f9e2af; }
QPushButton#yellow:hover { background-color: #f9e2af; color: #11111b; }

QTableWidget {
    background-color: #1e1e2e; color: #cdd6f4;
    border: 1px solid #313244; border-radius: 4px;
    gridline-color: #313244;
}
QHeaderView::section {
    background-color: #181825; color: #cba6f7;
    border: none; padding: 4px; font-weight: bold;
}
QTableWidget::item:selected { background-color: #313244; }

QProgressBar {
    background: #1e1e2e; border: 1px solid #45475a;
    border-radius: 4px; text-align: center; color: #cdd6f4; height: 14px;
}
QProgressBar::chunk { background-color: #7ed957; border-radius: 4px; }

QScrollArea { border: none; }
"""

_BTN_DOCK = """
QPushButton {
    background-color: #1e1e2e;
    color: #cba6f7;
    border: 1px solid #cba6f7;
    border-radius: 6px;
    padding: 10px;
    font-weight: bold;
    margin-top: 6px;
}
QPushButton:hover { background-color: #cba6f7; color: #11111b; }
"""

# =============================================================================
#  MOTOR DE TRACKING  (desacoplado — puede usarse sin Qt)
# =============================================================================

class TrackingEngine:
    """
    Encapsula la lógica de KCF y de interpolación lineal.
    Sin dependencias de Qt: recibe / devuelve tuplas (x, y, w, h) en píxeles.
    """

    @staticmethod
    def create_tracker(tracker_type: str = "CSRT"):
        """
        Crea una instancia de tracker según el tipo.
        Tipos: 'KCF', 'CSRT'.
        """
        if tracker_type == "KCF":
            try: return cv2.TrackerKCF_create()
            except AttributeError:
                try: return cv2.legacy.TrackerKCF_create()
                except AttributeError: pass
        
        # Default/Fallback to CSRT
        try: return cv2.TrackerCSRT_create()
        except AttributeError:
            try: return cv2.legacy.TrackerCSRT_create()
            except AttributeError:
                try: return cv2.TrackerKCF_create() # Last resort
                except: return None

    @staticmethod
    def track_one_step(
        img_path: str,
        roi: Tuple[int, int, int, int],
        next_img_path: str,
        tracker_type: str = "CSRT"
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Predice la posición en un solo paso (re-inicializando el tracker).
        """
        def load_img(path):
            try:
                return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            except:
                return cv2.imread(path)

        frame1 = load_img(img_path)
        frame2 = load_img(next_img_path)
        
        if frame1 is None or frame2 is None:
            return None

        tracker = TrackingEngine.create_tracker(tracker_type)
        if not tracker:
            return None

        x, y, w, h = [int(v) for v in roi]
        ih, iw = frame1.shape[:2]
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > iw or y + h > ih:
            return None

        try:
            tracker.init(frame1, (x, y, w, h))
            success, box = tracker.update(frame2)
            if success:
                return tuple(int(v) for v in box)
        except:
            pass
        return None

    # ── Interpolación lineal ──────────────────────────────────────────────────
    @staticmethod
    def interpolate(
        box_a: Tuple[float, float, float, float],
        box_z: Tuple[float, float, float, float],
        n_frames: int,
    ) -> List[Tuple[float, float, float, float]]:
        """
        Genera `n_frames` cajas intermedias (sin incluir A ni Z) entre
        dos bounding-boxes dados como (x, y, w, h).

        Ejemplo: A=frame 0, Z=frame 10, n_frames=9  → frames 1…9
        """
        if n_frames <= 0:
            return []
        ax, ay, aw, ah = box_a
        zx, zy, zw, zh = box_z
        result = []
        for i in range(1, n_frames + 1):
            t = i / (n_frames + 1)
            result.append((
                ax + t * (zx - ax),
                ay + t * (zy - ay),
                aw + t * (zw - aw),
                ah + t * (zh - ah),
            ))
        return result

    # ── Utilidades de conversión ──────────────────────────────────────────────
    @staticmethod
    def xywh_from_qpoints(
        points: list,
    ) -> Tuple[float, float, float, float]:
        """Convierte lista de QPointF (4 esquinas) a (x, y, w, h)."""
        xs = [p.x() for p in points]
        ys = [p.y() for p in points]
        x, y = min(xs), min(ys)
        w, h = max(xs) - x, max(ys) - y
        return x, y, w, h

    @staticmethod
    def qpoints_from_xywh(
        x: float, y: float, w: float, h: float
    ) -> List[QPointF]:
        """Convierte (x,y,w,h) a lista de 4 QPointF (esquinas TL→TR→BR→BL)."""
        return [
            QPointF(x,     y    ),
            QPointF(x + w, y    ),
            QPointF(x + w, y + h),
            QPointF(x,     y + h),
        ]


# =============================================================================
#  PLUGIN
# =============================================================================

class ObjectTrackerPlugin:

    def __init__(self, mw):
        self.mw     = mw
        self.canvas = mw.canvas
        self.engine = TrackingEngine()

        # Estado interno
        self._tracked_shapes: Dict[int, dict] = {}  # idx_img → {label, box}
        self._interp_anchor_a: Optional[dict]  = None
        self._interp_anchor_z: Optional[dict]  = None
        self.panel = None  # Referencia persistente para ventana no modal

        self._setup_ui()
        self._hook_next_image()

    # =========================================================================
    #  UI
    # =========================================================================
    def _setup_ui(self):
        print("[ObjectTracker] Configurando interfaz...")
        
        # 1. Crear Acción Principal
        self.act_tracker = QAction("🎯 Tracker", self.mw)
        self.act_tracker.setStatusTip("Abrir panel de seguimiento de objetos")
        self.act_tracker.triggered.connect(self._open_panel)

        # 2. Inyectar en el Menubar (al lado de Plugins)
        menubar = self.mw.menuBar()
        inserted_menu = False
        for action in menubar.actions():
            # Buscar "Plugins" o "Propagación" para insertar cerca
            txt = action.text().lower()
            if "plugin" in txt or "propaga" in txt:
                menubar.insertAction(action, self.act_tracker)
                inserted_menu = True
                break
        if not inserted_menu:
            menubar.addAction(self.act_tracker)

        # 3. Inyectar en el Toolbar principal (arriba del todo)
        if hasattr(self.mw, "tools"):
            tb = self.mw.tools
            # Lo ponemos después de "Open Dir" (índice 2 aprox) o simplemente al principio
            if tb.actions():
                tb.insertAction(tb.actions()[0], self.act_tracker)
            else:
                tb.addAction(self.act_tracker)

        # 4. Inyectar en el panel lateral (Dock) si existe el gestor de plugins
        # Esto creará un botón grande en la derecha como los otros que tienes
        if hasattr(self.mw, "register_plugin_tool"):
            try:
                self.mw.register_plugin_tool(
                    "Herramientas de Clases", # Intentamos usar el nombre que sale en tu captura
                    "🎯 Abrir Object Tracker",
                    self._open_panel
                )
            except:
                self.mw.register_plugin_tool(
                    "class_tools",
                    "🎯 Object Tracker",
                    self._open_panel
                )

        if hasattr(self.mw, "register_plugin_action"):
            self.mw.register_plugin_action("Tracking", self.act_tracker)
        elif hasattr(self.mw, "menu_plugins"):
            self.mw.menu_plugins.addAction(self.act_tracker)
        
        print("[ObjectTracker] Interfaz configurada con éxito.")

    def _inject_dock_button(self):
        # Ya no es estrictamente necesario si tenemos el botón en toolbar/menubar,
        # pero lo mantenemos por si acaso como fallback.
        if hasattr(self.mw, "dock") and self.mw.dock.widget():
            dock_layout = self.mw.dock.widget().layout()
            if dock_layout:
                btn = QPushButton("🎯 Object Tracker")
                btn.setStyleSheet(_BTN_DOCK)
                btn.clicked.connect(self._open_panel)
                dock_layout.insertWidget(0, btn)

    # =========================================================================
    #  Hook en open_next_image
    # =========================================================================
    def _hook_next_image(self):
        """
        Envuelve open_next_image para interceptar el avance de frame y
        ejecutar el tracker KCF automáticamente si está activo.
        """
        original = getattr(self.mw, "open_next_image", None)
        if original is None or getattr(original, "_tracker_wrapped", False):
            return

        plugin = self

        def wrapped(*args, **kwargs):
            result = original(*args, **kwargs)
            plugin._auto_track_on_advance()
            return result

        wrapped._tracker_wrapped = True
        self.mw.open_next_image = wrapped

    def _auto_track_on_advance(self):
        """Ejecuta KCF sobre las shapes marcadas para tracking."""
        if not self._tracked_shapes:
            return

        img_list = getattr(self.mw, "m_img_list", [])
        cur_idx  = getattr(self.mw, "cur_img_idx", 0)
        prev_idx = cur_idx - 1
        if prev_idx < 0 or cur_idx >= len(img_list):
            return

        prev_entries = self._tracked_shapes.get(prev_idx)
        if not prev_entries:
            return

        # Intentar trackear cada una
        for entry in prev_entries:
            # Usamos CSRT por defecto para el auto-track por ser más robusto
            new_box = TrackingEngine.track_one_step(
                img_list[prev_idx], entry["box"], img_list[cur_idx],
                tracker_type="CSRT"
            )
            
            if new_box is None:
                continue
            
            label = entry["label"]
            self._create_shape_on_canvas(label, new_box)
            # Guardar posición predicha para el siguiente salto
            self._tracked_shapes.setdefault(cur_idx, []).append(
                {"label": label, "box": new_box}
            )

        if hasattr(self.mw, "set_dirty"):
            self.mw.set_dirty()
        if hasattr(self.mw, "save_file"):
            self.mw.save_file()
        self.canvas.update()

    # =========================================================================
    #  Panel principal
    # =========================================================================
    def _open_panel(self, _=False):
        if self.panel is None:
            self.panel = TrackerPanel(self.mw, self)
        
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    # =========================================================================
    #  API pública (llamable desde el panel o desde otros plugins)
    # =========================================================================
    def start_tracking_selected(self) -> bool:
        """
        Registra las shapes actualmente seleccionadas en el canvas
        para seguimiento KCF a partir del frame actual.
        """
        cur_idx  = getattr(self.mw, "cur_img_idx", 0)
        img_list = getattr(self.mw, "m_img_list", [])
        if not img_list:
            return False

        shapes = getattr(self.canvas, "selected_shapes", [])
        if not shapes and getattr(self.canvas, "selected_shape", None):
            shapes = [self.canvas.selected_shape]

        if not shapes:
            QMessageBox.warning(
                self.mw, "Sin selección",
                "Selecciona al menos una caja antes de iniciar el tracking."
            )
            return False

        entries = []
        for s in shapes:
            box = TrackingEngine.xywh_from_qpoints(s.points)
            entries.append({"label": s.label, "box": tuple(int(v) for v in box)})

        self._tracked_shapes[cur_idx] = entries
        self.mw.status(
            f"[Tracker] ✔ {len(entries)} shape(s) registrada(s) para tracking desde frame {cur_idx + 1}."
        )
        return True

    def stop_tracking(self):
        self._tracked_shapes.clear()
        self._interp_anchor_a = None
        self._interp_anchor_z = None
        self.mw.status("[Tracker] ⏹ Tracking detenido.")

    def run_interpolation(
        self,
        label: str,
        box_a: tuple,
        idx_a: int,
        box_z: tuple,
        idx_z: int,
    ) -> int:
        """
        Genera cajas interpoladas entre frame idx_a y idx_z para `label`.
        Devuelve número de frames generados.
        """
        img_list = getattr(self.mw, "m_img_list", [])
        if not img_list:
            return 0

        gap = idx_z - idx_a - 1
        if gap <= 0:
            return 0

        boxes = TrackingEngine.interpolate(box_a, box_z, gap)

        original_idx  = getattr(self.mw, "cur_img_idx", 0)
        original_path = getattr(self.mw, "file_path", None)
        saved = 0

        progress = _make_progress(self.mw, "🔢 Interpolando frames…", len(boxes))
        progress.show()

        for step, (frame_idx, box) in enumerate(
            zip(range(idx_a + 1, idx_z), boxes)
        ):
            if progress.wasCanceled():
                break
            progress.setValue(step)
            progress.setLabelText(
                f"[{step + 1}/{len(boxes)}]  Frame {frame_idx + 1}: {_short(img_list[frame_idx])}"
            )
            QApplication.processEvents()

            if not self.mw.load_file(img_list[frame_idx]):
                continue

            self._create_shape_on_canvas(label, box)

            if hasattr(self.mw, "set_dirty"):
                self.mw.set_dirty()
            if hasattr(self.mw, "save_file"):
                self.mw.save_file()
            saved += 1

        progress.setValue(len(boxes))
        progress.close()

        if original_path:
            self.mw.load_file(original_path)

        return saved

    def run_kcf_range(
        self,
        label: str,
        box_start: tuple,
        idx_start: int,
        idx_end: int,
        tracker_type: str = "CSRT"
    ) -> int:
        """
        Aplica tracking persistente frame a frame.
        """
        img_list = getattr(self.mw, "m_img_list", [])
        if not img_list: return 0

        def load_img(path):
            return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

        # Inicializar tracker persistente
        tracker = TrackingEngine.create_tracker(tracker_type)
        first_frame = load_img(img_list[idx_start])
        if first_frame is None or tracker is None:
            return 0
        
        tracker.init(first_frame, box_start)

        original_path = getattr(self.mw, "file_path", None)
        saved = 0
        total = idx_end - idx_start

        progress = _make_progress(self.mw, f"🎯 {tracker_type} Tracking…", total)
        progress.show()

        for step in range(1, total + 1):
            if progress.wasCanceled(): break
            
            curr_idx = idx_start + step
            if curr_idx >= len(img_list): break

            progress.setValue(step)
            progress.setLabelText(f"Trackeando frame {curr_idx + 1}...")
            QApplication.processEvents()

            frame = load_img(img_list[curr_idx])
            if frame is None: break

            success, box = tracker.update(frame)
            if not success:
                self.mw.status(f"[Tracker] ⚠ Perdido en frame {curr_idx + 1}")
                break

            # Cargar en UI y guardar
            if not self.mw.load_file(img_list[curr_idx]): break
            
            new_box = tuple(int(v) for v in box)
            self._create_shape_on_canvas(label, new_box)

            if hasattr(self.mw, "set_dirty"): self.mw.set_dirty()
            if hasattr(self.mw, "save_file"): self.mw.save_file()
            saved += 1

        progress.close()
        if original_path: self.mw.load_file(original_path)
        return saved

    # =========================================================================
    #  Helpers internos
    # =========================================================================
    def _create_shape_on_canvas(self, label: str, box: tuple):
        """
        Inserta una nueva Shape en el canvas con las coordenadas dadas.
        box = (x, y, w, h) en coordenadas de imagen.
        """
        from libs.shape import Shape
        from libs.utils import generate_color_by_text

        x, y, w, h = [float(v) for v in box]
        points = TrackingEngine.qpoints_from_xywh(x, y, w, h)

        shape = Shape(label=label)
        for p in points:
            shape.add_point(p)
        shape.close()

        color = generate_color_by_text(label)
        shape.line_color = color
        shape.fill_color = color

        self.canvas.shapes.append(shape)
        self.mw.add_label(shape)
        self.canvas.update()

    def _get_selected_box(self) -> Optional[Tuple[str, tuple, int]]:
        """
        Devuelve (label, (x,y,w,h), cur_idx) de la shape seleccionada, o None.
        """
        shapes = getattr(self.canvas, "selected_shapes", [])
        if not shapes and getattr(self.canvas, "selected_shape", None):
            shapes = [self.canvas.selected_shape]
        if not shapes:
            return None
        s   = shapes[0]
        box = tuple(int(v) for v in TrackingEngine.xywh_from_qpoints(s.points))
        return s.label, box, getattr(self.mw, "cur_img_idx", 0)

    @property
    def img_count(self) -> int:
        return len(getattr(self.mw, "m_img_list", []))

    @property
    def cur_idx(self) -> int:
        return getattr(self.mw, "cur_img_idx", 0)


# =============================================================================
#  PANEL Qt
# =============================================================================

class TrackerPanel(QDialog):

    def __init__(self, mw, plugin: ObjectTrackerPlugin):
        super().__init__(mw)
        self.mw     = mw
        self.plugin = plugin
        self.setWindowTitle("🎯 Object Tracker")
        self.setMinimumWidth(560)
        self.setStyleSheet(_QSS)
        self._anchor_a: Optional[Tuple[str, tuple, int]] = None
        self._anchor_z: Optional[Tuple[str, tuple, int]] = None
        self._build_ui()
        self._refresh_status()

    # ── Construcción UI ───────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        # ── Título
        lbl = QLabel("🎯 Object Tracker")
        lbl.setObjectName("title")
        root.addWidget(lbl)

        # Alerta si no hay trackers
        try:
            cv2.TrackerKCF_create()
        except AttributeError:
            err = QLabel("⚠ ERROR: No hay trackers disponibles (OpenCV Contrib no instalado).")
            err.setStyleSheet("color: #f7768e; font-weight: bold; background: #2d1b22; padding: 10px; border-radius: 6px;")
            err.setWordWrap(True)
            root.addWidget(err)
            
            help_lib = QLabel("Ejecuta: pip install opencv-contrib-python")
            help_lib.setObjectName("info")
            root.addWidget(help_lib)

        # ── Opciones de Algoritmo
        self.group_algo = QGroupBox("Algoritmo de Seguimiento")
        self.group_algo.setObjectName("group")
        algo_layout = QVBoxLayout(self.group_algo)
        
        self.rb_csrt = QRadioButton("CSRT (Muy Robusto, recomendado)")
        self.rb_csrt.setChecked(True)
        self.rb_kcf = QRadioButton("KCF (Muy Rápido, menos preciso)")
        
        algo_layout.addWidget(self.rb_csrt)
        algo_layout.addWidget(self.rb_kcf)
        root.addWidget(self.group_algo)

        info = QLabel(
            "Selecciona una caja en el canvas antes de usar cualquier función."
        )
        info.setObjectName("info")
        root.addWidget(info)

        root.addWidget(_hline())

        # ══════════════════════════════════════════════════════════════════════
        #  SECCIÓN 1 — KCF Continuo
        # ══════════════════════════════════════════════════════════════════════
        lbl_kcf = QLabel("① KCF — Seguimiento continuo (frame a frame)")
        lbl_kcf.setObjectName("subtitle")
        root.addWidget(lbl_kcf)

        info_kcf = QLabel(
            "Activa el tracker sobre la(s) caja(s) seleccionadas. "
            "El plugin propagará automáticamente la posición al avanzar con Next Image."
        )
        info_kcf.setObjectName("info")
        info_kcf.setWordWrap(True)
        root.addWidget(info_kcf)

        row_kcf = QHBoxLayout()
        self.btn_start = QPushButton("▶ Iniciar tracking")
        self.btn_start.setObjectName("green")
        self.btn_start.clicked.connect(self._on_start_tracking)
        row_kcf.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ Detener")
        self.btn_stop.setObjectName("red")
        self.btn_stop.clicked.connect(self._on_stop_tracking)
        row_kcf.addWidget(self.btn_stop)
        row_kcf.addStretch()
        root.addLayout(row_kcf)

        # ── KCF por rango explícito
        lbl_kcf2 = QLabel("    KCF en rango de frames (sin avanzar manualmente):")
        lbl_kcf2.setObjectName("info")
        root.addWidget(lbl_kcf2)

        row_kcf2 = QHBoxLayout()
        row_kcf2.addWidget(QLabel("Desde frame actual hasta frame:"))
        self.spn_kcf_end = QSpinBox()
        self.spn_kcf_end.setMinimum(1)
        self.spn_kcf_end.setMaximum(max(1, self.plugin.img_count))
        self.spn_kcf_end.setValue(
            min(self.plugin.cur_idx + 10, self.plugin.img_count)
        )
        row_kcf2.addWidget(self.spn_kcf_end)

        btn_kcf_run = QPushButton("🚀 Ejecutar KCF en rango")
        btn_kcf_run.setObjectName("yellow")
        btn_kcf_run.clicked.connect(self._on_kcf_range)
        row_kcf2.addWidget(btn_kcf_run)
        row_kcf2.addStretch()
        root.addLayout(row_kcf2)

        self.lbl_kcf_status = QLabel("")
        self.lbl_kcf_status.setObjectName("preview")
        root.addWidget(self.lbl_kcf_status)

        root.addWidget(_hline())

        # ══════════════════════════════════════════════════════════════════════
        #  SECCIÓN 2 — Interpolación lineal
        # ══════════════════════════════════════════════════════════════════════
        lbl_interp = QLabel("② Interpolación lineal  (frame A → frame Z)")
        lbl_interp.setObjectName("subtitle")
        root.addWidget(lbl_interp)

        info_interp = QLabel(
            "Etiqueta el frame inicial (A) y el frame final (Z) de forma manual, "
            "luego el plugin genera automáticamente todas las cajas intermedias."
        )
        info_interp.setObjectName("info")
        info_interp.setWordWrap(True)
        root.addWidget(info_interp)

        # Anclas A / Z
        row_anchors = QHBoxLayout()

        # Columna A
        col_a = QVBoxLayout()
        col_a.addWidget(QLabel("📍 Frame A (inicio):"))
        self.lbl_anchor_a = QLabel("Sin establecer")
        self.lbl_anchor_a.setObjectName("preview")
        self.lbl_anchor_a.setWordWrap(True)
        col_a.addWidget(self.lbl_anchor_a)
        btn_set_a = QPushButton("Establecer A (frame actual)")
        btn_set_a.clicked.connect(self._on_set_anchor_a)
        col_a.addWidget(btn_set_a)
        row_anchors.addLayout(col_a)

        row_anchors.addSpacing(16)

        # Columna Z
        col_z = QVBoxLayout()
        col_z.addWidget(QLabel("🏁 Frame Z (fin):"))
        self.lbl_anchor_z = QLabel("Sin establecer")
        self.lbl_anchor_z.setObjectName("preview")
        self.lbl_anchor_z.setWordWrap(True)
        col_z.addWidget(self.lbl_anchor_z)
        btn_set_z = QPushButton("Establecer Z (frame actual)")
        btn_set_z.clicked.connect(self._on_set_anchor_z)
        col_z.addWidget(btn_set_z)
        row_anchors.addLayout(col_z)

        root.addLayout(row_anchors)

        self.lbl_interp_preview = QLabel("Define A y Z para ver el resumen.")
        self.lbl_interp_preview.setObjectName("preview")
        self.lbl_interp_preview.setWordWrap(True)
        root.addWidget(self.lbl_interp_preview)

        btn_interp = QPushButton("🔢 Generar frames interpolados")
        btn_interp.setObjectName("green")
        btn_interp.clicked.connect(self._on_interpolate)
        root.addWidget(btn_interp)

        root.addWidget(_hline())

        # ── Pie
        self.lbl_global_status = QLabel("Listo.")
        self.lbl_global_status.setObjectName("info")
        root.addWidget(self.lbl_global_status)

        foot = QHBoxLayout()
        foot.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.setObjectName("red")
        btn_close.clicked.connect(self.hide)
        foot.addWidget(btn_close)
        root.addLayout(foot)

    # ── Refresco de estado ────────────────────────────────────────────────────
    def _refresh_status(self):
        n_tracked = sum(
            len(v) for v in self.plugin._tracked_shapes.values()
        )
        if n_tracked:
            self.lbl_kcf_status.setText(
                f"✦ Tracking activo: {n_tracked} shape(s) en {len(self.plugin._tracked_shapes)} frame(s)."
            )
        else:
            self.lbl_kcf_status.setText("✦ Tracking inactivo.")

        self._refresh_interp_preview()

    def _refresh_interp_preview(self):
        a = self._anchor_a
        z = self._anchor_z

        if a:
            self.lbl_anchor_a.setText(
                f"Frame {a[2] + 1}  |  '{a[0]}'  |  "
                f"box({a[1][0]},{a[1][1]},{a[1][2]},{a[1][3]})"
            )
        if z:
            self.lbl_anchor_z.setText(
                f"Frame {z[2] + 1}  |  '{z[0]}'  |  "
                f"box({z[1][0]},{z[1][1]},{z[1][2]},{z[1][3]})"
            )

        if a and z:
            gap = z[2] - a[2] - 1
            if gap <= 0:
                self.lbl_interp_preview.setText(
                    "⚠ Frame Z debe ser posterior a frame A."
                )
            else:
                self.lbl_interp_preview.setText(
                    f"✦ Se generarán  {gap}  frame(s) intermedios  "
                    f"(frame {a[2] + 2} → frame {z[2]})  "
                    f"para la etiqueta  '{a[0]}'."
                )

    # ── Handlers ──────────────────────────────────────────────────────────────
    def _on_start_tracking(self):
        ok = self.plugin.start_tracking_selected()
        if ok:
            self.lbl_global_status.setText(
                "✔ Tracking iniciado. Avanza con Next Image para propagar."
            )
        self._refresh_status()

    def _on_stop_tracking(self):
        self.plugin.stop_tracking()
        self._refresh_status()
        self.lbl_global_status.setText("⏹ Tracking detenido.")

    def _on_kcf_range(self):
        sel = self.plugin._get_selected_box()
        if sel is None:
            QMessageBox.warning(
                self, "Sin selección",
                "Selecciona una caja en el canvas antes de ejecutar KCF en rango."
            )
            return

        label, box, cur_idx = sel
        end_1based = self.spn_kcf_end.value()
        end_idx    = end_1based - 1

        if end_idx <= cur_idx:
            QMessageBox.warning(
                self, "Rango inválido",
                "El frame destino debe ser mayor que el frame actual."
            )
            return

        algo = "CSRT" if self.rb_csrt.isChecked() else "KCF"

        total = end_idx - cur_idx
        reply = QMessageBox.question(
            self, "Confirmar",
            f"Se aplicará {algo} sobre <b>{total}</b> frame(s) para la etiqueta "
            f"<b>'{label}'</b>.<br>¿Continuar?",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return

        saved = self.plugin.run_kcf_range(label, box, cur_idx, end_idx, tracker_type=algo)
        self.lbl_global_status.setText(
            f"✔ {algo} completado: {saved} frame(s) guardados."
        )
        QMessageBox.information(
            self, f"{algo} completado",
            f"Se propagaron <b>{saved}</b> frame(s) para '{label}'."
        )
        self._refresh_status()

    def _on_set_anchor_a(self):
        sel = self.plugin._get_selected_box()
        if sel is None:
            QMessageBox.warning(
                self, "Sin selección",
                "Selecciona una caja antes de establecer el ancla A."
            )
            return
        self._anchor_a = sel
        self._refresh_interp_preview()

    def _on_set_anchor_z(self):
        sel = self.plugin._get_selected_box()
        if sel is None:
            QMessageBox.warning(
                self, "Sin selección",
                "Selecciona una caja antes de establecer el ancla Z."
            )
            return
        self._anchor_z = sel
        self._refresh_interp_preview()

    def _on_interpolate(self):
        a = self._anchor_a
        z = self._anchor_z

        if a is None or z is None:
            QMessageBox.warning(
                self, "Anclas incompletas",
                "Define el frame A y el frame Z antes de interpolar."
            )
            return

        if a[0] != z[0]:
            reply = QMessageBox.question(
                self, "Etiquetas distintas",
                f"A usa  '{a[0]}'  y Z usa  '{z[0]}'.<br>"
                f"Se usará la etiqueta de A  (<b>'{a[0]}'</b>).<br>¿Continuar?",
                QMessageBox.Yes | QMessageBox.Cancel,
            )
            if reply != QMessageBox.Yes:
                return

        gap = z[2] - a[2] - 1
        if gap <= 0:
            QMessageBox.warning(
                self, "Rango inválido",
                "El frame Z debe ser estrictamente posterior al frame A."
            )
            return

        saved = self.plugin.run_interpolation(
            label  = a[0],
            box_a  = a[1],
            idx_a  = a[2],
            box_z  = z[1],
            idx_z  = z[2],
        )
        self.lbl_global_status.setText(
            f"✔ Interpolación completada: {saved} frame(s) guardados."
        )
        QMessageBox.information(
            self, "✅ Interpolación completada",
            f"<b>{saved}</b> frame(s) generados para '<b>{a[0]}</b>'.<br>"
            f"Frames {a[2] + 2} → {z[2]}."
        )
        self._refresh_status()


# =============================================================================
#  Helpers globales
# =============================================================================

def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


def _make_progress(parent, title: str, total: int) -> QProgressDialog:
    dlg = QProgressDialog("Iniciando…", "Cancelar", 0, total, parent)
    dlg.setWindowTitle(title)
    dlg.setWindowModality(Qt.WindowModal)
    dlg.setMinimumWidth(460)
    dlg.setStyleSheet(_QSS)
    return dlg


def _short(path: str, n: int = 50) -> str:
    name = os.path.basename(path)
    return name if len(name) <= n else "…" + name[-(n - 1):]


# =============================================================================
#  ENTRY POINT  ← llamado por custom/loader.py
# =============================================================================

def setup(main_window):
    try:
        # Verificar que cv2 esté disponible
        _ = cv2.__version__
        # Verificar KCF (requiere opencv-contrib)
        try:
            cv2.TrackerKCF_create()
        except AttributeError:
            try:
                cv2.TrackerCSRT_create()
                print("[ObjectTracker] ⚠ KCF no disponible, usando CSRT como fallback.")
            except AttributeError:
                print(
                    "[ObjectTracker] ✖ Ningún tracker disponible. "
                    "Instala opencv-contrib-python."
                )
    except Exception as exc:
        print(f"[ObjectTracker] Error al verificar OpenCV: {exc}")

    plugin = ObjectTrackerPlugin(main_window)
    main_window._object_tracker = plugin
    return plugin