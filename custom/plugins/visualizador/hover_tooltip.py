# =============================================================================
# custom/plugins/visualizador/hover_tooltip.py
# =============================================================================
# Ventana flotante sin bordes que aparece al pasar el cursor sobre una caja
# o al seleccionarla. Muestra imagen(es) del producto + gramaje + nombre + cluster.
# =============================================================================

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PyQt5.QtCore import QPoint, QSize, Qt, QTimer, QObject, QEvent
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QPen
from PyQt5.QtWidgets import (
    QApplication, QFrame, QGridLayout, QLabel,
    QSizePolicy, QVBoxLayout, QWidget,
)

if TYPE_CHECKING:
    from .catalog_db import CatalogDB

# ── Dimensiones ───────────────────────────────────────────────────────────────
_HOVER_W   = 160   # ancho miniatura modo hover (1 imagen)
_HOVER_H   = 160
_SELECT_W  = 150   # ancho miniatura modo selección (hasta 3)
_SELECT_H  = 150
_MARGIN    = 12
_HOVER_DELAY_MS  = 350   # retardo antes de mostrar tooltip hover


# =============================================================================
class ProductTooltip(QWidget):
    """
    Ventana tooltip flotante Qt (sin bordes, frameless).
    Se puede usar en modo HOVER (1 imagen) o SELECTION (hasta 3 imágenes).
    """

    def __init__(self, parent=None):
        # 🟢 FIX BUG: Se remueve Qt.WindowStaysOnTopHint para evitar que la imagen se quede trabada sobre la interfaz
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAutoFillBackground(True)

        # Estilo del contenedor
        self.setStyleSheet("""
            ProductTooltip {
                background-color: #11111b;
                border: 1px solid #45475a;
                border-radius: 10px;
            }
            QLabel#title {
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
            }
            QLabel#gramaje {
                color: #a6e3a1;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#cluster {
                color: #f9e2af;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#sku {
                color: #89b4fa;
                font-size: 11px;
                font-weight: bold;
            }
        """)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        self._outer.setSpacing(4)

        # Fila de imágenes
        self._img_grid = QGridLayout()
        self._img_grid.setSpacing(4)
        self._outer.addLayout(self._img_grid)

        # Etiquetas de texto
        self._lbl_name    = QLabel()
        self._lbl_name.setObjectName("title")
        self._lbl_name.setWordWrap(True)
        self._lbl_name.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        self._lbl_gramaje = QLabel()
        self._lbl_gramaje.setObjectName("gramaje")

        self._lbl_cluster = QLabel()
        self._lbl_cluster.setObjectName("cluster")

        self._lbl_sku = QLabel()
        self._lbl_sku.setObjectName("sku")

        self._outer.addWidget(self._lbl_name)
        self._outer.addWidget(self._lbl_gramaje)
        self._outer.addWidget(self._lbl_cluster)  # 🟢 NUEVO: Etiqueta de Cluster ID
        self._outer.addWidget(self._lbl_sku)

        # Mantener pixmaps referenciados para no ser recolectados
        self._pixmaps: list[QPixmap] = []

    # ── API pública ───────────────────────────────────────────────────────────
    def show_for_label(
        self,
        label_text: str,
        db: "CatalogDB",
        mode: str = "hover",          # "hover" | "selection"
        global_pos: QPoint | None = None,
    ) -> None:
        rows = db.find_by_label(label_text)
        if rows.empty:
            self.hide()
            return

        row = rows.iloc[0]
        upc = row.get("upc_version", "")

        max_imgs = 1 if mode == "hover" else 3
        img_paths = db.get_images(upc, max_images=max_imgs)

        self._populate(row, img_paths, mode)
        self._reposition(global_pos)
        self.show()
        self.raise_()

    def _populate(self, row, img_paths: list[str], mode: str) -> None:
        # 🟢 FIX: Desvincular e inmediatamente remover del layout las imágenes anteriores
        for i in reversed(range(self._img_grid.count())):
            item = self._img_grid.itemAt(i)
            if item and item.widget():
                w = item.widget()
                self._img_grid.removeWidget(w)
                w.setParent(None)
                w.deleteLater()
        self._pixmaps.clear()

        tw = _HOVER_W if mode == "hover" else _SELECT_W
        th = _HOVER_H if mode == "hover" else _SELECT_H

        # Agregar miniaturas
        for col_idx, path in enumerate(img_paths):
            lbl = QLabel()
            lbl.setFixedSize(tw, th)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background: #181825; border-radius: 4px;")

            if os.path.isfile(path):
                px = QPixmap(path)
                if not px.isNull():
                    px = px.scaled(tw, th, Qt.KeepAspectRatio,
                                   Qt.SmoothTransformation)
                    lbl.setPixmap(px)
                    self._pixmaps.append(px)
            else:
                lbl.setText("📷")
                lbl.setStyleSheet(
                    "color:#585b70; font-size:28px;"
                    "background:#181825; border-radius:4px;")

            self._img_grid.addWidget(lbl, 0, col_idx)

        # Sin imágenes → placeholder
        if not img_paths:
            ph = QLabel("Sin imagen")
            ph.setFixedSize(tw, th)
            ph.setAlignment(Qt.AlignCenter)
            ph.setStyleSheet("color:#585b70; background:#181825; border-radius:4px;")
            self._img_grid.addWidget(ph, 0, 0)

        # Texto
        nombre  = str(row.get("nombre_capturado", ""))[:60]
        gramaje = str(row.get("gramaje", ""))
        cluster = str(row.get("cluster_id", ""))
        sku     = str(row.get("sku_indice", ""))

        self._lbl_name.setText(nombre or "—")
        self._lbl_gramaje.setText(f"⚖ {gramaje}" if gramaje else "")
        self._lbl_cluster.setText(f"🏷️ Cluster ID: {cluster}" if cluster else "")
        self._lbl_sku.setText(f"📦 SKU índice: {sku}" if sku else "")

        # 🟢 FIX: Forzar colapso de dimensiones para recalcular el ancho exacto
        self.resize(1, 1)
        self.adjustSize()

    def _reposition(self, global_pos: QPoint | None) -> None:
        if global_pos is None:
            global_pos = QApplication.desktop().rect().center()

        screen = QApplication.desktop().screenGeometry(global_pos)
        x = global_pos.x() + 18
        y = global_pos.y() + 18

        if x + self.width() > screen.right():
            x = global_pos.x() - self.width() - 8
        if y + self.height() > screen.bottom():
            y = global_pos.y() - self.height() - 8

        self.move(x, y)


