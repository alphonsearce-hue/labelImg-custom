# =============================================================================
# custom/plugins/object_tracker/core.py
# =============================================================================
# PROPÓSITO : Interpolación lineal de bounding-boxes entre frame A y frame Z.
# VERSIÓN   : 2.0.0
# =============================================================================

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

__version__ = "2.0.0"
__description__ = "Interpolación lineal de cajas entre frames."

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

QProgressBar {
    background: #1e1e2e; border: 1px solid #45475a;
    border-radius: 4px; text-align: center; color: #cdd6f4; height: 14px;
}
QProgressBar::chunk { background-color: #7ed957; border-radius: 4px; }
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


class InterpolationEngine:
    """Lógica pura de interpolación (sin OpenCV ni Qt)."""

    @staticmethod
    def interpolate(
        box_a: Tuple[float, float, float, float],
        box_z: Tuple[float, float, float, float],
        n_frames: int,
    ) -> List[Tuple[float, float, float, float]]:
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

    @staticmethod
    def xywh_from_qpoints(points: list) -> Tuple[float, float, float, float]:
        xs = [p.x() for p in points]
        ys = [p.y() for p in points]
        x, y = min(xs), min(ys)
        return x, y, max(xs) - x, max(ys) - y

    @staticmethod
    def qpoints_from_xywh(x: float, y: float, w: float, h: float) -> List[QPointF]:
        return [
            QPointF(x, y),
            QPointF(x + w, y),
            QPointF(x + w, y + h),
            QPointF(x, y + h),
        ]


class ObjectTrackerPlugin:

    def __init__(self, mw):
        self.mw = mw
        self.canvas = mw.canvas
        self.panel = None

        self._setup_ui()

    def _setup_ui(self):
        self.act_tracker = QAction("🎯 Tracker", self.mw)
        self.act_tracker.setStatusTip("Abrir panel de interpolación entre frames")
        self.act_tracker.triggered.connect(self._open_panel)

        menubar = self.mw.menuBar()
        inserted_menu = False
        for action in menubar.actions():
            txt = action.text().lower()
            if "plugin" in txt or "propaga" in txt:
                menubar.insertAction(action, self.act_tracker)
                inserted_menu = True
                break
        if not inserted_menu:
            menubar.addAction(self.act_tracker)

        if hasattr(self.mw, "tools"):
            tb = self.mw.tools
            if tb.actions():
                tb.insertAction(tb.actions()[0], self.act_tracker)
            else:
                tb.addAction(self.act_tracker)

        if hasattr(self.mw, "register_plugin_tool"):
            try:
                self.mw.register_plugin_tool(
                    "Herramientas de Clases",
                    "🎯 Abrir Object Tracker",
                    self._open_panel,
                )
            except Exception:
                self.mw.register_plugin_tool(
                    "class_tools",
                    "🎯 Object Tracker",
                    self._open_panel,
                )

        if hasattr(self.mw, "register_plugin_action"):
            self.mw.register_plugin_action("Tracking", self.act_tracker)
        elif hasattr(self.mw, "menu_plugins"):
            self.mw.menu_plugins.addAction(self.act_tracker)

    def _open_panel(self, _=False):
        if self.panel is None:
            self.panel = TrackerPanel(self.mw, self)
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def run_interpolation(
        self,
        label: str,
        box_a: tuple,
        idx_a: int,
        box_z: tuple,
        idx_z: int,
    ) -> int:
        img_list = getattr(self.mw, "m_img_list", [])
        if not img_list:
            return 0

        gap = idx_z - idx_a - 1
        if gap <= 0:
            return 0

        boxes = InterpolationEngine.interpolate(box_a, box_z, gap)
        original_path = getattr(self.mw, "file_path", None)
        saved = 0

        progress = _make_progress(self.mw, "🔢 Interpolando frames…", len(boxes))
        progress.show()

        for step, (frame_idx, box) in enumerate(zip(range(idx_a + 1, idx_z), boxes)):
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

    def _create_shape_on_canvas(self, label: str, box: tuple):
        from libs.shape import Shape
        from libs.utils import generate_color_by_text

        x, y, w, h = [float(v) for v in box]
        points = InterpolationEngine.qpoints_from_xywh(x, y, w, h)

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
        shapes = getattr(self.canvas, "selected_shapes", [])
        if not shapes and getattr(self.canvas, "selected_shape", None):
            shapes = [self.canvas.selected_shape]
        if not shapes:
            return None
        s = shapes[0]
        box = tuple(int(v) for v in InterpolationEngine.xywh_from_qpoints(s.points))
        return s.label, box, getattr(self.mw, "cur_img_idx", 0)

    @property
    def img_count(self) -> int:
        return len(getattr(self.mw, "m_img_list", []))

    @property
    def cur_idx(self) -> int:
        return getattr(self.mw, "cur_img_idx", 0)


class TrackerPanel(QDialog):

    def __init__(self, mw, plugin: ObjectTrackerPlugin):
        super().__init__(mw)
        self.mw = mw
        self.plugin = plugin
        self.setWindowTitle("🎯 Object Tracker — Interpolación")
        self.setMinimumWidth(520)
        self.setStyleSheet(_QSS)
        self._anchor_a: Optional[Tuple[str, tuple, int]] = None
        self._anchor_z: Optional[Tuple[str, tuple, int]] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        lbl = QLabel("🎯 Interpolación lineal entre frames")
        lbl.setObjectName("title")
        root.addWidget(lbl)

        info = QLabel(
            "Etiqueta el frame inicial (A) y el final (Z) con una caja seleccionada. "
            "El plugin generará automáticamente las cajas intermedias."
        )
        info.setObjectName("info")
        info.setWordWrap(True)
        root.addWidget(info)

        root.addWidget(_hline())

        row_anchors = QHBoxLayout()

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
                    f"✦ Se generarán {gap} frame(s) intermedios "
                    f"(frame {a[2] + 2} → frame {z[2]}) para '{a[0]}'."
                )

    def _on_set_anchor_a(self):
        sel = self.plugin._get_selected_box()
        if sel is None:
            QMessageBox.warning(self, "Sin selección", "Selecciona una caja antes de establecer A.")
            return
        self._anchor_a = sel
        self._refresh_interp_preview()

    def _on_set_anchor_z(self):
        sel = self.plugin._get_selected_box()
        if sel is None:
            QMessageBox.warning(self, "Sin selección", "Selecciona una caja antes de establecer Z.")
            return
        self._anchor_z = sel
        self._refresh_interp_preview()

    def _on_interpolate(self):
        a = self._anchor_a
        z = self._anchor_z

        if a is None or z is None:
            QMessageBox.warning(
                self, "Anclas incompletas",
                "Define el frame A y el frame Z antes de interpolar.",
            )
            return

        if a[0] != z[0]:
            reply = QMessageBox.question(
                self, "Etiquetas distintas",
                f"A usa '{a[0]}' y Z usa '{z[0]}'.<br>"
                f"Se usará la etiqueta de A (<b>'{a[0]}'</b>).<br>¿Continuar?",
                QMessageBox.Yes | QMessageBox.Cancel,
            )
            if reply != QMessageBox.Yes:
                return

        gap = z[2] - a[2] - 1
        if gap <= 0:
            QMessageBox.warning(
                self, "Rango inválido",
                "El frame Z debe ser estrictamente posterior al frame A.",
            )
            return

        saved = self.plugin.run_interpolation(
            label=a[0], box_a=a[1], idx_a=a[2], box_z=z[1], idx_z=z[2],
        )
        self.lbl_global_status.setText(
            f"✔ Interpolación completada: {saved} frame(s) guardados."
        )
        QMessageBox.information(
            self, "✅ Interpolación completada",
            f"<b>{saved}</b> frame(s) generados para '<b>{a[0]}</b>'.<br>"
            f"Frames {a[2] + 2} → {z[2]}.",
        )


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


def setup(main_window):
    plugin = ObjectTrackerPlugin(main_window)
    main_window._object_tracker = plugin
    return plugin
