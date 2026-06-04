# =============================================================================
# custom/loader.py
# =============================================================================
# PROPÓSITO: Cargador dinámico de plugins con soporte de auto-habilitación.
# =============================================================================

import importlib
import json
import os
import pkgutil
import time


class PluginLoader:
    @staticmethod
    def _load_plugin(main_window, plugin_name):
        try:
            module_name = f"custom.plugins.{plugin_name}.core"
            module = importlib.import_module(module_name)

            if hasattr(module, "setup"):
                module.setup(main_window)
                if not hasattr(main_window, "_loaded_plugins"):
                    main_window._loaded_plugins = set()
                main_window._loaded_plugins.add(plugin_name)
                print(
                    f"[Loader] Success: {plugin_name} (v{getattr(module, '__version__', '?.?')})"
                )
            else:
                print(f"[Loader] Warning: {plugin_name} no tiene función setup()")
        except Exception as e:
            print(f"[Loader] Error cargando {plugin_name}: {e}")

    @staticmethod
    def load_all(main_window):
        """Descubre e inicializa plugins desde custom/plugins/."""
        # Usar ruta absoluta basada en este archivo
        base_dir = os.path.dirname(os.path.abspath(__file__))
        plugins_dir = os.path.join(base_dir, "plugins")
        config_path = os.path.join(base_dir, "config.json")

        # Cargar configuración de habilitación
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except:
                pass

        print("--- Cargando Plugins ---")

        plugin_names = [
            name for _, name, ispkg in pkgutil.iter_modules([plugins_dir]) if ispkg
        ]

        # El plugin_manager es crítico y siempre se carga primero.
        plugin_manager_name = "gestor_plugins"
        if plugin_manager_name in plugin_names:
            PluginLoader._load_plugin(main_window, plugin_manager_name)
            if plugin_manager_name not in config:
                config[plugin_manager_name] = True
            plugin_names.remove(plugin_manager_name)

        for name in plugin_names:
            if name not in config:
                if name == "visualizador":
                    config[name] = False
                else:
                    config[name] = True

            if not config[name]:
                print(f"[Loader] Skipped: {name} (desactivado)")
                continue

            PluginLoader._load_plugin(main_window, name)

        # Guardar configuración actualizada
        try:
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)
        except:
            pass

        print("------------------------")

        if os.environ.get("LABELIMG_PROFILE", "").strip() in ("1", "true", "yes"):
            PluginLoader._install_profiler(main_window)

    @staticmethod
    def _install_profiler(main_window):
        """
        Activa trazas de rendimiento en consola.
        Uso (PowerShell):
            $env:LABELIMG_PROFILE="1"
            python labelImg.py
        """
        threshold_ms = float(os.environ.get("LABELIMG_PROFILE_MS", "5"))

        def wrap(method_name):
            original = getattr(main_window, method_name, None)
            if original is None or getattr(original, "_perf_wrapped", False):
                return

            def wrapper(*args, **kwargs):
                t0 = time.perf_counter()
                result = original(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if elapsed_ms >= threshold_ms:
                    n_shapes = len(getattr(main_window.canvas, "shapes", []))
                    n_items = main_window.label_list.count() if hasattr(main_window, "label_list") else 0
                    plugins = sorted(getattr(main_window, "_loaded_plugins", []))
                    print(
                        f"[PERF] {method_name}: {elapsed_ms:.1f} ms | "
                        f"shapes={n_shapes} items={n_items} | plugins={plugins}"
                    )
                return result

            wrapper._perf_wrapped = True
            setattr(main_window, method_name, wrapper)

        for name in ("load_file", "load_labels", "update_combo_box", "paint_canvas", "show_bounding_box_from_annotation_file"):
            wrap(name)

        print("[PERF] Profiler activo. Cambia de imagen y revisa tiempos en consola.")
