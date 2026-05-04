# =============================================================================
# custom/plugins/image_jumper/core.py
# =============================================================================

import os
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QShortcut, QDockWidget, QMessageBox
)
from PyQt5.QtGui import QKeySequence, QIntValidator

__version__ = "2.0.0"
__description__ = "Navegación directa + eliminación de imagen y su .txt asociado."

STYLE = """
QWidget#jumper_root {
    background-color: #12121c;
    border: 1px solid #2a2a3d;
    border-radius: 6px;
}
QLabel#lbl_counter {
    color: #7ed957;
    font-family: 'Segoe UI', sans-serif;
    font-size: 11px;
    font-weight: bold;
}
QLabel#lbl_sep {
    color: #444466;
    font-size: 11px;
}
QLineEdit#jumper_input {
    background-color: #1e1e2e;
    color: #ffffff;
    border: 1px solid #7ed957;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 12px;
    font-family: 'Consolas', monospace;
    max-width: 64px;
    min-width: 48px;
}
QLineEdit#jumper_input:focus {
    border-color: #a8ff6e;
    background-color: #252535;
}
QPushButton#btn_go {
    background-color: transparent;
    color: #7ed957;
    border: 1px solid #7ed957;
    border-radius: 4px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 11px;
    min-width: 28px;
}
QPushButton#btn_go:hover { background-color: #7ed957; color: #11111b; }

QPushButton#btn_nav {
    background-color: transparent;
    color: #888aaa;
    border: 1px solid #2e2e4e;
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 11px;
}
QPushButton#btn_nav:hover { background-color: #2a2a4a; color: #ffffff; }

QPushButton#btn_delete {
    background-color: transparent;
    color: #ff5555;
    border: 1px solid #ff5555;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: bold;
}
QPushButton#btn_delete:hover { background-color: #ff5555; color: #ffffff; }
"""


