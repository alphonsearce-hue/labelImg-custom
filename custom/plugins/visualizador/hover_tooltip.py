# =============================================================================
# custom/plugins/visualizador/hover_tooltip.py
# =============================================================================
# Ventana flotante sin bordes que aparece al pasar el cursor sobre una caja
# o al seleccionarla.  Muestra imagen(es) del producto + gramaje + nombre.
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
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint |
                         Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAutoFillBackground(True)

        # Estilo del contenedor
        self.setStyleSheet("""
            ProductTooltip {
                background-color: #1e1e2e;
                border: 1px solid #45475a;
                border-radius: 8px;
            }
            QLabel#title {
                color: #cdd6f4;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#sub {
                color: #a6adc8;
                font-size: 10px;
            }
            QLabel#gramaje {
                color: #a6e3a1;
                font-size: 11px;
                font-weight: bold;
            }
        """)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        self._outer.setSpacing(6)

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

        self._lbl_sku     = QLabel()
        self._lbl_sku.setObjectName("sub")

        self._outer.addWidget(self._lbl_name)
        self._outer.addWidget(self._lbl_gramaje)
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
        """
        Carga datos del producto y muestra el tooltip.
        mode="hover"     → 1 imagen, tamaño pequeño
        mode="selection" → hasta 3 imágenes, tamaño medio
        """
        rows = db.find_by_label(label_text)
        if rows.empty:
            self.hide()
            return

        row = rows.iloc[0]
        upc = row.get("upc_version", "")

        # Número de imágenes según modo
        max_imgs = 1 if mode == "hover" else 3
        img_paths = db.get_images(upc, max_images=max_imgs)

        self._populate(row, img_paths, mode)
        self._reposition(global_pos)
        self.show()
        self.raise_()

    def _populate(self, row, img_paths: list[str], mode: str) -> None:
        # Limpiar imágenes anteriores
        for i in reversed(range(self._img_grid.count())):
            item = self._img_grid.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
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
        sku     = str(row.get("sku_indice", ""))

        self._lbl_name.setText(nombre or "—")
        self._lbl_gramaje.setText(f"⚖ {gramaje}" if gramaje else "")
        self._lbl_sku.setText(f"SKU índice: {sku}" if sku else "")

        self.adjustSize()

    def _reposition(self, global_pos: QPoint | None) -> None:
        if global_pos is None:
            global_pos = QApplication.desktop().rect().center()

        screen = QApplication.desktop().screenGeometry(global_pos)
        x = global_pos.x() + 18
        y = global_pos.y() + 18

        # Evitar salir por la derecha
        if x + self.width() > screen.right():
            x = global_pos.x() - self.width() - 8
        # Evitar salir por abajo
        if y + self.height() > screen.bottom():
            y = global_pos.y() - self.height() - 8

        self.move(x, y)


# =============================================================================
class HoverTooltipManager:
    """
    Intercepta el mouseMoveEvent del canvas mediante monkey-patch y gestiona
    el ciclo de vida del tooltip.

    Modos independientes (toggleables):
      - hover_enabled:     muestra 1 imagen al pasar el cursor
      - selection_enabled: muestra 3 imágenes al seleccionar una caja
    """

    def __init__(self, main_window, db: "CatalogDB"):
        self.mw        = main_window
        self.db        = db
        self.canvas    = main_window.canvas
        self._tooltip  = ProductTooltip()

        self.hover_enabled     = True
        self.selection_enabled = True

        # Timer para el retardo del hover
        self._hover_timer = QTimer()
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._on_hover_timer)
        self._pending_label: str | None = None
        self._pending_pos: QPoint | None = None

        self._last_h_label: str | None = None   # etiqueta bajo el cursor
        self._current_sel_label: str | None = None  # etiqueta seleccionada

        self._install()

    # ── Instalación ───────────────────────────────────────────────────────────
    def _install(self) -> None:
        """Monkey-patch del mouseMoveEvent y conexión con selectionChanged."""
        canvas = self.canvas
        original_move = canvas.mouseMoveEvent

        mgr = self  # capturar referencia

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
                # Ocultar solo si no está mostrando la selección activa
                if mgr._current_sel_label is None:
                    mgr._tooltip.hide()

        canvas.mouseMoveEvent = patched_move
        
        # Interceptar clear_selection porque selectionChanged(False) a veces no se emite
        if hasattr(canvas, 'clear_selection'):
            original_clear_selection = canvas.clear_selection
            def patched_clear_selection(*args, **kwargs):
                original_clear_selection(*args, **kwargs)
                mgr._current_sel_label = None
                mgr._last_h_label = None
                mgr._tooltip.hide()
            canvas.clear_selection = patched_clear_selection

        # Event filter para ocultar el tooltip si se cambia a otra aplicación
        class FocusFilter(QObject):
            def eventFilter(self, obj, ev):
                if ev.type() == QEvent.WindowDeactivate:
                    if mgr._tooltip.isVisible():
                        mgr._tooltip.hide()
                        # Resetear estado para que vuelva a dispararse si regresan
                        mgr._current_sel_label = None
                        mgr._last_h_label = None
                return False
        
        self._focus_filter = FocusFilter()
        self.mw.installEventFilter(self._focus_filter)

        # Conectar selectionChanged
        try:
            canvas.selectionChanged.connect(self._on_selection_changed)
        except Exception as e:
            print(f"[Visualizador] No se pudo conectar selectionChanged: {e}")

    # ── Slots ─────────────────────────────────────────────────────────────────
    def _on_hover_timer(self) -> None:
        if not self.hover_enabled or not self._pending_label:
            return
        # No mostrar hover si ya hay tooltip de selección visible
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
            self._current_sel_label = None
            self._last_h_label = None  # Resetear para que el hover vuelva a dispararse
            self._tooltip.hide()
            return

        shape = self.canvas.selected_shape
        if shape is None:
            self._current_sel_label = None
            self._tooltip.hide()
            return

        label = shape.label or ""
        self._current_sel_label = label
        self._hover_timer.stop()

        # Posición: esquina superior-derecha de la ventana principal
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
