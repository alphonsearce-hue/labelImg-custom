# =============================================================================
# custom/plugins/robust_autosave/core.py
# =============================================================================
# PROPÓSITO: Guardado automático redundante con optimización de rendimiento.
# =============================================================================

__version__ = "1.1.0"
__description__ = "Guardado automático robusto con debounce (1s) para evitar lag."

import os
import json
import datetime
from PyQt5.QtCore import QTimer
from libs.pascal_voc_io import PascalVocWriter

class RobustAutoSave:
    def __init__(self, main_window):
        self.main_window = main_window
        self.backup_dir = os.path.join(os.getcwd(), "custom", "autosave_backup")
        os.makedirs(self.backup_dir, exist_ok=True)
        
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._do_save)
        
        self._setup_hooks()

    def _setup_hooks(self):
        self.main_window.canvas.newShape.connect(self.trigger_save)
        self.main_window.canvas.shapeMoved.connect(self.trigger_save)
        
        original_delete = self.main_window.delete_selected_shape
        def hooked_delete(*args, **kwargs):
            res = original_delete(*args, **kwargs)
            self.trigger_save()
            return res
        self.main_window.delete_selected_shape = hooked_delete

    def trigger_save(self):
        if self.main_window.file_path:
            self.save_timer.start(1000)

    def _do_save(self):
        try:
            img_path = self.main_window.file_path
            img_folder = os.path.dirname(img_path)
            img_name = os.path.basename(img_path)
            base_name = os.path.splitext(img_name)[0]
            
            shapes = self.main_window.canvas.shapes
            img_size = self.main_window.image.size()
            w, h = img_size.width(), img_size.height()

            # 1. Guardado XML PascalVOC
            xml_path = os.path.join(img_folder, base_name + ".xml")
            writer = PascalVocWriter(img_folder, img_name, (h, w, 3))
            for shape in shapes:
                points = shape.points
                label = shape.label
                xmin = int(min(p.x() for p in points))
                ymin = int(min(p.y() for p in points))
                xmax = int(max(p.x() for p in points))
                ymax = int(max(p.y() for p in points))
                writer.add_object(label, xmin, ymin, xmax, ymax)
            writer.save(xml_path)

            # 2. Shadow Copy
            self._save_emergency_shadow_copy(base_name)
            
            self.main_window.statusBar().showMessage(f"💾 Auto-guardado exitoso: {base_name}", 2000)
        except Exception as e:
            print(f"[AutoSave Error] {e}")

    def _save_emergency_shadow_copy(self, base_name):
        backup_path = os.path.join(self.backup_dir, f"{base_name}_backup.json")
        data = {
            "image": self.main_window.file_path,
            "shapes": [{"label": s.label, "points": [[p.x(), p.y()] for p in s.points]} for s in self.main_window.canvas.shapes]
        }
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

def setup(main_window):
    main_window._robust_autosave = RobustAutoSave(main_window)
