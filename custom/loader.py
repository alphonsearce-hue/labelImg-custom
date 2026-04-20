# =============================================================================
# custom/loader.py
# =============================================================================
# PROPÓSITO: Cargador dinámico de plugins con soporte de auto-habilitación.
# =============================================================================

import os
import json
import importlib
import pkgutil

class PluginLoader:
    @staticmethod
    def load_all(main_window):
        """Descubre e inicializa plugins desde custom/plugins/."""
        plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        
        # Cargar configuración de habilitación
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
            except: pass

        print("--- Cargando Plugins ---")
        
        # Recorrer subcarpetas de custom/plugins/
        for finder, name, ispkg in pkgutil.iter_modules([plugins_dir]):
            if ispkg:
                # Si el plugin no está en el config, lo habilitamos por defecto
                if name not in config:
                    config[name] = True
                
                if not config[name]:
                    print(f"[Loader] Skipped: {name} (desactivado)")
                    continue

                try:
                    # Importar el módulo core de la subcarpeta
                    module_name = f"custom.plugins.{name}.core"
                    module = importlib.import_module(module_name)
                    
                    # Ejecutar setup(main_window)
                    if hasattr(module, "setup"):
                        module.setup(main_window)
                        print(f"[Loader] Success: {name} (v{getattr(module, '__version__', '?.?')})")
                    else:
                        print(f"[Loader] Warning: {name} no tiene función setup()")
                except Exception as e:
                    print(f"[Loader] Error cargando {name}: {e}")

        # Guardar configuración actualizada
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except: pass
        
        print("------------------------")
