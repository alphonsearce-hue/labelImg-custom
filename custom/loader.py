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
    def _load_plugin(main_window, plugin_name):
        try:
            module_name = f"custom.plugins.{plugin_name}.core"
            module = importlib.import_module(module_name)

            if hasattr(module, "setup"):
                module.setup(main_window)
                print(f"[Loader] Success: {plugin_name} (v{getattr(module, '__version__', '?.?')})")
            else:
                print(f"[Loader] Warning: {plugin_name} no tiene función setup()")
        except Exception as e:
            print(f"[Loader] Error cargando {plugin_name}: {e}")

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

        plugin_names = [
            name for _, name, ispkg in pkgutil.iter_modules([plugins_dir]) if ispkg
        ]

        # El plugin_manager es crítico y siempre se carga primero.
        plugin_manager_name = "plugin_manager"
        if plugin_manager_name in plugin_names:
            PluginLoader._load_plugin(main_window, plugin_manager_name)
            if plugin_manager_name not in config:
                config[plugin_manager_name] = True
            plugin_names.remove(plugin_manager_name)

        for name in plugin_names:
            if name not in config:
                config[name] = True

            if not config[name]:
                print(f"[Loader] Skipped: {name} (desactivado)")
                continue

            PluginLoader._load_plugin(main_window, name)

        # Guardar configuración actualizada
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except: pass
        
        print("------------------------")
