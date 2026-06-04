# =============================================================================
# custom/plugins/class_sync/core.py
# =============================================================================

import os
import codecs
import time

from PyQt5.QtCore import QFileSystemWatcher, QTimer
from PyQt5.QtWidgets import QAction

__version__ = "1.1.0"
__description__ = "Sincroniza classes.txt del dataset con predefined_classes.txt automáticamente."

DATASET_CLASSES_FILENAME = "classes.txt"

# Ruta al predefined_classes.txt (raíz del proyecto LabelImg)
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.abspath(os.path.join(_PLUGIN_DIR, "..", "..", ".."))
PREDEFINED_CLASSES_PATH = os.path.join(_ROOT_DIR, "data", "predefined_classes.txt")


class ClassSyncPlugin:

    def __init__(self, main_window):
        self.main_window = main_window
        self._current_watched_file = None
        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._on_classes_file_changed)
        self._last_checked_dir = None
        self._missing_classes_cache = {}
        self._missing_log_cooldown_sec = 30

        self._patch_methods()
        self._add_menu_action()

        print(f"[ClassSync] Plugin iniciado. ROOT: {_ROOT_DIR}")
        print(f"[ClassSync] predefined_classes.txt -> {PREDEFINED_CLASSES_PATH}")

    # ------------------------------------------------------------------
    # Monkey-patching
    # ------------------------------------------------------------------

    def _patch_methods(self):
        self._patch("import_dir_images", self._after_import_dir)
        self._patch("open_dir_dialog",   self._after_open_dir)
        self._patch("load_file",          self._after_load_file)

    def _patch(self, method_name, after_hook):
        original = getattr(self.main_window, method_name, None)
        if original is None:
            return
        tag = f"_class_sync_patched_{method_name}"
        if getattr(original, tag, False):
            return

        def make_wrapper(orig, hook):
            def wrapper(*args, **kwargs):
                result = orig(*args, **kwargs)
                try:
                    hook(args, kwargs)
                except Exception as e:
                    print(f"[ClassSync] Error en hook de {method_name}: {e}")
                return result
            setattr(wrapper, tag, True)
            return wrapper

        setattr(self.main_window, method_name, make_wrapper(original, after_hook))

    # ------------------------------------------------------------------
    # Hooks post-ejecución
    # ------------------------------------------------------------------

    def _after_import_dir(self, args, kwargs):
        dir_path = args[0] if args else kwargs.get("dir_path", None)
        print(f"[ClassSync] _after_import_dir -> dir_path={dir_path}")
        if dir_path:
            self._try_sync_from_dir(dir_path, force=True)

    def _after_open_dir(self, args, kwargs):
        QTimer.singleShot(300, self._sync_from_last_open_dir)

    def _after_load_file(self, args, kwargs):
        file_path = args[0] if args else kwargs.get("file_path", None)
        if file_path and os.path.isfile(str(file_path)):
            self._try_sync_from_dir(os.path.dirname(str(file_path)))

    def _sync_from_last_open_dir(self):
        d = self.main_window.last_open_dir
        print(f"[ClassSync] _sync_from_last_open_dir -> {d}")
        if d and os.path.isdir(d):
            self._try_sync_from_dir(d, force=True)

    # ------------------------------------------------------------------
    # Lógica principal
    # ------------------------------------------------------------------

    def _try_sync_from_dir(self, dir_path, force=False):
        if not dir_path or not os.path.isdir(str(dir_path)):
            print(f"[ClassSync] Carpeta inválida: {dir_path}")
            return

        norm_dir = os.path.normcase(os.path.abspath(str(dir_path)))
        classes_path = os.path.join(norm_dir, DATASET_CLASSES_FILENAME)

        # En navegación normal (load_file), no reevaluar la misma carpeta en cada imagen.
        if not force and norm_dir == self._last_checked_dir:
            return
        self._last_checked_dir = norm_dir

        if not os.path.isfile(classes_path):
            now = time.time()
            last_log = self._missing_classes_cache.get(norm_dir, 0)
            if force or (now - last_log) >= self._missing_log_cooldown_sec:
                print(f"[ClassSync] No encontrado: {classes_path}")
                self._missing_classes_cache[norm_dir] = now
            return

        print(f"[ClassSync] Encontrado. Sincronizando...")
        # Si aparece el archivo, limpiar cache de faltantes para esa carpeta.
        self._missing_classes_cache.pop(norm_dir, None)
        self._watch_file(classes_path)
        self._sync_classes(classes_path)

    def _sync_classes(self, classes_path):
        raw_lines = []
        # Intento 1: UTF-8
        try:
            with codecs.open(classes_path, "r", "utf-8") as f:
                raw_lines = f.readlines()
        except UnicodeDecodeError:
            # Intento 2: Latin-1 (para compatibilidad con acentos en Windows)
            try:
                with codecs.open(classes_path, "r", "latin-1") as f:
                    raw_lines = f.readlines()
                print(f"[ClassSync] Archivo leído con codificación latin-1")
            except Exception as e:
                print(f"[ClassSync] Error leyendo {classes_path}: {e}")
                return
        except Exception as e:
            print(f"[ClassSync] Error leyendo {classes_path}: {e}")
            return

        classes = [line.strip() for line in raw_lines if line.strip()]
        print(f"[ClassSync] Clases leídas: {classes}")

        if not classes:
            self._status("[ClassSync] classes.txt vacío — sin cambios.")
            return

        # 1. Escribir predefined_classes.txt
        self._write_predefined(classes)

        # 2. Actualizar label_hist en memoria
        self.main_window.label_hist = classes[:]

        # 3. Actualizar default_label
        if classes:
            self.main_window.default_label = classes[0]

        # 4. Refrescar combo de etiqueta por defecto
        self._refresh_default_label_combo(classes)

        # 5. Recrear LabelDialog
        self._refresh_label_dialog(classes)

        # 6. Notificar
        folder_name = os.path.basename(os.path.dirname(classes_path))
        self._status(f"✔ {len(classes)} clases cargadas desde '{folder_name}'")
        print(f"[ClassSync] [OK] Sincronización completa: {classes}")

    def _write_predefined(self, classes):
        try:
            os.makedirs(os.path.dirname(PREDEFINED_CLASSES_PATH), exist_ok=True)
            with codecs.open(PREDEFINED_CLASSES_PATH, "w", "utf-8") as f:
                f.write("\n".join(classes) + "\n")
            print(f"[ClassSync] predefined_classes.txt actualizado en: {PREDEFINED_CLASSES_PATH}")
        except Exception as e:
            print(f"[ClassSync] Error escribiendo predefined_classes.txt: {e}")

    def _refresh_default_label_combo(self, classes):
        try:
            combo = self.main_window.default_label_combo_box
            cb = combo.cb
            
            current_text = cb.currentText()
            
            cb.blockSignals(True)
            cb.clear()
            for c in classes:
                cb.addItem(c)
                
            index = cb.findText(current_text)
            if index >= 0:
                cb.setCurrentIndex(index)
                self.main_window.default_label = current_text
            else:
                cb.setCurrentIndex(0)
                if classes:
                    self.main_window.default_label = classes[0]
                    
            cb.blockSignals(False)
        except Exception as e:
            print(f"[ClassSync] Error actualizando combo: {e}")

    def _refresh_label_dialog(self, classes):
        try:
            from libs.labelDialog import LabelDialog
            self.main_window.label_dialog = LabelDialog(
                parent=self.main_window,
                list_item=classes
            )
            print("[ClassSync] LabelDialog recreado con nuevas clases.")
        except Exception as e:
            print(f"[ClassSync] Error recreando LabelDialog: {e}")

    # ------------------------------------------------------------------
    # Watcher
    # ------------------------------------------------------------------

    def _watch_file(self, file_path):
        if self._current_watched_file and self._current_watched_file != file_path:
            self._watcher.removePath(self._current_watched_file)
        if file_path not in self._watcher.files():
            self._watcher.addPath(file_path)
        self._current_watched_file = file_path

    def _on_classes_file_changed(self, path):
        print(f"[ClassSync] Cambio detectado en disco: {path}")
        if os.path.isfile(path):
            self._sync_classes(path)

    # ------------------------------------------------------------------
    # Menú manual
    # ------------------------------------------------------------------

    def _add_menu_action(self):
        try:
            action = QAction("🔄 Sincronizar clases (classes.txt)", self.main_window)
            action.setStatusTip("Recarga las clases desde el classes.txt de la carpeta actual")
            action.triggered.connect(self._manual_sync)
            self.main_window.menus.file.addSeparator()
            self.main_window.menus.file.addAction(action)
        except Exception as e:
            print(f"[ClassSync] No se pudo añadir acción al menú: {e}")

    def _manual_sync(self):
        dir_path = None
        if self.main_window.last_open_dir and os.path.isdir(self.main_window.last_open_dir):
            dir_path = self.main_window.last_open_dir
        elif self.main_window.file_path and os.path.isfile(str(self.main_window.file_path)):
            dir_path = os.path.dirname(str(self.main_window.file_path))

        print(f"[ClassSync] Sincronización manual. Carpeta: {dir_path}")

        if dir_path:
            self._try_sync_from_dir(dir_path, force=True)
        else:
            self._status("[ClassSync] No hay carpeta abierta para sincronizar.")

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _status(self, message, delay=5000):
        try:
            self.main_window.statusBar().showMessage(message, delay)
        except Exception:
            try:
                print(message)
            except UnicodeEncodeError:
                print(message.encode('ascii', 'ignore').decode('ascii'))


# ----------------------------------------------------------------------
# Punto de entrada
# ----------------------------------------------------------------------

def setup(main_window):
    plugin = ClassSyncPlugin(main_window)
    main_window._class_sync_plugin = plugin
    return plugin