class ImageJumperPlugin:

    def __init__(self, main_window):
        self.main_window = main_window
        self._build_widget()
        self._inject_into_ui()
        self._patch_navigation()
        self._setup_shortcut()

    # ------------------------------------------------------------------
    # Widget
    # ------------------------------------------------------------------

    def _build_widget(self):
        self.root = QWidget()
        self.root.setObjectName("jumper_root")
        self.root.setStyleSheet(STYLE)
        self.root.setFixedHeight(30)

        row = QHBoxLayout(self.root)
        row.setContentsMargins(8, 2, 8, 2)
        row.setSpacing(5)

        # ⏮ Primera
        self.btn_first = QPushButton("⏮")
        self.btn_first.setObjectName("btn_nav")
        self.btn_first.setFixedSize(26, 22)
        self.btn_first.setToolTip("Primera imagen")
        self.btn_first.clicked.connect(lambda: self._jump_to(0))

        # Contador  "10 / 2925"
        self.lbl_current = QLabel("1")
        self.lbl_current.setObjectName("lbl_counter")
        sep = QLabel("/")
        sep.setObjectName("lbl_sep")
        self.lbl_total = QLabel("?")
        self.lbl_total.setObjectName("lbl_counter")
        self.lbl_total.setStyleSheet("color: #666688; font-size:11px; font-weight:bold;")

        # Input
        self.input = QLineEdit()
        self.input.setObjectName("jumper_input")
        self.input.setPlaceholderText("# img")
        self.input.setAlignment(Qt.AlignCenter)
        self.input.setFixedHeight(22)
        self.input.returnPressed.connect(self._jump)

        # Ir
        self.btn_go = QPushButton("Ir")
        self.btn_go.setObjectName("btn_go")
        self.btn_go.setFixedHeight(22)
        self.btn_go.setToolTip("Saltar (Enter / Ctrl+G)")
        self.btn_go.clicked.connect(self._jump)

        # ⏭ Última
        self.btn_last = QPushButton("⏭")
        self.btn_last.setObjectName("btn_nav")
        self.btn_last.setFixedSize(26, 22)
        self.btn_last.setToolTip("Última imagen")
        self.btn_last.clicked.connect(self._jump_to_last)

        # Separador visual
        sep_line = QLabel("|")
        sep_line.setStyleSheet("color: #2e2e4e; font-size: 14px;")

        # 🗑 Eliminar
        self.btn_delete = QPushButton("🗑 Eliminar")
        self.btn_delete.setObjectName("btn_delete")
        self.btn_delete.setFixedHeight(22)
        self.btn_delete.setToolTip("Eliminar imagen + .txt asociado")
        self.btn_delete.clicked.connect(self._confirm_delete)

        row.addWidget(self.btn_first)
        row.addWidget(self.lbl_current)
        row.addWidget(sep)
        row.addWidget(self.lbl_total)
        row.addWidget(self.input)
        row.addWidget(self.btn_go)
        row.addWidget(self.btn_last)
        row.addWidget(sep_line)
        row.addWidget(self.btn_delete)
        row.addStretch()

    # ------------------------------------------------------------------
    # Dock
    # ------------------------------------------------------------------

    def _inject_into_ui(self):
        try:
            dock = QDockWidget("🎯 Navegación", self.main_window)
            dock.setObjectName("image_jumper_dock")
            dock.setWidget(self.root)
            dock.setFeatures(
                QDockWidget.DockWidgetFloatable |
                QDockWidget.DockWidgetMovable
            )
            dock.setAllowedAreas(
                Qt.BottomDockWidgetArea |
                Qt.TopDockWidgetArea
            )
            # Forzar altura mínima del dock
            dock.setMinimumHeight(48)
            dock.setMaximumHeight(56)
            self.main_window.addDockWidget(Qt.BottomDockWidgetArea, dock)
            self._dock = dock
        except Exception as e:
            print(f"[ImageJumper] Error inyectando dock: {e}")

    # ------------------------------------------------------------------
    # Parchear navegación para actualizar contador
    # ------------------------------------------------------------------

    def _patch_navigation(self):
        tag = "_image_jumper_patched"
        plugin = self

        for m in ("load_file", "open_next_image", "open_prev_image"):
            orig = getattr(self.main_window, m, None)
            if orig is None or getattr(orig, tag, False):
                continue

            def make_wrapper(o):
                def wrapper(*args, **kwargs):
                    result = o(*args, **kwargs)
                    QTimer.singleShot(60, plugin._refresh_counter)
                    return result
                setattr(wrapper, tag, True)
                return wrapper

            setattr(self.main_window, m, make_wrapper(orig))

    # ------------------------------------------------------------------
    # Shortcut Ctrl+G
    # ------------------------------------------------------------------

    def _setup_shortcut(self):
        try:
            sc = QShortcut(QKeySequence("Ctrl+G"), self.main_window)
            sc.activated.connect(self._focus_input)
        except Exception as e:
            print(f"[ImageJumper] Shortcut error: {e}")

    def _focus_input(self):
        self.input.setFocus()
        self.input.selectAll()

    # ------------------------------------------------------------------
    # Navegación
    # ------------------------------------------------------------------

    def _jump(self):
        text = self.input.text().strip()
        if not text:
            return
        try:
            num = int(text)
        except ValueError:
            self._flash_error()
            return
        total = self._get_total()
        if total == 0:
            return
        self._jump_to(max(0, min(num - 1, total - 1)))
        self.input.clear()

    def _jump_to(self, idx):
        mw = self.main_window
        if not mw.m_img_list:
            return
        idx = max(0, min(idx, len(mw.m_img_list) - 1))
        mw.cur_img_idx = idx
        mw.load_file(mw.m_img_list[idx])

    def _jump_to_last(self):
        total = self._get_total()
        if total > 0:
            self._jump_to(total - 1)

    # ------------------------------------------------------------------
    # Eliminar imagen + .txt
    # ------------------------------------------------------------------

    def _confirm_delete(self):
        mw = self.main_window
        img_path = mw.file_path

        if not img_path or not os.path.isfile(img_path):
            self._msg("Sin imagen", "No hay ninguna imagen cargada actualmente.")
            return

        # Buscar el .txt asociado
        base = os.path.splitext(img_path)[0]
        txt_path = base + ".txt"
        txt_exists = os.path.isfile(txt_path)

        img_name = os.path.basename(img_path)
        txt_name = os.path.basename(txt_path) if txt_exists else "(no existe)"

        # Diálogo de confirmación
        msg = QMessageBox(self.main_window)
        msg.setWindowTitle("⚠️ Confirmar eliminación")
        msg.setIcon(QMessageBox.Warning)
        msg.setText(
            f"<b>¿Eliminar los siguientes archivos?</b><br><br>"
            f"🖼 <code>{img_name}</code><br>"
            f"📄 <code>{txt_name}</code>"
        )
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #12121c;
                color: #e0e0f0;
                font-family: 'Segoe UI';
            }
            QLabel { color: #e0e0f0; font-size: 13px; }
            QPushButton {
                background-color: #1e1e2e;
                color: #aaaacc;
                border: 1px solid #3a3a5a;
                border-radius: 5px;
                padding: 5px 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2a2a4a; color: #ffffff; }
        """)
        btn_yes = msg.addButton("🗑 Sí, eliminar", QMessageBox.AcceptRole)
        btn_yes.setStyleSheet(
            "background-color: #3a1010; color: #ff6666; "
            "border: 1px solid #ff4444; border-radius: 5px; padding: 5px 16px;"
        )
        msg.addButton("Cancelar", QMessageBox.RejectRole)
        msg.exec_()

        if msg.clickedButton() != btn_yes:
            return

        # Guardar datos antes de eliminar
        idx = mw.cur_img_idx
        open_dir = mw.last_open_dir

        # Cerrar archivo actual
        mw.reset_state()
        mw.set_clean()

        # Eliminar imagen
        try:
            os.remove(img_path)
            print(f"[ImageJumper] Eliminado: {img_path}")
        except Exception as e:
            self._msg("Error", f"No se pudo eliminar la imagen:\n{e}")
            return

        # Eliminar .txt si existe
        if txt_exists:
            try:
                os.remove(txt_path)
                print(f"[ImageJumper] Eliminado: {txt_path}")
            except Exception as e:
                print(f"[ImageJumper] No se pudo eliminar el .txt: {e}")

        # Recargar el directorio y navegar a la misma posición
        if open_dir and os.path.isdir(open_dir):
            mw.import_dir_images(open_dir)
            new_total = len(mw.m_img_list)
            if new_total > 0:
                new_idx = min(idx, new_total - 1)
                mw.cur_img_idx = new_idx
                mw.load_file(mw.m_img_list[new_idx])

        QTimer.singleShot(100, self._refresh_counter)

    # ------------------------------------------------------------------
    # Contador
    # ------------------------------------------------------------------

    def _refresh_counter(self):
        mw = self.main_window
        total = self._get_total()
        current = mw.cur_img_idx + 1
        self.lbl_current.setText(str(current))
        self.lbl_total.setText(str(total))
        self.input.setValidator(QIntValidator(1, max(1, total)))

    def _get_total(self):
        return len(self.main_window.m_img_list)

    # ------------------------------------------------------------------
    # Helpers UI
    # ------------------------------------------------------------------

    def _flash_error(self):
        self.input.setStyleSheet(
            "QLineEdit { background-color: #3a1010; border: 1px solid #ff5555; "
            "border-radius: 4px; color: #ff5555; padding: 2px 6px; }"
        )
        QTimer.singleShot(600, lambda: self.input.setStyleSheet(""))

    def _msg(self, title, text):
        QMessageBox.information(self.main_window, title, text)


# ----------------------------------------------------------------------
# Punto de entrada
# ----------------------------------------------------------------------

def setup(main_window):
    plugin = ImageJumperPlugin(main_window)
    main_window._image_jumper_plugin = plugin
    return plugin