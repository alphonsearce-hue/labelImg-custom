import json
import os
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QMessageBox


__version__ = "1.0.0"
__description__ = "Respaldo continuo del archivo activo con recuperación tras cierre inesperado."


def setup(main_window):
    plugin = SessionBackupManagerPlugin(main_window)
    main_window._session_backup_manager = plugin
    return plugin


class SessionBackupManagerPlugin:
    def __init__(self, main_window):
        self.mw = main_window
        self.canvas = main_window.canvas
        self._restoring = False

        backup_dir = os.path.join("custom", "autosave_backup")
        os.makedirs(backup_dir, exist_ok=True)
        self.backup_path = os.path.join(backup_dir, "working_copy.json")

        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(lambda: self._write_backup(dirty=True))

        self.backup_dir = backup_dir
        self.backup_path = os.path.join(backup_dir, "working_copy.json")
        self.last_stable_path = os.path.join(backup_dir, "last_stable_backup.json")

        self._patch_methods()

    def _patch_methods(self):
        original_set_dirty = self.mw.set_dirty
        original_load_file = self.mw.load_file
        original_save_file_internal = self.mw._save_file

        def wrapped_set_dirty(*args, **kwargs):
            result = original_set_dirty(*args, **kwargs)
            if not self._restoring and self.mw.file_path:
                self.save_timer.start(120)
            return result

        def wrapped_load_file(*args, **kwargs):
            result = original_load_file(*args, **kwargs)
            if result and self.mw.file_path:
                recovered = self._prompt_recovery_if_available(self.mw.file_path)
                if not recovered:
                    self._write_backup(dirty=False)
            return result

        def wrapped_save_file_internal(*args, **kwargs):
            result = original_save_file_internal(*args, **kwargs)
            if self.mw.file_path and not self.mw.dirty:
                self._write_backup(dirty=False)
            return result

        self.mw.set_dirty = wrapped_set_dirty
        self.mw.load_file = wrapped_load_file
        self.mw._save_file = wrapped_save_file_internal

    def _snapshot(self):
        shapes = []
        for shape in self.canvas.shapes:
            shapes.append(
                {
                    "label": shape.label or "",
                    "points": [[float(p.x()), float(p.y())] for p in shape.points],
                    "line_color": list(shape.line_color.getRgb()),
                    "fill_color": list(shape.fill_color.getRgb()),
                    "difficult": bool(getattr(shape, "difficult", False)),
                    "visible": bool(self.canvas.isVisible(shape)),
                }
            )
        return {"file_path": self.mw.file_path, "shapes": shapes}

    def _write_backup(self, dirty):
        if not self.mw.file_path:
            return

        payload = {
            "file_path": self.mw.file_path,
            "dirty": bool(dirty),
            "updated_at": datetime.utcnow().isoformat(),
            "snapshot": self._snapshot(),
        }
        
        try:
            # Si el archivo actual es "estable" (no dirty), guardarlo como respaldo principal
            if not dirty:
                if os.path.exists(self.backup_path):
                    import shutil
                    shutil.copy2(self.backup_path, self.last_stable_path)
            
            with open(self.backup_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    def _read_backup(self):
        if not os.path.exists(self.backup_path):
            return None
        try:
            with open(self.backup_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _prompt_recovery_if_available(self, loaded_file_path):
        backup = self._read_backup()
        if not backup:
            return False

        if backup.get("file_path") != loaded_file_path:
            return False
        if not backup.get("dirty", False):
            return False

        reply = QMessageBox.question(
            self.mw,
            "Recuperar respaldo",
            "Se detectó un respaldo no guardado para esta imagen.\n¿Deseas cargarlo?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return False

        snapshot = backup.get("snapshot")
        if not snapshot:
            return False

        # Aseguramos que el path sea el mismo (normalizado)
        if os.path.normpath(backup.get("file_path", "")) != os.path.normpath(self.mw.file_path):
            return False

        self._restore_state(snapshot)
        self._write_backup(dirty=True)
        return True

    def _restore_state(self, state):
        if state.get("file_path") != self.mw.file_path:
            return

        self._restoring = True
        try:
            self.mw.items_to_shapes.clear()
            self.mw.shapes_to_items.clear()
            self.mw.label_list.clear()
            self.canvas.shapes = []
            self.canvas.visible = {}
            self.canvas.clear_selection()

            tuples_for_load = []
            visibility = []
            for entry in state.get("shapes", []):
                tuples_for_load.append(
                    (
                        entry.get("label", ""),
                        entry.get("points", []),
                        entry.get("line_color"),
                        entry.get("fill_color"),
                        entry.get("difficult", False),
                    )
                )
                visibility.append(bool(entry.get("visible", True)))

            self.mw.load_labels(tuples_for_load)
            for index, shape in enumerate(self.canvas.shapes):
                visible = visibility[index] if index < len(visibility) else True
                self.canvas.set_shape_visible(shape, visible)
                item = self.mw.shapes_to_items.get(shape)
                if item:
                    item.setCheckState(Qt.Checked if visible else Qt.Unchecked)

            self.canvas.update()
            self.mw.set_dirty()
            
            # Forzar actualización de la lista de clases para que el usuario vea el cambio
            if hasattr(self.mw, 'update_combo_box'):
                self.mw.update_combo_box()
            
            # Mostrar mensaje de éxito
            self.mw.statusBar().showMessage("Respaldo restaurado correctamente.", 3000)
        finally:
            self._restoring = False