# =============================================================================
class HoverTooltipManager:
    """
    Intercepta eventos del canvas para gestionar el ciclo de vida del tooltip.
    """

    def __init__(self, main_window, db: "CatalogDB"):
        self.mw        = main_window
        self.db        = db
        self.canvas    = main_window.canvas
        self._tooltip  = ProductTooltip()

        self.hover_enabled     = True
        self.selection_enabled = True

        self._hover_timer = QTimer()
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._on_hover_timer)
        self._pending_label: str | None = None
        self._pending_pos: QPoint | None = None

        self._last_h_label: str | None = None
        self._current_sel_label: str | None = None

        self._install()

    # ── Instalación ───────────────────────────────────────────────────────────
    def _install(self) -> None:
        canvas = self.canvas
        original_move  = canvas.mouseMoveEvent
        original_press = canvas.mousePressEvent
        original_leave = getattr(canvas, 'leaveEvent', None)

        mgr = self

        # 🟢 FIX BUG: Ocultar al mover el mouse fuera de cajas válidas
        def patched_move(ev):
            original_move(ev)
            if not mgr.hover_enabled:
                return
            h_shape = canvas.h_shape
            if h_shape is not None:
                label = h_shape.label or ""
                if label != mgr._last_h_label:
                    mgr._last_h_label = label
                    mgr._pending_label = label
                    mgr._pending_pos   = ev.globalPos()
                    mgr._hover_timer.start(_HOVER_DELAY_MS)
            else:
                mgr._last_h_label = None
                mgr._hover_timer.stop()
                if mgr._current_sel_label is None:
                    mgr._tooltip.hide()

        # 🟢 FIX BUG: Ocultar si el mouse sale del lienzo (Canvas)
        def patched_leave(ev):
            if original_leave:
                original_leave(ev)
            mgr._last_h_label = None
            mgr._pending_label = None
            mgr._hover_timer.stop()
            if mgr._current_sel_label is None:
                mgr._tooltip.hide()

        # 🟢 FIX BUG: Ocultar si se hace clic fuera de una caja
        def patched_press(ev):
            original_press(ev)
            if canvas.selected_shape is None:
                mgr._current_sel_label = None
                mgr._tooltip.hide()
            

        canvas.mouseMoveEvent  = patched_move
        canvas.mousePressEvent = patched_press
        canvas.leaveEvent      = patched_leave
        
        # Interceptar selección limpia
        if hasattr(canvas, 'clear_selection'):
            original_clear_selection = canvas.clear_selection
            def patched_clear_selection(*args, **kwargs):
                original_clear_selection(*args, **kwargs)
                mgr._current_sel_label = None
                mgr._last_h_label = None
                mgr._tooltip.hide()
            canvas.clear_selection = patched_clear_selection

        # 🟢 FIX BUG: Ocultar tooltip si se cambia de imagen en la lista de archivos
        try:
            if hasattr(self.mw, 'file_list_widget'):
                self.mw.file_list_widget.itemSelectionChanged.connect(self._force_hide)
        except Exception:
            pass

        # Event filter para ocultar si se minimiza o cambia de aplicación
        class FocusFilter(QObject):
            def eventFilter(self, obj, ev):
                if ev.type() in (QEvent.WindowDeactivate, QEvent.FocusOut):
                    mgr._force_hide()
                return False
        
        self._focus_filter = FocusFilter()
        self.mw.installEventFilter(self._focus_filter)

        try:
            canvas.selectionChanged.connect(self._on_selection_changed)
        except Exception as e:
            print(f"[Visualizador] No se pudo conectar selectionChanged: {e}")

    def _force_hide(self) -> None:
        self._hover_timer.stop()
        self._current_sel_label = None
        self._last_h_label = None
        self._tooltip.hide()

    # ── Slots ─────────────────────────────────────────────────────────────────
    def _on_hover_timer(self) -> None:
        if not self.hover_enabled or not self._pending_label:
            return
        if self.selection_enabled and self._current_sel_label:
            return
        self._tooltip.show_for_label(
            self._pending_label, self.db,
            mode="hover",
            global_pos=self._pending_pos,
        )

    def _on_selection_changed(self, selected: bool) -> None:
        if not self.selection_enabled:
            self._current_sel_label = None
            return

        if not selected:
            self._force_hide()
            return

        shape = self.canvas.selected_shape
        if shape is None:
            self._force_hide()
            return

        label = shape.label or ""
        self._current_sel_label = label
        self._hover_timer.stop()

        geo = self.mw.geometry()
        global_pos = self.mw.mapToGlobal(
            QPoint(geo.width() // 2, geo.height() // 4)
        )

        self._tooltip.show_for_label(
            label, self.db,
            mode="selection",
            global_pos=global_pos,
        )

    # ── Control externo ───────────────────────────────────────────────────────
    def set_hover_enabled(self, enabled: bool) -> None:
        self.hover_enabled = enabled
        if not enabled:
            self._tooltip.hide()

    def set_selection_enabled(self, enabled: bool) -> None:
        self.selection_enabled = enabled
        if not enabled and self._current_sel_label:
            self._current_sel_label = None
            self._tooltip.hide()

    def destroy(self) -> None:
        self._tooltip.hide()
        self._tooltip.deleteLater()