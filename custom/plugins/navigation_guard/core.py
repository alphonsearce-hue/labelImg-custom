import os
from PyQt5.QtWidgets import QMessageBox


__version__ = "1.0.0"
__description__ = "Bloquea el cambio de imagen si hay cambios sin guardar hasta confirmación explícita."


def setup(main_window):
    plugin = NavigationGuardPlugin(main_window)
    return plugin


class NavigationGuardPlugin:
    def __init__(self, main_window):
        self.mw = main_window
        self._patch_navigation()

    def _patch_navigation(self):
        # Guardamos referencias originales
        self.original_open_next = self.mw.open_next_image
        self.original_open_prev = self.mw.open_prev_image
        self.original_load_recent = self.mw.load_recent

        # Redefinimos con guardias
        self.mw.open_next_image = self._wrapped_next
        self.mw.open_prev_image = self._wrapped_prev
        self.mw.load_recent = self._wrapped_load_recent

    def _can_navigate(self):
        if not self.mw.dirty:
            return True

        msg = (
            "Tienes cambios sin guardar en esta imagen.\n\n"
            "¿Qué deseas hacer?\n"
            "• [Guardar] para conservar cambios y continuar.\n"
            "• [Descartar] para perder cambios y continuar.\n"
            "• [Cancelar] para quedarte en esta imagen."
        )
        
        msg_box = QMessageBox(self.mw)
        msg_box.setWindowTitle("Cambios sin guardar")
        msg_box.setText(msg)
        msg_box.setIcon(QMessageBox.Warning)
        
        save_btn = msg_box.addButton("Guardar y Continuar", QMessageBox.AcceptRole)
        discard_btn = msg_box.addButton("Descartar y Continuar", QMessageBox.DestructiveRole)
        cancel_btn = msg_box.addButton("Cancelar", QMessageBox.RejectRole)
        
        msg_box.setDefaultButton(save_btn)
        msg_box.exec_()
        
        clicked = msg_box.clickedButton()
        
        if clicked == save_btn:
            self.mw.save_file()
            return True
        elif clicked == discard_btn:
            # Para descartar, simplemente limpiamos el dirty
            self.mw.set_clean()
            return True
        else:
            return False

    def _wrapped_next(self, _value=False):
        if self._can_navigate():
            self.original_open_next(_value)

    def _wrapped_prev(self, _value=False):
        if self._can_navigate():
            self.original_open_prev(_value)

    def _wrapped_load_recent(self, filename):
        if self._can_navigate():
            self.original_load_recent(filename)
