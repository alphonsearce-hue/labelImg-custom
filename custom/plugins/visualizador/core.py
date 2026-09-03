# =============================================================================
# custom/plugins/visualizador/core.py
# =============================================================================
# Punto de entrada del plugin Visualizador.
# El loader llama a setup(main_window) — desde aquí se orquesta todo.
#
# SIN MODIFICAR labelImg.py: todo el enganche se hace por monkey-patch y
# conexión de señales Qt existentes.
# =============================================================================

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAction, QDockWidget, QPushButton

from .catalog_db     import CatalogDB
from .hover_tooltip  import HoverTooltipManager
from .product_panel  import ProductPanel

__version__     = "1.0.0"
__description__ = (
    "Visualizador de productos del catálogo: tooltip con imagen al pasar "
    "el cursor, panel de búsqueda, edición de etiquetas sin salir de LabelImg."
)


# =============================================================================
def setup(main_window) -> "VisualizadorPlugin":
    plugin = VisualizadorPlugin(main_window)
    main_window._visualizador_plugin = plugin
    return plugin


# =============================================================================
class VisualizadorPlugin:
    """
    Orquestador del plugin. Instancia los tres módulos y los conecta.
    """

    def __init__(self, main_window):
        self.mw = main_window
        print("[Visualizador] Iniciando…")

        # 1. Capa de datos
        self.db = CatalogDB()

        # 2. Tooltip flotante (requiere canvas ya creado)
        self.tooltip_mgr = HoverTooltipManager(main_window, self.db)

        # 3. Panel dock
        self.panel = ProductPanel(main_window, self.db, self.tooltip_mgr)

        # Cargar opciones guardadas si el objeto implementa los métodos
        if hasattr(self.panel, "_load_options") and callable(self.panel._load_options):
            self.panel._load_options()
        if hasattr(self.panel, "_apply_options") and callable(self.panel._apply_options):
            self.panel._apply_options()

        # 4. Añadir el dock a la ventana principal y tabularlo con el dock por defecto
        main_window.product_dock = self.panel
        main_window.addDockWidget(Qt.RightDockWidgetArea, self.panel)

        if hasattr(main_window, "dock") and isinstance(main_window.dock, QDockWidget):
            main_window.tabifyDockWidget(main_window.dock, self.panel)
            main_window.dock.raise_()  # Mantiene activa la pestaña principal de etiquetas

        # 5. Registrar botón / acción en la UI de LabelImg
        self._register_ui()

        print(f"[Visualizador] Listo — {len(self.db.df)} productos cargados.")

    # ── Registro en la UI ──────────────────────────────────────────────────────
    def _register_ui(self) -> None:
        """
        Registra la acción del plugin de forma robusta:
        - Si existe register_plugin_tool  → usa el sistema de plugins
        - Si existe menu_plugins          → agrega al menú
        - Siempre: agrega botón al dock lateral izquierdo
        """
        mw = self.mw

        def _toggle_panel(show: bool):
            if show:
                self.panel.show()
                self.panel.raise_()  # Selecciona la pestaña en primer plano
            else:
                self.panel.hide()

        # Acción de toggle del dock
        toggle_action = QAction("🔍 Visualizador de Productos", mw)
        toggle_action.setCheckable(True)
        toggle_action.setChecked(False)
        toggle_action.triggered.connect(_toggle_panel)

        self.panel.visibilityChanged.connect(
            lambda vis: toggle_action.setChecked(vis)
        )

        # Método preferido: register_plugin_tool
        if hasattr(mw, "register_plugin_tool"):
            mw.register_plugin_tool(
                "view_tools",
                "🔍 Visualizador de Productos",
                lambda: _toggle_panel(not self.panel.isVisible()),
            )

        # Método alternativo: menu_plugins / register_plugin_action
        if hasattr(mw, "register_plugin_action"):
            mw.register_plugin_action("Vista", toggle_action)
        elif hasattr(mw, "menu_plugins"):
            mw.menu_plugins.addAction(toggle_action)

        # Botón en el dock lateral (siempre)
        self._add_dock_button()

    def _add_dock_button(self) -> None:
        """Inserta un botón en el dock izquierdo (si existe)."""
        mw = self.mw
        dock_widget = getattr(mw, "dock", None)
        if dock_widget is None:
            return

        inner = dock_widget.widget()
        if inner is None:
            return

        layout = inner.layout()
        if layout is None:
            return

        btn = QPushButton("🔍 Visualizador")
        btn.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e;
                color: #f5c2e7;
                border: 1px solid #f5c2e7;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
                margin-top: 8px;
            }
            QPushButton:hover {
                background-color: #f5c2e7;
                color: #11111b;
            }
            QPushButton:checked {
                background-color: #f5c2e7;
                color: #11111b;
            }
        """)
        btn.setCheckable(True)
        btn.setChecked(False)

        def _toggle():
            vis = not self.panel.isVisible()
            if vis:
                self.panel.show()
                self.panel.raise_()
            else:
                self.panel.hide()
            btn.setChecked(vis)

        btn.clicked.connect(_toggle)
        self.panel.visibilityChanged.connect(btn.setChecked)

        layout.insertWidget(0, btn)